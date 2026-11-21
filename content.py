"""MABCOS content engine — generates STRUCTURED, specific, sourced card specs
per pillar, ready for cards.make_card().

Two sourcing modes:
  - GROUNDED (Gemini + Google Search): current, real opportunities, jobs, papers,
    and tech developments — verified at generation time.
  - EVERGREEN (Gemini): accurate knowledge/business/fact cards with real numbers,
    in the MABCOS voice, built on the strict accuracy rules below.

Each generator returns {"template","data","caption","kind"}:
  template -> "card.html.j2" or "card_photo.html.j2"
  data     -> dict for the Jinja template
  caption  -> the Facebook caption (with CTAs + hashtags)
"""
from __future__ import annotations

import json
import os
import re

from google import genai
from google.genai import types

import config
import fallbacks

_client = genai.Client() if os.getenv("GEMINI_API_KEY") else None

ACCURACY = (
    "ACCURACY IS NON-NEGOTIABLE. Every fact, number, name, date, and link must be "
    "real and correct. Never invent statistics, studies, people, or URLs. If you are "
    "not certain, use only what is well established. No medical advice or cure claims."
)
VOICE = (
    f"Write for MABCOS (@innovationthroughbiotech), a biotech/biochem/bioinformatics "
    f"page. Audience: {config.AUDIENCE} Voice: credible, specific, useful, a little "
    f"inspiring. No hype, no fluff."
)

# How captions must read (this is what makes people stop scrolling and click).
CAPTION_STYLE = """
CAPTION STYLE — follow exactly, it drives reach:
- "fb_hook" is the FIRST LINE people see before Facebook's "See more". Make it a
  scroll-stopping opener that reads like breaking tech/science news: a surprising
  claim or a concrete number that promises a payoff. It must make someone think
  "wait, what?" and tap to read more. NO emoji. NO hashtags. NO "Did you know".
  Just a confident, specific, plain-English sentence (~8-16 words).
- "fb_body" delivers on that hook in 2-4 SHORT paragraphs (a blank line between
  each), written like a mini news story: the what, the how, and the real NUMBERS
  (percentages, costs, scale). Add a one-line credibility note or "Source:" when
  relevant. End with ONE short, EASY-to-answer question — a this-or-that, a yes/no,
  "which would you pick?", or "guess before you read" — the kind of question someone
  replies to in 3 seconds. Easy questions get fast comments, and early comments are
  what trigger Facebook to show the post to more people. At most ONE emoji in the whole
  body, and never at the start of a line.
- "hashtags": at most 3, lowercase, relevant. (Facebook is not Instagram.)
All numbers must be real and verifiable."""


def _gen(prompt: str, grounded: bool = False, temp: float = 0.5) -> str:
    if _client is None:
        raise RuntimeError("GEMINI_API_KEY not set")
    cfg = types.GenerateContentConfig(temperature=temp)
    if grounded:
        cfg.tools = [types.Tool(google_search=types.GoogleSearch())]
    resp = _client.models.generate_content(
        model=config.TEXT_MODEL, contents=prompt, config=cfg)
    return resp.text or ""


def _json(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    s, e = cleaned.find("{"), cleaned.rfind("}")
    if s == -1 or e == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(cleaned[s:e + 1])


_EMOJI_TAIL = re.compile(r'[\U0001F000-\U0001FAFF☀-➿←-⇿️\s]+$')


def _clean_hook(h: str) -> str:
    """Make the first line a clean, emoji-free opener (what readers see first)."""
    h = (h or "").strip()
    h = re.sub(r'^[^\w"“\'‘(]+', "", h)      # drop leading emoji/bullets
    h = _EMOJI_TAIL.sub("", h).strip()         # drop trailing emoji (keep . ? !)
    return h


def _shorten(text: str, limit: int) -> str:
    """Trim to <= limit chars on a word boundary (no mid-word cuts), add an ellipsis."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or text[:limit]) + "…"


# Rotate CTAs toward ACTIONS that trigger Facebook distribution (share > save > tag),
# with Follow as the occasional default. Comments come from the body's question.
_ACTION_CTAS = [config.CTA_SHARE, config.CTA_SHARE, config.CTA_SAVE, config.CTA_SAVE,
                config.CTA_TAG, config.CTA_TAG, config.CTA_FOLLOW]


def _caption(hook: str, body: str, hashtags: list[str], cta: str = None) -> str:
    cta = cta or _random.choice(_ACTION_CTAS)
    tags = " ".join("#" + t.lstrip("#") for t in (hashtags or [])[:3])  # FB ≠ IG: keep it light
    parts = [p for p in [_clean_hook(hook), (body or "").strip(), cta, tags] if p]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# EVERGREEN pillars (Gemini, accuracy-grounded by rules)
# ---------------------------------------------------------------------------
def gen_education() -> dict:
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}

Create ONE "Bio-Education" card: a specific, true, surprising fact from
biotechnology, biochemistry, genetics, or microbiology, built around REAL numbers.
Pick something concrete (an impact figure, a cost, a percentage, a record) — like
the kind of fact a curious student screenshots.

Respond ONLY as JSON:
{{"kicker":"2-3 word topic in Title Case",
  "title":"punchy headline, max 8 words, no period",
  "lede":"1-2 sentences of context. Use <b>...</b> around the key term.",
  "stats":[{{"n":"big number e.g. 9% or $57B","l":"what it measures, <=9 words"}},
           {{"n":"second number","l":"what it measures, <=9 words"}}],
  "callout":"one 'why it matters' sentence, <b>...</b> on the key idea",
  "fb_hook":"1 line caption hook","fb_body":"1-2 sentence caption body + a question",
  "hashtags":["6-9 relevant tags"]}}
Both stats must be real and verifiable."""
    d = _json(_gen(prompt, temp=0.7))
    data = {"series": "Bio · Education", "kicker": d.get("kicker"),
            "title": d["title"], "lede": d.get("lede"),
            "stats": d.get("stats", [])[:2], "callout": d.get("callout")}
    return {"template": "card.html.j2", "data": data, "kind": "education",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []))}


