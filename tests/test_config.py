import pytest
from ais_atis_bridge.config import validate


def test_defaults_are_valid():
    result=validate({})
    assert result["tuning_mode"]=="scan" and len(result["channels"])>1
def test_non_local_ais_url_is_rejected():
    with pytest.raises(ValueError): validate({"ais_ships_url":"https://example.com/ships.json"})
def test_frequency_is_bounded():
    with pytest.raises(ValueError): validate({"channels":[{"id":"bad","label":"Bad","frequency_mhz":145.8,"scan_enabled":True}]})

def test_scan_requires_enabled_channel():
    with pytest.raises(ValueError): validate({"channels":[{"id":"x","label":"X","frequency_mhz":160.6,"scan_enabled":False}]})


def test_scan_interval_defaults_to_200_ms():
    assert validate({})["scan_interval_ms"] == 200


@pytest.mark.parametrize("value", [99, 125, 501, "fast", None])
def test_scan_interval_is_bounded_and_stepped(value):
    with pytest.raises(ValueError):
        validate({"scan_interval_ms": value})
