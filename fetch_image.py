"""Fetch attractive stock photos from Pexels for card backgrounds.

Given a topic (or a plain search query) this searches Pexels for a high-quality
portrait photo, downloads it, and crops it to the card size. Recently-used photo
IDs are remembered so the same image doesn't come back two days in a row.

Everything here fails *soft*: if there is no PEXELS_API_KEY, the network is down,
or nothing suitable is found, the functions return None and the caller falls back
to the locally-drawn gradient background.
"""
from __future__ import annotations

import io
import json
import os
import random
from pathlib import Path

import requests
from PIL import Image

import config

_API_URL = "https://api.pexels.com/v1/search"
_HISTORY_FILE = ".pexels_history.json"
_RECENT_IDS = 120  # how many recently-used photo ids to remember


def _api_key() -> str | None:
    key = os.getenv("PEXELS_API_KEY")
    return key.strip() if key else None


def _history_path() -> Path:
    return config.OUTPUT_DIR / _HISTORY_FILE


def _load_used_ids() -> list[int]:
    try:
        data = json.loads(_history_path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [int(x) for x in data]
    except Exception:
        pass
    return []


def _remember_id(photo_id: int) -> None:
    ids = _load_used_ids()
    ids.append(int(photo_id))
    ids = ids[-_RECENT_IDS:]
    try:
        _history_path().parent.mkdir(parents=True, exist_ok=True)
        _history_path().write_text(json.dumps(ids), encoding="utf-8")
    except Exception:
        pass


def _cover_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Resize + center-crop so the image fully covers a w×h frame (no bars)."""
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(w / src_w, h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def _search(query: str, key: str, per_page: int = 40) -> list[dict]:
    headers = {"Authorization": key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "large",
        "per_page": per_page,
        # Nudge toward a fresh page so popular top results don't dominate.
        "page": random.randint(1, 3),
    }
    resp = requests.get(_API_URL, headers=headers, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("photos", []) or []


def _best_src(photo: dict) -> str | None:
    src = photo.get("src", {})
    for key in ("original", "large2x", "portrait", "large"):
        if src.get(key):
            return src[key]
    return None


def fetch_background(topic_or_query, out_path, w: int | None = None, h: int | None = None) -> str | None:
    """Download a topic-matched Pexels photo cropped to the card size.

    ``topic_or_query`` may be a topic dict (uses its ``pexels_queries``) or a
    plain string. Returns the saved path, or None if anything goes wrong so the
    caller can fall back to a local gradient.
    """
    key = _api_key()
    if not key:
        return None

    w = w or config.CARD_W
    h = h or config.CARD_H
    out_path = Path(out_path)

    if isinstance(topic_or_query, dict):
        # Curated queries first (shuffled among themselves); the topic id is a
        # weak last resort because it often returns literal matches (e.g.
        # "small gestures" -> mannequin hands) rather than romantic scenes.
        queries = list(topic_or_query.get("pexels_queries") or [])
        random.shuffle(queries)
        if topic_or_query.get("id"):
            queries.append(topic_or_query["id"].replace("_", " "))
    else:
        queries = [str(topic_or_query)]

    used = set(_load_used_ids())

    for query in queries:
        try:
            photos = _search(query, key)
        except Exception as exc:
            print(f"  Pexels search failed for '{query}' ({exc})")
            continue
        if not photos:
            continue

        random.shuffle(photos)
        # Prefer a photo we haven't used recently; otherwise take any.
        ordered = [p for p in photos if p.get("id") not in used] or photos

        for photo in ordered:
            url = _best_src(photo)
            if not url:
                continue
            try:
                img_resp = requests.get(url, timeout=30)
                img_resp.raise_for_status()
                img = Image.open(io.BytesIO(img_resp.content))
                img = _cover_crop(img, w, h)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(out_path)
                _remember_id(photo.get("id"))
                print(f"  Pexels: '{query}' -> photo {photo.get('id')} by "
                      f"{photo.get('photographer', 'unknown')}")
                return str(out_path)
            except Exception as exc:
                print(f"  Pexels download/crop failed ({exc}); trying next")
                continue

    return None
