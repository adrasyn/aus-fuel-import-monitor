"""Tanker ship-type classification and LNG exclusion.

AIS type codes 80-89 are all "Tanker" with only hazard-category subdivisions —
the protocol has no crude-vs-product distinction. Operators also routinely
broadcast generic code 80 regardless of actual cargo. So we can't trust the
AIS code and instead layer heuristics:

  1. LNG name-pattern filter — excludes methane / LNG / gas carriers entirely
     (project scope is "all liquid fuels excluding LNG").
  2. Optional per-IMO override file at data/vessel-overrides.json, keyed by
     IMO, values "crude" / "product" / "lng". Absent by default.
  3. Operator-prefix hints on the vessel name for a small set of globally
     recognisable fleets (HAFNIA, STI, TORM, etc.).
  4. Size-class fallback — Handysize / MR / LR2 default to product, Aframax
     and above default to crude. Reflects the practical reality of which
     hull sizes carry which cargo.

The override file is optional enrichment: when present it wins, when absent
the heuristics do the work. Maintaining it is never a requirement.
"""

from __future__ import annotations

import json
import os
import re

_LNG_NAME_PATTERNS = [
    re.compile(r"\bMETHANE\b", re.IGNORECASE),
    re.compile(r"\bLNG\b", re.IGNORECASE),
    re.compile(r"\bGAS CARRIER\b", re.IGNORECASE),
]

# Operator-prefix hints keyed on the first whitespace-delimited token of the
# vessel name (uppercased). Kept conservative — only globally recognisable
# fleets whose misattribution risk is low.
_OPERATOR_HINTS: dict[str, str] = {
    "HAFNIA": "product",
    "TORM": "product",
    "STI": "product",       # Scorpio Tankers
    "MAERSK": "product",
    "ARDMORE": "product",
    "FRONTLINE": "crude",
    "EURONAV": "crude",
}

# Size-class default. Reflects that MR-and-below tonnage almost always carries
# clean products, and Aframax-and-above almost always carries crude.
_CLASS_DEFAULT: dict[str, str] = {
    "VLCC": "crude",
    "Suezmax": "crude",
    "Aframax": "crude",
    "LR2/Panamax": "product",
    "MR": "product",
    "Handysize": "product",
}


def is_lng_carrier(name: str | None) -> bool:
    """True if the vessel name matches an LNG / gas-carrier pattern."""
    if not name:
        return False
    return any(p.search(name) for p in _LNG_NAME_PATTERNS)


def load_overrides(path: str = "data/vessel-overrides.json") -> dict[str, str]:
    """Load the optional per-IMO override file. Returns {} if absent or
    unreadable — overrides are an enrichment, not a dependency."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v).lower() for k, v in data.items()}


def classify_ship_type(
    name: str | None,
    vessel_class: str,
    imo: str | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """Classify a tanker as 'crude' or 'product'.

    Assumes the caller has already run is_lng_carrier and excluded matches —
    this function is only called for non-LNG tankers we intend to keep.

    Precedence:
      1. Override for this IMO (if supplied and present).
      2. Operator-prefix hint on the vessel name.
      3. Size-class default.
      4. 'product' as a last resort (safest for miscategorised MR-class).
    """
    if overrides and imo and imo in overrides:
        override = overrides[imo]
        if override in ("crude", "product"):
            return override
    first_token = ""
    if name:
        stripped = name.strip()
        if stripped:
            first_token = stripped.split()[0].upper()
    if first_token in _OPERATOR_HINTS:
        return _OPERATOR_HINTS[first_token]
    return _CLASS_DEFAULT.get(vessel_class, "product")
