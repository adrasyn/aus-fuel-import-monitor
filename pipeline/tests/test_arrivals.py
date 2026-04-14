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
