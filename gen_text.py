"""Text generation for MABCOS.

The pipeline prefers Gemini for copy, but falls back to local, hand-written
templates when the API is unavailable or quota-limited so the review workflow
still runs. Every fallback fact here is scientifically accurate and safe.

Both the live prompts and the local fallbacks are organised by *topic category*
(see topics.py) so the feed keeps moving through different subjects each run.
"""
import json
import os
import random
import re

from google import genai

import config
import prompts

_client = None
if os.getenv("GEMINI_API_KEY"):
    try:
        _client = genai.Client()  # reads GEMINI_API_KEY from the environment
    except Exception:
        _client = None


def _parse_json(raw: str):
    """Strip any code fences and parse a JSON array from the model output."""
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


# ---------------------------------------------------------------------------
# Local fallback pools, tagged by topic category. These only run when Gemini is
# unreachable or out of quota. Every fact is true and well established.
# ---------------------------------------------------------------------------
_FALLBACK_LINES: list[dict] = [
    {"category": "education", "title": "The Central Dogma",
     "line": "DNA is copied into RNA, and RNA is read to build proteins — one flow of information runs almost every living thing.",
     "caption": "Get this one diagram and half of molecular biology suddenly makes sense. What concept finally clicked for you?",
     "hashtags": ["biochemistry", "molecularbiology", "centraldogma", "dna", "biotechnology", "genetics", "sciencestudent"]},
    {"category": "education", "title": "Why Enzymes",
     "line": "Enzymes don't force reactions to happen — they just lower the energy barrier, so chemistry that would take years happens in milliseconds.",
     "caption": "That's why life runs at body temperature instead of needing a furnace. Which enzyme fascinates you most?",
     "hashtags": ["biochemistry", "enzymes", "metabolism", "biology", "biotechnology", "science", "catalysis"]},
    {"category": "education", "title": "Energy Currency",
     "line": "ATP is the cell's rechargeable battery: your cells make and spend roughly your own body weight in ATP every single day.",
     "caption": "You recycle it constantly rather than storing it. Isn't that wild? What fact about the cell still amazes you?",
     "hashtags": ["biochemistry", "atp", "metabolism", "cellbiology", "biology", "science", "biotechnology"]},
    {"category": "bioinformatics", "title": "What BLAST Does",
     "line": "BLAST lets you take an unknown DNA or protein sequence and find its closest known relatives in seconds — function by similarity.",
     "caption": "It's often the first tool a bioinformatician reaches for. What was the first tool you learned?",
     "hashtags": ["bioinformatics", "blast", "genomics", "computationalbiology", "biotechnology", "datascience", "biology"]},
    {"category": "bioinformatics", "title": "Learn Python",
     "line": "A few lines of Python can rename a thousand files or parse a whole genome — the skill that quietly multiplies a biologist's output.",
     "caption": "You don't need to become a software engineer, just dangerous enough to automate the boring parts. Are you learning to code?",
     "hashtags": ["bioinformatics", "python", "coding", "biotechnology", "datascience", "learntocode", "biology"]},
    {"category": "career", "title": "Get Hired",
     "line": "The biotech graduates who stand out aren't the ones who memorized the most — they're the ones who can actually run, troubleshoot, and explain a method.",
     "caption": "Skills travel further than grades. What skill do you wish you'd started sooner?",
     "hashtags": ["biotechnology", "career", "science", "jobs", "skills", "stem", "lifesciences"]},
    {"category": "tutorial", "title": "Pipette Right",
     "line": "Pre-wet a fresh tip before measuring volatile or viscous liquids — a dry tip quietly draws the wrong volume and skews your whole assay.",
     "caption": "Tiny technique, big difference in reproducibility. What's a lab tip you wish someone had told you on day one?",
     "hashtags": ["labtips", "biotechnology", "biochemistry", "wetlab", "sciencestudent", "research", "technique"]},
    {"category": "news", "title": "mRNA Is A Platform",
     "line": "mRNA technology isn't only for vaccines — it's a way to tell your own cells to make almost any protein, which is why researchers are exploring it far beyond infectious disease.",
     "caption": "The vaccine was the first big proof, not the finish line. Where do you think it goes next?",
     "hashtags": ["biotechnology", "mrna", "science", "innovation", "biotech", "research", "futuretech"]},
    {"category": "scholarship", "title": "Stand Out",
     "line": "A strong scholarship application doesn't just list achievements — it tells one clear story about why this field, why you, and why now.",
     "caption": "Reviewers read hundreds; clarity wins. Applying to anything soon? Drop your field below. 👇",
     "hashtags": ["scholarships", "stem", "biotechnology", "students", "opportunity", "education", "science"]},
    {"category": "business", "title": "Lab To Market",
     "line": "Most biotech value isn't the discovery itself — it's turning it into something reliable, reproducible, and useful to someone who'll pay for it.",
     "caption": "Science and value are related but not the same skill. Ever thought of building something from your research?",
     "hashtags": ["biotechnology", "entrepreneurship", "startup", "innovation", "science", "business", "lifesciences"]},
    {"category": "inspiration", "title": "One Cell",
     "line": "A single one of your cells runs thousands of chemical reactions at once, copies 2 metres of DNA without tangling it, and does it silently, right now.",
     "caption": "The most astonishing machine you'll ever study is already inside you. What first made you love biology?",
     "hashtags": ["cellbiology", "biology", "science", "wonder", "biochemistry", "biotechnology", "stem"]},
]

