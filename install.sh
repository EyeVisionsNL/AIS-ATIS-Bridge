#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then echo "Run with sudo: sudo ./install.sh" >&2; exit 1; fi
SOURCE_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
apt-get update
apt-get install -y python3 python3-venv rtl-sdr
"$SOURCE_DIR/scripts/install_rtlsdr_airband.sh"
id aisatis >/dev/null 2>&1 || useradd --system --home /nonexistent --shell /usr/sbin/nologin aisatis
install -d -m 0755 /opt/ais-atis-bridge /etc/ais-atis-bridge
cp -a "$SOURCE_DIR"/. /opt/ais-atis-bridge/
python3 -m venv /opt/ais-atis-bridge/venv
/opt/ais-atis-bridge/venv/bin/pip install --disable-pip-version-check /opt/ais-atis-bridge
if [[ ! -f /etc/ais-atis-bridge/config.json ]]; then
  AIS_ATIS_CONFIG=/etc/ais-atis-bridge/config.json /opt/ais-atis-bridge/venv/bin/python -c 'from ais_atis_bridge.config import DEFAULTS, save; save(DEFAULTS)'
  chown aisatis:aisatis /etc/ais-atis-bridge/config.json
fi
install -m 0644 /opt/ais-atis-bridge/systemd/ais-atis-bridge.service /etc/systemd/system/ais-atis-bridge.service
if [[ -d /etc/AIS-catcher/plugins ]]; then install -m 0644 /opt/ais-atis-bridge/plugins/ais_atis_bridge.pjs /etc/AIS-catcher/plugins/ais_atis_bridge.pjs; fi
systemctl daemon-reload
systemctl enable --now ais-atis-bridge.service
echo "Open http://$(hostname -I | awk '{print $1}'):8120"
