# Design: Approached-then-vanished → probable arrivals

**Date:** 2026-06-08
**Status:** Approved (design); pending implementation plan

## Problem

The monitor captures only ~half of Australia's monthly fuel imports. For May 2026
it recorded 2,482 ML of arrivals against an official benchmark of ~5,300 ML/month
(~47%). Diagnosis showed the dominant, *recoverable* leak is not vessels we never
saw — it is vessels we **tracked as laden and Australia-bound, then silently
dropped**. In the May window, 60 laden tankers were pruned from the in-transit
roster at the 14-day staleness mark (`reason: stale_prune_14d`) without ever being
matched to an arrival, carrying ~1,830 ML. Most went AIS-dark on approach to a
named port (Geraldton, Kwinana, Brisbane, Sydney…).

A vessel is counted as an import only if it is caught **both** in transit *and*
parked (speed < 1.0) inside a 5–8 km port geofence. Vessels that go dark on
approach or at anchorage leave their last fix outside the port circle, so neither
the live nor the silent-arrival detector fires, and they age out as "lost."

## Goal

Infer an arrival when a tracked vessel "approaches then vanishes," surfacing these
as a distinct **probable** tier (never silently merged into confirmed counts), so
the monthly number reflects cargo that almost certainly landed — honestly labelled.

### Non-goals

- Closing the residual gap from vessels **never tracked at all** (the genuine AIS
  coverage hole — free aisstream, terrestrial bias, 30-min nightly window). That
  needs better *collection*, not better inference, and is out of scope.
- Changing crude/product classification or cargo estimation.

## Expected impact (computed from current data)

Applying the rule + backfill to existing `lost-vessels.json`:

| May 2026 | Total | Crude | Product | Arrivals |
|---|---|---|---|---|
| Confirmed | 2,482 ML (47%) | 543 (62%) | 1,939 (44%) | 55 |
| + Probable | +942 ML | +313 | +630 | +35 |
| **Confirmed + probable** | **3,425 ML (65%)** | **856 (97%)** | **2,569 (58%)** | **90** |

> Figures are **as of the 2026-06-08 nightly data** (after the same-voyage backfill
> dedup — see Backfill). The probable total is not static: it grows as nightly
> lost-vessel data accrues (May ships that go dark in late May only hit the 14-day
> prune — and so become recoverable — in early June). A design-time projection
> against the 2026-06-01 snapshot put May at ~3,100 ML; a week of further data
> lifts it to ~3,425 ML. The backfill is idempotent, so each nightly run simply
> re-derives the current band.

Crude is near-complete; the residual gap is overwhelmingly *product* tankers
never tracked. The backfill also lifts April (+796 ML / 19 vessels), as cargoes
bucket into the month the vessel actually went dark, not the prune date.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Confidence model | Separate **probable** tier; dashboard shows confirmed + a probable band. Reversible. |
| Proximity gate | **150 km** of a port (declared-destination port, else nearest in range), **tiered**: ≤50 km counts on proximity alone; 50–150 km also requires the anchored-or-closing check. |
| Firing trigger | **Early + reversible** — fire after ~3–5 days dark; withdraw if the vessel reappears in transit. |
| Backfill | **Yes** — idempotent one-shot over `lost-vessels.json`. |
| Dashboard | **In scope** — surface the probable band in `HistoricalChart`. |

## Architecture

A new detector, `detect_probable_arrivals`, mirroring the existing
`detect_silent_arrivals` in `pipeline/arrivals.py`, wired into the orchestrator
after the confirmed-arrival passes and before the prune. Probable arrivals are
tagged rows in `arrivals.json`; monthly totals already rebuild from that file
(`rebucket_monthly_from_arrivals`), so reversal, upgrade, and month-bucketing are
row operations.

### State machine

A trip moves: `in_transit` → `probable_arrived` → one of {`confirmed`, `reversed`,
finalized-as-probable}. Implemented with the existing `in_transit` block plus one
new record marker, `record["probable_arrival"] = {port, since}`.

