"""Read-only update discovery and stable/beta channel selection."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
from threading import RLock
from urllib.request import Request, urlopen
from uuid import uuid4


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / "VERSION").is_file() else Path("/opt/ais-atis-bridge")
VERSION_FILE = Path(os.environ.get("AIS_ATIS_VERSION_FILE", PROJECT_ROOT / "VERSION"))
RELEASE_CHANNEL_FILE = PROJECT_ROOT / "RELEASE_CHANNEL"
CHANNEL_FILE = Path(os.environ.get("AIS_ATIS_CHANNEL_STATE", "/etc/ais-atis-bridge/update-channel.json"))
STATUS_FILE = Path(os.environ.get("AIS_ATIS_UPDATE_STATUS", "/var/lib/ais-atis-bridge/update-status.json"))
REMOTE_VERSION = "https://raw.githubusercontent.com/EyeVisionsNL/AIS-ATIS-Bridge/{channel}/VERSION"
ALLOWED_CHANNELS = {"main", "develop"}
ACTIVE_STATES = {"queued", "starting", "downloading", "validating", "backing_up", "installing", "restarting"}
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]?([A-Za-z0-9.-]+))?$")
_LOCK = RLock()
_CHECK: dict = {"latest_version": None, "last_checked_at": None, "check_error": None, "channel": None}


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _default_channel() -> str:
    try:
        configured = str(os.environ.get("AIS_ATIS_INSTALLED_CHANNEL") or
                         RELEASE_CHANNEL_FILE.read_text(encoding="utf-8").strip()).lower()
    except OSError:
        configured = "main"
    return configured if configured in ALLOWED_CHANNELS else "main"


def _read_channel_state() -> dict[str, str]:
    initial = _default_channel()
    state = {"selected": initial, "installed": initial}
    try:
        payload = json.loads(CHANNEL_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return state
    if not isinstance(payload, dict):
        return state
    for key in ("selected", "installed"):
        value = str(payload.get(key) or initial).strip().lower()
        state[key] = value if value in ALLOWED_CHANNELS else initial
    return state


def _write_channel_state(state: dict[str, str]) -> None:
    CHANNEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = CHANNEL_FILE.with_name(CHANNEL_FILE.name + ".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o640)
    temporary.replace(CHANNEL_FILE)


def version_key(value: str) -> tuple | None:
    match = VERSION_RE.fullmatch(str(value or "").strip())
    if not match:
        return None
    suffix = (match.group(4) or "").lower()
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)),
            1 if not suffix else 0, suffix)


def compare_versions(local: str, remote: str) -> int | None:
    left, right = version_key(local), version_key(remote)
    if left is None or right is None:
        return None
    return -1 if left < right else 1 if left > right else 0


def _installed_version() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def _read_worker_status() -> dict:
    try:
        value = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(value, dict):
        return {}
    if value.get("state") in ACTIVE_STATES:
        try:
            result = subprocess.run(["systemctl", "show", "--property=ActiveState", "--value", "ais-atis-bridge-update.service"],
                                        capture_output=True, text=True, timeout=3, check=False)
            active = result.returncode == 0 and result.stdout.strip() in {"active", "activating", "reloading"}
        except (OSError, subprocess.SubprocessError):
            active = False
        if not active:
            value = dict(value)
            value.update(state="interrupted", message="A previous update stopped before health checks finished. You can check and retry.")
    return value


def get_status() -> dict:
    local = _installed_version()
    state = _read_channel_state()
    with _LOCK:
        check = dict(_CHECK)
    selected = state["selected"]
    if check.get("channel") != selected:
        latest = checked_at = check_error = None
    else:
        latest, checked_at, check_error = check.get("latest_version"), check.get("last_checked_at"), check.get("check_error")
    comparison = compare_versions(local, latest) if latest else None
    channel_pending = selected != state["installed"]
    return {
        "ok": check_error is None,
        "installed_version": local,
        "latest_version": latest,
        "update_available": comparison == -1 or (channel_pending and comparison is not None),
        "same_version": comparison == 0,
        "local_ahead": comparison == 1,
        "last_checked_at": checked_at,
        "check_error": check_error,
        "worker": _read_worker_status(),
        "channel": selected,
        "source_channel": selected,
        "installed_channel": state["installed"],
        "channel_change_pending": channel_pending,
        "beta_program": selected == "develop",
    }


def check_remote_version(timeout: float = 5.0) -> dict:
    selected = _read_channel_state()["selected"]
    checked_at, latest, error = _now(), None, None
    try:
        url = REMOTE_VERSION.format(channel=selected) + "?check=" + uuid4().hex
        request = Request(url, headers={
            "User-Agent": "AIS-ATIS-Bridge-update-check",
            "Cache-Control": "no-cache, no-store", "Pragma": "no-cache",
        })
        with urlopen(request, timeout=timeout) as response:
            latest = response.read(256).decode("utf-8", "replace").strip()
        if version_key(latest) is None:
            raise ValueError(f"Unexpected remote VERSION value: {latest!r}")
        manifest_url = REMOTE_VERSION.format(channel=selected).rsplit("/", 1)[0] + "/scripts/install/update_manifest.json"
        try:
            with urlopen(Request(manifest_url, headers={"User-Agent": "AIS-ATIS-Bridge-update-check"}), timeout=timeout) as response:
                manifest = json.loads(response.read(1024 * 1024))
            if not isinstance(manifest.get("files"), dict) or "VERSION" not in manifest["files"]:
                raise ValueError("Missing VERSION hash")
        except Exception as exc:
            raise ValueError(f"{selected} {latest} does not offer a compatible update manifest yet") from exc
    except Exception as exc:  # network and HTTP failures are displayed in UI
        error = str(exc)
        latest = None
    with _LOCK:
        _CHECK.update(latest_version=latest, last_checked_at=checked_at,
                      check_error=error, channel=selected)
    return get_status()


def set_channel(channel: str) -> dict:
    selected = str(channel or "").strip().lower()
    if selected not in ALLOWED_CHANNELS:
        raise ValueError("Channel must be main or develop")
    if _read_worker_status().get("state") in ACTIVE_STATES:
        raise RuntimeError("Update channel cannot be changed while an update is running")
    state = _read_channel_state()
    state["selected"] = selected
    _write_channel_state(state)
    with _LOCK:
        _CHECK.update(latest_version=None, last_checked_at=None, check_error=None, channel=None)
    return check_remote_version()
