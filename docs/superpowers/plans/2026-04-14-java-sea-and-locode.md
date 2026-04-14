# Java Sea Carve-Out + AU LOCODE Parsing Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to execute. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Two related fixes uncovered while inspecting the first multi-region collector run.

1. **Java Sea bug (#3 from feedback):** Indonesian domestic tankers around Lamongan/Tuban/Paciran (clustered at lat ~-7, lon ~112-114) are being kept by `AU_APPROACH`'s "keep all" rule. They have no AU destination. Fix by adding a `JAVA_SEA` carve-out region that requires destination filtering, listed first in `REGIONS` so it shadows `AU_APPROACH`.

2. **AU LOCODE parsing:** Real AU-bound vessels declare destinations using 5-letter UN/LOCODE codes (`AUBTB`, `AUKWI`, `AUBUY`, `AUGLT`, `AUFRE`, etc.) which the parser doesn't currently recognise — they show up as "Unknown" in the table. Add the codes as patterns under their respective ports.

**Architecture:** Both are pure-data edits to existing modules. No new files; no signature changes; no schema changes downstream.

**Tech Stack:** Python 3.12, pytest.

---

## File Structure

- **Modify** `pipeline/regions.py` — insert `JAVA_SEA` entry first in `REGIONS`.
- **Modify** `pipeline/tests/test_regions.py` — add tests for `JAVA_SEA` classification + retention.
- **Modify** `pipeline/destinations.py` — append LOCODE codes to existing `_PORT_PATTERNS`; add a new "Bunbury" entry.
- **Modify** `pipeline/tests/test_destinations.py` — add tests for the LOCODE codes and the new Bunbury port.

---

## Task 1: Add `JAVA_SEA` carve-out region

**Files:**
- Modify: `pipeline/regions.py`
- Modify: `pipeline/tests/test_regions.py`

### Step 1: Write failing tests

Append to `pipeline/tests/test_regions.py`:

```python
def test_classify_region_java_sea_off_lamongan():
    # Java Sea cluster observed in real data
    assert classify_region(-6.85, 112.44) == "JAVA_SEA"


def test_classify_region_java_sea_takes_priority_over_au_approach():
    # The carve-out must be listed BEFORE AU_APPROACH so Java Sea wins
    # at lat -6.85 (which is also inside the broad AU_APPROACH box).
    assert classify_region(-6.85, 112.44) == "JAVA_SEA"


def test_classify_region_south_of_java_sea_still_au_approach():
    # South of the Java coast (-7.5 cutoff) → falls through to AU_APPROACH
    assert classify_region(-8.0, 112.0) == "AU_APPROACH"


def test_classify_region_east_of_java_sea_still_au_approach():
    # East of lon 117 (Bali/Flores Sea) → falls through to AU_APPROACH
    assert classify_region(-7.0, 121.0) == "AU_APPROACH"


def test_should_drop_java_sea_vessel_without_au_destination():
    # Java Sea vessel with Indonesian destination — must be dropped
    assert should_keep_vessel("JAVA_SEA", None) is False


def test_should_keep_java_sea_vessel_with_au_destination():
    # Hypothetical: a vessel in the Java Sea with AU destination → keep
    assert should_keep_vessel("JAVA_SEA", "Fremantle") is True
```

### Step 2: Run tests, expect failures

Run: `python -m pytest pipeline/tests/test_regions.py -v`

Expected:
- `test_classify_region_java_sea_off_lamongan` — **FAIL** (currently returns `"AU_APPROACH"`)
- `test_classify_region_java_sea_takes_priority_over_au_approach` — **FAIL** (same reason)
- `test_should_drop_java_sea_vessel_without_au_destination` — **FAIL** (the function treats `"JAVA_SEA"` as a known origin region and returns `False`, but only because the implementation doesn't actually need `JAVA_SEA` to exist in `REGIONS` to evaluate `should_keep_vessel`. **Wait — re-check this:** `should_keep_vessel` only inspects the region string and destination. `should_keep_vessel("JAVA_SEA", None)` returns `False` because region is not `"AU_APPROACH"` and destination is None. So this test will actually **PASS** without the fix. Mark this expectation as **PASS** in the verification.)

Updated expected:
- `test_classify_region_java_sea_off_lamongan` — **FAIL**
- `test_classify_region_java_sea_takes_priority_over_au_approach` — **FAIL**
- `test_classify_region_south_of_java_sea_still_au_approach` — **PASS** (already)
- `test_classify_region_east_of_java_sea_still_au_approach` — **PASS** (already)
- `test_should_drop_java_sea_vessel_without_au_destination` — **PASS** (already)
- `test_should_keep_java_sea_vessel_with_au_destination` — **PASS** (already)

If the actual pattern doesn't match this, **stop and report DONE_WITH_CONCERNS** — the design assumption is wrong and the plan needs revision.

### Step 3: Add `JAVA_SEA` as the FIRST entry in `REGIONS`

In `pipeline/regions.py`, modify the `REGIONS` dict so `JAVA_SEA` is the very first entry. The comment explaining ordering should be updated too.

Replace:

```python
REGIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    "AU_APPROACH":   ((-50.0,   90.0), ( -5.0,  170.0)),
    "SE_ASIA":       (( -5.0,   95.0), ( 10.0,  120.0)),
```

with:

```python
REGIONS: dict[str, tuple[tuple[float, float], tuple[float, float]]] = {
    # JAVA_SEA must come BEFORE AU_APPROACH: it carves out the Indonesian
    # Java Sea (north of Java) from the broader AU_APPROACH box so domestic
    # Indonesian tankers (e.g. Lamongan, Tuban, Paciran) don't get retained
    # unconditionally. classify_region returns the first match.
    "JAVA_SEA":      (( -7.5,  105.0), ( -3.0,  117.0)),
    "AU_APPROACH":   ((-50.0,   90.0), ( -5.0,  170.0)),
    "SE_ASIA":       (( -5.0,   95.0), ( 10.0,  120.0)),
```

(Other entries unchanged.)

### Step 4: Run tests, expect all pass

Run: `python -m pytest pipeline/tests/test_regions.py -v`
Expected: 26 passed (20 pre-existing + 6 new, all pass).

### Step 5: Run full suite

Run: `python -m pytest pipeline/tests/ -v`
Expected: 75 passed (69 pre-existing + 6 new).

### Step 6: Commit

```bash
git add pipeline/regions.py pipeline/tests/test_regions.py
git commit -m "$(cat <<'EOF'
fix(regions): add JAVA_SEA carve-out to drop Indonesian domestic tankers

The AU_APPROACH box's "keep all" rule was scooping up Indonesian
domestic tanker traffic in the Java Sea (Lamongan, Tuban, Paciran).
JAVA_SEA is listed first in REGIONS so it shadows AU_APPROACH at
those coordinates, applying the destination-required filter.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add AU LOCODE patterns to the destination parser

**Files:**
- Modify: `pipeline/destinations.py`
- Modify: `pipeline/tests/test_destinations.py`

### Step 1: Write failing tests

Append to `pipeline/tests/test_destinations.py`:

```python
def test_locode_aubtb_botany():
    assert parse_destination("AUBTB") == "Sydney / Botany"


def test_locode_aukwi_fremantle():
    # Kwinana is part of the Fremantle metro port complex
    assert parse_destination("AUKWI") == "Fremantle"


def test_locode_aubuy_bunbury():
    assert parse_destination("AUBUY") == "Bunbury"


def test_locode_auglt_gladstone():
    assert parse_destination("AUGLT") == "Gladstone"


def test_locode_aufre_fremantle():
    assert parse_destination("AUFRE") == "Fremantle"


def test_locode_aumel_melbourne():
    assert parse_destination("AUMEL") == "Melbourne"


def test_locode_ausyd_sydney():
    assert parse_destination("AUSYD") == "Sydney / Botany"


def test_locode_audar_darwin():
    assert parse_destination("AUDAR") == "Darwin"


def test_locode_aubne_brisbane():
    assert parse_destination("AUBNE") == "Brisbane"


def test_locode_autsv_townsville():
    assert parse_destination("AUTSV") == "Townsville"


def test_locode_auadl_adelaide():
    assert parse_destination("AUADL") == "Adelaide"


def test_locode_aupkl_port_kembla():
    assert parse_destination("AUPKL") == "Port Kembla"


def test_bunbury_full_name():
    # New port entry added alongside the LOCODE
    assert parse_destination("BUNBURY") == "Bunbury"
```

### Step 2: Run tests, expect failures

Run: `python -m pytest pipeline/tests/test_destinations.py -v`

Expected: all 13 new tests **FAIL** (they currently return either `None` or `"Australia (port unknown)"`). The 20 pre-existing tests must still **PASS**.

If any pre-existing test fails, stop and report — the fix may have broken something. Otherwise proceed.

### Step 3: Add LOCODE patterns + Bunbury port

Replace the `_PORT_PATTERNS` block in `pipeline/destinations.py`:

```python
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
```

with:

```python
_PORT_PATTERNS: list[tuple[list[str], str]] = [
    (["port kembla", "kembla", "pt kembla", "ptkembla", "aupkl"], "Port Kembla"),
    (["botany", "sydney", "syd", "au syd", "pt botany", "ausyd", "aubtb"], "Sydney / Botany"),
    (["geelong", "gee", "au gee", "geelg"], "Geelong"),
    (["melbourne", "melb", "au mel", "au melb", "melbne", "aumel"], "Melbourne"),
    (["brisbane", "bris", "au bri", "bne", "aubne"], "Brisbane"),
    (["gladstone", "glad", "au gla", "auglt"], "Gladstone"),
    (["fremantle", "freo", "fre", "au fre", "fremantl", "aufre", "aukwi"], "Fremantle"),
    (["adelaide", "adel", "au ade", "adl", "auadl"], "Adelaide"),
    (["darwin", "drw", "au dar", "audar"], "Darwin"),
    (["townsville", "tsv", "au tow", "twnsv", "autsv"], "Townsville"),
    (["bunbury", "aubuy"], "Bunbury"),
]
```

Notes:
- Each port group gains its UN/LOCODE 5-letter code (where confirmed).
- "Bunbury" is a new port entry — added because `AUBUY` was observed in real data.
- `AUKWI` is mapped to Fremantle (Kwinana is part of the Fremantle Port Authority complex).
- The `_COMPILED_PORT_PATTERNS` derivation auto-recompiles from the new list — no other changes needed.

### Step 4: Run tests, expect all pass

Run: `python -m pytest pipeline/tests/test_destinations.py -v`
Expected: 33 passed (20 pre-existing + 13 new).

### Step 5: Run full suite

Run: `python -m pytest pipeline/tests/ -v`
Expected: 88 passed (75 after Task 1 + 13 new).

### Step 6: Smoke-check the previously-unparseable destinations from real data

Run:
```bash
python -c "from pipeline.destinations import parse_destination; \
  for d in ['AUBTB', 'AUKWI', 'AUBUY', 'AUGLT', 'LAMONGAN IDN', 'PORT EVERGLADES', 'AU MEL']: \
    print(f'{d!r:25s} -> {parse_destination(d)!r}')"
```

Expected output (formatted):
```
'AUBTB'                   -> 'Sydney / Botany'
'AUKWI'                   -> 'Fremantle'
'AUBUY'                   -> 'Bunbury'
'AUGLT'                   -> 'Gladstone'
'LAMONGAN IDN'            -> None
'PORT EVERGLADES'         -> None
'AU MEL'                  -> 'Melbourne'
```

### Step 7: Commit

```bash
git add pipeline/destinations.py pipeline/tests/test_destinations.py
git commit -m "$(cat <<'EOF'
feat(destinations): recognise AU UN/LOCODE 5-letter port codes

Adds AUBTB, AUKWI, AUBUY, AUGLT, AUFRE, AUMEL, AUSYD, AUDAR,
AUBNE, AUTSV, AUADL, AUPKL to the existing port pattern groups.
Adds Bunbury as a new port entry (observed AUBUY in real data).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:**
  - Java Sea bug: JAVA_SEA region added before AU_APPROACH → Indonesian Java Sea ships drop unless AU-destined. Verified against real data points (Lamongan, Tuban, Paciran cluster).
  - LOCODE: 12 known AU LOCODEs added to existing port groups; new Bunbury group added.
- **Backwards compatibility:** No signature changes, no schema changes. All existing tests must continue to pass (20 destinations + 20 regions = 40 pre-existing).
- **Region ordering:** JAVA_SEA explicitly first in REGIONS dict. Verified that `should_keep_vessel("JAVA_SEA", None)` is `False` without code change because the function treats anything that's not `AU_APPROACH` (and not `None`) as a destination-gated region.
- **Word-boundary regex still applies** to all new patterns — `\bauglt\b` matches "AUGLT" and "AUGLT > AUSYD" but not "PAUGLTLY" (hypothetical).
