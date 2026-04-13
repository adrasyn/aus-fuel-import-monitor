"""Vessel classification, DWT estimation, and cargo volume calculation."""

TANKER_CLASSES = {
    "VLCC": {
        "min_length": 300, "min_beam": 55,
        "dwt": 260000,
        "ballast_draught": 8.0, "laden_draught": 16.5,
    },
    "Suezmax": {
        "min_length": 250, "min_beam": 44,
        "dwt": 160000,
        "ballast_draught": 7.0, "laden_draught": 17.0,
    },
    "Aframax": {
        "min_length": 220, "min_beam": 40,
        "dwt": 100000,
        "ballast_draught": 6.5, "laden_draught": 15.0,
    },
    "LR2/Panamax": {
        "min_length": 200, "min_beam": 30,
        "dwt": 70000,
        "ballast_draught": 6.0, "laden_draught": 13.5,
    },
    "MR": {
        "min_length": 160, "min_beam": 27,
        "dwt": 40000,
        "ballast_draught": 5.0, "laden_draught": 11.5,
    },
    "Handysize": {
        "min_length": 0, "min_beam": 0,
        "dwt": 17000,
        "ballast_draught": 4.0, "laden_draught": 9.5,
    },
}

_CLASS_ORDER = ["VLCC", "Suezmax", "Aframax", "LR2/Panamax", "MR", "Handysize"]

FUEL_DENSITIES = {
    "crude": {"density_kg_m3": 860, "litres_per_tonne": 1163},
    "product": {"density_kg_m3": 820, "litres_per_tonne": 1220},
}

BALLAST_THRESHOLD = 0.15
DEFAULT_LOAD_FACTOR = 0.75


def classify_vessel(length: float, beam: float) -> str:
    for cls_name in _CLASS_ORDER:
        cls = TANKER_CLASSES[cls_name]
        if length >= cls["min_length"] and beam >= cls["min_beam"]:
            return cls_name
    return "Handysize"


def estimate_load_factor(draught: float, vessel_class: str) -> float:
    if draught <= 0:
        return DEFAULT_LOAD_FACTOR
    cls = TANKER_CLASSES[vessel_class]
    ballast = cls["ballast_draught"]
    laden = cls["laden_draught"]
    factor = (draught - ballast) / (laden - ballast)
    return max(0.0, min(1.0, factor))


def estimate_cargo(length: float, beam: float, draught: float, ship_type: str) -> dict:
    vessel_class = classify_vessel(length, beam)
    dwt = TANKER_CLASSES[vessel_class]["dwt"]
    draught_missing = draught <= 0
    load_factor = estimate_load_factor(draught, vessel_class)
    is_ballast = load_factor < BALLAST_THRESHOLD and not draught_missing
    cargo_tonnes = dwt * load_factor
    fuel = FUEL_DENSITIES.get(ship_type, FUEL_DENSITIES["product"])
    cargo_litres = cargo_tonnes * fuel["litres_per_tonne"]
    return {
        "vessel_class": vessel_class,
        "dwt": dwt,
        "load_factor": round(load_factor, 3),
        "cargo_tonnes": round(cargo_tonnes),
        "cargo_litres": round(cargo_litres),
        "is_ballast": is_ballast,
        "draught_missing": draught_missing,
    }
