# Australian Fuel Import Monitor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static website that tracks oil/fuel tankers en route to Australia, updated nightly via GitHub Actions, deployed on GitHub Pages.

**Architecture:** Python data pipeline (AISStream WebSocket collector + government stats parser) produces JSON files committed to the repo. Next.js static export reads those JSON files at build time and renders an editorial-style dashboard with interactive map, vessel table, and historical chart. GitHub Actions orchestrates nightly: collect → process → build → deploy.

**Tech Stack:** Python 3.12+ (websockets, openpyxl, haversine), Next.js 14 (App Router, static export), Leaflet (react-leaflet), Recharts, Tailwind CSS, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-04-13-aus-fuel-import-monitor-design.md`

---

## File Structure

```
aus-fuel-shipments/
├── .github/workflows/
│   └── nightly-update.yml          # Cron job: collect → process → build → deploy
├── pipeline/
│   ├── requirements.txt             # Python dependencies
│   ├── cargo.py                     # Vessel classification, DWT estimation, cargo volume calc
│   ├── destinations.py              # Parse AIS destination strings → Australian port names
│   ├── arrivals.py                  # Port geofence arrival detection
│   ├── vessels.py                   # Vessel database management (keyed by IMO)
│   ├── collector.py                 # AISStream WebSocket collector
│   ├── petroleum_stats.py           # Australian Petroleum Statistics Excel parser
│   ├── orchestrator.py              # Runs full pipeline: collect → detect → update → build data
│   └── tests/
│       ├── test_cargo.py
│       ├── test_destinations.py
│       ├── test_arrivals.py
│       ├── test_vessels.py
│       └── test_petroleum_stats.py
├── data/
│   ├── ports.json                   # Static: Australian port coordinates + geofence radii
│   ├── snapshot.json                # Generated: current tankers en route
│   ├── arrivals.json                # Generated: cumulative arrival log
│   ├── vessels.json                 # Generated: vessel database by IMO
│   ├── monthly-estimates.json       # Generated: per-month arrived + en-route volumes
│   └── imports.json                 # Generated: government petroleum statistics
├── src/
│   ├── app/
│   │   ├── layout.tsx               # Root layout: fonts, metadata, global styles
│   │   ├── page.tsx                 # Main dashboard page: composes all sections
│   │   └── globals.css              # Tailwind directives + custom editorial styles
│   ├── components/
│   │   ├── Header.tsx               # Site name, headline sentence, update timestamp
│   │   ├── StatBar.tsx              # Row of headline stats (counts, volumes, reserve days)
│   │   ├── VesselMap.tsx            # Leaflet interactive map with tanker positions
│   │   ├── VesselTable.tsx          # Sortable vessel table with all columns
│   │   ├── HistoricalChart.tsx      # Stacked bar chart: govt data + AIS estimates + current month
│   │   ├── Footer.tsx               # Disclaimer + attribution
│   │   └── StaleBanner.tsx          # "Data last updated" warning banner
│   └── lib/
│       ├── types.ts                 # TypeScript interfaces for all data shapes
│       └── data.ts                  # Static data loading helpers (read JSON at build time)
├── public/
│   └── (static assets if needed)
├── package.json
├── next.config.ts                   # Static export config
├── tailwind.config.ts               # Tailwind with custom colours/fonts
└── tsconfig.json
```

---

## Phase 1: Project Scaffolding

### Task 1: Initialize repo and project structure

**Files:**
- Create: `package.json`, `next.config.ts`, `tailwind.config.ts`, `tsconfig.json`, `src/app/layout.tsx`, `src/app/page.tsx`, `src/app/globals.css`, `.gitignore`
- Create: `pipeline/requirements.txt`
- Create: `data/ports.json`

- [ ] **Step 1: Initialize git repo**

```bash
cd C:/Users/wilso/Documents/Claude/Projects/aus-fuel-shipments
git init
```

- [ ] **Step 2: Create .gitignore**

```gitignore
node_modules/
.next/
out/
__pycache__/
*.pyc
.env
.env.local
.superpowers/
```

- [ ] **Step 3: Create Next.js project**

```bash
npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --no-import-alias --use-npm
```

Accept defaults. This scaffolds the Next.js project with App Router, TypeScript, Tailwind, and ESLint.

- [ ] **Step 4: Configure Next.js for static export**

Replace `next.config.ts` with:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
```

- [ ] **Step 5: Configure Tailwind with custom theme**