def gen_business() -> dict:
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}

Create ONE "Bio-Business Idea": a concrete, realistic biotech/bioinformatics
venture a small team in a developing country could actually start. Be specific and
practical, with a real money angle. (In the style: soil testing lab, biopesticide
manufacturing, forensic DNA services, bioinformatics consulting.)

Respond ONLY as JSON:
{{"title":"the venture name, max 6 words",
  "lede":"1 sentence on the real need it serves",
  "blocks":[{{"head":"💡 The idea","body":"what you'd offer, 1-2 sentences, <b>key</b>"}},
            {{"head":"💰 Who pays","body":"the paying customer + why recurring, <b>key</b>"}},
            {{"head":"🚀 Why now","body":"the trend making it timely","tone":"blue"}}],
  "fb_hook":"caption hook","fb_body":"caption body + a question","hashtags":["6-9 tags"]}}"""
    d = _json(_gen(prompt, temp=0.8))
    data = {"series": "Bio · Business Idea", "kicker": "Venture",
            "title": d["title"], "title_size": 66, "lede": d.get("lede"),
            "blocks": d.get("blocks", []), "footer_sub": "Would you build this? 👇"}
    return {"template": "card.html.j2", "data": data, "kind": "business",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []), cta=config.CTA_TAG)}


def gen_didyouknow() -> dict:
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}

Create ONE "Did You Know" card. Either (A) a ranked comparison suited to a bar
chart (3-6 items with real % values), OR (B) a single astonishing true fact.
Prefer (A) when a good real dataset exists (e.g. % DNA shared across species,
genome sizes, time scales).

Respond ONLY as JSON. For (A):
{{"mode":"bars","title":"short question headline","title_size":64,
  "lede":"one setup line; wrap the metric in <span class='hl'>...</span>",
  "bars":[{{"name":"label","sub":"optional small note or empty","val":<int 0-100>}}],
  "footer_sub":"a question + 👇","fb_hook":"","fb_body":"","hashtags":["6-9"]}}
For (B):
{{"mode":"fact","title":"headline","lede":"the fact in 1-2 sentences, <b>key</b>",
  "callout":"why it's amazing/useful","footer_sub":"a question + 👇",
  "fb_hook":"","fb_body":"","hashtags":["6-9"]}}
All numbers must be real."""
    d = _json(_gen(prompt, temp=0.8))
    data = {"series": "Did You Know", "title": d["title"],
            "title_size": d.get("title_size", 66), "lede": d.get("lede"),
            "footer_sub": d.get("footer_sub", "Which surprised you most? 👇")}
    if d.get("mode") == "bars" and d.get("bars"):
        data["bars"] = d["bars"][:6]
    else:
        data["callout"] = d.get("callout")
    return {"template": "card.html.j2", "data": data, "kind": "didyouknow",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []))}


# ---------------------------------------------------------------------------
# GROUNDED pillars (Gemini + Google Search) — current & real
# ---------------------------------------------------------------------------
def gen_opportune() -> dict:
    from datetime import date
    today = date.today().isoformat()
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Today is {today}. Use Google Search to find ONE real, currently-open opportunity
for biotech/biochem/bioinformatics students or early scientists — a conference,
scholarship, fellowship, competition, or summer school — whose registration or
application DEADLINE is still in the future. Verify it is real and current.

Respond ONLY as JSON:
{{"title":"short event/opportunity name, max 7 words","kicker":"type · field, e.g. 'Scholarship · Genomics'",
  "lede":"1-2 sentences: what it is and who it's great for",
  "meta":[{{"icon":"📅","label":"When","value":"<b>dates or N/A</b>"}},
          {{"icon":"📍","label":"Where","value":"location or Online"}},
          {{"icon":"⏳","label":"Deadline","value":"<b>the real deadline</b>"}}],
  "link_display":"short domain e.g. slas.org/awards","url":"the real full URL",
  "tip":"one practical sentence on why to apply",
  "fb_hook":"caption hook","fb_body":"caption body","hashtags":["6-9"]}}"""
    d = _json(_gen(prompt, grounded=True, temp=0.3))
    data = {"series": "Bio · Opportune", "kicker": d.get("kicker"),
            "title": d["title"], "title_size": 58, "lede": d.get("lede"),
            "meta": d.get("meta", []), "linkchip": d.get("link_display"),
            "callout": d.get("tip"), "callout_tone": "gold",
            "footer_sub": "Save before the deadline 🔖"}
    url = d.get("url", "")
    cap_body = (d.get("fb_body", "") + (f"\n\n🔗 {url}" if url else "")).strip()
    return {"template": "card.html.j2", "data": data, "kind": "opportune",
            "caption": _caption(d.get("fb_hook", d["title"]), cap_body,
                                 d.get("hashtags", [])), "url": url}


def gen_paper() -> dict:
    from datetime import date
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Today is {date.today().isoformat()}. Use Google Search to find ONE real, recent
(last ~12 months) notable paper/result in biotech/biochem/bioinformatics. Summarize
it AND extract the concrete business or career OPPORTUNITY it points to.

Respond ONLY as JSON:
{{"title":"vivid plain-English headline, max 7 words","kicker":"subfield e.g. 'Gene Editing'",
  "blocks":[{{"head":"📄 The paper","body":"what they did & found, plain English, <b>key</b>; name the journal if sure"}},
            {{"head":"💰 The opportunity","body":"the business/career angle; name a company if one exists","tone":"blue"}}],
  "takeaway":"one 'for you' sentence on where the value/jobs are, <b>key</b>",
  "fb_hook":"caption hook","fb_body":"caption body","hashtags":["6-9"]}}
Do not fabricate a DOI or company; omit if unsure."""
    d = _json(_gen(prompt, grounded=True, temp=0.4))
    data = {"series": "Paper → Opportunity", "kicker": d.get("kicker"),
            "title": d["title"], "title_size": 60, "blocks": d.get("blocks", []),
            "callout": d.get("takeaway"), "callout_tone": "gold",
            "footer_sub": "Follow for the science behind the startups"}
    return {"template": "card.html.j2", "data": data, "kind": "paper",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []))}


