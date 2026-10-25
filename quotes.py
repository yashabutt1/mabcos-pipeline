"""Curated bank of REAL, correctly-attributed science quotes for the long-form
reflection posts (a warm essay woven around a famous line). Hand-curated so the
AI never invents or misattributes a quote; it only writes the reflection *around*
the given one. Edit freely — add favorites or remove any you're unsure about.

A shuffle-bag picker serves each quote once before any repeats.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import config

_HISTORY_FILE = ".quote_history.json"

QUOTES: list[dict] = [
    {"text": "Nothing in life is to be feared, it is only to be understood. Now is the time to understand more, so that we may fear less.", "author": "Marie Curie"},
    {"text": "I am among those who think that science has great beauty.", "author": "Marie Curie"},
    {"text": "Research is to see what everybody else has seen, and to think what nobody else has thought.", "author": "Albert Szent-Györgyi"},
    {"text": "Science is a way of thinking much more than it is a body of knowledge.", "author": "Carl Sagan"},
    {"text": "Somewhere, something incredible is waiting to be known.", "author": "Carl Sagan"},
    {"text": "The important thing is to never stop questioning.", "author": "Albert Einstein"},
    {"text": "The good thing about science is that it's true whether or not you believe in it.", "author": "Neil deGrasse Tyson"},
    {"text": "In the fields of observation chance favors only the prepared mind.", "author": "Louis Pasteur"},
    {"text": "Science knows no country, because knowledge belongs to humanity, and is the torch which illuminates the world.", "author": "Louis Pasteur"},
    {"text": "If I have seen further it is by standing on the shoulders of giants.", "author": "Isaac Newton"},
    {"text": "In science the credit goes to the man who convinces the world, not to the man to whom the idea first occurs.", "author": "Francis Darwin"},
    {"text": "Nothing in biology makes sense except in the light of evolution.", "author": "Theodosius Dobzhansky"},
    {"text": "What I cannot create, I do not understand.", "author": "Richard Feynman"},
    {"text": "Nature uses only the longest threads to weave her patterns, so that each small piece of her fabric reveals the organization of the entire tapestry.", "author": "Richard Feynman"},
    {"text": "An expert is a person who has made all the mistakes that can be made in a very narrow field.", "author": "Niels Bohr"},
    {"text": "We can only see a short distance ahead, but we can see plenty there that needs to be done.", "author": "Alan Turing"},
    {"text": "The science of today is the technology of tomorrow.", "author": "Edward Teller"},
    {"text": "Equipped with his five senses, man explores the universe around him and calls the adventure Science.", "author": "Edwin Hubble"},
    {"text": "A scientist in his laboratory is not a mere technician: he is also a child confronting natural phenomena that impress him as though they were fairy tales.", "author": "Marie Curie"},
    {"text": "The whole of science is nothing more than a refinement of everyday thinking.", "author": "Albert Einstein"},
    {"text": "To raise new questions, new possibilities, to regard old problems from a new angle, requires creative imagination and marks real advance in science.", "author": "Albert Einstein"},
    {"text": "Science never solves a problem without creating ten more.", "author": "George Bernard Shaw"},
]


def _history_path() -> Path:
    return config.OUTPUT_DIR / _HISTORY_FILE


def _load_bag() -> list[int]:
    try:
        data = json.loads(_history_path().read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [int(x) for x in data]
    except Exception:
        pass
    return []


def _save_bag(bag: list[int]) -> None:
    try:
        _history_path().parent.mkdir(parents=True, exist_ok=True)
        _history_path().write_text(json.dumps(bag), encoding="utf-8")
    except Exception:
        pass


def pick_quotes(n: int) -> list[dict]:
    """Return n quotes, each used once before any repeats (shuffle-bag)."""
    if n < 1 or not QUOTES:
        return []
    bag = [i for i in _load_bag() if 0 <= i < len(QUOTES)]
    chosen = []
    while len(chosen) < n:
        if not bag:
            bag = list(range(len(QUOTES)))
            random.shuffle(bag)
        chosen.append(QUOTES[bag.pop()])
    _save_bag(bag)
    return chosen
