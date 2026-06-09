from pipeline.arrivals import (
    haversine_km,
    bearing_deg,
    angular_diff,
    is_within_port,
    detect_arrivals,
    detect_silent_arrivals,
    detect_probable_arrivals,
    reconcile_probable_arrivals,
)


def test_haversine_known_distance():
    dist = haversine_km(-33.87, 151.21, -37.81, 144.96)
    assert 700 < dist < 730


def test_haversine_same_point():
    dist = haversine_km(-33.87, 151.21, -33.87, 151.21)
    assert dist == 0.0


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


def test_detect_arrivals_stamps_coastal_false_when_vessel_has_departed():
    # Default case: vessel was on an international leg, departed_au flag True.
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -36.0, "lon": 144.0, "speed": 12.0, "destination": "GEELONG",
        "last_position_update": "2026-04-13T22:00:00Z",
    })
    vessel_db["1234567"]["departed_au_since_arrival"] = True
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 1
    assert new_arrivals[0]["coastal"] is False


def test_detect_arrivals_stamps_coastal_true_when_vessel_on_coastal_hop():
    # Vessel arrived previously and hasn't been observed offshore — coastal.
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    vessel_db = _vessel_db_with("1234567", in_transit={
        "lat": -36.0, "lon": 144.0, "speed": 12.0, "destination": "GEELONG",
        "last_position_update": "2026-04-13T22:00:00Z",
    })
    vessel_db["1234567"]["departed_au_since_arrival"] = False
    vessel_db["1234567"]["arrival_count"] = 1
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    new_arrivals = detect_arrivals(current_snapshot, vessel_db, ports, [])
    assert len(new_arrivals) == 1
    assert new_arrivals[0]["coastal"] is True


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


# ---------- detect_silent_arrivals ----------


def _silent_record(imo: str, lat: float, lon: float, speed: float = 0.0,
                   ship_type: str = "product", arrival_count: int = 0,
                   departed: bool = True) -> dict:
    return {
        imo: {
            "name": "Silent Tanker",
            "vessel_class": "MR",
            "dwt": 50000,
            "length": 183,
            "beam": 32,
            "ship_type": ship_type,
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-15T00:00:00Z",
            "arrival_count": arrival_count,
            "departed_au_since_arrival": departed,
            "in_transit": {
                "lat": lat,
                "lon": lon,
                "speed": speed,
                "draught": 9.0,
                "destination": "AU FRE",
                "destination_parsed": "Fremantle",
                "region": "AU_APPROACH",
                "cargo_litres": 50_000_000,
                "cargo_tonnes": 40_000,
                "load_factor": 0.9,
                "is_ballast": False,
                "draught_missing": False,
                "last_position_update": "2026-04-15T00:00:00Z",
            },
        }
    }


def test_silent_arrival_detected_when_parked_at_port():
    ports = [{"name": "Fremantle", "lat": -32.05, "lon": 115.74, "radius_km": 5}]
    db = _silent_record("9000001", lat=-32.05, lon=115.74, speed=0.0)

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=[])

    assert len(arrivals) == 1
    assert arrivals[0]["port"] == "Fremantle"
    assert arrivals[0]["coastal"] is False  # departed=True → not coastal
    # Roster mutated: in_transit cleared, counters bumped, parked-flag set
    assert db["9000001"]["in_transit"] is None
    assert db["9000001"]["arrival_count"] == 1
    assert db["9000001"]["departed_au_since_arrival"] is False


def test_silent_arrival_skipped_when_moving():
    ports = [{"name": "Fremantle", "lat": -32.05, "lon": 115.74, "radius_km": 5}]
    db = _silent_record("9000002", lat=-32.05, lon=115.74, speed=8.0)

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=[])

    assert arrivals == []
    assert db["9000002"]["in_transit"] is not None


def test_silent_arrival_skipped_when_outside_port_radius():
    ports = [{"name": "Fremantle", "lat": -32.05, "lon": 115.74, "radius_km": 5}]
    # Far offshore — even at speed 0 (drifting), not at any port
    db = _silent_record("9000003", lat=-30.0, lon=110.0, speed=0.0)

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=[])

    assert arrivals == []
    assert db["9000003"]["in_transit"] is not None


def test_silent_arrival_dedupes_against_existing_record():
    # Vessel was already recorded as arrived on a prior run; sweep should clear
    # the lingering in_transit but NOT add a duplicate arrival row.
    ports = [{"name": "Fremantle", "lat": -32.05, "lon": 115.74, "radius_km": 5}]
    db = _silent_record(
        "9000004", lat=-32.05, lon=115.74, speed=0.0,
        arrival_count=1, departed=False,
    )
    existing = [{"imo": "9000004", "port": "Fremantle", "timestamp": "2026-04-10T00:00:00Z"}]

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=existing)

    assert arrivals == []
    assert db["9000004"]["in_transit"] is None
    # Counter not bumped — existing arrival was authoritative
    assert db["9000004"]["arrival_count"] == 1


def test_silent_arrival_marks_coastal_when_vessel_already_in_au():
    # Vessel previously arrived in AU and hasn't been observed offshore since
    # — its next "arrival" (e.g. from a coastal hop) is not a fresh import.
    ports = [{"name": "Brisbane", "lat": -27.38, "lon": 153.17, "radius_km": 5}]
    db = _silent_record(
        "9000005", lat=-27.38, lon=153.17, speed=0.0,
        arrival_count=1, departed=False,
    )

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=[])

    assert len(arrivals) == 1
    assert arrivals[0]["coastal"] is True
    assert db["9000005"]["arrival_count"] == 2


def test_silent_arrival_no_in_transit_skipped():
    # Vessel not currently in transit (already cleared) — nothing to do.
    db = {
        "9000006": {
            "name": "Done", "vessel_class": "MR", "dwt": 50000,
            "length": 183, "beam": 32, "ship_type": "product",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-15T00:00:00Z",
            "arrival_count": 1,
            "departed_au_since_arrival": False,
            "in_transit": None,
        }
    }
    ports = [{"name": "Fremantle", "lat": -32.05, "lon": 115.74, "radius_km": 5}]

    arrivals = detect_silent_arrivals(db, ports, existing_arrivals=[])

    assert arrivals == []


# ---------- detect_probable_arrivals ----------

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


def test_probable_outer_band_slow_speed_included():
    # ~90km south of Geelong, nearly stopped, pointed AWAY from port —
    # slow speed alone qualifies in the outer band, no heading check needed.
    db = _roster("1000010", _it(-38.95, 144.36, speed=0.5, course=180.0))
    rows = detect_probable_arrivals(db, PORTS, [], [], NOW)
    assert len(rows) == 1 and rows[0]["port"] == "Geelong"


def test_probable_already_marked_is_idempotent():
    # A record already carrying a probable_arrival marker must not be re-emitted.
    db = _roster("1000011", _it(-38.13, 144.36))
    first = detect_probable_arrivals(db, PORTS, [], [], NOW)
    assert len(first) == 1
    # Second call on the same (now-marked) db yields nothing new.
    second = detect_probable_arrivals(db, PORTS, [], first, NOW)
    assert second == []


# ---------- reconcile_probable_arrivals ----------


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
