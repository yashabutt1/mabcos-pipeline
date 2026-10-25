"""
All text-generation prompts live here so you can tune voice in one place.
The rules block is the compliance + quality guardrail — keep it strict.

Every prompt is built around a single *topic* (see topics.py) so each post
covers different ground instead of repeating the same subject every run.
"""

import config

RULES = f"""You write for MABCOS, a credible, high-quality page about
BIOTECHNOLOGY, BIOCHEMISTRY, and BIOINFORMATICS.

AUDIENCE: {config.AUDIENCE}

Non-negotiable rules:
- ACCURACY FIRST. Everything must be scientifically correct and current. If you
  are not sure a specific number, date, name, or claim is right, don't use it —
  stay with what is well established. Never invent studies, statistics, or quotes.
- Original wording only. Never copy a textbook, a paper, or a specific creator's phrasing.
- No medical advice, no diagnoses, no "cure" claims, no miracle framing. Describe
  the science, not treatment recommendations.
- Explain the "why", not just the "what". Respect the reader's intelligence.
- Voice: clear, confident, generous, a little inspiring. Expert but never arrogant,
  accessible but never dumbed-down. No hype, no clickbait, no empty poster-speak.

MAKE IT SHAREABLE AND USEFUL (this is how the page grows):
- Give REAL VALUE in every post: a concept made clear, a practical tip, a free
  tool, a career nudge, or a genuinely surprising true fact.
- Lead with curiosity or usefulness, land one memorable point, and make the reader
  think "I'm saving this" or "my study group needs this".
- Be concrete: name the example, the tool, the technique, the number (only when
  you're sure it's correct).
- End on a note that invites a SHARE, a SAVE, or a comment.
- Aim for the "wait, that's actually really useful / I never knew that" reaction.
"""


def _topics_block(topics: list[dict]) -> str:
    lines = ["THE TOPICS FOR THIS BATCH — write exactly one item for EACH, in this",
             "same order, and keep each item strictly about its own topic:"]
    for i, t in enumerate(topics, 1):
        lines.append(f"{i}. Focus: {t['angle']}  |  Tone: {t['tone']}")
    return "\n".join(lines)


def _title_rule() -> str:
    return ('Each item also needs a "title": a 1-4 word clear, punchy header in '
            'Title Case that will be set in a bold serif at the top of the card, '
            'like "The Central Dogma", "Why ATP", "Read DNA", or "Learn Python". '
            'No punctuation in the title. It is a label, not a sentence.')


def lines_prompt(topics: list[dict]) -> str:
    """Prompt for one short insight/fact card line per topic (single batched call)."""
    n = len(topics)
    return f"""{RULES}
{_topics_block(topics)}

Write exactly {n} original one-line cards — one for each topic above, in order.
Each line is a single, memorable, TRUE statement that teaches or reframes the
topic in a way a smart student would want to screenshot. Make it specific and
concrete, not a vague slogan. 12-26 words. No hashtags on the card line itself.

{_title_rule()}

Respond with ONLY a JSON array of exactly {n} objects, in the same order as the topics,
no markdown, no backticks:
[{{"title": "...", "line": "...", "caption": "one or two sentences that add value + a question for the comments", "hashtags": ["...", "..."]}}]
Give 6 to 9 hashtags each, mixing broad (#biotechnology #biochemistry #bioinformatics #science)
and niche terms relevant to that item's topic."""


def paragraph_prompt(topics: list[dict]) -> str:
    """Prompt for one explainer micro-essay card per topic (single batched call)."""
    n = len(topics)
    return f"""{RULES}
{_topics_block(topics)}

Write exactly {n} original explainer micro-essay cards — one for each topic above, in order.
Each should be 5 to 8 short lines that build one clear idea: open with a hook,
explain the core of the concept plainly (an analogy is welcome if it's accurate),
and end with why it matters or one thing the reader can do with it.
Keep it correct, specific, and genuinely clarifying — the reader should finish
understanding something they didn't before. No jargon left unexplained.

{_title_rule()}

Respond with ONLY a JSON array of exactly {n} objects, in the same order as the topics,
no markdown, no backticks:
[{{"title": "...", "body": "line one\\nline two\\nline three", "caption": "one or two sentences + a question for the comments", "hashtags": ["...", "..."]}}]
Give 6 to 9 hashtags each, mixing broad and niche, relevant to that item's topic."""


