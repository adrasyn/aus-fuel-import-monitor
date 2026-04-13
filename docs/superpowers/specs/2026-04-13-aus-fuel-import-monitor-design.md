# Australian Fuel Import Monitor — Design Spec

## Overview

A public website that tracks oil and liquid fuel tankers en route to Australia, showing how many vessels are inbound and how much fuel they're estimated to be carrying. Updated nightly. Fills a gap — no existing public dashboard shows incoming fuel shipments to Australia.

**Name:** Australian Fuel Import Monitor
**Audience:** Industry analysts, energy sector professionals, policy researchers — while remaining accessible to the general public.
**Tone:** Data-forward, authoritative, editorial. Not a days-of-supply calculator (that exists elsewhere). The focus is on what's coming in.

---

## Data Sources

### 1. AISStream.io — Live vessel tracking (primary)

- Free WebSocket-based real-time AIS stream
- API key obtained via GitHub login
- Provides: vessel name, MMSI, IMO number, position (lat/lon), destination, draught, dimensions (length/beam), ship type code, speed, course, heading
- Nightly collection: Python script connects to AISStream WebSocket, filters for tanker-type vessels within an Australian bounding box, listens for ~30 minutes, accumulates vessel messages, disconnects
- Builds our own port arrival database by detecting when tankers arrive at Australian port geofences

### 2. Australian Petroleum Statistics — Historical import volumes

- Published monthly by Dept of Climate Change, Energy, the Environment and Water
- Available as Excel download on data.gov.au
- URL pattern is predictable for automation
- Key sheet: "Imports volume" — monthly import volumes by fuel type in megalitres (ML), from July 2010 to present
- Fuel types: crude oil & refinery feedstocks, automotive gasoline, aviation turbine fuel, diesel oil, fuel oil, LPG
- ~3 month publication delay (e.g. January data available in March/April)
- Licensed under Creative Commons

---

## Architecture

### Pipeline (GitHub Actions nightly cron)

```
GitHub Actions (nightly cron, ~02:00 AEST)
  ├── Step 1: AISStream Collector (Python)
  │   Connect to WebSocket, listen ~30 mins
  │   Filter: tanker ship types in AU bounding box
  │   Output: data/snapshot.json (current vessels en route)
  │
  ├── Step 2: Arrival Detection (Python)
  │   Compare today's snapshot with previous snapshots
  │   Detect arrivals: vessel in port geofence + speed < 1 knot
  │   Append to: data/arrivals.json
  │   Update: data/monthly-estimates.json (running monthly totals)
  │
  ├── Step 3: Vessel Database Update (Python)
  │   Any new IMO numbers → add to data/vessels.json with dimension-based DWT estimate
  │   Existing entries retained and enriched over time
  │
  ├── Step 4: Petroleum Stats Check (Python)
  │   Download latest Excel from data.gov.au
  │   Parse "Imports volume" and "Consumption cover" sheets
  │   Output: data/imports.json
  │
  ├── Step 5: Next.js Static Build
  │   Reads all JSON from data/
  │   Generates static HTML/CSS/JS
  │
  └── Step 6: Deploy to GitHub Pages
```

### Data files

| File | Description | Updated |
|---|---|---|
| `data/snapshot.json` | Current tankers en route — position, identity, destination, draught, dimensions, ship type, speed | Nightly |
| `data/arrivals.json` | Cumulative log of detected port arrivals — vessel details, port, timestamp, estimated cargo | Nightly (appended) |
| `data/vessels.json` | Vessel database keyed by IMO — DWT estimate, tanker class, dimensions, type. Grows over time. | Nightly |
| `data/monthly-estimates.json` | Per-month estimated arrived volume and en-route volume, by fuel type. For the historical chart. | Nightly |
| `data/imports.json` | Government petroleum statistics — monthly import volumes by fuel type (July 2010–present) and consumption cover days | Monthly |
| `data/ports.json` | Australian port coordinates and geofence radii | Static, manually maintained |

### Deployment

- **Hosting:** GitHub Pages (free for public repos)
- **Automation:** GitHub Actions cron job (free for public repos, 2,000 mins/month)
- **Custom domain:** User purchases domain, points DNS to GitHub Pages, free HTTPS via Let's Encrypt
- **Repo:** Public

---

## Cargo Estimation

### Step 1 — Classify vessel by dimensions

