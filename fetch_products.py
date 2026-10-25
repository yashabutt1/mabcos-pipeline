"""Amazon Associates product picker (manual-link mode, no PA-API).

You curate a pool of best-seller links in products.txt (one "name | url" per
line). This module parses that pool, ensures YOUR Associate tag is on every
link, and picks a few products per day that haven't been posted recently.

No Amazon scraping happens here — product discovery is your curation; we only
build the affiliate URL from a link you already chose, which is allowed under
the Associates Operating Agreement (it's your own tag).
"""
from __future__ import annotations

import csv
import io
import json
import os
import random
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

import requests

import config

_POSTED_FILE = ".product_posted.json"       # permanent: actually posted to FB
_SUGGESTED_FILE = ".product_suggested.json"  # short window: recently sent to Telegram
# When the number of never-posted products left drops to/below this, the daily
# run flags it so the pool can be refreshed before it runs dry.
LOW_POOL_THRESHOLD = 6

_ASIN_RE = re.compile(r"(?:/dp/|/gp/product/|/gp/aw/d/|/product/|/d/|asin=)([A-Z0-9]{10})", re.I)
_BARE_ASIN_RE = re.compile(r"/([A-Z0-9]{10})(?:[/?]|$)")


def _tag() -> str:
    return os.getenv("AMAZON_ASSOC_TAG", "").strip() or config.AMAZON_ASSOC_TAG


def _marketplace() -> str:
    return os.getenv("AMAZON_MARKETPLACE", "").strip() or config.AMAZON_MARKETPLACE or "www.amazon.com"


def extract_asin(url: str) -> str | None:
    m = _ASIN_RE.search(url) or _BARE_ASIN_RE.search(url)
    return m.group(1).upper() if m else None


def build_affiliate_url(url: str) -> str:
    """Return a clean product URL carrying our Associate tag."""
    tag = _tag()
    asin = extract_asin(url)
    if asin:
        base = f"https://{_marketplace()}/dp/{asin}/"
        return f"{base}?tag={tag}" if tag else base
    # Fallback: keep the given URL but set/replace the tag query param.
    parts = urlparse(url if "//" in url else "https://" + url)
    query = dict(parse_qsl(parts.query))
    if tag:
        query["tag"] = tag
    return urlunparse(parts._replace(query=urlencode(query)))


def _load_from_file() -> list[dict]:
    path = config.PRODUCTS_FILE
    if not path.exists():
        return []
    items = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        name, url = (p.strip() for p in line.split("|", 1))
        if not name or not url or "EXAMPLE" in url:
            continue
        items.append({"name": name, "url": url, "asin": extract_asin(url)})
    return items


def _load_from_sheet() -> list[dict]:
    """Read a published-to-web Google Sheet (CSV): columns Name | Amazon URL."""
    url = os.getenv("GOOGLE_SHEET_CSV_URL", "").strip() or config.GOOGLE_SHEET_CSV_URL
    if not url:
        return []
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        rows = list(csv.reader(io.StringIO(resp.text)))
    except Exception as exc:
        print(f"  Google Sheet fetch failed ({exc}); using local products only")
        return []
    items = []
    for row in rows:
        if not row:
            continue
        if len(row) >= 2:
            name, link = row[0].strip(), row[1].strip()
        elif "|" in row[0]:
            name, link = (p.strip() for p in row[0].split("|", 1))
        else:
            continue
        if not name or not link or "amazon" not in link.lower() and "/dp/" not in link:
            continue
        if name.lower() in ("name", "product", "title") or "EXAMPLE" in link:
            continue  # header row / placeholder
        items.append({"name": name, "url": link, "asin": extract_asin(link)})
    return items


def load_products() -> list[dict]:
    """Merge products from products.txt and the optional Google Sheet, deduped."""
    combined = _load_from_file() + _load_from_sheet()
    seen, unique = set(), []
    for it in combined:
        key = it.get("asin") or it.get("url")
        if key in seen:
            continue
        seen.add(key)
        unique.append(it)
    return unique


def _read_list(name: str) -> list[str]:
    try:
        data = json.loads((config.OUTPUT_DIR / name).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def _write_list(name: str, keys: list[str]) -> None:
    try:
        (config.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        (config.OUTPUT_DIR / name).write_text(json.dumps(keys), encoding="utf-8")
    except Exception:
        pass


def _key(item: dict) -> str:
    return item.get("asin") or item.get("url")


def mark_posted(key: str) -> None:
    """Permanently retire a product once it's actually been posted to Facebook."""
    if not key:
        return
    posted = _read_list(_POSTED_FILE)
    if key not in posted:
        posted.append(key)
        _write_list(_POSTED_FILE, posted)


def unposted_count() -> int:
    """How many never-POSTED products remain in the pool."""
    posted = set(_read_list(_POSTED_FILE))
    return len([p for p in load_products() if _key(p) not in posted])


def pick_products(n: int) -> list[dict]:
    """Pick up to n products to suggest.

    Excludes anything already POSTED (permanent) and anything suggested in the
    last couple of batches (so the same item doesn't reappear the very next day
    while it's pending). Rejected items simply return to the pool later — they're
    only retired for good once actually posted (see mark_posted, called on approve).
    """
    products = load_products()
    if not products:
        return []
    posted = set(_read_list(_POSTED_FILE))
    recent_suggested = set(_read_list(_SUGGESTED_FILE))

    # Prefer items neither posted nor just-suggested; fall back to not-posted.
    primary = [p for p in products if _key(p) not in posted and _key(p) not in recent_suggested]
    fallback = [p for p in products if _key(p) not in posted]
    random.shuffle(primary)
    random.shuffle(fallback)
    ordered, seen = [], set()
    for p in primary + fallback:
        k = _key(p)
        if k in seen:
            continue
        seen.add(k)
        ordered.append(p)

    chosen = ordered[:n]
    for p in chosen:
        p["affiliate_url"] = build_affiliate_url(p["url"])
    # Remember what we just suggested (keep a short rolling window).
    new_suggested = (_read_list(_SUGGESTED_FILE) + [_key(p) for p in chosen])[-(n * 3):]
    _write_list(_SUGGESTED_FILE, new_suggested)
    return chosen
