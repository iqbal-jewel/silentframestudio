"""Publishes cozy Reels from videos/ against plan/reels_plan.json.

Videos are matched to plan rows purely by order: the Nth video file that
shows up in videos/ (natural sort) is assigned to the Nth unused plan row,
regardless of its filename. One video is scheduled per day, stepping the
daily slot forward each time a new video is found -- so this is meant to be
re-run locally (manually, or via Task Scheduler) whenever a new video lands
in the folder; it only acts on videos it hasn't seen before.

    python -m src.publish_reels status
    python -m src.publish_reels run                # dry run
    python -m src.publish_reels run --live
"""
import argparse
import datetime as dt
import json
import re
import sys
import zoneinfo
from pathlib import Path

from . import reels

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "plan" / "reels_plan.json"
VIDEOS = ROOT / "videos"
STATE_PATH = ROOT / "state" / "reels_state.json"

ET = zoneinfo.ZoneInfo("America/New_York")
SLOT_HOUR, SLOT_MINUTE = 18, 0  # one cozy Reel per day, 6pm ET
MIN_LEAD = dt.timedelta(minutes=20)
VIDEO_EXTS = {".mp4", ".mov", ".m4v"}


def _natural_key(name: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", name)]


def load_plan():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8-sig"))


def load_state():
    if STATE_PATH.exists() and STATE_PATH.stat().st_size:
        return json.loads(STATE_PATH.read_text(encoding="utf-8-sig"))
    return {"last_scheduled_date": None, "next_plan_index": 0,
            "used_video_files": [], "posts": {}}


def save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")


def list_new_videos(state):
    files = sorted((p for p in VIDEOS.iterdir() if p.suffix.lower() in VIDEO_EXTS),
                    key=lambda p: _natural_key(p.name))
    used = set(state["used_video_files"])
    return [p for p in files if p.name not in used]


def next_slot(state, now):
    if state["last_scheduled_date"]:
        last = dt.date.fromisoformat(state["last_scheduled_date"])
        day = last + dt.timedelta(days=1)
    else:
        candidate = dt.datetime.combine(now.date(), dt.time(SLOT_HOUR, SLOT_MINUTE), ET)
        day = now.date() if now + MIN_LEAD <= candidate else now.date() + dt.timedelta(days=1)
    return dt.datetime.combine(day, dt.time(SLOT_HOUR, SLOT_MINUTE), ET)


def log(msg):
    print(f"[{dt.datetime.now(ET):%Y-%m-%d %H:%M %Z}] {msg}", flush=True)


def cmd_status(args):
    plan = load_plan()
    state = load_state()
    new_videos = list_new_videos(state)
    log(f"plan: {len(plan)} rows, next unused index: {state['next_plan_index']}")
    log(f"videos/ : {len(state['used_video_files'])} already scheduled, "
        f"{len(new_videos)} new and waiting")
    for p in new_videos:
        log(f"  NEW  {p.name}")
    log(f"last scheduled date: {state['last_scheduled_date'] or 'none yet'}")
    counts = {}
    for post in state["posts"].values():
        counts[post.get("status", "?")] = counts.get(post.get("status", "?"), 0) + 1
    log(f"recorded posts: {counts}")
    return 0


def cmd_run(args):
    plan = load_plan()
    state = load_state()
    new_videos = list_new_videos(state)
    if not new_videos:
        log("no new videos in videos/ -- nothing to do")
        return 0

    if state["next_plan_index"] + len(new_videos) > len(plan):
        log(f"WARNING: only {len(plan) - state['next_plan_index']} plan rows left "
            f"but {len(new_videos)} new videos -- extra videos will be skipped "
            f"until the plan is extended")

    creds = reels.credentials() if args.live else None
    now = dt.datetime.now(ET)
    failures = 0

    for video_path in new_videos:
        if state["next_plan_index"] >= len(plan):
            log(f"  SKIP {video_path.name}: no plan rows left")
            break
        row = plan[state["next_plan_index"]]
        publish_at = next_slot(state, now)
        caption = row["caption_with_hashtags"]

        if not args.live:
            log(f"  DRY  row {row['id']} <- {video_path.name} "
                f"@ {publish_at:%Y-%m-%d %H:%M %Z}  {caption.splitlines()[0][:60]}")
            state["next_plan_index"] += 1
            state["used_video_files"].append(video_path.name)
            state["last_scheduled_date"] = publish_at.date().isoformat()
            continue

        try:
            video_id = reels.publish_reel(creds["page_id"], creds["token"],
                                           video_path, caption, scheduled_at=publish_at)
            state["posts"][row["id"]] = {
                "video_file": video_path.name,
                "remote_id": video_id,
                "status": "scheduled",
                "publish_at": publish_at.isoformat(),
                "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            }
            state["next_plan_index"] += 1
            state["used_video_files"].append(video_path.name)
            state["last_scheduled_date"] = publish_at.date().isoformat()
            save_state(state)
            log(f"  OK   row {row['id']} <- {video_path.name} "
                f"scheduled {publish_at:%Y-%m-%d %H:%M %Z} -> {video_id}")
        except Exception as e:
            failures += 1
            log(f"  FAIL {video_path.name}: {e}")

    if not args.live:
        log("DRY RUN -- pass --live to actually upload and schedule")
    else:
        save_state(state)
    return 1 if failures else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "run"])
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args(argv)
    handler = {"status": cmd_status, "run": cmd_run}
    return handler[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
