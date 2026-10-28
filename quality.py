"""Quality gate: reject INCOMPLETE or REPETITIVE posts before they reach Telegram.

Catches the ways a post can come out broken:
  • truncated caption / title / body (model stopped mid-thought)
  • empty or placeholder fields, leftover template or JSON artifacts
  • unrendered <b>/<span> markup leaking into the caption
  • structural gaps (a poll with <2 options)
  • near-duplicates, within the batch and against recent history

`check()` returns (ok, reasons) so the pipeline can swap in a clean fallback.
"""
from __future__ import annotations

import re

_PLACEHOLDERS = ("lorem ipsum", "todo", "tbd", "xxxx", "undefined", "placeholder",
                 "insert ", "your text here", "n/a", "<span class='hl'></span>", "<b></b>")

# a caption/sentence ending on one of these words was almost certainly cut off
_DANGLING = {"and", "or", "but", "the", "a", "an", "to", "of", "for", "with", "in", "on",
             "at", "by", "that", "as", "is", "are", "was", "were", "which", "while",
             "because", "from", "this", "their", "its", "our", "how", "when", "where",
             "who", "than", "then", "into", "about", "over", "can", "could", "may"}

_CTA_PREFIXES = ("🔁", "🔖", "🏷️", "🔬", "#")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def looks_truncated(text: str) -> bool:
    """True when a piece of text appears cut off mid-thought."""
    t = (text or "").strip()
    if not t:
        return True
    if t[-1] in "-–—:,;":
        return True
    # unbalanced brackets, quotes, or bold tags
    if t.count("(") != t.count(")") or t.count("[") != t.count("]"):
        return True
    if t.count("<b>") != t.count("</b>"):
        return True
    # ends on a connective word, with no sentence punctuation
    if t[-1] not in ".!?…\"')":
        words = re.findall(r"[A-Za-z']+", t)
        if words and words[-1].lower() in _DANGLING:
            return True
    return False


def _body_paragraphs(caption: str) -> list[str]:
    paras = [p.strip() for p in (caption or "").split("\n\n") if p.strip()]
    return [p for p in paras if not p.startswith(_CTA_PREFIXES)]


def issues(item: dict) -> list[str]:
    """All completeness problems with one generated item ({caption,data,kind,...})."""
    out = []
    data = item.get("data", {}) or {}
    cap = (item.get("caption") or "").strip()
    title = (data.get("title") or "").strip()

    if len(cap) < 50:
        out.append("caption too short")
    if not title:
        out.append("missing title")
    elif looks_truncated(title):
        out.append("title truncated")

    low = cap.lower()
    for ph in _PLACEHOLDERS:
        if ph in low:
            out.append(f"placeholder:{ph.strip()}")
    if "{" in cap or "}" in cap or "```" in cap:
        out.append("raw json/braces in caption")
    if "<b>" in cap or "</b>" in cap or "<span" in cap:
        out.append("unrendered markup in caption")

    body = _body_paragraphs(cap)
    if not body:
        out.append("no body text")
    elif looks_truncated(body[-1]) and not body[-1].rstrip().endswith("?"):
        out.append("body truncated")

    kind = item.get("kind")
    if kind == "interactive" and len(data.get("options", []) or []) < 2:
        out.append("poll has <2 options")

    return out


def check(item: dict) -> tuple[bool, list[str]]:
    probs = issues(item)
    return (not probs, probs)


def _keys(item: dict) -> set:
    data = item.get("data", {}) or {}
    hook = (item.get("caption") or "").split("\n", 1)[0]
    ks = {norm(data.get("title", ""))[:48], norm(hook)[:48]}
    return {k for k in ks if len(k) >= 12}


def seed_seen(recent) -> set:
    """Build the 'already seen' set from recent history titles/hooks."""
    seen = set()
    for t in (recent or []):
        n = norm(t)[:48]
        if len(n) >= 12:
            seen.add(n)
    return seen


def is_redundant(item: dict, seen: set) -> bool:
    """True if this item repeats something already in ``seen``; else records it."""
    ks = _keys(item)
    if ks & seen:
        return True
    seen |= ks
    return False


def reel_ok(reel: dict) -> bool:
    cap = (reel.get("caption") or "").strip()
    line = (reel.get("line") or "").strip()
    return bool(line) and len(cap) >= 30 and not looks_truncated(cap.split("\n", 1)[0])
