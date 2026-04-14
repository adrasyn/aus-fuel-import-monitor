# In-Transit Roster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist each in-transit vessel's trip state across pipeline runs so out-of-range tankers stay counted in the dashboard, and arrivals are detected even when a vessel went silent the day before docking.

**Architecture:** Extend the IMO-keyed `data/vessels.json` database with an optional `in_transit` block (last position, cargo, destination, region, last-position timestamp). The pipeline rebuilds `in_transit` from each fresh ping, leaves it alone for ships not seen this run, prunes after 14 days, and clears it on arrival. The dashboard reads the roster (filtered to records with `in_transit` set) instead of `snapshot.json`. Stale map markers (>24h since last ping) are dimmed with a tooltip.

**Tech Stack:** Python 3.12, pytest, Next.js 14 + TypeScript + Tailwind, react-leaflet.

---

## File Structure

- **Modify** `pipeline/vessels.py` — add `STALENESS_DAYS`, `build_in_transit()`, `prune_stale_in_transit()`; extend `update_vessel_db()` to manage the lifecycle.
- **Modify** `pipeline/arrivals.py` — `detect_arrivals()` switches from `previous_snapshot` to the vessel-db roster.
- **Modify** `pipeline/orchestrator.py` — wire roster into arrivals; recompute en-route monthly estimate from the roster's `in_transit` records.
- **Modify** `pipeline/tests/test_vessels.py` — extend with `in_transit` lifecycle tests.
- **Modify** `pipeline/tests/test_arrivals.py` — switch fixtures to roster shape.
- **Create** `pipeline/tests/test_orchestrator.py` — tests for `update_monthly_estimates` (new behaviour).
- **Modify** `src/lib/types.ts` — add `last_position_update: string` to `Vessel`.
- **Modify** `src/lib/data.ts` — read `vessels.json`, filter to in-transit, flatten onto `Snapshot` shape.
- **Modify** `src/components/VesselMap.tsx` — dim markers stale >24h, add "Last seen Xd ago" to popup.

---

## Task 1: Add `STALENESS_DAYS` constant and `build_in_transit()` helper

**Files:**
- Modify: `pipeline/vessels.py`
- Modify: `pipeline/tests/test_vessels.py`

- [ ] **Step 1: Write failing tests**

Append to `pipeline/tests/test_vessels.py`:

```python
from pipeline.vessels import build_in_transit


def test_build_in_transit_copies_dynamic_fields():
    snapshot_row = {
        "imo": "9876543",
        "mmsi": "636019825",
        "name": "Test Tanker",
        "ship_type": "crude",
        "lat": -25.5, "lon": 130.2,
        "speed": 12.4, "course": 180.0, "heading": 180.0,
        "draught": 14.5,
        "destination": "AU GLT",
        "destination_parsed": "Gladstone",
        "region": "AU_APPROACH",
        "cargo_litres": 95_000_000,
        "cargo_tonnes": 80_000,
        "load_factor": 0.95,
        "is_ballast": False,
        "draught_missing": False,
        "vessel_class": "Aframax",
        "dwt": 80_000,
        "length": 250, "beam": 44,
        "last_update": "2026-04-14T12:30:00Z",
    }
    in_transit = build_in_transit(snapshot_row, now="2026-04-14T13:00:00Z")
    assert in_transit["mmsi"] == "636019825"
    assert in_transit["lat"] == -25.5
    assert in_transit["lon"] == 130.2
    assert in_transit["destination_parsed"] == "Gladstone"
    assert in_transit["region"] == "AU_APPROACH"
    assert in_transit["cargo_litres"] == 95_000_000
    assert in_transit["is_ballast"] is False
    assert in_transit["last_position_update"] == "2026-04-14T13:00:00Z"


def test_build_in_transit_omits_static_top_level_fields():
    # Static fields like name/length/beam/ship_type live on the parent
    # vessel record; they must NOT also appear in in_transit.
    snapshot_row = {
        "imo": "9876543", "mmsi": "636019825", "name": "Test Tanker",
        "ship_type": "crude", "length": 250, "beam": 44,
        "vessel_class": "Aframax", "dwt": 80_000,
        "lat": 0.0, "lon": 0.0, "speed": 0.0, "course": 0.0, "heading": 0.0,
        "draught": 0.0, "destination": "", "destination_parsed": None,
        "region": "AU_APPROACH",
        "cargo_litres": 0, "cargo_tonnes": 0, "load_factor": 0.0,
        "is_ballast": True, "draught_missing": True,
        "last_update": "2026-04-14T12:30:00Z",
    }
    in_transit = build_in_transit(snapshot_row, now="2026-04-14T13:00:00Z")
    assert "name" not in in_transit
    assert "length" not in in_transit
    assert "beam" not in in_transit
    assert "ship_type" not in in_transit
    assert "vessel_class" not in in_transit
    assert "dwt" not in in_transit
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: `ImportError: cannot import name 'build_in_transit' from 'pipeline.vessels'`

- [ ] **Step 3: Implement `STALENESS_DAYS` and `build_in_transit`**

Replace the top of `pipeline/vessels.py`:

```python
"""Vessel database management, keyed by IMO number."""

