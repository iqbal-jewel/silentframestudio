"""Run-time state, kept as JSON so it stays diffable in git.

post_id is the idempotency key: a post recorded here is never sent again,
even if a run is retried or overlaps.
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_PATH = ROOT / "state" / "state.json"


class State:
    def __init__(self, path: Path = STATE_PATH):
        self.path = path
        if path.exists() and path.stat().st_size:
            self.data = json.loads(path.read_text(encoding="utf-8-sig"))
        else:
            self.data = {"posts": {}}
        self.data.setdefault("posts", {})

    TERMINAL = ("posted", "scheduled", "skipped")

    def is_done(self, post_id) -> bool:
        return self.data["posts"].get(post_id, {}).get("status") in self.TERMINAL

    def record_skipped(self, post_id, publish_at, reason):
        self.data["posts"][post_id] = {
            "remote_id": None,
            "status": "skipped",
            "reason": reason,
            "publish_at": publish_at,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        }

    def record_post(self, post_id, remote_id, status="scheduled", **extra):
        self.data["posts"][post_id] = {
            "remote_id": remote_id,
            "status": status,
            "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            **extra,
        }

    def record_failure(self, post_id, error):
        entry = self.data["posts"].setdefault(post_id, {})
        entry["status"] = "failed"
        entry["error"] = str(error)[:400]
        entry["attempts"] = entry.get("attempts", 0) + 1
        entry["at"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def summary(self):
        posts = self.data["posts"].values()
        counts = {}
        for p in posts:
            counts[p.get("status", "?")] = counts.get(p.get("status", "?"), 0) + 1
        return counts