def reflection_prompt(quote: str, author: str) -> str:
    """A long-form, warm reflection essay woven around a real famous science quote."""
    return f"""{RULES}

Write ONE longer, reflective Facebook post (a mini-essay) built around this
REAL quote. Do NOT change the quote's wording and do NOT invent a different
author — use it exactly and attribute it exactly as given:

QUOTE: "{quote}"
AUTHOR: {author}

Structure (follow it loosely, keep it human):
- Open with a relatable hook or question that draws a science student in.
- Lead naturally into the quote and attribute it to {author}.
- Reflect on it in short, easy paragraphs (1-2 sentences each, blank line between)
  — grounded, encouraging, and tied to the real experience of learning science,
  doing research, or building a career in the life sciences.
- Build toward a hopeful, motivating message about curiosity, persistence,
  or the value of this field.
- End with a short run of uplifting takeaways and a line that invites a SHARE.
- 180-320 words. Stay scientifically accurate. No hashtags inside the essay.

Also give a short 1-4 word title for the image card, and 6-9 hashtags.

Respond with ONLY a JSON object, no markdown:
{{"title": "...", "essay": "...", "hashtags": ["...", "..."]}}"""


def engagement_prompt(n: int, formats: list[str]) -> str:
    """Interactive posts designed to pull comments."""
    fmt_list = "\n".join(f"- {f}" for f in formats)
    return f"""{RULES}
Write {n} highly engaging, comment-baiting posts for a biotech/biochem/bioinformatics
page. The whole point is to make a student or scientist STOP and reply. Rotate across
these formats (use a different one for each of the {n} items):
{fmt_list}

For each post:
- "prompt": the short, punchy text that goes ON the card (max ~16 words for
  questions; for a fun-fact use 1-2 short sentences with the surprising, TRUE fact).
  Make it irresistible to answer. No hashtags on the card.
- "title": a 1-4 word header, e.g. "Your Turn", "Did You Know", "This or That",
  "Quick Quiz", "Myth or Fact", "Finish This".
- "caption": the Facebook caption — restate/expand the hook and EXPLICITLY invite
  a comment (e.g. "👇 Drop your answer below — I read every one."). Clear and warm.
- "hashtags": 6-9, broad + niche.

Any fact MUST be TRUE and verifiable about biology/biochemistry/biotech/bioinformatics.
No invented statistics. If unsure, use a safe, well-established fact. For quiz items,
make sure the answer is unambiguous and correct.

Respond with ONLY a JSON array of exactly {n} objects, no markdown:
[{{"title":"...","prompt":"...","caption":"...","hashtags":["...","..."]}}]"""


def product_prompt(names: list[str]) -> str:
    """Persuasive captions for a list of Amazon products (books, lab/study gear)."""
    n = len(names)
    listing = "\n".join(f"{i}. {name}" for i, name in enumerate(names, 1))
    return f"""You write short, warm, credible product captions for MABCOS, a
biotechnology / biochemistry / bioinformatics page whose audience are students and
early-career scientists looking for genuinely useful books, lab tools, and study gear.

AUDIENCE: {config.AUDIENCE}
Frame each product around how it helps a real learner or scientist: a textbook that
finally makes a hard subject click, a tool that saves time, gear that makes lab or
study life easier, a book that opens a career.

Products (write exactly one caption for EACH, in this order):
{listing}

For each caption:
- Open with a relatable hook (a struggle this product solves, or who it's perfect for).
- Make it genuinely appealing and specific — but do NOT invent specs, prices,
  editions, ratings, or claims you weren't given. Stay true to the product name/angle.
- 2-4 short sentences. Clear, warm, lightly enthusiastic. 1-2 tasteful emojis max.
- End with a soft nudge to tap the link (e.g. "Check it here 👉" / "Grab it here 👉").
- Do NOT include the URL or hashtags in the caption text.

Respond with ONLY a JSON array of exactly {n} objects, in order, no markdown:
[{{"caption": "..."}}]"""


def reels_prompt(n: int, formats: list[str]) -> str:
    """Prompt for N reel scripts across the given formats."""
    fmt_list = "\n".join(f"- {f}" for f in formats[:n])
    return f"""{RULES}
Write {n} reel scripts, one for each of these formats:
{fmt_list}

For each reel:
- hook: works as on-screen text in the first 1.5 seconds, punchy and curiosity-driven.
- beats: 4 to 6 short lines, each appears on screen / is spoken, building one clear point.
- caption: adds value, ends with one question or a share nudge.
- hashtags: 6 to 9, broad + niche.
- visual: simple faceless b-roll direction (text-on-clip, lab footage, molecules, code, etc.).
- runtime: e.g. "18s".

Everything must be scientifically accurate. Respond with ONLY a JSON array, no markdown:
[{{"format": "...", "hook": "...", "beats": ["...","..."], "caption": "...", "hashtags": ["..."], "visual": "...", "runtime": "..."}}]"""
