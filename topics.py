"""Topic taxonomy + rotation for MABCOS (biotech / biochemistry / bioinformatics).

Each run picks a *different* set of topics and remembers recent picks so the feed
keeps moving through new ground instead of repeating one lane. The page's remit —
education, careers, tutorials, news, scholarships, business ideas, events — is
spread across the categories below.

Each topic carries:
  - id / category   : identity + grouping (category is matched to fallback pools)
  - angle           : what the writer should focus on (injected into prompts)
  - tone            : the register for this piece
  - pexels_queries  : image search terms that match the subject
  - mood            : palette hint for the local gradient fallback
"""
from __future__ import annotations

import json
import random
from pathlib import Path

_HISTORY_FILE = ".topic_history.json"
# Remember this many recent topic ids so picks don't repeat too soon.
_RECENT = 14


TOPICS: list[dict] = [
    # ---- education: core concepts explained clearly -----------------------
    {
        "id": "central_dogma",
        "category": "education",
        "angle": "the central dogma (DNA -> RNA -> protein) explained so it finally clicks, with why it matters",
        "tone": "clear, confident, teacherly",
        "pexels_queries": ["dna helix blue", "molecular biology render", "genetic code abstract"],
        "mood": "blue DNA double helix abstract, glowing, scientific",
    },
    {
        "id": "enzyme_kinetics",
        "category": "education",
        "angle": "what enzymes actually do and why they speed up life's reactions, with one intuitive analogy",
        "tone": "clear, vivid, concrete",
        "pexels_queries": ["protein structure render", "molecular model", "biochemistry abstract"],
        "mood": "green and teal molecular structure render, clean dark background",
    },
    {
        "id": "pcr_explained",
        "category": "education",
        "angle": "how PCR copies DNA and why it changed biology, in plain language",
        "tone": "clear, practical, illuminating",
        "pexels_queries": ["pcr machine laboratory", "lab equipment close up", "pipette tubes"],
        "mood": "microscope and glassware in a modern laboratory, shallow depth of field",
    },
    {
        "id": "crispr_basics",
        "category": "education",
        "angle": "what CRISPR-Cas9 is and how gene editing works, without the hype",
        "tone": "credible, clear, balanced",
        "pexels_queries": ["dna editing abstract", "genetic engineering", "molecular render blue"],
        "mood": "blue DNA double helix abstract, glowing, scientific",
    },
    {
        "id": "metabolism_atp",
        "category": "education",
        "angle": "why ATP is the cell's energy currency and what that really means",
        "tone": "clear, memorable, concrete",
        "pexels_queries": ["mitochondria illustration", "cell biology render", "molecular energy abstract"],
        "mood": "green and teal molecular structure render, clean dark background",
    },

    # ---- bioinformatics: computation, tools, coding -----------------------
    {
        "id": "sequence_alignment",
        "category": "bioinformatics",
        "angle": "what sequence alignment (BLAST) does and why comparing sequences reveals function",
        "tone": "clear, practical, geeky-but-friendly",
        "pexels_queries": ["code on screen", "data visualization blue", "programming computer"],
        "mood": "data visualization of a genome, blue and cyan code-like pattern",
    },
    {
        "id": "learn_python_bio",
        "category": "bioinformatics",
        "angle": "why Python is the first language a biologist should learn and one tiny thing it automates",
        "tone": "encouraging, practical, motivating",
        "pexels_queries": ["python code screen", "laptop coding", "programmer workspace"],
        "mood": "abstract network of connected nodes, bioinformatics, deep blue",
    },
    {
        "id": "free_bio_tools",
        "category": "bioinformatics",
        "angle": "a genuinely useful free bioinformatics tool/database and exactly what you'd use it for",
        "tone": "generous, practical, resourceful",
        "pexels_queries": ["data dashboard screen", "computer analysis", "network nodes abstract"],
        "mood": "abstract network of connected nodes, bioinformatics, deep blue",
    },
    {
        "id": "genomics_data",
        "category": "bioinformatics",
        "angle": "how reading a whole genome became cheap and fast, and what that unlocks",
        "tone": "clear, awed-but-grounded",
        "pexels_queries": ["dna sequencing data", "genome visualization", "blue data abstract"],
        "mood": "data visualization of a genome, blue and cyan code-like pattern",
    },

    # ---- careers / skills -------------------------------------------------
    {
        "id": "career_skills",
        "category": "career",
        "angle": "one concrete skill that makes a biotech/biochem graduate far more employable",
        "tone": "direct, encouraging, practical",
        "pexels_queries": ["scientist laptop lab", "professional laboratory", "lab coat workspace"],
        "mood": "microscope and glassware in a modern laboratory, shallow depth of field",
    },
    {
        "id": "lab_to_industry",
        "category": "career",
        "angle": "the mindset shift from academic lab to biotech industry, and why it matters",
        "tone": "mentoring, honest, encouraging",
        "pexels_queries": ["biotech company lab", "team meeting lab", "modern laboratory clean"],
        "mood": "green plants in a tissue-culture lab, biotechnology, bright and clean",
    },
    {
        "id": "research_habits",
        "category": "career",
        "angle": "a research/study habit that compounds — how strong scientists actually work",
        "tone": "wise, practical, motivating",
        "pexels_queries": ["student studying notes", "research notebook desk", "focused work desk"],
        "mood": "petri dishes and pipettes on a clean bench, soft light",
    },

    # ---- tutorials / how-to (lab + dry lab) -------------------------------
    {
        "id": "pipetting_technique",
        "category": "tutorial",
        "angle": "one lab technique done right (e.g. accurate pipetting) and the common mistake to avoid",
        "tone": "practical, precise, helpful",
        "pexels_queries": ["pipette laboratory hands", "lab bench equipment", "micropipette tubes"],
        "mood": "a researcher's gloved hands with a pipette, crisp light, laboratory",
    },
    {
        "id": "reading_papers",
        "category": "tutorial",
        "angle": "how to read a scientific paper efficiently without drowning in jargon",
        "tone": "practical, reassuring, step-by-step",
        "pexels_queries": ["reading documents desk", "research papers laptop", "study notes"],
        "mood": "data visualization of a genome, blue and cyan code-like pattern",
    },
    {
        "id": "lab_safety",
        "category": "tutorial",
        "angle": "a lab-safety habit that separates careful scientists from reckless ones",
        "tone": "serious-but-warm, practical",
        "pexels_queries": ["laboratory safety gloves", "lab coat goggles", "clean lab bench"],
        "mood": "petri dishes and pipettes on a clean bench, soft light",
    },

    # ---- news / emerging tech (framed evergreen, not dated) ---------------
    {
        "id": "mrna_tech",
        "category": "news",
        "angle": "why mRNA technology is a platform (not just vaccines) and what it could do next",
        "tone": "curious, credible, forward-looking",
        "pexels_queries": ["vaccine vial lab", "molecular render blue", "biotech research"],
        "mood": "green and teal molecular structure render, clean dark background",
    },
    {
        "id": "synthetic_biology",
        "category": "news",
        "angle": "what synthetic biology means — programming cells like software — with a real example",
        "tone": "curious, grounded, inspiring",
        "pexels_queries": ["bioreactor lab", "synthetic biology abstract", "green biotech lab"],
        "mood": "green plants in a tissue-culture lab, biotechnology, bright and clean",
    },
    {
        "id": "ai_in_biology",
        "category": "news",
        "angle": "how AI (e.g. protein structure prediction) is changing biology, explained honestly",
        "tone": "credible, measured, exciting",
        "pexels_queries": ["protein folding render", "ai data visualization", "molecular model abstract"],
        "mood": "abstract network of connected nodes, bioinformatics, deep blue",
    },

    # ---- scholarships / opportunities -------------------------------------
    {
        "id": "scholarship_howto",
        "category": "scholarship",
        "angle": "one practical tip that makes a scholarship / fellowship application stand out",
        "tone": "encouraging, actionable, generous",
        "pexels_queries": ["graduation success", "student writing application", "university campus"],
        "mood": "green plants in a tissue-culture lab, biotechnology, bright and clean",
    },
    {
        "id": "funding_mindset",
        "category": "scholarship",
        "angle": "where life-science students overlook funding/opportunities and how to find them",
        "tone": "resourceful, motivating, practical",
        "pexels_queries": ["student laptop library", "research opportunity desk", "university study"],
        "mood": "microscope and glassware in a modern laboratory, shallow depth of field",
    },

    # ---- entrepreneurship / business ideas --------------------------------
    {
        "id": "biotech_startup",
        "category": "business",
        "angle": "a realistic biotech/bioinformatics business idea a small team could actually start",
        "tone": "practical, entrepreneurial, grounded",
        "pexels_queries": ["startup team lab", "biotech business meeting", "modern office science"],
        "mood": "green plants in a tissue-culture lab, biotechnology, bright and clean",
    },
    {
        "id": "science_to_value",
        "category": "business",
        "angle": "how a lab discovery becomes a product/service, and where the value is created",
        "tone": "clear, strategic, inspiring",
        "pexels_queries": ["biotech production lab", "pharmaceutical manufacturing", "clean industrial lab"],
        "mood": "petri dishes and pipettes on a clean bench, soft light",
    },

    # ---- wonder / inspiration ---------------------------------------------
    {
        "id": "cell_wonder",
        "category": "inspiration",
        "angle": "the sheer astonishment of what a single cell does every second — awe with accuracy",
        "tone": "wonder-filled, vivid, uplifting",
        "pexels_queries": ["cell biology render", "microscope cells", "molecular world abstract"],
        "mood": "blue DNA double helix abstract, glowing, scientific",
    },
    {
        "id": "why_biotech_matters",
        "category": "inspiration",
        "angle": "why this field matters — biotech quietly solving real human problems",
        "tone": "inspiring, hopeful, grounded",
        "pexels_queries": ["medicine research hope", "green biotechnology", "science for good"],
        "mood": "green plants in a tissue-culture lab, biotechnology, bright and clean",
    },
]