_FALLBACK_PARAGRAPHS: list[dict] = [
    {"category": "education", "title": "The Central Dogma",
     "body": "Biology has a backbone, and it's simpler than the textbook makes it look.\nDNA holds the instructions.\nRNA carries a working copy out to where things get built.\nProteins are what actually get made — the machines that run the cell.\nDNA to RNA to protein. One direction, one flow.\nOnce you see it, replication, transcription, and translation stop being three random words and become one story.",
     "caption": "If this had clicked earlier it would've saved me a semester. What topic do you wish someone had explained simply?",
     "hashtags": ["molecularbiology", "biochemistry", "centraldogma", "genetics", "biotechnology", "sciencestudent", "dna"]},
    {"category": "bioinformatics", "title": "Why Code",
     "body": "You don't need to become a programmer to benefit from code.\nYou just need to stop doing by hand what a computer does in seconds.\nRenaming 500 files. Counting sequences. Cleaning a messy spreadsheet.\nTen minutes of Python saves ten hours a month.\nStart with one real annoyance in your own work and automate just that.\nThat's how every bioinformatician actually began.",
     "caption": "The goal isn't elegance, it's leverage. What's one task you'd love to automate?",
     "hashtags": ["bioinformatics", "python", "coding", "datascience", "biotechnology", "learntocode", "research"]},
    {"category": "career", "title": "What Gets You Hired",
     "body": "Grades open the first door. They rarely open the second.\nEmployers want to know what you can actually do on Monday morning.\nCan you run the method, read the result, and spot when it went wrong?\nCan you explain it to someone who wasn't in the room?\nPick one skill this field truly values and get genuinely good at it.\nDepth in one real skill beats a long list of things you've only heard of.",
     "caption": "Pick one skill and go deep this year. Which one are you choosing?",
     "hashtags": ["career", "biotechnology", "skills", "stem", "jobs", "lifesciences", "science"]},
    {"category": "tutorial", "title": "Read Smarter",
     "body": "You don't read a scientific paper front to back like a novel.\nStart with the abstract to see if it's even relevant.\nJump to the figures — they carry most of the real story.\nRead the last paragraph of the intro for the exact question.\nThen the conclusion for what they claim to have answered.\nOnly then dive into methods and results, and only the parts you need.",
     "caption": "Reading order is a skill nobody teaches. How do you tackle a dense paper?",
     "hashtags": ["research", "howto", "sciencestudent", "biotechnology", "academia", "study", "papers"]},
    {"category": "news", "title": "Programming Cells",
     "body": "Synthetic biology treats the cell a little like a computer.\nGenes become parts. Combinations of parts become circuits.\nResearchers design those parts so a cell does something useful on purpose —\nmake a medicine, sense a toxin, produce a material.\nIt's early, and biology is messier than code.\nBut the idea — engineering life deliberately instead of just observing it — is genuinely new.",
     "caption": "Engineering biology, not just studying it. What application excites you most?",
     "hashtags": ["syntheticbiology", "biotechnology", "innovation", "bioengineering", "science", "future", "biotech"]},
    {"category": "inspiration", "title": "Why It Matters",
     "body": "It's easy to lose the plot in the middle of an exam or a failed experiment.\nSo here's the plot.\nThe things you're learning help feed people, heal them, and clean up messes we made.\nBetter crops. Faster diagnostics. Cleaner ways to make what we need.\nYou're not just memorizing pathways.\nYou're learning the language of the people who quietly fix hard problems.",
     "caption": "Zoom out on the hard days. What made you choose the life sciences?",
     "hashtags": ["biotechnology", "science", "motivation", "stem", "lifesciences", "purpose", "biology"]},
    {"category": "scholarship", "title": "Find The Door",
     "body": "The opportunities exist. Most students just never see them in time.\nFellowships, summer research spots, travel grants, open labs.\nFollow the funding bodies and societies in your field directly.\nSet a reminder a month before every deadline you find.\nAnd email a researcher whose work you admire — politely, specifically, briefly.\nThe worst case is a no. The best case changes your path.",
     "caption": "Opportunity rewards the ones who look early. What are you applying to this year?",
     "hashtags": ["scholarships", "opportunity", "stem", "students", "biotechnology", "education", "research"]},
    {"category": "business", "title": "From Bench To Value",
     "body": "A discovery and a product are not the same thing.\nThe lab proves it can work once.\nThe hard part is making it work every time, for someone who isn't you.\nReliable. Reproducible. Something a customer actually needs.\nThat gap is where most of the value — and most of the jobs — live.\nLearning to cross it is its own skill, and it's teachable.",
     "caption": "The science is step one, not the whole staircase. Ever thought of building something?",
     "hashtags": ["entrepreneurship", "biotechnology", "startup", "innovation", "business", "science", "lifesciences"]},
]


