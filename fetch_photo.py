"""Fetch a high-quality, attractive stock photo from Pexels for photo-forward
cards. Returns a local file path + a photographer credit line.

Needs PEXELS_API_KEY in the environment. Picks a large, well-sized image for the
requested orientation and avoids recently-used photo IDs.
"""
from __future__ import annotations

import io
import json
import os
import random
from pathlib import Path

import requests
from PIL import Image

_API = "https://api.pexels.com/v1/search"
_HISTORY = Path(__file__).parent / "output" / ".photo_history.json"


def _recent() -> list[int]:
    try:
        return [int(x) for x in json.loads(_HISTORY.read_text())]
    except Exception:
        return []


def _remember(pid: int) -> None:
    ids = (_recent() + [int(pid)])[-200:]
    try:
        _HISTORY.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY.write_text(json.dumps(ids))
    except Exception:
        pass


def _best(photo: dict) -> str | None:
    src = photo.get("src", {})
    for k in ("original", "large2x", "large", "landscape"):
        if src.get(k):
            return src[k]
    return None


def fetch(queries, out_path, orientation: str = "landscape",
          min_w: int = 1200) -> dict | None:
    """Download an attractive Pexels photo for the first query that yields one.

    ``queries`` may be a string or a list (tried in order). Returns
    {path, credit, url, photographer} or None on failure.
    """
    key = (os.getenv("PEXELS_API_KEY") or "").strip()
    if not key:
        return None
    if isinstance(queries, str):
        queries = [queries]
    out_path = Path(out_path)
    used = set(_recent())
    headers = {"Authorization": key}

    for q in queries:
        try:
            params = {"query": q, "orientation": orientation, "size": "large",
                      "per_page": 40, "page": random.randint(1, 2)}
            r = requests.get(_API, headers=headers, params=params, timeout=20)
            r.raise_for_status()
            photos = r.json().get("photos", []) or []
        except Exception as exc:
            print(f"  Pexels search failed for '{q}' ({exc})")
            continue
        # Prefer large, unused, well-sized photos.
        photos = [p for p in photos if p.get("width", 0) >= min_w]
        random.shuffle(photos)
        ordered = [p for p in photos if p.get("id") not in used] or photos
        for p in ordered:
            url = _best(p)
            if not url:
                continue
            try:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                img.save(out_path, quality=92)
                _remember(p.get("id"))
                who = p.get("photographer", "Pexels")
                print(f"  Pexels photo: '{q}' -> {p.get('id')} by {who}")
                return {"path": str(out_path), "photographer": who,
                        "credit": f"Photo: {who} / Pexels", "url": p.get("url", "")}
            except Exception as exc:
                print(f"  download failed ({exc}); next")
                continue
    return None