from datetime import datetime, timedelta, timezone
from pipeline.cargo import classify_vessel, TANKER_CLASSES

STALENESS_DAYS = 14

# Dynamic fields copied from a snapshot row into the in_transit block.
# Static fields (name, length, beam, ship_type, vessel_class, dwt) stay on
# the parent vessel record and must not be duplicated here.
_IN_TRANSIT_FIELDS = (
    "mmsi", "lat", "lon", "speed", "course", "heading", "draught",
    "destination", "destination_parsed", "region",
    "cargo_litres", "cargo_tonnes", "load_factor",
    "is_ballast", "draught_missing",
)


def build_in_transit(snapshot_row: dict, now: str) -> dict:
    """Build an in_transit block from a vessel's row in the latest snapshot."""
    in_transit = {field: snapshot_row.get(field) for field in _IN_TRANSIT_FIELDS}
    in_transit["last_position_update"] = now
    return in_transit
```

(The existing `update_vessel_db` function stays unchanged for now — Task 3 will extend it.)

- [ ] **Step 4: Run tests, verify pass**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: 6 passed (4 pre-existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "$(cat <<'EOF'
feat(vessels): add build_in_transit helper and STALENESS_DAYS constant

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `prune_stale_in_transit()` helper

**Files:**
- Modify: `pipeline/vessels.py`
- Modify: `pipeline/tests/test_vessels.py`

- [ ] **Step 1: Write failing tests**

Append to `pipeline/tests/test_vessels.py`:

```python
from pipeline.vessels import prune_stale_in_transit, STALENESS_DAYS


def test_prune_clears_in_transit_older_than_threshold():
    db = {
        "9000001": {
            "name": "Old Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-03-31T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "lat": -10.0, "lon": 110.0, "speed": 12.0,
                "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "mmsi": "100000001",
                "last_position_update": "2026-03-31T00:00:00Z",  # 14+ days old
            },
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert db["9000001"]["in_transit"] is None


def test_prune_keeps_in_transit_within_threshold():
    db = {
        "9000002": {
            "name": "Recent Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "lat": -10.0, "lon": 110.0, "speed": 12.0,
                "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "mmsi": "100000002",
                "last_position_update": "2026-04-13T00:00:00Z",  # 1 day old
            },
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert db["9000002"]["in_transit"] is not None


def test_prune_skips_records_without_in_transit():
    # Already-arrived (or migration) records have no in_transit. No mutation.
    db = {
        "9000003": {
            "name": "Arrived Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 1,
            # no in_transit key at all
        }
    }
    prune_stale_in_transit(db, now="2026-04-14T12:00:00Z")
    assert "in_transit" not in db["9000003"]
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: `ImportError: cannot import name 'prune_stale_in_transit'`

- [ ] **Step 3: Implement `prune_stale_in_transit`**

Append to `pipeline/vessels.py`:

```python
def prune_stale_in_transit(db: dict, now: str) -> None:
    """Clear in_transit on any vessel last pinged > STALENESS_DAYS ago.

    Mutates db in place. No-op for records without an in_transit block.
    """
    cutoff = datetime.fromisoformat(now.replace("Z", "+00:00")) - timedelta(days=STALENESS_DAYS)
    for record in db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        last = in_transit.get("last_position_update")
        if not last:
            continue
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        if last_dt < cutoff:
            record["in_transit"] = None
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: 9 passed (6 + 3 new).

- [ ] **Step 5: Commit**

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "$(cat <<'EOF'
feat(vessels): add prune_stale_in_transit helper (14-day cutoff)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Extend `update_vessel_db` to manage `in_transit` lifecycle

**Files:**
- Modify: `pipeline/vessels.py`
- Modify: `pipeline/tests/test_vessels.py`

`update_vessel_db` already takes `(db, vessels, new_arrivals)`. New responsibilities:
- For each vessel in the snapshot list with an IMO: rebuild that record's `in_transit` from the snapshot row.
- For vessels in the db not in this snapshot: leave `in_transit` alone (carry over from prior run).
- For each new arrival: clear that record's `in_transit` (set to `None`).
- After the above, call `prune_stale_in_transit(db, now)`.

- [ ] **Step 1: Write failing tests**

Append to `pipeline/tests/test_vessels.py`:

```python
def test_update_vessel_db_populates_in_transit_for_pinged_vessels():
    db = {}
    vessels = [
        {
            "imo": "9876543", "mmsi": "636019825", "name": "Test Tanker",
            "length": 245, "beam": 44, "draught": 14.5,
            "ship_type": "crude",
            "lat": -25.5, "lon": 130.2,
            "speed": 12.4, "course": 180.0, "heading": 180.0,
            "destination": "AU GLT", "destination_parsed": "Gladstone",
            "region": "AU_APPROACH",
            "cargo_litres": 95_000_000, "cargo_tonnes": 80_000,
            "load_factor": 0.95, "is_ballast": False, "draught_missing": False,
        }
    ]
    updated = update_vessel_db(db, vessels)
    assert updated["9876543"]["in_transit"] is not None
    assert updated["9876543"]["in_transit"]["destination_parsed"] == "Gladstone"
    assert updated["9876543"]["in_transit"]["lat"] == -25.5


def test_update_vessel_db_preserves_in_transit_for_unseen_vessel():
    # Vessel was in the roster yesterday with in_transit set; not pinged today.
    # Today's snapshot is empty for this IMO — in_transit must persist.
    yesterday_in_transit = {
        "mmsi": "636019825", "lat": -10.0, "lon": 100.0,
        "speed": 12.0, "course": 90.0, "heading": 90.0, "draught": 14.5,
        "destination": "AU FRE", "destination_parsed": "Fremantle",
        "region": "AU_APPROACH",
        "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
        "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
        "last_position_update": "2026-04-13T00:00:00Z",
    }
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": yesterday_in_transit,
        }
    }
    updated = update_vessel_db(db, [])  # empty snapshot
    assert updated["9876543"]["in_transit"] == yesterday_in_transit


