from __future__ import annotations

import re
import subprocess
from typing import Any

_DEVICE = re.compile(r"^\s*(\d+):\s+(.+?),\s+SN:\s*(\S+)\s*$")


def inventory() -> dict[str, Any]:
    """Return RTL-SDR inventory without claiming a receiver long-term."""
    try:
        completed = subprocess.run(
            ["rtl_test", "-t"], capture_output=True, text=True,
            timeout=2.0, check=False,
        )
        text = completed.stdout + "\n" + completed.stderr
    except subprocess.TimeoutExpired as error:
        text = (error.stdout or "") + "\n" + (error.stderr or "")
    except OSError as error:
        return {"available": False, "devices": [], "error": str(error)}
    devices = []
    for line in text.splitlines():
        match = _DEVICE.match(line)
        if match:
            devices.append({
                "index": int(match.group(1)),
                "label": match.group(2).strip(),
                "serial": match.group(3).strip(),
            })
    return {"available": True, "devices": devices, "error": None}
