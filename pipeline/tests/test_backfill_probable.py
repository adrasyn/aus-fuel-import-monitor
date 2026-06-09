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
