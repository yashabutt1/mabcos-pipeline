"""Pick a royalty-free music track for a reel.

Reads whatever audio files live in config.MUSIC_DIR and rotates through them,
avoiding recently-used tracks (remembered in output/.music_history.json) so the
same song doesn't back-to-back. Returns None when the folder is empty, in which
case the reel is built without music.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import config

_HISTORY_FILE = ".music_history.json"
_ATTRIB_FILE = "attribution.json"
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"}


def attribution_for(track_name: str) -> dict | None:
    """Return the attribution record for a track filename, if one exists."""
    try:
        data = json.loads((config.MUSIC_DIR / _ATTRIB_FILE).read_text(encoding="utf-8"))
        return data.get(track_name)
    except Exception:
        return None


def credit_line(track_name: str) -> str | None:
    """CC-BY credit line for a track, or None (e.g. no-attribution Pixabay track)."""
    a = attribution_for(track_name)
    if not a:
        return None
    return (f"\U0001F3B5 \"{a.get('title','')}\" by {a.get('artist','')} "
            f"({a.get('source','ccMixter')}), licensed under {a.get('license','CC BY')}")


def _history_path() -> Path:
    return config.OUTPUT_DIR / _HISTORY_FILE


def _load_recent() -> list[str]:
    try:
        data = json.loads(_history_path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def _remember(name: str, keep: int) -> None:
    recent = _load_recent()
    recent.append(name)
    recent = recent[-keep:]
    try:
        _history_path().parent.mkdir(parents=True, exist_ok=True)
        _history_path().write_text(json.dumps(recent), encoding="utf-8")
    except Exception:
        pass


def available_tracks() -> list[Path]:
    if not config.MUSIC_DIR.exists():
        return []
    return sorted(p for p in config.MUSIC_DIR.iterdir()
                  if p.is_file() and p.suffix.lower() in _AUDIO_EXTS)


def pick_track() -> str | None:
    """Return the path to a track not used recently, or None if none available."""
    tracks = available_tracks()
    if not tracks:
        return None
    # Avoid the most-recently-used half of the library so rotation feels varied.
    recent = set(_load_recent()[-(len(tracks) // 2 or 1):])
    fresh = [t for t in tracks if t.name not in recent] or tracks
    choice = random.choice(fresh)
    _remember(choice.name, keep=max(1, len(tracks) // 2))
    return str(choice)
