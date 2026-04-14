# Destination Parser Word-Boundary Matching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace naive substring matching in `pipeline/destinations.py` with precompiled word-boundary regex to eliminate the class of false positives that caused `"PORT EVERGLADES"` to parse as `"Gladstone"`.

**Architecture:** Keep `_PORT_PATTERNS` as human-editable strings. Derive a precompiled `_COMPILED_PORT_PATTERNS` at module import. Change `parse_destination`'s lookup to use `re.search` with the precompiled patterns. `_AU_INDICATORS` stays substring-based.

**Tech Stack:** Python 3.12, `re` (stdlib), `pytest`.

---

## File Structure

- **Modify** `pipeline/destinations.py` — add `re` import, add `_COMPILED_PORT_PATTERNS`, change lookup in `parse_destination`.
- **Modify** `pipeline/tests/test_destinations.py` — add tests for the false-positive cases and a guard test confirming bare short codes still match.

No new files.

---

## Task 1: Write failing tests for the false-positive cases

**Files:**
- Modify: `pipeline/tests/test_destinations.py`

- [ ] **Step 1: Append failing tests**

Append to `pipeline/tests/test_destinations.py`:

```python
def test_everglades_does_not_false_match_gladstone():
    # "glad" is a substring of "everglades" but not a word inside it
    assert parse_destination("EVERGLADES") is None


def test_port_everglades_does_not_false_match_gladstone():
    # Real-world false positive observed in first multi-region run
    assert parse_destination("PORT EVERGLADES") is None


def test_bare_glad_still_matches_gladstone():
    # Whitespace-delimited bare abbreviation must still resolve
    assert parse_destination("GLAD") == "Gladstone"


def test_au_glad_still_matches_gladstone():
    # Country-prefixed short form must still resolve
    assert parse_destination("AU GLAD") == "Gladstone"


def test_freeport_does_not_false_match_fremantle():
    # "fre" is a substring of "freeport" but not a word inside it
    assert parse_destination("FREEPORT") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest pipeline/tests/test_destinations.py -v`
Expected (before the fix):
- `test_everglades_does_not_false_match_gladstone` — FAIL (currently returns `"Gladstone"`)
- `test_port_everglades_does_not_false_match_gladstone` — FAIL
- `test_freeport_does_not_false_match_fremantle` — FAIL
- `test_bare_glad_still_matches_gladstone` — PASS (current code already handles this)
- `test_au_glad_still_matches_gladstone` — PASS
- All 15 pre-existing tests — PASS

If any of the PASS expectations is FAIL or vice versa, stop and report — this suggests the spec's assumptions don't match real current behaviour.

- [ ] **Step 3: Commit failing tests**

```bash
git add pipeline/tests/test_destinations.py
git commit -m "$(cat <<'EOF'
test: failing cases for destination-parser false positives

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Switch parser to precompiled word-boundary regex

**Files:**
- Modify: `pipeline/destinations.py`

- [ ] **Step 1: Read the current file**

Read `pipeline/destinations.py` in full. Key elements:
- `_PORT_PATTERNS` (lines 3–14)
- `_AU_INDICATORS` (line 16)
- `parse_destination` (lines 19–32)

- [ ] **Step 2: Replace the implementation**

Replace the entire contents of `pipeline/destinations.py` with:

```python
"""Parse AIS destination strings into Australian port names."""

import re

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

# Precompile each port pattern with word boundaries so short abbreviations
# like "glad" no longer substring-match inside words like "everglades".
_COMPILED_PORT_PATTERNS: list[tuple[list[re.Pattern[str]], str]] = [
    ([re.compile(rf"\b{re.escape(p)}\b") for p in patterns], port_name)
    for patterns, port_name in _PORT_PATTERNS
]


def parse_destination(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if not cleaned:
        return None
    for compiled_patterns, port_name in _COMPILED_PORT_PATTERNS:
        if any(p.search(cleaned) for p in compiled_patterns):
            return port_name
    for indicator in _AU_INDICATORS:
        if indicator in cleaned:
            return "Australia (port unknown)"
    return None
```

- [ ] **Step 3: Run the destination tests to confirm they all pass**

Run: `python -m pytest pipeline/tests/test_destinations.py -v`
Expected: 20 passed (15 pre-existing + 5 new). No failures, no errors.

If any previously-passing test now fails, stop — the word-boundary change may have broken a legitimate match (for example, a pattern containing a regex-special character that should have been escaped, or an edge case in `_AU_INDICATORS`). Report back rather than guessing.

- [ ] **Step 4: Run the full suite to confirm no downstream regressions**

Run: `python -m pytest pipeline/tests/ -v`
Expected: 69 passed (64 pre-existing + 5 new).

- [ ] **Step 5: Smoke-check the fix against the real false positive**

Run: `python -c "from pipeline.destinations import parse_destination; print(repr(parse_destination('PORT EVERGLADES')))"`
Expected: `None`

Run: `python -c "from pipeline.destinations import parse_destination; print(repr(parse_destination('GLADSTONE')))"`
Expected: `'Gladstone'`

- [ ] **Step 6: Commit**

```bash
git add pipeline/destinations.py
git commit -m "$(cat <<'EOF'
fix: word-boundary matching in destination parser

Prevents substring false positives (e.g. "everglades" matching the
"glad" pattern and resolving to Gladstone). Port patterns are now
precompiled with \b boundaries; AU_INDICATORS stay substring-based.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** Problem and goal addressed by Task 2's regex change. Non-goals respected — port list unchanged, `_AU_INDICATORS` unchanged, function signature unchanged.
- **Regression guard:** Task 1 adds 5 tests; Task 2 must keep all 20 tests in `test_destinations.py` passing. Any break means investigate, don't paper over.
- **`re.escape` consistency:** Used on every pattern to handle any future additions with regex-significant characters.
- **Performance:** Parsing runs once per vessel in the post-processing pass — trivial. No hot-loop concern.
