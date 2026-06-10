# Twice-Daily Collection, Once-Daily Publish — Design

**Date:** 2026-06-10
**Status:** Approved, ready for implementation plan

## Problem

The data pipeline listens to AISStream for a single 30-minute window per day
(`COLLECTION_DURATION: 1800` seconds, fired at `0 20 * * *` UTC = 06:00 AEST).
That samples 30 minutes out of 1,440, so most vessels never ping during the
window — which is why the pipeline carries `silent_arrival` / `probable_arrival`
inference to compensate for sparse sampling.

Adding a second 30-minute listening window 12 hours later roughly doubles the
raw catch and gives the inference logic more observations to work with,
improving coverage. The live site should still refresh only once a day, in the
morning, as it does today.

## Goal

Run data collection twice a day (12h apart), publish the site once a day
(morning), with no double-counting and no change to the collector or pipeline.

## Scope

The entire change is contained in `.github/workflows/nightly-update.yml`. No
changes to the collector, the pipeline (`pipeline/`), `deploy.yml`, or
`COLLECTION_DURATION`.

## Design

### Schedule

Two cron entries in `nightly-update.yml`, exactly 12 hours apart in UTC so the
gap holds through Australian DST transitions:

- `0 20 * * *` → 06:00 AEST / 07:00 AEDT — **publishing run** (unchanged from today)
- `0 8 * * *`  → 18:00 AEST / 19:00 AEDT — **collect-only run** (new)

### Run behaviour

The job body is identical for both runs — same collector, same 30-minute
`COLLECTION_DURATION`, same pipeline steps. Only two steps branch on which cron
fired, using `github.event.schedule`:

1. **Commit step.** The collect-only run commits its data with `[skip ci]` in
   the commit message. The data still lands on `main` (so the next morning's
   run builds on it), but GitHub skips the push-triggered `deploy.yml`, so the
   live site does not rebuild. The publishing run commits normally.

2. **Deploy-trigger step.** Gated to the publishing run only. Manual
   `workflow_dispatch` is treated as a publishing run (preserves today's
   "publish now" behaviour).

`workflow_dispatch` has no `github.event.schedule` value, so the branch
conditions must treat "not the 18:00 schedule" as publish — i.e. the
collect-only path keys specifically off `github.event.schedule == '0 8 * * *'`,
and everything else (the 20:00 schedule and manual dispatch) publishes.

### Why this is safe (no double-counting)

Verified against the current pipeline code:

- **Arrivals** (`arrivals.json`) are deduped against existing records at
  detection time → a vessel is not counted twice.
- **Monthly estimates** (`monthly-estimates.json`) are fully *rebuilt* from
  `arrivals.json` every run (`rebucket_monthly_from_arrivals`) → idempotent.
- **Daily estimates** and the **en-route snapshot** are *overwritten* per run
  (last-write-wins live snapshots) → no accumulation.

A second run per day therefore just folds in more observations through the
persisted state files; it cannot inflate any total.

### Cumulative coverage mechanism

The collector only listens live for its own 30-minute window — neither run
re-listens to the other's window. Cumulative coverage comes from persistence,
not from a longer listen: each run loads the committed state files
(`vessels.json`, `arrivals.json`, …), folds in its window's observations, and
commits them back. The morning publishing run therefore loads state that
already carries the previous evening's observations, listens its own 30
minutes, then publishes the combined result.

Concrete payoff: a vessel that pings near a port at 18:00 and then goes silent
can be caught as a `probable_arrival` and later confirmed using the evening
data, where a morning-only schedule would have missed it entirely.

### Accepted behaviour: daily series is last-write-wins

`update_daily_estimates` keys the en-route snapshot by Sydney-local date and
overwrites that date's entry every run. With two runs on the same Sydney date,
the 18:00 write overwrites the 06:00 write.

Effect:

- The "today" figure the site shows at publish time is always the fresh 06:00
  morning snapshot.
- Once the *next* morning's deploy goes out, the now-historical day's entry
  reflects the **evening (18:00)** snapshot, because that was the last write to
  that date.

This is accepted as-is. The evening reading is an equally valid (arguably more
complete) measure of en-route volume, nothing is double-counted, and the chart
does not depend on a fixed daily sample time. We explicitly chose **not** to
pin the daily series to the morning run, to avoid adding a branch for no real
benefit.

## Out of scope (YAGNI)

- No change to the collector or any `pipeline/` module.
- No change to `deploy.yml`.
- No change to `COLLECTION_DURATION` (stays 1800s / 30 min per window).
- No pinning of the daily series to a fixed time of day.

## Success criteria

- `nightly-update.yml` has two cron entries 12h apart (`0 20 * * *`, `0 8 * * *`).
- The 18:00 run collects, commits data to `main` with `[skip ci]`, and does
  **not** deploy.
- The 20:00 run and manual `workflow_dispatch` collect, commit normally, and
  deploy — i.e. site refresh time and cadence (once daily, morning) are
  unchanged from today.
- No new double-counting in any data file.
