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


def _resolve_page_access_token(page_id: str) -> str:
    configured_token = os.getenv("FB_PAGE_TOKEN", "").strip()
    if not configured_token:
        raise RuntimeError("Set FB_PAGE_TOKEN to either a Page access token or a user token that can access /me/accounts")

    debug_url = "https://graph.facebook.com/v21.0/debug_token"
    debug_params = {"input_token": configured_token, "access_token": configured_token}
    debug_resp = requests.get(debug_url, params=debug_params, timeout=30)
    debug_payload = debug_resp.json()
    if not debug_resp.ok:
        raise RuntimeError(json.dumps(debug_payload, indent=2))

    token_type = debug_payload.get("data", {}).get("type", "").upper()
    if token_type == "PAGE":
        print(f"Using configured Page access token for page {page_id}")
        return configured_token

    if token_type not in ("USER", "SYSTEM_USER"):
        raise RuntimeError("FB_PAGE_TOKEN must be a valid User, System User, or Page access token")

    print(f"FB_PAGE_TOKEN is a {token_type.lower()} token; resolving a Page access token from /me/accounts")
    url = "https://graph.facebook.com/v21.0/me/accounts"
    params = {"access_token": configured_token, "fields": "id,name,access_token"}
    resp = requests.get(url, params=params, timeout=30)
    payload = resp.json()
    if not resp.ok:
        raise RuntimeError(json.dumps(payload, indent=2))

    for page in payload.get("data", []):
        if page.get("id") == page_id:
            page_token = page.get("access_token", "").strip()
            if page_token:
                print(f"Resolved Page access token from /me/accounts for page {page_id}")
                return page_token

    raise RuntimeError("Could not resolve a Page access token from /me/accounts. Grant the app the required Page permissions and use a Page access token in FB_PAGE_TOKEN.")


def check_token():
    page_id = _env("FB_PAGE_ID")
    token = _resolve_page_access_token(page_id)
    url = "https://graph.facebook.com/v21.0/debug_token"
    params = {"input_token": token, "access_token": token}
    try:
        resp = requests.get(url, params=params, timeout=30)
        payload = resp.json()
        if not resp.ok:
            print(payload)
            raise RuntimeError("Facebook token validation failed")
        data = payload.get("data", {})
        expires_at = data.get("expires_at")
        if expires_at:
            from datetime import datetime, timezone
            expiry = datetime.fromtimestamp(expires_at, tz=timezone.utc)
            days_left = (expiry - datetime.now(timezone.utc)).days
            print(f"Token expires at {expiry.isoformat()} ({days_left} days left)")
            if days_left < 7:
                print("Warning: fewer than 7 days remain. Re-generate and extend the token in the Access Token Debugger.")
        else:
            print("Token does not expire")
        return payload
    except Exception as exc:
        print(f"Facebook token check failed: {exc}")
        print("If the token is expired or invalid, re-generate it in the Access Token Debugger and extend it before posting.")
        raise


def build_caption(caption: str) -> str:
    return caption.strip()


def post_card(image_path, caption, when=None):
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(image_path)

    page_id = _env("FB_PAGE_ID")
    page_token = _resolve_page_access_token(page_id)
    url = f"https://graph.facebook.com/v21.0/{page_id}/photos"
    with image_path.open("rb") as fh:
        files = {"source": (image_path.name, fh, "image/png")}
        data = {"caption": build_caption(caption), "access_token": page_token}
        if when:  # schedule for a peak window instead of publishing now
            data["published"] = "false"
            data["scheduled_publish_time"] = int(when)
        try:
            resp = requests.post(url, files=files, data=data, timeout=120)
            payload = resp.json()
            if not resp.ok:
                if payload.get("error", {}).get("code") in {190, 102}:
                    print("Facebook rejected the request. If the token is expired or invalid, re-generate and extend the Page access token in the Access Token Debugger.")
                raise RuntimeError(json.dumps(payload, indent=2))
            print(json.dumps(payload, indent=2))
            return payload
        except requests.RequestException as exc:
            raise RuntimeError(f"Network error while posting to Facebook: {exc}") from exc


def _post_video_fallback(page_id, token, video_path, caption, when=None):
    """Plain video post (used if the Reels API is unavailable for this token)."""
    url = f"https://graph.facebook.com/v21.0/{page_id}/videos"
    with Path(video_path).open("rb") as fh:
        files = {"source": (Path(video_path).name, fh, "video/mp4")}
        data = {"description": build_caption(caption), "access_token": token}
        if when:
            data["published"] = "false"
            data["scheduled_publish_time"] = int(when)
        resp = requests.post(url, files=files, data=data, timeout=300)
    payload = resp.json()
    if not resp.ok:
        raise RuntimeError(json.dumps(payload, indent=2))
    print("Posted as a regular video (Reels API not available for this token).")
    return {"id": payload.get("id"), "as": "video"}


