"""MABCOS batch builder (v2) — assembles a free-tier batch of branded cards,
renders them, and writes the same captions.json contract the existing Telegram
review + Facebook posting already understand (cards[], products[], alerts[]).

    python pipeline.py            # one batch into output/<date>[-slot]/

Nothing posts automatically — notify.py sends it to Telegram for approval.
"""
from __future__ import annotations

import argparse
import html
import json
import random
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
except Exception:
    pass

import config
import content
import cards
import fetch_photo


def _day_dir(offset: int = 0) -> Path:
    d = config.current_batch_dir(offset)
    (d / "cards").mkdir(parents=True, exist_ok=True)
    (d / "backgrounds").mkdir(parents=True, exist_ok=True)
    return d


def _render_card(result: dict, day_dir: Path, idx: int) -> dict:
    data = result["data"]
    template = result.get("template", "card.html.j2")
    if template == "card_photo.html.j2":
        queries = data.pop("_photo_queries", ["modern laboratory science"])
        orient = "landscape" if data.get("layout") == "hero" else "portrait"
        ph = fetch_photo.fetch(queries, day_dir / "backgrounds" / f"photo_{idx}.jpg",
                               orientation=orient)
        if ph:
            data["image"] = Path(ph["path"]).resolve().as_uri()
            data["credit"] = ph["credit"]
        else:
            # No photo available -> skip to a safe graphic card instead of a blank.
            print("  no photo; substituting a local graphic card")
            import fallbacks
            alt = fallbacks.pick("education")
            return _render_card(alt, day_dir, idx)
    card_file = f"card_{idx}.png"
    cards.make_card(data, day_dir / "cards" / card_file, template=template)
    return {"file": card_file, "title": data.get("title"),
            "caption": result["caption"], "kind": result.get("kind")}


_PRODUCT_INTROS = [
    "A solid pick for anyone serious about the life sciences 👇",
    "Worth a spot on your shelf if this is your field 👇",
    "The kind of resource that pays for itself in saved hours 👇",
]


def _product_posts() -> list[dict]:
    if config.PRODUCT_POSTS_PER_RUN < 1:
        return []
    import os
    from datetime import date
    import fetch_products
    allp = fetch_products.load_products()
    if not allp:
        return []
    # Stateless rotation: cycle through the whole pool over time, 2 picks/day, no
    # repeat until the pool is exhausted. Works in the cloud with no state file.
    slot = os.getenv("MABCOS_SLOT", "")
    try:
        half = 1 if int(slot[:2]) >= 12 else 0
    except Exception:
        half = 0
    start = (date.today().toordinal() * 2 + half) % len(allp)
    products = []
    for k in range(config.PRODUCT_POSTS_PER_RUN):
        p = dict(allp[(start + k) % len(allp)])
        p["affiliate_url"] = fetch_products.build_affiliate_url(p["url"])
        products.append(p)
    posts = []
    for p in products:
        name, url = p["name"], p["affiliate_url"]
        text = f"📚 {name} — {random.choice(_PRODUCT_INTROS)}"
        posts.append({
            "name": name, "asin": p.get("asin"), "url": url,
            "caption": text,
            "tg_text": f"{text}\n\n{config.CTA_TAG}\n\n{url}",
            "fb_message": f"{text}\n\n{config.CTA_TAG}\n\n{config.AFFILIATE_DISCLOSURE}",
        })
    return posts


