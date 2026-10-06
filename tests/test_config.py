import json

import pytest
from ais_atis_bridge import config
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


def test_old_channel_bank_migrates_by_frequency_and_keeps_local_choices(tmp_path, monkeypatch):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "receiver": "LOCAL-SDR", "tuning_mode": "scan", "selected_channel_id": "old61",
        "channel_bank": "rotterdam_port", "gain_mode": "auto", "gain_db": 19.2,
        "channels": [
            {"id": "old61", "label": "Old VHF61", "frequency_mhz": 160.675, "scan_enabled": True},
            {"id": "private", "label": "Private Marine", "frequency_mhz": 162.5, "scan_enabled": False},
        ],
    }), encoding="utf-8")
    result = config.load()
    assert len(result["channels"]) == 60
    selected = next(item for item in result["channels"] if item["frequency_mhz"] == 160.675)
    assert selected["id"] == "vhf61" and selected["scan_enabled"] is True
    assert result["selected_channel_id"] == "vhf61"
    assert result["gain_mode"] == "smart" and result["gain_db"] == 19.2
    assert result["receiver"] == "LOCAL-SDR"
    assert result["channels"][-1]["id"] == "private"


@pytest.mark.parametrize("value", [99, 125, 501, "fast", None])
def test_scan_interval_is_bounded_and_stepped(value):
    with pytest.raises(ValueError):
        validate({"scan_interval_ms": value})
