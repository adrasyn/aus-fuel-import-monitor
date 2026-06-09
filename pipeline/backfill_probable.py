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
