# Multi-Region Tanker Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand AIS collection from a single Australian-approach bounding box to a union of regional boxes, retaining every tanker in the AU approach zone plus AU-destined tankers in known origin regions (Middle East, US Gulf, US West Coast, China, India, Korea/Japan, SE Asia, Philippines).

**Architecture:** Introduce a new pure module `pipeline/regions.py` holding the region dictionary and two small functions: `classify_region(lat, lon)` returning the matching region name (or None), and `should_keep_vessel(region, destination_parsed)` returning the retention decision. `pipeline/collector.py` imports these and replaces its single-box constant with the regions list; vessels are tagged with a `region` field in the output.

**Tech Stack:** Python 3.12, `websockets`, `pytest`. Runs headless in GitHub Actions nightly.

---

## File Structure

- **Create** `pipeline/regions.py` — `REGIONS` dict, `classify_region()`, `should_keep_vessel()`, `bounding_boxes_for_subscription()`
- **Create** `pipeline/tests/test_regions.py` — unit tests for the three functions
- **Modify** `pipeline/collector.py` — remove `AU_BOUNDING_BOX`, import from `regions`, update subscription call, add `region` field to vessel records, replace retention branch

The existing `pipeline/destinations.py` parser is unchanged.

---

## Task 1: Create `pipeline/regions.py` with `REGIONS` and `classify_region()`

**Files:**
- Create: `pipeline/regions.py`
- Create: `pipeline/tests/test_regions.py`

- [ ] **Step 1: Write the failing test**

Create `pipeline/tests/test_regions.py`:

```python
"""Tests for pipeline.regions."""

from pipeline.regions import classify_region


def test_classify_region_in_au_approach():
    # Off southern WA coast
    assert classify_region(-32.0, 115.0) == "AU_APPROACH"


def test_classify_region_in_middle_east():
    # Strait of Hormuz area
    assert classify_region(26.0, 56.0) == "MIDDLE_EAST"


def test_classify_region_in_us_gulf():
    # Off Houston
    assert classify_region(28.0, -94.0) == "US_GULF"


def test_classify_region_in_us_west_coast():
    # Off Los Angeles
    assert classify_region(33.0, -120.0) == "US_WEST_COAST"


def test_classify_region_in_china():
    # Off Shanghai
    assert classify_region(31.0, 122.0) == "CHINA"


def test_classify_region_in_korea_japan():
    # Tokyo Bay area
    assert classify_region(35.0, 140.0) == "KOREA_JAPAN"


def test_classify_region_in_india():
    # Off Mumbai
    assert classify_region(19.0, 72.0) == "INDIA"


def test_classify_region_in_se_asia():
    # Off Singapore
    assert classify_region(1.3, 103.8) == "SE_ASIA"


def test_classify_region_in_philippines():
    # Off Manila Bay
    assert classify_region(14.5, 120.9) == "PHILIPPINES"


def test_classify_region_outside_all_boxes():
    # Mid-Atlantic, no subscribed box
    assert classify_region(0.0, -30.0) is None


def test_classify_region_boundary_inclusive():
    # Exact lat_min / lon_min of AU_APPROACH is considered inside
    assert classify_region(-50.0, 90.0) == "AU_APPROACH"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: `ModuleNotFoundError: No module named 'pipeline.regions'`

- [ ] **Step 3: Write minimal implementation**

Create `pipeline/regions.py`:

```python
"""Named geographic regions for AIS collection and their retention rules.

Each region is a ((lat_min, lon_min), (lat_max, lon_max)) box. Vessels
inside AU_APPROACH are kept unconditionally; vessels inside any other
region are kept only if their destination parses as Australian.
"""

from __future__ import annotations

REGIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "AU_APPROACH":   ((-50.0,   90.0), ( -5.0,  170.0)),
    "SE_ASIA":       (( -5.0,   95.0), ( 10.0,  120.0)),
    "PHILIPPINES":   ((  5.0,  117.0), ( 20.0,  127.0)),
    "CHINA":         (( 18.0,  108.0), ( 41.0,  125.0)),
    "KOREA_JAPAN":   (( 30.0,  125.0), ( 45.0,  145.0)),
    "INDIA":         ((  5.0,   65.0), ( 25.0,   90.0)),
    "MIDDLE_EAST":   (( 10.0,   40.0), ( 30.0,   80.0)),
    "US_GULF":       (( 18.0,  -98.0), ( 31.0,  -80.0)),
    "US_WEST_COAST": (( 25.0, -125.0), ( 50.0, -115.0)),
}


def classify_region(lat: float, lon: float) -> str | None:
    for name, ((lat_min, lon_min), (lat_max, lon_max)) in REGIONS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py pipeline/tests/test_regions.py
