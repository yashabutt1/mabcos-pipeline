import argparse
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

import config

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")


def _env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is not set. Add it to .env first.")
    return value


def send_photo(image_path, caption, callback_data):
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{callback_data}"},
            {"text": "❌ Reject", "callback_data": f"reject:{callback_data}"},
        ]]
    }
    # Telegram caps photo captions at 1024 chars; the FULL caption still posts to
    # Facebook (approve_bot reads it from captions.json, not from this preview).
    tg_caption = caption if len(caption) <= 1024 else caption[:1015].rstrip() + " […]"
    data = {"chat_id": chat_id, "caption": tg_caption, "reply_markup": json.dumps(keyboard)}
    with image_path.open("rb") as fh:
        files = {"photo": (image_path.name, fh, "image/png")}
        resp = requests.post(url, data=data, files=files, timeout=120)
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def send_notice(text):
    """Plain informational message (no approve/reject buttons)."""
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text[:4000]}, timeout=60)


def send_message(text, callback_data):
    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{callback_data}"},
            {"text": "❌ Reject", "callback_data": f"reject:{callback_data}"},
        ]]
    }
    data = {"chat_id": chat_id, "text": text[:4000],
            "reply_markup": json.dumps(keyboard)}
    resp = requests.post(url, data=data, timeout=60)
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def send_video(video_path, caption, callback_data):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    token = _env("TELEGRAM_BOT_TOKEN")
    chat_id = _env("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendVideo"
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Approve", "callback_data": f"approve:{callback_data}"},
            {"text": "❌ Reject", "callback_data": f"reject:{callback_data}"},
        ]]
    }
    data = {"chat_id": chat_id, "caption": caption[:1024],
            "reply_markup": json.dumps(keyboard)}
    with video_path.open("rb") as fh:
        files = {"video": (video_path.name, fh, "video/mp4")}
        resp = requests.post(url, data=data, files=files, timeout=300)
    payload = resp.json()
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def _latest_output_dir() -> Path:
    # Prefer the batch just generated for the current slot (morning/evening),
    # so the evening run notifies the evening batch, not the morning one.
    current = config.current_batch_dir()
    if (current / "captions.json").exists():
        return current
    output_root = config.OUTPUT_DIR
    dirs = sorted((p for p in output_root.iterdir() if p.is_dir()),
                  key=lambda p: p.stat().st_mtime)
    if not dirs:
        raise FileNotFoundError("No output directories found")
    return dirs[-1]


def _latest_cards(output_dir: Path):
    captions_path = output_dir / "captions.json"
    if captions_path.exists():
        payload = json.loads(captions_path.read_text(encoding="utf-8"))
        cards = payload.get("cards", [])
        for item in cards:
            file_name = item.get("file")
            if file_name:
                image_path = output_dir / "cards" / file_name
                if image_path.exists():
                    yield image_path, item
        return

    for image_path in sorted((output_dir / "cards").glob("*.png")):
        yield image_path, {}


def send_latest_batch(output_dir: Path):
    for image_path, item in _latest_cards(output_dir):
        caption = item.get("caption") or "New card for review"
        if item.get("line"):
            caption = f"{caption}\n\n{item['line']}"
        print(f"Sending {image_path.name}...")
        send_photo(image_path, caption, f"{output_dir.name}/{image_path.name}")

    captions_path = output_dir / "captions.json"
    if captions_path.exists():
        payload = json.loads(captions_path.read_text(encoding="utf-8"))

        # Long-form reflection essays (image in cards/, long caption).
        for item in payload.get("reflections", []):
            file_name = item.get("file")
            if not file_name:
                continue
            image_path = output_dir / "cards" / file_name
            if not image_path.exists():
                continue
            caption = item.get("caption") or item.get("essay") or "New reflection post"
            print(f"Sending reflection {file_name}...")
            send_photo(image_path, f"📝 REFLECTION POST\n\n{caption}",
                       f"{output_dir.name}/{file_name}")

        # Interactive engagement cards (images in cards/) — same buttons.
        for item in payload.get("engagement", []):
            file_name = item.get("file")
            if not file_name:
                continue
            image_path = output_dir / "cards" / file_name
            if not image_path.exists():
                continue
            caption = item.get("caption") or item.get("prompt") or "New engagement post"
            print(f"Sending engagement {file_name}...")
            send_photo(image_path, f"💬 ENGAGEMENT POST\n\n{caption}",
                       f"{output_dir.name}/{file_name}")

        # Video reels (if any) — sent with the same Approve/Reject buttons.
        for item in payload.get("video_reels", []):
            file_name = item.get("file")
            if not file_name:
                continue
            video_path = output_dir / "reels" / file_name
            if not video_path.exists():
                continue
            caption = item.get("caption") or item.get("line") or "New reel for review"
            print(f"Sending reel {file_name}...")
            send_video(video_path, caption, f"{output_dir.name}/reels/{file_name}")

        # Amazon affiliate product posts (link posts, no media file).
        for item in payload.get("products", []):
            asin = item.get("asin") or item.get("url", "")[-12:]
            text = item.get("tg_text") or item.get("caption") or "New product for review"
            print(f"Sending product {item.get('name','')[:40]}...")
            send_message(f"🛒 PRODUCT POST\n\n{text}",
                         f"{output_dir.name}/products/{asin}")

        # Informational alerts (e.g. product pool running low) — no buttons.
        for msg in payload.get("alerts", []):
            print(f"Sending alert: {msg[:50]}")
            send_notice(msg)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Send a card image to Telegram")
    parser.add_argument("--test", action="store_true", help="Send one existing card from the latest output folder")
    parser.add_argument("--image", help="Path to the image file to send")
    parser.add_argument("--caption", default="New card for review", help="Caption to send")
    parser.add_argument("--callback-data", default="test", help="Callback data payload")
    args = parser.parse_args(argv)

    if args.test:
        output_dir = _latest_output_dir()
        image_path = output_dir / "cards" / "card_1.png"
        if not image_path.exists():
            image_path = next((p for p in (output_dir / "cards").glob("*.png") if p.is_file()), None)
        if image_path is None or not image_path.exists():
            raise FileNotFoundError("No card images found in the latest output folder")
        print(f"Sending {image_path}...")
        send_photo(image_path, args.caption, f"{output_dir.name}/{image_path.name}")
        return

    if args.image:
        send_photo(args.image, args.caption, args.callback_data)
        return

    send_latest_batch(_latest_output_dir())


if __name__ == "__main__":
    main(sys.argv[1:])
