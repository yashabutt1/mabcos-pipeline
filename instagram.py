"""Auto cross-post approved content to Instagram (a Business/Creator account linked
to the Facebook Page), for extra automated reach beyond the dormant FB page.

Instagram's publishing API needs a PUBLIC media URL (it fetches the file itself),
so the caller passes the image's public Facebook-CDN URL (cards) or a public video
URL (reels). Everything no-ops cleanly until Instagram is actually set up:

  SETUP (one time):
    1. Have an Instagram **Business or Creator** account for MABCOS.
    2. Link it to the Facebook Page (Meta Business Suite → Settings → Instagram).
    3. Assign the IG account to the system user and grant instagram_basic +
       instagram_content_publish, then put the new token in FB_PAGE_TOKEN.

`available()` tells the caller whether cross-posting is live.
"""
from __future__ import annotations

import time

import requests

import post_fb

G = "https://graph.facebook.com/v21.0"


def _ig_user_id(token: str):
    r = requests.get(f"{G}/{post_fb.page_id()}",
                     params={"fields": "instagram_business_account", "access_token": token},
                     timeout=30).json()
    return (r.get("instagram_business_account") or {}).get("id")


def available(token: str = None) -> bool:
    try:
        token = token or post_fb.resolve_token()
        return bool(_ig_user_id(token))
    except Exception:
        return False


def _publish(igid: str, token: str, params: dict) -> str:
    create = requests.post(f"{G}/{igid}/media",
                           data={**params, "access_token": token}, timeout=120).json()
    cid = create.get("id")
    if not cid:
        raise RuntimeError(f"container create failed: {create}")
    # ALL media (images included) need a moment to finish processing before publish —
    # publishing too early returns code 9007 "media is not ready". Poll until FINISHED.
    is_video = params.get("media_type") in ("REELS", "VIDEO")
    for _ in range(40 if is_video else 12):
        st = requests.get(f"{G}/{cid}", params={"fields": "status_code", "access_token": token},
                          timeout=30).json().get("status_code")
        if st == "FINISHED":
            break
        if st == "ERROR":
            raise RuntimeError("Instagram failed to process the media")
        time.sleep(6 if is_video else 3)
    # Publish, retrying briefly if Instagram still reports the media isn't ready (9007).
    last = None
    for _ in range(5):
        pub = requests.post(f"{G}/{igid}/media_publish",
                            data={"creation_id": cid, "access_token": token}, timeout=60).json()
        if pub.get("id"):
            return pub["id"]
        last = pub
        if (pub.get("error", {}) or {}).get("code") == 9007:
            time.sleep(4)
            continue
        break
    raise RuntimeError(f"media_publish failed: {last}")


def publish_image(image_url: str, caption: str, token: str = None):
    """Cross-post a card image to Instagram. Returns the IG media id or None."""
    token = token or post_fb.resolve_token()
    igid = _ig_user_id(token)
    if not igid or not image_url:
        return None
    return _publish(igid, token, {"image_url": image_url, "caption": (caption or "")[:2200]})


def publish_reel(video_url: str, caption: str, token: str = None):
    """Cross-post a reel to Instagram Reels. Returns the IG media id or None."""
    token = token or post_fb.resolve_token()
    igid = _ig_user_id(token)
    if not igid or not video_url:
        return None
    return _publish(igid, token, {"media_type": "REELS", "video_url": video_url,
                                  "caption": (caption or "")[:2200]})