def test_update_vessel_db_clears_in_transit_on_arrival():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636019825", "lat": -38.0, "lon": 144.4,
                "speed": 0.5, "course": 0.0, "heading": 0.0, "draught": 14.5,
                "destination": "AU GEE", "destination_parsed": "Geelong",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-13T22:00:00Z",
            },
        }
    }
    new_arrivals = [{"imo": "9876543", "port": "Geelong"}]
    updated = update_vessel_db(db, [], new_arrivals=new_arrivals)
    assert updated["9876543"]["in_transit"] is None
    assert updated["9876543"]["arrival_count"] == 1


def test_update_vessel_db_prunes_stale_in_transit():
    # Vessel last pinged 20 days ago — must be cleared.
    db = {
        "9876543": {
            "name": "Old Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-03-25T00:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636019825", "lat": -10.0, "lon": 110.0,
                "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 14.5,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 80_000_000, "cargo_tonnes": 70_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-03-25T00:00:00Z",
            },
        }
    }
    updated = update_vessel_db(db, [])  # no fresh ping
    assert updated["9876543"]["in_transit"] is None
```

- [ ] **Step 2: Run tests, verify the four new ones fail**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: 4 fails (current update_vessel_db doesn't manage in_transit yet); the 9 pre-existing tests still pass.

If the existing tests start failing, **stop and report** — Task 1 or 2 broke something.

- [ ] **Step 3: Refactor `update_vessel_db` to manage `in_transit` lifecycle**

Replace the entire `update_vessel_db` function in `pipeline/vessels.py` with:

```python
def update_vessel_db(db: dict, vessels: list[dict], new_arrivals: list[dict] | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    pinged_imos = set()
    for vessel in vessels:
        imo = vessel.get("imo", "")
        if not imo:
            continue
        pinged_imos.add(imo)

        vessel_class = classify_vessel(vessel.get("length", 0), vessel.get("beam", 0))
        dwt = TANKER_CLASSES[vessel_class]["dwt"]

        if imo in db:
            db[imo]["last_seen"] = now
            db[imo]["name"] = vessel.get("name", db[imo]["name"])
        else:
            db[imo] = {
                "name": vessel.get("name", "Unknown"),
                "vessel_class": vessel_class,
                "dwt": dwt,
                "length": vessel.get("length", 0),
                "beam": vessel.get("beam", 0),
                "ship_type": vessel.get("ship_type", "product"),
                "first_seen": now,
                "last_seen": now,
                "arrival_count": 0,
            }

        # Rebuild in_transit from this fresh ping
        db[imo]["in_transit"] = build_in_transit(vessel, now=now)

    if new_arrivals:
        for arrival in new_arrivals:
            imo = arrival.get("imo", "")
            if imo in db:
                db[imo]["arrival_count"] += 1
                db[imo]["in_transit"] = None  # arrived → no longer in transit

    prune_stale_in_transit(db, now=now)

    return db
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `python -m pytest pipeline/tests/test_vessels.py -v`
Expected: 13 passed (9 pre-existing + 4 new). The 9 pre-existing tests pass because the new behaviour is additive: they don't assert on `in_transit` so the new field is invisible to them.

- [ ] **Step 5: Run full suite to confirm no other regressions**

Run: `python -m pytest pipeline/tests/ -v`
Expected: 97 passed (88 baseline + 9 added across Tasks 1, 2, 3).

If `test_arrivals.py` regresses, **stop and report** — Task 4 will be needed sooner than planned.

- [ ] **Step 6: Commit**

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "$(cat <<'EOF'
feat(vessels): manage in_transit lifecycle in update_vessel_db

- Rebuild in_transit for vessels in the latest snapshot
- Preserve in_transit for vessels not pinged this run
- Clear in_transit on arrival
- Prune entries silent for >14 days

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Refactor `detect_arrivals` to use the roster instead of `previous_snapshot`

**Files:**
- Modify: `pipeline/arrivals.py`
- Modify: `pipeline/tests/test_arrivals.py`

The check `imo not in previous_imos` becomes `record's in_transit must be set in the roster`. This handles ships that went silent the day before docking.

- [ ] **Step 1: Update existing tests + add new test**

Replace the entirety of `pipeline/tests/test_arrivals.py` with:

```python
from pipeline.arrivals import haversine_km, is_within_port, detect_arrivals


def test_haversine_known_distance():
    dist = haversine_km(-33.87, 151.21, -37.81, 144.96)
    assert 700 < dist < 730


def test_haversine_same_point():
    dist = haversine_km(-33.87, 151.21, -33.87, 151.21)
    assert dist == 0.0


def test_is_within_port_true():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-37.84, 144.92, ports)
    assert result == "Melbourne"


def test_is_within_port_false():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-33.87, 151.21, ports)
    assert result is None


def test_is_within_port_edge():
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    result = is_within_port(-37.785, 144.92, ports)
    assert result is None


def _vessel_db_with(imo: str, in_transit: dict | None) -> dict:
    return {
        imo: {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-13T00:00:00Z",
            "arrival_count": 0,
            "in_transit": in_transit,
        }
    }


def test_detect_arrivals_vessel_arrived_with_roster():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -36.0, "lon": 144.0, "speed": 12.0, "destination": "GEELONG",
        "last_position_update": "2026-04-13T22:00:00Z",
    })
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 1
    assert new_arrivals[0]["port"] == "Geelong"
    assert new_arrivals[0]["imo"] == "1234567"


def test_detect_arrivals_handles_silent_then_dock():
    # Vessel was silent the day before docking — roster still has in_transit set,
    # so today's port ping must count as arrival even without a previous snapshot.
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -36.0, "lon": 144.0, "speed": 12.0, "destination": "GEELONG",
        "last_position_update": "2026-04-12T22:00:00Z",  # 2 days ago
    })
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 1


def test_detect_arrivals_skips_vessel_not_in_roster():
    # A ship's first ever ping happens to be at a port — no in_transit means
    # we have no prior knowledge of it being in transit. Don't fire arrival.
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = {}  # empty roster
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 0


def test_detect_arrivals_vessel_still_at_sea():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -36.0, "lon": 144.0, "speed": 12.0, "destination": "GEELONG",
        "last_position_update": "2026-04-13T22:00:00Z",
    })
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -37.0, "lon": 144.2,
             "speed": 11.5, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 0


def test_detect_arrivals_no_duplicate():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -38.15, "lon": 144.36, "speed": 0.3, "destination": "GEELONG",
        "last_position_update": "2026-04-13T22:00:00Z",
    })
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    existing_arrivals = [
        {"imo": "1234567", "port": "Geelong", "timestamp": "2026-04-12T02:00:00Z"}
    ]
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, existing_arrivals)
    assert len(new_arrivals) == 0
```

- [ ] **Step 2: Run tests, expect failures because the new signature doesn't exist yet**

Run: `python -m pytest pipeline/tests/test_arrivals.py -v`
Expected: the 5 detect_arrivals tests fail (signature mismatch — current `detect_arrivals` takes `previous_snapshot`, tests pass `vessel_db`); haversine + is_within_port tests still pass.

- [ ] **Step 3: Refactor `detect_arrivals` to take the roster**

Replace the entirety of `pipeline/arrivals.py` with:

```python
"""Port arrival detection using geofencing."""

import json
import math
from datetime import datetime, timezone
from pipeline.cargo import estimate_cargo


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_ports(ports_path: str = "data/ports.json") -> list[dict]:
    with open(ports_path) as f:
        return json.load(f)["ports"]


def is_within_port(lat: float, lon: float, ports: list[dict]) -> str | None:
    for port in ports:
        dist = haversine_km(lat, lon, port["lat"], port["lon"])
        if dist <= port["radius_km"]:
            return port["name"]
    return None


def detect_arrivals(
    current_snapshot: dict,
    vessel_db: dict,
    ports: list[dict],
    existing_arrivals: list[dict],
) -> list[dict]:
    """Detect new port arrivals.

    A vessel counts as a new arrival when:
    - it appears in the current snapshot at speed < 1.0 inside a port radius
    - the roster has it as in_transit (we previously knew it was on a trip)
    - the (imo, port) pair has not already been recorded
    """
    arrived_imos = {(a["imo"], a["port"]) for a in existing_arrivals}
    in_transit_imos = {
        imo for imo, record in vessel_db.items()
        if record.get("in_transit") is not None
    }
    new_arrivals = []
    now = datetime.now(timezone.utc).isoformat()

    for vessel in current_snapshot.get("vessels", []):
        imo = vessel["imo"]
        speed = vessel.get("speed", 99)
        lat = vessel["lat"]
        lon = vessel["lon"]

        if speed >= 1.0:
            continue
        port_name = is_within_port(lat, lon, ports)
        if port_name is None:
            continue
        if imo not in in_transit_imos:
            continue
        if (imo, port_name) in arrived_imos:
            continue

        cargo = estimate_cargo(
            length=vessel.get("length", 0),
            beam=vessel.get("beam", 0),
            draught=vessel.get("draught", 0),
            ship_type=vessel.get("ship_type", "product"),
        )

        new_arrivals.append({
            "imo": imo,
            "name": vessel.get("name", "Unknown"),
            "port": port_name,
            "timestamp": now,
            "ship_type": vessel.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
        })

    return new_arrivals
```

- [ ] **Step 4: Run tests, verify all pass**

Run: `python -m pytest pipeline/tests/test_arrivals.py -v`
Expected: 10 passed (5 pre-existing helper tests + 5 detect_arrivals tests).

- [ ] **Step 5: Confirm full suite still passes**

Run: `python -m pytest pipeline/tests/ -v`
Expected: **99 passed** (97 from end of Task 3 + 2 net from Task 4: pre-existing arrivals had 8 tests, now has 10).

If you see failures, **stop and report**.

- [ ] **Step 6: Commit**

```bash
git add pipeline/arrivals.py pipeline/tests/test_arrivals.py
git commit -m "$(cat <<'EOF'
feat(arrivals): use vessel_db roster instead of previous_snapshot

Detects arrivals when a ship was silent the day before docking,
using the persistent in_transit roster to confirm prior in-transit
state instead of relying on yesterday's snapshot.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Wire orchestrator + recompute monthly en-route from roster

**Files:**
- Modify: `pipeline/orchestrator.py`
- Create: `pipeline/tests/test_orchestrator.py`

Two changes in `orchestrator.py`:
1. Pass `vessel_db` (not `previous_snapshot`) to `detect_arrivals`. Note: arrivals are detected **before** the vessel-db update for the current run, so the roster passed in is yesterday's state — exactly what we want for the "was previously in transit" check.
2. `update_monthly_estimates` sums en-route volumes from the roster's `in_transit` records, not from `current_snapshot["vessels"]`.

- [ ] **Step 1: Write failing test for `update_monthly_estimates`**

Create `pipeline/tests/test_orchestrator.py`:

```python
from pipeline.orchestrator import update_monthly_estimates


def test_update_monthly_estimates_sums_en_route_from_roster():
    monthly = {"months": {}}
    vessel_db = {
        "9000001": {
            "name": "Crude One", "vessel_class": "VLCC", "dwt": 300000,
            "length": 333, "beam": 60, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636011111", "lat": -10.0, "lon": 110.0,
                "speed": 12.0, "course": 180.0, "heading": 180.0, "draught": 22.0,
                "destination": "AU FRE", "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 320_000_000, "cargo_tonnes": 280_000,
                "load_factor": 0.95, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000002": {
            "name": "Product One", "vessel_class": "MR", "dwt": 50000,
            "length": 180, "beam": 32, "ship_type": "product",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636022222", "lat": -25.0, "lon": 130.0,
                "speed": 11.0, "course": 200.0, "heading": 200.0, "draught": 12.0,
                "destination": "AU MEL", "destination_parsed": "Melbourne",
                "region": "AU_APPROACH",
                "cargo_litres": 60_000_000, "cargo_tonnes": 50_000,
                "load_factor": 0.9, "is_ballast": False, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000003": {
            # Ballast — must not contribute to en-route totals
            "name": "Ballast One", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-14T12:00:00Z",
            "arrival_count": 0,
            "in_transit": {
                "mmsi": "636033333", "lat": -20.0, "lon": 120.0,
                "speed": 10.0, "course": 90.0, "heading": 90.0, "draught": 7.0,
                "destination": "", "destination_parsed": None,
                "region": "AU_APPROACH",
                "cargo_litres": 0, "cargo_tonnes": 0,
                "load_factor": 0.0, "is_ballast": True, "draught_missing": False,
                "last_position_update": "2026-04-14T12:00:00Z",
            },
        },
        "9000004": {
            # Arrived (in_transit = None) — must not contribute to en-route
            "name": "Arrived One", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-03-01T00:00:00Z",
            "last_seen": "2026-04-13T22:00:00Z",
            "arrival_count": 1,
            "in_transit": None,
        },
    }
    updated = update_monthly_estimates(monthly, [], vessel_db)
    months = updated["months"]
    assert len(months) == 1
    month = next(iter(months.values()))
    assert month["en_route_crude_litres"] == 320_000_000
    assert month["en_route_product_litres"] == 60_000_000
```

- [ ] **Step 2: Run test, verify failure**

Run: `python -m pytest pipeline/tests/test_orchestrator.py -v`
Expected: failure — `update_monthly_estimates` currently takes `current_snapshot`, not `vessel_db`. The test passes a `vessel_db` as the third argument; the function will iterate over `vessel_db["vessels"]` (or similar) and explode.

- [ ] **Step 3: Refactor `update_monthly_estimates` and the orchestrator wiring**

In `pipeline/orchestrator.py`:

Replace `update_monthly_estimates`:

```python
def update_monthly_estimates(monthly: dict, new_arrivals: list[dict], vessel_db: dict) -> dict:
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    if month_key not in monthly.get("months", {}):
        monthly.setdefault("months", {})[month_key] = {
            "arrived_crude_litres": 0,
            "arrived_product_litres": 0,
            "arrived_crude_tonnes": 0,
            "arrived_product_tonnes": 0,
            "arrival_count": 0,
        }

    month = monthly["months"][month_key]

    for arrival in new_arrivals:
        month["arrival_count"] += 1
        if arrival["ship_type"] == "crude":
            month["arrived_crude_litres"] += arrival["cargo_litres"]
            month["arrived_crude_tonnes"] += arrival["cargo_tonnes"]
        else:
            month["arrived_product_litres"] += arrival["cargo_litres"]
            month["arrived_product_tonnes"] += arrival["cargo_tonnes"]

    en_route_crude_litres = 0
    en_route_product_litres = 0
    for record in vessel_db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if in_transit.get("is_ballast"):
            continue
        if record.get("ship_type") == "crude":
            en_route_crude_litres += in_transit.get("cargo_litres", 0)
        else:
            en_route_product_litres += in_transit.get("cargo_litres", 0)

    month["en_route_crude_litres"] = en_route_crude_litres
    month["en_route_product_litres"] = en_route_product_litres
    month["last_updated"] = now.isoformat()

    return monthly
```

Update `run_pipeline` so the calls become:

```python
    print("Step 2: Detecting port arrivals...")
    new_arrivals = detect_arrivals(
        current_snapshot, vessel_db, ports, arrivals_data["arrivals"]
    )
    arrivals_data["arrivals"].extend(new_arrivals)
    save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)
    print(f"  {len(new_arrivals)} new arrivals detected")

    print("Step 3: Updating vessel database...")
    vessel_db = update_vessel_db(vessel_db, current_snapshot["vessels"], new_arrivals)
    save_json(f"{DATA_DIR}/vessels.json", vessel_db)
    print(f"  {len(vessel_db)} vessels in database")

    print("Step 4: Updating monthly estimates...")
    monthly = update_monthly_estimates(monthly, new_arrivals, vessel_db)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)
