"""Vessel database management, keyed by IMO number."""

from datetime import datetime, timezone
from pipeline.cargo import classify_vessel, TANKER_CLASSES


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
