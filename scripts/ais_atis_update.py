#!/usr/bin/env python3
"""Root-owned, no-argument launcher for the isolated update worker."""

from __future__ import annotations

import json
import os
import subprocess
import sys


def main() -> int:
    if os.geteuid() != 0 or len(sys.argv) != 1:
        print(json.dumps({"ok": False, "error": "Run with sudo and no arguments."}))
        return 2
    command = [
        "systemd-run", "--quiet", "--collect", "--unit=ais-atis-bridge-update.service",
        "--property=Type=oneshot", "--property=TimeoutStartSec=20min",
        "/usr/bin/python3", "/opt/ais-atis-bridge/scripts/ais_atis_update_worker.py",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"ok": False, "error": f"Could not launch update worker: {error}"}))
        return 1
    if result.returncode:
        detail = (result.stderr or result.stdout or "systemd-run failed").strip()
        print(json.dumps({"ok": False, "error": detail}))
        return result.returncode
    print(json.dumps({"ok": True, "message": "Update worker started"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