```

The call order matters: `detect_arrivals` runs **before** `update_vessel_db`, so it sees yesterday's roster (correct — we want to know if the vessel was previously in transit). Then `update_vessel_db` refreshes/clears `in_transit`. Then `update_monthly_estimates` uses the freshly-updated roster for en-route sums.

Also drop the now-unused `previous_snapshot` load near the top of `run_pipeline`:

Replace:

```python
    previous_snapshot = load_json(f"{DATA_DIR}/snapshot.json", {"vessels": []})
    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
```

with:

```python
    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
```

(The collector still writes `snapshot.json` after Step 1; we just don't read the previous one anymore.)

- [ ] **Step 4: Run all tests**

Run: `python -m pytest pipeline/tests/ -v`
Expected: **100 passed** (99 from end of Task 4 + 1 new from `test_orchestrator.py`).

- [ ] **Step 5: Smoke-import the orchestrator**

Run: `python -c "from pipeline.orchestrator import run_pipeline, update_monthly_estimates; print('ok')"`
Expected: `ok`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrator.py pipeline/tests/test_orchestrator.py
git commit -m "$(cat <<'EOF'
feat(orchestrator): wire roster into arrivals + monthly en-route sums

- detect_arrivals now reads the roster (yesterday's state) before
  vessels are refreshed for the current run
- update_monthly_estimates sums en-route volumes from the roster's
  in_transit records, so out-of-range vessels still count
- previous_snapshot load removed (no longer needed)

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Frontend types + data layer (read from `vessels.json`)

**Files:**
- Modify: `src/lib/types.ts`
- Modify: `src/lib/data.ts`

- [ ] **Step 1: Add `last_position_update` to the `Vessel` interface**

In `src/lib/types.ts`, change the `Vessel` interface to add `last_position_update`:

Replace:

```typescript
export interface Vessel {
  mmsi: string;
  imo: string;
  name: string;
  ship_type: "crude" | "product";
  lat: number;
  lon: number;
  speed: number;
  course: number;
  draught: number;
  length: number;
  beam: number;
  destination: string;
  destination_parsed: string | null;
  vessel_class: string;
  dwt: number;
  load_factor: number;
  cargo_tonnes: number;
  cargo_litres: number;
  is_ballast: boolean;
  draught_missing: boolean;
  last_update: string;
}
```

with:

```typescript
export interface Vessel {
  mmsi: string;
  imo: string;
  name: string;
  ship_type: "crude" | "product";
  lat: number;
  lon: number;
  speed: number;
  course: number;
  draught: number;
  length: number;
  beam: number;
  destination: string;
  destination_parsed: string | null;
  vessel_class: string;
  dwt: number;
  load_factor: number;
  cargo_tonnes: number;
  cargo_litres: number;
  is_ballast: boolean;
  draught_missing: boolean;
  last_update: string;
  last_position_update: string;
}

