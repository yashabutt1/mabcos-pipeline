"""Pull REAL, UPCOMING biotech events (conferences, workshops, seminars) from
curated listing sites, so 'Event' posts carry a real date, place and link.

Only future-dated events are returned — a stale/expired conference must never post.
Each site has its own small parser; a site that changes layout just yields nothing
(fails soft) and the caller falls back to Gemini search or the local bank.

Needs requests. Fails soft on any dead/blocked site.
"""
from __future__ import annotations

import datetime
import re

import requests

_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")}

_MON = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _today() -> datetime.date:
    return datetime.date.today()


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = s.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#039;", "'").replace("&rsquo;", "’")
    return re.sub(r"\s+", " ", s).strip()


def _get(url: str) -> str:
    r = requests.get(url, headers=_UA, timeout=30)
    r.raise_for_status()
    return r.text


def _iso_from_text(text: str):
    """Parse 'November 9-11, 2026' / 'Nov 3 2026' → (iso, 'Nov 9–11, 2026'). None if unparseable."""
    m = re.search(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?,?\s+(20\d{2})", text or "")
    if not m:
        return None
    mon = _MON.get(m.group(1)[:3].lower())
    if not mon:
        return None
    try:
        d1 = datetime.date(int(m.group(4)), mon, int(m.group(2)))
    except ValueError:
        return None
    label = m.group(1)[:3].title()
    span = f"{label} {int(m.group(2))}" + (f"–{int(m.group(3))}" if m.group(3) else "") + f", {m.group(4)}"
    return d1.isoformat(), span


def _human(iso: str) -> str:
    d = datetime.date.fromisoformat(iso)
    return f"{d.strftime('%b')} {d.day}, {d.year}"


# --------------------------------------------------------------------------- allconferencealert
def _parse_allconf() -> list[dict]:
    html = _get("https://www.allconferencealert.com/usa/biotechnology")
    out = []
    for block in html.split('class="event-card"')[1:]:
        a = re.search(r'<a href="([^"]+)"[^>]*>\s*([^<]{8,140}?)\s*</a>', block)
        t = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})"', block)
        if not (a and t):
            continue
        if datetime.date.fromisoformat(t.group(1)) < _today():
            continue
        loc = re.search(r'fa-map-marker-alt[^>]*></i>\s*<span>\s*([^<]+?)\s*</span>', block)
        out.append({"title": _clean(a.group(2)), "link": a.group(1).strip(),
                    "date_iso": t.group(1), "date": _human(t.group(1)),
                    "location": _clean(loc.group(1)) if loc else "", "source": "All Conference Alert"})
    return out


# --------------------------------------------------------------------------- bio.org
def _parse_bioorg() -> list[dict]:
    html = _get("https://www.bio.org/events")
    out = []
    for block in html.split("mc-tileImage__link")[1:]:
        href = re.search(r'href="([^"]+)"', block)
        title = re.search(r'mc-tileImage__title[^>]*>\s*<div[^>]*>\s*([^<]{4,140}?)\s*</div>', block)
        desc = re.search(r'mc-tileImage__description.*?<p>(.*?)</p>', block, re.S)
        if not (href and title and desc):
            continue
        parts = re.split(r"<br\s*/?>", desc.group(1))
        parsed = _iso_from_text(_clean(parts[0]))
        if not parsed:
            continue
        iso, span = parsed
        if datetime.date.fromisoformat(iso) < _today():
            continue
        loc = _clean(parts[1]) if len(parts) > 1 else ""
        out.append({"title": _clean(title.group(1)), "link": href.group(1).strip(),
                    "date_iso": iso, "date": span, "location": loc, "source": "BIO.org"})
    return out


# --------------------------------------------------------------------------- innovatebio.org
def _parse_innovatebio() -> list[dict]:
    html = _get("https://innovatebio.org/events")
    out = []
    # Each event is a <h2><a href="/event/…">Title</a></h2> followed (within ~2.5k chars)
    # by its smartdate <time>. Pair each title with the nearest following date.
    for m in re.finditer(r'<h2>\s*<a href="(/event/[^"]+)"[^>]*>\s*([^<]{5,140}?)\s*</a>', html):
        t = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})"', html[m.end():m.end() + 2500])
        if not t or datetime.date.fromisoformat(t.group(1)) < _today():
            continue
        out.append({"title": _clean(m.group(2)), "link": "https://innovatebio.org" + m.group(1),
                    "date_iso": t.group(1), "date": _human(t.group(1)),
                    "location": "", "source": "InnovATEBIO"})
    return out


_PARSERS = (_parse_allconf, _parse_bioorg, _parse_innovatebio)


def fetch_events(max_per_site: int = 8) -> list[dict]:
    """Future-dated {title, link, date, date_iso, location, source}, soonest first."""
    items, seen = [], set()
    for parse in _PARSERS:
        try:
            got = parse()
        except Exception as exc:
            print(f"  event source {parse.__name__} failed ({exc})")
            continue
        for it in got[:max_per_site]:
            key = re.sub(r"[^a-z0-9]", "", it["title"].lower())[:50]
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(it)
    items.sort(key=lambda x: x["date_iso"])
    return items


def domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""
