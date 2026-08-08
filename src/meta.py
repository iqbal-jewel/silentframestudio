"""Thin wrapper around the Meta Graph API for text-only Facebook Page posts."""
import os
import time

import requests

GRAPH = "https://graph.facebook.com/v19.0"


def credentials():
    page_id = os.environ.get("SILENTFRAMESSTUDIO_PAGE_ID")
    token = os.environ.get("SILENTFRAMESSTUDIO_PAGE_TOKEN")
    if not page_id or not token:
        raise RuntimeError(
            "SILENTFRAMESSTUDIO_PAGE_ID / SILENTFRAMESSTUDIO_PAGE_TOKEN not set"
        )
    return {"page_id": page_id, "token": token}


def fb_post(page_id, token, message, scheduled_at=None):
    """Publish (or schedule) a text post to the Page feed.

    scheduled_at, if given, must be a tz-aware datetime at least 10 minutes
    in the future; Meta accepts up to ~75 days ahead.
    """
    params = {"message": message, "access_token": token}
    if scheduled_at is not None:
        params["published"] = "false"
        params["scheduled_publish_time"] = int(scheduled_at.timestamp())
    r = requests.post(f"{GRAPH}/{page_id}/feed", data=params, timeout=30)
    r.raise_for_status()
    return r.json()["id"]


def fb_photo(page_id, token, image_path, caption, scheduled_at=None):
    """Publish (or schedule) a photo post. Bytes go up in the request body,
    so no public URL is needed."""
    params = {"caption": caption, "access_token": token}
    if scheduled_at is not None:
        params["published"] = "false"
        params["scheduled_publish_time"] = int(scheduled_at.timestamp())
    with open(image_path, "rb") as f:
        r = requests.post(f"{GRAPH}/{page_id}/photos", data=params,
                           files={"source": f}, timeout=60)
    r.raise_for_status()
    return r.json()["id"]


def debug_token(token):
    r = requests.get(f"{GRAPH}/debug_token",
                      params={"input_token": token, "access_token": token},
                      timeout=30)
    r.raise_for_status()
    return r.json()["data"]


def token_expiry(token):
    info = debug_token(token)
    exp = info.get("expires_at")
    if not exp:
        return None
    return int((exp - time.time()) // 86400)
