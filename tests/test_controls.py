from unittest.mock import patch

import pytest

from ais_atis_bridge import config
from ais_atis_bridge.app import create_app
from ais_atis_bridge.runtime import ReceiverRuntime


@pytest.mark.parametrize("tuning", ["fixed", "scan"])
@pytest.mark.parametrize("threshold", [1, 3.5, 6, 12.5, 30])
def test_squelch_save_reload_and_receiver_config(tmp_path, monkeypatch, tuning, threshold):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    config.save({**config.DEFAULTS, "ais_viewer_url": "http://localhost:8443/map/"})
    client = create_app().test_client()
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = client.post("/api/settings", json={
            "receiver": "TEST", "tuning_mode": tuning,
            "squelch_snr_db": threshold,
        })
        assert response.status_code == 200
        saved = config.load()
        assert saved["squelch_snr_db"] == threshold
        assert saved["ais_viewer_url"] == "http://localhost:8443/map/"
        rendered = ReceiverRuntime.render_airband_config(start.call_args.args[0])
        assert f"squelch_snr_threshold = {threshold:.1f};" in rendered
        assert "squelch_threshold =" not in rendered
        assert "gain = 12.5;" in rendered
        assert "dest_port = 49555;" in rendered and "continuous = true;" in rendered
        assert "dest_port = 49556;" in rendered and "continuous = false;" in rendered


@pytest.mark.parametrize("threshold", [0, -1, 30.5, 31, 1.25, float("nan"), float("inf"), None, True])
def test_invalid_squelch_does_not_restart_receiver(tmp_path, monkeypatch, threshold):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    with patch("ais_atis_bridge.app.runtime.start") as start:
        response = create_app().test_client().post("/api/settings", json={"squelch_snr_db": threshold})
        assert response.status_code == 400
        start.assert_not_called()


def test_legacy_squelch_dbfs_settings_upgrade_to_snr(tmp_path, monkeypatch):
    monkeypatch.setenv("AIS_ATIS_CONFIG", str(tmp_path / "config.json"))
    import json
    target = tmp_path / "config.json"
    target.write_text(json.dumps({
        "receiver": "OLD-SDR", "gain_db": 19.2, "squelch_mode": "manual",
        "squelch_threshold_dbfs": -47, "scan_interval_ms": 250,
    }), encoding="utf-8")
    loaded = config.load()
    assert loaded["squelch_snr_db"] == 6.0
    assert "squelch_mode" not in loaded
    assert "squelch_threshold_dbfs" not in loaded
    assert loaded["receiver"] == "OLD-SDR" and loaded["gain_db"] == 19.2
    assert loaded["scan_interval_ms"] == 250
    clean = config.save(loaded)
    assert set(("squelch_mode", "squelch_threshold_dbfs")).isdisjoint(clean)
    assert config.load()["squelch_snr_db"] == 6.0


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
