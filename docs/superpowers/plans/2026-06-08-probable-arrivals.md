# Probable Arrivals (Approached-then-Vanished) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recover laden, Australia-bound tankers that go AIS-dark on approach and are currently pruned without an arrival, surfacing them as a separate reversible "probable" tier in the monthly import totals and on the dashboard.

**Architecture:** A new `detect_probable_arrivals` pass (mirroring `detect_silent_arrivals`) marks vanished vessels and writes `status: "probable"` rows to `arrivals.json`. A `reconcile_probable_arrivals` pass handles reversal (vessel reappears) and upgrade (vessel later confirmed at berth). The 14-day prune finalizes still-dark probables instead of logging them lost. Monthly totals (already rebuilt from `arrivals.json` each run) split by status into `arrived_*` (confirmed) and new `probable_*` fields; the dashboard stacks a distinct probable band. A one-shot idempotent backfill recovers historical lost vessels.

**Tech Stack:** Python 3.12 (pipeline, pytest), Next.js / React / TypeScript / recharts (dashboard).

**Reference spec:** `docs/superpowers/specs/2026-06-08-probable-arrivals-design.md`

**Key constants (locked):** `DARK_DAYS=4`, `INNER_KM=50`, `APPROACH_KM=150`, `SLOW_KN=1.5`, `HEADING_TOL=75.0`.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `pipeline/arrivals.py` | Arrival detectors + geofence/geometry helpers | Add `bearing_deg`, `angular_diff`, `_resolve_probable_port`, `detect_probable_arrivals`, `reconcile_probable_arrivals`, constants; relax confirmed dedupe to ignore probable rows |
| `pipeline/vessels.py` | Vessel DB lifecycle + prune | Finalize probable records in `prune_stale_in_transit` (no lost-log) |
| `pipeline/orchestrator.py` | Nightly pipeline wiring + monthly aggregation | Wire new passes; split `rebucket_monthly_from_arrivals` by status; exclude marked records from en-route sums; add backfill step |
| `pipeline/daily_estimates.py` | Daily en-route sum | Exclude marked records |
| `pipeline/backfill_probable.py` | One-shot historical recovery from lost-vessels | New file |
| `src/lib/types.ts` | Dashboard types | Add `probable_*` fields to `MonthEstimate` |
| `src/components/HistoricalChart.tsx` | Imports bar chart | Stack a distinct probable band |
| `pipeline/tests/test_arrivals.py` | — | Tests for new detectors/helpers |
| `pipeline/tests/test_vessels.py` | — | Finalization test |
| `pipeline/tests/test_orchestrator.py` | — | Monthly split + en-route exclusion tests |
| `pipeline/tests/test_backfill_probable.py` | — | New backfill tests |

Run all pipeline tests with: `python -m pytest pipeline/tests/ -q`

---

## Task 1: Geometry helpers (`bearing_deg`, `angular_diff`)

**Files:**
- Modify: `pipeline/arrivals.py` (add after `haversine_km`, ~line 30)
- Test: `pipeline/tests/test_arrivals.py`

- [ ] **Step 1: Write the failing tests**

Add to `pipeline/tests/test_arrivals.py` (extend the import from `pipeline.arrivals` to include `bearing_deg, angular_diff`):

```python
from pipeline.arrivals import bearing_deg, angular_diff


def test_bearing_due_north():
    # From equator origin straight up in latitude → ~0° (north)
    assert abs(bearing_deg(0.0, 0.0, 1.0, 0.0) - 0.0) < 1.0


def test_bearing_due_east():
    assert abs(bearing_deg(0.0, 0.0, 0.0, 1.0) - 90.0) < 1.0


def test_angular_diff_wraps():
    assert angular_diff(350.0, 10.0) == 20.0
    assert angular_diff(10.0, 350.0) == 20.0
    assert angular_diff(90.0, 90.0) == 0.0
    assert angular_diff(0.0, 180.0) == 180.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_arrivals.py -k "bearing or angular" -v`
Expected: FAIL — `ImportError: cannot import name 'bearing_deg'`

- [ ] **Step 3: Implement the helpers**

Add to `pipeline/arrivals.py` immediately after `haversine_km`:

```python
def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing from point 1 to point 2, in degrees (0-360, 0=N)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360.0) % 360.0


def angular_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two compass bearings, in degrees (0-180)."""
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_arrivals.py -k "bearing or angular" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add pipeline/arrivals.py pipeline/tests/test_arrivals.py
git commit -m "feat(arrivals): add bearing_deg and angular_diff geometry helpers"
```

---

## Task 2: Port resolver + `detect_probable_arrivals`

**Files:**
- Modify: `pipeline/arrivals.py` (add constants near top; functions after `detect_silent_arrivals`)
- Test: `pipeline/tests/test_arrivals.py`

The detector mirrors `detect_silent_arrivals`: it iterates the roster, returns new probable rows, and sets `record["probable_arrival"]` on qualifying records. It fires only on vessels **not** in the current ping set (vanished) that have been dark ≥ `DARK_DAYS`.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline/tests/test_arrivals.py`:

```python
from pipeline.arrivals import detect_probable_arrivals