def _strip(item: dict) -> dict:
    return {k: v for k, v in item.items() if k != "category"}


def _fallback_for_topics(pool: list[dict], topics: list[dict]) -> list[dict]:
    """Return one distinct fallback per topic, matching category where possible."""
    remaining = pool[:]
    random.shuffle(remaining)
    out: list[dict] = []
    for topic in topics:
        cat = (topic or {}).get("category")
        pick = next((x for x in remaining if x.get("category") == cat), None)
        if pick is None:
            pick = remaining[0] if remaining else random.choice(pool)
        if pick in remaining:
            remaining.remove(pick)
        out.append(_strip(pick))
    return out


def _fallback_lines(topics: list[dict]):
    return _fallback_for_topics(_FALLBACK_LINES, topics)


def _fallback_paragraphs(topics: list[dict]):
    return _fallback_for_topics(_FALLBACK_PARAGRAPHS, topics)


def _align(items, topics, pool):
    """Make ``items`` line up 1:1 with ``topics``; fill any gaps from fallback."""
    if not isinstance(items, list):
        items = []
    items = [x for x in items if isinstance(x, dict)]
    if len(items) >= len(topics):
        return items[: len(topics)]
    missing = topics[len(items):]
    return items + _fallback_for_topics(pool, missing)


def _fallback_reels(n: int):
    return [
        {
            "format": "One concept in 15 seconds — explain a single biotech idea simply",
            "hook": "DNA to RNA to protein — in 15 seconds.",
            "beats": ["DNA stores the instructions", "RNA carries a working copy", "Proteins get built from that copy", "That's the central dogma"],
            "caption": "The one flow of information behind almost all of molecular biology. What should we explain next?",
            "hashtags": ["biotechnology", "biochemistry", "molecularbiology", "centraldogma", "sciencestudent", "biology", "learnscience"],
            "visual": "Text on clean molecular b-roll (DNA helix, then protein render)",
            "runtime": "16s",
        }
        for _ in range(n)
    ]


def make_lines(topics: list[dict]):
    """One batched Gemini call -> one {title, line, caption, hashtags} per topic."""
    if not topics:
        return []
    if _client is None:
        return _fallback_lines(topics)
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL, contents=prompts.lines_prompt(topics))
        return _align(_parse_json(resp.text), topics, _FALLBACK_LINES)
    except Exception as exc:
        print(f"  Gemini line generation failed ({exc}); using local fallback content")
        return _fallback_lines(topics)


