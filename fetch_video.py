"""Fetch free HD vertical stock video clips from Pexels for reels.

Given a topic (or a plain query) this finds a portrait video, downloads the best
vertical rendition near the target resolution, and remembers recently-used clip
IDs so a video is never reused. Fails soft (returns None) so the caller can skip.
Uses the same PEXELS_API_KEY as the photo backgrounds.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

import requests

import config

_API_URL = "https://api.pexels.com/videos/search"
_HISTORY_FILE = ".pexels_video_history.json"
_RECENT_IDS = 120


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


def _remember_id(video_id: int) -> None:
    ids = _load_used_ids()
    ids.append(int(video_id))
    ids = ids[-_RECENT_IDS:]
    try:
        _history_path().parent.mkdir(parents=True, exist_ok=True)
        _history_path().write_text(json.dumps(ids), encoding="utf-8")
    except Exception:
        pass


def _search(query: str, key: str, per_page: int = 30) -> list[dict]:
    headers = {"Authorization": key}
    params = {
        "query": query,
        "orientation": "portrait",
        "size": "medium",
        "per_page": per_page,
        "page": random.randint(1, 3),
    }
    resp = requests.get(_API_URL, headers=headers, params=params, timeout=25)
    resp.raise_for_status()
    return resp.json().get("videos", []) or []


def _best_file(video: dict, target_h: int) -> dict | None:
    """Pick the portrait .mp4 rendition whose height is closest to target_h
    (preferring >= target_h so we can downscale rather than upscale)."""
    files = [
        f for f in video.get("video_files", [])
        if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
        and f["height"] >= f["width"]  # portrait only
    ]
    if not files:
        return None
    at_or_above = [f for f in files if f["height"] >= target_h]
    pool = at_or_above or files
    return min(pool, key=lambda f: abs(f["height"] - target_h))


def fetch_clip(topic_or_query, out_path, min_duration: int = 5) -> dict | None:
    """Download a topic-matched Pexels clip. Returns metadata dict on success
    ({"path", "id", "duration", "author"}) or None on any failure."""
    key = _api_key()
    if not key:
        return None
    out_path = Path(out_path)

    if isinstance(topic_or_query, dict):
        queries = list(topic_or_query.get("pexels_queries") or [])
        random.shuffle(queries)
        if topic_or_query.get("id"):
            queries.append(topic_or_query["id"].replace("_", " "))
    else:
        queries = [str(topic_or_query)]

    used = set(_load_used_ids())

    for query in queries:
        try:
            videos = _search(query, key)
        except Exception as exc:
            print(f"  Pexels video search failed for '{query}' ({exc})")
            continue
        if not videos:
            continue
        random.shuffle(videos)
        ordered = [v for v in videos if v.get("id") not in used] or videos

        for video in ordered:
            if (video.get("duration") or 0) < min_duration:
                continue
            vf = _best_file(video, config.REEL_H)
            if not vf:
                continue
            try:
                resp = requests.get(vf["link"], timeout=90)
                resp.raise_for_status()
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(resp.content)
                _remember_id(video.get("id"))
                author = video.get("user", {}).get("name", "unknown")
                print(f"  Pexels video: '{query}' -> clip {video.get('id')} by {author} "
                      f"({vf['width']}x{vf['height']}, {video.get('duration')}s)")
                return {
                    "path": str(out_path),
                    "id": video.get("id"),
                    "duration": video.get("duration"),
                    "author": author,
                }
            except Exception as exc:
                print(f"  Pexels video download failed ({exc}); trying next")
                continue

    return None
