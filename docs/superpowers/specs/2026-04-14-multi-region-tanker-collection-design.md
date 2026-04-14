# Multi-Region Tanker Collection Design

**Date:** 2026-04-14
**Status:** Proposed

## Problem

The current AIS collector subscribes to a single bounding box covering southern Australian approaches (`[-50, 90] → [-5, 170]`) and keeps any tanker (AIS type 80-89) that appears in it, regardless of destination. This captures:

- Tankers arriving at Australian ports ✓
- Tankers merely passing through (e.g., Singapore-bound) — noise
- It misses Australia-bound tankers that are still far from the box (e.g., loading in the Persian Gulf or crossing the Pacific from US Gulf Coast)

AISStream filters server-side by bounding box, so there's no way to catch "any AU-bound tanker globally" from a single subscription.

## Goal

Capture a vessel if **either** condition is true:
- It's inside the Australian approach box (as today), **OR**
- It's inside a known origin region **and** its declared AIS destination parses as Australian

## Design

### 1. Region definitions

Replace the single `AU_BOUNDING_BOX` constant with a named list of regions, each with its own retention rule.

| Region | Approximate box (lat_min, lon_min → lat_max, lon_max) | Rule |
|---|---|---|
| `AU_APPROACH` | `-50, 90 → -5, 170` (current) | keep all tankers |
| `SE_ASIA` | `-5, 95 → 10, 120` (Singapore, Malaysia, Indonesian straits) | keep only AU-destined |
| `CHINA` | `18, 108 → 41, 125` (east-coast export ports) | keep only AU-destined |
| `KOREA_JAPAN` | `30, 125 → 45, 145` | keep only AU-destined |
| `INDIA` | `5, 65 → 25, 90` | keep only AU-destined |
| `MIDDLE_EAST` | `10, 40 → 30, 80` (Persian Gulf + Arabian Sea) | keep only AU-destined |
| `US_GULF` | `18, -98 → 31, -80` (Gulf of Mexico) | keep only AU-destined |
| `US_WEST_COAST` | `25, -125 → 50, -115` | keep only AU-destined |

Coordinates are starting estimates and easy to tune once we see real traffic.

### 2. Subscription

AISStream's `BoundingBoxes` accepts a list of boxes in one subscription. Pass all of them at once. The server sends messages for any vessel in any box; the client can't tell which box matched.

### 3. Client-side classification and filtering

After collection, post-process each vessel:

```python
def classify_region(lat: float, lon: float) -> str | None:
    for name, ((lat_min, lon_min), (lat_max, lon_max)) in REGIONS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None  # shouldn't happen — vessel was outside every subscribed box
```

Retention rule (applied in the existing filter loop):

```python
region = classify_region(vessel["lat"], vessel["lon"])
if region == "AU_APPROACH":
    keep
elif region is not None and vessel["destination_parsed"] is not None:
    keep
else:
    drop
```

If a vessel straddles overlapping boxes, `classify_region` returns the first match — ordering doesn't matter because the retention decision for origin boxes is the same (destination-gated).

Vessels with blank/unparseable destinations outside `AU_APPROACH` are dropped. This is a known limitation — captains often leave destination blank or stale. No reliable client-side inference at the collection stage.

### 4. Destination parser

`pipeline/destinations.py` already returns a non-None value for AU-bound strings and None otherwise. No changes needed. Regex/pattern tuning can happen later if false negatives are observed.

### 5. Storage on the vessel record

Add a `region` field to the vessel dict so downstream consumers can see origin context. Useful for the dashboard (e.g., "in transit from Middle East").

## Affected files

- `pipeline/collector.py` — region constants, subscription update, post-process classification, retention logic, add `region` field to vessel record
- `pipeline/tests/test_*.py` — new test for `classify_region`; update existing collector tests if any assert on bounding-box count

## Non-goals

- No change to destination parsing logic
- No change to cargo estimation, arrivals detection, or monthly estimates
- No attempt to infer destination for vessels with blank AIS destination
- No change to the dashboard (separate task, once data shape stabilises)

## Risk

- **More bandwidth.** Origin regions carry heavy non-tanker traffic; we filter by type 80-89 client-side. Message volume will go up but cost depends on AISStream's billing model. Monitor the first couple of runs.
- **Destination parser coverage.** If the parser misses common AU variants, we'll under-capture. Easy to tune — add patterns as we see real data.
- **Box boundaries.** Initial coordinates are estimates. First run will show whether we're catching the right ports.
