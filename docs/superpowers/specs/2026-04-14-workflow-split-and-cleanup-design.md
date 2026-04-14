# Workflow Split + Indonesia Cleanup + Chart + Cron — Design

**Date:** 2026-04-14
**Status:** Approved (verbal, via chat)

## Problem

Four issues noticed after the incident recovery:

1. **Code pushes don't deploy.** The single `nightly-update.yml` workflow bundles data collection and site deployment, and it only triggers on cron/manual dispatch. Pushing a code-only change (component tweak, spec doc) doesn't update the site — the user has to wait for the next scheduled run or manually trigger one, which spends 30 minutes collecting AIS data it doesn't need.
2. **Stale Indonesia ships linger on the map.** The JAVA_SEA carve-out works on fresh data, but six existing `vessels.json` records have `region: "AU_APPROACH"` from the pre-JAVA_SEA era (restored from commit `6c7d440` during the incident recovery). These records' stored classification never gets re-validated, so the retention filter can't catch them.
3. **Chart still shows current (incomplete) starting month.** Previous decision was "label current month as MTD" but the intent was narrower: hide the pipeline's *starting* incomplete month (April 2026), and only start rendering a month once it has a reasonable shot at filling out.
4. **Cron runs at 16:00 UTC.** User wants overnight UK time (~3am).

## Goals

- Code pushes deploy in ~1 minute without touching the pipeline.
- Nightly pipeline still runs at 3am UK.
- Six Indonesian records stop showing on the map now, and the site is self-correcting if the classification rules shift again later.
- The monthly chart hides the month the pipeline started in until the next month begins.

## Design

### 1. Split workflows

Keep `.github/workflows/nightly-update.yml` for the data pipeline only. Remove the Node build, upload-artifact, and deploy-pages steps from the end — its last step is committing + pushing the data update.

Add `.github/workflows/deploy.yml` triggered on `push` to `main` (and `workflow_dispatch` for manual redeploys). It checks out, runs `npm ci` + `npm run build`, uploads the artifact, and deploys to GH Pages.

A nightly pipeline run writes a data commit, which pushes to main, which triggers `deploy.yml` — so data updates still flow to the site automatically. Code-only pushes trigger `deploy.yml` directly.

Concurrency: `deploy.yml` uses `concurrency: { group: pages, cancel-in-progress: false }`. `nightly-update.yml` no longer deploys so no longer needs that group. Permissions split correctly: nightly needs `contents: write`, deploy needs `pages: write` + `id-token: write`.

### 2. Cron schedule

Change `"0 16 * * *"` → `"0 2 * * *"`. That's 3am BST in summer and 2am GMT in winter. GitHub Actions cron runs in UTC only, so a ±1h seasonal drift is unavoidable without ugly workarounds; 2am UTC picks the current-season-correct version (we're in BST right now).

### 3. Revalidate `in_transit` against current classification rules

Add a new pure function `revalidate_in_transit(db)` in `pipeline/vessels.py`:

```python
def revalidate_in_transit(db: dict) -> int:
    """Re-apply classify_region + should_keep_vessel to every in_transit block.
    Clears in_transit on records that no longer qualify, updates the stored
    region field on those that still do. Returns count of records cleared.
    """
```

Call it in the orchestrator right after `migrate_missing_in_transit`, before the AIS collection step. That way it runs on every pipeline run (including 0-message runs that short-circuit before `update_vessel_db`). One pass per run is enough — it's O(n) over a small dict.

This one-off repair the Indonesia ships on the next run, and self-heals any future classification-rule changes.

### 4. Hide the pipeline's starting (incomplete) month on the historical chart

In `src/components/HistoricalChart.tsx`, after computing `estimateMonths`, identify the earliest AIS-estimate month. If that month equals the current UTC month, skip it when pushing rows into `chartData`. Semantics: "the month I'm running in was already partially over when I started collecting, so don't plot a tiny misleading bar for it; I'll start showing months from the next one onward."

Once the next calendar month begins, the rule stops matching (earliest AIS-estimate is no longer equal to current), so the chart resumes showing the current month with its existing `MTD` label and dashed styling.

Consequence: the "Dashed = current month (to date)" legend item can be misleading when there's no dashed bar in view. Hide that legend item when no row in `chartData` has `source === "current_month"`.

## Affected files

- **Modify** `.github/workflows/nightly-update.yml` — strip deploy steps, change cron.
- **Create** `.github/workflows/deploy.yml` — push-triggered build + deploy.
- **Modify** `pipeline/vessels.py` — add `revalidate_in_transit`.
- **Modify** `pipeline/tests/test_vessels.py` — tests for the new function.
- **Modify** `pipeline/orchestrator.py` — call `revalidate_in_transit` after migration.
- **Modify** `src/components/HistoricalChart.tsx` — hide starting-month row, conditional legend entry.

## Non-goals

- No change to the AIS collector, destination parser, region coordinates, arrivals logic, or daily chart.
- No retroactive correction of historical monthly estimates — the April 2026 `monthly-estimates.json` entry still gets updated by the pipeline, it's just not rendered on the chart.
- No migration of the six Indonesian records by manual data surgery — `revalidate_in_transit` handles it on the next pipeline run, which will run in a few hours at the new cron time or on the next code push.

## Risk

- **Cron drift:** ±1 hour seasonally. Flagged above.
- **Deploy workflow concurrency:** if a code push lands during a nightly data commit's deploy run, GitHub's `concurrency.group: pages` with `cancel-in-progress: false` queues the second deploy. No data loss, minor delay.
- **Revalidate clearing too aggressively:** if `classify_region` ever returns `None` for a lat/lon inside any region box (shouldn't happen — the box list was designed so subscribed regions always classify), records would be cleared. Mitigation: tests cover the branch; region boxes are stable; `should_keep_vessel(None, ...)` always returns False which is the safe default.