Replace `tailwind.config.ts` with:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        crude: "#dc2626",
        product: "#1e40af",
        border: "#e2e8f0",
        "border-heavy": "#111827",
        label: "#6b7280",
        "label-light": "#9ca3af",
        panel: "#f8fafc",
      },
      fontFamily: {
        headline: ['"Instrument Serif"', "Georgia", "serif"],
        body: ['"Inter"', "system-ui", "sans-serif"],
      },
      letterSpacing: {
        label: "0.15em",
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 6: Set up global CSS**

Replace `src/app/globals.css` with:

```css
@import "tailwindcss";

@theme {
  --color-crude: #dc2626;
  --color-product: #1e40af;
  --color-border: #e2e8f0;
  --color-border-heavy: #111827;
  --color-label: #6b7280;
  --color-label-light: #9ca3af;
  --color-panel: #f8fafc;

  --font-headline: "Instrument Serif", Georgia, serif;
  --font-body: "Inter", system-ui, sans-serif;
}

body {
  font-family: var(--font-body);
  color: #111827;
  background: #ffffff;
}
```

- [ ] **Step 7: Set up root layout with fonts**

Replace `src/app/layout.tsx` with:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Australian Fuel Import Monitor",
  description:
    "Tracking oil and liquid fuel tankers en route to Australia. Updated nightly from AIS vessel tracking data.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Instrument+Serif&family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-body antialiased">{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create placeholder page**

Replace `src/app/page.tsx` with:

```tsx
export default function Home() {
  return (
    <main className="max-w-7xl mx-auto px-6 py-8">
      <div className="border-b-[2.5px] border-border-heavy pb-3 mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-1">
          Australian Fuel Import Monitor
        </p>
        <h1 className="font-headline text-2xl">
          Site under construction
        </h1>
      </div>
    </main>
  );
}
```

- [ ] **Step 9: Create Python pipeline directory and requirements**

Create `pipeline/requirements.txt`:

```
websockets>=12.0
openpyxl>=3.1.0
requests>=2.31.0
pytest>=8.0.0
```

- [ ] **Step 10: Create ports.json with Australian fuel port geofences**

Create `data/ports.json`:

```json
{
  "ports": [
    {
      "name": "Geelong",
      "lat": -38.1499,
      "lon": 144.3600,
      "radius_km": 5
    },
    {
      "name": "Melbourne",
      "lat": -37.8400,
      "lon": 144.9200,
      "radius_km": 5
    },
    {
      "name": "Sydney / Botany",
      "lat": -33.9700,
      "lon": 151.2100,
      "radius_km": 5
    },
    {
      "name": "Port Kembla",
      "lat": -34.4700,
      "lon": 150.9000,
      "radius_km": 5
    },
    {
      "name": "Brisbane",
      "lat": -27.3800,
      "lon": 153.1700,
      "radius_km": 5
    },
    {
      "name": "Gladstone",
      "lat": -23.8500,
      "lon": 151.2800,
      "radius_km": 5
    },
    {
      "name": "Fremantle",
      "lat": -32.0500,
      "lon": 115.7400,
      "radius_km": 5
    },
    {
      "name": "Adelaide",
      "lat": -34.7900,
      "lon": 138.4800,
      "radius_km": 5
    },
    {
      "name": "Darwin",
      "lat": -12.4300,
      "lon": 130.8500,
      "radius_km": 5
    },
    {
      "name": "Townsville",
      "lat": -19.2500,
      "lon": 146.7700,
      "radius_km": 5
    }
  ]
}
```

- [ ] **Step 11: Create seed data files for development**

Create `data/snapshot.json`:

```json
{
  "timestamp": "2026-04-13T16:00:00Z",
  "vessels": []
}
```

Create `data/arrivals.json`:

```json
{
  "arrivals": []
}
```

Create `data/vessels.json`:

```json
{}
```

Create `data/monthly-estimates.json`:

```json
{
  "months": {}
}
```

Create `data/imports.json`:

```json
{
  "imports_by_month": [],
  "consumption_cover": []
}
```

- [ ] **Step 12: Verify Next.js builds and runs**

```bash
npm run build
npm run start
```

Expected: Site builds successfully with static export. Opens in browser showing "Site under construction" with the editorial header style.

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "feat: scaffold project with Next.js, Tailwind, Python pipeline structure, and seed data"
```

---

## Phase 2: Python Pipeline — Core Modules

### Task 2: Cargo estimation module

**Files:**
- Create: `pipeline/cargo.py`
- Create: `pipeline/tests/test_cargo.py`

- [ ] **Step 1: Write failing tests for vessel classification and cargo estimation**

Create `pipeline/tests/__init__.py` (empty file).

Create `pipeline/tests/test_cargo.py`:

```python
from pipeline.cargo import classify_vessel, estimate_load_factor, estimate_cargo, TANKER_CLASSES


def test_classify_vlcc():
    result = classify_vessel(length=330, beam=60)
    assert result == "VLCC"


def test_classify_suezmax():
    result = classify_vessel(length=275, beam=50)
    assert result == "Suezmax"


def test_classify_aframax():
    result = classify_vessel(length=245, beam=44)
    assert result == "Aframax"


def test_classify_lr2():
    result = classify_vessel(length=220, beam=32)
    assert result == "LR2/Panamax"


def test_classify_mr():
    result = classify_vessel(length=183, beam=32)
    assert result == "MR"


def test_classify_handysize():
    result = classify_vessel(length=140, beam=22)
    assert result == "Handysize"


def test_load_factor_full():
    factor = estimate_load_factor(draught=16.0, vessel_class="VLCC")
    assert 0.9 < factor <= 1.0


def test_load_factor_ballast():
    factor = estimate_load_factor(draught=8.0, vessel_class="VLCC")
    assert factor < 0.15


def test_load_factor_missing_draught():
    factor = estimate_load_factor(draught=0.0, vessel_class="VLCC")
    assert factor == 0.75


def test_load_factor_clamps_to_zero():
    factor = estimate_load_factor(draught=1.0, vessel_class="VLCC")
    assert factor == 0.0


def test_load_factor_clamps_to_one():
    factor = estimate_load_factor(draught=25.0, vessel_class="VLCC")
    assert factor == 1.0


def test_estimate_cargo_crude():
    result = estimate_cargo(
        length=330, beam=60, draught=16.0, ship_type="crude"
    )
    assert result["vessel_class"] == "VLCC"
    assert result["cargo_tonnes"] > 200000
    assert result["cargo_litres"] > 0
    assert result["is_ballast"] is False
    assert result["draught_missing"] is False


def test_estimate_cargo_product():
    result = estimate_cargo(
        length=183, beam=32, draught=10.0, ship_type="product"
    )
    assert result["vessel_class"] == "MR"
    assert result["cargo_litres"] > result["cargo_tonnes"]  # litres > tonnes for product


def test_estimate_cargo_ballast_detected():
    result = estimate_cargo(
        length=330, beam=60, draught=8.0, ship_type="crude"
    )
    assert result["is_ballast"] is True


def test_estimate_cargo_missing_draught_flagged():
    result = estimate_cargo(
        length=245, beam=44, draught=0.0, ship_type="crude"
    )
    assert result["draught_missing"] is True
    assert result["cargo_tonnes"] > 0  # still estimates using 0.75
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:/Users/wilso/Documents/Claude/Projects/aus-fuel-shipments
python -m pytest pipeline/tests/test_cargo.py -v
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'pipeline.cargo'`

- [ ] **Step 3: Implement cargo estimation module**

Create `pipeline/__init__.py` (empty file).

Create `pipeline/cargo.py`:

```python
"""Vessel classification, DWT estimation, and cargo volume calculation."""

TANKER_CLASSES = {
    "VLCC": {
        "min_length": 300, "min_beam": 55,
        "dwt": 260000,
        "ballast_draught": 8.0, "laden_draught": 21.0,
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

# Ordered largest to smallest for classification
_CLASS_ORDER = ["VLCC", "Suezmax", "Aframax", "LR2/Panamax", "MR", "Handysize"]

# Density conversions: kg/m³ → litres per tonne = 1000 / density
FUEL_DENSITIES = {
    "crude": {"density_kg_m3": 860, "litres_per_tonne": 1163},
    "product": {"density_kg_m3": 820, "litres_per_tonne": 1220},
}

BALLAST_THRESHOLD = 0.15
DEFAULT_LOAD_FACTOR = 0.75


def classify_vessel(length: float, beam: float) -> str:
    """Classify a tanker into a size class based on dimensions."""
    for cls_name in _CLASS_ORDER:
        cls = TANKER_CLASSES[cls_name]
        if length >= cls["min_length"] and beam >= cls["min_beam"]:
            return cls_name
    return "Handysize"


def estimate_load_factor(draught: float, vessel_class: str) -> float:
    """Estimate how full a vessel is from its current draught."""
    if draught <= 0:
        return DEFAULT_LOAD_FACTOR

    cls = TANKER_CLASSES[vessel_class]
    ballast = cls["ballast_draught"]
    laden = cls["laden_draught"]

    factor = (draught - ballast) / (laden - ballast)
    return max(0.0, min(1.0, factor))


def estimate_cargo(
    length: float,
    beam: float,
    draught: float,
    ship_type: str,
) -> dict:
    """Full cargo estimation pipeline for a single vessel.

    Args:
        length: Vessel length in metres.
        beam: Vessel beam in metres.
        draught: Current draught in metres (0 if unknown).
        ship_type: 'crude' or 'product'.

    Returns:
        Dict with vessel_class, dwt, load_factor, cargo_tonnes, cargo_litres,
        is_ballast, draught_missing.
    """
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest pipeline/tests/test_cargo.py -v
```

Expected: All 13 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/__init__.py pipeline/cargo.py pipeline/tests/__init__.py pipeline/tests/test_cargo.py
git commit -m "feat: cargo estimation module — vessel classification, DWT, load factor, volume calc"
```

---

### Task 3: Destination parser module

**Files:**
- Create: `pipeline/destinations.py`
- Create: `pipeline/tests/test_destinations.py`

- [ ] **Step 1: Write failing tests for destination parsing**

Create `pipeline/tests/test_destinations.py`:

```python
from pipeline.destinations import parse_destination


def test_exact_match():
    assert parse_destination("MELBOURNE") == "Melbourne"


def test_abbreviation():
    assert parse_destination("MELB") == "Melbourne"


def test_au_prefix():
    assert parse_destination("AU MEL") == "Melbourne"


def test_au_prefix_geelong():
    assert parse_destination("AU GEE") == "Geelong"


def test_port_kembla():
    assert parse_destination("PORT KEMBLA") == "Port Kembla"


def test_sydney_botany():
    assert parse_destination("BOTANY BAY") == "Sydney / Botany"


def test_case_insensitive():
    assert parse_destination("brisbane") == "Brisbane"


def test_whitespace_stripped():
    assert parse_destination("  FREMANTLE  ") == "Fremantle"


def test_unknown_australian():
    """Destination mentions Australia but port is unrecognised."""
    assert parse_destination("AUSTRALIA") == "Australia (port unknown)"


def test_unknown_non_australian():
    """Destination doesn't mention Australia at all."""
    assert parse_destination("SINGAPORE") is None


def test_empty_string():
    assert parse_destination("") is None


def test_none_input():
    assert parse_destination(None) is None


def test_darwin():
    assert parse_destination("DARWIN") == "Darwin"


def test_gladstone():
    assert parse_destination("GLADSTONE") == "Gladstone"


def test_adelaide():
    assert parse_destination("ADELAIDE") == "Adelaide"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest pipeline/tests/test_destinations.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement destination parser**

Create `pipeline/destinations.py`:

```python
"""Parse AIS destination strings into Australian port names."""

# Maps lowercase patterns to canonical port names.
# Order matters: longer/more specific patterns first.
_PORT_PATTERNS: list[tuple[list[str], str]] = [
    (["port kembla", "kembla", "pt kembla", "ptkembla"], "Port Kembla"),
    (["botany", "sydney", "syd", "au syd", "pt botany"], "Sydney / Botany"),
    (["geelong", "gee", "au gee", "geelg"], "Geelong"),
    (["melbourne", "melb", "au mel", "au melb", "melbne"], "Melbourne"),
    (["brisbane", "bris", "au bri", "bne"], "Brisbane"),
    (["gladstone", "glad", "au gla"], "Gladstone"),
    (["fremantle", "freo", "fre", "au fre", "fremantl"], "Fremantle"),
    (["adelaide", "adel", "au ade", "adl"], "Adelaide"),
    (["darwin", "drw", "au dar"], "Darwin"),
    (["townsville", "tsv", "au tow", "twnsv"], "Townsville"),
]

_AU_INDICATORS = ["australia", "au ", "aust", " au"]


def parse_destination(raw: str | None) -> str | None:
    """Parse an AIS destination string to an Australian port name.

    Returns:
        Canonical port name (e.g. "Melbourne"), or
        "Australia (port unknown)" if Australia is mentioned but port unclear, or
        None if not headed to Australia.
    """
    if not raw:
        return None

    cleaned = raw.strip().lower()
    if not cleaned:
        return None

    # Try matching against known port patterns
    for patterns, port_name in _PORT_PATTERNS:
        for pattern in patterns:
            if pattern in cleaned or cleaned == pattern:
                return port_name

    # Check if Australia is mentioned but port is unknown
    for indicator in _AU_INDICATORS:
        if indicator in cleaned:
            return "Australia (port unknown)"

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest pipeline/tests/test_destinations.py -v
```

Expected: All 15 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/destinations.py pipeline/tests/test_destinations.py
git commit -m "feat: AIS destination parser — maps raw strings to Australian port names"
```

---

### Task 4: Port arrival detection module

**Files:**
- Create: `pipeline/arrivals.py`
- Create: `pipeline/tests/test_arrivals.py`

- [ ] **Step 1: Write failing tests for arrival detection**

Create `pipeline/tests/test_arrivals.py`:

```python
import json
from pipeline.arrivals import (
    haversine_km,
    is_within_port,
    detect_arrivals,
    load_ports,
)


def test_haversine_known_distance():
    """Sydney to Melbourne is roughly 714 km."""
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
    """Point just outside the geofence."""
    ports = [{"name": "Melbourne", "lat": -37.84, "lon": 144.92, "radius_km": 5}]
    # ~6km north of Melbourne port
    result = is_within_port(-37.785, 144.92, ports)
    assert result is None


def test_detect_arrivals_vessel_arrived():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -36.0, "lon": 144.0,
             "speed": 12.0, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    existing_arrivals = []

    new_arrivals = detect_arrivals(
        current_snapshot, previous_snapshot, ports, existing_arrivals
    )
    assert len(new_arrivals) == 1
    assert new_arrivals[0]["port"] == "Geelong"
    assert new_arrivals[0]["imo"] == "1234567"


def test_detect_arrivals_vessel_still_at_sea():
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -36.0, "lon": 144.0,
             "speed": 12.0, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -37.0, "lon": 144.2,
             "speed": 11.5, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    existing_arrivals = []

    new_arrivals = detect_arrivals(
        current_snapshot, previous_snapshot, ports, existing_arrivals
    )
    assert len(new_arrivals) == 0


def test_detect_arrivals_no_duplicate():
    """Vessel already logged as arrived should not be re-logged."""
    ports = [{"name": "Geelong", "lat": -38.15, "lon": 144.36, "radius_km": 5}]
    previous_snapshot = {
        "vessels": [
            {"imo": "1234567", "name": "Test Tanker", "lat": -38.15, "lon": 144.36,
             "speed": 0.3, "ship_type": "crude", "length": 245, "beam": 44,
             "draught": 14.5, "destination": "GEELONG"}
        ]
    }
    current_snapshot = previous_snapshot  # still there
    existing_arrivals = [{"imo": "1234567", "port": "Geelong", "timestamp": "2026-04-12T02:00:00Z"}]

    new_arrivals = detect_arrivals(
        current_snapshot, previous_snapshot, ports, existing_arrivals
    )
    assert len(new_arrivals) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest pipeline/tests/test_arrivals.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement arrival detection module**

Create `pipeline/arrivals.py`:

```python
"""Port arrival detection using geofencing."""

import json
import math
from datetime import datetime, timezone

from pipeline.cargo import estimate_cargo


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometres."""
    R = 6371.0  # Earth radius in km
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_ports(ports_path: str = "data/ports.json") -> list[dict]:
    """Load port geofence definitions."""
    with open(ports_path) as f:
        return json.load(f)["ports"]


def is_within_port(
    lat: float, lon: float, ports: list[dict]
) -> str | None:
    """Check if a position falls within any port geofence.

    Returns the port name if within a geofence, None otherwise.
    """
    for port in ports:
        dist = haversine_km(lat, lon, port["lat"], port["lon"])
        if dist <= port["radius_km"]:
            return port["name"]
    return None


def detect_arrivals(
    current_snapshot: dict,
    previous_snapshot: dict,
    ports: list[dict],
    existing_arrivals: list[dict],
) -> list[dict]:
    """Detect new port arrivals by comparing snapshots.

    A vessel has arrived if:
    1. It's within a port geofence
    2. Its speed is < 1 knot
    3. It was previously seen en route (in previous snapshot)
    4. It hasn't already been logged as arrived at this port

    Returns list of new arrival records.
    """
    # IMOs already logged as arrived (to prevent duplicates)
    arrived_imos = {
        (a["imo"], a["port"]) for a in existing_arrivals
    }

    # IMOs that were in the previous snapshot (i.e. known to be en route)
    previous_imos = {v["imo"] for v in previous_snapshot.get("vessels", [])}

    new_arrivals = []
    now = datetime.now(timezone.utc).isoformat()

    for vessel in current_snapshot.get("vessels", []):
        imo = vessel["imo"]
        speed = vessel.get("speed", 99)
        lat = vessel["lat"]
        lon = vessel["lon"]

        # Must be slow (< 1 knot)
        if speed >= 1.0:
            continue

        # Must be within a port geofence
        port_name = is_within_port(lat, lon, ports)
        if port_name is None:
            continue

        # Must have been seen previously (not just appeared at port)
        if imo not in previous_imos:
            continue

        # Must not already be logged
        if (imo, port_name) in arrived_imos:
            continue

        # Calculate cargo estimate
        cargo = estimate_cargo(
            length=vessel.get("length", 0),
            beam=vessel.get("beam", 0),
            draught=vessel.get("draught", 0),
            ship_type=vessel.get("ship_type", "product"),
        )

        new_arrivals.append({
            "imo": imo,
            "name": vessel.get("name", "Unknown"),
            "port": port_name,
            "timestamp": now,
            "ship_type": vessel.get("ship_type", "product"),
            "vessel_class": cargo["vessel_class"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "draught_missing": cargo["draught_missing"],
        })

    return new_arrivals
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest pipeline/tests/test_arrivals.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/arrivals.py pipeline/tests/test_arrivals.py
git commit -m "feat: port arrival detection — geofencing, speed check, duplicate prevention"
```

---

### Task 5: Vessel database module

**Files:**
- Create: `pipeline/vessels.py`
- Create: `pipeline/tests/test_vessels.py`

- [ ] **Step 1: Write failing tests**

Create `pipeline/tests/test_vessels.py`:

```python
from pipeline.vessels import update_vessel_db


def test_new_vessel_added():
    db = {}
    vessels = [
        {"imo": "9876543", "name": "Test Tanker", "length": 245, "beam": 44,
         "draught": 14.5, "ship_type": "crude"}
    ]
    updated = update_vessel_db(db, vessels)
    assert "9876543" in updated
    assert updated["9876543"]["name"] == "Test Tanker"
    assert updated["9876543"]["vessel_class"] == "Aframax"
    assert updated["9876543"]["dwt"] == 100000
    assert updated["9876543"]["arrival_count"] == 0


def test_existing_vessel_updated():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-10T00:00:00Z",
            "arrival_count": 2,
        }
    }
    vessels = [
        {"imo": "9876543", "name": "Test Tanker", "length": 245, "beam": 44,
         "draught": 14.5, "ship_type": "crude"}
    ]
    updated = update_vessel_db(db, vessels)
    assert updated["9876543"]["arrival_count"] == 2  # unchanged
    assert updated["9876543"]["last_seen"] != "2026-04-10T00:00:00Z"  # updated


def test_vessel_without_imo_skipped():
    db = {}
    vessels = [
        {"imo": "", "name": "No IMO", "length": 100, "beam": 20,
         "draught": 5.0, "ship_type": "product"}
    ]
    updated = update_vessel_db(db, vessels)
    assert len(updated) == 0


def test_increment_arrival_count():
    db = {
        "9876543": {
            "name": "Test Tanker", "vessel_class": "Aframax", "dwt": 100000,
            "length": 245, "beam": 44, "ship_type": "crude",
            "first_seen": "2026-04-01T00:00:00Z",
            "last_seen": "2026-04-10T00:00:00Z",
            "arrival_count": 2,
        }
    }
    new_arrivals = [{"imo": "9876543", "port": "Geelong"}]
    updated = update_vessel_db(db, [], new_arrivals=new_arrivals)
    assert updated["9876543"]["arrival_count"] == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest pipeline/tests/test_vessels.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement vessel database module**

Create `pipeline/vessels.py`:

```python
"""Vessel database management, keyed by IMO number."""

from datetime import datetime, timezone

from pipeline.cargo import classify_vessel, TANKER_CLASSES


def update_vessel_db(
    db: dict,
    vessels: list[dict],
    new_arrivals: list[dict] | None = None,
) -> dict:
    """Update the vessel database with new observations and arrivals.

    Args:
        db: Existing vessel database {imo: vessel_info}.
        vessels: List of vessel observations from current snapshot.
        new_arrivals: List of newly detected arrivals to increment counts.

    Returns:
        Updated vessel database.
    """
    now = datetime.now(timezone.utc).isoformat()

    for vessel in vessels:
        imo = vessel.get("imo", "")
        if not imo:
            continue

        vessel_class = classify_vessel(
            vessel.get("length", 0), vessel.get("beam", 0)
        )
        dwt = TANKER_CLASSES[vessel_class]["dwt"]

        if imo in db:
            # Update existing entry
            db[imo]["last_seen"] = now
            db[imo]["name"] = vessel.get("name", db[imo]["name"])
        else:
            # New vessel
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

    # Increment arrival counts
    if new_arrivals:
        for arrival in new_arrivals:
            imo = arrival.get("imo", "")
            if imo in db:
                db[imo]["arrival_count"] += 1

    return db
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest pipeline/tests/test_vessels.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pipeline/vessels.py pipeline/tests/test_vessels.py
git commit -m "feat: vessel database module — IMO-keyed records, arrival counting"
```

---

### Task 6: Petroleum Statistics Excel parser

**Files:**
- Create: `pipeline/petroleum_stats.py`
- Create: `pipeline/tests/test_petroleum_stats.py`

- [ ] **Step 1: Write failing tests**

Create `pipeline/tests/test_petroleum_stats.py`:

```python
import json
from pipeline.petroleum_stats import parse_imports_sheet, parse_consumption_cover


def test_parse_imports_sheet(tmp_path):
    """Test with the real downloaded Excel file if available, otherwise skip."""
    import os
    excel_path = r"C:\Users\wilso\Downloads\aus-petroleum-stats-jan-2026.xlsx"
    if not os.path.exists(excel_path):
        import pytest
        pytest.skip("Excel file not available for testing")

    records = parse_imports_sheet(excel_path)
    assert len(records) > 100  # Should have 15+ years of monthly data
    first = records[0]
    assert "month" in first
    assert "crude_oil_ml" in first
    assert "diesel_ml" in first
    assert "gasoline_ml" in first
    assert "jet_fuel_ml" in first
    assert "fuel_oil_ml" in first
    assert "lpg_ml" in first
    assert "total_ml" in first


def test_parse_consumption_cover(tmp_path):
    """Test with real Excel file if available."""
    import os
    excel_path = r"C:\Users\wilso\Downloads\aus-petroleum-stats-jan-2026.xlsx"
    if not os.path.exists(excel_path):
        import pytest
        pytest.skip("Excel file not available for testing")

    records = parse_consumption_cover(excel_path)
    assert len(records) > 100
    last = records[-1]
    assert "month" in last
    assert "total_days" in last
    assert last["total_days"] > 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest pipeline/tests/test_petroleum_stats.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement Excel parser**

Create `pipeline/petroleum_stats.py`:

```python
"""Parse Australian Petroleum Statistics Excel files from data.gov.au."""

import os
import requests
from openpyxl import load_workbook


# data.gov.au dataset page for Australian Petroleum Statistics
DATASET_URL = "https://data.gov.au/data/api/3/action/package_show?id=australian-petroleum-statistics"


def download_latest_excel(output_path: str) -> str:
    """Download the latest Australian Petroleum Statistics Excel file.

    Returns the path to the downloaded file.
    """
    resp = requests.get(DATASET_URL, timeout=30)
    resp.raise_for_status()
    resources = resp.json()["result"]["resources"]

    # Find the Excel resource (most recent)
    xlsx_resources = [
        r for r in resources
        if r["format"].upper() in ("XLSX", "XLS") or r["url"].endswith(".xlsx")
    ]
    if not xlsx_resources:
        raise RuntimeError("No Excel resource found in dataset")

    resource = xlsx_resources[0]
    download_url = resource["url"]

    data_resp = requests.get(download_url, timeout=120)
    data_resp.raise_for_status()

    with open(output_path, "wb") as f:
        f.write(data_resp.content)

    return output_path


def parse_imports_sheet(excel_path: str) -> list[dict]:
    """Parse the 'Imports volume' sheet into structured records."""
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb["Imports volume"]

    records = []
    header_row = None

    for row in ws.iter_rows(values_only=True):
        if row[0] == "Month":
            header_row = row
            continue
        if header_row is None:
            continue

        month_val = row[0]
        if month_val is None:
            continue

        # Month is a datetime object from openpyxl
        month_str = month_val.strftime("%Y-%m") if hasattr(month_val, "strftime") else str(month_val)

        def safe_float(val):
            if val is None or val == "n.a." or val == "":
                return 0.0
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0.0

        record = {
            "month": month_str,
            "crude_oil_ml": safe_float(row[1]),
            "lpg_ml": safe_float(row[2]),
            "gasoline_ml": safe_float(row[3]),
            "jet_fuel_ml": safe_float(row[5]),
            "diesel_ml": safe_float(row[7]),
            "fuel_oil_ml": safe_float(row[8]),
            "total_ml": safe_float(row[13]),
        }
        records.append(record)

    wb.close()
    return records


def parse_consumption_cover(excel_path: str) -> list[dict]:
    """Parse the 'Consumption cover' sheet for days-of-supply data."""
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb["Consumption cover"]

    records = []
    header_row = None

    for row in ws.iter_rows(values_only=True):
        if row[0] == "Month":
            header_row = row
            continue
        if header_row is None:
            continue

        month_val = row[0]
        if month_val is None:
            continue

        month_str = month_val.strftime("%Y-%m") if hasattr(month_val, "strftime") else str(month_val)

        def safe_int(val):
            if val is None or val == "n.a." or val == "":
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        record = {
            "month": month_str,
            "crude_days": safe_int(row[1]),
            "gasoline_days": safe_int(row[3]),
            "jet_fuel_days": safe_int(row[5]),
            "diesel_days": safe_int(row[6]),
            "total_days": safe_int(row[10]),
        }
        records.append(record)

    wb.close()
    return records


def build_imports_json(excel_path: str) -> dict:
    """Build the complete imports.json data structure."""
    imports = parse_imports_sheet(excel_path)
    consumption = parse_consumption_cover(excel_path)
    return {
        "imports_by_month": imports,
        "consumption_cover": consumption,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest pipeline/tests/test_petroleum_stats.py -v
```

Expected: 2 tests PASS (or SKIP if Excel file not at expected path — tests are designed to handle this).

- [ ] **Step 5: Commit**

```bash
git add pipeline/petroleum_stats.py pipeline/tests/test_petroleum_stats.py
git commit -m "feat: petroleum stats Excel parser — imports volume and consumption cover"
```

---

### Task 7: AISStream WebSocket collector

**Files:**
- Create: `pipeline/collector.py`

- [ ] **Step 1: Implement the AISStream collector**

Create `pipeline/collector.py`:

```python
"""AISStream WebSocket collector for tanker vessels near Australia."""

import asyncio
import json
import os
import time
from datetime import datetime, timezone

import websockets

from pipeline.cargo import estimate_cargo
from pipeline.destinations import parse_destination

AISSTREAM_URL = "wss://stream.aisstream.io/v0/stream"

# Bounding box covering approaches to Australia + SE Asia shipping lanes
AU_BOUNDING_BOX = [
    [[-5.0, 90.0], [-50.0, 170.0]]  # [[lat_min, lon_min], [lat_max, lon_max]] — note AISStream format
]

# AIS ship type codes for tankers (excluding LNG/LPG)
# 80-89: Tanker, all types
TANKER_TYPE_CODES = set(range(80, 90))

# Map AIS type codes to our fuel categories
# 80-84: crude/oil tankers, 85-89: chemical/product tankers
CRUDE_CODES = {80, 81, 82, 83, 84}
PRODUCT_CODES = {85, 86, 87, 88, 89}


def classify_ship_type(ais_type: int) -> str:
    """Map AIS ship type code to 'crude' or 'product'."""
    if ais_type in CRUDE_CODES:
        return "crude"
    return "product"


async def collect_vessels(
    api_key: str,
    duration_seconds: int = 1800,
) -> dict:
    """Connect to AISStream and collect tanker vessel data.

    Args:
        api_key: AISStream API key.
        duration_seconds: How long to listen (default 30 minutes).

    Returns:
        Snapshot dict with timestamp and vessels list.
    """
    vessels: dict[str, dict] = {}  # keyed by MMSI to deduplicate
    start_time = time.time()

    subscription = {
        "APIKey": api_key,
        "BoundingBoxes": AU_BOUNDING_BOX,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }

    print(f"Connecting to AISStream, collecting for {duration_seconds}s...")

    try:
        async with websockets.connect(AISSTREAM_URL) as ws:
            await ws.send(json.dumps(subscription))

            while (time.time() - start_time) < duration_seconds:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                except asyncio.TimeoutError:
                    continue

                msg = json.loads(raw)
                msg_type = msg.get("MessageType", "")
                meta = msg.get("MetaData", {})
                mmsi = str(meta.get("MMSI", ""))

                if not mmsi:
                    continue

                ais_type = meta.get("ShipType", 0)

                # Only process tanker types
                if ais_type not in TANKER_TYPE_CODES:
                    continue

                # Initialize vessel record if new
                if mmsi not in vessels:
                    vessels[mmsi] = {
                        "mmsi": mmsi,
                        "imo": "",
                        "name": meta.get("ShipName", "").strip(),
                        "ship_type": classify_ship_type(ais_type),
                        "ais_type_code": ais_type,
                        "lat": 0.0,
                        "lon": 0.0,
                        "speed": 0.0,
                        "course": 0.0,
                        "heading": 0.0,
                        "draught": 0.0,
                        "length": 0,
                        "beam": 0,
                        "destination": "",
                        "destination_parsed": None,
                        "last_update": "",
                    }

                vessel = vessels[mmsi]

                if msg_type == "PositionReport":
                    report = msg.get("Message", {}).get("PositionReport", {})
                    vessel["lat"] = meta.get("latitude", 0.0)
                    vessel["lon"] = meta.get("longitude", 0.0)
                    vessel["speed"] = report.get("Sog", 0.0)
                    vessel["course"] = report.get("Cog", 0.0)
                    vessel["heading"] = report.get("TrueHeading", 0.0)
                    vessel["last_update"] = meta.get("time_utc", "")

                elif msg_type == "ShipStaticData":
                    static = msg.get("Message", {}).get("ShipStaticData", {})
                    vessel["imo"] = str(static.get("ImoNumber", ""))
                    vessel["name"] = static.get("Name", vessel["name"]).strip()
                    vessel["draught"] = static.get("MaximumStaticDraught", 0.0)
                    vessel["destination"] = static.get("Destination", "").strip()
                    vessel["destination_parsed"] = parse_destination(
                        vessel["destination"]
                    )

                    dimension = static.get("Dimension", {})
                    vessel["length"] = dimension.get("A", 0) + dimension.get("B", 0)
                    vessel["beam"] = dimension.get("C", 0) + dimension.get("D", 0)

    except Exception as e:
        print(f"Collection error: {e}")

    # Post-process: add cargo estimates, filter to AU-bound
    result_vessels = []
    for vessel in vessels.values():
        # Skip vessels with no position
        if vessel["lat"] == 0.0 and vessel["lon"] == 0.0:
            continue

        # Add cargo estimate
        cargo = estimate_cargo(
            length=vessel["length"],
            beam=vessel["beam"],
            draught=vessel["draught"],
            ship_type=vessel["ship_type"],
        )
        vessel.update({
            "vessel_class": cargo["vessel_class"],
            "dwt": cargo["dwt"],
            "load_factor": cargo["load_factor"],
            "cargo_tonnes": cargo["cargo_tonnes"],
            "cargo_litres": cargo["cargo_litres"],
            "is_ballast": cargo["is_ballast"],
            "draught_missing": cargo["draught_missing"],
        })
        result_vessels.append(vessel)

    count = len(result_vessels)
    tanker_count = len([v for v in result_vessels if not v["is_ballast"]])
    print(f"Collected {count} tanker vessels ({tanker_count} laden, {count - tanker_count} ballast)")

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "vessels": result_vessels,
    }


def run_collector(api_key: str, duration_seconds: int = 1800) -> dict:
    """Synchronous wrapper for the async collector."""
    return asyncio.run(collect_vessels(api_key, duration_seconds))


if __name__ == "__main__":
    key = os.environ.get("AISSTREAM_API_KEY", "")
    if not key:
        print("Error: AISSTREAM_API_KEY environment variable not set")
        exit(1)
    snapshot = run_collector(key)
    print(json.dumps(snapshot, indent=2)[:2000])
```

Note: This module is hard to unit test due to the WebSocket dependency. We test it via integration (running the pipeline end-to-end with a real API key). The modules it delegates to (cargo, destinations) are thoroughly unit tested.

- [ ] **Step 2: Commit**

```bash
git add pipeline/collector.py
git commit -m "feat: AISStream WebSocket collector — connects, filters tankers, estimates cargo"
```

---

### Task 8: Pipeline orchestrator

**Files:**
- Create: `pipeline/orchestrator.py`

- [ ] **Step 1: Implement the orchestrator that ties everything together**

Create `pipeline/orchestrator.py`:

```python
"""Pipeline orchestrator — runs the full nightly data collection and processing."""

import json
import os
import sys
from datetime import datetime, timezone

from pipeline.collector import run_collector
from pipeline.arrivals import detect_arrivals, load_ports
from pipeline.vessels import update_vessel_db
from pipeline.petroleum_stats import download_latest_excel, build_imports_json

DATA_DIR = "data"
EXCEL_CACHE = "data/petroleum_stats_cache.xlsx"


def load_json(path: str, default: any) -> any:
    """Load a JSON file, returning default if it doesn't exist."""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: str, data: any) -> None:
    """Save data as formatted JSON."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved {path}")


def update_monthly_estimates(
    monthly: dict,
    new_arrivals: list[dict],
    current_snapshot: dict,
) -> dict:
    """Update monthly arrival estimates and en-route figures."""
    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    if month_key not in monthly.get("months", {}):
        monthly.setdefault("months", {})[month_key] = {
            "arrived_crude_litres": 0,
            "arrived_product_litres": 0,
            "arrived_crude_tonnes": 0,
            "arrived_product_tonnes": 0,
            "arrival_count": 0,
        }

    month = monthly["months"][month_key]

    # Add new arrivals
    for arrival in new_arrivals:
        month["arrival_count"] += 1
        if arrival["ship_type"] == "crude":
            month["arrived_crude_litres"] += arrival["cargo_litres"]
            month["arrived_crude_tonnes"] += arrival["cargo_tonnes"]
        else:
            month["arrived_product_litres"] += arrival["cargo_litres"]
            month["arrived_product_tonnes"] += arrival["cargo_tonnes"]

    # Calculate current en-route totals from snapshot
    en_route_crude_litres = 0
    en_route_product_litres = 0
    for v in current_snapshot.get("vessels", []):
        if v.get("is_ballast"):
            continue
        if v.get("ship_type") == "crude":
            en_route_crude_litres += v.get("cargo_litres", 0)
        else:
            en_route_product_litres += v.get("cargo_litres", 0)

    month["en_route_crude_litres"] = en_route_crude_litres
    month["en_route_product_litres"] = en_route_product_litres
    month["last_updated"] = now.isoformat()

    return monthly


def run_pipeline(api_key: str, duration_seconds: int = 1800) -> None:
    """Run the full nightly pipeline."""
    os.makedirs(DATA_DIR, exist_ok=True)

    # Load existing data
    previous_snapshot = load_json(f"{DATA_DIR}/snapshot.json", {"vessels": []})
    arrivals_data = load_json(f"{DATA_DIR}/arrivals.json", {"arrivals": []})
    vessel_db = load_json(f"{DATA_DIR}/vessels.json", {})
    monthly = load_json(f"{DATA_DIR}/monthly-estimates.json", {"months": {}})
    ports = load_ports(f"{DATA_DIR}/ports.json")

    # Step 1: Collect from AISStream
    print("Step 1: Collecting from AISStream...")
    current_snapshot = run_collector(api_key, duration_seconds)
    save_json(f"{DATA_DIR}/snapshot.json", current_snapshot)

    # Step 2: Detect arrivals
    print("Step 2: Detecting port arrivals...")
    new_arrivals = detect_arrivals(
        current_snapshot, previous_snapshot, ports, arrivals_data["arrivals"]
    )
    arrivals_data["arrivals"].extend(new_arrivals)
    save_json(f"{DATA_DIR}/arrivals.json", arrivals_data)
    print(f"  {len(new_arrivals)} new arrivals detected")

    # Step 3: Update vessel database
    print("Step 3: Updating vessel database...")
    vessel_db = update_vessel_db(
        vessel_db, current_snapshot["vessels"], new_arrivals
    )
    save_json(f"{DATA_DIR}/vessels.json", vessel_db)
    print(f"  {len(vessel_db)} vessels in database")

    # Step 4: Update monthly estimates
    print("Step 4: Updating monthly estimates...")
    monthly = update_monthly_estimates(monthly, new_arrivals, current_snapshot)
    save_json(f"{DATA_DIR}/monthly-estimates.json", monthly)

    # Step 5: Update petroleum statistics (monthly check)
    print("Step 5: Checking petroleum statistics...")
    try:
        download_latest_excel(EXCEL_CACHE)
        imports_data = build_imports_json(EXCEL_CACHE)
        save_json(f"{DATA_DIR}/imports.json", imports_data)
        print("  Updated imports data")
    except Exception as e:
        print(f"  Skipped petroleum stats update: {e}")
        # Not fatal — imports.json may already exist from a previous run

    print("Pipeline complete.")


if __name__ == "__main__":
    key = os.environ.get("AISSTREAM_API_KEY", "")
    if not key:
        print("Error: AISSTREAM_API_KEY environment variable not set")
        sys.exit(1)

    duration = int(os.environ.get("COLLECTION_DURATION", "1800"))
    run_pipeline(key, duration)
```

- [ ] **Step 2: Commit**

```bash
git add pipeline/orchestrator.py
git commit -m "feat: pipeline orchestrator — runs full nightly collect, detect, update cycle"
```

---

## Phase 3: Frontend — TypeScript Types & Data Loading

### Task 9: TypeScript types and data loading

**Files:**
- Create: `src/lib/types.ts`
- Create: `src/lib/data.ts`

- [ ] **Step 1: Define TypeScript interfaces for all data shapes**

Create `src/lib/types.ts`:

```typescript
export interface Vessel {
  mmsi: string;
  imo: string;
  name: string;
  ship_type: "crude" | "product";
  lat: number;
  lon: number;
  speed: number;
  course: number;
  draught: number;
  length: number;
  beam: number;
  destination: string;
  destination_parsed: string | null;
  vessel_class: string;
  dwt: number;
  load_factor: number;
  cargo_tonnes: number;
  cargo_litres: number;
  is_ballast: boolean;
  draught_missing: boolean;
  last_update: string;
}

export interface Snapshot {
  timestamp: string;
  vessels: Vessel[];
}

export interface Arrival {
  imo: string;
  name: string;
  port: string;
  timestamp: string;
  ship_type: "crude" | "product";
  vessel_class: string;
  cargo_tonnes: number;
  cargo_litres: number;
  draught_missing: boolean;
}

export interface MonthEstimate {
  arrived_crude_litres: number;
  arrived_product_litres: number;
  arrived_crude_tonnes: number;
  arrived_product_tonnes: number;
  en_route_crude_litres: number;
  en_route_product_litres: number;
  arrival_count: number;
  last_updated: string;
}

export interface MonthlyEstimates {
  months: Record<string, MonthEstimate>;
}

export interface ImportRecord {
  month: string;
  crude_oil_ml: number;
  lpg_ml: number;
  gasoline_ml: number;
  jet_fuel_ml: number;
  diesel_ml: number;
  fuel_oil_ml: number;
  total_ml: number;
}

export interface ConsumptionRecord {
  month: string;
  crude_days: number;
  gasoline_days: number;
  jet_fuel_days: number;
  diesel_days: number;
  total_days: number;
}

export interface ImportsData {
  imports_by_month: ImportRecord[];
  consumption_cover: ConsumptionRecord[];
}

export interface DashboardData {
  snapshot: Snapshot;
  arrivals: Arrival[];
  monthlyEstimates: MonthlyEstimates;
  imports: ImportsData;
}
```

- [ ] **Step 2: Create data loading helpers**

Create `src/lib/data.ts`:

```typescript
import fs from "fs";
import path from "path";
import type {
  Snapshot,
  Arrival,
  MonthlyEstimates,
  ImportsData,
  DashboardData,
} from "./types";

const DATA_DIR = path.join(process.cwd(), "data");

function readJson<T>(filename: string, fallback: T): T {
  const filePath = path.join(DATA_DIR, filename);
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadDashboardData(): DashboardData {
  const snapshot = readJson<Snapshot>("snapshot.json", {
    timestamp: "",
    vessels: [],
  });

  const arrivalsData = readJson<{ arrivals: Arrival[] }>("arrivals.json", {
    arrivals: [],
  });

  const monthlyEstimates = readJson<MonthlyEstimates>(
    "monthly-estimates.json",
    { months: {} }
  );

  const imports = readJson<ImportsData>("imports.json", {
    imports_by_month: [],
    consumption_cover: [],
  });

  return {
    snapshot,
    arrivals: arrivalsData.arrivals,
    monthlyEstimates,
    imports,
  };
}

export function formatLitres(litres: number): string {
  if (litres >= 1_000_000_000) {
    return `${(litres / 1_000_000_000).toFixed(1)}B L`;
  }
  if (litres >= 1_000_000) {
    return `${(litres / 1_000_000).toFixed(0)}M L`;
  }
  return `${litres.toLocaleString()} L`;
}

export function formatMegalitres(ml: number): string {
  if (ml >= 1000) {
    return `${(ml / 1000).toFixed(1)}B L`;
  }
  return `${ml.toFixed(0)} ML`;
}
```

- [ ] **Step 3: Commit**

```bash
git add src/lib/types.ts src/lib/data.ts
git commit -m "feat: TypeScript types and data loading for all JSON data files"
```

---

## Phase 4: Frontend — Components

### Task 10: Header and StatBar components

**Files:**
- Create: `src/components/Header.tsx`
- Create: `src/components/StatBar.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Create Header component**

Create `src/components/Header.tsx`:

```tsx
import type { Snapshot } from "@/lib/types";

interface HeaderProps {
  snapshot: Snapshot;
  totalLitres: number;
  vesselCount: number;
}

export default function Header({ snapshot, totalLitres, vesselCount }: HeaderProps) {
  const litresFormatted =
    totalLitres >= 1_000_000_000
      ? `${(totalLitres / 1_000_000_000).toFixed(1)} billion litres`
      : `${(totalLitres / 1_000_000).toFixed(0)} million litres`;

  const timestamp = snapshot.timestamp
    ? new Date(snapshot.timestamp).toLocaleDateString("en-AU", {
        day: "numeric",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: "Australia/Sydney",
        timeZoneName: "short",
      })
    : "No data available";

  return (
    <header className="border-b-[2.5px] border-border-heavy pb-3 mb-6">
      <p className="text-[10px] uppercase tracking-label text-label mb-1">
        Australian Fuel Import Monitor
      </p>
      <div className="flex justify-between items-baseline gap-8">
        <h1 className="font-headline text-2xl md:text-3xl leading-tight">
          {vesselCount} tankers carrying an estimated {litresFormatted} of fuel
          are en route to Australia
        </h1>
        <p className="text-[10px] text-label-light whitespace-nowrap text-right hidden sm:block">
          Updated {timestamp}
        </p>
      </div>
      <p className="text-[10px] text-label-light mt-1 sm:hidden">
        Updated {timestamp}
      </p>
    </header>
  );
}
```

- [ ] **Step 2: Create StatBar component**

Create `src/components/StatBar.tsx`:

```tsx
import type { Vessel, ConsumptionRecord } from "@/lib/types";

interface StatBarProps {
  vessels: Vessel[];
  latestConsumptionCover: ConsumptionRecord | null;
}

function Stat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="font-headline text-3xl font-light">{value}</div>
      <div className="text-[10px] uppercase tracking-label text-label">
        {label}
      </div>
    </div>
  );
}

export default function StatBar({ vessels, latestConsumptionCover }: StatBarProps) {
  const laden = vessels.filter((v) => !v.is_ballast);
  const crude = laden.filter((v) => v.ship_type === "crude");
  const product = laden.filter((v) => v.ship_type === "product");

  const crudeLitres = crude.reduce((sum, v) => sum + v.cargo_litres, 0);
  const productLitres = product.reduce((sum, v) => sum + v.cargo_litres, 0);

  const formatBL = (litres: number) => {
    if (litres >= 1_000_000_000) return `${(litres / 1_000_000_000).toFixed(1)}B L`;
    if (litres >= 1_000_000) return `${(litres / 1_000_000).toFixed(0)}M L`;
    return `${litres.toLocaleString()} L`;
  };

  const reserveDays = latestConsumptionCover?.total_days ?? "—";

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-4 pb-5 mb-6 border-b border-border">
      <Stat value={String(crude.length)} label="Crude oil tankers" />
      <Stat value={String(product.length)} label="Product tankers" />
      <Stat value={formatBL(crudeLitres)} label="Crude oil est." />
      <Stat value={formatBL(productLitres)} label="Refined products est." />
      <Stat
        value={String(reserveDays)}
        label="Days reserve (govt)"
      />
    </div>
  );
}
```

- [ ] **Step 3: Wire into page**

Replace `src/app/page.tsx`:

```tsx
import { loadDashboardData } from "@/lib/data";
import Header from "@/components/Header";
import StatBar from "@/components/StatBar";

export default function Home() {
  const data = loadDashboardData();
  const laden = data.snapshot.vessels.filter((v) => !v.is_ballast);
  const totalLitres = laden.reduce((sum, v) => sum + v.cargo_litres, 0);

  const latestConsumption =
    data.imports.consumption_cover.length > 0
      ? data.imports.consumption_cover[data.imports.consumption_cover.length - 1]
      : null;

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
      <Header
        snapshot={data.snapshot}
        totalLitres={totalLitres}
        vesselCount={laden.length}
      />
      <StatBar
        vessels={data.snapshot.vessels}
        latestConsumptionCover={latestConsumption}
      />
      {/* Map + Table will go here */}
      {/* Historical chart will go here */}
    </main>
  );
}
```

- [ ] **Step 4: Verify it builds**

```bash
npm run build
```

Expected: Builds with static export. Header and stats render (with zero values from seed data).

- [ ] **Step 5: Commit**

```bash
git add src/components/Header.tsx src/components/StatBar.tsx src/app/page.tsx
git commit -m "feat: Header and StatBar components with editorial typography"
```

---

### Task 11: Interactive map component

**Files:**
- Create: `src/components/VesselMap.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Install Leaflet dependencies**

```bash
npm install leaflet react-leaflet
npm install -D @types/leaflet
```

- [ ] **Step 2: Create VesselMap component**

Create `src/components/VesselMap.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import type { Vessel } from "@/lib/types";

interface VesselMapProps {
  vessels: Vessel[];
  selectedImo: string | null;
  onSelectVessel: (imo: string | null) => void;
}

export default function VesselMap({
  vessels,
  selectedImo,
  onSelectVessel,
}: VesselMapProps) {
  const [MapComponents, setMapComponents] = useState<any>(null);

  useEffect(() => {
    // Dynamic import to avoid SSR issues with Leaflet
    Promise.all([
      import("react-leaflet"),
      import("leaflet"),
      import("leaflet/dist/leaflet.css"),
    ]).then(([rl, L]) => {
      setMapComponents({ rl, L: L.default });
    });
  }, []);

  if (!MapComponents) {
    return (
      <div className="bg-panel border border-border h-[400px] md:h-full min-h-[300px] flex items-center justify-center">
        <span className="text-label-light text-sm">Loading map...</span>
      </div>
    );
  }

  const { MapContainer, TileLayer, CircleMarker, Popup } = MapComponents.rl;

  // Center on Australia/SE Asia region
  const center: [number, number] = [-20, 130];

  return (
    <MapContainer
      center={center}
      zoom={4}
      className="h-[400px] md:h-full min-h-[300px] w-full border border-border"
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png"
      />
      {vessels.map((vessel) => {
        if (vessel.lat === 0 && vessel.lon === 0) return null;

        const isSelected = vessel.imo === selectedImo;
        const color = vessel.ship_type === "crude" ? "#dc2626" : "#1e40af";
        const radius = isSelected ? 8 : 5;
        const opacity = vessel.is_ballast ? 0.3 : 1;

        return (
          <CircleMarker
            key={vessel.mmsi}
            center={[vessel.lat, vessel.lon]}
            radius={radius}
            pathOptions={{
              color: isSelected ? "#111827" : color,
              fillColor: color,
              fillOpacity: opacity,
              weight: isSelected ? 2 : 1,
            }}
            eventHandlers={{
              click: () => onSelectVessel(vessel.imo),
            }}
          >
            <Popup>
              <div className="font-body text-xs">
                <p className="font-semibold">{vessel.name || "Unknown"}</p>
                <p className="text-label">
                  {vessel.vessel_class} &middot;{" "}
                  <span
                    className={
                      vessel.ship_type === "crude"
                        ? "text-crude"
                        : "text-product"
                    }
                  >
                    {vessel.ship_type === "crude" ? "Crude" : "Product"}
                  </span>
                </p>
                <p>
                  Est. cargo:{" "}
                  {(vessel.cargo_litres / 1_000_000).toFixed(0)}M L
                  {vessel.draught_missing && " *"}
                </p>
                <p>
                  Dest: {vessel.destination_parsed || vessel.destination || "Unknown"}
                </p>
                <p>Speed: {vessel.speed.toFixed(1)} kn</p>
                {vessel.is_ballast && (
                  <p className="text-label-light italic">Ballast (empty)</p>
                )}
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
```

- [ ] **Step 3: Add map to page with client-side state wrapper**

We need a client component to manage the selected vessel state shared between map and table. Create `src/components/DashboardGrid.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";
import VesselMap from "./VesselMap";

interface DashboardGridProps {
  vessels: Vessel[];
}

export default function DashboardGrid({ vessels }: DashboardGridProps) {
  const [selectedImo, setSelectedImo] = useState<string | null>(null);

  return (
    <div className="flex flex-col md:flex-row gap-5 mb-6">
      <div className="md:w-3/5">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessels in transit
        </p>
        <VesselMap
          vessels={vessels}
          selectedImo={selectedImo}
          onSelectVessel={setSelectedImo}
        />
      </div>
      <div className="md:w-2/5">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Vessel details
        </p>
        {/* VesselTable will be added in next task */}
        <div className="border border-border h-[400px] md:h-full min-h-[300px] flex items-center justify-center text-label-light text-sm">
          Vessel table placeholder
        </div>
      </div>
    </div>
  );
}
```

Update `src/app/page.tsx` — add after StatBar:

```tsx
import DashboardGrid from "@/components/DashboardGrid";
```

And in the JSX, replace the `{/* Map + Table will go here */}` comment:

```tsx
      <DashboardGrid vessels={data.snapshot.vessels} />
```

- [ ] **Step 4: Verify it builds**

```bash
npm run build
```

Expected: Builds successfully. Map renders with CartoDB light tiles centered on Australia.

- [ ] **Step 5: Commit**

```bash
git add src/components/VesselMap.tsx src/components/DashboardGrid.tsx src/app/page.tsx package.json package-lock.json
git commit -m "feat: interactive Leaflet map with tanker positions and vessel popups"
```

---

### Task 12: Vessel table component

**Files:**
- Create: `src/components/VesselTable.tsx`
- Modify: `src/components/DashboardGrid.tsx`

- [ ] **Step 1: Create sortable vessel table**

Create `src/components/VesselTable.tsx`:

```tsx
"use client";

import { useState } from "react";
import type { Vessel } from "@/lib/types";

interface VesselTableProps {
  vessels: Vessel[];
  selectedImo: string | null;
  onSelectVessel: (imo: string | null) => void;
}

type SortKey = "name" | "ship_type" | "destination_parsed" | "cargo_litres" | "vessel_class" | "speed" | "last_update";
type SortDir = "asc" | "desc";

export default function VesselTable({
  vessels,
  selectedImo,
  onSelectVessel,
}: VesselTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("cargo_litres");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir("desc");
    }
  };

  const sorted = [...vessels].sort((a, b) => {
    const aVal = a[sortKey] ?? "";
    const bVal = b[sortKey] ?? "";
    const cmp = typeof aVal === "number" && typeof bVal === "number"
      ? aVal - bVal
      : String(aVal).localeCompare(String(bVal));
    return sortDir === "asc" ? cmp : -cmp;
  });

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortDir === "asc" ? " \u25B2" : " \u25BC") : "";

  const marineTrafficUrl = (imo: string) =>
    imo ? `https://www.marinetraffic.com/en/ais/details/ships/imo:${imo}` : "#";

  return (
    <div className="border border-border overflow-x-auto h-[400px] md:h-full min-h-[300px] overflow-y-auto">
      <table className="w-full text-[11px] min-w-[500px]">
        <thead>
          <tr className="bg-panel border-b border-border text-[9px] uppercase tracking-label text-label font-semibold">
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("name")}>
              Vessel{arrow("name")}
            </th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("ship_type")}>
              Type{arrow("ship_type")}
            </th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("destination_parsed")}>
              Dest.{arrow("destination_parsed")}
            </th>
            <th className="text-right px-3 py-2 cursor-pointer" onClick={() => handleSort("cargo_litres")}>
              Est. cargo{arrow("cargo_litres")}
            </th>
            <th className="text-left px-3 py-2 cursor-pointer" onClick={() => handleSort("vessel_class")}>
              Class{arrow("vessel_class")}
            </th>
            <th className="text-right px-3 py-2 cursor-pointer" onClick={() => handleSort("speed")}>
              Speed{arrow("speed")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((v) => (
            <tr
              key={v.mmsi}
              className={`border-b border-border/50 cursor-pointer hover:bg-panel/50 transition-colors ${
                v.imo === selectedImo ? "bg-panel" : ""
              } ${v.is_ballast ? "opacity-40" : ""}`}
              onClick={() => onSelectVessel(v.imo === selectedImo ? null : v.imo)}
            >
              <td className="px-3 py-[7px] font-medium">
                {v.imo ? (
                  <a
                    href={marineTrafficUrl(v.imo)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {v.name || "Unknown"}
                  </a>
                ) : (
                  v.name || "Unknown"
                )}
              </td>
              <td className={`px-3 py-[7px] ${v.ship_type === "crude" ? "text-crude" : "text-product"}`}>
                {v.is_ballast ? "Ballast" : v.ship_type === "crude" ? "Crude" : "Product"}
              </td>
              <td className="px-3 py-[7px]">
                {v.destination_parsed || v.destination || "Unknown"}
              </td>
              <td className="px-3 py-[7px] text-right">
                {(v.cargo_litres / 1_000_000).toFixed(0)}M L
                {v.draught_missing && <span className="text-label-light" title="Draught data unavailable — cargo estimate based on typical load"> *</span>}
              </td>
              <td className="px-3 py-[7px]">{v.vessel_class}</td>
              <td className="px-3 py-[7px] text-right">{v.speed.toFixed(1)} kn</td>
            </tr>
          ))}
          {sorted.length === 0 && (
            <tr>
              <td colSpan={6} className="px-3 py-8 text-center text-label-light">
                No vessels currently tracked
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Wire table into DashboardGrid**

Update `src/components/DashboardGrid.tsx` — add import and replace placeholder:

```tsx
import VesselTable from "./VesselTable";
```

Replace the placeholder div in the `md:w-2/5` section with:

```tsx
        <VesselTable
          vessels={vessels}
          selectedImo={selectedImo}
          onSelectVessel={setSelectedImo}
        />
```

- [ ] **Step 3: Verify it builds**

```bash
npm run build
```

Expected: Builds. Table renders with sortable headers.

- [ ] **Step 4: Commit**

```bash
git add src/components/VesselTable.tsx src/components/DashboardGrid.tsx
git commit -m "feat: sortable vessel table with MarineTraffic links and map selection sync"
```

---

### Task 13: Historical chart component

**Files:**
- Create: `src/components/HistoricalChart.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Install Recharts**

```bash
npm install recharts
```

- [ ] **Step 2: Create HistoricalChart component**

Create `src/components/HistoricalChart.tsx`:

```tsx
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ImportRecord, MonthlyEstimates } from "@/lib/types";

interface HistoricalChartProps {
  imports: ImportRecord[];
  monthlyEstimates: MonthlyEstimates;
}

interface ChartRow {
  month: string;
  crude: number;
  gasoline: number;
  diesel: number;
  jet_fuel: number;
  fuel_oil: number;
  lpg: number;
  source: "government" | "ais_estimate" | "current_month";
}

const FUEL_COLORS = {
  crude: "#111827",
  diesel: "#374151",
  gasoline: "#6b7280",
  jet_fuel: "#9ca3af",
  fuel_oil: "#d1d5db",
  lpg: "#e5e7eb",
};

export default function HistoricalChart({
  imports,
  monthlyEstimates,
}: HistoricalChartProps) {
  // Build chart data combining government data and AIS estimates
  const chartData: ChartRow[] = [];

  // Government data (show last 24 months to keep chart readable)
  const recentImports = imports.slice(-24);
  const lastGovtMonth = recentImports.length > 0
    ? recentImports[recentImports.length - 1].month
    : "";

  for (const record of recentImports) {
    chartData.push({
      month: record.month,
      crude: record.crude_oil_ml,
      gasoline: record.gasoline_ml,
      diesel: record.diesel_ml,
      jet_fuel: record.jet_fuel_ml,
      fuel_oil: record.fuel_oil_ml,
      lpg: record.lpg_ml,
      source: "government",
    });
  }

  // AIS estimate months (months after last government data)
  const estimateMonths = Object.entries(monthlyEstimates.months)
    .filter(([month]) => month > lastGovtMonth)
    .sort(([a], [b]) => a.localeCompare(b));

  const now = new Date();
  const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  for (const [month, est] of estimateMonths) {
    const isCurrent = month === currentMonth;
    // Convert litres to megalitres for consistency with government data
    const crudeMl = (est.arrived_crude_litres + (isCurrent ? est.en_route_crude_litres : 0)) / 1_000_000;
    const productMl = (est.arrived_product_litres + (isCurrent ? est.en_route_product_litres : 0)) / 1_000_000;

    chartData.push({
      month,
      crude: Math.round(crudeMl),
      gasoline: 0,
      diesel: Math.round(productMl * 0.5), // rough split of product
      jet_fuel: Math.round(productMl * 0.25),
      fuel_oil: Math.round(productMl * 0.15),
      lpg: Math.round(productMl * 0.1),
      source: isCurrent ? "current_month" : "ais_estimate",
    });
  }

  if (chartData.length === 0) {
    return (
      <div className="border border-border h-[300px] flex items-center justify-center text-label-light text-sm">
        No import data available yet
      </div>
    );
  }

  const formatMonth = (month: string) => {
    const [y, m] = month.split("-");
    const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return `${months[parseInt(m) - 1]} ${y.slice(2)}`;
  };

  return (
    <div>
      <ResponsiveContainer width="100%" height={350}>
        <BarChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis
            dataKey="month"
            tickFormatter={formatMonth}
            tick={{ fontSize: 10, fill: "#6b7280" }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#6b7280" }}
            label={{
              value: "Megalitres",
              angle: -90,
              position: "insideLeft",
              style: { fontSize: 10, fill: "#6b7280" },
            }}
          />
          <Tooltip
            formatter={(value: number, name: string) => [`${value} ML`, name]}
            labelFormatter={formatMonth}
          />
          <Legend
            wrapperStyle={{ fontSize: 10 }}
          />
          <Bar dataKey="crude" name="Crude oil" stackId="fuel" fill={FUEL_COLORS.crude}>
            {chartData.map((entry, i) => (
              <Cell
                key={i}
                fillOpacity={entry.source === "government" ? 1 : 0.4}
                strokeDasharray={entry.source === "current_month" ? "4 2" : undefined}
                stroke={entry.source === "current_month" ? FUEL_COLORS.crude : undefined}
              />
            ))}
          </Bar>
          <Bar dataKey="diesel" name="Diesel" stackId="fuel" fill={FUEL_COLORS.diesel}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />
            ))}
          </Bar>
          <Bar dataKey="gasoline" name="Gasoline" stackId="fuel" fill={FUEL_COLORS.gasoline}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />
            ))}
          </Bar>
          <Bar dataKey="jet_fuel" name="Jet fuel" stackId="fuel" fill={FUEL_COLORS.jet_fuel}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />
            ))}
          </Bar>
          <Bar dataKey="fuel_oil" name="Fuel oil" stackId="fuel" fill={FUEL_COLORS.fuel_oil}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />
            ))}
          </Bar>
          <Bar dataKey="lpg" name="LPG" stackId="fuel" fill={FUEL_COLORS.lpg}>
            {chartData.map((entry, i) => (
              <Cell key={i} fillOpacity={entry.source === "government" ? 1 : 0.4} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="flex gap-4 mt-2 text-[9px] text-label-light">
        <span>
          <span className="inline-block w-3 h-3 bg-border-heavy mr-1 align-middle" />
          Solid = government data
        </span>
        <span>
          <span className="inline-block w-3 h-3 bg-border-heavy/40 mr-1 align-middle" />
          Faded = AIS estimate (provisional)
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire chart into page**

Update `src/app/page.tsx` — add import:

```tsx
import HistoricalChart from "@/components/HistoricalChart";
```

Add after the DashboardGrid in the JSX, replacing the `{/* Historical chart will go here */}` comment:

```tsx
      <div className="mb-6">
        <p className="text-[10px] uppercase tracking-label text-label mb-2">
          Monthly fuel imports by type
        </p>
        <HistoricalChart
          imports={data.imports.imports_by_month}
          monthlyEstimates={data.monthlyEstimates}
        />
        <p className="text-[9px] text-label-light mt-2">
          Source: Australian Petroleum Statistics, Dept of Climate Change, Energy, the Environment and Water
        </p>
      </div>
```

- [ ] **Step 4: Verify it builds**

```bash
npm run build
```

Expected: Builds. Chart renders (empty with seed data, populated once real data flows).

- [ ] **Step 5: Commit**

```bash
git add src/components/HistoricalChart.tsx src/app/page.tsx package.json package-lock.json
git commit -m "feat: historical stacked bar chart with govt data and AIS estimate visual distinction"
```

---

### Task 14: Footer and stale data banner

**Files:**
- Create: `src/components/Footer.tsx`
- Create: `src/components/StaleBanner.tsx`
- Modify: `src/app/page.tsx`

- [ ] **Step 1: Create Footer component**

Create `src/components/Footer.tsx`:

```tsx
export default function Footer() {
  return (
    <footer className="border-t border-border pt-6 mt-8 pb-8">
      <p className="text-[10px] text-label-light leading-relaxed max-w-3xl">
        This site provides estimates based on publicly available AIS vessel
        tracking data and Australian Government petroleum statistics. Cargo
        volumes are approximations derived from vessel dimensions and draught
        readings. This site is not affiliated with AMSA or the Australian
        Government.
      </p>
      <p className="text-[10px] text-label-light mt-3">
        With love from{" "}
        <a
          href="https://x.com/jameswilson"
          target="_blank"
          rel="noopener noreferrer"
          className="underline hover:text-label"
        >
          James Wilson
        </a>
      </p>
    </footer>
  );
}
```

- [ ] **Step 2: Create StaleBanner component**

Create `src/components/StaleBanner.tsx`:

```tsx
interface StaleBannerProps {
  timestamp: string;
}

export default function StaleBanner({ timestamp }: StaleBannerProps) {
  if (!timestamp) return null;

  const lastUpdate = new Date(timestamp);
  const now = new Date();
  const hoursAgo = (now.getTime() - lastUpdate.getTime()) / (1000 * 60 * 60);

  // Show banner if data is more than 36 hours old (allows for timezone/cron variance)
  if (hoursAgo < 36) return null;

  const formatted = lastUpdate.toLocaleDateString("en-AU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Australia/Sydney",
    timeZoneName: "short",
  });

  return (
    <div className="bg-panel border border-border px-4 py-3 mb-6 text-sm text-label">
      Data last updated {formatted}. Live collection unavailable — showing
      most recent snapshot.
    </div>
  );
}
```

- [ ] **Step 3: Wire into page**

Update `src/app/page.tsx` — add imports:

```tsx
import Footer from "@/components/Footer";
import StaleBanner from "@/components/StaleBanner";
```

Add `<StaleBanner timestamp={data.snapshot.timestamp} />` right after `<main>` opens, before the Header. Add `<Footer />` just before `</main>` closes.

- [ ] **Step 4: Verify it builds**

```bash
npm run build
```

Expected: Builds. Footer shows disclaimer and attribution link. Stale banner shows because seed data has old/empty timestamp.

- [ ] **Step 5: Commit**

```bash
git add src/components/Footer.tsx src/components/StaleBanner.tsx src/app/page.tsx
git commit -m "feat: footer with disclaimer and attribution, stale data warning banner"
```

---

## Phase 5: Deployment

### Task 15: GitHub Actions nightly workflow

**Files:**
- Create: `.github/workflows/nightly-update.yml`

- [ ] **Step 1: Create the GitHub Actions workflow**

Create `.github/workflows/nightly-update.yml`:

```yaml
name: Nightly Data Update & Deploy

on:
  schedule:
    # Run at 16:00 UTC (02:00 AEST)
    - cron: "0 16 * * *"
  workflow_dispatch: # Allow manual trigger

permissions:
  contents: write
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

jobs:
  collect-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 45

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
          cache-dependency-path: "pipeline/requirements.txt"

      - name: Install Python dependencies
        run: pip install -r pipeline/requirements.txt

      - name: Run data collection pipeline
        env:
          AISSTREAM_API_KEY: ${{ secrets.AISSTREAM_API_KEY }}
          COLLECTION_DURATION: "1800"
        run: python -m pipeline.orchestrator

      - name: Commit updated data
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --staged --quiet || git commit -m "data: nightly update $(date -u +%Y-%m-%d)"
          git push

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"

      - name: Install Node dependencies
        run: npm ci

      - name: Build Next.js static site
        run: npm run build

      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: out

      - name: Deploy to GitHub Pages
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/nightly-update.yml
git commit -m "feat: GitHub Actions nightly workflow — collect, commit data, build, deploy"
```

---

### Task 16: GitHub Pages configuration

**Files:**
- Modify: `next.config.ts` (if repo name requires basePath)

- [ ] **Step 1: Ensure Next.js static export produces correct output**

Run a full build to verify the `out/` directory is created:

```bash
npm run build
ls out/
```

Expected: `out/` directory contains `index.html` and static assets.

- [ ] **Step 2: Create a README for the repo**

Create `README.md`:

```markdown
# Australian Fuel Import Monitor

Tracks oil and liquid fuel tankers en route to Australia. Updated nightly from AIS vessel tracking data and Australian Government petroleum statistics.

## Setup

### Prerequisites
- Node.js 20+
- Python 3.12+

### Install
```bash
npm install
pip install -r pipeline/requirements.txt
```

### Run locally
```bash
npm run dev
```

### Run data pipeline
```bash
export AISSTREAM_API_KEY=your_key_here
python -m pipeline.orchestrator
```

## Deployment

Deployed automatically via GitHub Actions to GitHub Pages. Runs nightly at 02:00 AEST.

### Required secrets
- `AISSTREAM_API_KEY` — Get a free key at [aisstream.io](https://aisstream.io)

### Custom domain
1. Add your domain in GitHub repo Settings → Pages → Custom domain
2. Create a CNAME DNS record pointing to `<username>.github.io`
3. GitHub provides free HTTPS via Let's Encrypt
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and deployment instructions"
```

---

## Phase 6: Integration & First Run

### Task 17: End-to-end integration test

- [ ] **Step 1: Set up AISStream API key**

Sign up at aisstream.io with GitHub, generate an API key. Set it as an environment variable:

```bash
export AISSTREAM_API_KEY=your_actual_key
```

- [ ] **Step 2: Run a short collection test**

```bash
cd C:/Users/wilso/Documents/Claude/Projects/aus-fuel-shipments
COLLECTION_DURATION=120 python -m pipeline.orchestrator
```

Expected: Pipeline runs for 2 minutes, outputs snapshot.json with real vessel data, detects no arrivals (first run), creates vessel database.

- [ ] **Step 3: Verify the frontend renders real data**

```bash
npm run dev
```

Open http://localhost:3000. Expected: Map shows actual tanker positions. Table lists real vessels. Stats show non-zero numbers. Historical chart shows government data (if imports.json was populated).

- [ ] **Step 4: Run all Python tests**

```bash
python -m pytest pipeline/tests/ -v
```

Expected: All tests pass.

- [ ] **Step 5: Run a full static build**

```bash
npm run build
```

Expected: Static export succeeds with real data.

- [ ] **Step 6: Commit real data from first collection**

```bash
git add data/
git commit -m "data: initial collection — first real vessel snapshot"
```

---

### Task 18: Push to GitHub and enable Pages

- [ ] **Step 1: Create GitHub repo**

```bash
gh repo create aus-fuel-import-monitor --public --source=. --remote=origin
```

- [ ] **Step 2: Add AISStream API key as a repo secret**

```bash
gh secret set AISSTREAM_API_KEY
```

(Paste the API key when prompted)

- [ ] **Step 3: Push and verify**

```bash
git push -u origin main
```

- [ ] **Step 4: Enable GitHub Pages**

In the GitHub repo settings, go to Pages → Source → select "GitHub Actions".

- [ ] **Step 5: Trigger the workflow manually to verify deployment**

```bash
gh workflow run "Nightly Data Update & Deploy"
```

Monitor at: `gh run watch`

Expected: Workflow completes. Site is live at `https://<username>.github.io/aus-fuel-import-monitor/`.

- [ ] **Step 6: Commit any basePath fix if needed**

If the site is at a subpath (e.g. `/aus-fuel-import-monitor/`), update `next.config.ts`:

```typescript
const nextConfig: NextConfig = {
  output: "export",
  basePath: "/aus-fuel-import-monitor",
  images: {
    unoptimized: true,
  },
};
```

Commit and push if changed.
