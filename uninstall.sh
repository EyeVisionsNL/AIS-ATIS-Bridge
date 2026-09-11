#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo "Run with sudo: sudo ./uninstall.sh" >&2; exit 1; fi
systemctl disable --now ais-atis-bridge.service 2>/dev/null || true
rm -f /etc/systemd/system/ais-atis-bridge.service /etc/AIS-catcher/plugins/ais_atis_bridge.pjs
systemctl daemon-reload
rm -rf /opt/ais-atis-bridge
echo "Removed program files. Configuration remains in /etc/ais-atis-bridge."