git commit -m "feat: add regions module with classify_region()"
```

---

## Task 2: Add `should_keep_vessel()` retention rule

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `pipeline/tests/test_regions.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_regions.py`:

```python
from pipeline.regions import should_keep_vessel


def test_should_keep_au_approach_without_destination():
    assert should_keep_vessel("AU_APPROACH", None) is True


def test_should_keep_au_approach_with_destination():
    assert should_keep_vessel("AU_APPROACH", "Fremantle") is True


def test_should_keep_origin_region_with_au_destination():
    assert should_keep_vessel("MIDDLE_EAST", "Fremantle") is True


def test_should_keep_origin_region_with_au_unknown_port():
    assert should_keep_vessel("US_GULF", "Australia (port unknown)") is True


def test_drop_origin_region_without_destination():
    assert should_keep_vessel("US_GULF", None) is False


def test_drop_vessel_outside_all_regions():
    # region is None — vessel is not in any subscribed box
    assert should_keep_vessel(None, None) is False


def test_drop_vessel_outside_all_regions_even_with_destination():
    assert should_keep_vessel(None, "Fremantle") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: `ImportError: cannot import name 'should_keep_vessel' from 'pipeline.regions'`

- [ ] **Step 3: Implement `should_keep_vessel`**

Append to `pipeline/regions.py`:

```python
def should_keep_vessel(region: str | None, destination_parsed: str | None) -> bool:
    """Decide whether to keep a tanker based on its region and parsed destination.

    - AU_APPROACH: keep unconditionally (arrival zone).
    - Other known regions: keep only if destination parses as Australian.
    - Unknown region (outside every box): drop.
    """
    if region is None:
        return False
    if region == "AU_APPROACH":
        return True
    return destination_parsed is not None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: 18 passed (11 from Task 1 + 7 new)

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py pipeline/tests/test_regions.py
git commit -m "feat: add should_keep_vessel retention rule"
```

---

## Task 3: Add `bounding_boxes_for_subscription()` helper

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `pipeline/tests/test_regions.py`

- [ ] **Step 1: Write the failing test**

Append to `pipeline/tests/test_regions.py`:

```python
from pipeline.regions import REGIONS, bounding_boxes_for_subscription


def test_bounding_boxes_for_subscription_shape():
    boxes = bounding_boxes_for_subscription()

    # One box per region
    assert len(boxes) == len(REGIONS)

    # Each box is a 2-element list of [lat, lon] pairs (AISStream format)
    for box in boxes:
        assert len(box) == 2
        assert len(box[0]) == 2
        assert len(box[1]) == 2


def test_bounding_boxes_for_subscription_includes_au_approach():
    boxes = bounding_boxes_for_subscription()
    assert [[-50.0, 90.0], [-5.0, 170.0]] in boxes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: `ImportError: cannot import name 'bounding_boxes_for_subscription'`

- [ ] **Step 3: Implement helper**

Append to `pipeline/regions.py`:

```python
def bounding_boxes_for_subscription() -> list[list[list[float]]]:
    """Convert REGIONS to AISStream's BoundingBoxes wire format.

    AISStream expects: [[[lat_min, lon_min], [lat_max, lon_max]], ...]
    """
    return [
        [[lat_min, lon_min], [lat_max, lon_max]]
        for (lat_min, lon_min), (lat_max, lon_max) in REGIONS.values()
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest pipeline/tests/test_regions.py -v`
Expected: 20 passed (18 + 2 new)

- [ ] **Step 5: Commit**

```bash
git add pipeline/regions.py pipeline/tests/test_regions.py
git commit -m "feat: add bounding_boxes_for_subscription helper"
```

---

## Task 4: Wire `collector.py` to use the regions module

**Files:**
- Modify: `pipeline/collector.py`

- [ ] **Step 1: Read the current collector to confirm the lines being changed**

Read `pipeline/collector.py` in full so you see the current `AU_BOUNDING_BOX` constant (lines 16-20), the subscription dict (lines 40-44), the initial vessel record (lines 69-87), and the post-processing filter (lines 122-147).

- [ ] **Step 2: Replace imports and remove `AU_BOUNDING_BOX`**

At the top of `pipeline/collector.py`, replace:

```python
from pipeline.cargo import estimate_cargo
from pipeline.destinations import parse_destination

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Bounding box covering approaches to Australia + SE Asia shipping lanes
# AISStream format: [[lat_min, lon_min], [lat_max, lon_max]]
AU_BOUNDING_BOX = [
    [[-50.0, 90.0], [-5.0, 170.0]]
]
```

with:

```python
from pipeline.cargo import estimate_cargo
from pipeline.destinations import parse_destination
from pipeline.regions import (
    bounding_boxes_for_subscription,
    classify_region,
    should_keep_vessel,
)

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"
```

- [ ] **Step 3: Update the subscription dict**

In `collect_vessels`, change:

```python
subscription = {
    "APIKey": api_key,
    "BoundingBoxes": AU_BOUNDING_BOX,
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
}
```

to:

```python
subscription = {
    "APIKey": api_key,
    "BoundingBoxes": bounding_boxes_for_subscription(),
    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
}
```

- [ ] **Step 4: Add `region` field to the initial vessel record**

In the `if mmsi not in vessels:` block, add `"region": "",` alongside the other fields. The updated block should read:

```python
if mmsi not in vessels:
    vessels[mmsi] = {
        "mmsi": mmsi,
        "imo": "",
        "name": meta.get("ShipName", "").strip(),
        "ship_type": "product",
        "ais_type_code": 0,
        "lat": 0.0,
        "lon": 0.0,
        "speed": 0.0,
        "course": 0.0,
        "heading": 0.0,
        "draught": 0.0,
        "length": 0,
        "beam": 0,
        "destination": "",
        "destination_parsed": None,
        "region": "",
        "last_update": "",
    }
```

- [ ] **Step 5: Replace the post-processing filter to apply region + retention rule**

Replace the existing block:

```python
# Post-process: filter to tankers only, add cargo estimates
result_vessels = []
for vessel in vessels.values():
    # Skip vessels with no position
    if vessel["lat"] == 0.0 and vessel["lon"] == 0.0:
        continue

    # Only keep tankers (type 80-89) — skip vessels where we never got static data
    if vessel["ais_type_code"] not in TANKER_TYPE_CODES:
        continue

    cargo = estimate_cargo(
```

with:

```python
# Post-process: filter to tankers only, add cargo estimates
result_vessels = []
for vessel in vessels.values():
    # Skip vessels with no position
    if vessel["lat"] == 0.0 and vessel["lon"] == 0.0:
        continue

    # Only keep tankers (type 80-89) — skip vessels where we never got static data
    if vessel["ais_type_code"] not in TANKER_TYPE_CODES:
        continue

    # Region-based retention: all tankers in AU_APPROACH; elsewhere
    # only vessels whose declared destination parses as Australian.
    region = classify_region(vessel["lat"], vessel["lon"])
    vessel["region"] = region or ""
    if not should_keep_vessel(region, vessel["destination_parsed"]):
        continue

    cargo = estimate_cargo(
```

- [ ] **Step 6: Run the full test suite**

Run: `pytest pipeline/tests/ -v`
Expected: all tests pass (20 in test_regions.py plus the existing suites for cargo, destinations, arrivals, vessels, petroleum_stats).

- [ ] **Step 7: Smoke-import the collector**

Run: `python -c "from pipeline.collector import collect_vessels; from pipeline.regions import REGIONS; print(len(REGIONS), 'regions wired')"`
Expected: `9 regions wired`

- [ ] **Step 8: Commit**

```bash
git add pipeline/collector.py
git commit -m "feat: collect from multiple regions with destination-based retention"
```

---

## Task 5: End-to-end verification via a manual workflow run

**Files:**
- No code changes expected; this task validates the deployed pipeline.

- [ ] **Step 1: Push the branch and trigger the nightly workflow manually**

Run: `gh workflow run "Nightly Data Update & Deploy"`

- [ ] **Step 2: Wait for the run to complete (~30 minutes due to 1800s AIS window)**

Run: `gh run watch` (or `gh run list --limit 1` to check status)
Expected: workflow succeeds through data collection and deploy steps.

- [ ] **Step 3: Inspect the updated snapshot**

Pull the latest `main` and open `data/snapshot.json`. Confirm:
- At least one vessel object has a `"region"` field populated (e.g. `"AU_APPROACH"`, `"MIDDLE_EAST"`, etc.)
- Vessels outside `AU_APPROACH` have a non-null `destination_parsed` (evidence the retention rule fired)
- Vessel count is ≥ the previous run's count (8 tankers in last good run) — expect more now

- [ ] **Step 4: If boxes need tuning, create follow-up ticket; otherwise close out**

Box coordinates are estimates. If inspection shows we're missing obvious ports or pulling too much noise, note it as a follow-up; do not tune in this plan.

---

## Self-Review Notes

- **Spec coverage:** All 9 regions from the spec table are in `REGIONS` (Task 1). Subscription change (spec §2) = Task 4 Step 3. Classification + retention (spec §3) = Tasks 1, 2, 4. `region` field on vessel record (spec §5) = Task 4 Steps 4-5. Destination parser untouched (spec §4).
- **Non-goals respected:** No changes to cargo, arrivals, monthly estimates, or destinations. No dashboard changes. No attempt to infer missing destinations.
- **Function signatures consistent:** `classify_region(lat, lon) -> str | None` and `should_keep_vessel(region, destination_parsed) -> bool` are used identically in both `regions.py` and in `collector.py`.