| Class | Length | Beam | Estimated DWT |
|---|---|---|---|
| VLCC | ≥300m | ≥55m | ~260,000t |
| Suezmax | ≥250m | ≥44m | ~160,000t |
| Aframax | ≥220m | ≥40m | ~100,000t |
| LR2/Panamax | ≥200m | ≥30m | ~70,000t |
| MR (Medium Range) | ≥160m | ≥27m | ~40,000t |
| Handysize | Below MR thresholds | — | ~17,000t |

### Step 2 — Estimate load factor from draught

Each tanker class has known ballast (empty) and laden (full) draughts.

```
load_factor = (current_draught - ballast_draught) / (laden_draught - ballast_draught)
```

Clamped to 0–1. If draught is 0 or missing, assume 0.75 and flag the estimate.

### Step 3 — Calculate cargo

```
estimated_cargo_tonnes = class_DWT × load_factor
```

### Step 4 — Convert to volume

- Crude oil: ~860 kg/m³ → ~1,163 litres/tonne
- Refined products: ~820 kg/m³ → ~1,220 litres/tonne

Fuel type determined by AIS ship type code (crude tanker vs product/chemical tanker).

### Step 5 — Filter ballast vessels

If `load_factor < 0.15`, the vessel is likely returning empty. Excluded from headline numbers, shown greyed out in the vessel table with a "Ballast" tag.

### Vessel database (vessels.json)

Keyed by IMO number (permanent vessel identifier). Stores:
- Dimension-based DWT estimate and tanker class
- All observed dimensions, draughts, ship type codes
- Count of observed arrivals at Australian ports
- First seen / last seen dates

Future enhancement: enrich with actual DWT from Datalastic API (100 free calls/month).

---

## Port Arrival Detection

### Geofencing

`data/ports.json` contains coordinates and radii for major Australian fuel import ports:
- Geelong, Melbourne, Sydney/Botany, Port Kembla, Brisbane, Gladstone, Fremantle, Adelaide, Darwin, Townsville, and others as needed

A vessel is detected as "arrived" when:
1. Its position falls within a port geofence (configurable radius, ~5km default)
2. Its speed drops below 1 knot
3. It was previously seen en route in a prior snapshot

Arrival logged to `arrivals.json` with: vessel name, IMO, port, timestamp, estimated cargo (tonnes and litres), fuel type.

---

## Frontend

### Tech stack

- **Framework:** Next.js with static export (`next export`)
- **Map:** Leaflet with OpenStreetMap tiles (free)
- **Charts:** Recharts or similar React charting library
- **Styling:** Tailwind CSS or CSS modules
- **Fonts:** Instrument Serif (Google Fonts) for headlines/numbers, Inter (Google Fonts) for body/UI

### Design direction

Editorial / data journalism aesthetic:
- Pure white (`#ffffff`) background
- Cool slate greys for panels and borders (`#f8fafc`, `#e2e8f0`, `#e5e7eb`)
- Strong horizontal rules to create structure and hierarchy
- Instrument Serif for the headline sentence and large stat numbers
- Inter for labels, table text, all UI elements
- Uppercase labels with generous letter-spacing for section headers
- Minimal colour: red (`#dc2626`) for crude tankers, blue (`#1e40af`) for product tankers, otherwise monochrome
- Source attribution visible below each data section

### Page layout (Layout B — Dashboard Grid)

**Header area:**
- Site name in small uppercase: "AUSTRALIAN FUEL IMPORT MONITOR"
- Headline sentence in Instrument Serif: "24 tankers carrying an estimated 8.2 billion litres of fuel are en route to Australia"
- Update timestamp: "Updated 13 April 2026, 02:00 AEST"

**Stat bar:**
- Crude oil tanker count
- Product tanker count
- Estimated crude oil volume (litres)
- Estimated refined products volume (litres)
- Government-reported reserve days (from Petroleum Stats "Consumption cover" sheet)
- Separated by a horizontal rule below

**Map + Table (side by side, 60/40 split):**
- Left: Interactive Leaflet map showing tanker positions in the AU/SE Asia region. Red dots for crude, blue for product. Click a dot for vessel popup.
- Right: Vessel table (see columns below). Clicking a row highlights the vessel on the map. Sortable by any column.

**Historical chart (full-width below):**
- See "Historical Chart Design" section below

