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
import peak

HERE = Path(__file__).resolve().parent
PENDING = HERE / "pending.json"
PUBLISHED = HERE / "published.json"
COMMENTS = HERE / "comments.json"


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _record_published(res, it):
    """Remember a post we just published so comment_watch can watch it for comments."""
    pid = (res or {}).get("post_id") or (res or {}).get("id")
    if not pid:
        return
    import time
    data = _load_json(PUBLISHED, {"targets": []})
    data.setdefault("targets", [])
    data["targets"].append({
        "id": pid,
        "post_url_id": (res or {}).get("post_id") or pid,
        "type": it.get("type"),
        "caption": (it.get("caption") or it.get("fb_message") or "")[:160],
        "ts": int(time.time()),
    })
    data["targets"] = data["targets"][-60:]
    _save_json(PUBLISHED, data)


def _post_id(res) -> str:
    return (res or {}).get("post_id") or (res or {}).get("id") or ""


import random as _random

_FC_BOOST = [
    "I reply to everyone 👇",
    "Curious what you all think 👇",
    "Tag someone who'd have a take on this 👇",
    "Drop your answer below 👇",
]


def _first_comment(caption: str) -> str:
    """An engaging first comment to pin the conversation — re-asks the post's own
    question (so the top comment is a discussion starter) or a generic nudge."""
    import re
    body = "\n".join(l for l in (caption or "").splitlines()
                     if not l.strip().startswith(("🔁", "🔖", "🏷️", "🔬", "#")))
    qs = re.findall(r"[^.!?\n]*\?", body)
    q = qs[-1].strip() if qs else ""
    boost = _random.choice(_FC_BOOST)
    if q and len(q) < 160:
        return f"{q} {boost}"
    return _random.choice([
        "What's your take? 👇 I reply to everyone.",
        "Agree or disagree? Tell me below 👇",
        "Tag someone who should see this 👇",
    ])


def _load_groups():
    """User's target groups from groups.txt ('Name | url' per line)."""
    p = HERE / "groups.txt"
    out = []
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "|" in line:
            name, url = line.split("|", 1)
            name, url = name.strip(), url.strip()
        else:
            name = url = line
        if url.startswith("http"):
            out.append((name[:28], url))
    return out


def _send_share_nudge(pid: str, caption: str) -> None:
    """After a post goes live, nudge you to share it into your groups (the single
    fastest way to get reach), with the live-post link, the caption to copy, and a
    tappable button per group. Posting to groups must be manual — Facebook removed
    the Groups API in 2024 — but this makes it a few taps."""
    groups = _load_groups()
    if not groups:
        return
    try:
        import notify
    except Exception:
        return
    permalink = f"https://www.facebook.com/{pid}" if pid else ""
    text = ("📣 Live! Share it into your groups NOW — the first hour drives reach.\n"
            + (f"\nPost: {permalink}\n" if permalink else "")
            + "\nTap a group, then paste this caption:\n\n" + (caption or "")[:1500])
    rows = []
    if permalink:
        rows.append([{"text": "🔗 Open the post", "url": permalink}])
    pair = []
    for name, url in groups[:20]:
        pair.append({"text": f"➡️ {name}", "url": url})
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    try:
        notify.send_buttons(text, rows)
    except Exception as exc:
        print(f"share nudge failed: {exc}")


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


def _get_updates(offset: int, long_poll: int = 0):
    r = requests.get(f"https://api.telegram.org/bot{_token()}/getUpdates",
                     params={"offset": offset, "timeout": long_poll,
                             "allowed_updates": json.dumps(["callback_query"])},
                     timeout=long_poll + 25)
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


def _poll_once(state, long_poll: int = 0) -> int:
    items = state["items"]
    offset = state.get("offset", 0)
    updates = _get_updates(offset, long_poll=long_poll)
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

        # --- comment-reply callbacks (cb is a Facebook comment id) ---
        if action in ("sendreply", "ignorecmt"):
            cstate = _load_json(COMMENTS, {"seen": [], "pending": {}})
            pend = cstate.get("pending", {})
            info = pend.get(cb)
            if not info:
                _answer(qid, "Expired or already handled")
                continue
            if action == "ignorecmt":
                pend.pop(cb, None)
                cstate["pending"] = pend
                _save_json(COMMENTS, cstate)
                _answer(qid, "Dismissed")
                _edit(chat, mid, "🙈 Dismissed — no reply sent")
                continue
            try:
                post_fb.post_comment_reply(cb, info["draft"])
                pend.pop(cb, None)
                cstate["pending"] = pend
                _save_json(COMMENTS, cstate)
                _answer(qid, "Reply sent ✅")
                _edit(chat, mid, f"✅ Reply sent:\n{info['draft']}")
            except Exception as exc:
                _answer(qid, "Failed — tap again")
                print(f"reply failed for {cb}: {exc}")
            continue

        # --- post approve/reject (cb is a queue item key) ---
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
            when = peak.next_publish_ts()   # None = post now; else schedule to next peak
            if it["type"] == "product":
                res = post_fb.post_link(it.get("fb_message", ""), it.get("url", ""), when=when)
            elif it["type"] == "reel":
                tmp = _download(it["file_id"], ".mp4")
                res = post_fb.post_reel(tmp, it.get("caption", ""), when=when)
                os.unlink(tmp)
            else:  # card (photo)
                tmp = _download(it["file_id"], ".jpg")
                res = post_fb.post_card(tmp, it.get("caption", ""), when=when)
                os.unlink(tmp)
            _record_published(res, it)
            items.pop(cb, None)
            posted += 1
            if when:
                _answer(qid, "Scheduled ✅")
                _edit(chat, mid, f"⏰ Scheduled for peak time — {peak.describe(when)}")
            else:
                _answer(qid, "Posted ✅")
                _edit(chat, mid, "✅ Posted to the page")
                # Live now: pin an engaging first comment + nudge you to share to groups.
                pid = _post_id(res)
                if pid and it["type"] != "product":
                    try:
                        post_fb.post_comment_reply(pid, _first_comment(it.get("caption", "")))
                    except Exception as exc:
                        print(f"first comment failed: {exc}")
                _send_share_nudge(pid, it.get("caption", "") or it.get("fb_message", ""))
        except Exception as exc:
            # keep the item so a re-tap retries; the consumed update won't come back
            _answer(qid, "Failed — tap Approve again")
            print(f"post failed for {cb}: {exc}")

    state["offset"] = offset
    _save(state)
    return posted


def main():
    import time
    budget = int(os.getenv("MABCOS_POLL_SECONDS", "0") or 0)
    deadline = time.time() + budget
    total = 0
    while True:
        # Long-poll (25s) when running a window so taps post within seconds; a
        # single quick check otherwise.
        total += _poll_once(_load_into(), long_poll=25 if budget else 0)
        if budget <= 0 or time.time() >= deadline:
            break
    print(f"posted {total}; offset persisted")


# Reload state each iteration so a concurrent generate commit is respected.
def _load_into():
    return _load()


if __name__ == "__main__":
    main()
