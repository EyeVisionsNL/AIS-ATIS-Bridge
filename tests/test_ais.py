from ais_atis_bridge.ais import codes_for_ship, match_atis


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