**Footer:**
- Data disclaimer: "This site provides estimates based on publicly available AIS vessel tracking data and Australian Government petroleum statistics. Cargo volumes are approximations derived from vessel dimensions and draught readings. This site is not affiliated with AMSA or the Australian Government."
- Attribution: "With love from James Wilson" — "James Wilson" links to https://x.com/jameswilson

### Vessel table columns

| Column | Source | Notes |
|---|---|---|
| Vessel name | AISStream | Primary identifier. Links to MarineTraffic public page via IMO. |
| Type | AIS ship type code | "Crude" or "Product" |
| Destination | AIS destination field | Parsed to Australian port name where possible. Falls back to "Australia (port unknown)". |
| Est. cargo | Calculated | DWT estimate × load factor, displayed in megalitres. Asterisk if draught was missing. |
| Tanker class | Derived from dimensions | VLCC, Suezmax, Aframax, MR, etc. |
| Speed | AISStream | Knots. Helps identify if vessel is underway or anchored. |
| Last seen | AISStream timestamp | Freshness of position data. |

### Historical chart design

The chart at the bottom of the page shows fuel import volumes over time, combining government data with our AIS-derived estimates. It tells a story across three time periods:

**Historical months (July 2010 — ~3 months ago):**
- Source: Australian Petroleum Statistics "Imports volume" sheet
- Stacked bar chart by fuel type (crude, gasoline, diesel, jet fuel, fuel oil, LPG)
- Solid bars — this is authoritative government data
- Volumes in megalitres

**Recent months (~3 months ago — last month):**
- Government data not yet published for these months
- Show our AIS-derived arrival estimates instead
- Same stacked bar format but visually distinguished: lighter shade, hatched, or outlined bars
- Labelled: "Estimated from vessel tracking"
- When government data eventually arrives for a month, the estimate is replaced by the official figure

**Current month (rightmost bar):**
- A bar that grows day by day as we detect more arrivals
- Two visual segments:
  - **Arrived:** Fuel detected arriving at Australian ports this month (vessels that entered port geofences). Grows as more vessels arrive through the month.
  - **En route:** Fuel currently on vessels heading to Australia. Fluid — shrinks as vessels arrive, replenished by new departures.
- Dashed top edge or "growing" indicator to show it's incomplete
- Updates nightly

**Chart legend clearly distinguishes:**
- Solid = government data (authoritative)
- Light/outlined = AIS estimate (provisional)
- Growing bar = current month (incomplete)

Over time, users can compare our estimates against official figures when they land — validating the estimation methodology.

### Responsive design

**Desktop (>1024px):** As described above. Map and table side-by-side.

**Tablet (768–1024px):** Map and table stack vertically. Stats wrap to 2×3 grid.

**Mobile (<768px):**
- Headline sentence stays prominent
- Stats stacked — all visible, no horizontal scrolling. 2-column grid or full-width stack.
- Map full-width, reduced height (~250px), interactive with touch (pinch-to-zoom, tap for popup)
- Table remains a real table — condensed columns, horizontal scroll if needed
- Chart full-width, touch-friendly
- All tap targets minimum 44px

---

## Error States & Data Caveats

**AISStream collection fails:**
- Show most recent successful snapshot
- Prominent banner: "Data last updated [date]. Live collection unavailable — showing most recent snapshot."
- Historical sections unaffected

**Missing/zero draught on a vessel:**
- Use 0.75 load factor assumption
- Flag in table with asterisk/icon
- Tooltip: "Draught data unavailable — cargo estimate based on typical load"

**Unparseable destination:**
- Maintain lookup table mapping common abbreviations to Australian ports (e.g. "MELB" → Melbourne, "AU GEE" → Geelong)
- If unparseable: show "Australia (port unknown)"
- If vessel heading toward AU bounding box but destination doesn't mention Australia: "Possible — unconfirmed destination"

**Petroleum Stats not yet published:**
- Chart shows data up to last available month. No error state.

**Ballast vessels:**
- Excluded from headline numbers and en-route totals
- Shown in vessel table greyed out with "Ballast" tag

**General disclaimer in footer** (see Footer section above).

---

## Scope exclusions (future enhancements, not in v1)

- Datalastic DWT enrichment (100 free calls/month for actual vessel specs)
- Source country breakdown chart (data available in Petroleum Stats but deferred)
- Import value (A$) charts
- AMSA CTS shapefile backfill for pre-launch historical vessel data
- Individual vessel detail page/view
- Notifications or alerts
- Data export/download for users
- LNG tracking