def gen_tech() -> dict:
    """Latest-tech card as a photo-hero (needs a Pexels image)."""
    from datetime import date
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Today is {date.today().isoformat()}. Use Google Search to find ONE real, recent
development/trend in biotech or bioinformatics worth explaining simply.

Respond ONLY as JSON:
{{"title":"plain headline, max 6 words","kicker":"the subfield, Title Case",
  "lede":"1-2 sentences explaining it simply, <b>key</b>",
  "photo_queries":["3-4 attractive stock-photo search queries that fit it"],
  "fb_hook":"caption hook","fb_body":"caption body","hashtags":["6-9"]}}"""
    d = _json(_gen(prompt, grounded=True, temp=0.5))
    data = {"layout": "hero", "series": "New Tech", "kicker": d.get("kicker"),
            "title": d["title"], "lede": d.get("lede"),
            "footer_sub": "Follow for the tech shaping biotech",
            "_photo_queries": d.get("photo_queries", ["modern laboratory science"])}
    return {"template": "card_photo.html.j2", "data": data, "kind": "tech",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []))}


def _event_like(kind, series, search_line, meta_spec, footer, cta=None):
    """Shared builder for event/job (graphic card with meta rows + link)."""
    from datetime import date
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Today is {date.today().isoformat()}. {search_line}
Respond ONLY as JSON:
{{"title":"max 7 words","kicker":"short label","lede":"1-2 sentences",
  "meta":[{meta_spec}],
  "link_display":"short domain","url":"real full URL","tip":"one practical sentence",
  "fb_hook":"","fb_body":"","hashtags":["6-9"]}}"""
    d = _json(_gen(prompt, grounded=True, temp=0.3))
    data = {"series": series, "kicker": d.get("kicker"), "title": d["title"],
            "title_size": 58, "lede": d.get("lede"), "meta": d.get("meta", []),
            "linkchip": d.get("link_display"), "callout": d.get("tip"),
            "callout_tone": "gold", "footer_sub": footer}
    url = d.get("url", "")
    body = (d.get("fb_body", "") + (f"\n\n🔗 {url}" if url else "")).strip()
    return {"template": "card.html.j2", "data": data, "kind": kind,
            "caption": _caption(d.get("fb_hook", d["title"]), body, d.get("hashtags", []), cta=cta), "url": url}


def gen_event(recent=None) -> dict:
    """Prefer a REAL upcoming event scraped from curated listing sites (quota-free,
    with real date/place/link); fall back to a grounded Gemini search, then the bank."""
    recent = recent if recent is not None else load_recent()
    try:
        ev = _pick_event(recent)
    except Exception as exc:
        print(f"  event sources unavailable ({exc}); using Gemini search")
        ev = None
    if ev:
        return _event_from_source(ev)
    return _event_like(
        "event", "Bio · Event",
        "Use Google Search to find ONE real, UPCOMING flagship conference in genomics/biotech/"
        "bioinformatics (e.g. AGBT, ISMB/ECCB, Keystone Symposia, Gordon Research Conferences, "
        "SynBioBeta, Festival of Genomics, ASHG) whose dates are in the future. Verify it is real.",
        '{"icon":"📅","label":"When","value":"<b>dates</b>"},{"icon":"📍","label":"Where","value":"city, country or Virtual"},{"icon":"🎟️","label":"Register","value":"status or deadline"}',
        "Save this conference 🔖")


