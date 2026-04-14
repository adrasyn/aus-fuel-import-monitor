"""Named geographic regions for AIS collection and their retention rules.

Each region is a ((lat_min, lon_min), (lat_max, lon_max)) box. Vessels
inside AU_APPROACH are kept unconditionally; vessels inside any other
region are kept only if their destination parses as Australian.
"""

from __future__ import annotations

REGIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "AU_APPROACH":   ((-50.0,   90.0), ( -5.0,  170.0)),
    "SE_ASIA":       (( -5.0,   95.0), ( 10.0,  120.0)),
    "PHILIPPINES":   ((  5.0,  117.0), ( 20.0,  127.0)),
    "CHINA":         (( 18.0,  108.0), ( 41.0,  125.0)),
    "KOREA_JAPAN":   (( 30.0,  125.0), ( 45.0,  145.0)),
    "INDIA":         ((  5.0,   65.0), ( 25.0,   90.0)),
    "MIDDLE_EAST":   (( 10.0,   40.0), ( 30.0,   80.0)),
    "US_GULF":       (( 18.0,  -98.0), ( 31.0,  -80.0)),
    "US_WEST_COAST": (( 25.0, -125.0), ( 50.0, -115.0)),
}


def classify_region(lat: float, lon: float) -> str | None:
    for name, ((lat_min, lon_min), (lat_max, lon_max)) in REGIONS.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return name
    return None


def should_keep_vessel(region: str | None, destination_parsed: str | None) -> bool:
    """Decide whether to keep a tanker based on its region and parsed destination.

    - AU_APPROACH: keep unconditionally (arrival zone).
    - Other known regions: keep only if destination parses as Australian.
    - Unknown region (outside every box): drop.
    """
    if region is None:
        return False
    if region == "AU_APPROACH":
        return True
    return destination_parsed is not None
