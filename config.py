"""
Central configuration for the MABCOS content pipeline.

MABCOS = the "innovationthroughbiotech" Facebook page: biotechnology,
biochemistry, and bioinformatics — education, careers, tutorials, news,
scholarships, business ideas, and events.

Edit this file to change branding, models, sizes, or how many posts per run.
"""
from pathlib import Path

# ---------------------------------------------------------------------------
# Brand identity
# ---------------------------------------------------------------------------
PAGE_NAME = "MABCOS"
HANDLE = "@innovationthroughbiotech"   # shown small on cards; set to "" to hide

# Who actually follows the page: shapes the voice of every post.
AUDIENCE = (
    "Your audience is students, early-career scientists, researchers, educators, "
    "and curious professionals in BIOTECHNOLOGY, BIOCHEMISTRY, and BIOINFORMATICS, "
    "worldwide (strong in South Asia, Africa, the Middle East, and globally). Many "
    "are undergraduates, master's/PhD students, lab technicians, and job-seekers who "
    "want to LEARN real concepts, build skills, find scholarships and opportunities, "
    "and stay current with the field. Write for a smart, ambitious reader who is NOT "
    "an expert yet but is serious and capable. Be accurate, concrete, and genuinely "
    "useful — explain the 'why', give one thing they can actually use, and respect "
    "their intelligence. Credible and inspiring, never dumbed-down, never clickbait, "
    "never hype. The kind of post a student proudly shares to their study group and a "
    "professional reposts because it's actually correct.")

# ---------------------------------------------------------------------------
# Calls-to-action appended to captions to boost reach (follow/share/save/tag).
# These signals (shares, saves, comments) are what the algorithm rewards.
# ---------------------------------------------------------------------------
# Clean, non-patronizing CTAs — no "save it for your exam/interview" or prescriptive
# usage instructions; readers know how to use a post.
CTA_FOLLOW = f"Follow {HANDLE} for more."
CTA_SHARE = "Share it with someone who'd find it useful."
CTA_SAVE = ""   # removed — the "save this for your interview" line read as silly
CTA_TAG = "Tag someone who'd want to see this."

# ---------------------------------------------------------------------------
# Models  (verify current names at ai.google.dev/gemini-api/docs/models)
# ---------------------------------------------------------------------------
# GEMINI_API_KEY powers the text side. Backgrounds come from Pexels stock photos
# (free API key -> PEXELS_API_KEY in .env). Get one at pexels.com/api.
TEXT_MODEL = "gemini-2.5-flash"          # fast + cheap for copy
IMAGE_MODEL = "gemini-2.5-flash-image"   # retained for compatibility; not used

# Where card backgrounds come from:
#   "pexels"   -> real stock photos matched to each card's topic (recommended)
#   "gradient" -> a locally-drawn Pillow gradient (offline, no key)
IMAGE_SOURCE = "pexels"

# Floral accents are a love-page thing — OFF for a science brand (clean look).
DECORATE_FLORALS = False

# ---------------------------------------------------------------------------
# How much to make each run
# ---------------------------------------------------------------------------
# Counts are PER BATCH. The pipeline runs twice a day (morning + evening slots),
# so daily totals are roughly double these.
# REELS-FIRST: reels are the only format Facebook pushes to NON-followers, so
# they're weighted heaviest — that's the growth engine. Feed cards mostly reach
# existing followers.
# Three generate runs a day (morning/lunch/evening peak windows), so posts spread
# across peak activity instead of dumping. Per run: 1 reel + 1 card (reel-led), plus
# one affiliate product a day → ~7 candidates/day, so you comfortably approve 6+.
CARDS_PER_RUN = 1              # one feed card per run (-> ~3/day), leans to timely/engaging pillars
PARAGRAPH_CARDS_PER_RUN = 1    # explainer micro-essay cards (-> ~2/day, shareable)
REELS_PER_RUN = 0              # reel SCRIPTS are not posted — off to save quota
VIDEO_REELS_PER_RUN = 1        # finished video reels (-> ~3/day, the growth engine)
PRODUCT_POSTS_PER_RUN = 1      # Amazon affiliate product recommendations (gated to 1/day)
ENGAGEMENT_POSTS_PER_RUN = 1   # interactive "comment below" posts (-> ~2/day)
REFLECTION_POSTS_PER_RUN = 1   # long-form essay around a famous science quote (-> ~2/day)

# ---------------------------------------------------------------------------
# Amazon Associates (manual-link mode — no PA-API)
# ---------------------------------------------------------------------------
import os as _os
AMAZON_ASSOC_TAG = _os.getenv("AMAZON_ASSOC_TAG", "").strip()
AMAZON_MARKETPLACE = _os.getenv("AMAZON_MARKETPLACE", "www.amazon.com").strip()
# You curate products here (name | url per line). See products.example.txt.
PRODUCTS_FILE = Path(__file__).parent / "products.txt"
# Optional: a published-to-web Google Sheet (CSV) so links can be added from any
# device. Columns: Name | Amazon URL. Merged with products.txt.
GOOGLE_SHEET_CSV_URL = _os.getenv("GOOGLE_SHEET_CSV_URL", "").strip()
AFFILIATE_DISCLOSURE = (
    "As an Amazon Associate, MABCOS earns from qualifying purchases.")

# ---------------------------------------------------------------------------
# Video reels
# ---------------------------------------------------------------------------
REEL_W = 1080
REEL_H = 1920          # 9:16 vertical for Reels
REEL_TARGET_SECONDS = 14   # final reel length (clip is looped/trimmed to fit)

