"""Cloud step: send the freshly generated batch to Telegram with Approve/Reject
buttons AND record each item (with its Telegram file_id) into pending.json, so the
poller can post whatever you approve later — even hours afterward.

Media is stored by Telegram itself (we keep only the file_id), so nothing heavy is
committed to the repo — just the small pending.json state.
"""
from __future__ import annotations

import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import config
import notify

PENDING = Path(__file__).resolve().parent / "pending.json"


def _load() -> dict:
    try:
        d = json.loads(PENDING.read_text(encoding="utf-8"))
        d.setdefault("offset", 0)
        d.setdefault("items", {})
        return d
    except Exception:
        return {"offset": 0, "items": {}}


def _save(state: dict) -> None:
    PENDING.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _photo_fid(payload: dict):
    photos = (payload or {}).get("result", {}).get("photo", [])
    return photos[-1]["file_id"] if photos else None


def _video_fid(payload: dict):
    return (payload or {}).get("result", {}).get("video", {}).get("file_id")


def main():
    day_dir = notify._latest_output_dir()
    cap = json.loads((day_dir / "captions.json").read_text(encoding="utf-8"))
    state = _load()
    items = state["items"]
    n = 0

    for c in cap.get("cards", []):
        f = day_dir / "cards" / c.get("file", "")
        if not f.exists():
            continue
        cb = f"{day_dir.name}/{c['file']}"
        payload = notify.send_photo(f, f"🧪 {c.get('caption','')}", cb)
        items[cb] = {"type": "card", "caption": c.get("caption", ""),
                     "file_id": _photo_fid(payload)}
        n += 1

    for r in cap.get("video_reels", []):
        f = day_dir / "reels" / r.get("file", "")
        if not f.exists():
            continue
        cb = f"{day_dir.name}/reels/{r['file']}"
        payload = notify.send_video(f, f"🎬 {r.get('caption','')}", cb)
        items[cb] = {"type": "reel", "caption": r.get("caption", ""),
                     "file_id": _video_fid(payload)}
        n += 1

    for p in cap.get("products", []):
        asin = p.get("asin") or p.get("url", "")[-12:]
        cb = f"{day_dir.name}/products/{asin}"
        notify.send_message(f"🛒 {p.get('tg_text','')}", cb)
        items[cb] = {"type": "product",
                     "fb_message": p.get("fb_message", p.get("caption", "")),
                     "url": p.get("url", "")}
        n += 1

    for a in cap.get("alerts", []):
        try:
            notify.send_notice(a)
        except Exception:
            pass

    _save(state)
    print(f"queued {n} item(s) to Telegram; {len(items)} total pending")


if __name__ == "__main__":
    main()
