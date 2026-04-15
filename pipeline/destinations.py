"""Parse AIS destination strings into Australian port names."""

import re

_PORT_PATTERNS: list[tuple[list[str], str]] = [
    (["port kembla", "kembla", "pt kembla", "ptkembla", "aupkl", "au pkl"], "Port Kembla"),
    (["botany", "sydney", "syd", "au syd", "pt botany", "ausyd", "aubtb", "au btb"], "Sydney / Botany"),
    (["geelong", "gee", "au gee", "geelg"], "Geelong"),
    (["melbourne", "melb", "au mel", "au melb", "melbne", "aumel"], "Melbourne"),
    (["brisbane", "bris", "au bri", "bne", "aubne"], "Brisbane"),
    (["gladstone", "glad", "au gla", "auglt", "au glt"], "Gladstone"),
    (["fremantle", "freo", "fre", "au fre", "fremantl", "aufre", "aukwi", "au kwi"], "Fremantle"),
    (["adelaide", "adel", "au ade", "adl", "auadl"], "Adelaide"),
    (["darwin", "drw", "au dar", "audar"], "Darwin"),
    (["townsville", "tsv", "au tow", "twnsv", "autsv"], "Townsville"),
    (["bunbury", "aubuy", "au buy"], "Bunbury"),
]

# Word-boundary regex so "au" as a standalone token / "aust*" prefix are
# matched, but substrings inside larger words (e.g. "bau" in "BAU-BAU IDN")
# are not. Previously these were plain substrings and "au " false-matched
# inside "bau " before whitespace.
_AU_INDICATOR_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bau\b"),      # "AU" as a standalone country-code token
    re.compile(r"\baust"),      # "aust", "austral", "australia", "australian"
]

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
    if any(p.search(cleaned) for p in _AU_INDICATOR_PATTERNS):
        return "Australia (port unknown)"
    return None


# Two-letter UN/LOCODE country prefixes for jurisdictions whose tankers
# regularly transit the AU_APPROACH bbox en route to non-AU destinations.
# Used to override AU_APPROACH's unconditional retention so e.g. NZ-bound
# vessels passing the QLD coast aren't counted as inbound to Australia.
_FOREIGN_COUNTRY_CODES = {
    "nz", "us", "sg", "cn", "jp", "kr", "ph", "my", "th",
    "vn", "in", "id", "lk", "tw", "hk", "pg",
}


def looks_foreign(raw: str | None) -> bool:
    """True if the raw AIS destination explicitly names a non-AU jurisdiction.

    Rules:
    - If the parser already resolves it to an AU port, it isn't foreign.
    - If the text contains any AU indicator anywhere, it isn't foreign
      (mixed-leg routes like "SG SIN >> AU DAM" terminate in AU).
    - If the first whitespace-delimited token is a known foreign country
      code (e.g. "nz" in "NZ NPL"), it's foreign.
    - If the first token is a 5-letter LOCODE whose first two letters are
      a known foreign country code (e.g. "USFLL"), it's foreign.
    """
    if not raw:
        return False
    cleaned = raw.strip().lower()
    if not cleaned:
        return False
    if parse_destination(raw) is not None:
        return False
    if any(p.search(cleaned) for p in _AU_INDICATOR_PATTERNS):
        return False
    tokens = cleaned.split()
    if not tokens:
        return False
    first = tokens[0]
    if first in _FOREIGN_COUNTRY_CODES:
        return True
    if len(first) == 5 and first.isalpha() and first[:2] in _FOREIGN_COUNTRY_CODES:
        return True
    return False
