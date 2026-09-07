# The Nightlight Express -- cozy Reels automation

This repo (originally SilentFrameStudio, same Page ID, now repurposed and
renamed "The Nightlight Express") posts one cozy Ghibli-style ambient Reel
per day to the Page's Facebook Reels, driven by a 90-video content plan.

The old trivia/fact/on-this-day GitHub Actions pipeline (`src/publish.py`,
`src/meta.py`, `src/render.py`) is retired -- those old posts were purged
from the Page and `PUBLISH_ENABLED` is off. `src/publish_reels.py` is the
active pipeline now; see below.

## Cozy Reels pipeline

- `plan/reels_plan.json` -- 90 rows (id, location, variant, caption+hashtags)
  extracted from the source content plan spreadsheet.
- `videos/` (gitignored, local only) -- drop finished videos here as you
  make them. Videos are matched to plan rows purely by **order**: the Nth
  video that shows up (natural sort) gets plan row N's caption, regardless
  of filename.
- `state/reels_state.json` -- tracks which videos have been consumed and
  which plan row/date they were scheduled against, so re-running is safe.

Runs **locally** (not GitHub Actions) since videos are large local files:

```
python -m src.publish_reels status
python -m src.publish_reels run            # dry run
python -m src.publish_reels run --live
```

One video is scheduled per day at 6pm ET via Facebook's native Reels
scheduler (`video_reels` resumable upload + `scheduled_publish_time`), so
re-run this anytime you add a new video -- it only acts on videos it
hasn't seen before, and only schedules as many days ahead as you have
videos ready.

## Setup

```
pip install -r requirements.txt
```

Environment variables (see `.env.example` in `../Automation`):

- `SILENTFRAMESSTUDIO_PAGE_ID`, `SILENTFRAMESSTUDIO_PAGE_TOKEN` -- Page access
- `PEXELS_API_KEY` -- optional; on-this-day cards fall back to a gradient
  background if unset

## Commands

```
python -m src.publish status
python -m src.publish schedule --days 7            # dry run
python -m src.publish schedule --days 7 --live
```

## Going live

Nothing publishes from the scheduled GitHub Actions workflow until the repo
variable `PUBLISH_ENABLED` is set to `true` (Settings -> Secrets and
variables -> Actions -> Variables). Use `workflow_dispatch` with `live: true`
to test a single manual run first.

## Content plan

`plan/content_plan.json` holds every post: post_id, slot (`trivia` / `fact` /
`on_this_day`), publish_at (ET), message, and (for on_this_day) an
image_query. post_id is the idempotency key in `state/state.json` -- a post
recorded there is never sent again.
