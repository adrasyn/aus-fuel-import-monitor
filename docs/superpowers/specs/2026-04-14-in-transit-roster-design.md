# In-Transit Roster Design

**Date:** 2026-04-14
**Status:** Proposed

## Problem

The dashboard's "currently en route" stats are derived from `data/snapshot.json`, which holds only vessels pinged during the most recent ~30-minute AISStream collection window. A tanker that goes out of terrestrial AIS range overnight (mid-Pacific, mid-Indian Ocean) **disappears** from the stats until she's back in range — making the visible fleet jitter day-to-day, under-counting Australian fuel imports in transit, and breaking arrival detection (which today requires a vessel to be in **both** the current and previous snapshots to count).

This affects: (a) live "fleet en route" counts and volumes, (b) arrival detection accuracy, (c) the chart's en-route month-to-date estimate.

## Goal

Treat "currently in transit to Australia" as **persistent state** rather than "pinged today". A vessel stays in the in-transit roster from the first time we see her until she's either detected arriving at an Australian port, or has been silent for 14 days (the longest credible coverage gap on a cross-Pacific or cross-Indian-Ocean route).

## Design

### 1. Data model: extend `vessels.json`

The existing IMO-keyed database in `data/vessels.json` already tracks static vessel info (name, class, dimensions) and basic lifecycle markers (`first_seen`, `last_seen`, `arrival_count`). Add a new optional field `in_transit` per record. When present, the ship is currently on a trip; when `null` or absent, she's arrived or been pruned.

```json
{
  "9876543": {
    "name": "GARDEN STATE",
    "vessel_class": "Aframax",
    "dwt": 80000,
    "length": 250,
    "beam": 44,
    "ship_type": "crude",
    "first_seen": "2026-03-21T...",
    "last_seen": "2026-04-14T12:30:00Z",
    "arrival_count": 2,
    "in_transit": {
      "lat": -25.5,
      "lon": 130.2,
      "speed": 12.4,
      "course": 180.0,
      "heading": 180.0,
      "draught": 14.5,
      "destination": "AU GLT",
      "destination_parsed": "Gladstone",
      "region": "AU_APPROACH",
      "cargo_litres": 95000000,
      "cargo_tonnes": 80000,
      "load_factor": 0.95,
      "is_ballast": false,
      "draught_missing": false,
      "last_position_update": "2026-04-14T12:30:00Z"
    }
  }
}
```

`last_position_update` is the timestamp of the most recent successful ping that updated `in_transit`. A ship not pinged in the latest run keeps her old `in_transit` block and her `last_position_update` does **not** advance.

### 2. Pipeline orchestration

The collector and most pipeline steps stay as-is; the changes are concentrated in the vessels-database update step and arrival detection.

| Step | Old behaviour | New behaviour |
|---|---|---|
| Collect AIS | → `snapshot.json` | Unchanged. Snapshot stays as the per-run audit + the input to roster updates. |
| Update vessel DB | Refresh static fields only | (a) For each vessel in current snapshot: refresh static fields **and** rebuild her `in_transit` block from the snapshot row. (b) For each existing roster vessel **not** in current snapshot but with `in_transit` set: leave her `in_transit` untouched (she stays "in transit" with stale position). (c) Prune: any vessel whose `in_transit.last_position_update` is older than **14 days** has `in_transit` set to `null`. |
| Detect arrivals | Vessel must be in current AND previous snapshot, stationary, inside port radius | Vessel must be in current snapshot (still need a fresh ping for lat/lon/speed), stationary, inside port radius, **and** in the roster's `in_transit` set (replaces the "previous snapshot" check). Handles ships that went silent the day before docking. |
| On arrival | `arrival_count++` | `arrival_count++` **and** set `in_transit = null` (ship has arrived). |
| Update monthly estimates | "en route" summed from snapshot | "en route" summed from roster's `in_transit` records (so out-of-range ships still count toward this month's en-route volume). Arrived volumes still added from `new_arrivals` as today. |

`snapshot.json` keeps its current shape and contents — useful for debugging, audit, and any external consumer; nothing reads from it that the roster doesn't also know.