PORTS = [
    {"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5},
    {"name": "Brisbane", "lat": -27.38, "lon": 153.17, "radius_km": 5},
]


def _roster(imo, in_transit, departed_au=True, length=183, beam=32, ship_type="product"):
    return {imo: {
        "name": "PROB TANKER", "vessel_class": "MR", "dwt": 40000,
        "length": length, "beam": beam, "ship_type": ship_type,
        "first_seen": "2026-05-01T00:00:00+00:00",
        "last_seen": "2026-05-05T00:00:00+00:00",
        "arrival_count": 0, "departed_au_since_arrival": departed_au,
        "in_transit": in_transit,
    }}


def _it(lat, lon, speed=0.0, course=0.0, last="2026-05-05T00:00:00+00:00",
        dest="GEELONG", dest_parsed="Geelong", is_ballast=False, draught=11.0):
    return {
        "lat": lat, "lon": lon, "speed": speed, "course": course,
        "destination": dest, "destination_parsed": dest_parsed,
        "draught": draught, "is_ballast": is_ballast,
        "cargo_litres": 48000000, "cargo_tonnes": 40000,
        "last_position_update": last,
    }


NOW = "2026-05-12T00:00:00+00:00"  # 7 days after last ping → dark


def test_probable_inner_band_stationary():
    # Parked 3km from Geelong, dark 7 days → probable, no kinematic check needed
    db = _roster("1000001", _it(-38.13, 144.36, speed=0.0))
    rows = detect_probable_arrivals(db, PORTS, [], [], NOW)
    assert len(rows) == 1
    assert rows[0]["status"] == "probable"
    assert rows[0]["port"] == "Geelong"
    assert rows[0]["timestamp"] == "2026-05-05T00:00:00+00:00"  # dark date, not NOW
    assert db["1000001"]["probable_arrival"]["port"] == "Geelong"


def test_probable_ballast_excluded():
    db = _roster("1000002", _it(-38.13, 144.36, is_ballast=True))
    assert detect_probable_arrivals(db, PORTS, [], [], NOW) == []


def test_probable_coastal_leg_excluded():
    db = _roster("1000003", _it(-38.13, 144.36), departed_au=False)
    assert detect_probable_arrivals(db, PORTS, [], [], NOW) == []


def test_probable_not_dark_enough_excluded():
    # last ping only 2 days ago
    db = _roster("1000004", _it(-38.13, 144.36, last="2026-05-10T00:00:00+00:00"))
    assert detect_probable_arrivals(db, PORTS, [], [], NOW) == []


def test_probable_still_pinging_excluded():
    db = _roster("1000005", _it(-38.13, 144.36))
    current = [{"imo": "1000005", "lat": -38.13, "lon": 144.36}]
    assert detect_probable_arrivals(db, PORTS, current, [], NOW) == []


def test_probable_far_outside_approach_excluded():
    # 600km+ from any port
    db = _roster("1000006", _it(-20.0, 130.0))
    assert detect_probable_arrivals(db, PORTS, [], [], NOW) == []


def test_probable_outer_band_closing_heading_included():
    # ~90km south of Geelong, moving, course pointed north (toward port)
    db = _roster("1000007", _it(-38.95, 144.36, speed=11.0, course=0.0))
    rows = detect_probable_arrivals(db, PORTS, [], [], NOW)
    assert len(rows) == 1 and rows[0]["port"] == "Geelong"


def test_probable_outer_band_heading_away_excluded():
    # ~90km south of Geelong, moving, course pointed south (away from port)
    db = _roster("1000008", _it(-38.95, 144.36, speed=11.0, course=180.0))
    assert detect_probable_arrivals(db, PORTS, [], [], NOW) == []


def test_probable_dedupe_existing_confirmed():
    db = _roster("1000009", _it(-38.13, 144.36))
    existing = [{"imo": "1000009", "port": "Geelong", "status": "confirmed"}]
    assert detect_probable_arrivals(db, PORTS, [], existing, NOW) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_arrivals.py -k probable -v`
Expected: FAIL — `ImportError: cannot import name 'detect_probable_arrivals'`

- [ ] **Step 3: Implement constants, resolver, and detector**

Add constants near the top of `pipeline/arrivals.py` (after `_SILENT_ARRIVAL_SPEED_CAP`):

```python
# Probable-arrival ("approached then vanished") tunables. A laden, AU-bound
# vessel that goes AIS-dark near a port is inferred to have berthed.
DARK_DAYS = 4          # days silent before a probable arrival fires
INNER_KM = 50          # within this of a port → proximity alone (no kinematic check)
APPROACH_KM = 150      # outer max distance from a port for "approached"
SLOW_KN = 1.5          # at/below → treated as anchored/slowing (outer band)
HEADING_TOL = 75.0     # max course deviation from bearing-to-port for "closing" (outer band)
```

Add `from datetime import datetime, timezone, timedelta` to the imports if not present (the module currently imports `datetime` — confirm and extend). Then add after `detect_silent_arrivals`:

```python
def _resolve_probable_port(in_transit: dict, lat: float, lon: float, ports: list[dict]):
    """Pick the port P a vanished vessel is most likely heading to.

    Prefer the declared destination if it names a known port within
    APPROACH_KM; otherwise the nearest port within APPROACH_KM. Returns
    (port_dict, distance_km) or (None, None) if nothing is in range.
    """
    dest = in_transit.get("destination_parsed")
    if dest:
        named = [p for p in ports if p["name"] == dest]
        if named:
            p = min(named, key=lambda pt: haversine_km(lat, lon, pt["lat"], pt["lon"]))
            d = haversine_km(lat, lon, p["lat"], p["lon"])
            if d <= APPROACH_KM:
                return p, d
    p = min(ports, key=lambda pt: haversine_km(lat, lon, pt["lat"], pt["lon"]))
    d = haversine_km(lat, lon, p["lat"], p["lon"])
    if d <= APPROACH_KM:
        return p, d
    return None, None


def detect_probable_arrivals(
    vessel_db: dict,
    ports: list[dict],
    current_vessels: list[dict],
    existing_arrivals: list[dict],
    now: str,
) -> list[dict]:
    """Infer arrivals for laden, AU-bound vessels that went AIS-dark near a port.

    Fires on roster records that: are laden, on a fresh international leg, NOT in
    the current ping batch (vanished), dark >= DARK_DAYS, and last seen within
    APPROACH_KM of a port. Within INNER_KM proximity alone qualifies; in the
    50-150km band the vessel must also be anchored/slowing OR on a closing
    heading. Sets record["probable_arrival"] and returns new probable rows.
    Idempotent: skips records already marked or already having a confirmed
    arrival at the resolved port.
    """
    now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
    dark_cutoff = now_dt - timedelta(days=DARK_DAYS)
    pinged = {v.get("imo", "") for v in current_vessels if v.get("imo")}
    confirmed_keys = {
        (a["imo"], a["port"]) for a in existing_arrivals
        if a.get("status") != "probable"
    }

    new_rows = []
    for imo, record in vessel_db.items():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if record.get("probable_arrival"):
            continue
        if in_transit.get("is_ballast"):
            continue
        if not record.get("departed_au_since_arrival", True):
            continue
        if imo in pinged:
            continue
        last = in_transit.get("last_position_update")
        if not last:
            continue
        if datetime.fromisoformat(last.replace("Z", "+00:00")) >= dark_cutoff:
            continue
        lat, lon = in_transit.get("lat"), in_transit.get("lon")
        if lat is None or lon is None:
            continue

        port, dist = _resolve_probable_port(in_transit, lat, lon, ports)
        if port is None:
            continue
        port_name = port["name"]
        if (imo, port_name) in confirmed_keys:
            continue

        if dist > INNER_KM:
            speed = in_transit.get("speed", 99) or 0.0
            closing = speed < SLOW_KN
            if not closing:
                course = in_transit.get("course")
                if course is not None:
                    brg = bearing_deg(lat, lon, port["lat"], port["lon"])
                    closing = angular_diff(course, brg) <= HEADING_TOL
            if not closing:
                continue

        cargo = estimate_cargo(
            length=record.get("length", 0),
            beam=record.get("beam", 0),
            draught=in_transit.get("draught", 0),
            ship_type=record.get("ship_type", "product"),
        )
        new_rows.append({
            "imo": imo,
            "name": record.get("name", "Unknown"),
            "port": port_name,
            "timestamp": last,
            "ship_type": record.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
            "coastal": False,
            "status": "probable",
        })
        record["probable_arrival"] = {"port": port_name, "since": now}

    return new_rows
```

Note: `estimate_cargo` is already imported at the top of `pipeline/arrivals.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_arrivals.py -k probable -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Run the full arrivals suite (no regressions)**

Run: `python -m pytest pipeline/tests/test_arrivals.py -q`
Expected: PASS (all)

- [ ] **Step 6: Commit**

```bash
git add pipeline/arrivals.py pipeline/tests/test_arrivals.py
git commit -m "feat(arrivals): add detect_probable_arrivals with tiered proximity gate"
```

---

## Task 3: Relax confirmed dedupe + `reconcile_probable_arrivals`

**Files:**
- Modify: `pipeline/arrivals.py` (`detect_arrivals`, `detect_silent_arrivals` dedupe; add `reconcile_probable_arrivals`)
- Test: `pipeline/tests/test_arrivals.py`

So a probable row never blocks a real berth detection, and so reappearances/confirmations clean up the probable row.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline/tests/test_arrivals.py`:

```python
from pipeline.arrivals import reconcile_probable_arrivals


def test_reconcile_upgrade_drops_probable_on_confirmed():
    # A confirmed arrival exists for the same (imo, port) as a probable row.
    db = _roster("2000001", _it(-38.13, 144.36))
    db["2000001"]["probable_arrival"] = {"port": "Geelong", "since": NOW}
    arrivals = [
        {"imo": "2000001", "port": "Geelong", "status": "probable", "cargo_litres": 1},
        {"imo": "2000001", "port": "Geelong", "status": "confirmed", "cargo_litres": 1},
    ]
    removed = reconcile_probable_arrivals(db, [], arrivals)
    assert removed == 1
    assert [a for a in arrivals if a.get("status") == "probable"] == []
    assert db["2000001"].get("probable_arrival") is None


def test_reconcile_reversal_when_vessel_reappears():
    # Marked probable, but the vessel pinged again this run and was NOT confirmed.
    db = _roster("2000002", _it(-38.13, 144.36))
    db["2000002"]["probable_arrival"] = {"port": "Geelong", "since": NOW}
    arrivals = [{"imo": "2000002", "port": "Geelong", "status": "probable", "cargo_litres": 1}]
    current = [{"imo": "2000002", "lat": -36.0, "lon": 144.0}]
    removed = reconcile_probable_arrivals(db, current, arrivals)
    assert removed == 1
    assert arrivals == []
    assert db["2000002"].get("probable_arrival") is None


def test_reconcile_keeps_probable_when_still_dark():
    db = _roster("2000003", _it(-38.13, 144.36))
    db["2000003"]["probable_arrival"] = {"port": "Geelong", "since": NOW}
    arrivals = [{"imo": "2000003", "port": "Geelong", "status": "probable", "cargo_litres": 1}]
    removed = reconcile_probable_arrivals(db, [], arrivals)
    assert removed == 0
    assert len(arrivals) == 1
    assert db["2000003"]["probable_arrival"] is not None


def test_detect_arrivals_not_blocked_by_probable_row():
    # Existing probable row must NOT prevent a confirmed arrival being detected.
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    db = _roster("2000004", _it(-38.15, 144.36))
    existing = [{"imo": "2000004", "port": "Geelong", "status": "probable"}]
    snapshot = {"vessels": [{
        "imo": "2000004", "name": "PROB TANKER", "lat": -38.15, "lon": 144.36,
        "speed": 0.2, "ship_type": "product", "length": 183, "beam": 32,
        "draught": 11.0, "destination": "GEELONG",
    }]}
    rows = detect_arrivals(snapshot, db, ports, existing)
    assert len(rows) == 1
    assert rows[0]["port"] == "Geelong"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_arrivals.py -k "reconcile or not_blocked" -v`
Expected: FAIL — `ImportError` for `reconcile_probable_arrivals`, and `test_detect_arrivals_not_blocked_by_probable_row` fails (probable row currently blocks).

- [ ] **Step 3: Relax dedupe in both confirmed detectors**

In `pipeline/arrivals.py`, in `detect_arrivals`, change:

```python
    arrived_imos = {(a["imo"], a["port"]) for a in existing_arrivals}
```
to:
```python
    arrived_imos = {
        (a["imo"], a["port"]) for a in existing_arrivals
        if a.get("status") != "probable"
    }
```

Make the identical change to the `arrived_imos` line in `detect_silent_arrivals`.

- [ ] **Step 4: Implement `reconcile_probable_arrivals`**

Add after `detect_probable_arrivals` in `pipeline/arrivals.py`:

```python
def reconcile_probable_arrivals(
    vessel_db: dict,
    current_vessels: list[dict],
    arrivals: list[dict],
) -> int:
    """Resolve probable rows against confirmations and reappearances.

    1. Upgrade: drop any probable row whose (imo, port) now has a confirmed
       arrival (incl. backfilled probables superseded by a real berth).
    2. Reversal: for a record still marked probable that pinged this run but was
       NOT confirmed, the "vanished" inference is void — drop its probable row
       and clear the marker so it returns to normal in-transit tracking.

    Mutates `arrivals` in place. Returns the number of probable rows removed.
    """
    pinged = {v.get("imo", "") for v in current_vessels if v.get("imo")}
    confirmed_keys = {
        (a["imo"], a["port"]) for a in arrivals
        if a.get("status") != "probable"
    }

    removed = 0
    kept = []
    for a in arrivals:
        if a.get("status") == "probable" and (a["imo"], a["port"]) in confirmed_keys:
            removed += 1
            continue
        kept.append(a)
    arrivals[:] = kept

    for imo, record in vessel_db.items():
        pa = record.get("probable_arrival")
        if not pa:
            continue
        port = pa["port"]
        if (imo, port) in confirmed_keys:
            record["probable_arrival"] = None  # upgraded; row already dropped above
            continue
        if imo in pinged:
            before = len(arrivals)
            arrivals[:] = [
                a for a in arrivals
                if not (a.get("status") == "probable" and a["imo"] == imo and a["port"] == port)
            ]
            removed += before - len(arrivals)
            record["probable_arrival"] = None

    return removed
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_arrivals.py -q`
Expected: PASS (all, including the 4 new tests)

- [ ] **Step 6: Commit**

```bash
git add pipeline/arrivals.py pipeline/tests/test_arrivals.py
git commit -m "feat(arrivals): reconcile probable arrivals (upgrade + reversal); ignore probable rows in confirmed dedupe"
```

---

## Task 4: Finalize probables in the prune (no lost-log)

**Files:**
- Modify: `pipeline/vessels.py:277-293` (`prune_stale_in_transit`)
- Test: `pipeline/tests/test_vessels.py`

A still-dark probable that ages out at 14 days must be kept (as our best estimate), not logged lost. Clearing the marker on finalization stops a future reappearance from wrongly reversing it.

- [ ] **Step 1: Write the failing tests**

Add to `pipeline/tests/test_vessels.py` (import `prune_stale_in_transit` if not already imported):

```python
from pipeline.vessels import prune_stale_in_transit


def _stale_record(marked: bool):
    rec = {
        "name": "FINAL TANKER", "ship_type": "product", "vessel_class": "MR",
        "arrival_count": 0, "departed_au_since_arrival": True,
        "in_transit": {
            "lat": -38.13, "lon": 144.36, "cargo_litres": 48000000,
            "cargo_tonnes": 40000, "is_ballast": False,
            "last_position_update": "2026-05-01T00:00:00+00:00",  # >14d before NOW
        },
    }
    if marked:
        rec["probable_arrival"] = {"port": "Geelong", "since": "2026-05-05T00:00:00+00:00"}
    return rec


def test_prune_marked_probable_is_finalized_not_lost():
    db = {"3000001": _stale_record(marked=True)}
    lost = []
    prune_stale_in_transit(db, now="2026-05-20T00:00:00+00:00", lost_log=lost)
    assert db["3000001"]["in_transit"] is None
    assert db["3000001"].get("probable_arrival") is None  # marker cleared
    assert lost == []  # NOT logged lost


def test_prune_unmarked_stale_still_logged_lost():
    db = {"3000002": _stale_record(marked=False)}
    lost = []
    prune_stale_in_transit(db, now="2026-05-20T00:00:00+00:00", lost_log=lost)
    assert db["3000002"]["in_transit"] is None
    assert len(lost) == 1
    assert lost[0]["reason"] == "stale_prune_14d"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_vessels.py -k "finalized or still_logged" -v`
Expected: FAIL — `test_prune_marked_probable_is_finalized_not_lost` logs a lost event (current behavior).

- [ ] **Step 3: Implement finalization in the prune**

In `pipeline/vessels.py`, change the tail of `prune_stale_in_transit`:

```python
        if last_dt < cutoff:
            _record_lost(record, imo, "stale_prune_14d", now, lost_log)
            record["in_transit"] = None
```
to:
```python
        if last_dt < cutoff:
            if record.get("probable_arrival"):
                # Already accounted as a probable arrival — finalize the trip:
                # keep the probable row, drop the marker (so a later reappearance
                # can't reverse it), and don't log it as lost.
                record["probable_arrival"] = None
            else:
                _record_lost(record, imo, "stale_prune_14d", now, lost_log)
            record["in_transit"] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_vessels.py -q`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "feat(vessels): finalize probable arrivals at 14d prune instead of logging lost"
```

---

## Task 5: Monthly split by status + en-route exclusion

**Files:**
- Modify: `pipeline/orchestrator.py` (`_empty_month_bucket`, `rebucket_monthly_from_arrivals`, en-route loop in `update_monthly_estimates`)
- Modify: `pipeline/daily_estimates.py` (`update_daily_estimates` en-route loop)
- Test: `pipeline/tests/test_orchestrator.py`

- [ ] **Step 1: Write the failing tests**

Add to `pipeline/tests/test_orchestrator.py` (import `rebucket_monthly_from_arrivals` and `update_monthly_estimates` if not already):

```python
from pipeline.orchestrator import rebucket_monthly_from_arrivals, update_monthly_estimates


def test_rebucket_splits_confirmed_and_probable():
    arrivals = [
        {"imo": "a", "port": "Geelong", "timestamp": "2026-05-03T00:00:00+00:00",
         "ship_type": "product", "cargo_litres": 100, "cargo_tonnes": 80, "status": "confirmed"},
        {"imo": "b", "port": "Geelong", "timestamp": "2026-05-04T00:00:00+00:00",
         "ship_type": "product", "cargo_litres": 40, "cargo_tonnes": 33, "status": "probable"},
        {"imo": "c", "port": "Brisbane", "timestamp": "2026-05-05T00:00:00+00:00",
         "ship_type": "crude", "cargo_litres": 90, "cargo_tonnes": 77},  # no status → confirmed
    ]
    monthly = rebucket_monthly_from_arrivals({"months": {}}, arrivals)
    m = monthly["months"]["2026-05"]
    assert m["arrived_product_litres"] == 100
    assert m["arrived_crude_litres"] == 90
    assert m["arrival_count"] == 2  # confirmed only
    assert m["probable_product_litres"] == 40
    assert m["probable_count"] == 1


def test_en_route_excludes_probable_marked_records():
    db = {
        "x": {"ship_type": "product", "departed_au_since_arrival": True,
              "in_transit": {"is_ballast": False, "cargo_litres": 500}},
        "y": {"ship_type": "product", "departed_au_since_arrival": True,
              "probable_arrival": {"port": "Geelong", "since": "z"},
              "in_transit": {"is_ballast": False, "cargo_litres": 999}},
    }
    monthly = update_monthly_estimates({"months": {}}, [], db,
                                       now=datetime(2026, 5, 20, tzinfo=timezone.utc))
    m = monthly["months"]["2026-05"]
    assert m["en_route_product_litres"] == 500  # y excluded
```

(Ensure `from datetime import datetime, timezone` is present in the test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_orchestrator.py -k "splits or en_route_excludes" -v`
Expected: FAIL — `KeyError: 'probable_product_litres'` and en-route includes 999.

- [ ] **Step 3: Add probable fields to the bucket**

In `pipeline/orchestrator.py`, change `_empty_month_bucket`:

```python
def _empty_month_bucket() -> dict:
    return {
        "arrived_crude_litres": 0,
        "arrived_product_litres": 0,
        "arrived_crude_tonnes": 0,
        "arrived_product_tonnes": 0,
        "arrival_count": 0,
        "probable_crude_litres": 0,
        "probable_product_litres": 0,
        "probable_crude_tonnes": 0,
        "probable_product_tonnes": 0,
        "probable_count": 0,
    }
```

- [ ] **Step 4: Split in `rebucket_monthly_from_arrivals`**

Replace the zeroing loop and the accumulation loop in `rebucket_monthly_from_arrivals`:

```python
    months = monthly.setdefault("months", {})
    for m in months.values():
        m["arrived_crude_litres"] = 0
        m["arrived_product_litres"] = 0
        m["arrived_crude_tonnes"] = 0
        m["arrived_product_tonnes"] = 0
        m["arrival_count"] = 0
        m["probable_crude_litres"] = 0
        m["probable_product_litres"] = 0
        m["probable_crude_tonnes"] = 0
        m["probable_product_tonnes"] = 0
        m["probable_count"] = 0

    for arrival in arrivals:
        if arrival.get("coastal"):
            continue
        ts = arrival.get("timestamp") or ""
        if len(ts) < 7:
            continue
        month_key = ts[:7]
        month = months.setdefault(month_key, _empty_month_bucket())
        is_probable = arrival.get("status") == "probable"
        is_crude = arrival["ship_type"] == "crude"
        if is_probable:
            month["probable_count"] += 1
            if is_crude:
                month["probable_crude_litres"] += arrival["cargo_litres"]
                month["probable_crude_tonnes"] += arrival["cargo_tonnes"]
            else:
                month["probable_product_litres"] += arrival["cargo_litres"]
                month["probable_product_tonnes"] += arrival["cargo_tonnes"]
        else:
            month["arrival_count"] += 1
            if is_crude:
                month["arrived_crude_litres"] += arrival["cargo_litres"]
                month["arrived_crude_tonnes"] += arrival["cargo_tonnes"]
            else:
                month["arrived_product_litres"] += arrival["cargo_litres"]
                month["arrived_product_tonnes"] += arrival["cargo_tonnes"]

    return monthly
```

- [ ] **Step 5: Exclude marked records from en-route sums**

In `pipeline/orchestrator.py`, in `update_monthly_estimates`, inside the `for record in vessel_db.values():` en-route loop, add after the `in_transit`/`is_ballast` guards and before the ship_type split:

```python
        if record.get("probable_arrival"):
            continue
```

In `pipeline/daily_estimates.py`, in `update_daily_estimates`, inside its `for record in vessel_db.values():` loop, add the same guard after the existing `is_ballast` / `departed_au_since_arrival` checks:

```python
        if record.get("probable_arrival"):
            continue
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_orchestrator.py pipeline/tests/test_daily_estimates.py -q`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add pipeline/orchestrator.py pipeline/daily_estimates.py pipeline/tests/test_orchestrator.py
git commit -m "feat(estimates): split monthly totals into confirmed/probable; exclude probables from en-route"
```

---

## Task 6: Wire the new passes into the orchestrator

**Files:**
- Modify: `pipeline/orchestrator.py` (`run_pipeline`)

Insert `detect_probable_arrivals` after the confirmed-arrival passes (before `update_vessel_db`), and `reconcile_probable_arrivals` after `update_vessel_db`.

- [ ] **Step 1: Update the import**

In `pipeline/orchestrator.py`, change:

```python
from pipeline.arrivals import detect_arrivals, detect_silent_arrivals, load_ports
```
to:
```python
from pipeline.arrivals import (
    detect_arrivals,
    detect_silent_arrivals,
    detect_probable_arrivals,
    reconcile_probable_arrivals,
    load_ports,
)
```

- [ ] **Step 2: Insert the probable-detection step**

In `run_pipeline`, immediately after the `detect_arrivals` block (`arrivals_data["arrivals"].extend(new_arrivals)` … `print(f"  {len(new_arrivals)} new arrivals detected")`) and before `print("Step 3: Updating vessel database...")`, insert:

```python
    print("Step 2c: Detecting probable arrivals (approached then vanished)...")
    probable = detect_probable_arrivals(
        vessel_db, ports, current_snapshot["vessels"], arrivals_data["arrivals"], now.isoformat()
    )
    arrivals_data["arrivals"].extend(probable)
    if probable:
        print(f"  {len(probable)} probable arrival(s) inferred from vanished in-transit vessels")
```

- [ ] **Step 3: Insert the reconcile step**

Immediately after the `update_vessel_db` block (`vessel_db = update_vessel_db(...)`, `save_json(.../vessels.json, vessel_db)`, `print(f"  {len(vessel_db)} vessels in database")`) and before the `if new_lost:` block, insert:

```python
    reversed_count = reconcile_probable_arrivals(
        vessel_db, current_snapshot["vessels"], arrivals_data["arrivals"]
    )
    if reversed_count:
        print(f"  Reconciled {reversed_count} probable arrival(s) (upgraded to confirmed or reversed)")
    save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)
    save_json(f"{DATA_DIR}/vessels.json", vessel_db)
```

(The extra `save_json` calls persist the probable rows, reconciled arrivals, and cleared markers. The earlier `save_json` after `detect_arrivals` stays; this re-save reflects post-reconcile state.)

- [ ] **Step 4: Verify the full pipeline test suite passes**

Run: `python -m pytest pipeline/tests/ -q`
Expected: PASS (all). The orchestrator's `run_pipeline` is not unit-tested end-to-end (it needs a live socket), so this verifies the helper-level tests and imports resolve.

- [ ] **Step 5: Smoke-test the wiring offline**

Run:
```bash
python -c "import pipeline.orchestrator as o; print('import OK'); print(hasattr(o, 'reconcile_probable_arrivals') or 'detect_probable_arrivals' in dir(__import__('pipeline.arrivals', fromlist=['x'])))"
```
Expected: prints `import OK` then `True`.

- [ ] **Step 6: Commit**

```bash
git add pipeline/orchestrator.py
git commit -m "feat(orchestrator): wire probable-arrival detection and reconciliation into nightly run"
```

---

## Task 7: Idempotent backfill from `lost-vessels.json`

**Files:**
- Create: `pipeline/backfill_probable.py`
- Modify: `pipeline/orchestrator.py` (call backfill as a migration before Step 4)
- Test: `pipeline/tests/test_backfill_probable.py`

Inner-band (≤50 km) only — see spec: no heading data in lost records, and backfilled false positives are not self-correcting.

- [ ] **Step 1: Write the failing tests**

Create `pipeline/tests/test_backfill_probable.py`:

```python
from pipeline.backfill_probable import backfill_probable_arrivals

PORTS = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]


def _event(imo, lat, lon, **kw):
    e = {
        "imo": imo, "name": "LOST TANKER", "ship_type": "product",
        "vessel_class": "MR", "cargo_litres": 48000000, "cargo_tonnes": 40000,
        "is_ballast": False, "last_lat": lat, "last_lon": lon,
        "last_position_update": "2026-05-05T00:00:00+00:00",
        "reason": "stale_prune_14d",
    }
    e.update(kw)
    return e


def test_backfill_recovers_inner_band():
    lost = {"events": [_event("9000001", -38.13, 144.36)]}  # ~3km from Geelong
    arrivals = {"arrivals": []}
    added = backfill_probable_arrivals(lost, arrivals, PORTS)
    assert added == 1
    row = arrivals["arrivals"][0]
    assert row["status"] == "probable" and row["port"] == "Geelong"
    assert row["timestamp"] == "2026-05-05T00:00:00+00:00"
    assert lost["events"][0]["recovered_as"] == "probable"


def test_backfill_skips_outer_band():
    lost = {"events": [_event("9000002", -38.95, 144.36)]}  # ~90km from Geelong
    arrivals = {"arrivals": []}
    assert backfill_probable_arrivals(lost, arrivals, PORTS) == 0
    assert arrivals["arrivals"] == []


def test_backfill_skips_ballast():
    lost = {"events": [_event("9000003", -38.13, 144.36, is_ballast=True)]}
    arrivals = {"arrivals": []}
    assert backfill_probable_arrivals(lost, arrivals, PORTS) == 0


def test_backfill_is_idempotent():
    lost = {"events": [_event("9000004", -38.13, 144.36)]}
    arrivals = {"arrivals": []}
    assert backfill_probable_arrivals(lost, arrivals, PORTS) == 1
    assert backfill_probable_arrivals(lost, arrivals, PORTS) == 0  # already recovered
    assert len(arrivals["arrivals"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_backfill_probable.py -v`
Expected: FAIL — module `pipeline.backfill_probable` does not exist.

- [ ] **Step 3: Implement the backfill**

Create `pipeline/backfill_probable.py`:

```python
"""One-shot, idempotent recovery of historical probable arrivals.

Reprocesses data/lost-vessels.json events (vessels pruned at 14-day staleness
without an arrival) into probable arrival rows, using the inner-band proximity
gate only. Lost records store no speed/course, so the outer-band kinematic
check (see pipeline.arrivals) cannot be applied retroactively; a backfilled
false positive is also not self-correcting (reversal only fires on vessels that
reappear live). So we recover only the unambiguous inner-band cases.
"""

from pipeline.arrivals import haversine_km, INNER_KM


def backfill_probable_arrivals(lost_vessels: dict, arrivals_data: dict, ports: list[dict]) -> int:
    """Append probable rows for inner-band lost vessels. Marks each recovered
    event with recovered_as="probable" so re-runs are no-ops. Returns the count
    added."""
    arrivals = arrivals_data.setdefault("arrivals", [])
    existing_keys = {(a["imo"], a["port"]) for a in arrivals}

    added = 0
    for event in lost_vessels.get("events", []):
        if event.get("recovered_as"):
            continue
        if event.get("is_ballast"):
            continue
        lat, lon = event.get("last_lat"), event.get("last_lon")
        if lat is None or lon is None:
            continue
        port = min(ports, key=lambda p: haversine_km(lat, lon, p["lat"], p["lon"]))
        dist = haversine_km(lat, lon, port["lat"], port["lon"])
        if dist > INNER_KM:
            continue
        key = (event["imo"], port["name"])
        if key in existing_keys:
            event["recovered_as"] = "probable"
            continue
        arrivals.append({
            "imo": event["imo"],
            "name": event.get("name", "Unknown"),
            "port": port["name"],
            "timestamp": event.get("last_position_update"),
            "ship_type": event.get("ship_type", "product"),
            "vessel_class": event.get("vessel_class"),
            "cargo_tonnes": event.get("cargo_tonnes", 0),
            "cargo_litres": event.get("cargo_litres", 0),
            "draught_missing": False,
            "coastal": False,
            "status": "probable",
        })
        existing_keys.add(key)
        event["recovered_as"] = "probable"
        added += 1

    return added
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest pipeline/tests/test_backfill_probable.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Wire backfill into the orchestrator as a migration**

In `pipeline/orchestrator.py`, add the import near the other pipeline imports:

```python
from pipeline.backfill_probable import backfill_probable_arrivals
```

In `run_pipeline`, in the migration block near the top (after `revalidated = revalidate_in_transit(...)` and before `print("Step 1: Collecting...")`), add:

```python
    backfilled = backfill_probable_arrivals(lost_vessels, arrivals_data, ports)
    if backfilled:
        print(f"Backfill: recovered {backfilled} probable arrival(s) from lost-vessels.json")
        save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)
        save_json(f"{DATA_DIR}/lost-vessels.json", lost_vessels)
```

(`lost_vessels`, `arrivals_data`, and `ports` are all already loaded above this point in `run_pipeline`.)

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest pipeline/tests/ -q`
Expected: PASS (all)

- [ ] **Step 7: Commit**

```bash
git add pipeline/backfill_probable.py pipeline/orchestrator.py pipeline/tests/test_backfill_probable.py
git commit -m "feat(pipeline): idempotent backfill of probable arrivals from lost-vessels.json"
```

---

## Task 8: Apply the backfill + rebucket to live data

**Files:**
- Modify (data): `data/arrivals.json`, `data/lost-vessels.json`, `data/monthly-estimates.json`

This produces the actual May/April numbers without waiting for a nightly run. Run a small script that performs exactly the backfill + rebucket the orchestrator would.

- [ ] **Step 1: Run the one-shot data update**

Run:
```bash
cd /Users/James/Documents/Claude/Projects/aus-fuel-import-monitor
python -c "
import json
from pipeline.arrivals import load_ports
from pipeline.backfill_probable import backfill_probable_arrivals
from pipeline.orchestrator import rebucket_monthly_from_arrivals
ports = load_ports('data/ports.json')
arrivals = json.load(open('data/arrivals.json'))
lost = json.load(open('data/lost-vessels.json'))
monthly = json.load(open('data/monthly-estimates.json'))
n = backfill_probable_arrivals(lost, arrivals, ports)
monthly = rebucket_monthly_from_arrivals(monthly, arrivals['arrivals'])
json.dump(arrivals, open('data/arrivals.json','w'), indent=2)
json.dump(lost, open('data/lost-vessels.json','w'), indent=2)
json.dump(monthly, open('data/monthly-estimates.json','w'), indent=2)
m = monthly['months']['2026-05']
print(f'backfilled {n}')
print('May confirmed product/crude:', m['arrived_product_litres']//10**6, m['arrived_crude_litres']//10**6, 'ML')
print('May probable product/crude:', m['probable_product_litres']//10**6, m['probable_crude_litres']//10**6, 'ML')
"
```
Expected: `backfilled 48` (April+May inner-band events); May probable ≈ 418 product + 281 crude ML; confirmed unchanged at 1939 / 543 ML.

- [ ] **Step 2: Sanity-check the totals match the spec**

Expected May confirmed+probable: crude ≈ 824 ML, product ≈ 2,357 ML, total ≈ 3,181 ML. If the numbers differ materially from the spec's impact table, STOP and investigate before committing.

- [ ] **Step 3: Commit the regenerated data**

```bash
git add data/arrivals.json data/lost-vessels.json data/monthly-estimates.json
git commit -m "data: backfill probable arrivals and rebucket monthly estimates"
```

---

## Task 9: Dashboard types — `probable_*` on `MonthEstimate`

**Files:**
- Modify: `src/lib/types.ts:78-87` (`MonthEstimate`)

- [ ] **Step 1: Add the optional probable fields**

In `src/lib/types.ts`, change the `MonthEstimate` interface to add the five probable fields (optional, so older data without them still type-checks):

```typescript
export interface MonthEstimate {
  arrived_crude_litres: number;
  arrived_product_litres: number;
  arrived_crude_tonnes: number;
  arrived_product_tonnes: number;
  en_route_crude_litres: number;
  en_route_product_litres: number;
  probable_crude_litres?: number;
  probable_product_litres?: number;
  probable_crude_tonnes?: number;
  probable_product_tonnes?: number;
  probable_count?: number;
  // keep any existing trailing fields (e.g. arrival_count, last_updated) below
}
```

Preserve every field already present in the interface (do not drop `arrival_count` / `last_updated` if they exist) — only add the five `probable_*` lines.

- [ ] **Step 2: Verify the type-checks/build pass**

Run: `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add src/lib/types.ts
git commit -m "feat(types): add probable_* fields to MonthEstimate"
```

---

## Task 10: Dashboard — stack the probable band in `HistoricalChart`

**Files:**
- Modify: `src/components/HistoricalChart.tsx`

Add a distinct stacked segment above the confirmed bars for AIS months, with legend + tooltip support.

- [ ] **Step 1: Extend `ChartRow` and `FUEL_*` maps**

In `src/components/HistoricalChart.tsx`, add two fields to `interface ChartRow` (after `product`):

```typescript
  probable_crude: number;
  probable_product: number;
```

Add to `FUEL_COLORS` (after `product`):

```typescript
  probable_crude: "#9ca3af",
  probable_product: "#cbd5e1",
```

Add to `FUEL_LABELS`:

```typescript
  probable_crude: "Crude (probable)",
  probable_product: "Product (probable)",
```

Do NOT add the probable keys to `FUEL_ORDER` (that array drives the confirmed tooltip rows; the probable split is shown separately in Step 4).

- [ ] **Step 2: Populate the probable fields for AIS months**

In the `if ((isCurrent || hasFullAisCoverage) && est) {` branch, after the existing `productMl` line, add:

```typescript
        const probCrudeMl = (est.probable_crude_litres ?? 0) / 1_000_000;
        const probProductMl = (est.probable_product_litres ?? 0) / 1_000_000;
```

and add to the `chartData.push({ ... })` object (after `product: Math.round(productMl),`):

```typescript
          probable_crude: Math.round(probCrudeMl),
          probable_product: Math.round(probProductMl),
```

Then add `probable_crude: 0, probable_product: 0,` to the **other** two `chartData.push` objects (the government-data loop near the top, and the `no_data` else-branch) so every row has the fields.

- [ ] **Step 3: Render the probable bars**

In the JSX, immediately after the existing `<Bar dataKey="product" ...>...</Bar>` block and before the `no_data` Bar, add two bars drawn as a lighter, dashed-outline "cap":

```tsx
          <Bar dataKey="probable_crude" name="Crude (probable)" stackId="fuel" fill={FUEL_COLORS.probable_crude}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "no_data" ? 0 : 0.25}
                strokeDasharray="3 2" stroke={entry.source === "no_data" ? undefined : "#6b7280"} />
            ))}
          </Bar>
          <Bar dataKey="probable_product" name="Product (probable)" stackId="fuel" fill={FUEL_COLORS.probable_product}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "no_data" ? 0 : 0.25}
                strokeDasharray="3 2" stroke={entry.source === "no_data" ? undefined : "#6b7280"} />
            ))}
          </Bar>
```

- [ ] **Step 4: Show the probable split in the tooltip**

In `CustomTooltip`, after the `FUEL_ORDER.filter(...)` block that lists confirmed fuels, add a probable line when present:

```tsx
      {row.source !== "no_data" && (row.probable_crude + row.probable_product) > 0 && (
        <div style={{ marginTop: 2, paddingTop: 2, borderTop: "1px dashed #d1d5db", color: "#6b7280" }}>
          + probable: {row.probable_crude + row.probable_product} ML
        </div>
      )}
```

- [ ] **Step 5: Add a legend hint**

In the bottom legend `<div className="flex flex-wrap gap-4 ...">`, add a final span:

```tsx
        {chartData.some((r) => (r.probable_crude + r.probable_product) > 0) && (
          <span><span className="inline-block w-3 h-3 mr-1 align-middle border border-dashed border-border-heavy" style={{ background: "#cbd5e1", opacity: 0.4 }} /> Lighter cap = probable arrivals (AIS-inferred)</span>
        )}
```

- [ ] **Step 6: Verify build + visual check**

Run: `npx tsc --noEmit && npm run build`
Expected: build succeeds with no type errors.

Then run `npm run dev` and confirm the current/AIS months show a lighter dashed cap above the solid arrivals bar, the legend entry appears, and the tooltip shows "+ probable: N ML". (See `superpowers:verification-before-completion` before claiming done.)

- [ ] **Step 7: Commit**

```bash
git add src/components/HistoricalChart.tsx
git commit -m "feat(dashboard): stack probable-arrival band on the imports chart"
```

---

## Task 11: Full-suite regression + final verification

- [ ] **Step 1: Run the entire pipeline test suite**

Run: `python -m pytest pipeline/tests/ -q`
Expected: PASS (all), including every new test from Tasks 1-7.

- [ ] **Step 2: Type-check + build the dashboard**

Run: `npx tsc --noEmit && npm run build`
Expected: success.

- [ ] **Step 3: Confirm the data reconciles**

Run:
```bash
python -c "
import json
m = json.load(open('data/monthly-estimates.json'))['months']['2026-05']
conf = (m['arrived_crude_litres']+m['arrived_product_litres'])//10**6
prob = (m['probable_crude_litres']+m['probable_product_litres'])//10**6
print(f'May confirmed {conf} ML + probable {prob} ML = {conf+prob} ML')
assert 3100 <= conf+prob <= 3260, 'May total outside expected ~3,181 ML band'
print('OK')
"
```
Expected: `May confirmed 2482 ML + probable 699 ML = 3181 ML` then `OK`.

- [ ] **Step 4: Final commit (if any uncommitted changes remain)**

```bash
git add -A && git commit -m "chore: probable-arrivals feature complete" || echo "nothing to commit"
```

---

## Notes / Known limitations (from spec)

- **Repeat same-port visitors:** if a vessel's probable arrival is finalized, then on a later voyage it genuinely berths at the *same* port, the upgrade-dedupe will drop the old probable in favour of the new confirmed row. Volume-neutral in practice; acceptable for an experimental dataset.
- **Backfill is inner-band only** (≤50 km), by design — no heading data in lost records and no self-correction for historical false positives.
- **Out of scope:** improving raw AIS collection coverage (the never-tracked product-tanker gap). That is the logical follow-up project.
