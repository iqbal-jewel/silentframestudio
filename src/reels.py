"""Facebook Page Reels publishing (resumable upload protocol).

    start   -> POST {page}/video_reels?upload_phase=start   => video_id, upload_url
    upload  -> POST upload_url with raw video bytes           (rupload.facebook.com)
    finish  -> POST {page}/video_reels?upload_phase=finish   => publish or schedule
"""
import os

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


def start_upload(page_id, token):
    r = requests.post(f"{GRAPH}/{page_id}/video_reels",
                       params={"upload_phase": "start", "access_token": token},
                       timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["video_id"], data["upload_url"]


def upload_bytes(upload_url, token, video_path):
    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(
            upload_url,
            headers={
                "Authorization": f"OAuth {token}",
                "offset": "0",
                "file_size": str(size),
            },
            data=f,
            timeout=600,
        )
    r.raise_for_status()
    body = r.json()
    if not body.get("success", True):
        raise RuntimeError(f"upload failed: {body}")


def finish_upload(page_id, token, video_id, description, scheduled_at=None):
    params = {
        "upload_phase": "finish",
        "video_id": video_id,
        "description": description,
        "access_token": token,
    }
    if scheduled_at is not None:
        params["video_state"] = "SCHEDULED"
        params["scheduled_publish_time"] = int(scheduled_at.timestamp())
    else:
        params["video_state"] = "PUBLISHED"
    r = requests.post(f"{GRAPH}/{page_id}/video_reels", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def publish_reel(page_id, token, video_path, caption, scheduled_at=None):
    """Full flow: start -> upload -> finish. Returns the video_id."""
    video_id, upload_url = start_upload(page_id, token)
    upload_bytes(upload_url, token, video_path)
    finish_upload(page_id, token, video_id, caption, scheduled_at=scheduled_at)
    return video_id