While `probable_arrived`: the `in_transit` block is **retained** (needed to detect
reappearance), but the record is **excluded from all "en route" sums** — a probable
arrival is no longer en route.

### Detection pass — `detect_probable_arrivals(vessel_db, ports, current_snapshot, existing_arrivals, now)`

A record qualifies when **all** hold:

1. has an `in_transit` block; not already `probable_arrival`; no confirmed row for this `(imo, port)`
2. **laden** — `in_transit.is_ballast == False` (excludes post-discharge departures, which ride in ballast)
3. `departed_au_since_arrival == True` (fresh international leg, not a coastal hop)
4. **dark** — `now − in_transit.last_position_update ≥ DARK_DAYS` (≈4) and absent from the current snapshot
5. **near a port** — last position within `APPROACH_KM` (150) of a port **P**; P = declared-destination port if `destination_parsed` maps to a specific port, else nearest port within range
6. **approaching (tiered by distance to P):**
   - **inner band** — within `INNER_KM` (50) of P: **no further check.** A laden vessel that goes dark within 50 km of a berth has effectively nowhere else to be; this covers ~95% of recoverable cargo and avoids trusting a single, sparse, stale speed/course reading (we observe only ~30 min/day, so the stored kinematics are one noisy instantaneous fix, not a track).
   - **outer band** — 50–150 km from P: require `in_transit.speed < SLOW_KN` (≈1.5; anchored/slowing) **OR** course within ±`HEADING_TOL` (≈75°) of the bearing from the last position to P. The kinematic guardrail is applied only here, where "near a port" is genuinely ambiguous (a vessel could be transiting past).

Effect:

- Append a row to `arrivals.json`:
  `{imo, name, port: P, timestamp: in_transit.last_position_update, ship_type, vessel_class, cargo_tonnes, cargo_litres, draught_missing, coastal: False, status: "probable"}`
  — `timestamp` is the **dark date** so the cargo buckets into the correct month.
- Set `record["probable_arrival"] = {port: P, since: now}`.

### Reversal — vessel reappears

When a record with `probable_arrival` gets a fresh ping in the current snapshot that
is **moving** (`speed ≥ SLOW_KN`) **and not** inside a port radius (i.e. genuinely
still at sea): remove its probable row (match `imo` + `status == "probable"`), clear
the marker, and rebuild `in_transit` from the fresh ping as normal. Handled where
fresh pings are already processed (`apply_departed_au_rules` / `update_vessel_db`).
If the fresh ping is parked inside a port radius, do nothing here — let the confirmed
pass upgrade it.

### Upgrade — probable → confirmed

When a confirmed arrival is detected (live or silent) for `(imo, P)` that already has
a probable row: the confirmed pass must not be blocked by the probable row. Relax the
`(imo, port)` dedupe so **only confirmed rows block** confirmation. When the confirmed
row is created, drop the matching probable row and clear `record["probable_arrival"]`.
Net: cargo moves from the probable bucket to the confirmed bucket — never both.

### Finalization — still dark at 14 days

`prune_stale_in_transit`: if the record has `probable_arrival` set, null `in_transit`
but **do not** log to `lost-vessels.json` (it is accounted as a probable arrival, not
lost). The probable row stands as our best estimate. Records without the marker prune
exactly as today.

### Backfill (idempotent, one-shot)

A migration step (pattern of the existing `migrate_*` functions) that reprocesses
`lost-vessels.json` events into probable arrivals:

- For each event with `is_ballast == False` whose `(last_lat, last_lon)` is within
  **`INNER_KM` (50 km)** of a port P, append a probable row with `timestamp =
  last_position_update`, `port = P`, cargo from the event. Mark the event recovered
  (e.g. `recovered_as: "probable"`) so re-runs are no-ops.
- **Backfill uses the inner band only.** The outer-band kinematic guardrail (step 6)
  cannot be applied retroactively — lost records store no speed/course — and a
  backfilled false positive is *not* self-correcting (reversal only fires on vessels
  that reappear in a live snapshot; historical lost vessels never will). So we recover
  only the unambiguous inner-band vessels and leave outer-band events as lost. This
  costs little: ~95% of recoverable cargo is within 50 km. Document this asymmetry in code.
