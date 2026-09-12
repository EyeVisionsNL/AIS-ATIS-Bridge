#!/usr/bin/env bash
set -euo pipefail
trap 'echo "Installation failed at line $LINENO. Fix the reported error and rerun sudo ./install.sh." >&2' ERR
if [[ ${EUID} -ne 0 ]]; then echo "Run with sudo: sudo ./install.sh" >&2; exit 1; fi
SOURCE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else "Python 3.11 or newer is required")'
command -v systemctl >/dev/null || { echo "A systemd-based installation is required." >&2; exit 1; }
apt-get update
apt-get install -y python3 python3-venv rtl-sdr ca-certificates tar udev util-linux passwd
bash "$SOURCE_DIR/scripts/install_rtlsdr_airband.sh"
getent group aisatis >/dev/null || groupadd --system aisatis
id aisatis >/dev/null 2>&1 || useradd --system --gid aisatis --home /nonexistent --shell /usr/sbin/nologin aisatis
getent group plugdev >/dev/null || groupadd --system plugdev
usermod -a -G plugdev aisatis
install -d -m 0755 /opt/ais-atis-bridge
# Atomic config replacement needs write permission on the directory, not just the file.
install -d -o aisatis -g aisatis -m 0750 /etc/ais-atis-bridge
if systemctl is-active --quiet ais-atis-bridge.service; then
  systemctl stop ais-atis-bridge.service
fi
if [[ "$SOURCE_DIR" != /opt/ais-atis-bridge ]]; then
  # Copy only runtime/install sources. Never copy a checkout's venv or build cache.
  tar -C "$SOURCE_DIR" --exclude=__pycache__ --exclude='*.pyc' -cf - \
    pyproject.toml VERSION README.md LICENSE install.sh uninstall.sh ais_atis_bridge scripts plugins systemd \
    | tar -C /opt/ais-atis-bridge -xf -
fi
python3 -m venv /opt/ais-atis-bridge/venv
/opt/ais-atis-bridge/venv/bin/pip install --disable-pip-version-check /opt/ais-atis-bridge
if [[ ! -f /etc/ais-atis-bridge/config.json ]]; then
  AIS_ATIS_CONFIG=/etc/ais-atis-bridge/config.json /opt/ais-atis-bridge/venv/bin/python -c 'from ais_atis_bridge.config import DEFAULTS, save; save(DEFAULTS)'
fi
chown aisatis:aisatis /etc/ais-atis-bridge/config.json
chmod 0640 /etc/ais-atis-bridge/config.json
# Verify saving as the actual service user before starting it; preserve existing settings.
runuser -u aisatis -- env AIS_ATIS_CONFIG=/etc/ais-atis-bridge/config.json \
  /opt/ais-atis-bridge/venv/bin/python -c 'from ais_atis_bridge.config import load, save; save(load())'
install -d -m 0755 /etc/udev/rules.d
install -m 0644 "$SOURCE_DIR/systemd/70-ais-atis-bridge.rules" /etc/udev/rules.d/70-ais-atis-bridge.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=usb --action=change
install -m 0644 /opt/ais-atis-bridge/systemd/ais-atis-bridge.service /etc/systemd/system/ais-atis-bridge.service
if [[ -d /etc/AIS-catcher/plugins ]]; then
  install -m 0644 /opt/ais-atis-bridge/plugins/ais_atis_bridge.pjs /etc/AIS-catcher/plugins/ais_atis_bridge.pjs
fi
systemctl daemon-reload
systemctl enable ais-atis-bridge.service
systemctl restart ais-atis-bridge.service
/opt/ais-atis-bridge/venv/bin/python /opt/ais-atis-bridge/scripts/check_install.py
echo "Installation complete. AIS-catcher itself has not been restarted."
