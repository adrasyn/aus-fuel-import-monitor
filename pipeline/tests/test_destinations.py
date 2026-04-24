from pipeline.destinations import parse_destination, looks_foreign

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
    assert parse_destination("AUSTRALIA") == "Australia (port unknown)"

def test_unknown_non_australian():
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


def test_locode_aubtb_botany():
    assert parse_destination("AUBTB") == "Sydney / Botany"


def test_locode_aukwi_kwinana():
    # Kwinana is a distinct anchorage from Fremantle proper (~20km south,
    # in Cockburn Sound) and gets its own geofence — so we surface it as a
    # separate destination rather than folding it into Fremantle.
    assert parse_destination("AUKWI") == "Kwinana"


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


def test_bau_bau_idn_does_not_false_match_australia():
    # Real-world false positive: the substring "au " inside "BAU  IDN"
    # (note double space) tripped the old substring-based AU indicator check.
    # Bau-Bau is an Indonesian port; must not resolve as AU.
    assert parse_destination("BAU-BAU  IDN") is None


def test_bau_bau_single_space_does_not_false_match():
    # Same class of bug with a single space between tokens
    assert parse_destination("BAU-BAU IDN") is None


# ---------- spaced LOCODE forms ----------
# AIS operators often type the country code separately from the port code
# ("AU GLT" instead of "AUGLT"). Both forms must resolve to the same port.


def test_locode_au_glt_spaced_gladstone():
    assert parse_destination("AU GLT") == "Gladstone"


def test_locode_au_kwi_spaced_kwinana():
    assert parse_destination("AU KWI") == "Kwinana"


def test_locode_au_buy_spaced_bunbury():
    assert parse_destination("AU BUY") == "Bunbury"


def test_locode_au_btb_spaced_botany():
    assert parse_destination("AU BTB") == "Sydney / Botany"


def test_locode_au_pkl_spaced_port_kembla():
    assert parse_destination("AU PKL") == "Port Kembla"


# ---------- looks_foreign ----------

def test_looks_foreign_nz_with_space():
    # Real-world: SOUTHERN LEADER transiting east AU coast en route to NZ
    assert looks_foreign("NZ NPL") is True


def test_looks_foreign_nz_locode():
    assert looks_foreign("NZNPL") is True


def test_looks_foreign_us_locode():
    assert looks_foreign("USFLL") is True


def test_looks_foreign_us_with_space():
    assert looks_foreign("US LAX") is True


def test_looks_foreign_au_locode_is_not_foreign():
    # AUKWI starts with "au" — must not trip the foreign check
    assert looks_foreign("AUKWI") is False


def test_looks_foreign_au_word_is_not_foreign():
    assert looks_foreign("AU MEL") is False


def test_looks_foreign_known_au_port_is_not_foreign():
    # Anything that already parses as an AU port is, by definition, not foreign
    assert looks_foreign("MELBOURNE") is False


def test_looks_foreign_mixed_route_with_au_terminus():
    # "SG SIN >> AU DAM" — leg starts in Singapore but terminates in Darwin
    assert looks_foreign("SG SIN >> AU DAM") is False


def test_looks_foreign_unknown_text_without_country_code():
    # "PORT EVERGLADES" has no country code; foreign-check shouldn't fire here.
    # The region check (US_GULF + parse=None) is what drops these vessels.
    assert looks_foreign("PORT EVERGLADES") is False


def test_looks_foreign_empty_string():
    assert looks_foreign("") is False


def test_looks_foreign_none():
    assert looks_foreign(None) is False


def test_looks_foreign_singapore_locode():
    assert looks_foreign("SGSIN") is True


def test_looks_foreign_japan_locode():
    assert looks_foreign("JPYOK") is True


# ---------- new ports ----------


def test_locode_auntl_newcastle():
    assert parse_destination("AUNTL") == "Newcastle"


def test_au_ntl_spaced_newcastle():
    assert parse_destination("AU NTL") == "Newcastle"


def test_newcastle_full_name():
    assert parse_destination("NEWCASTLE") == "Newcastle"


def test_locode_aucns_cairns():
    assert parse_destination("AUCNS") == "Cairns"


def test_cairns_full_name():
    assert parse_destination("CAIRNS") == "Cairns"


def test_locode_auget_geraldton():
    assert parse_destination("AUGET") == "Geraldton"


def test_locode_augex_geraldton():
    # Some operators use AUGEX as the alternate Geraldton LOCODE
    assert parse_destination("AUGEX") == "Geraldton"


def test_geraldton_full_name():
    assert parse_destination("GERALDTON") == "Geraldton"


def test_locode_audpo_devonport():
    assert parse_destination("AUDPO") == "Devonport"


def test_devonport_full_name():
    assert parse_destination("DEVONPORT") == "Devonport"


def test_locode_auhba_hobart():
    assert parse_destination("AUHBA") == "Hobart"


def test_hobart_full_name():
    assert parse_destination("HOBART") == "Hobart"


def test_kwinana_distinct_from_fremantle():
    # Kwinana is a separate port within the Fremantle metro complex; we now
    # surface it as its own arrival destination so we can geofence it.
    assert parse_destination("KWINANA") == "Kwinana"
    assert parse_destination("AUKWI") == "Kwinana"


# ---------- route-leg parsing (multi-segment destinations) ----------


def test_route_leg_outbound_drops_origin_match():
    # Real-world: ORCHID KEFALONIA bound out of Brisbane for the US Gulf.
    # The leading "AUBNE" is the *origin*; matching it as the destination
    # was the bug. Last leg is "USMRZ" which has no AU pattern, so we should
    # return None (the foreign region check then drops the vessel).
    assert parse_destination("AUBNE>USMRZ") is None


def test_route_leg_inbound_uses_last_segment():
    # USCP4>AUBTB — origin US, terminus Sydney/Botany. Must still resolve.
    assert parse_destination("USCP4>AUBTB") == "Sydney / Botany"


def test_route_leg_double_arrow():
    # Some operators use ">>" — splitter must collapse empty segments.
    assert parse_destination("AUGLT>>AUBNE") == "Brisbane"


def test_route_leg_au_to_au_coastal():
    # Coastal hop: terminus is Newcastle, not Sydney/Botany (the origin).
    assert parse_destination("AUBTB>AUNTL") == "Newcastle"


def test_route_leg_with_spaces():
    # Spaced separator — strip per-segment.
    assert parse_destination("CN DGG > AU KWI") == "Kwinana"


def test_looks_foreign_route_outbound_to_us():
    # AUBNE>USMRZ: origin AU, terminus US — should be flagged foreign so the
    # AU_APPROACH retention rule drops it before it pads the en-route count.
    assert looks_foreign("AUBNE>USMRZ") is True


def test_looks_foreign_route_inbound_from_us_not_foreign():
    # Origin US, terminus AU — must NOT be foreign.
    assert looks_foreign("USCP4>AUBTB") is False
