# Daily En-Route Chart Design

**Date:** 2026-04-14
**Status:** Proposed

## Problem

The dashboard currently shows a monthly bar chart of fuel imports (government data + AIS-estimated current month). There's no visibility into the short-term shape of the fleet currently en route — whether the total volume is trending up or down week-over-week, or whether a big crude shipment just arrived and dropped the total overnight. Users ask: *"What's changed in the last few days?"* and the dashboard can't answer.

## Goal

Add a second chart below the monthly one showing the estimated volume in transit to Australia for each of the last 30 days, split into crude vs product as a stacked area. Data is captured once per day at the end of the pipeline run (from the in-transit roster) and accumulates forward.

## Design

### 1. Data layer

A new file `data/daily-estimates.json` keyed by UTC date string (`YYYY-MM-DD`):

```json
{
  "days": {
    "2026-04-14": {
      "en_route_crude_litres": 320000000,
      "en_route_product_litres": 180000000,
      "captured_at": "2026-04-14T12:30:00Z"
    },
    "2026-04-15": { ... }
  }
}
```

- All historical days are kept indefinitely (a year of daily entries is ~40 KB — trivial).
- The chart uses a **rolling 30-calendar-day window ending today** (UTC), so gaps where the pipeline didn't run are visible rather than silently collapsed. If we've only been live for 10 days, the chart shows 10 data points against a 30-day axis; if the workflow skipped 3 days, those slots remain gaps.
- Same-day reruns overwrite: if the workflow runs twice on the same UTC date, the second run replaces the first's entry. This is fine — the last run of the day is the most representative.

### 2. Pipeline

A new pure-function module `pipeline/daily_estimates.py` with:

```python
def update_daily_estimates(daily: dict, vessel_db: dict, now: datetime) -> dict:
    """Write today's en-route totals into daily["days"][YYYY-MM-DD].

    Sums cargo_litres from each record's in_transit block, skipping
    ballast and arrived (in_transit=None) vessels. Overwrites any
    prior entry for today's date.
    """
```

Signature mirrors `update_monthly_estimates`. Returns the updated `daily` dict for the caller to persist.

The orchestrator gains a new Step 5 between "Update monthly estimates" and "Check petroleum statistics":

```
Step 5: Updating daily estimates...
  Saved data/daily-estimates.json
```

The existing "Check petroleum statistics" step becomes Step 6. The "Updating monthly estimates" step stays Step 4.

### 3. Frontend

**Types** (`src/lib/types.ts`):

```typescript
export interface DailyEstimate {
  en_route_crude_litres: number;
  en_route_product_litres: number;
  captured_at: string;
}

export interface DailyEstimates {
  days: Record<string, DailyEstimate>;
}
```

`DashboardData` gains a `dailyEstimates: DailyEstimates` field.

**Data layer** (`src/lib/data.ts`): `loadDashboardData` reads `daily-estimates.json` with fallback `{days: {}}` and returns it on the data object.

**New component** `src/components/DailyEnRouteChart.tsx`:
- Recharts stacked `AreaChart` (library already used elsewhere).
- Two series: **crude** (top) and **product** (bottom), same palette as the monthly chart (`FUEL_COLORS.crude` and `FUEL_COLORS.diesel` as the representative product tone).
- Height ~300px (slightly shorter than the monthly chart so it doesn't dominate).
- X-axis: the rolling 30-calendar-day window ending today (UTC). Every day in the window gets a slot; slots with no data render as gaps. Tick format `DD MMM` (e.g. `14 Apr`), `interval="preserveStartEnd"` to avoid label crowding.
- Y-axis: megalitres, label `Megalitres en route`.
- Gaps for missing days (`connectNulls={false}`) — honest about missing data rather than interpolating.
- Tooltip shows `DD MMM YY`, crude ML, product ML, total ML.

**Placement** (`src/app/page.tsx`): below the existing `<HistoricalChart>` block, a new section:

```jsx
<div className="mb-6">
  <p className="text-[10px] uppercase tracking-label text-label mb-2">
    Daily volume en route (last 30 days)
  </p>
  <DailyEnRouteChart dailyEstimates={data.dailyEstimates} />
</div>
```

### 4. Backfill

None. The chart starts populating from the first pipeline run after deploy. For the first week the chart looks sparse; over time it fills in. Acceptable given the PoC scope.

### 5. Edge cases

- **First deploy:** `daily-estimates.json` absent → pipeline writes `{"days": {<today>: {...}}}`; frontend fallback is `{days: {}}` so it renders empty gracefully if the file hasn't landed yet.
- **Fewer than 30 days of data:** chart shows what we have. No padding, no "insufficient data" banner.
- **Gap days (workflow failed or skipped):** visible gap in the series. Users can see when data is missing.
- **Ballast / arrived vessels:** excluded from both crude and product totals (matches monthly-en-route logic).
- **Clock skew between runs:** `captured_at` is stored for debugging but the chart keys on the UTC date string, so small timezone drift is a non-issue.

## Affected files

- **Create** `pipeline/daily_estimates.py` — `update_daily_estimates()`
- **Create** `pipeline/tests/test_daily_estimates.py` — unit tests
- **Modify** `pipeline/orchestrator.py` — add Step 5, load/save daily file
- **Modify** `src/lib/types.ts` — `DailyEstimate`, `DailyEstimates`, extend `DashboardData`
- **Modify** `src/lib/data.ts` — read `daily-estimates.json`, return on data object
- **Create** `src/components/DailyEnRouteChart.tsx` — the chart component
- **Modify** `src/app/page.tsx` — mount the chart below the monthly one

## Non-goals

- No backfill from existing snapshots or monthly aggregates — start fresh.
- No retention / pruning of old entries — file stays small even at multi-year scale.
- No granularity finer than daily (no hourly/intra-day chart).
- No breakdown by region, port, or vessel class — crude vs product only, matching the feedback.
- No change to the existing monthly chart.
- No new summary statistic (e.g., week-over-week delta) — chart-only.

## Risk

- **Missing-day noise:** if the workflow fails often, the chart will have lots of gaps. Pipeline reliability is a separate concern; if it becomes painful we can add forward-fill later.
- **Chart visual clutter with long runs:** at 30 day-points on a ~900px-wide chart the ticks are readable; no concern at PoC scale.
- **Day boundary ambiguity:** UTC keys mean a workflow run at 23:50 UTC on the 14th and another at 00:10 UTC on the 15th produce two entries, not one. This is correct — they're different days — but worth noting for anyone debugging why two entries look "close together" in time.
