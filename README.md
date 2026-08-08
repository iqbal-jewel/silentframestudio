# SilentFrameStudio Facebook automation

Posts 3x/day to the [Silent Frames Studio](https://facebook.com/1016600324866519)
Facebook Page for 6 months: animation trivia, "did you know" facts, and an
"on this day in animation" post with a rendered image (colourful Pexels
photo background + headline, falls back to a gradient if Pexels is
unavailable).

Everything ships through Facebook's native scheduler (`scheduled_publish_time`),
so a missed GitHub Actions run never drops a post -- it's just picked up and
scheduled on the next hourly run, up to 7 days ahead.

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
