"""Bulk-download royalty-free instrumental music into the music/ folder.

Source: ccMixter (https://ccmixter.org) via its open API, filtered to the plain
Attribution (CC-BY) license — free for commercial use (a monetized page) as long
as the artist is credited. This script saves the tracks and records the required
attribution in music/attribution.json; the reel pipeline reads that file and adds
the credit line to each reel's caption automatically.

Run:  .venv/bin/python populate_music.py --target 45
Re-runnable: it skips tracks already present and tops up toward --target.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

import config

API = "https://ccmixter.org/api/query"
# Referer defeats ccMixter's hotlink protection on the content files.
HEADERS = {"User-Agent": "Mozilla/5.0 love-lens/1.0", "Referer": "https://ccmixter.org/"}
MOOD_TAGS = [
    "instrumental", "ambient", "cinematic", "piano", "chill", "mellow",
    "uplifting", "acoustic", "calm", "electronic", "guitar", "strings",
    "downtempo", "relaxing", "beautiful", "emotional", "soft", "dreamy",
    "lounge", "atmospheric", "melodic", "peaceful", "warm", "romantic",
    "meditation", "folk", "orchestral", "synth", "newage", "tender",
    "hopeful", "film", "background", "pad", "nature", "hopeful",
    "jazz", "world", "harp", "cello", "violin", "flute", "nostalgic", "serene",
]
MIN_SECONDS, MAX_SECONDS = 25, 600
ATTRIB_FILE = "attribution.json"


def _slug(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text[:60] or "track"


def _load_attrib(music_dir: Path) -> dict:
    try:
        return json.loads((music_dir / ATTRIB_FILE).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_attrib(music_dir: Path, data: dict) -> None:
    (music_dir / ATTRIB_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")


def _duration(path: Path) -> float:
    try:
        out = subprocess.run(
            [config.FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nk=1:nw=1", str(path)],
            capture_output=True, text=True).stdout.strip()
        return float(out)
    except Exception:
        return 0.0


def _query(tag: str, limit: int = 40, attempts: int = 4) -> list[dict]:
    # ccMixter intermittently emits an oversized HTTP header that trips
    # http.client (LineTooLong). A fresh connection on retry usually clears it.
    params = {"f": "json", "lic": "by", "tags": tag, "limit": limit, "sort": "rank"}
    headers = {**HEADERS, "Connection": "close"}
    last = None
    for _ in range(attempts):
        try:
            with requests.Session() as s:
                r = s.get(API, params=params, headers=headers, timeout=40)
            r.raise_for_status()
            return r.json() or []
        except Exception as exc:
            last = exc
            continue
    raise last


def populate(target: int) -> int:
    music_dir = config.MUSIC_DIR
    music_dir.mkdir(parents=True, exist_ok=True)
    attrib = _load_attrib(music_dir)

    have = len([p for p in music_dir.iterdir()
                if p.is_file() and p.suffix.lower() == ".mp3"])
    print(f"Currently have {have} track(s); target {target}.")

    for tag in MOOD_TAGS:
        if have >= target:
            break
        try:
            tracks = _query(tag)
        except Exception as exc:
            print(f"  query '{tag}' failed ({exc})")
            continue
        print(f"· tag '{tag}': {len(tracks)} candidates")
        for t in tracks:
            if have >= target:
                break
            title = t.get("upload_name") or "Untitled"
            artist = t.get("user_name") or "Unknown"
            key = f"{_slug(artist)}__{_slug(title)}"
            fname = f"{key}.mp3"
            dest = music_dir / fname
            if fname in attrib or dest.exists():
                continue
            mp3s = [f for f in t.get("files", [])
                    if f.get("download_url", "").lower().endswith(".mp3")]
            if not mp3s:
                continue
            url = mp3s[0]["download_url"]
            try:
                data = requests.get(url, headers=HEADERS, timeout=120).content
                if len(data) < 300_000:  # too small to be a real track
                    continue
                dest.write_bytes(data)
                dur = _duration(dest)
                if not (MIN_SECONDS <= dur <= MAX_SECONDS):
                    dest.unlink(missing_ok=True)
                    continue
            except Exception as exc:
                print(f"    skip {title[:30]} ({exc})")
                dest.unlink(missing_ok=True)
                continue
            attrib[fname] = {
                "title": title,
                "artist": artist,
                "license": t.get("license_name") or "CC BY",
                "source": "ccMixter",
                "page": (mp3s[0].get("file_page_url")
                         or f"https://ccmixter.org/files/{artist}"),
            }
            have += 1
            print(f"    + [{have}/{target}] {title[:38]} — {artist} ({round(dur)}s)")

    _save_attrib(music_dir, attrib)
    print(f"Done. {have} track(s) in {music_dir}")
    return have


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bulk-download CC-BY music into music/")
    ap.add_argument("--target", type=int, default=45, help="how many tracks to have")
    args = ap.parse_args(argv)
    populate(args.target)


if __name__ == "__main__":
    main(sys.argv[1:])