### 3. Frontend

`src/lib/data.ts`:
- Read the in-transit list from `vessels.json` (filter to records where `in_transit` is not null), flatten the nested `in_transit` block onto a `Vessel` shape compatible with the existing components.
- The `snapshot.json` read can be dropped from `loadDashboardData` (no other component uses it).

`src/components/VesselMap.tsx`:
- For each vessel marker, compute `staleHours = (now - last_position_update) / 3600_000`.
- If `staleHours > 24`, render the marker with `opacity-50` (or equivalent dim treatment) and add a tooltip line "Last seen Xd ago" (or "Xh ago" if <48h).

`src/components/VesselTable.tsx`:
- No "last seen" indicator in this iteration. Keep the table dense. Map markers and the AIS-range disclaimer already convey staleness; we can add a column later if it turns out to read poorly without one.

StatBar counts and sums use the full in-transit roster including stale entries. The "AIS terrestrial range" disclaimer added in UI batch 1 already explains why some entries may be old.

### 4. Type definitions

`src/lib/types.ts`:
- Add `last_position_update: string` to `Vessel` (or whatever the current type name is).
- Optionally add a derived `staleHours: number` if the data layer pre-computes it; otherwise components compute on the fly.

`pipeline/vessels.py`:
- The `update_vessel_db` function gets a new responsibility: building/updating/pruning `in_transit`. Signature stays compatible (it already takes the snapshot vessel list); the test surface grows.

### 5. Migration & edge cases

- **First run after deploy:** the existing `vessels.json` records have no `in_transit` field. Pipeline treats absent = `null`. After one run, every actively pinged ship gets her `in_transit` populated. Pre-existing arrived/inactive ships remain without `in_transit` (correct — they're not in transit).
- **Ship lost >14 days, then reappears:** roster pruned her; she comes back in as a fresh trip with a new `in_transit` block.
- **Arrival of a ship not in the roster** (e.g., very first ping happens to be at a port): arrival still added to `arrivals.json` and to monthly stats; no roster mutation needed (nothing to clear).
- **Snapshot consumers:** `snapshot.json` continues to be written every run with current-ping vessels. No consumer reads it after this change, but it stays for debugging/audit.

## Affected files

- `pipeline/vessels.py` — extended responsibilities (build/update/prune `in_transit`)
- `pipeline/arrivals.py` — accepts roster instead of `previous_snapshot`; clears `in_transit` on arrival
- `pipeline/orchestrator.py` — wiring change (roster passed to arrivals; monthly estimates use roster)
- `pipeline/tests/test_vessels.py` — extended; new tests for `in_transit` lifecycle and 14-day prune
- `pipeline/tests/test_arrivals.py` — updated for the new "was in roster" check
- `src/lib/data.ts` — read `vessels.json` instead of `snapshot.json` for the in-transit list
- `src/lib/types.ts` — add `last_position_update` (and possibly `staleHours`)
- `src/components/VesselMap.tsx` — dim stale markers + tooltip

## Non-goals

- No change to AIS collection, region classification, destination parsing, cargo estimation, or petroleum-stats ingestion.
- No change to `snapshot.json` shape.
- No backfill of historical data — the roster starts populating from the next pipeline run after deploy.
- No new staleness configuration UI — the 14-day cut-off is a hard-coded constant in the pipeline.
- No multi-trip arrival deduplication beyond what already exists (`arrived_imos` uses `(imo, port)` tuples — pre-existing behaviour, out of scope).

## Risk

- **Stale data shown as live:** mitigated by the dim marker + tooltip + the existing AIS-range disclaimer. Users can see at a glance which positions are old.
- **Pruning too aggressively:** 14 days might cut off a particularly slow tanker (rare). Easy to tune later if observed.
- **Roster grows unbounded:** in practice fleet is small (~20-50 vessels in transit at any time, ~hundreds across a year). No concern at PoC scale; trivial JSON file.
- **Arrival detection regression:** the new "was in roster" check is strictly **more permissive** than "was in previous snapshot" (covers a superset). No vessel that would have been detected before gets missed.
