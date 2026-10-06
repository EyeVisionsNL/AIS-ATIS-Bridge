import hashlib
import io
import json
import tarfile

import pytest

from scripts import ais_atis_update_worker as worker


def make_archive(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo("AIS-ATIS-Bridge-develop/" + name)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def test_verified_stage_checks_sha256_and_version(tmp_path, monkeypatch):
    payload = {"VERSION": b"0.1.9\n", "ais_atis_bridge/app.py": b"print('safe')\n"}
    manifest = {name: hashlib.sha256(value).hexdigest() for name, value in payload.items()}
    monkeypatch.setattr(worker, "fetch", lambda *args, **kwargs: make_archive(payload))
    stage = worker.verified_stage("develop", manifest, "0.1.9", tmp_path)
    assert (stage / "VERSION").read_bytes() == payload["VERSION"]
    assert (stage / "ais_atis_bridge/app.py").read_bytes() == payload["ais_atis_bridge/app.py"]

    manifest["ais_atis_bridge/app.py"] = "0" * 64
    with pytest.raises(RuntimeError, match="SHA-256"):
        worker.verified_stage("develop", manifest, "0.1.9", tmp_path)


def test_update_manifest_rejects_parent_path(monkeypatch):
    document = json.dumps({"files": {
        "../outside": "a" * 64,
        "VERSION": "b" * 64,
        "pyproject.toml": "c" * 64,
    }}).encode()
    response = iter((b"0.1.9\n", document))
    monkeypatch.setattr(worker, "fetch", lambda *args, **kwargs: next(response))
    with pytest.raises(RuntimeError, match="Unsafe update path"):
        worker.load_manifest("develop")


def test_lower_version_is_allowed_only_for_explicit_channel_switch(tmp_path, monkeypatch):
    channel_file = tmp_path / "channel.json"
    channel_file.write_text(json.dumps({"selected": "main", "installed": "develop"}), encoding="utf-8")
    monkeypatch.setattr(worker, "CHANNEL_FILE", channel_file)
    assert worker.validate_target_version("main", "0.1.8", "0.1.9") is True

    channel_file.write_text(json.dumps({"selected": "develop", "installed": "develop"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="downgrade is blocked"):
        worker.validate_target_version("develop", "0.1.8", "0.1.9")


@pytest.mark.parametrize('fail_health', [False, True])
def test_update_transaction_and_rollback_preserve_settings(tmp_path, monkeypatch, fail_health):
    project = tmp_path / 'installed'
    project.mkdir()
    (project / 'VERSION').write_text('0.1.8\n')
    (project / 'app.txt').write_text('old code')
    channel = tmp_path / 'channel.json'
    channel.write_text('{"selected":"develop","installed":"main"}')
    config = tmp_path / 'config.json'
    config.write_text('{"receiver":"PRIVATE-SERIAL","gain_db":12.5}')
    original_config = config.read_bytes()
    for name, value in {
        'PROJECT': project, 'CHANNEL_FILE': channel, 'STATUS_FILE': tmp_path / 'status.json',
        'LOCK_FILE': tmp_path / 'lock', 'HELPER_PATH': tmp_path / 'helper',
        'UNIT_TARGET': tmp_path / 'unit', 'BACKUP_ROOT': tmp_path / 'backups',
    }.items(): monkeypatch.setattr(worker, name, value)
    payload = {'VERSION': b'0.1.9\n', 'app.txt': b'new code', 'added.txt': b'new file'}
    manifest = {key: hashlib.sha256(data).hexdigest() for key, data in payload.items()}
    monkeypatch.setattr(worker, 'load_manifest', lambda branch: (manifest, '0.1.9'))
    monkeypatch.setattr(worker, 'fetch', lambda *args: make_archive(payload))
    commands = []
    monkeypatch.setattr(worker, 'run', lambda command, **kw: commands.append(command))
    monkeypatch.setattr(worker.subprocess, 'run', lambda *a, **k: None)
    monkeypatch.setattr(worker.shutil, 'chown', lambda *a, **k: None)
    def health(version):
        assert version == '0.1.9'
        if fail_health: raise RuntimeError('simulated health failure')
    monkeypatch.setattr(worker, 'health_check', health)
    assert worker.main() == (1 if fail_health else 0)
    assert config.read_bytes() == original_config
    assert (project / 'app.txt').read_text() == ('old code' if fail_health else 'new code')
    assert (project / 'added.txt').exists() is not fail_health
    assert json.loads(channel.read_text())['installed'] == ('main' if fail_health else 'develop')
    assert json.loads(worker.STATUS_FILE.read_text())['state'] == ('failed' if fail_health else 'complete')