def _history_path(output_root: Path | str) -> Path:
    return Path(output_root) / _HISTORY_FILE


def _load_recent(output_root: Path | str) -> list[str]:
    try:
        data = json.loads(_history_path(output_root).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def _save_recent(output_root: Path | str, ids: list[str]) -> None:
    try:
        p = _history_path(output_root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(ids[-_RECENT:]), encoding="utf-8")
    except Exception:
        pass


def pick_topics(n: int, output_root: Path | str) -> list[dict]:
    """Return ``n`` distinct topics, preferring ones not used recently, spreading
    across different categories where possible, and remembering the picks."""
    if n < 1:
        return []
    recent = set(_load_recent(output_root))

    fresh = [t for t in TOPICS if t["id"] not in recent]
    stale = [t for t in TOPICS if t["id"] in recent]
    random.shuffle(fresh)
    random.shuffle(stale)
    pool = fresh + stale

    chosen: list[dict] = []
    used_cats: set[str] = set()
    # First pass: prefer a different category each pick for variety.
    for t in pool:
        if len(chosen) >= n:
            break
        if t["category"] not in used_cats:
            chosen.append(t)
            used_cats.add(t["category"])
    # Second pass: fill any remaining slots regardless of category.
    if len(chosen) < n:
        for t in pool:
            if len(chosen) >= n:
                break
            if t not in chosen:
                chosen.append(t)
    # If n exceeds the taxonomy size, allow repeats.
    while len(chosen) < n:
        chosen.append(random.choice(TOPICS))

    _save_recent(output_root, list(recent) + [t["id"] for t in chosen])
    return chosen
