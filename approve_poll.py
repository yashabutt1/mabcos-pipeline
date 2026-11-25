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


def _cross_post_instagram(res, it):
    """Mirror a just-published post to Instagram for extra reach. Uses only public,
    token-free Facebook-CDN media URLs; if one isn't available (e.g. a reel source),
    it simply skips IG for that item. No-ops cleanly until Instagram is set up."""
    try:
        import instagram
    except Exception:
        return
    try:
        if it["type"] == "product":
            return
        # Use the MEDIA object id (res["id"]) — the photo/video id — not the feed
        # story post_id, which carries no images/source field.
        media_id = (res or {}).get("id")
        if it["type"] == "reel":
            # Facebook needs a moment after posting to process the reel and expose its
            # public source URL — poll until it's ready, then hand it to Instagram.
            import time
            url = None
            for _ in range(15):
                url = post_fb.video_source_url(media_id)
                if url:
                    break
                time.sleep(5)
            igid = instagram.publish_reel(url, it.get("caption", "")) if url else None
        else:  # photo card
            url = post_fb.photo_public_url(media_id)
            igid = instagram.publish_image(url, it.get("caption", "")) if url else None
        if igid:
            print(f"cross-posted to Instagram: {igid}")
        elif not url:
            print(f"IG cross-post skipped: no public media URL for {it['type']} (id={media_id})")
        else:
            print("IG cross-post skipped: Instagram unavailable")
    except Exception as exc:
        print(f"IG cross-post skipped: {exc}")


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


def _refresh_items(state: dict) -> None:
    """Pull the latest queued items from the repo so a long-running poll also sees
    cards the generate workflow queued AFTER this job checked out. The poll is
    otherwise stateless about pending.json: it never writes it, so it can never race
    the generate workflow. Telegram itself is the source of truth for 'already
    handled' (a tap is delivered once, then confirmed server-side)."""
    url = os.getenv("PENDING_URL", "").strip()
    if not url:
        return
    try:
        r = requests.get(url, timeout=20, headers={"Cache-Control": "no-cache"})
        if r.ok:
            remote = r.json().get("items")
            if isinstance(remote, dict) and remote:
                state["items"] = remote
    except Exception as exc:
        print(f"  (item refresh skipped: {exc})", flush=True)


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
    if not gf.get("ok") or "result" not in gf:
        # e.g. "file is too big" (>20MB getFile limit) or an expired file_id
        raise RuntimeError(f"Telegram getFile failed: {gf.get('description', gf)}")
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
            # Post IMMEDIATELY on approval (visible at once on FB + Instagram). Peak
            # timing is handled by WHEN the batch alerts you, not by delaying the post —
            # scheduling made approved posts invisible for hours and caused confusion.
            when = None
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
            # Cross-post to Instagram NOW, whether FB posts live or is scheduled —
            # the uploaded photo/video already has a public URL, so IG shouldn't wait.
            _cross_post_instagram(res, it)
            if when:
                _answer(qid, "Scheduled ✅ (also on Instagram)")
                _edit(chat, mid, f"⏰ FB scheduled for {peak.describe(when)} · Instagram posted now")
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

    # NOTE: pending.json is deliberately NOT written here. The poll is stateless
    # about the queue — it relies on Telegram confirming handled taps (see main),
    # so it can never race the generate workflow's pending.json commit. published.json
    # and comments.json ARE written above (by _record_published / the reply handler),
    # since the poll owns those files.
    state["offset"] = offset
    return posted


def _scan_comments() -> None:
    """Scan published posts for new comments and alert on Telegram. Run in-process
    during the long poll so reply alerts stay responsive (the first 10–20 min after
    a comment is when a reply lifts reach)."""
    try:
        import comment_watch
        comment_watch.scan()
    except Exception as exc:
        print(f"  comment scan error (continuing): {exc}", flush=True)


def main():
    import time
    budget = int(os.getenv("MABCOS_POLL_SECONDS", "0") or 0)
    deadline = time.time() + budget
    scan_every = int(os.getenv("MABCOS_SCAN_SECONDS", "600") or 600)
    # One in-memory state for the whole run. Start the offset at 0: Telegram only
    # returns updates it hasn't confirmed yet, and each long-poll iteration confirms
    # the previous batch, so handled taps never come back even though the poll never
    # persists pending.json. This makes posting immune to the pending.json write race
    # that was swallowing approvals. published.json / comments.json are still written
    # (and committed by the workflow at the end of the run) so comment-watch survives.
    state = _load()
    state["offset"] = 0
    total = 0
    loops = 0
    last_scan = 0.0
    while True:
        loops += 1
        if time.time() - last_scan >= scan_every:
            _scan_comments()
            last_scan = time.time()
        try:
            _refresh_items(state)
            # Long-poll (25s) when running a window so taps post within seconds; a
            # single quick check otherwise.
            total += _poll_once(state, long_poll=25 if budget else 0)
        except Exception as exc:
            # A transient Telegram/network hiccup must never kill a long poll run.
            print(f"  poll iteration error (continuing): {exc}", flush=True)
            time.sleep(5)
        if budget <= 0 or time.time() >= deadline:
            break
    print(f"posted {total}; polled {loops}x over ~{budget}s")


if __name__ == "__main__":
    main()
