from ais_atis_bridge.ais import codes_for_ship, match_atis
import pytest


def ship(**changes):
    base={"mmsi":244123456,"callsign":"PB3655","shipname":"TEST","lat":51.9,"lon":4.3,"last_signal":2,"validated":1}
    base.update(changes); return base


def test_direct_mmsi_match():
    result=match_atis("9244123456",{"ships":[ship()]})
    assert result["matched"] is True and result["mmsi"] == "244123456"


def test_standard_callsign_code_is_derived():
    assert "9244023655" in codes_for_ship(ship())


def test_ambiguous_match_fails_closed():
    result=match_atis("9244123456",{"ships":[ship(),ship()]})
    assert result["matched"] is False and result["status"] == "ambiguous"


def test_stale_match_is_rejected():
    result=match_atis("9244123456",{"ships":[ship(last_signal=60)]})
    assert result["status"] == "stale"


def barendsz(**changes):
    # AIS fields captured live; ATIS code below is reconstructed from PD4821.
    base = ship(mmsi=205595190, callsign="PD4821", shipname="BARENDSZ",
                lat=51.894085, lon=4.32698, last_signal=8)
    base.update(changes)
    return base


@pytest.mark.parametrize("mid", [244, 245, 246])
def test_dutch_callsign_matches_foreign_mmsi(mid):
    result = match_atis(f"9{mid}044821", {"ships": [barendsz(callsign=" pd4821 ")]})
    assert result["matched"] is True
    assert result["mmsi"] == "205595190"
    assert result["callsign"] == "PD4821"
    assert result["shipname"] == "BARENDSZ"
    assert result["match_method"] == "callsign_exact_fallback"


@pytest.mark.parametrize("changes,status", [
    ({"last_signal": 31}, "stale"),
    ({"last_signal": None}, "stale"),
    ({"validated": 0}, "not_validated"),
    ({"lat": 91}, "invalid_position"),
    ({"mmsi": 123}, "invalid_position"),
    ({"callsign": "PD4822"}, "not_found"),
])
def test_fallback_keeps_validation(changes, status):
    result = match_atis("9244044821", {"ships": [barendsz(**changes)]})
    assert result["matched"] is False
    assert result["status"] == status


def test_fallback_duplicate_rejected():
    result = match_atis("9244044821", [barendsz(), barendsz(mmsi=205595191)])
    assert result["status"] == "ambiguous" and not result["matched"]


def test_standard_rejection_not_bypassed():
    standard = barendsz(mmsi=244595190, last_signal=31)
    result = match_atis("9244044821", [standard, barendsz()])
    assert result["status"] == "stale" and not result["matched"]
    result = match_atis("9244044821", [standard, barendsz(mmsi=244595191), barendsz()])
    assert result["status"] == "ambiguous" and not result["matched"]


@pytest.mark.parametrize("code", ["9211044821", "9244004821", "9244274821", "invalid"])
def test_no_foreign_or_invalid_projection(code):
    assert not match_atis(code, [barendsz()])["matched"]


@pytest.mark.parametrize("code,method", [
    ("9205044821", "callsign_standard"), ("9205595190", "mmsi_direct"),
])
def test_standard_matching_preserved(code, method):
    result = match_atis(code, [barendsz()])
    assert result["matched"] and result["match_method"] == method


def test_fallback_respects_explicit_age_limit():
    assert match_atis("9244044821", [barendsz()], max_age_seconds=7)["status"] == "stale"
