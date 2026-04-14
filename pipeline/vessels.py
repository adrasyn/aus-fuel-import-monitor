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


def update_vessel_db(db: dict, vessels: list[dict], new_arrivals: list[dict] | None = None) -> dict:
    now = datetime.now(timezone.utc).isoformat()

    for vessel in vessels:
        imo = vessel.get("imo", "")
        if not imo:
            continue

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

    if new_arrivals:
        for arrival in new_arrivals:
            imo = arrival.get("imo", "")
            if imo in db:
                db[imo]["arrival_count"] += 1

    return db
