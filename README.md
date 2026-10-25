# MABCOS — automated content pipeline

Automated, **human-approved** content for the **MABCOS / innovationthroughbiotech**
Facebook page: biotechnology, biochemistry, and bioinformatics — education,
careers, tutorials, news, scholarships, business ideas, and events.

Each run builds a batch of posts, renders the media, sends everything to Telegram
with **Approve / Reject** buttons, and auto-posts only what you approve from your
phone. It's a retarget of the proven `love-lens-pipeline` engine — same reliable
infra (deduping, soft fallbacks, launchd scheduling), retargeted voice + content.

## What a batch contains (per run, ~2 runs/day)

| Format | What it is | Posts as |
| --- | --- | --- |
| **Video reels** ×2 | Pexels science clip + bold caption + music | Facebook Reel (the growth engine — reaches non-followers) |
| **Insight card** ×1 | One true, memorable line on a concept | Photo post |
| **Explainer card** ×1 | A 5–8 line micro-essay that makes a concept click | Photo post |
| **Engagement post** ×1 | Quiz / fact / "finish the sentence" comment bait | Photo post |
| **Reflection post** ×1 | Warm essay around a real, attributed science quote | Photo post |
| **Amazon product** ×1 | Useful book / lab gear with your affiliate tag | Link post |

All copy is accuracy-first and runs through a strict compliance block (no medical
advice, no invented facts/quotes/stats). Nothing posts without your tap.

## How it flows

1. `run.py` generates a dated batch into `output/<date>-<slot>/` (text via Gemini,
   with hand-written **accurate** local fallbacks if the API is down/quota-limited;
   photos + reel clips via Pexels; cards rendered with Pillow; reels with ffmpeg).
2. `notify.py` sends every item to Telegram with Approve/Reject buttons.
3. You review on your phone.
4. `approve_bot.py` posts approved items to the page and never double-posts.

## Files

- `config.py` — brand, audience voice, per-run counts, fonts, sizes.
- `topics.py` — the biotech/biochem/bioinformatics topic taxonomy + rotation.
- `prompts.py` — all generation prompts (voice + the compliance guardrail).
- `gen_text.py` — Gemini calls + accurate local fallbacks per topic category.
- `quotes.py` — real, correctly-attributed science quotes for reflection posts.
- `reel_visuals.py` — reel clip categories (lab / molecular / data / nature).
- `fetch_image.py`, `gen_image.py`, `compose.py` — card backgrounds + rendering.
- `fetch_video.py`, `fetch_music.py`, `compose_video.py` — reel building.
- `fetch_products.py`, `products.txt` — Amazon Associates (manual-link mode).
- `notify.py`, `approve_bot.py`, `post_fb.py` — Telegram review + Facebook posting.
- `dedupe.py` — stops repeated lines/essays across days.
- `run_slot.sh` + `com.mabcos.*.plist` — scheduling (launchd).

## Setup

```bash
cd /Users/yashabutt/mabcos-pipeline
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`bin/` (ffmpeg/ffprobe) and `music/` (royalty-free tracks) were copied from the
love-lens pipeline, so reels work out of the box.

## Go live — two switches (one-time account actions you must do)

The `.env` already has your shared Gemini, Pexels, Amazon, Facebook **user token**,
and Telegram **chat id** filled in. Two blanks remain:

1. **Telegram bot** — mabcos needs its **own** bot (don't reuse the Love Lens bot
   token; two bots on one token fight over updates). In Telegram, message
   **@BotFather** → `/newbot` → copy the token → set `TELEGRAM_BOT_TOKEN` in `.env`.
   Then send that new bot any message once so it can reach your chat.

2. **Facebook page access** — the app behind your user token is currently granted
   only the *Love Lens* page. Grant it the **mabcos** page too:
   - Open the [Graph API Explorer](https://developers.facebook.com/tools/explorer/),
     select your app, add permissions `pages_show_list`, `pages_read_engagement`,
     `pages_manage_posts`, and when prompted **select the innovationthroughbiotech
     page**. Generate the token (extend it to long-lived in the
     [Access Token Debugger](https://developers.facebook.com/tools/debug/accesstoken/)).
   - Find the mabcos **Page ID**: with that token, open
     `https://graph.facebook.com/v21.0/me/accounts?fields=id,name` — the mabcos row's
     `id` goes into `FB_PAGE_ID`. If you regenerated the user token, paste it into
     `FB_PAGE_TOKEN` too (the same token then serves both pages).

Verify Facebook is wired correctly:

```bash
cd /Users/yashabutt/mabcos-pipeline && .venv/bin/python post_fb.py --test
```

## Run it

Dry run (generates a batch, posts nothing):

```bash
cd /Users/yashabutt/mabcos-pipeline && .venv/bin/python run.py
```

Open `output/<date>/review.html` to eyeball the batch. Then, once the two
switches above are set, send the batch to Telegram:

```bash
cd /Users/yashabutt/mabcos-pipeline && .venv/bin/python notify.py
```

Start the approval listener (keep it running):

```bash
cd /Users/yashabutt/mabcos-pipeline && .venv/bin/python approve_bot.py
```

## Schedule (launchd — survives a sleeping laptop)

```bash
cp com.mabcos.morning.plist com.mabcos.evening.plist com.mabcos.approvebot.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.mabcos.morning.plist
launchctl load ~/Library/LaunchAgents/com.mabcos.evening.plist
launchctl load ~/Library/LaunchAgents/com.mabcos.approvebot.plist
```

Morning slot fires 08:00, evening 19:30 (offset from the Love Lens pipeline so
both don't run at the same minute). Each slot writes its own `output/<date>-<slot>`
folder and runs at most once per day (atomic lock + daily marker).

## Curating Amazon products

Edit `products.txt` (`Name | URL`, one per line). The seeds use search links that
never 404; for better previews swap in specific `…/dp/ASIN…` best-seller links.
Your Associate tag is forced onto every link automatically. When the pool runs
low, the daily run sends you a Telegram alert.

## Compliance gate

Before anything goes live: accurate, original wording, no medical advice, no
invented facts/quotes/stats, genuinely useful. The human Telegram approval step
stays in the loop even when everything else is automated.
