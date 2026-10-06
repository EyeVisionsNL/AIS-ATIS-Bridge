#!/usr/bin/env python3
"""Download, verify, back up, install and health-check an AIS-ATIS update."""

from __future__ import annotations

from datetime import datetime
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from urllib.request import Request, urlopen
from uuid import uuid4


REPOSITORY = "EyeVisionsNL/AIS-ATIS-Bridge"
PROJECT = Path("/opt/ais-atis-bridge")
CHANNEL_FILE = Path("/etc/ais-atis-bridge/update-channel.json")
STATUS_FILE = Path("/var/lib/ais-atis-bridge/update-status.json")
LOCK_FILE = Path("/run/lock/ais-atis-bridge-update.lock")
HELPER_PATH = Path("/usr/local/sbin/ais-atis-update")
BACKUP_ROOT = Path("/var/backups/ais-atis-bridge")
UNIT_TARGET = Path("/etc/systemd/system/ais-atis-bridge.service")
ALLOWED_BRANCHES = {"main", "develop"}
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]?([A-Za-z0-9.-]+))?$")


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def status(state: str, message: str, **extra) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"state": state, "message": message, "updated_at": now(), **extra}
    temporary = STATUS_FILE.with_name(STATUS_FILE.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o644)
    os.replace(temporary, STATUS_FILE)


def read_channel() -> str:
    try:
        value = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
        branch = str(value.get("selected") or "main").strip().lower()
    except (OSError, ValueError, TypeError, AttributeError):
        branch = "main"
    if branch not in ALLOWED_BRANCHES:
        raise RuntimeError("Update channel must be main or develop")
    return branch


def read_installed_channel() -> str:
    try:
        value = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
        branch = str(value.get("installed") or "main").strip().lower()
    except (OSError, ValueError, TypeError, AttributeError):
        branch = "main"
    if branch not in ALLOWED_BRANCHES:
        raise RuntimeError("Installed update channel must be main or develop")
    return branch


def version_key(value: str) -> tuple:
    match = VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        raise RuntimeError(f"Unsupported version value: {value!r}")
    suffix = (match.group(4) or "").lower()
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)), 1 if not suffix else 0, suffix)


def validate_target_version(branch: str, version: str, installed_version: str) -> bool:
    """Allow an older version only when changing the explicitly selected channel."""
    switching_channels = branch != read_installed_channel()
    if version_key(version) < version_key(installed_version) and not switching_channels:
        raise RuntimeError(
            f"Selected {branch} version {version} is older than installed {installed_version}; downgrade is blocked"
        )
    return switching_channels


def fetch(url: str, maximum: int) -> bytes:
    url += ("&" if "?" in url else "?") + "check=" + uuid4().hex
    request = Request(url, headers={"User-Agent": "AIS-ATIS-Bridge-updater", "Cache-Control": "no-cache"})
    with urlopen(request, timeout=30) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise RuntimeError("Update download exceeds its size limit")
    return data


