"""One-shot, idempotent recovery of historical probable arrivals.

Reprocesses data/lost-vessels.json events (vessels pruned at 14-day staleness
without an arrival) into probable arrival rows, using the inner-band proximity
gate only. Lost records store no speed/course, so the outer-band kinematic
check (see pipeline.arrivals) cannot be applied retroactively; a backfilled
false positive is also not self-correcting (reversal only fires on vessels that
reappear live). So we recover only the unambiguous inner-band cases.
"""

from datetime import datetime

from pipeline.arrivals import haversine_km, INNER_KM

# A backfilled probable within this many days of a CONFIRMED arrival for the
# same vessel is treated as the same voyage (the dark fix was just nearest a
# different port than the berth) and suppressed, to avoid double-counting.
DEDUP_WINDOW_DAYS = 5


def _parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _has_nearby_confirmed(imo: str, ts: str, arrivals: list[dict]) -> bool:
    """True if the same vessel has a CONFIRMED arrival within DEDUP_WINDOW_DAYS
    of `ts` — i.e. the probable is almost certainly the same voyage."""
    t = _parse_iso(ts)
    if t is None:
        return False
    window = DEDUP_WINDOW_DAYS * 86400
    for a in arrivals:
        if a.get("imo") != imo or a.get("status") == "probable":
            continue
        at = _parse_iso(a.get("timestamp"))
        if at is None:
            continue
        if abs((at - t).total_seconds()) <= window:
            return True
    return False


def backfill_probable_arrivals(lost_vessels: dict, arrivals_data: dict, ports: list[dict]) -> int:
    """Append probable rows for inner-band lost vessels. Marks each recovered
    event with recovered_as="probable" so re-runs are no-ops. Returns the count
    added."""
    arrivals = arrivals_data.setdefault("arrivals", [])
    existing_keys = {(a["imo"], a["port"]) for a in arrivals if a.get("status") == "probable"}

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
        if _has_nearby_confirmed(event["imo"], event.get("last_position_update"), arrivals):
            event["recovered_as"] = "duplicate_of_confirmed"
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
