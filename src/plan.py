"""Loads the content plan (plan/content_plan.json) into Post objects.

The plan is a flat JSON list of entries, one per scheduled post:
    {"post_id": "2026-08-09-trivia", "date": "2026-08-09", "slot": "trivia",
     "publish_at": "2026-08-09T14:00:00-04:00", "message": "...",
     "image_query": "film reel"}

publish_at is the only thing that matters for scheduling; date/slot are kept
for readability and idempotency-key stability. image_query is only present
on on_this_day rows (the only slot that carries an image).
"""
import datetime as dt
import json
import zoneinfo
from dataclasses import dataclass
from pathlib import Path

ET = zoneinfo.ZoneInfo("America/New_York")


@dataclass
class Post:
    post_id: str
    slot: str
    publish_at: dt.datetime
    message: str
    image_query: str | None = None

    @property
    def platform(self):
        return "Facebook"

    @property
    def has_image(self):
        return self.slot == "on_this_day"

    @property
    def image_name(self):
        return f"{self.post_id}.jpg"


def load(path) -> list[Post]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    posts = []
    for row in data:
        posts.append(Post(
            post_id=row["post_id"],
            slot=row["slot"],
            publish_at=dt.datetime.fromisoformat(row["publish_at"]),
            message=row["message"],
            image_query=row.get("image_query"),
        ))
    posts.sort(key=lambda p: p.publish_at)
    return posts


def due(posts, now, max_late_minutes):
    cutoff = now - dt.timedelta(minutes=max_late_minutes)
    return [p for p in posts if cutoff <= p.publish_at <= now]


def overdue(posts, now, max_late_minutes):
    cutoff = now - dt.timedelta(minutes=max_late_minutes)
    return [p for p in posts if p.publish_at < cutoff]