def _pick_event(recent) -> dict | None:
    """One fresh, soon upcoming event not already covered in ``recent``."""
    import random
    import event_sources
    evs = event_sources.fetch_events()
    if not evs:
        return None
    avoid = {fallbacks._norm(x) for x in (recent or [])}
    fresh = [e for e in evs if fallbacks._norm(e["title"]) not in avoid]
    pool = fresh or evs
    # Bias toward the soonest events (timely) while keeping some variety.
    return random.choice(pool[:max(3, len(pool) * 2 // 3)])


def _event_from_source(ev: dict) -> dict:
    """Render a scraped real event as a catchy MABCOS event card."""
    import event_sources
    loc = ev["location"] or "See details"
    dom = event_sources.domain(ev["link"])
    prompt = f"""{VOICE}
{CAPTION_STYLE}
Write a short, exciting MABCOS post about this REAL upcoming event. Do NOT change the
name, date or place, and do not invent a venue or speakers. Make students and scientists
want to attend or share it.
EVENT: {ev['title']}
DATE: {ev['date']}
PLACE: {loc}
Respond ONLY as JSON:
{{"title":"a punchy 4-7 word card headline (not the full event name)",
  "lede":"1 sentence on who it's for / why it matters, <b>key</b>",
  "fb_hook":"scroll-stopping first line, no emoji",
  "fb_body":"2-3 short lines: what it is, why go, who should attend; end with a question",
  "hashtags":["2-3"]}}"""
    try:
        d = _json(_gen(prompt, grounded=False, temp=0.6))
    except Exception as exc:
        print(f"  event rewrite failed ({exc}); using the listing directly")
        where = f" · {loc}" if ev["location"] else ""
        d = {"title": _shorten(ev["title"], 52),
             "lede": f"Mark your calendar — <b>{ev['date']}</b>{where}",
             "fb_hook": f"{ev['title']} — {ev['date']}" + (f", {loc}" if ev["location"] else ""),
             "fb_body": (f"Happening {ev['date']}" + (f" in {loc}" if ev["location"] else "")
                         + ". Worth a look if you're in biotech — details and registration at the link."),
             "hashtags": ["biotech", "conference", "biotechnology"]}
    meta = [{"icon": "📅", "label": "When", "value": f"<b>{ev['date']}</b>"}]
    if ev["location"]:
        meta.append({"icon": "📍", "label": "Where", "value": loc})
    meta.append({"icon": "🔗", "label": "Info", "value": dom})
    data = {"series": "Bio · Event", "kicker": "Upcoming Event", "title": d["title"],
            "title_size": 54, "lede": d.get("lede"), "meta": meta,
            "linkchip": dom, "callout": "Save it, share it, show up.", "callout_tone": "gold",
            "footer_sub": "Upcoming in biotech"}
    url = ev["link"]
    where = f" · {loc}" if ev["location"] else ""
    body = (d.get("fb_body", "") + f"\n\n📅 {ev['date']}{where}\n🔗 {url}").strip()
    return {"template": "card.html.j2", "data": data, "kind": "event",
            "caption": _caption(d.get("fb_hook", ev["title"]), body, d.get("hashtags", []),
                                cta="Save this conference 🔖"), "url": url}


def gen_job() -> dict:
    return _event_like(
        "job", "Bio · Jobs",
        "Use Google Search to find ONE real, currently-open JOB or INTERNSHIP in biotech/biochem/"
        "bioinformatics suited to a student or early-career scientist (entry-level, internship or "
        "junior). Verify it is open now.",
        '{"icon":"🏢","label":"Company","value":"<b>name</b>"},{"icon":"📍","label":"Location","value":"city / Remote"},{"icon":"💼","label":"Type","value":"Full-time / Internship / Junior"}',
        "Tag someone who should apply 👇", cta=config.CTA_TAG)


def _photo_current(kind, series, search_line, extra_fields, footer, link_field, data_extra=None, cta=None):
    """Shared builder for news/tutorial (photo-hero + link)."""
    from datetime import date
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Today is {date.today().isoformat()}. {search_line}
Respond ONLY as JSON:
{{"title":"max 8 words","kicker":"topic","lede":"1-2 sentences, <b>key</b>",{extra_fields}
  "url":"real full URL","photo_queries":["3-4 attractive stock-photo queries"],
  "fb_hook":"","fb_body":"","hashtags":["6-9"]}}"""
    d = _json(_gen(prompt, grounded=True, temp=0.4))
    data = {"layout": "hero", "series": series, "kicker": d.get("kicker"),
            "title": d["title"], "lede": d.get("lede"),
            "linkchip": d.get(link_field), "footer_sub": footer,
            "_photo_queries": d.get("photo_queries", ["modern laboratory science"])}
    if data_extra:
        data.update(data_extra)
    url = d.get("url", "")
    body = (d.get("fb_body", "") + (f"\n\n🔗 {url}" if url else "")).strip()
    return {"template": "card_photo.html.j2", "data": data, "kind": kind,
            "caption": _caption(d.get("fb_hook", d["title"]), body, d.get("hashtags", []), cta=cta), "url": url}


def gen_news() -> dict:
    return _photo_current(
        "news", "Bio · News",
        "Use Google Search to find ONE real, RECENT (last ~2 weeks) news development in biotech/"
        "biochem/bioinformatics worth sharing. Verify it.",
        '"source_display":"short source domain e.g. nature.com",',
        "Follow for biotech news that matters", "source_display")


def gen_tutorial() -> dict:
    return _photo_current(
        "tutorial", "Tutorial",
        "Use Google Search to find ONE genuinely excellent, FREE, currently-available tutorial / "
        "course / learning resource for biotech/biochem/bioinformatics students (e.g. Rosalind, "
        "Galaxy Training, an EMBL-EBI course, a famous MOOC, a great YouTube series). Verify it is free.",
        '"resource_display":"short domain of the resource",',
        "Save this to learn later 🔖", "resource_display", cta=config.CTA_SAVE)


def gen_success() -> dict:
    from datetime import date
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}
Use Google Search to find ONE real, inspiring success story in biotech/biochem/bioinformatics —
a scientist, founder or company whose story motivates students. Verify the facts; no invented
quotes or awards.
Respond ONLY as JSON:
{{"title":"short inspiring headline, max 7 words","kicker":"who / field",
  "lede":"2-3 short sentences telling the story, <b>key</b>",
  "stat":{{"n":"one real number","l":"what it represents, <=9 words"}},
  "photo_queries":["3-4 SYMBOLIC stock-photo queries WITHOUT a person's face (labs, molecules, DNA, glassware) — the image is representative, never implying it is the real person"],
  "fb_hook":"","fb_body":"","hashtags":["6-9"]}}"""
    d = _json(_gen(prompt, grounded=True, temp=0.5))
    data = {"layout": "full", "series": "Success Story", "kicker": d.get("kicker"),
            "title": d["title"], "title_size": 60, "lede": d.get("lede"),
            "stat": d.get("stat"), "footer_sub": "Follow for stories that inspire",
            "_photo_queries": d.get("photo_queries", ["scientist laboratory success"])}
    return {"template": "card_photo.html.j2", "data": data, "kind": "success",
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""), d.get("hashtags", []))}


def gen_sciencenews(recent=None) -> dict:
    """Pull a REAL current headline from top sources (Nature, GEN, IEEE Spectrum,
    ScienceDaily, Harvard Gazette) and rewrite it as a catchy, credible MABCOS post
    with the real source link."""
    import random
    import news_sources
    recent = recent if recent is not None else load_recent()
    items = news_sources.fetch_items()
    if not items:
        raise RuntimeError("no science-news items available")
    avoid = {fallbacks._norm(x) for x in (recent or [])}
    fresh = [it for it in items if fallbacks._norm(it["title"]) not in avoid]
    it = random.choice(fresh or items)
    prompt = f"""{VOICE}
{CAPTION_STYLE}
Rewrite this REAL science-news item as a MABCOS post. Stay strictly accurate to the
item — do NOT invent facts, numbers, or claims beyond what's given.
HEADLINE: {it['title']}
SUMMARY: {it['summary']}
SOURCE: {it['source']}
Respond ONLY as JSON:
{{"title":"a punchy 4-8 word card headline","kicker":"via {it['source']}",
  "lede":"1-2 plain-English sentences on what it is, <b>key</b>",
  "photo_queries":["3-4 attractive stock-photo queries fitting the topic"],
  "fb_hook":"scroll-stopping first line, no emoji","fb_body":"2-3 short paragraphs on the finding and why it matters; end with a question","hashtags":["2-3"]}}"""
    try:
        d = _json(_gen(prompt, grounded=False, temp=0.6))
    except Exception as exc:
        print(f"  sciencenews rewrite failed ({exc}); using the headline directly")
        d = {"title": _shorten(it["title"], 64), "kicker": f"via {it['source']}",
             "lede": it["summary"][:200],
             "photo_queries": ["science laboratory research", "dna molecule blue", "microscope close up"],
             "fb_hook": it["title"], "fb_body": it["summary"][:380],
             "hashtags": ["biotechnology", "science", "research"]}
    data = {"layout": "hero", "series": "Science News", "kicker": d.get("kicker"),
            "title": d["title"], "lede": d.get("lede"),
            "linkchip": news_sources.domain(it["link"]),
            "footer_sub": "Follow for the science that matters",
            "_photo_queries": d.get("photo_queries", ["science laboratory research"])}
    url = it["link"]
    body = (d.get("fb_body", "") + f"\n\nSource: {it['source']}\n🔗 {url}").strip()
    return {"template": "card_photo.html.j2", "data": data, "kind": "sciencenews",
            "caption": _caption(d.get("fb_hook", it["title"]), body, d.get("hashtags", [])), "url": url}


# Registry (per-card generators; used for the one grounded "current" card).
GENERATORS = {
    "education": gen_education, "business": gen_business, "didyouknow": gen_didyouknow,
    "opportune": gen_opportune, "paper": gen_paper, "tech": gen_tech,
    "event": gen_event, "job": gen_job, "news": gen_news,
    "tutorial": gen_tutorial, "success": gen_success, "sciencenews": gen_sciencenews,
}

# ---------------------------------------------------------------------------
# FREE-TIER FRUGAL BATCH: one Gemini call for several evergreen cards, plus one
# grounded call for a current card. Everything falls back to the local bank so a
# batch always ships even when the quota is spent.
# ---------------------------------------------------------------------------
import random as _random


def _json_array(text: str) -> list:
    cleaned = re.sub(r"```(?:json)?|```", "", text).strip()
    s, e = cleaned.find("["), cleaned.rfind("]")
    if s == -1 or e == -1:
        raise ValueError("no JSON array in model output")
    return json.loads(cleaned[s:e + 1])


def _map(kind: str, d: dict) -> dict:
    """Map one parsed object to a {template,data,caption,kind} result."""
    if kind == "education":
        data = {"series": "Bio · Education", "kicker": d.get("kicker"),
                "title": d["title"], "lede": d.get("lede"),
                "stats": d.get("stats", [])[:2], "callout": d.get("callout")}
        cta = config.CTA_FOLLOW
    elif kind == "business":
        data = {"series": "Bio · Business Idea", "kicker": "Venture", "title_size": 66,
                "title": d["title"], "lede": d.get("lede"),
                "blocks": d.get("blocks", []), "footer_sub": "Would you build this? 👇"}
        cta = config.CTA_TAG
    elif kind == "didyouknow":
        data = {"series": "Did You Know", "title": d["title"],
                "title_size": d.get("title_size", 64), "lede": d.get("lede"),
                "footer_sub": d.get("footer_sub", "Which surprised you most? 👇")}
        if d.get("bars"):
            data["bars"] = d["bars"][:6]
        else:
            data["callout"] = d.get("callout")
        cta = config.CTA_FOLLOW
    elif kind == "interactive":
        data = {"series": d.get("pill", "Poll"), "kicker": d.get("kicker"),
                "title": d["title"], "title_size": d.get("title_size", 60),
                "lede": d.get("lede"), "options": d.get("options", [])[:4],
                "callout": d.get("callout"), "callout_tone": "gold",
                "footer_sub": d.get("footer_sub", "Vote in the comments 👇")}
        cta = config.CTA_FOLLOW
    elif kind == "opinion":
        data = {"series": d.get("pill", "Hot Take"), "kicker": d.get("kicker", "Opinion"),
                "title": d["title"], "title_size": d.get("title_size", 58),
                "lede": d.get("lede"), "callout": d.get("callout", "Agree or disagree? 👇"),
                "callout_tone": "gold", "footer_sub": d.get("footer_sub", "Agree or disagree? 👇")}
        cta = config.CTA_SHARE
    else:
        raise ValueError(f"no batch mapper for {kind}")
    return {"template": "card.html.j2", "data": data, "kind": kind,
            "caption": _caption(d.get("fb_hook", d["title"]), d.get("fb_body", ""),
                                 d.get("hashtags", []), cta=cta)}


_BATCH_SPEC = {
    "education": "a 'Bio-Education' fact with REAL numbers -> fields: kicker, title (<=8 words), lede (use <b>key</b>), stats (array of exactly 2 {n,l}), callout, fb_hook, fb_body, hashtags (6-9)",
    "business": "a concrete 'Bio-Business Idea' venture -> fields: title (<=6 words), lede, blocks (array of 3: {head:'💡 The idea',body},{head:'💰 Who pays',body},{head:'🚀 Why now',body,tone:'blue'}), fb_hook, fb_body, hashtags",
    "didyouknow": "a 'Did You Know' bar-chart fact with 3-6 REAL percentages -> fields: title, lede (wrap the metric in <span class='hl'>...</span>), bars (array of {name,sub,val 0-100}), footer_sub, fb_hook, fb_body, hashtags",
    "interactive": "a poll / this-or-that / quiz that makes people comment -> fields: pill (short label: 'Poll' or 'This or That' or 'Quiz'), title (the question), lede (1 short setup line or empty), options (array of 2-4 {key:'A'/'B'/'C', text}), callout (the vote instruction e.g. 'Comment A or B 👇'), footer_sub, fb_hook, fb_body, hashtags",
    "opinion": "a bold but FAIR opinion / hot-take about biotech, science careers, ethics, or the future of the field that makes people want to weigh in (never offensive, never misinformation) -> fields: pill ('Hot Take' or 'Opinion'), title (the claim in <=10 words), lede (1 line of nuance, use <b>key</b>), callout (e.g. 'Agree or disagree? Tell me below 👇'), footer_sub, fb_hook, fb_body (make the case in 2-3 short lines, END with 'Where do you stand?'), hashtags (3)",
}


def _avoid_note(recent) -> str:
    recent = [r for r in (recent or []) if r][-24:]
    if not recent:
        return ""
    return ("\n\nDo NOT repeat or closely echo any of these recently-posted titles/"
            "topics — pick genuinely DIFFERENT ones:\n- " + "\n- ".join(recent))


def batch_evergreen(kinds: list[str], recent=None) -> list[dict]:
    """ONE Gemini call for several evergreen cards; per-kind fallback on failure."""
    if not kinds:
        return []
    specs = "\n".join(f"{i+1}) {k}: {_BATCH_SPEC[k]}" for i, k in enumerate(kinds))
    prompt = f"""{VOICE}
{ACCURACY}
{CAPTION_STYLE}{_avoid_note(recent)}

Produce content for {len(kinds)} different cards. Respond with ONLY a JSON ARRAY of
exactly {len(kinds)} objects, IN THIS EXACT ORDER (no markdown, no extra text):
{specs}

Each object contains only that card's fields. All facts and numbers must be real."""
    try:
        arr = _json_array(_gen(prompt, temp=0.85))
    except Exception as exc:
        print(f"  batch_evergreen failed ({exc}); using local fallbacks")
        return [fallbacks.pick(k, recent) for k in kinds]
    out = []
    for i, k in enumerate(kinds):
        try:
            out.append(_map(k, arr[i]))
        except Exception as exc:
            print(f"  mapping {k} failed ({exc}); fallback")
            out.append(fallbacks.pick(k, recent))
    return out


def current_card(kind: str, recent=None) -> dict:
    """One grounded (search) card; falls back to the evergreen bank on failure."""
    try:
        return GENERATORS[kind]()
    except Exception as exc:
        print(f"  grounded {kind} failed ({exc}); using local fallback")
        return fallbacks.pick(kind, recent)


# Rotation pools so each run covers different ground. Every batch pulls 2
# evergreen cards (ONE Gemini call) + 1 current card (ONE grounded call), so all
# pillars cycle through over successive runs while staying free-tier friendly.
# interactive (polls) and opinion (hot-takes) are weighted up — they pull the most
# comments, and comments are what push a post to more people.
_EVERGREEN_POOL = ["education", "business", "didyouknow",
                   "interactive", "interactive", "opinion", "opinion"]
# "sciencenews" (real headlines from Nature/GEN/IEEE/ScienceDaily/Harvard) is weighted
# high — it's the most credible, current, source-linked pillar.
_CURRENT_POOL = ["sciencenews", "sciencenews", "sciencenews", "event", "event", "job",
                 "paper", "tech", "tutorial", "success", "opportune"]


def build_batch(seed: str = "", recent=None, n_cards: int = None) -> list[dict]:
    """A batch of ``n_cards`` feed cards (default config.CARDS_PER_RUN). Leans toward
    the timely, engaging 'current' pillars (real science news, upcoming events, papers)
    with some evergreen for variety; evergreen cards share one Gemini call. Falls back
    fully to local content when quota is spent. ``recent`` steers away from repeats.
    """
    rnd = _random.Random(seed or None)
    n = n_cards if n_cards is not None else getattr(config, "CARDS_PER_RUN", 2)
    n = max(1, n)
    # ~60% current (news/events — the posts that pull reach), rest evergreen.
    plan = ["current" if rnd.random() < 0.6 else "evergreen" for _ in range(n)]
    ev = [rnd.choice(_EVERGREEN_POOL) for k in plan if k == "evergreen"]
    results = batch_evergreen(ev, recent) if ev else []
    for k in plan:
        if k == "current":
            results.append(current_card(rnd.choice(_CURRENT_POOL), recent))
    rnd.shuffle(results)
    return results


# ---------------------------------------------------------------------------
# Rolling history so the same fact/hook doesn't repeat for weeks (anti-repetition)
# ---------------------------------------------------------------------------
from pathlib import Path as _Path
HISTORY_FILE = _Path(__file__).parent / "history.json"


def load_recent() -> list:
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8")).get("titles", [])
    except Exception:
        return []


def save_recent(new_titles) -> None:
    titles = (load_recent() + [t for t in new_titles if t])[-120:]
    try:
        HISTORY_FILE.write_text(json.dumps({"titles": titles}, indent=2), encoding="utf-8")
    except Exception:
        pass


def pick_reel_hooks(n: int, recent=None) -> list[dict]:
    """Pick n reel hooks, preferring ones not used recently (anti-repetition)."""
    avoid = {fallbacks._norm(x) for x in (recent or [])}
    fresh = [h for h in REEL_HOOKS if fallbacks._norm(h["hook"]) not in avoid]
    pool = fresh if len(fresh) >= n else REEL_HOOKS[:]
    _random.shuffle(pool)
    return pool[:n]


# ---------------------------------------------------------------------------
# Reel hooks — punchy, TRUE one-liners for the branded video overlay. Local (no
# API call), so reels cost nothing against the Gemini quota.
# ---------------------------------------------------------------------------
REEL_HOOKS = [
    {"pill": "Did You Know", "hook": "Your DNA is <span class='hl'>2 metres</span> long.",
     "sub": "And it fits inside a cell millionths of a metre wide.",
     "queries": ["dna helix animation", "dna strand glowing", "chromosome microscope", "cell nucleus microscope", "molecular structure blue"],
     "caption": _caption("Two metres of DNA, folded into one tiny cell 🤯",
                         "The packing problem alone is a marvel of biology. Follow for more.",
                         ["dna", "cellbiology", "biology", "sciencefacts", "biotechnology", "bioinformatics"])},
    {"pill": "In 15 Seconds", "hook": "DNA → RNA → <span class='hl'>Protein</span>.",
     "sub": "One flow of information behind almost all of life.",
     "queries": ["dna transcription animation", "molecular biology animation", "protein structure 3d render", "rna molecule animation", "laboratory dna analysis"],
     "caption": _caption("The central dogma, in one line 🧬",
                         "Get this and half of molecular biology clicks. Follow for more.",
                         ["centraldogma", "molecularbiology", "biochemistry", "dna", "biology", "biotechnology"])},
    {"pill": "New Tech", "hook": "AI can now <span class='hl'>design proteins</span> that never existed.",
     "sub": "From a text description to a working molecule.",
     "queries": ["artificial intelligence visualization", "protein structure rotating 3d", "molecular model animation", "data science computer screen", "futuristic laboratory"],
     "caption": _caption("AI is designing brand-new proteins 🤖🧬",
                         "A grand challenge of biology, cracked. Follow for the science behind the headlines.",
                         ["ai", "proteindesign", "bioinformatics", "biotechnology", "alphafold", "science"])},
    {"pill": "Did You Know", "hook": "<span class='hl'>CRISPR</span> = molecular scissors you can program.",
     "sub": "Tell it an address in the genome, and it cuts.",
     "queries": ["dna editing animation", "genetic engineering laboratory", "dna molecule glowing", "scientist pipette lab", "gene research microscope"],
     "caption": _caption("Gene editing, explained simply ✂️🧬",
                         "CRISPR won the 2020 Nobel and built an industry. Follow for more.",
                         ["crispr", "geneediting", "biotechnology", "genetics", "science", "biology"])},
    {"pill": "Science", "hook": "One <span class='hl'>E. coli</span> becomes millions overnight.",
     "sub": "Doubling roughly every 20 minutes in ideal conditions.",
     "queries": ["bacteria microscope", "petri dish bacteria colony", "microorganisms microscope", "cell division microscope", "laboratory culture plate"],
     "caption": _caption("Why microbes are biotech's workhorses 🦠",
                         "Fast growth = fast science and fast manufacturing. Follow for more.",
                         ["microbiology", "ecoli", "biotechnology", "biology", "sciencefacts", "research"])},
    {"pill": "mRNA", "hook": "mRNA doesn't change your DNA.",
     "sub": "It's a <span class='hl'>temporary recipe</span> your cells read, then discard.",
     "queries": ["vaccine vial laboratory", "mrna molecule render", "medical research laboratory", "scientist vaccine lab", "pipette tubes laboratory"],
     "caption": _caption("Clearing up the biggest mRNA myth 💉",
                         "A short-lived instruction, not a genome edit. Follow for clear biotech science.",
                         ["mrna", "biotechnology", "vaccines", "science", "biology", "mythbusting"])},
    {"pill": "Biochemistry", "hook": "Enzymes make reactions up to a <span class='hl'>billion times</span> faster.",
     "sub": "It's why life runs at body temperature, not in a furnace.",
     "queries": ["enzyme reaction animation", "molecular catalysis render", "protein enzyme 3d", "laboratory reaction colorful", "molecular structure blue"],
     "caption": _caption("The tiny machines that make life possible ⚙️🧬",
                         "Enzymes are nature's catalysts — staggeringly fast and specific. Follow for more.",
                         ["enzymes", "biochemistry", "biology", "metabolism", "biotechnology", "science"])},
    {"pill": "Did You Know", "hook": "Your mitochondria have their <span class='hl'>own DNA</span>.",
     "sub": "A clue they were once free-living bacteria.",
     "queries": ["mitochondria animation", "cell organelle render", "microscope cells", "molecular biology animation", "cell nucleus microscope"],
     "caption": _caption("There's a second genome inside you 🧬",
                         "Mitochondrial DNA is inherited from your mother alone. Follow for more.",
                         ["mitochondria", "cellbiology", "evolution", "genetics", "biology", "biotechnology"])},
    {"pill": "Genomics", "hook": "Reading a human genome once cost <span class='hl'>$3 billion</span>.",
     "sub": "Today it's a few hundred dollars.",
     "queries": ["dna sequencing machine", "genomics laboratory", "genome data screen", "sequencing lab equipment", "data visualization dna"],
     "caption": _caption("The fastest-falling price in science 📉🧬",
                         "Cheap sequencing is quietly reshaping medicine and biology. Follow for more.",
                         ["genomics", "sequencing", "dna", "bioinformatics", "biotechnology", "science"])},
    {"pill": "New Tech", "hook": "AI predicted <span class='hl'>200 million</span> protein structures.",
     "sub": "A 50-year puzzle, solved — and shared for free.",
     "queries": ["protein structure 3d render", "ai data visualization", "molecular model rotating", "computer science laboratory", "futuristic data"],
     "caption": _caption("AlphaFold changed biology overnight 🤖🧬",
                         "Free protein structures are accelerating drug discovery worldwide. Follow for more.",
                         ["alphafold", "ai", "bioinformatics", "proteins", "biotechnology", "science"])},
    {"pill": "Science", "hook": "Much of modern medicine is <span class='hl'>brewed</span>, not synthesized.",
     "sub": "Engineered microbes make insulin, antibiotics and more.",
     "queries": ["bioreactor fermentation", "laboratory fermentation tanks", "pharmaceutical production lab", "biotech manufacturing", "green biotech lab"],
     "caption": _caption("Your medicine might be made by microbes 🦠💊",
                         "Recombinant insulin and many antibiotics come from engineered cells. Follow for more.",
                         ["biotechnology", "fermentation", "insulin", "biomanufacturing", "science", "biology"])},
    {"pill": "Immunology", "hook": "Your body makes <span class='hl'>billions</span> of unique antibodies.",
     "sub": "A custom defense for almost any invader it meets.",
     "queries": ["antibody 3d render", "immune cells microscope", "white blood cells animation", "molecular antibody structure", "laboratory blood sample"],
     "caption": _caption("Your immune system is a billion-strong library 🛡️",
                         "Antibody diversity is one of biology's great engineering feats. Follow for more.",
                         ["immunology", "antibodies", "biology", "biotechnology", "science"])},
    {"pill": "In 15 Seconds", "hook": "<span class='hl'>PCR</span> copies one DNA strand into billions.",
     "sub": "The reaction behind every DNA test and diagnosis.",
     "queries": ["pcr machine laboratory", "thermal cycler lab", "dna amplification animation", "scientist pipetting tubes", "laboratory dna test"],
     "caption": _caption("The reaction that powers modern diagnostics 🧬",
                         "PCR turns a trace of DNA into a readable signal. Follow for more.",
                         ["pcr", "molecularbiology", "diagnostics", "biotechnology", "science"])},
    {"pill": "Did You Know", "hook": "You carry more <span class='hl'>microbial cells</span> than human ones.",
     "sub": "Your microbiome is an organ you were never taught about.",
     "queries": ["gut bacteria microscope", "microbiome animation", "bacteria colony petri dish", "microorganisms microscope", "intestine biology render"],
     "caption": _caption("You're more microbe than human 🦠",
                         "The microbiome shapes immunity, mood and metabolism. Follow for more.",
                         ["microbiome", "gutbacteria", "microbiology", "biology", "health"])},
    {"pill": "New Tech", "hook": "<span class='hl'>Stem cells</span> can become almost any cell in you.",
     "sub": "The raw material behind regenerative medicine.",
     "queries": ["stem cell microscope", "cell culture laboratory", "cells dividing animation", "regenerative medicine lab", "petri dish cells"],
     "caption": _caption("One cell type, endless possibilities 🔬",
                         "Stem cells are rebuilding how we treat disease. Follow for more.",
                         ["stemcells", "regenerativemedicine", "biology", "biotechnology", "science"])},
    {"pill": "Bioinformatics", "hook": "A single genome is <span class='hl'>3 billion</span> letters of code.",
     "sub": "Reading it is a job for algorithms, not eyes.",
     "queries": ["dna data visualization", "bioinformatics screen code", "genome sequence display", "computational biology lab", "data analysis screen"],
     "caption": _caption("Biology is now a data science 💻🧬",
                         "Bioinformatics turns raw sequence into real insight. Follow for more.",
                         ["bioinformatics", "genomics", "datascience", "biotechnology", "science"])},
    {"pill": "Science", "hook": "Antibiotic resistance kills over a <span class='hl'>million</span> people a year.",
     "sub": "The microbes are evolving faster than our drugs.",
     "queries": ["bacteria resistance microscope", "antibiotic laboratory research", "petri dish bacteria", "pharmaceutical research lab", "microbiology culture"],
     "caption": _caption("The slow-motion crisis in medicine 🦠",
                         "Why new antibiotics and smart stewardship matter now. Follow for more.",
                         ["antibioticresistance", "microbiology", "publichealth", "biotechnology", "science"])},
    {"pill": "Synthetic Biology", "hook": "Scientists can now <span class='hl'>program cells</span> like computers.",
     "sub": "Genetic circuits that sense, decide and respond.",
     "queries": ["synthetic biology lab", "genetic engineering animation", "bioreactor laboratory", "molecular circuit render", "biotech research lab"],
     "caption": _caption("Cells as living, programmable machines ⚙️🧬",
                         "Synthetic biology is engineering life itself. Follow for more.",
                         ["syntheticbiology", "genetesting", "biotechnology", "bioengineering", "science"])},
    {"pill": "Did You Know", "hook": "A virus is just <span class='hl'>genes in a shell</span>.",
     "sub": "Not quite alive — yet it rewrites the rules of biology.",
     "queries": ["virus 3d render", "virus particle animation", "molecular virus structure", "laboratory virology research", "microscope pathogen"],
     "caption": _caption("What even IS a virus? 🦠",
                         "Genes wrapped in protein, borrowing your cells to copy itself. Follow for more.",
                         ["virology", "virus", "microbiology", "biology", "science"])},
    {"pill": "Biochemistry", "hook": "Every thought you have runs on <span class='hl'>molecular signals</span>.",
     "sub": "Neurotransmitters firing across tiny gaps, billions of times a second.",
     "queries": ["neuron animation", "brain cells microscope", "synapse 3d render", "neuroscience laboratory", "molecular signaling render"],
     "caption": _caption("Your mind is biochemistry in motion 🧠",
                         "Neurotransmitters turn chemistry into thought. Follow for more.",
                         ["neuroscience", "biochemistry", "brain", "biology", "science"])},
]