- **Same-voyage dedup (`DEDUP_WINDOW_DAYS = 5`).** Backfill attributes to the *nearest*
  port, but confirmed arrivals use the *declared* port — so a vessel that berthed at Q
  (confirmed) whose last dark fix was nearest an adjacent port P would otherwise get a
  duplicate probable at P for the same voyage. Suppress a lost event when the same IMO
  already has a confirmed arrival within 5 days (stamp `recovered_as:
  "duplicate_of_confirmed"`). Genuine repeat voyages (>5 days apart, same or different
  port) are still recovered. This removed ~4 May duplicates (3,181 → 3,096 ML).

### Aggregation

- `rebucket_monthly_from_arrivals`: split rows by `status`. Confirmed rows feed the
  existing `arrived_*` fields (unchanged meaning, back-compatible). Probable rows feed
  **new** fields: `probable_crude_litres`, `probable_product_litres`,
  `probable_crude_tonnes`, `probable_product_tonnes`, `probable_count`. Rows missing
  `status` are treated as confirmed (back-compat for existing data).
- En-route sums (`update_monthly_estimates`, `update_daily_estimates`): skip records
  with `probable_arrival` set.
- **Frontend roster (`src/lib/data.ts` `rosterToSnapshot`)**: also skip
  `probable_arrival`-marked records. A probable vessel keeps its `in_transit` block (for
  reversal), so without this guard it would show as "en route" on the map/headline while
  being excluded from the en-route *totals* — an inconsistency. `VesselDbRecord` gains an
  optional `probable_arrival` field.

### Dashboard

- `src/lib/types.ts`: add the five `probable_*` fields to `MonthEstimate`.
- `src/components/HistoricalChart.tsx`: for AIS months, keep the confirmed `arrived_*`
  bars exactly as today and **stack a probable segment on top** (`probable_crude` +
  `probable_product`), drawn distinctly (outline-only / lower opacity than the
  confirmed fill) so the bar reads "confirmed solid, lighter cap to confirmed+probable."
  Add a legend entry ("Lighter cap = probable arrivals, AIS-inferred") and the split in
  the tooltip. Government and no-data rendering unchanged.

## Tunable constants (module top, `arrivals.py`)

| Constant | Value | Meaning |
|---|---|---|
| `DARK_DAYS` | 4 | days AIS-dark before a probable arrival fires |
| `INNER_KM` | 50 | within this ⇒ proximity alone counts (no kinematic check); also the backfill gate |
| `APPROACH_KM` | 150 | outer max distance from a port for "approached" |
| `SLOW_KN` | 1.5 | at/below ⇒ treated as anchored/slowing (outer band only) |
| `HEADING_TOL` | 75° | max course deviation from bearing-to-port for "closing" (outer band only) |

## Testing (TDD, `pipeline/tests`)

- `detect_probable_arrivals`: each trigger condition independently (laden vs ballast;
  inner band counts with *no* kinematic check, even heading-away; outer band requires
  stationary or closing-heading and rejects heading-away; `INNER_KM`/`APPROACH_KM`
  boundary cases; declared-port vs nearest-port attribution; dark-threshold boundary).
- Reversal: probable vessel reappears moving offshore ⇒ row removed, marker cleared.
- Upgrade: probable then confirmed at berth ⇒ single confirmed row, cargo not double
  counted.
- Finalize: probable still dark at 14 days ⇒ pruned, not logged lost, row retained.
- `rebucket_monthly_from_arrivals`: confirmed/probable split; statusless rows counted
  as confirmed.
- En-route sums exclude `probable_arrival` records.
- Backfill: idempotency (re-run is a no-op); inner-band (50 km) gate only; month
  bucketing by `last_position_update`.

## Out of scope / follow-ups

- Improving raw AIS collection coverage (the never-tracked product gap).
- Tuning thresholds against observed false positives once live.
