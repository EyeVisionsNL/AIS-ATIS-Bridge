from unittest.mock import patch

import pytest

from ais_atis_bridge import config
from ais_atis_bridge.app import create_app
from ais_atis_bridge.runtime import ReceiverRuntime


@pytest.mark.parametrize("tuning", ["fixed", "scan"])
@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_squelch_save_reload_and_receiver_config(tmp_path, monkeypatch, tuning, mode):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    config.save({**config.DEFAULTS, "ais_viewer_url": "http://localhost:8443/map/"})
    client = create_app().test_client()
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = client.post("/api/settings", json={
            "receiver": "TEST", "tuning_mode": tuning,
            "squelch_mode": mode, "squelch_threshold_dbfs": -47,
        })
        assert response.status_code == 200
        saved = config.load()
        assert saved["squelch_mode"] == mode
        assert saved["ais_viewer_url"] == "http://localhost:8443/map/"
        rendered = ReceiverRuntime.render_airband_config(start.call_args.args[0])
        assert ("squelch_threshold = -47;" in rendered) == (mode == "manual")
        assert ("squelch_snr_threshold = 4.0;" in rendered) == (mode == "auto")


@pytest.mark.parametrize("threshold", [0, -101, -47.5, "NaN", None])
def test_invalid_squelch_does_not_restart_receiver(tmp_path, monkeypatch, threshold):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = create_app().test_client().post("/api/settings", json={"squelch_threshold_dbfs": threshold})
        assert response.status_code == 400
        start.assert_not_called()


def test_stale_atis_cannot_select_map_vessel(tmp_path, monkeypatch):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    with patch("ais_atis_bridge.app.runtime.status", return_value={"latest": {
        "atis_code": "9244123456", "fresh": False,
    }}), patch("ais_atis_bridge.app.ais.read_ships") as read:
        assert create_app().test_client().get("/api/status").json["ais_match"] is None
        read.assert_not_called()


def test_scan_interval_save_reload_and_receiver_config(tmp_path, monkeypatch):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    client = create_app().test_client()
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = client.post("/api/settings", json={
            "receiver": "TEST", "scan_interval_ms": 100,
        })
        assert response.status_code == 200
        assert config.load()["scan_interval_ms"] == 100
        rendered = ReceiverRuntime.render_airband_config(start.call_args.args[0])
        assert "scan_interval_ms = 100;" in rendered


@pytest.mark.parametrize("value", [99, 125, 501])
def test_invalid_scan_interval_does_not_restart_receiver(tmp_path, monkeypatch, value):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = create_app().test_client().post("/api/settings", json={"scan_interval_ms": value})
        assert response.status_code == 400
        start.assert_not_called()