def post_reel(video_path, caption, when=None):
    """Publish a vertical MP4 as a Facebook Reel via the resumable Reels API.

    Falls back to a normal video post if the Reels endpoint rejects the token.
    ``when`` (unix seconds) schedules the reel for a peak window instead of now.
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(video_path)
    page_id = _env("FB_PAGE_ID")
    token = _resolve_page_access_token(page_id)
    base = "https://graph.facebook.com/v21.0"

    try:
        # 1) start an upload session
        start = requests.post(f"{base}/{page_id}/video_reels",
                              data={"upload_phase": "start", "access_token": token}, timeout=60)
        sj = start.json()
        if not start.ok or "video_id" not in sj or "upload_url" not in sj:
            raise RuntimeError(json.dumps(sj, indent=2))
        video_id, upload_url = sj["video_id"], sj["upload_url"]

        # 2) upload the binary
        size = video_path.stat().st_size
        with video_path.open("rb") as fh:
            up = requests.post(upload_url,
                               headers={"Authorization": f"OAuth {token}",
                                        "offset": "0", "file_size": str(size)},
                               data=fh, timeout=600)
        uj = up.json() if up.content else {}
        if not up.ok or not uj.get("success", True):
            raise RuntimeError(f"upload failed: {up.status_code} {up.text[:400]}")

        # 3) publish (or schedule for a peak window)
        fin_data = {"upload_phase": "finish", "video_id": video_id,
                    "description": build_caption(caption), "access_token": token}
        if when:
            fin_data["video_state"] = "SCHEDULED"
            fin_data["scheduled_publish_time"] = int(when)
        else:
            fin_data["video_state"] = "PUBLISHED"
        fin = requests.post(f"{base}/{page_id}/video_reels", data=fin_data, timeout=120)
        fj = fin.json()
        if not fin.ok or not fj.get("success", False):
            raise RuntimeError(json.dumps(fj, indent=2))
        print(f"{'Scheduled' if when else 'Published'} reel {video_id}")
        return {"id": video_id, "as": "reel"}
    except Exception as exc:
        print(f"Reels API failed ({exc}); falling back to a normal video post.")
        return _post_video_fallback(page_id, token, video_path, caption, when=when)


def post_link(message, link, when=None):
    """Publish a link post to the Page feed (Facebook renders the link preview)."""
    page_id = _env("FB_PAGE_ID")
    token = _resolve_page_access_token(page_id)
    url = f"https://graph.facebook.com/v21.0/{page_id}/feed"
    data = {"message": message, "link": link, "access_token": token}
    if when:
        data["published"] = "false"
        data["scheduled_publish_time"] = int(when)
    resp = requests.post(url, data=data, timeout=60)
    payload = resp.json()
    if not resp.ok:
        raise RuntimeError(json.dumps(payload, indent=2))
    return {"id": payload.get("id")}


# --------------------------------------------------------------------------- comments
def resolve_token() -> str:
    """Public helper: resolve a usable Page access token once (cache-friendly)."""
    return _resolve_page_access_token(_env("FB_PAGE_ID"))


def page_id() -> str:
    return _env("FB_PAGE_ID")


def list_comments(object_id: str, token: str = None, limit: int = 25) -> list[dict]:
    """Recent comments on a post/photo/reel, newest first."""
    token = token or resolve_token()
    url = f"https://graph.facebook.com/v21.0/{object_id}/comments"
    params = {"access_token": token, "fields": "id,message,from,created_time",
              "order": "reverse_chronological", "limit": limit}
    resp = requests.get(url, params=params, timeout=30)
    payload = resp.json()
    if not resp.ok:
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload.get("data", [])


def photo_public_url(photo_id: str, token: str = None):
    """Public CDN URL of a posted photo — used as the Instagram image source."""
    token = token or resolve_token()
    r = requests.get(f"https://graph.facebook.com/v21.0/{photo_id}",
                     params={"fields": "images", "access_token": token}, timeout=30).json()
    imgs = r.get("images") or []
    return imgs[0]["source"] if imgs else None


def video_source_url(video_id: str, token: str = None):
    """Public source URL of a posted video/reel, if the token can read it."""
    token = token or resolve_token()
    r = requests.get(f"https://graph.facebook.com/v21.0/{video_id}",
                     params={"fields": "source", "access_token": token}, timeout=30).json()
    return r.get("source")


def post_comment_reply(comment_id: str, message: str, token: str = None) -> dict:
    """Reply to a specific comment (used only when YOU tap 'Send reply')."""
    token = token or resolve_token()
    url = f"https://graph.facebook.com/v21.0/{comment_id}/comments"
    resp = requests.post(url, data={"message": message, "access_token": token}, timeout=60)
    payload = resp.json()
    if not resp.ok:
        raise RuntimeError(json.dumps(payload, indent=2))
    return {"id": payload.get("id")}


def _latest_output_dir() -> Path:
    output_root = config.OUTPUT_DIR
    dirs = sorted(p for p in output_root.iterdir() if p.is_dir())
    if not dirs:
        raise FileNotFoundError("No output directories found")
    return dirs[-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Post a card to the Facebook Page")
    parser.add_argument("--test", action="store_true", help="Post one existing card from the latest output folder")
    parser.add_argument("--image", help="Path to the image file to post")
    parser.add_argument("--caption", default="New from The Love Lens", help="Caption to post")
    args = parser.parse_args(argv)

    if args.test:
        output_dir = _latest_output_dir()
        image_path = output_dir / "cards" / "card_1.png"
        if not image_path.exists():
            image_path = next((p for p in (output_dir / "cards").glob("*.png") if p.is_file()), None)
        if image_path is None or not image_path.exists():
            raise FileNotFoundError("No card images found in the latest output folder")
        print(f"Posting {image_path}...")
        post_card(image_path, args.caption)
        return

    if args.image:
        post_card(args.image, args.caption)
        return

    parser.error("Specify --test or --image")


if __name__ == "__main__":
    if "--test" in sys.argv:
        check_token()
    main(sys.argv[1:])
