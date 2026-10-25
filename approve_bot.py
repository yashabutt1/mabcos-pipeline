import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

import post_fb

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

ROOT = Path(__file__).resolve().parent
LOG_FILE = ROOT / "approval_log.txt"
REJECTED_DIR = ROOT / "rejected"
POSTED_DIR = ROOT / "posted"
OFFSET_FILE = ROOT / "last_update_offset.txt"
REJECTED_DIR.mkdir(exist_ok=True)
POSTED_DIR.mkdir(exist_ok=True)


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to .env first.")
    return value


def _log(message: str):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _latest_output_dir() -> Path:
    output_root = ROOT / "output"
    dirs = sorted(p for p in output_root.iterdir() if p.is_dir())
    if not dirs:
        raise FileNotFoundError("No output directories found")
    return dirs[-1]


def _get_updates(offset: int = 0):
    token = _env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    params = {"timeout": 50, "offset": offset}
    resp = requests.get(url, params=params, timeout=60)
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload.get("result", [])


def _load_offset() -> int:
    if not OFFSET_FILE.exists():
        return 0
    try:
        return int(OFFSET_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return 0


def _save_offset(offset: int):
    OFFSET_FILE.write_text(str(offset), encoding="utf-8")


def _answer_callback(query_id, text):
    token = _env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    requests.post(url, data={"callback_query_id": query_id, "text": text}, timeout=30)


def _edit_message(chat_id, message_id, text):
    token = _env("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/editMessageText"
    requests.post(url, data={"chat_id": chat_id, "message_id": message_id, "text": text}, timeout=30)


def _move_to_rejected(media_path: Path):
    if media_path.exists():
        target = REJECTED_DIR / media_path.name
        media_path.rename(target)
        return str(target)
    return None


def _posted_marker(batch_dir: Path, filename: str) -> Path:
    marker_name = f"{batch_dir.name}_{Path(filename).name}"
    return POSTED_DIR / marker_name


def _resolve_batch_dir(date_part: str) -> Path:
    candidate = ROOT / "output" / date_part
    if date_part and candidate.is_dir():
        return candidate
    # Legacy callback_data with no date segment (messages sent before this fix).
    return _latest_output_dir()


def process_update(update):
    callback = update.get("callback_query")
    if not callback:
        return
    data = callback.get("data", "")
    query_id = callback.get("id")
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")
    if not data.startswith(("approve:", "reject:")):
        return
    action, payload = data.split(":", 1)
    if "/" in payload:
        date_part, rel = payload.split("/", 1)
    else:
        date_part, rel = "", payload
    batch_dir = _resolve_batch_dir(date_part)

    base_name = Path(rel).name
    is_product = rel.startswith("products/")
    is_reel = (not is_product) and base_name.lower().endswith(".mp4")
    # cards come through as a bare filename (legacy) -> live under cards/
    media_path = batch_dir / rel if "/" in rel else batch_dir / "cards" / rel
    posted_marker = _posted_marker(batch_dir, base_name)
    captions_path = batch_dir / "captions.json"

    if action != "approve":
        if not is_product:
            moved = _move_to_rejected(media_path)
            _log(f"Rejected {base_name} -> {moved}")
        else:
            _log(f"Rejected product {base_name}")
        _answer_callback(query_id, "Skipped")
        _edit_message(chat_id, message_id, f"Skipped {base_name}")
        return

    if posted_marker.exists():
        _answer_callback(query_id, "Already posted")
        _edit_message(chat_id, message_id, f"Already posted {base_name}")
        _log(f"Already posted {base_name}, skipped")
        return
    if not is_product and not media_path.exists():
        _answer_callback(query_id, "File not found")
        _log(f"Approve failed: {media_path} missing")
        return

    try:
        captions_data = {}
        if captions_path.exists():
            captions_data = json.loads(captions_path.read_text(encoding="utf-8"))

        if is_product:
            post = next((p for p in captions_data.get("products", [])
                         if (p.get("asin") or "") == base_name
                         or p.get("url", "").endswith(base_name)), None)
            if not post:
                _answer_callback(query_id, "Product not found")
                _log(f"Approve failed: product {base_name} not in captions.json")
                return
            result = post_fb.post_link(post.get("fb_message", post.get("caption", "")),
                                       post["url"])
            kind = "product"
            try:
                import fetch_products
                fetch_products.mark_posted(post.get("asin") or post.get("url"))
            except Exception as mp_exc:
                _log(f"Warning: could not mark product posted: {mp_exc}")
        else:
            if is_reel:
                lookup = captions_data.get("video_reels", [])
            else:
                # quote/paragraph cards, engagement, and reflections all post as photos
                lookup = (captions_data.get("cards", [])
                          + captions_data.get("engagement", [])
                          + captions_data.get("reflections", []))
            caption = ""
            for item in lookup:
                if item.get("file") == base_name:
                    caption = item.get("caption", "").strip()
                    break
            if is_reel:
                result = post_fb.post_reel(str(media_path), caption)
                kind = "reel"
            else:
                result = post_fb.post_card(str(media_path), caption)
                kind = "card"

        try:
            posted_marker.write_text("posted", encoding="utf-8")
        except Exception as write_exc:
            _log(f"Warning: could not write posted marker for {base_name}: {write_exc}")
        post_id = result.get("id")
        page_id = os.getenv("FB_PAGE_ID", "").strip()
        link = f"https://www.facebook.com/{page_id}/posts/{post_id}" if page_id and post_id else str(post_id or "")
        _answer_callback(query_id, "Posted ✅")
        _edit_message(chat_id, message_id, f"Posted ✅ {link}")
        _log(f"Approved and posted {kind} {base_name} -> {link}")
    except Exception as exc:
        _answer_callback(query_id, f"Failed: {exc}")
        _log(f"Approve failed for {base_name}: {exc}")


def _reconcile_offset(saved_offset: int) -> int:
    """Don't blindly trust the persisted offset on startup. If it's ahead of
    everything Telegram still has pending, a prior run bumped it past updates
    it never actually processed (crash, bad write, restart mid-poll) — new
    button taps would silently never be returned by getUpdates again."""
    try:
        pending = _get_updates(0)
    except requests.exceptions.RequestException as exc:
        _log(f"startup reconcile: could not fetch pending updates ({exc}); trusting saved offset {saved_offset}")
        return saved_offset
    if not pending:
        return saved_offset
    highest_pending_plus_one = max(u.get("update_id", 0) for u in pending) + 1
    if saved_offset > highest_pending_plus_one:
        _log(
            f"startup reconcile: saved offset {saved_offset} is ahead of "
            f"highest pending update ({highest_pending_plus_one}); discarding stale offset"
        )
        return 0
    return saved_offset


def main():
    offset = _reconcile_offset(_load_offset())
    _save_offset(offset)
    _log(f"approve_bot starting, offset={offset}")
    while True:
        try:
            updates = _get_updates(offset)
            for update in updates:
                process_update(update)
                offset = max(offset, update.get("update_id", 0) + 1)
                _save_offset(offset)
        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, requests.exceptions.RequestException) as exc:
            _log(f"network hiccup, retrying: {exc}")
            time.sleep(3)
            continue
        except Exception as exc:
            _log(f"unexpected loop error, retrying: {exc}")
            time.sleep(3)
            continue
        time.sleep(2)


if __name__ == "__main__":
    main()
