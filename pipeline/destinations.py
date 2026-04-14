"""Parse AIS destination strings into Australian port names."""

import re

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

# Kept substring-based: entries encode their own whitespace delimiters
# (e.g. "au ", " au") which word-boundary regex would mishandle at string ends.
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
