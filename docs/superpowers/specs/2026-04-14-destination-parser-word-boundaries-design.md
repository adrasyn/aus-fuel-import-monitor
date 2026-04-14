# Destination Parser Word-Boundary Matching Design

**Date:** 2026-04-14
**Status:** Proposed

## Problem

`pipeline/destinations.py` uses naive substring matching (`if pattern in cleaned`) to map messy AIS destination strings to Australian port names. When destinations were only used as display labels, this was harmless. Now that the new multi-region collector uses the parsed destination as a **retention gate** for vessels in origin regions, false positives cause non-Australian vessels to be kept.

Confirmed real-world false positive from the first multi-region run:

| Raw AIS destination | Parsed as | Problem |
|---|---|---|
| `"PORT EVERGLADES"` (Florida) | `"Gladstone"` | `"glad"` is a substring of "everglades" |

Other latent risks (not yet observed but plausible):
- `"fre"` → could match "Freeport", "Frederick*"
- `"gee"` → could match various words
- `"bne"` → short enough to collide

## Goal

Eliminate substring-style false positives while preserving the parser's ability to match short, whitespace-delimited codes (e.g. a bare `"GLAD"` or `"FRE"` typed by a captain).

## Design

### 1. Word-boundary regex matching

Replace the `if pattern in cleaned` check with a precompiled regex that matches each pattern only at word boundaries.

- Patterns are lowercased and `\b`-wrapped: `r"\bglad\b"` matches `"glad"`, `"au glad"`, `"glad > au"` — but **not** `"everglades"`.
- Regexes are compiled once at module import, not per-call.
- `re.escape(pattern)` ensures patterns like `"au "` are handled correctly (the trailing space would otherwise be regex-significant).

### 2. Structure

`_PORT_PATTERNS` stays a list of `(patterns, port_name)` tuples — human-editable as plain strings. A module-level `_COMPILED_PORT_PATTERNS` is derived from it once:

```python
_COMPILED_PORT_PATTERNS: list[tuple[list[re.Pattern[str]], str]] = [
    ([re.compile(rf"\b{re.escape(p)}\b") for p in patterns], port_name)
    for patterns, port_name in _PORT_PATTERNS
]
```

Lookup becomes:

```python
for compiled_patterns, port_name in _COMPILED_PORT_PATTERNS:
    if any(p.search(cleaned) for p in compiled_patterns):
        return port_name
```

### 3. `_AU_INDICATORS` check

The secondary check (for strings containing any Australia indicator like `"australia"`, `"au "`, `"aust"`, `" au"`) stays as substring matching. These indicators are longer or contain a leading/trailing space — substring matches on them are safe in practice, and keeping them permissive preserves catchall coverage for strings we can't pin to a specific port.

### 4. Handling of the existing `au ` prefix patterns

The current patterns include entries like `"au mel"`, `"au bri"`, etc. With word boundaries and `re.escape`, these still work — `\bau mel\b` matches `"au mel"`, `"au mel > syd"`, etc., because the space between `au` and `mel` is not a boundary character.

Verify during implementation that patterns containing internal spaces (e.g. `"pt kembla"`, `"au mel"`) still behave correctly under the new regex.

## Affected files

- `pipeline/destinations.py` — swap substring check for precompiled word-boundary regex
- `pipeline/tests/test_destinations.py` — add failing tests for the false-positive cases, keep all existing tests passing

## Non-goals

- No changes to the port list or indicator list
- No changes to `_AU_INDICATORS` matching (stays substring)
- No cross-parser refactor — `parse_destination` stays a single function with the same signature
- No behaviour change for currently-correct destinations — all existing test cases must continue to pass

## Risk

- **Patterns with special regex chars.** Current patterns are plain strings, but `re.escape` guards against any future additions like `"*"` or `"."`.
- **Legitimate bare-word false positives** (e.g. a foreign port legitimately named something containing a word-bounded `"glad"`). Possible but rare; we can tighten further if observed.
- **Performance.** Parsing runs once per vessel at post-processing time — O(dozens) per snapshot. Precompiled regex is fast enough; we're not in a hot loop.