def load_manifest(branch: str) -> tuple[dict[str, str], str]:
    base = f"https://raw.githubusercontent.com/{REPOSITORY}/{branch}"
    version = fetch(base + "/VERSION", 256).decode("utf-8", "replace").strip()
    if not VERSION_RE.fullmatch(version):
        raise RuntimeError(f"Branch {branch} published an invalid VERSION")
    document = json.loads(fetch(base + "/scripts/install/update_manifest.json", 1024 * 1024))
    if not isinstance(document, dict) or not isinstance(document.get("files"), dict):
        raise RuntimeError("Update manifest has an unsupported format")
    files = document["files"]
    if not 3 <= len(files) <= 1000:
        raise RuntimeError("Update manifest contains an invalid number of files")
    for relative, digest in files.items():
        path = PurePosixPath(str(relative))
        if path.is_absolute() or ".." in path.parts or not path.parts or "\\" in str(relative):
            raise RuntimeError(f"Unsafe update path: {relative!r}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise RuntimeError(f"Invalid SHA-256 in update manifest: {relative!r}")
    required = {
        "VERSION", "pyproject.toml", "ais_atis_bridge/app.py", "ais_atis_bridge/config.py",
        "ais_atis_bridge/static/rotterdam-port-channels.json",
        "ais_atis_bridge/static/rotterdam-port-channels.xlsx",
        "scripts/ais_atis_update.py", "scripts/ais_atis_update_worker.py",
        "systemd/ais-atis-bridge.service",
    }
    if not required.issubset(files):
        raise RuntimeError("Update manifest is missing required application files")
    return files, version


def verified_stage(branch: str, files: dict[str, str], expected_version: str, directory: Path) -> Path:
    archive_url = f"https://codeload.github.com/{REPOSITORY}/tar.gz/refs/heads/{branch}"
    archive_bytes = fetch(archive_url, MAX_ARCHIVE_BYTES)
    extracted: dict[str, bytes] = {}
    total_bytes = 0
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        members = archive.getmembers()
        if not members:
            raise RuntimeError("GitHub returned an empty source archive")
        first_parts = PurePosixPath(members[0].name).parts
        if not first_parts:
            raise RuntimeError("Source archive has no root folder")
        prefix = first_parts[0]
        by_name = {PurePosixPath(member.name).as_posix(): member for member in members}
        for relative, expected_hash in files.items():
            member = by_name.get(f"{prefix}/{relative}")
            if member is None or not member.isfile() or member.issym() or member.islnk():
                raise RuntimeError(f"Source archive is missing a regular file: {relative}")
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"Could not read source file: {relative}")
            content = source.read(MAX_ARCHIVE_BYTES + 1)
            if len(content) > MAX_ARCHIVE_BYTES:
                raise RuntimeError(f"Source file exceeds size limit: {relative}")
            total_bytes += len(content)
            if total_bytes > MAX_ARCHIVE_BYTES:
                raise RuntimeError("Verified update files exceed the aggregate size limit")
            actual = hashlib.sha256(content).hexdigest()
            if actual != expected_hash:
                raise RuntimeError(f"SHA-256 verification failed for {relative}")
            extracted[relative] = content
    if extracted.get("VERSION", b"").decode("utf-8", "replace").strip() != expected_version:
        raise RuntimeError("VERSION does not match the checked branch")

    stage = directory / "source"
    for relative, content in extracted.items():
        target = stage.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        if target.suffix == ".sh" or target.name.endswith(".py") and relative.startswith("scripts/"):
            target.chmod(0o755)
    return stage


def run(command: list[str], *, timeout: int = 600) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise RuntimeError(detail[-2000:])


