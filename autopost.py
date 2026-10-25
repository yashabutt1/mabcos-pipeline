"""Post the latest generated batch straight to Facebook, then send a Telegram
summary. Used in the cloud (GitHub Actions) where no interactive approval bot
runs — the pipeline generates a batch and this posts it unattended.

    python pipeline.py && python autopost.py

Accuracy guards live in generation (content.py / fallbacks.py). The Telegram
summary lets you see exactly what went out and remove anything on the Page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import config
import post_fb
import notify


def _latest_dir() -> Path:
    cur = config.current_batch_dir()
    if (cur / "captions.json").exists():
        return cur
    dirs = sorted((p for p in config.OUTPUT_DIR.iterdir() if p.is_dir()),
                  key=lambda p: p.stat().st_mtime)
    if not dirs:
        raise FileNotFoundError("no output batches found")
    return dirs[-1]


def main():
    day_dir = _latest_dir()
    cap = json.loads((day_dir / "captions.json").read_text(encoding="utf-8"))
    posted, failed = [], []

    for c in cap.get("cards", []):
        f = day_dir / "cards" / c.get("file", "")
        if not f.exists():
            continue
        try:
            post_fb.post_card(str(f), c.get("caption", ""))
            posted.append(f"🖼️ {c.get('title') or c['file']}")
        except Exception as exc:
            failed.append(f"card {c.get('file')}: {exc}")

    for r in cap.get("video_reels", []):
        f = day_dir / "reels" / r.get("file", "")
        if not f.exists():
            continue
        try:
            post_fb.post_reel(str(f), r.get("caption", ""))
            posted.append(f"🎬 reel {r['file']}")
        except Exception as exc:
            failed.append(f"reel {r.get('file')}: {exc}")

    for p in cap.get("products", []):
        try:
            post_fb.post_link(p.get("fb_message", p.get("caption", "")), p["url"])
            posted.append(f"🛒 {p.get('name')}")
        except Exception as exc:
            failed.append(f"product {p.get('name')}: {exc}")

    # Telegram summary (best-effort; cloud has the same secrets)
    try:
        lines = [f"✅ MABCOS auto-posted {len(posted)} item(s) — {day_dir.name}"]
        lines += ["  • " + x for x in posted]
        if failed:
            lines += ["", "⚠️ Failed:"] + ["  • " + x for x in failed]
        notify.send_notice("\n".join(lines))
    except Exception as exc:
        print(f"(telegram summary skipped: {exc})")

    print(f"posted {len(posted)}, failed {len(failed)}")
    for x in failed:
        print("FAIL:", x)
    if failed and not posted:
        sys.exit(1)


if __name__ == "__main__":
    main()
