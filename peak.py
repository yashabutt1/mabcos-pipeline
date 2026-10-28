"""Decide WHEN an approved post should go live, so posts land in peak-activity
windows even when you approve at an odd hour.

Peak windows are local-time hours (default Pakistan time, UTC+5). If you approve
*inside* a window, the post publishes immediately; otherwise it's scheduled to the
next window via Facebook's scheduled_publish_time. All tunable via env:

    MABCOS_TZ_OFFSET   hours east of UTC for your audience (default 5 = PKT)
    MABCOS_PEAK_HOURS  comma list of local peak hours   (default "8,13,20")
"""
from __future__ import annotations

import datetime
import os

WINDOW_HOURS = 2             # grace: approving within 2h after a peak hour = "now"
MIN_LEAD_SECONDS = 15 * 60   # FB needs scheduled time ≥10 min ahead; keep a margin


def _tz() -> datetime.timezone:
    return datetime.timezone(datetime.timedelta(hours=float(os.getenv("MABCOS_TZ_OFFSET", "5"))))


def _peak_hours() -> list[int]:
    raw = os.getenv("MABCOS_PEAK_HOURS", "8,13,20")
    return sorted({int(h) for h in raw.split(",") if h.strip().isdigit()})


def next_publish_ts(now: datetime.datetime = None):
    """None → publish right now (we're inside a peak window). Otherwise a unix
    timestamp (UTC seconds) of the next peak window to schedule the post for."""
    tz = _tz()
    now = (now.astimezone(tz) if now else datetime.datetime.now(tz))
    hours = _peak_hours()

    for h in hours:
        start = now.replace(hour=h, minute=0, second=0, microsecond=0)
        if start <= now < start + datetime.timedelta(hours=WINDOW_HOURS):
            return None  # already prime time — post immediately

    candidates = []
    for day in (0, 1):
        base = (now + datetime.timedelta(days=day)).replace(minute=0, second=0, microsecond=0)
        for h in hours:
            slot = base.replace(hour=h)
            if slot > now:
                candidates.append(int(slot.timestamp()))
    ts = min(candidates)
    return max(ts, int(now.timestamp()) + MIN_LEAD_SECONDS)


def describe(ts: int) -> str:
    """Human label for a scheduled timestamp, in the audience timezone."""
    dt = datetime.datetime.fromtimestamp(ts, tz=_tz())
    return dt.strftime("%a %-I:%M %p").replace("AM", "am").replace("PM", "pm")