def write_channel(branch: str) -> None:
    try:
        current = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {}
    except (OSError, ValueError, TypeError):
        current = {}
    current.update(selected=branch, installed=branch)
    temporary = CHANNEL_FILE.with_name(CHANNEL_FILE.name + ".tmp")
    temporary.write_text(json.dumps(current, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o640)
    shutil.chown(temporary, user="aisatis", group="aisatis")
    os.replace(temporary, CHANNEL_FILE)


def health_check(expected_version: str, timeout: float = 25.0) -> None:
    from urllib.request import urlopen
    port = 8120
    try:
        settings = json.loads(Path("/etc/ais-atis-bridge/config.json").read_text(encoding="utf-8"))
        candidate = int(settings.get("web_port", 8120))
        if 1 <= candidate <= 65535:
            port = candidate
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    deadline = time.monotonic() + timeout
    last = "service did not become ready"
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/status", timeout=3) as response:
                if response.status == 200:
                    payload = json.loads(response.read(2 * 1024 * 1024))
                    if payload.get("version") == expected_version:
                        return
                    last = "Dashboard reports an unexpected version"
                    continue
                last = f"HTTP {response.status}"
        except Exception as error:
            last = str(error)
        time.sleep(1)
    raise RuntimeError(f"Bridge health check failed: {last}")


def main() -> int:
    lock = LOCK_FILE.open("w")
    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    branch = read_channel()
    old_version = (PROJECT / "VERSION").read_text(encoding="utf-8").strip()
    stage = backup = None
    old_files: set[str] = set()
    copied_files: set[str] = set()
    service_stopped = False
    channel_state_before = None
    channel_updated = False
    helper_backed_up = False
    unit_backed_up = False
    try:
        try:
            channel_state_before = CHANNEL_FILE.read_bytes()
        except OSError:
            channel_state_before = None
        status("downloading", f"Downloading {branch} update", branch=branch, installed_version=old_version)
        files, version = load_manifest(branch)
        channel_switch = validate_target_version(branch, version, old_version)
        with tempfile.TemporaryDirectory(prefix="ais-atis-update-") as temp_name:
            temp = Path(temp_name)
            stage = verified_stage(branch, files, version, temp)
            status("validating", "All downloaded files passed SHA-256 validation", branch=branch,
                   installed_version=old_version, latest_version=version, files=len(files),
                   channel_switch=channel_switch)
            run([str(PROJECT / "venv/bin/python"), "-m", "compileall", "-q", str(stage / "ais_atis_bridge")], timeout=60)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = BACKUP_ROOT / timestamp
            backup.mkdir(parents=True, exist_ok=True)
            if HELPER_PATH.is_file():
                shutil.copy2(HELPER_PATH, backup / "ais-atis-update")
                helper_backed_up = True
            if UNIT_TARGET.is_file():
                shutil.copy2(UNIT_TARGET, backup / "ais-atis-bridge.service")
                unit_backed_up = True
            for relative in files:
                source = PROJECT.joinpath(*PurePosixPath(relative).parts)
                if source.is_file():
                    target = backup.joinpath(*PurePosixPath(relative).parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
                    old_files.add(relative)

            status("backing_up", "Backup created; stopping the bridge service", branch=branch,
                   installed_version=old_version, latest_version=version, backup=str(backup))
            run(["systemctl", "stop", "ais-atis-bridge.service"], timeout=60)
            service_stopped = True
            status("installing", "Installing verified bridge files", branch=branch,
                   installed_version=old_version, latest_version=version, backup=str(backup))
            for relative in files:
                source = stage.joinpath(*PurePosixPath(relative).parts)
                target = PROJECT.joinpath(*PurePosixPath(relative).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied_files.add(relative)
            new_helper = PROJECT / "scripts/ais_atis_update.py"
            if new_helper.is_file():
                shutil.copy2(new_helper, HELPER_PATH)
                HELPER_PATH.chmod(0o755)
            new_unit = PROJECT / "systemd/ais-atis-bridge.service"
            if new_unit.is_file():
                shutil.copy2(new_unit, UNIT_TARGET)
                UNIT_TARGET.chmod(0o644)
                run(["systemctl", "daemon-reload"], timeout=60)
            run([str(PROJECT / "venv/bin/pip"), "install", "--disable-pip-version-check",
                 "--no-deps", "--upgrade", str(PROJECT)], timeout=600)
            run([str(PROJECT / "venv/bin/python"), "-m", "compileall", "-q", str(PROJECT / "ais_atis_bridge")], timeout=60)
            status("restarting", "Starting the updated bridge and checking its dashboard", branch=branch,
                   installed_version=old_version, latest_version=version, backup=str(backup))
            run(["systemctl", "start", "ais-atis-bridge.service"], timeout=60)
            health_check(version)
            write_channel(branch)
            channel_updated = True
            status("complete", f"Updated to {version} on {branch}", branch=branch,
                   installed_version=version, latest_version=version, backup=str(backup))
        return 0
    except Exception as error:
        if channel_updated and channel_state_before is None:
            CHANNEL_FILE.unlink(missing_ok=True)
        elif channel_updated and channel_state_before is not None:
            try:
                temporary = CHANNEL_FILE.with_name(CHANNEL_FILE.name + ".rollback")
                temporary.write_bytes(channel_state_before)
                os.chmod(temporary, 0o640)
                shutil.chown(temporary, user="aisatis", group="aisatis")
                os.replace(temporary, CHANNEL_FILE)
            except OSError:
                pass
        if service_stopped:
            try:
                subprocess.run(["systemctl", "stop", "ais-atis-bridge.service"],
                               capture_output=True, timeout=60, check=False)
                for relative in copied_files:
                    source = backup.joinpath(*PurePosixPath(relative).parts) if backup else None
                    target = PROJECT.joinpath(*PurePosixPath(relative).parts)
                    if source and relative in old_files and source.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, target)
                    else:
                        target.unlink(missing_ok=True)
                helper_backup = backup / "ais-atis-update" if backup else None
                if helper_backed_up and helper_backup and helper_backup.is_file():
                    shutil.copy2(helper_backup, HELPER_PATH)
                elif not helper_backed_up:
                    HELPER_PATH.unlink(missing_ok=True)
                unit_backup = backup / "ais-atis-bridge.service" if backup else None
                if unit_backed_up and unit_backup and unit_backup.is_file():
                    shutil.copy2(unit_backup, UNIT_TARGET)
                elif not unit_backed_up:
                    UNIT_TARGET.unlink(missing_ok=True)
                subprocess.run(["systemctl", "daemon-reload"], capture_output=True,
                               timeout=60, check=False)
                if copied_files:
                    run([str(PROJECT / "venv/bin/pip"), "install", "--disable-pip-version-check",
                         "--no-deps", "--upgrade", str(PROJECT)], timeout=600)
                subprocess.run(["systemctl", "start", "ais-atis-bridge.service"],
                               capture_output=True, timeout=60, check=False)
            except Exception:
                pass
        status("failed", str(error), branch=branch, installed_version=old_version,
               backup=str(backup) if backup else None)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
