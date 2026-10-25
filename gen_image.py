"""Background generation for The Love Lens.

Preferred path: fetch an attractive, topic-matched stock photo from Pexels
(fetch_image.py). If that is unavailable (no PEXELS_API_KEY, no network, nothing
found) we fall back to a locally-drawn Pillow gradient so the pipeline always
produces a card. The gradient path takes no network and keeps the offline tests
green.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

import config


def _palette_for_mood(mood: str):
    palettes = [
        ("plum", "#42245f", "#150a1f"),
        ("navy", "#152f63", "#0a1730"),
        ("maroon", "#5a1325", "#1a0710"),
        ("pumpkin", "#85410c", "#241004"),
        ("forest", "#14492a", "#0a1f12"),
        ("mustard", "#6f530e", "#201705"),
        ("rust", "#6b260c", "#200b03"),
        ("teal", "#125046", "#0a2019"),
        ("indigo", "#22266d", "#0d0f2a"),
        ("burgundy", "#540d2b", "#1a0512"),
    ]
    if not mood:
        return palettes[0]
    key = sum(ord(ch) for ch in mood.lower()) % len(palettes)
    return palettes[key]


def _to_rgb(color: str):
    return tuple(int(color[i : i + 2], 16) for i in (1, 3, 5))


def _add_grain(img: Image.Image) -> Image.Image:
    width, height = img.size
    noise = Image.effect_noise((width, height), 12)
    noise = noise.filter(ImageFilter.GaussianBlur(radius=0.4))
    return Image.blend(img, noise.convert("RGB"), 0.02)


def make_gradient_background(mood: str, out_path, w=None, h=None) -> str:
    """Generate a soft branded gradient locally and save it as a PNG."""
    w = w or config.CARD_W
    h = h or config.CARD_H
    out_path = Path(out_path)

    _, start_hex, end_hex = _palette_for_mood(mood)
    start = _to_rgb(start_hex)
    end = _to_rgb(end_hex)

    img = Image.new("RGB", (w, h), start)
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / max(1, h - 1)
        r = tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3))
        draw.line((0, y, w, y), fill=r)

    img = _add_grain(img)
    img = img.resize((w, h), Image.Resampling.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return str(out_path)


def make_background(mood, out_path, w=None, h=None) -> str:
    """Return a background image path for a card.

    ``mood`` may be a topic dict (preferred — enables photo search) or a plain
    mood string (used for the gradient palette). Tries Pexels first when the
    source is enabled and a key is present, then falls back to the gradient.
    """
    if config.IMAGE_SOURCE == "pexels":
        try:
            import fetch_image

            result = fetch_image.fetch_background(mood, out_path, w, h)
            if result:
                return result
        except Exception as exc:  # pragma: no cover - defensive
            print(f"  photo fetch errored ({exc}); using local gradient")

    mood_str = mood.get("mood", "") if isinstance(mood, dict) else (mood or "")
    return make_gradient_background(mood_str, out_path, w, h)
