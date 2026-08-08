"""Publisher entrypoint.

All posts go through Facebook's native scheduler (scheduled_publish_time), so
they fire even if this runner is down for days. Each run just looks ahead a
window and hands Meta anything newly in range; post_id idempotency in state
stops duplicates.

    python -m src.publish status
    python -m src.publish schedule --days 7          # dry run
    python -m src.publish schedule --days 7 --live
"""
import argparse
import datetime as dt
import sys
import time
from pathlib import Path

from . import meta, plan, render
from .state import State

ROOT = Path(__file__).resolve().parent.parent
PLAN_PATH = ROOT / "plan" / "content_plan.json"
IMAGES = ROOT / "images"

# Meta rejects a scheduled time less than 10 minutes out.
MIN_LEAD = dt.timedelta(minutes=20)

_NOW = None


def now_et():
    return _NOW or dt.datetime.now(plan.ET)


def log(msg):
    print(f"[{dt.datetime.now(plan.ET):%Y-%m-%d %H:%M %Z}] {msg}", flush=True)


def cmd_schedule(args, posts, st):
    now = now_et()
    horizon = now + dt.timedelta(days=args.days)
    todo = [p for p in posts
            if now + MIN_LEAD <= p.publish_at <= horizon
            and not st.is_done(p.post_id)]

    log(f"{len(todo)} posts to schedule through {horizon:%Y-%m-%d}")
    if not todo:
        return 0

    creds = meta.credentials() if args.live else None
    failures = 0
    for p in todo:
        if not args.live:
            log(f"  DRY  {p.post_id} {p.publish_at:%m-%d %H:%M} {p.slot:12} "
                f"{p.message.splitlines()[0][:60]}")
            continue
        try:
            if p.has_image:
                img = IMAGES / p.image_name
                if not img.exists():
                    render.render(p.message.splitlines()[0], p.image_name,
                                  query=p.image_query or "animation film")
                rid = meta.fb_photo(creds["page_id"], creds["token"], img,
                                     p.message, scheduled_at=p.publish_at)
            else:
                rid = meta.fb_post(creds["page_id"], creds["token"], p.message,
                                    scheduled_at=p.publish_at)
            st.record_post(p.post_id, rid, status="scheduled",
                            publish_at=p.publish_at.isoformat())
            log(f"  OK   {p.post_id} scheduled -> {rid}")
        except Exception as e:  # keep going; one bad row shouldn't stall the batch
            failures += 1
            st.record_failure(p.post_id, e)
            log(f"  FAIL {p.post_id}: {e}")
        st.save()
    return 1 if failures else 0


def cmd_status(args, posts, st):
    now = now_et()
    counts = st.summary()
    upcoming = [p for p in posts if p.publish_at > now]

    log(f"plan: {len(posts)} posts, {posts[0].publish_at:%Y-%m-%d} "
        f"to {posts[-1].publish_at:%Y-%m-%d}")
    log(f"upcoming: {len(upcoming)}   recorded: {sum(counts.values())} {counts}")

    import os
    for key in ("SILENTFRAMESSTUDIO_PAGE_ID", "SILENTFRAMESSTUDIO_PAGE_TOKEN"):
        log(f"env {key}: {'set' if os.environ.get(key) else 'MISSING'}")

    token = os.environ.get("SILENTFRAMESSTUDIO_PAGE_TOKEN")
    if token:
        try:
            info = meta.debug_token(token)
            days = meta.token_expiry(token)
            log(f"token type: {info.get('type', '?')}  "
                f"expires in: {'never' if days is None else f'{days} days'}")
            if days is not None and days < 14:
                log("  WARNING: expires soon -- switch to a System User token")
            dae = info.get("data_access_expires_at")
            if dae:
                left = int((dae - time.time()) // 86400)
                log(f"data access expires in: {left} days")
                if left < 200:
                    log("  NOTE: shorter than the plan. Re-authorise before it lapses.")
            else:
                log("data access: no expiry")
        except Exception as e:
            log(f"token check failed: {e}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["status", "schedule"])
    ap.add_argument("--live", action="store_true",
                    help="actually publish; without it nothing is sent")
    ap.add_argument("--days", type=int, default=7,
                    help="scheduling horizon for schedule")
    ap.add_argument("--plan", default=str(PLAN_PATH))
    ap.add_argument("--now", help="simulate a moment in ET, e.g. 2026-08-01T11:05 "
                                  "(dry-run testing only)")
    args = ap.parse_args(argv)
    if args.now:
        if args.live:
            ap.error("--now is for dry-run testing; refusing to combine with --live")
        globals()["_NOW"] = dt.datetime.fromisoformat(args.now).replace(tzinfo=plan.ET)

    posts = plan.load(args.plan)
    st = State()
    if not args.live and args.command != "status":
        log("DRY RUN -- pass --live to publish")

    handler = {"status": cmd_status, "schedule": cmd_schedule}
    return handler[args.command](args, posts, st)


if __name__ == "__main__":
    sys.exit(main())
