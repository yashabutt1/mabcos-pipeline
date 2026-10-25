"""
Composite an original line onto a background photo -> finished, decorated card.

The card now layers, bottom to top:
  1. background photo (Pexels) or gradient
  2. a readability scrim so white text always pops
  3. soft decorative floral accents in the corners (optional)
  4. an elegant script title + the serif body text
  5. the handle
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
def _load_font(path, size):
    try:
        return ImageFont.truetype(str(path), size)
    except Exception:
        print(f"Warning: font not found at {path}; falling back to a bold system serif font")
        return ImageFont.load_default()


def _load_script_font(size):
    try:
        return ImageFont.truetype(str(config.FONT_SCRIPT), size)
    except Exception:
        return _load_font(config.FONT_SCRIPT_FALLBACK, size)


# ---------------------------------------------------------------------------
# Text layout helpers
# ---------------------------------------------------------------------------
def _wrap(draw, text, font, max_w):
    words, lines, line = text.split(), [], ""
    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _draw_center(draw, text, font, cx, y, fill=(245, 240, 236), shadow=(0, 0, 0)):
    tw = draw.textlength(text, font=font)
    x = cx - tw / 2
    if shadow is not None:
        draw.text((x + 2, y + 2), text, font=font, fill=shadow)
    draw.text((x, y), text, font=font, fill=fill)


def _fit_title_font(draw, text, w, max_w, start_frac=0.135, min_frac=0.066):
    """Shrink the title font until it fits ``max_w`` on one line.

    Love-lens titles were 1-2 words; MABCOS titles ("The Central Dogma",
    "BLAST Explained") are longer, so a fixed size overflows the card. This
    fits any title to the available width instead of clipping it.
    """
    size = int(w * start_frac)
    min_size = int(w * min_frac)
    font = _load_script_font(size)
    while draw.textlength(text, font=font) > max_w and size > min_size:
        size -= 3
        font = _load_script_font(size)
    return font, size


# ---------------------------------------------------------------------------
# Readability scrim
# ---------------------------------------------------------------------------
def _scrim(base, strength=0.42):
    """Darken the photo with a soft top+bottom-heavy gradient so text pops."""
    w, h = base.size
    grad = Image.new("L", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        # darker at top and bottom, a touch lighter through the middle
        edge = abs(t - 0.5) * 2  # 0 at center, 1 at edges
        a = int(255 * strength * (0.75 + 0.25 * edge))
        grad.putpixel((0, y), a)
    alpha = grad.resize((w, h))
    dark = Image.new("RGB", (w, h), (12, 9, 15))
    base = base.copy()
    base.paste(dark, (0, 0), alpha)
    return base


# ---------------------------------------------------------------------------
# Decorative florals (drawn, no external assets)
# ---------------------------------------------------------------------------
_FLOWER_COLORS = [
    (246, 166, 193), (245, 146, 126), (201, 168, 224),
    (247, 197, 159), (231, 122, 144), (185, 139, 214),
    (250, 182, 200), (238, 160, 168),
]
_LEAF_COLORS = [(150, 178, 140), (120, 160, 130), (168, 190, 150)]


def _one_flower(r, color, petals=6, alpha=170):
    """Return an RGBA tile with a single soft flower centered in it."""
    tile = int(r * 2.2)
    layer = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
    c = tile / 2
    petal_len = r
    petal_w = r * 0.62
    for i in range(petals):
        petal = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
        pd = ImageDraw.Draw(petal)
        pd.ellipse(
            [c - petal_w / 2, c - petal_len, c + petal_w / 2, c + petal_len * 0.08],
            fill=color + (alpha,),
        )
        angle = i * (360 / petals) + random.uniform(-6, 6)
        petal = petal.rotate(angle, resample=Image.BICUBIC, center=(c, c))
        layer = Image.alpha_composite(layer, petal)
    # center
    cd = ImageDraw.Draw(layer)
    cr = r * 0.28
    cd.ellipse([c - cr, c - cr, c + cr, c + cr], fill=(250, 214, 120, min(255, alpha + 40)))
    return layer


def _cluster(canvas, cx, cy, scale):
    """Paint a small cluster of flowers + leaves centered near (cx, cy)."""
    n_flowers = random.randint(2, 3)
    palette = random.sample(_FLOWER_COLORS, k=min(len(_FLOWER_COLORS), n_flowers + 1))
    # leaves first (behind)
    for _ in range(random.randint(2, 4)):
        r = random.uniform(38, 70) * scale
        leaf = _one_flower(r, random.choice(_LEAF_COLORS), petals=2, alpha=120)
        angle = random.uniform(0, 360)
        leaf = leaf.rotate(angle, resample=Image.BICUBIC)
        ox = cx + random.uniform(-90, 90) * scale - leaf.width / 2
        oy = cy + random.uniform(-90, 90) * scale - leaf.height / 2
        canvas.alpha_composite(leaf, (int(ox), int(oy)))
    # flowers on top
    for i in range(n_flowers):
        r = random.uniform(55, 95) * scale
        flower = _one_flower(r, palette[i % len(palette)],
                             petals=random.choice([5, 6, 6]),
                             alpha=random.randint(150, 195))
        ox = cx + random.uniform(-70, 70) * scale - flower.width / 2
        oy = cy + random.uniform(-70, 70) * scale - flower.height / 2
        canvas.alpha_composite(flower, (int(ox), int(oy)))


def _draw_florals(base):
    """Overlay soft floral accents in the bottom corners (and a top accent)."""
    w, h = base.size
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    scale = w / 1080.0
    # bottom corners — the heaviest decoration, like the example
    _cluster(canvas, int(w * 0.10), int(h * 0.95), scale)
    _cluster(canvas, int(w * 0.90), int(h * 0.96), scale)
    if random.random() < 0.6:
        _cluster(canvas, int(w * 0.93), int(h * 0.07), scale * 0.7)
    canvas = canvas.filter(ImageFilter.GaussianBlur(radius=1.2))
    base = base.convert("RGB")
    base.paste(canvas, (0, 0), canvas)
    return base


# ---------------------------------------------------------------------------
# Background loading
# ---------------------------------------------------------------------------
def _open_bg(background_path, w, h):
    if background_path:
        return Image.open(background_path).convert("RGB").resize((w, h))
    return Image.new("RGB", (w, h), (18, 14, 22))


def _draw_handle(draw, w, h, handle):
    if not handle:
        return
    sf = _load_font(config.FONT_SMALL, int(h * 0.020))
    _draw_center(draw, handle, sf, w / 2, int(h * 0.955),
                 fill=(235, 229, 225), shadow=(0, 0, 0))


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
def make_card(background_path, line, out_path, handle=None, title=None):
    handle = config.HANDLE if handle is None else handle
    w, h = config.CARD_W, config.CARD_H

    img = _open_bg(background_path, w, h)
    img = _scrim(img, 0.54)
    if config.DECORATE_FLORALS:
        img = _draw_florals(img)
    draw = ImageDraw.Draw(img)
    cx = w / 2

    top = int(h * 0.13)

    # bold-serif title, auto-fitted to the card width
    if title:
        tf, tsize = _fit_title_font(draw, title, w, int(w * 0.86))
        _draw_center(draw, title, tf, cx, top, fill=(250, 246, 242))
        top += int(tsize * 1.05)
        top += int(h * 0.04)

    # body line (serif), auto-sized to fit the space *below* the title
    body_bottom = int(h * 0.87)
    avail = body_bottom - top
    max_w = int(w * 0.82)
    min_size = int(w * 0.050)
    size = int(w * 0.090)
    font = _load_font(config.FONT_DISPLAY, size)
    while True:
        lines = _wrap(draw, line, font, max_w)
        line_h = int(size * 1.18)
        total_h = line_h * len(lines)
        if total_h <= avail or size <= min_size:
            break
        size -= 4
        font = _load_font(config.FONT_DISPLAY, size)

    y = top + max(0, (avail - total_h) // 2)
    for ln in lines:
        _draw_center(draw, ln, font, cx, y)
        y += line_h

    _draw_handle(draw, w, h, handle)
    img.save(out_path)
    return str(out_path)


def make_paragraph_card(background_path, body, out_path, handle=None, title=None):
    handle = config.HANDLE if handle is None else handle
    w, h = config.CARD_W, config.CARD_H

    img = _open_bg(background_path, w, h)
    img = _scrim(img, 0.6)
    if config.DECORATE_FLORALS:
        img = _draw_florals(img)
    draw = ImageDraw.Draw(img)
    cx = w / 2

    top = int(h * 0.10)
    if title:
        tf, tsize = _fit_title_font(draw, title, w, int(w * 0.86), start_frac=0.13)
        _draw_center(draw, title, tf, cx, top, fill=(250, 246, 242))
        top += int(tsize * 1.15)
        top += int(h * 0.03)

    max_w = int(w * 0.84)
    max_h = int(h * 0.78) - top
    start_size = int(w * 0.056)
    min_size = int(w * 0.040)
    line_spacing = 1.32

    raw_lines = [ln.strip() for ln in body.splitlines() if ln.strip()] or [body]

    size = start_size
    wrapped_lines = []
    while size >= min_size:
        font = _load_font(config.FONT_DISPLAY, size)
        wrapped_lines = []
        for ln in raw_lines:
            wrapped_lines.extend(_wrap(draw, ln, font, max_w))
        line_h = int(size * line_spacing)
        if line_h * len(wrapped_lines) <= max_h:
            break
        size -= 2
    else:
        font = _load_font(config.FONT_DISPLAY, min_size)
        wrapped_lines = []
        for ln in raw_lines:
            wrapped_lines.extend(_wrap(draw, ln, font, max_w))

    n = len(wrapped_lines) or 1
    line_h = int(size * line_spacing)
    total_h = line_h * n
    y = top + max(0, int((max_h - total_h) / 2))
    for ln in wrapped_lines:
        _draw_center(draw, ln, font, cx, y)
        y += line_h

    _draw_handle(draw, w, h, handle)
    print(f"PARAGRAPH font size = {size}, lines = {n}")
    img.save(out_path)
    return str(out_path)
