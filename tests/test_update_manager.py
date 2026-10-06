from io import BytesIO
import json

from ais_atis_bridge import update_manager


def remote(version):
    def response(request, **kwargs):
        if 'update_manifest.json' in request.full_url:
            return BytesIO(b'{"files":{"VERSION":"test"}}')
        return BytesIO(version)
    return response


def test_same_version_beta_channel_switch_is_offered_without_losing_installed_channel(tmp_path, monkeypatch):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"selected": "develop", "installed": "main"}), encoding="utf-8")
    monkeypatch.setattr(update_manager, "CHANNEL_FILE", channel_file)
    monkeypatch.setattr(update_manager, "STATUS_FILE", tmp_path / "status.json")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.9\n", encoding="utf-8")
    monkeypatch.setattr(update_manager, "VERSION_FILE", version_file)
    monkeypatch.setattr(update_manager, "urlopen", remote(b"0.1.9\n"))

    status = update_manager.check_remote_version()
    assert status["same_version"] is True
    assert status["update_available"] is True
    assert status["source_channel"] == "develop"
    assert status["installed_channel"] == "main"
    assert status["channel_change_pending"] is True


def test_older_release_is_available_when_switching_channels(tmp_path, monkeypatch):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"selected": "main", "installed": "develop"}), encoding="utf-8")
    monkeypatch.setattr(update_manager, "CHANNEL_FILE", channel_file)
    monkeypatch.setattr(update_manager, "STATUS_FILE", tmp_path / "status.json")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.9\n", encoding="utf-8")
    monkeypatch.setattr(update_manager, "VERSION_FILE", version_file)
    monkeypatch.setattr(update_manager, "urlopen", remote(b"0.1.8\n"))

    status = update_manager.check_remote_version()
    assert status["local_ahead"] is True
    assert status["update_available"] is True
    assert status["channel_change_pending"] is True


def test_older_release_is_not_available_within_installed_channel(tmp_path, monkeypatch):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"selected": "main", "installed": "main"}), encoding="utf-8")
    monkeypatch.setattr(update_manager, "CHANNEL_FILE", channel_file)
    monkeypatch.setattr(update_manager, "STATUS_FILE", tmp_path / "status.json")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.1.9\n", encoding="utf-8")
    monkeypatch.setattr(update_manager, "VERSION_FILE", version_file)
    monkeypatch.setattr(update_manager, "urlopen", remote(b"0.1.8\n"))

    status = update_manager.check_remote_version()
    assert status["local_ahead"] is True
    assert status["update_available"] is False


def test_channel_change_is_rejected_while_update_worker_is_active(tmp_path, monkeypatch):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"selected": "main", "installed": "main"}), encoding="utf-8")
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"state": "installing"}), encoding="utf-8")
    monkeypatch.setattr(update_manager, "CHANNEL_FILE", channel_file)
    monkeypatch.setattr(update_manager, "STATUS_FILE", status_file)
    monkeypatch.setattr(update_manager.subprocess, "run", lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": "activating\n"})())
    import pytest
    with pytest.raises(RuntimeError):
        update_manager.set_channel("develop")