def _build_reels(day_dir: Path, recent=None):
    """Build branded reels: several relevant clips + HTML overlay + music.
    Returns (reels, alerts). Hooks avoid recently-used ones (anti-repetition)."""
    import os
    n = config.VIDEO_REELS_PER_RUN
    if n < 1:
        return [], []
    import fetch_video
    import fetch_music
    import compose_video
    (day_dir / "reels").mkdir(parents=True, exist_ok=True)
    hooks = content.pick_reel_hooks(min(n, len(content.REEL_HOOKS)), recent)
    reels, alerts = [], []
    CLIPS_PER_REEL = 3
    for i, hook in enumerate(hooks, 1):
        print(f"· reel {i}/{len(hooks)} — '{hook['pill']}' — fetching clips…")
        # Several short, RELEVANT clips (matched to the hook) cut together.
        clip_paths = []
        for j in range(CLIPS_PER_REEL):
            c = fetch_video.fetch_clip({"pexels_queries": hook.get("queries", [])},
                                       day_dir / "reels" / f"clip_{i}_{j}.mp4")
            if c:
                clip_paths.append(c["path"])
        if not clip_paths:
            print("  no clips available; skipping this reel")
            continue
        music = fetch_music.pick_track()
        reel_file = f"reel_{i}.mp4"
        try:
            compose_video.make_reel(clip_paths, hook["hook"],
                                    day_dir / "reels" / reel_file, music_path=music,
                                    sub=hook.get("sub"), pill=hook.get("pill", "Reel"))
        except Exception as exc:
            print(f"  reel compose failed ({exc}); skipping")
            continue
        cap = hook["caption"]
        if music:
            try:
                cap += "\n\n" + fetch_music.credit_line(os.path.basename(music))
            except Exception:
                pass
        reels.append({"file": reel_file, "caption": cap, "line": hook["hook"]})
        print(f"    + reel: {hook['pill']} ({len(clip_paths)} clips)")
    if config.VIDEO_REELS_PER_RUN >= 1 and not reels:
        if not config.ffmpeg_available():
            alerts.append("⚠️ Reels did NOT render — ffmpeg is missing. Run ./install_ffmpeg.sh.")
        else:
            alerts.append("⚠️ Reels did not render this batch (clip/encode issue). Check cron.log.")
    return reels, alerts


def build_review_html(day_dir: Path, cards_out: list[dict], products: list[dict]):
    from datetime import date
    rows = []
    for c in cards_out:
        cap = html.escape(c.get("caption", "")).replace("\n", "<br>")
        rows.append(f"""<div class="card"><img src="cards/{c['file']}">
          <div class="meta"><p class="k">{html.escape(c.get('kind',''))}</p>
          <p class="t">{html.escape(c.get('title') or '')}</p><p class="c">{cap}</p></div></div>""")
    prod = "".join(f"<li><b>{html.escape(p['name'])}</b> — {html.escape(p['url'])}</li>" for p in products)
    doc = f"""<!doctype html><meta charset="utf-8"><title>MABCOS review {date.today().isoformat()}</title>
<style>body{{font-family:system-ui;background:#0b1330;color:#eaf0ff;max-width:1000px;margin:auto;padding:28px}}
.card{{display:flex;gap:18px;background:#121c44;border:1px solid #27305e;border-radius:14px;padding:14px;margin:14px 0}}
.card img{{width:230px;border-radius:10px}} .k{{color:#ffc62b;font-size:12px;text-transform:uppercase;letter-spacing:1px;margin:0}}
.t{{font-size:18px;font-weight:600;margin:4px 0}} .c{{font-size:14px;color:#aab6da;line-height:1.5}}
h2{{border-bottom:1px solid #27305e;padding-bottom:6px;margin-top:30px}}</style>
<h1>MABCOS — review {date.today().isoformat()}</h1>
<h2>Cards ({len(cards_out)})</h2>{''.join(rows)}
<h2>Products ({len(products)})</h2><ul>{prod}</ul>"""
    (day_dir / "review.html").write_text(doc, encoding="utf-8")


def generate_batch(offset: int = 0) -> Path:
    day_dir = _day_dir(offset)
    print(f"Generating into {day_dir}")
    recent = content.load_recent()
    results = content.build_batch(seed=day_dir.name, recent=recent)
    cards_out = []
    for i, r in enumerate(results, 1):
        print(f"· rendering {r.get('kind')} ({r.get('template')})…")
        cards_out.append(_render_card(r, day_dir, i))

    reels, alerts = _build_reels(day_dir, recent)

    # Remember what we just made so it isn't repeated for a long while.
    content.save_recent([c.get("title") for c in cards_out] + [r.get("line") for r in reels])

    products = _product_posts()

    (day_dir / "captions.json").write_text(json.dumps(
        {"cards": cards_out, "video_reels": reels, "products": products, "alerts": alerts},
        indent=2), encoding="utf-8")
    build_review_html(day_dir, cards_out, products)
    print(f"Done: {day_dir / 'review.html'}")
    return day_dir


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1)
    a = ap.parse_args(argv)
    for off in range(max(1, a.count)):
        generate_batch(off)


if __name__ == "__main__":
    main(sys.argv[1:])