def make_paragraphs(topics: list[dict]):
    """One batched Gemini call -> one {title, body, caption, hashtags} per topic."""
    if not topics:
        return []
    if _client is None:
        return _fallback_paragraphs(topics)
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL, contents=prompts.paragraph_prompt(topics))
        return _align(_parse_json(resp.text), topics, _FALLBACK_PARAGRAPHS)
    except Exception as exc:
        print(f"  Gemini paragraph generation failed ({exc}); using local fallback content")
        return _fallback_paragraphs(topics)


def _fallback_product_caption(name: str) -> str:
    return (f"If this is on your list, it's worth a look 👇 {name} — the kind of "
            f"resource that makes a hard subject click and saves you hours down the "
            f"line. Check it here 👉")


def make_product_captions(products: list[dict]):
    """One batched Gemini call -> a persuasive caption per product (by name)."""
    if not products:
        return []
    names = [p.get("name", "") for p in products]
    if _client is None:
        return [{"caption": _fallback_product_caption(n)} for n in names]
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL, contents=prompts.product_prompt(names))
        items = _parse_json(resp.text)
        if not isinstance(items, list) or len(items) < len(names):
            raise ValueError("short/invalid product caption response")
        return items[: len(names)]
    except Exception as exc:
        print(f"  Gemini product caption failed ({exc}); using local fallback")
        return [{"caption": _fallback_product_caption(n)} for n in names]


_FALLBACK_ENGAGEMENT = [
    {"title": "Did You Know", "prompt": "Uncoiled, the DNA in just one of your cells stretches about 2 metres.",
     "caption": "Did you know? The DNA in a single human cell is about 2 metres long, yet it packs into a nucleus a few microns across. 🧬 What biology fact still blows your mind? 👇",
     "hashtags": ["biology", "dna", "sciencefacts", "biochemistry", "biotechnology", "cellbiology", "didyouknow"]},
    {"title": "Finish This", "prompt": "The one concept that finally clicked for me in biochem was ______.",
     "caption": "Finish the sentence 👇 The one concept that finally clicked for me in biochemistry was ______. Your answer might be exactly what a struggling student needs to read.",
     "hashtags": ["biochemistry", "sciencestudent", "studytips", "biotechnology", "biology", "learnscience", "stem"]},
    {"title": "This Or That", "prompt": "Wet lab or dry lab (bioinformatics)? Pick one.",
     "caption": "Be honest 👀 Wet lab or dry lab (bioinformatics)? 👇 Pick one and tell us why — no wrong answers.",
     "hashtags": ["bioinformatics", "wetlab", "biotechnology", "thisorthat", "science", "research", "lablife"]},
    {"title": "Quick Quiz", "prompt": "Name the enzyme that unwinds the DNA double helix during replication. 👇",
     "caption": "Quick quiz 🧠 Which enzyme unwinds the DNA double helix so it can be copied? 👇 Drop your answer — no Googling! (Hint: it's not polymerase.)",
     "hashtags": ["biology", "quiz", "molecularbiology", "biochemistry", "biotechnology", "sciencestudent", "dna"]},
    {"title": "Myth Or Fact", "prompt": "We only use 10% of our brain. Myth or fact?",
     "caption": "Myth or fact? 🧠 'We only use 10% of our brain.' 👇 Vote in the comments — then I'll explain what the science actually says.",
     "hashtags": ["mythbusting", "neuroscience", "biology", "sciencefacts", "biotechnology", "didyouknow", "stem"]},
    {"title": "Tag Someone", "prompt": "Your failed experiment taught you more than the ones that worked.",
     "caption": "A reminder for anyone in the middle of a rough week in the lab 💙 The failed runs are teaching you the most. 👇 Tag a lab mate who needs this today.",
     "hashtags": ["motivation", "research", "phdlife", "biotechnology", "science", "labtips", "stem"]},
    {"title": "Did You Know", "prompt": "Mitochondria carry their own DNA, separate from the DNA in your nucleus.",
     "caption": "Did you know? Your mitochondria have their very own DNA — a clue that they were once free-living bacteria. 🔬 What's the coolest fact you learned this semester? 👇",
     "hashtags": ["cellbiology", "mitochondria", "evolution", "biology", "biochemistry", "sciencefacts", "biotechnology"]},
    {"title": "Your Turn", "prompt": "What skill do you wish you'd learned earlier in your science career?",
     "caption": "For the experienced folks here 👇 What skill do you wish you'd learned earlier in your science career? Students are reading — your hindsight is their head start.",
     "hashtags": ["career", "science", "biotechnology", "skills", "stem", "advice", "lifesciences"]},
    {"title": "This Or That", "prompt": "Memorize the pathway or understand the logic? Which got you through exams?",
     "caption": "Real talk 👀 In biochem, did memorizing the pathway or understanding the logic get you through exams? 👇 Defend your strategy.",
     "hashtags": ["biochemistry", "studytips", "sciencestudent", "biology", "exams", "biotechnology", "learnscience"]},
    {"title": "Did You Know", "prompt": "Under ideal conditions, one E. coli cell can divide roughly every 20 minutes.",
     "caption": "Did you know? In ideal conditions, E. coli can double about every 20 minutes — one cell becomes millions overnight. 🦠 What's a microbiology fact that surprised you? 👇",
     "hashtags": ["microbiology", "ecoli", "biology", "sciencefacts", "biotechnology", "didyouknow", "research"]},
]


