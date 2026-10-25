"""Visual variety for reels.

The reel's *words* come from the biotech topic system, but its *video* is chosen
from a wider visual palette so the feed isn't all the same look. Categories
rotate so the two daily reels differ from each other and from the day before.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

_HISTORY_FILE = ".reel_visual_history.json"

CATEGORIES: dict[str, list[str]] = {
    "lab": [
        "scientist pipetting laboratory", "microscope close up lab", "petri dish bacteria colony",
        "test tubes rack colorful", "centrifuge spinning lab", "researcher gloves pipette",
        "laboratory glassware light", "cell culture flask lab", "lab bench equipment clean",
        "dna gel electrophoresis",
    ],
    "molecular": [
        "dna double helix rotating", "protein structure 3d render", "molecular model animation",
        "dna strand glowing blue", "cell membrane illustration", "virus structure render",
        "chromosome abstract blue", "molecules floating 3d", "genetic code animation",
    ],
    "data": [
        "code scrolling screen", "data visualization network", "programmer typing laptop",
        "genome data dashboard", "network nodes connecting", "ai neural network abstract",
        "charts graphs analytics screen", "server data center blue", "binary code flowing",
    ],
    "nature": [
        "plant cells green macro", "forest biodiversity aerial", "green leaves macro dew",
        "coral reef underwater life", "algae water green", "seeds sprouting timelapse",
        "microscopic organisms water", "greenhouse plants rows", "bacteria culture growth",
    ],
}


def _history_path(output_root: Path | str) -> Path:
    return Path(output_root) / _HISTORY_FILE


def _load_last(output_root: Path | str) -> list[str]:
    try:
        data = json.loads(_history_path(output_root).read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(x) for x in data]
    except Exception:
        pass
    return []


def _save_last(output_root: Path | str, cats: list[str]) -> None:
    try:
        p = _history_path(output_root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cats), encoding="utf-8")
    except Exception:
        pass


def pick_visuals(n: int, output_root: Path | str) -> list[dict]:
    """Return ``n`` visual specs (distinct categories where possible), avoiding
    the categories used on the previous run, each with shuffled search queries."""
    last = set(_load_last(output_root))
    names = list(CATEGORIES.keys())
    fresh = [c for c in names if c not in last]
    random.shuffle(fresh)
    random.shuffle(names)
    ordered = fresh + [c for c in names if c not in fresh]

    chosen_cats: list[str] = []
    i = 0
    while len(chosen_cats) < n:
        chosen_cats.append(ordered[i % len(ordered)])
        i += 1
        if i >= len(ordered) and len(chosen_cats) < n:
            random.shuffle(ordered)

    specs = []
    for idx, cat in enumerate(chosen_cats):
        queries = CATEGORIES[cat][:]
        random.shuffle(queries)
        specs.append({"id": f"{cat}_{idx}", "category": cat, "pexels_queries": queries})

    _save_last(output_root, chosen_cats)
    return specs
