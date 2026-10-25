"""
MABCOS — one run makes a batch of cards + reels into a dated review folder.
You open review.html, run the compliance checklist, then notify.py sends the
batch to Telegram for approval.

    python run.py

Nothing posts automatically. That human gate is what keeps the page credible.
"""
import argparse
import html
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for minimal envs
    def load_dotenv() -> bool:
        return False

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

import config
import dedupe
import topics
import reel_visuals


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate quote-card batches and reel scripts")
    parser.add_argument(
        "--count",
        type=int,
        default=1,
        help="How many review batches to generate (default: 1)",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count must be at least 1")
    return args


def _day_dir(offset_days: int = 0) -> Path:
    d = config.current_batch_dir(offset_days)
    (d / "cards").mkdir(parents=True, exist_ok=True)
    (d / "backgrounds").mkdir(parents=True, exist_ok=True)
    (d / "reels").mkdir(parents=True, exist_ok=True)
    return d


def build_review_html(day_dir, cards, reels):
    rows = []
    for i, c in enumerate(cards, 1):
        tags = " ".join(("#" + t.lstrip("#")) for t in c["hashtags"])
        meta = ""
        if c.get("title"):
            meta += f"<p class=\"ttl\">{html.escape(c['title'])}</p>"
        if c.get("topic"):
            meta += f"<p class=\"topic\">topic: {html.escape(c['topic'])}</p>"
        if c.get("body"):
            meta += f"<p class=\"cap\">{html.escape(c['body'])}</p>"
        else:
            meta += f"<p class=\"cap\">{html.escape(c['caption'])}</p>"
        rows.append(f"""
        <div class="card">
          <img src="cards/{c['file']}" alt="card {i}">
          <div class="meta">
            {meta}
            <p class="tags">{html.escape(tags)}</p>
            <label><input type="checkbox"> approved — original, true, sounds human</label>
          </div>
        </div>""")

    reel_blocks = []
    for i, r in enumerate(reels, 1):
        beats = "".join(f"<li>{html.escape(b)}</li>" for b in r["beats"])
        tags = " ".join(("#" + t.lstrip("#")) for t in r["hashtags"])
        reel_blocks.append(f"""
        <div class="reel">
          <h3>{html.escape(r['format'])} · {html.escape(r.get('runtime',''))}</h3>
          <p class="hook">{html.escape(r['hook'])}</p>
          <ol>{beats}</ol>
          <p class="cap">{html.escape(r['caption'])}</p>
          <p class="tags">{html.escape(tags)}</p>
          <p class="vis"><b>Visual:</b> {html.escape(r['visual'])}</p>
        </div>""")

    doc = f"""<!doctype html><meta charset="utf-8">
<title>MABCOS — review {date.today().isoformat()}</title>
<style>
  body{{font-family:system-ui,sans-serif;background:#17131f;color:#f2ebe6;margin:0;padding:32px;max-width:1000px;margin:auto}}
  h1{{font-weight:600}} h2{{margin-top:40px;border-bottom:1px solid #3a2f47;padding-bottom:8px}}
  .card{{display:flex;gap:20px;background:#251e30;border:1px solid #3a2f47;border-radius:14px;padding:16px;margin:16px 0}}
  .card img{{width:220px;border-radius:10px}}
  .meta{{flex:1}} .cap{{font-size:15px;line-height:1.5}} .tags{{color:#b0a4dc;font-size:13px}}
  .ttl{{font-size:20px;color:#e6b489;margin:0 0 2px;font-style:italic}}
  .topic{{font-size:12px;color:#7d7391;margin:0 0 8px;text-transform:uppercase;letter-spacing:.5px}}
  label{{display:block;margin-top:12px;color:#e6b489;font-size:14px}}
  .reel{{background:#251e30;border:1px solid #3a2f47;border-radius:14px;padding:16px;margin:16px 0}}
  .hook{{font-size:18px;font-weight:600;color:#e8a0a8}} ol{{line-height:1.6}}
  .vis{{color:#9a90a8;font-size:13px}}
  .note{{background:#2d2439;border-left:3px solid #e8a0a8;padding:12px 16px;border-radius:0 8px 8px 0;font-size:14px}}
</style>
<h1>MABCOS — review for {date.today().isoformat()}</h1>
<p class="note">Check each: original wording? true & safe? sounds human? hook lands fast?
Approve the good ones, delete the rest, then load into your scheduler.</p>
<h2>Quote cards ({len(cards)})</h2>
{''.join(rows)}
<h2>Reel scripts ({len(reels)})</h2>
{''.join(reel_blocks)}
"""
    (day_dir / "review.html").write_text(doc, encoding="utf-8")


def _dedup_one(item, used_content, key, generator):
    """Return a non-duplicate version of ``item``; never raises.

    If a fresh variant can't be found (e.g. the free-tier quota is spent and the
    generator keeps returning the same fallback), keep the item as-is — the human
    Telegram approval step is the final guard against anything stale.
    """
    try:
        [item] = dedupe.ensure_unique_items([item], used_content, key, generator, attempts=3)
    except RuntimeError:
        value = dedupe._normalize_text(item.get(key, ""))
        if value:
            used_content.add(value)
    return item


def _with_cta(caption, *ctas):
    """Append calls-to-action (follow/share/save/tag) to a caption."""
    caption = (caption or "").strip()
    tail = "\n".join(c for c in ctas if c)
    return f"{caption}\n\n{tail}" if tail else caption


def generate_batch(offset_days: int = 0):
    import gen_image
    import gen_text
    import compose

    day_dir = _day_dir(offset_days)
    print(f"Generating into {day_dir}")

    used_content = dedupe.load_used_content(config.OUTPUT_DIR)

    # Each card gets its own distinct, recently-unused topic so the feed keeps
    # moving through different subjects instead of repeating one lane.
    chosen = topics.pick_topics(
        config.CARDS_PER_RUN + config.PARAGRAPH_CARDS_PER_RUN + config.VIDEO_REELS_PER_RUN,
        config.OUTPUT_DIR)
    line_topics = chosen[: config.CARDS_PER_RUN]
    para_topics = chosen[config.CARDS_PER_RUN : config.CARDS_PER_RUN + config.PARAGRAPH_CARDS_PER_RUN]
    reel_topics = chosen[config.CARDS_PER_RUN + config.PARAGRAPH_CARDS_PER_RUN :]
    print("· topics this batch: " + ", ".join(t["id"] for t in chosen))

    cards = []

    # One batched Gemini call for all quote lines, one for all paragraphs, so a
    # full day stays well under the free-tier request cap.
    print("· writing quote-card lines…")
    line_items = gen_text.make_lines(line_topics)
    print("· writing paragraph cards…")
    para_items = gen_text.make_paragraphs(para_topics)

    for i, (topic, item) in enumerate(zip(line_topics, line_items), 1):
        # Regenerate just this item if its wording duplicates something posted before.
        item = _dedup_one(item, used_content, "line",
                          lambda t=topic: gen_text.make_lines([t])[0])
        print(f"· quote card {i}/{len(line_topics)} — topic '{topic['id']}' — background…")
        bg = gen_image.make_background(topic, day_dir / "backgrounds" / f"bg_{i}.png")
        card_file = f"card_{i}.png"
        print("  composing text…")
        compose.make_card(bg, item["line"], day_dir / "cards" / card_file,
                          title=item.get("title"))
        cards.append({**item, "file": card_file, "topic": topic["id"],
                      "caption": _with_cta(item.get("caption"), config.CTA_FOLLOW, config.CTA_SHARE)})

    for i, (topic, item) in enumerate(zip(para_topics, para_items), 1):
        item = _dedup_one(item, used_content, "body",
                          lambda t=topic: gen_text.make_paragraphs([t])[0])
        print(f"· paragraph card {i}/{len(para_topics)} — topic '{topic['id']}' — background…")
        bg = gen_image.make_background(topic, day_dir / "backgrounds" / f"para_{i}.png")
        card_file = f"paragraph_{i}.png"
        print("  composing paragraph…")
        compose.make_paragraph_card(bg, item["body"], day_dir / "cards" / card_file,
                                    title=item.get("title"))
        cards.append({**item, "file": card_file, "body": item["body"], "topic": topic["id"],
                      "caption": _with_cta(item.get("caption"), config.CTA_FOLLOW, config.CTA_SAVE)})

    # ---- video reels: stock clip + branded text + music -------------------
    video_reels = build_video_reels(day_dir, reel_topics, used_content)

    # ---- interactive engagement posts (comment bait) ----------------------
    engagement = build_engagement_posts(day_dir, used_content)

    # ---- long-form reflection essays (famous quote + warm essay) ----------
    reflections = build_reflection_posts(day_dir, used_content)

    # ---- Amazon affiliate product recommendations -------------------------
    products = build_product_posts()
    alerts = []

    # Reels are the main growth format — if they didn't render, make it LOUD.
    if config.VIDEO_REELS_PER_RUN >= 1 and not video_reels:
        if not config.ffmpeg_available():
            alerts.append(
                "⚠️ Reels did NOT render — ffmpeg is missing. Run ./install_ffmpeg.sh "
                "in the love-lens-pipeline folder to fix. Reels are your main growth format.")
        else:
            alerts.append("⚠️ Reels did not render this batch (clip/encode issue). Check cron.log.")
    if config.PRODUCT_POSTS_PER_RUN >= 1:
        import fetch_products
        remaining = fetch_products.unposted_count()
        if remaining <= fetch_products.LOW_POOL_THRESHOLD:
            alerts.append(
                f"⚠️ Amazon product pool running low: {remaining} unused product(s) left. "
                f"Ask Claude to refresh the product list so posts don't run out.")

    print("· writing reel scripts…")
    reels = gen_text.make_reels(config.REELS_PER_RUN)

    (day_dir / "captions.json").write_text(
        json.dumps({"cards": cards, "reels": reels, "video_reels": video_reels,
                    "products": products, "engagement": engagement,
                    "reflections": reflections, "alerts": alerts},
                   indent=2),
        encoding="utf-8")
    build_review_html(day_dir, cards, reels)

    return day_dir


_ENGAGE_BG_QUERIES = [
    "dna double helix blue", "microscope laboratory close up",
    "molecular structure render", "petri dish science",
    "scientist pipette lab", "genome data visualization blue",
    "green plant cells macro", "code on screen bioinformatics",
]


def build_engagement_posts(day_dir, used_content):
    if config.ENGAGEMENT_POSTS_PER_RUN < 1:
        return []
    import gen_text
    import gen_image
    import compose
    import random

    print("· writing engagement posts…")
    items = gen_text.make_engagement(config.ENGAGEMENT_POSTS_PER_RUN)
    posts = []
    for i, item in enumerate(items, 1):
        item = _dedup_one(item, used_content, "prompt",
                          lambda: gen_text.make_engagement(1)[0])
        text = (item.get("prompt") or "").strip()
        if not text:
            continue
        query = random.choice(_ENGAGE_BG_QUERIES)
        bg = gen_image.make_background(query, day_dir / "backgrounds" / f"engage_{i}.png")
        card_file = f"engage_{i}.png"
        # longer/fact-style prompts read better as a paragraph card
        if len(text) > 90 or "\n" in text:
            compose.make_paragraph_card(bg, text, day_dir / "cards" / card_file,
                                        title=item.get("title"))
        else:
            compose.make_card(bg, text, day_dir / "cards" / card_file,
                              title=item.get("title"))
        tags = " ".join("#" + t.lstrip("#") for t in item.get("hashtags", []))
        caption = _with_cta((item.get("caption") or text).strip(), config.CTA_FOLLOW)
        if tags:
            caption = f"{caption}\n\n{tags}"
        posts.append({
            "file": card_file,
            "title": item.get("title"),
            "prompt": text,
            "caption": caption,
            "hashtags": item.get("hashtags", []),
            "kind": "engagement",
        })
        print(f"    + engagement: {text[:50]}")
    return posts


_REFLECTION_BG_QUERIES = [
    "dna helix glowing dark", "modern laboratory clean light",
    "molecular model abstract blue", "microscope lens macro",
    "green biotechnology lab", "network nodes science abstract", "cells under microscope",
]


def build_reflection_posts(day_dir, used_content):
    if config.REFLECTION_POSTS_PER_RUN < 1:
        return []
    import gen_text
    import gen_image
    import compose
    import quotes
    import random

    print("· writing reflection essays…")
    picked = quotes.pick_quotes(config.REFLECTION_POSTS_PER_RUN)
    posts = []
    for i, q in enumerate(picked, 1):
        item = gen_text.make_reflection(q)
        essay = (item.get("essay") or "").strip()
        # regenerate once if this essay already appeared before
        if essay and dedupe._normalize_text(essay) in used_content:
            item = gen_text.make_reflection(q)
            essay = (item.get("essay") or "").strip()
        if essay:
            used_content.add(dedupe._normalize_text(essay))

        query = random.choice(_REFLECTION_BG_QUERIES)
        bg = gen_image.make_background(query, day_dir / "backgrounds" / f"reflect_{i}.png")
        card_file = f"reflect_{i}.png"
        # the image card shows the quote + attribution
        card_body = f"“{q['text']}”\n\n— {q['author']}"
        compose.make_paragraph_card(bg, card_body, day_dir / "cards" / card_file,
                                    title=item.get("title") or "A Thought")

        tags = " ".join("#" + t.lstrip("#") for t in item.get("hashtags", []))
        caption = _with_cta(essay, config.CTA_SHARE, config.CTA_FOLLOW)
        if tags:
            caption = f"{caption}\n\n{tags}"
        posts.append({
            "file": card_file,
            "title": item.get("title"),
            "quote": q["text"],
            "author": q["author"],
            "essay": essay,
            "caption": caption,
            "kind": "reflection",
        })
        print(f"    + reflection on {q['author']}")
    return posts


def build_product_posts():
    if config.PRODUCT_POSTS_PER_RUN < 1:
        return []
    import gen_text
    import fetch_products

    products = fetch_products.pick_products(config.PRODUCT_POSTS_PER_RUN)
    if not products:
        print("· no products in products.txt yet; skipping product posts")
        return []
    print(f"· writing {len(products)} product caption(s)…")
    captions = gen_text.make_product_captions(products)

    posts = []
    for p, cap in zip(products, captions):
        text = (cap.get("caption") or "").strip() or gen_text._fallback_product_caption(p["name"])
        url = p["affiliate_url"]
        posts.append({
            "name": p["name"],
            "asin": p.get("asin"),
            "url": url,
            "caption": text,
            # what Telegram shows (link inline so it previews + is tappable)
            "tg_text": f"{text}\n\n{config.CTA_TAG}\n\n{url}",
            # what gets posted to Facebook (link passed separately as the card)
            "fb_message": f"{text}\n\n{config.CTA_TAG}",
        })
        print(f"    + {p['name'][:45]} -> {url}")
    return posts


def _reel_caption(item, topic, music_credit=None):
    """Hook line + soft engagement question + follow CTA + music credit + hashtags."""
    tags = " ".join("#" + t.lstrip("#") for t in item.get("hashtags", []))
    parts = [item.get("line", "").strip()]
    if item.get("caption"):
        parts.append(item["caption"].strip())
    parts.append(f"{config.CTA_FOLLOW}\n{config.CTA_SAVE}\n{config.CTA_SHARE}")
    if music_credit:
        parts.append(music_credit)
    if tags:
        parts.append(tags)
    return "\n\n".join(p for p in parts if p)


def build_video_reels(day_dir, reel_topics, used_content):
    if config.VIDEO_REELS_PER_RUN < 1 or not reel_topics:
        return []
    import gen_text
    import fetch_video
    import fetch_music
    import compose_video

    print("· writing reel lines…")
    reel_items = gen_text.make_lines(reel_topics)
    visuals = reel_visuals.pick_visuals(len(reel_topics), config.OUTPUT_DIR)

    video_reels = []
    for i, (topic, item, visual) in enumerate(zip(reel_topics, reel_items, visuals), 1):
        item = _dedup_one(item, used_content, "line",
                          lambda t=topic: gen_text.make_lines([t])[0])
        print(f"· reel {i}/{len(reel_topics)} — words '{topic['id']}' / visual '{visual['category']}' — clip…")
        clip = fetch_video.fetch_clip(visual, day_dir / "reels" / f"clip_{i}.mp4")
        if not clip:
            print("  no clip available (needs PEXELS_API_KEY / network); skipping reel")
            continue
        music = fetch_music.pick_track()
        music_name = os.path.basename(music) if music else None
        music_credit = fetch_music.credit_line(music_name) if music_name else None
        reel_file = f"reel_{i}.mp4"
        print(f"  composing reel (music: {music_name or 'none'})…")
        try:
            compose_video.make_reel(clip["path"], item.get("title"), item["line"],
                                    day_dir / "reels" / reel_file, music_path=music)
        except Exception as exc:
            print(f"  reel compose failed ({exc}); skipping")
            continue
        video_reels.append({
            **item,
            "file": reel_file,
            "topic": topic["id"],
            "visual": visual["category"],
            "caption": _reel_caption(item, topic, music_credit),
            "music": music_name,
            "music_credit": music_credit,
        })
    return video_reels


def main(argv=None):
    args = parse_args(argv)
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )

    generated_dirs = []
    for offset in range(args.count):
        generated_dirs.append(generate_batch(offset))

    print("\nCompleted batches:")
    for path in generated_dirs:
        print(f"- {path / 'review.html'}")


if __name__ == "__main__":
    main(sys.argv[1:])