def _fallback_reflection(quote: dict) -> dict:
    q, a = quote["text"], quote["author"]
    essay = (f"Have you ever felt stuck in the middle of a hard semester or a failing experiment, "
             f"wondering if it's worth it?\n\n"
             f"{a} once said:\n\n\"{q}\"\n\n"
             f"It's a good line to keep close.\n\n"
             f"Science rarely rewards you on your schedule. The pathway doesn't make sense for weeks, "
             f"and then one evening it does. The experiment fails five times before it teaches you the "
             f"thing you actually needed to know.\n\n"
             f"That slow, stubborn progress is the real work. Curiosity is what carries you through it.\n\n"
             f"So keep asking the next question. Keep running the next assay. Keep learning the tool you've "
             f"been avoiding.\n\n"
             f"The understanding compounds, quietly, until one day you realize how far you've come. 🔬")
    return {"title": "Keep Going", "essay": essay,
            "hashtags": ["science", "motivation", "biotechnology", "research", "stem", "curiosity", "biology"]}


def make_reflection(quote: dict):
    """A long-form reflection essay woven around a real curated science quote."""
    if _client is None:
        return _fallback_reflection(quote)
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=prompts.reflection_prompt(quote["text"], quote["author"]))
        data = _parse_json(resp.text)
        if isinstance(data, list):
            data = data[0]
        if not isinstance(data, dict) or not data.get("essay"):
            raise ValueError("invalid reflection response")
        return data
    except Exception as exc:
        print(f"  Gemini reflection failed ({exc}); using local fallback")
        return _fallback_reflection(quote)


def make_engagement(n: int):
    """Interactive comment-baiting posts: {title, prompt, caption, hashtags}."""
    if n < 1:
        return []
    if _client is None:
        import random as _r
        pool = _FALLBACK_ENGAGEMENT[:]
        _r.shuffle(pool)
        return pool[:n]
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL,
            contents=prompts.engagement_prompt(n, config.ENGAGEMENT_FORMATS))
        items = _parse_json(resp.text)
        if not isinstance(items, list) or len(items) < n:
            raise ValueError("short/invalid engagement response")
        return items[:n]
    except Exception as exc:
        print(f"  Gemini engagement generation failed ({exc}); using local fallback")
        import random as _r
        pool = _FALLBACK_ENGAGEMENT[:]
        _r.shuffle(pool)
        return pool[:n]


def make_reels(n: int):
    """Return a list of reel-script dicts."""
    if n < 1:
        return []
    if _client is None:
        return _fallback_reels(n)
    try:
        resp = _client.models.generate_content(
            model=config.TEXT_MODEL, contents=prompts.reels_prompt(n, config.REEL_FORMATS))
        return _parse_json(resp.text)
    except Exception as exc:
        print(f"  Gemini reel generation failed ({exc}); using local fallback content")
        return _fallback_reels(n)
