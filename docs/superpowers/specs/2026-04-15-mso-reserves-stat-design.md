# DCCEEW MSO Reserves Stat Design

**Date:** 2026-04-15
**Status:** Proposed

## Problem

The StatBar currently shows one "Days reserve (govt)" number sourced from the APS (Australian Petroleum Statistics) Excel feed, which reports stocks-on-hand expressed as days of consumption. Two issues:

1. **Stale.** APS publishes monthly and lags 2–3 months — as of 2026-04-15 we only have data through 2026-01.
2. **Single aggregate.** Users care about the breakdown by fuel type (petrol, kerosene, diesel) that the DCCEEW Minimum Stockholding Obligation page presents, not a single combined number.

The DCCEEW MSO statistics page at [https://www.dcceew.gov.au/energy/security/australias-fuel-security/minimum-stockholding-obligation/statistics](https://www.dcceew.gov.au/energy/security/australias-fuel-security/minimum-stockholding-obligation/statistics) is updated weekly and reports the three fuel types separately. The data is behind a PowerBI embed, which may or may not be scrapable without a headless browser.

## Goal

Replace the single APS-sourced reserve stat with three DCCEEW-sourced per-fuel stats (Petrol / Kerosene / Diesel), plus a small "as of" caption. Source the values via a hand-maintained JSON file for now; defer the scrape work to a follow-up.

## Design

### 1. Data file

New file at `data/mso-reserves.json`:

```json
{
  "source": "DCCEEW Minimum Stockholding Obligation",
  "source_url": "https://www.dcceew.gov.au/energy/security/australias-fuel-security/minimum-stockholding-obligation/statistics",
  "as_of": "2026-04-07",
  "fuels": [
    { "key": "petrol",   "label": "Petrol",   "days": 38 },
    { "key": "kerosene", "label": "Kerosene", "days": 28 },
    { "key": "diesel",   "label": "Diesel",   "days": 31 }
  ]
}
```

- `as_of` is an ISO date string (`YYYY-MM-DD`) for the date DCCEEW last updated the dashboard, not the date the JSON was edited.
- `fuels` is an array (not a map) so rendering order is explicit and deterministic.
- The initial commit uses the values the user captured on 2026-04-15: Petrol 38, Kerosene 28, Diesel 31, as of 7 April 2026.

### 2. Types

`src/lib/types.ts` gains:

```ts
export interface MsoReserveFuel {
  key: string;
  label: string;
  days: number;
}

export interface MsoReserve {
  source: string;
  source_url: string;
  as_of: string;   // YYYY-MM-DD
  fuels: MsoReserveFuel[];
}
```

`DashboardData` gains an optional `msoReserve: MsoReserve | null` field.

### 3. Data loading

`src/lib/data.ts` reads `data/mso-reserves.json` alongside the other data files and populates `msoReserve`. If the file is missing or fails to parse, `msoReserve` is `null` — not an error.

### 4. StatBar change

`src/components/StatBar.tsx`:

- **Remove** the existing single `Days reserve (govt)` stat (the one reading `latestConsumptionCover.total_days`). The `ConsumptionRecord` type and `consumption_cover` parsing stay in place — other future features may want them — but they're no longer rendered.
- **Add** three stats in that slot, one per fuel in `msoReserve.fuels`. Stat value is the number (e.g. `38`), label is `<Fuel> days` (e.g. `Petrol days`). Same `<Stat>` component used by the other stats for visual consistency.
- **Add** a caption line directly below the stat row: `MSO reserve · as of 7 Apr 2026`, rendered as a link to `source_url`. The date is formatted from `as_of` as `d MMM yyyy` (e.g. `2026-04-07` → `7 Apr 2026`) using `Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric" })`. Matches the small-gray aesthetic of the existing AIS disclaimer paragraph.
- If `msoReserve` is `null`, skip both the three stats and the caption — render nothing in that slot. The page still works.

Stat count goes from 5 → 7 in the headline row; the existing `flex-wrap gap-x-8 gap-y-4` handles the wider layout on desktop and wraps gracefully on mobile.

### 5. Page wiring

`src/app/page.tsx` passes `data.msoReserve` to `<StatBar>` as a new prop. `latestConsumptionCover` prop is removed (StatBar no longer uses it).

### 6. Update workflow

To refresh weekly, the user edits `data/mso-reserves.json` — updates `as_of` + the three `days` values — and commits. The push triggers `deploy.yml`, which rebuilds the static site in ~2 min. No pipeline involvement.

## Out of scope

- **Scraping the PowerBI embed.** Captured as a follow-up in `project_todo_next_session.md`. If/when the scrape is feasible, it writes the same `mso-reserves.json` file shape and this UI doesn't change.
- **Historical time-series of MSO values.** Single current snapshot only. If we later want a trend chart, that's a separate feature.
- **Retaining the APS `total_days` stat alongside DCCEEW.** Dropped — user-validated via design review.
- **Removing APS consumption-cover parsing from the pipeline.** The parser stays; only the display is removed. Future work may reintroduce it or use it elsewhere.

## Testing

- No new pipeline logic, so no new pytest — but the existing 135-test suite runs to confirm no regressions.
- Manual smoke checks after `npm run build`:
  - Page renders with three MSO stats and caption when `mso-reserves.json` is present.
  - Page renders without the MSO slot when `mso-reserves.json` is absent or malformed (no crash).
- Existing build + TypeScript checks cover the type-level changes.

## File-level change summary

| File | Change |
|------|--------|
| `data/mso-reserves.json` | NEW. Seeded with 2026-04-07 values. |
| `src/lib/types.ts` | Add `MsoReserveFuel`, `MsoReserve`, extend `DashboardData`. |
| `src/lib/data.ts` | Load `mso-reserves.json` into `DashboardData`. |
| `src/components/StatBar.tsx` | Swap single APS stat for three DCCEEW stats + caption. Drop `latestConsumptionCover` prop. |
| `src/app/page.tsx` | Pass `msoReserve` prop, drop `latestConsumptionCover`. |
