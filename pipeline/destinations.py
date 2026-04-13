"""Parse AIS destination strings into Australian port names."""

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
    if not raw:
        return None
    cleaned = raw.strip().lower()
    if not cleaned:
        return None
    for patterns, port_name in _PORT_PATTERNS:
        for pattern in patterns:
            if pattern in cleaned or cleaned == pattern:
                return port_name
    for indicator in _AU_INDICATORS:
        if indicator in cleaned:
            return "Australia (port unknown)"
    return None