interface VesselDbInTransit {
  mmsi: string;
  lat: number;
  lon: number;
  speed: number;
  course: number;
  heading: number;
  draught: number;
  destination: string;
  destination_parsed: string | null;
  region: string;
  cargo_litres: number;
  cargo_tonnes: number;
  load_factor: number;
  is_ballast: boolean;
  draught_missing: boolean;
  last_position_update: string;
}

export interface VesselDbRecord {
  name: string;
  vessel_class: string;
  dwt: number;
  length: number;
  beam: number;
  ship_type: "crude" | "product";
  first_seen: string;
  last_seen: string;
  arrival_count: number;
  in_transit: VesselDbInTransit | null;
}

export type VesselDb = Record<string, VesselDbRecord>;
```

- [ ] **Step 2: Update `loadDashboardData` to read from `vessels.json`**

Replace the entire contents of `src/lib/data.ts` with:

```typescript
import fs from "fs";
import path from "path";
import type {
  Snapshot,
  Vessel,
  VesselDb,
  Arrival,
  MonthlyEstimates,
  ImportsData,
  DashboardData,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filename: string, fallback: T): T {
  const filePath = path.join(DATA_DIR, filename);
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

function rosterToSnapshot(db: VesselDb): Snapshot {
  const vessels: Vessel[] = [];
  let latest = "";

  for (const [imo, record] of Object.entries(db)) {
    const it = record.in_transit;
    if (!it) continue;

    vessels.push({
      mmsi: it.mmsi,
      imo,
      name: record.name,
      ship_type: record.ship_type,
      lat: it.lat,
      lon: it.lon,
      speed: it.speed,
      course: it.course,
      draught: it.draught,
      length: record.length,
      beam: record.beam,
      destination: it.destination,
      destination_parsed: it.destination_parsed,
      vessel_class: record.vessel_class,
      dwt: record.dwt,
      load_factor: it.load_factor,
      cargo_tonnes: it.cargo_tonnes,
      cargo_litres: it.cargo_litres,
      is_ballast: it.is_ballast,
      draught_missing: it.draught_missing,
      last_update: it.last_position_update,
      last_position_update: it.last_position_update,
    });

    if (it.last_position_update > latest) {
      latest = it.last_position_update;
    }
  }

  return { timestamp: latest, vessels };
}

export function loadDashboardData(): DashboardData {
  const db = readJson<VesselDb>("vessels.json", {});
  const snapshot = rosterToSnapshot(db);
  const arrivalsData = readJson<{ arrivals: Arrival[] }>("arrivals.json", {
    arrivals: [],
  });
  const monthlyEstimates = readJson<MonthlyEstimates>(
    "monthly-estimates.json",
    { months: {} }
  );
  const imports = readJson<ImportsData>("imports.json", {
    imports_by_month: [],
    consumption_cover: [],
  });
  return {
    snapshot,
    arrivals: arrivalsData.arrivals,
    monthlyEstimates,
    imports,
  };
}

export function formatLitres(litres: number): string {
  if (litres >= 1_000_000_000) return `${(litres / 1_000_000_000).toFixed(1)}B L`;
  if (litres >= 1_000_000) return `${(litres / 1_000_000).toFixed(0)}M L`;
  return `${litres.toLocaleString()} L`;
}
```

- [ ] **Step 3: Build to verify TypeScript compiles**

Run: `npm run build`
Expected: clean build, no TS errors.

If the build fails with a missing import (e.g., `Vessel` not exported), make sure your edits to `types.ts` preserved the existing exports.

- [ ] **Step 4: Commit**

```bash
git add src/lib/types.ts src/lib/data.ts
git commit -m "$(cat <<'EOF'
feat(frontend): read in-transit roster from vessels.json

The dashboard now reads vessels.json (filtered to records with
in_transit set) instead of snapshot.json, so out-of-range tankers
remain in the stats and on the map.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Frontend — dim stale vessel markers + tooltip

**Files:**
- Modify: `src/components/VesselMap.tsx`

- [ ] **Step 1: Add staleness logic to the marker render**

Replace the `vessels.map(...)` block in `src/components/VesselMap.tsx` with:

```tsx
      {vessels.map((vessel) => {
        if (vessel.lat === 0 && vessel.lon === 0) return null;
        const isSelected = vessel.imo === selectedImo;
        const color = vessel.ship_type === "crude" ? "#dc2626" : "#1e40af";
        const radius = isSelected ? 8 : 5;

        const lastSeenMs = vessel.last_position_update
          ? Date.now() - new Date(vessel.last_position_update).getTime()
          : 0;
        const staleHours = lastSeenMs / 3_600_000;
        const isStale = staleHours > 24;

        const ballastFactor = vessel.is_ballast ? 0.3 : 1;
        const staleFactor = isStale ? 0.4 : 1;
        const opacity = ballastFactor * staleFactor;

        const lastSeenLabel = (() => {
          if (!isStale) return null;
          const days = Math.floor(staleHours / 24);
          if (days >= 1) return `Last seen ${days}d ago`;
          return `Last seen ${Math.floor(staleHours)}h ago`;
        })();

        return (
          <CircleMarker
            key={vessel.mmsi}
            center={[vessel.lat, vessel.lon]}
            radius={radius}
            pathOptions={{
              color: isSelected ? "#111827" : color,
              fillColor: color,
              fillOpacity: opacity,
              weight: isSelected ? 2 : 1,
            }}
            eventHandlers={{ click: () => onSelectVessel(vessel.imo) }}
          >
            <Popup>
              <div className="font-body text-xs">
                <p className="font-semibold">{vessel.name || "Unknown"}</p>
                <p className="text-label">
                  {vessel.vessel_class} &middot;{" "}
                  <span className={vessel.ship_type === "crude" ? "text-crude" : "text-product"}>
                    {vessel.ship_type === "crude" ? "Crude" : "Product"}
                  </span>
                </p>
                <p>Est. cargo: {(vessel.cargo_litres / 1_000_000).toFixed(0)}M L{vessel.draught_missing && " *"}</p>
                <p>Dest: {vessel.destination_parsed || vessel.destination || "Unknown"}</p>
                <p>Speed: {vessel.speed.toFixed(1)} kn</p>
                {vessel.is_ballast && <p className="text-label-light italic">Ballast (empty)</p>}
                {lastSeenLabel && (
                  <p className="text-label-light italic">{lastSeenLabel}</p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
```

- [ ] **Step 2: Build to verify**

Run: `npm run build`
Expected: clean build.

- [ ] **Step 3: Commit**

```bash
git add src/components/VesselMap.tsx
git commit -m "$(cat <<'EOF'
feat(map): dim stale (>24h) vessel markers + last-seen tooltip

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:**
- §1 Data model — Tasks 1, 2, 3 (all of `vessels.py`'s lifecycle work).
- §2 Pipeline orchestration — Tasks 4, 5.
- §3 Frontend — Tasks 6, 7. (`VesselTable` not modified per spec decision.)
- §4 Type definitions — Task 6 (Vessel + new VesselDb types).
- §5 Migration & edge cases — handled by behaviours implemented in Tasks 3, 4 (no `in_transit` ⇒ treated as not-in-transit; first-ping-at-port ⇒ no roster entry ⇒ no arrival, see Task 4 test `test_detect_arrivals_skips_vessel_not_in_roster`).

**No placeholders.** Every step has the full code or the full command and expected outcome.

**Type consistency:**
- `build_in_transit(snapshot_row, now: str) -> dict` — same signature in Tasks 1 and 3.
- `prune_stale_in_transit(db, now: str) -> None` — same in Tasks 2 and 3.
- `detect_arrivals(current_snapshot, vessel_db, ports, existing_arrivals)` — same in Tasks 4 and 5.
- `update_monthly_estimates(monthly, new_arrivals, vessel_db)` — same in Tasks 5 (new test) and the implementation.
- `VesselDbInTransit` / `VesselDbRecord` / `VesselDb` types defined once in Task 6, used in `data.ts` in the same task.
- Field names match across Python and TypeScript (snake_case throughout).

**Call-order invariant** (Task 5): `detect_arrivals` must run **before** `update_vessel_db` so it sees yesterday's roster, not the freshly-updated one. Plan calls this out in Step 3.
