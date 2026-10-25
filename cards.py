"""Render a structured card dict -> branded PNG via the Jinja template + Chrome.

A card dict fills the sections it needs (see templates/card.html.j2):
  series, kicker, title, title_size, lede, stats[], bars[], blocks[], meta[],
  callout, callout_tone, linkchip, footer_sub, cta
Unused sections are simply omitted from the layout.
"""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import render_card

_TEMPLATES = Path(__file__).parent / "templates"
_LOGO = Path(__file__).parent / "assets" / "logo_mark.png"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html", "j2"]),
)


def render_html(data: dict, template: str = "card.html.j2") -> str:
    ctx = dict(data)
    if _LOGO.exists() and "logo_uri" not in ctx:
        ctx["logo_uri"] = _LOGO.resolve().as_uri()
    return _env.get_template(template).render(**ctx)


def make_card(data: dict, out_png, template: str = "card.html.j2",
              w: int = 1080, h: int = 1350, scale: int = 2) -> str:
    """Render the card to PNG; returns the PNG path.

    template: "card.html.j2" (graphic card) or "card_photo.html.j2" (photo card).
    """
    out_png = Path(out_png)
    html_path = out_png.with_suffix(".html")
    html_path.write_text(render_html(data, template), encoding="utf-8")
    return render_card.render(html_path, out_png, w, h, scale)
