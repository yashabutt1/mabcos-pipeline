"""Pull the latest REAL headlines from top biotech/science news sources, so the
'Science News' posts are current, credible, and carry a real source link.

Needs feedparser + requests. Fails soft (skips a dead feed). Harvard Gazette is a
general feed, so its items are keyword-filtered down to life-science topics.
"""
from __future__ import annotations

import re

import requests

try:
    import feedparser
except Exception:  # pragma: no cover
    feedparser = None

_UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")}

# (name, rss_url, needs_topic_filter)
FEEDS = [
    ("Nature", "https://www.nature.com/subjects/biotechnology.rss", False),
    ("GEN", "https://www.genengnews.com/feed/", False),
    ("IEEE Spectrum", "https://spectrum.ieee.org/feeds/topic/biomedical.rss", False),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/plants_animals/biotechnology.xml", False),
    ("Harvard Gazette", "https://news.harvard.edu/gazette/feed/", True),
]

_KEYWORDS = ("gene", "dna", "rna", "protein", "crispr", "cell", "biotech", "genom",
             "microb", "enzyme", "molecul", "biolog", "vaccine", "cancer", "bioinformat",
             "stem", "antibiotic", "mrna", "sequenc", "neuro", "brain", "immun",
             "bacteri", "virus", "evolution", "drug", "therap", "disease")


def _clean(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html or "").replace("&nbsp;", " ").strip()


def _relevant(title: str, summary: str) -> bool:
    text = (title + " " + summary).lower()
    return any(k in text for k in _KEYWORDS)


def fetch_items(max_per_feed: int = 8) -> list[dict]:
    """Return recent {title, link, summary, source} items across the feeds."""
    if feedparser is None:
        return []
    items, seen = [], set()
    for name, url, needs_filter in FEEDS:
        try:
            r = requests.get(url, headers=_UA, timeout=20)
            parsed = feedparser.parse(r.content)
        except Exception as exc:
            print(f"  feed {name} failed ({exc})")
            continue
        kept = 0
        for e in parsed.entries:
            title = (e.get("title") or "").strip()
            link = (e.get("link") or "").strip()
            summary = _clean(e.get("summary") or e.get("description") or "")[:420]
            if not title or not link:
                continue
            if needs_filter and not _relevant(title, summary):
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append({"title": title, "link": link, "summary": summary, "source": name})
            kept += 1
            if kept >= max_per_feed:
                break
    return items


def domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""
