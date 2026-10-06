#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo "Run with sudo: sudo ./uninstall.sh" >&2; exit 1; fi
systemctl disable --now ais-atis-bridge.service 2>/dev/null || true
rm -f /etc/systemd/system/ais-atis-bridge.service /etc/AIS-catcher/plugins/ais_atis_bridge.pjs
rm -f /etc/udev/rules.d/70-ais-atis-bridge.rules
rm -f /usr/local/sbin/ais-atis-update /etc/sudoers.d/ais-atis-bridge-update
udevadm control --reload-rules
systemctl daemon-reload
rm -rf /opt/ais-atis-bridge
echo "Removed program and updater files. Configuration remains in /etc/ais-atis-bridge; update backups remain in /var/backups/ais-atis-bridge."
