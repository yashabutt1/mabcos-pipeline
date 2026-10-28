"""Watch recently published Facebook posts for NEW comments and alert you on
Telegram with a ready-to-send draft reply — so you can respond inside the first
10–20 minutes, which is what pushes a post to more people.

Nothing is replied automatically. The alert carries a "✍️ Send reply" button; the
reply only goes out when YOU tap it (handled by approve_poll.py). Replies you don't
act on simply expire.

State:
  published.json  {"targets": [{id, type, caption, ts}]}   written by approve_poll
  comments.json   {"seen": [comment_id...], "pending": {comment_id: {...}}}
"""
from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import post_fb
import notify

HERE = Path(__file__).resolve().parent
PUBLISHED = HERE / "published.json"
COMMENTS = HERE / "comments.json"

LOOKBACK_SECONDS = 3 * 24 * 3600   # only watch posts from the last 3 days
MAX_SEEN = 500                      # cap the dedup list


def _load(path: Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)


def _save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _first_name(frm: dict) -> str:
    name = (frm or {}).get("name", "").strip()
    return name.split()[0] if name else "there"


def _draft_reply(comment_text: str, post_caption: str, name: str) -> str:
    """A warm, specific one-liner. Uses Gemini when available, else a friendly
    template — either way it's only a DRAFT you review before sending."""
    try:
        import content  # needs google-genai; falls through to template if absent
        prompt = (
            "You run a biotech education page (MABCOS). Reply to this Facebook comment in "
            "ONE warm, human sentence — specific to what they said, no emoji spam, no hashtags, "
            "sound like a real person, invite them to keep engaging.\n"
            f"Your post was about: {post_caption[:200]}\n"
            f"Their comment: {comment_text[:300]}\n"
            "Reply:")
        txt = content._gen(prompt, grounded=False, temp=0.7).strip().strip('"')
        if txt:
            return txt[:400]
    except Exception as exc:
        print(f"  draft via Gemini unavailable ({exc}); using template")
    return (f"Thanks, {name}! Really glad this resonated — what part stood out most? "
            "Follow along for more biotech like this. 🔬")


def _post_url(target_id: str) -> str:
    return f"https://www.facebook.com/{target_id}"


def scan() -> int:
    targets = _load(PUBLISHED, {"targets": []}).get("targets", [])
    state = _load(COMMENTS, {"seen": [], "pending": {}})
    seen = set(state.get("seen", []))
    pending = state.get("pending", {})
    now = int(time.time())

    try:
        token = post_fb.resolve_token()
    except Exception as exc:
        print(f"cannot resolve FB token: {exc}")
        return 0
    my_page = post_fb.page_id()

    alerted = 0
    for tgt in targets:
        if now - int(tgt.get("ts", 0)) > LOOKBACK_SECONDS:
            continue
        oid = tgt.get("id")
        if not oid:
            continue
        try:
            comments = post_fb.list_comments(oid, token=token)
        except Exception as exc:
            print(f"  comments fetch failed for {oid} ({exc})")
            continue
        for c in comments:
            cid = c.get("id")
            frm = c.get("from") or {}
            if not cid or cid in seen:
                continue
            seen.add(cid)
            if frm.get("id") == my_page:      # skip the page's own replies
                continue
            text = (c.get("message") or "").strip()
            if not text:
                continue
            name = _first_name(frm)
            draft = _draft_reply(text, tgt.get("caption", ""), name)
            pending[cid] = {"draft": draft, "who": frm.get("name", ""),
                            "text": text, "post_id": oid, "ts": now}
            msg = (f"💬 New comment from {frm.get('name','someone')}:\n“{text[:500]}”\n\n"
                   f"Suggested reply:\n{draft}\n\n"
                   "Tap to send it, or open the post to reply in your own words.")
            rows = [
                [{"text": "✍️ Send reply", "callback_data": f"sendreply:{cid}"}],
                [{"text": "🔗 Open post", "url": _post_url(tgt.get("post_url_id", oid))},
                 {"text": "🙈 Dismiss", "callback_data": f"ignorecmt:{cid}"}],
            ]
            try:
                notify.send_buttons(msg, rows)
                alerted += 1
            except Exception as exc:
                print(f"  alert send failed ({exc})")

    state["seen"] = list(seen)[-MAX_SEEN:]
    state["pending"] = pending
    _save(COMMENTS, state)
    print(f"comment scan: {alerted} new comment alert(s); {len(pending)} awaiting your reply")
    return alerted


if __name__ == "__main__":
    scan()