# Static ffmpeg/ffprobe binaries live in ./bin. Falls back to PATH if absent.
_BIN = Path(__file__).parent / "bin"
FFMPEG = str(_BIN / "ffmpeg") if (_BIN / "ffmpeg").exists() else "ffmpeg"
FFPROBE = str(_BIN / "ffprobe") if (_BIN / "ffprobe").exists() else "ffprobe"


def ffmpeg_available() -> bool:
    """True if ffmpeg can actually be run (bin/ffmpeg or on PATH)."""
    import shutil
    return shutil.which(FFMPEG) is not None

# Royalty-free music pool. Drop .mp3/.m4a/.wav files here; reels rotate through
# them and avoid recently-used tracks. Empty folder -> reels ship without music.
MUSIC_DIR = Path(__file__).parent / "music"

# ---------------------------------------------------------------------------
# Card output size  (Instagram / Facebook feed)
# ---------------------------------------------------------------------------
CARD_W = 1080
CARD_H = 1350          # 4:5 portrait takes the most feed space. 1080 for square.

# Overlay darkness over the photo so text stays readable (0.0-1.0)
OVERLAY_STRENGTH = 0.45

# Add an AI-content label to Facebook captions when posting generated images.
AI_CONTENT_LABEL = True

# ---------------------------------------------------------------------------
# Typography — clean modern serif (Fraunces). No script/cursive for a science
# brand. Titles and body both use Fraunces so cards read as professional.
# ---------------------------------------------------------------------------
FONT_DISPLAY = Path(__file__).parent / "fonts" / "static" / "Fraunces_72pt-SemiBold.ttf"
FONT_SMALL = Path(__file__).parent / "fonts" / "static" / "Fraunces_72pt-SemiBold.ttf"
# The "title" slot reuses a clean bold serif (NOT a script font).
FONT_SCRIPT = Path(__file__).parent / "fonts" / "static" / "Fraunces_72pt-SemiBold.ttf"
FONT_SCRIPT_FALLBACK = Path(__file__).parent / "fonts" / "static" / "Fraunces_72pt-SemiBoldItalic.ttf"

# ---------------------------------------------------------------------------
# Background moods -> local palette choices used by the Pillow renderer.
# Clean, scientific, atmospheric. No identifiable faces.
# ---------------------------------------------------------------------------
BACKGROUND_MOODS = [
    "blue DNA double helix abstract, dark background, glowing, scientific, no people",
    "microscope and glassware in a bright modern laboratory, shallow depth of field, no people",
    "green and teal molecular structure render, clean dark background, no people",
    "petri dishes and pipettes on a clean bench, soft light, no people",
    "data visualization of a genome, blue and cyan code-like pattern, no people",
    "a researcher's gloved hands with a pipette (no face), crisp light, laboratory",
    "abstract network of connected nodes, bioinformatics, deep blue, no people",
    "green plants in a tissue-culture lab, biotechnology, bright and clean, no people",
]

STYLE_SUFFIX = (
    "clean scientific photography, modern laboratory, cool blue-green color grade, "
    "soft light, high quality, vertical composition, plenty of negative space for "
    "text, no text, no words, no watermark, no identifiable faces"
)

# ---------------------------------------------------------------------------
# Interactive engagement post formats (comment bait, science edition)
# ---------------------------------------------------------------------------
ENGAGEMENT_FORMATS = [
    "A surprising, TRUE science fact about biology/biochemistry/biotech + a question (e.g. 'Your DNA, uncoiled, would stretch about 2 metres per cell. What fact still blows your mind?')",
    "Finish the sentence: 'The one concept that finally clicked for me in biochem was ______.' (highly shareable among students)",
    "This or that for scientists (e.g. 'Wet lab or dry lab (bioinformatics)? 👇 Defend your choice.')",
    "A tiny PRACTICAL study/lab/career tip people save and share (a mnemonic, a free tool, a technique shortcut)",
    "A myth-vs-fact bust about a common biotech/biology misconception",
    "A motivating truth for students/early-career scientists + 'tag someone who needs this today'",
    "A quick quiz (e.g. 'Name the enzyme that unwinds the DNA double helix 👇 — answer in the comments')",
    "A career question (e.g. 'What skill do you wish you'd learned earlier in your science career?')",
]

# Reel-script formats (not posted by default; kept for reference / future use)
REEL_FORMATS = [
    "One concept in 15 seconds — explain a single biotech idea simply",
    "3 free tools every bioinformatics student should know",
    "Myth vs fact — bust one common biology misconception",
    "A career tip — one thing that helps you get hired in biotech",
    "Did you know — one astonishing true fact about the cell/genome",
]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
OUTPUT_DIR = Path(__file__).parent / "output"


def slot_suffix() -> str:
    """'-morning' / '-evening' when running as a scheduled slot, else ''."""
    s = _os.getenv("MABCOS_SLOT", "").strip()
    return f"-{s}" if s else ""


def today_dirname(offset_days: int = 0) -> str:
    from datetime import date, timedelta
    return (date.today() + timedelta(days=offset_days)).isoformat() + slot_suffix()


def current_batch_dir(offset_days: int = 0) -> Path:
    """The folder for the batch being generated/sent right now (slot-aware),
    so a morning and evening run on the same day don't overwrite each other."""
    return OUTPUT_DIR / today_dirname(offset_days)
