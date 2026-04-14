"""Daily en-route volume aggregation from the in-transit roster."""

from __future__ import annotations

from datetime import datetime


def update_daily_estimates(daily: dict, vessel_db: dict, now: datetime) -> dict:
    """Write today's en-route totals into daily["days"][YYYY-MM-DD].

    Sums cargo_litres from each record's in_transit block, grouped by
    ship_type. Skips ballast vessels and arrived records (in_transit=None).
    Overwrites any prior entry for today's UTC date.
    """
    day_key = now.strftime("%Y-%m-%d")

    crude = 0
    product = 0
    for record in vessel_db.values():
        in_transit = record.get("in_transit")
        if not in_transit:
            continue
        if in_transit.get("is_ballast"):
            continue
        cargo = in_transit.get("cargo_litres", 0)
        if record.get("ship_type") == "crude":
            crude += cargo
        else:
            product += cargo

    daily.setdefault("days", {})[day_key] = {
        "en_route_crude_litres": crude,
        "en_route_product_litres": product,
        "captured_at": now.isoformat(),
    }

    return daily
