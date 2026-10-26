"""Cloud poller: check Telegram for Approve/Reject taps and post approved items to
Facebook — however long after the batch was sent. Runs as a short scheduled job
(e.g. every 15 min). Media is pulled back from Telegram by file_id, so nothing
heavy lives in the repo; only pending.json (offset + unapproved items) persists.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import post_fb

PENDING = Path(__file__).resolve().parent / "pending.json"


def _token() -> str:
    t = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not t:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set")
    return t


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


def _get_updates(offset: int):
    r = requests.get(f"https://api.telegram.org/bot{_token()}/getUpdates",
                     params={"offset": offset, "timeout": 0,
                             "allowed_updates": json.dumps(["callback_query"])},
                     timeout=40)
    return r.json().get("result", [])


def _answer(qid, text):
    try:
        requests.post(f"https://api.telegram.org/bot{_token()}/answerCallbackQuery",
                      data={"callback_query_id": qid, "text": text}, timeout=20)
    except Exception:
        pass


def _edit(chat, mid, text):
    try:
        requests.post(f"https://api.telegram.org/bot{_token()}/editMessageText",
                      data={"chat_id": chat, "message_id": mid, "text": text}, timeout=20)
    except Exception:
        pass


def _download(file_id: str, suffix: str) -> str:
    gf = requests.get(f"https://api.telegram.org/bot{_token()}/getFile",
                      params={"file_id": file_id}, timeout=30).json()
    path = gf["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{_token()}/{path}"
    data = requests.get(url, timeout=180).content
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    return tmp.name


def main():
    state = _load()
    items = state["items"]
    offset = state.get("offset", 0)
    updates = _get_updates(offset)
    posted = 0

    for u in updates:
        offset = max(offset, u.get("update_id", 0) + 1)
        cq = u.get("callback_query")
        if not cq:
            continue
        data = cq.get("data", "")
        qid = cq.get("id")
        msg = cq.get("message", {})
        chat = msg.get("chat", {}).get("id")
        mid = msg.get("message_id")
        if ":" not in data:
            continue
        action, cb = data.split(":", 1)
        it = items.get(cb)
        if not it:
            _answer(qid, "Expired or already handled")
            continue
        if action == "reject":
            items.pop(cb, None)
            _answer(qid, "Skipped")
            _edit(chat, mid, "❌ Skipped")
            continue
        if action != "approve":
            continue
        try:
            if it["type"] == "product":
                post_fb.post_link(it.get("fb_message", ""), it.get("url", ""))
            elif it["type"] == "reel":
                tmp = _download(it["file_id"], ".mp4")
                post_fb.post_reel(tmp, it.get("caption", ""))
                os.unlink(tmp)
            else:  # card (photo)
                tmp = _download(it["file_id"], ".jpg")
                post_fb.post_card(tmp, it.get("caption", ""))
                os.unlink(tmp)
            items.pop(cb, None)
            posted += 1
            _answer(qid, "Posted ✅")
            _edit(chat, mid, "✅ Posted to the page")
        except Exception as exc:
            # keep the item so a re-tap retries; the consumed update won't come back
            _answer(qid, "Failed — tap Approve again")
            print(f"post failed for {cb}: {exc}")

    state["offset"] = offset
    _save(state)
    print(f"posted {posted}; {len(items)} still pending; offset={offset}")


if __name__ == "__main__":
    main()
