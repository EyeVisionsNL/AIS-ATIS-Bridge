# AIS-ATIS Bridge

Standalone Marine ATIS decoder and AIS-catcher companion for a second RTL-SDR.

The first RTL-SDR remains exclusively owned by AIS-catcher. AIS-ATIS Bridge lets
you select another RTL-SDR, receive one marine VHF channel, validate the
10-digit ATIS identity and correlate it with fresh vessels from AIS-catcher's
local `ships.json` endpoint.

> Initial hardware-validation release. Do not use for navigation or safety.

## First release scope

- Raspberry Pi OS 64-bit and Ubuntu 24.04/26.04
- RTL-SDR inventory and explicit second-receiver selection
- fixed-channel and multi-channel NFM scanning through RTLSDR-Airband
- selectable marine channel list with Excel import and export
- RAINWAT ATIS validation (10-unit symbols, time diversity and ECC)
- exact, fail-closed ATIS-to-AIS matching
- simple local web page and JSON API
- optional AIS-catcher target-card link plugin
- systemd service and uninstall script

RTLSDR-Airband is built from pinned commit
`61c5c4061967752da6b491a924664d72184b38fa` when it is not already installed.

## Requirements

- a running AIS-catcher viewer exposing `http://127.0.0.1:8119/ships.json`
- a second RTL-SDR that is not used by AIS-catcher
- Debian/Raspberry Pi OS 64-bit or Ubuntu

## Install

```bash
git clone https://github.com/EyeVisionsNL/AIS-ATIS-Bridge.git
cd AIS-ATIS-Bridge
sudo ./install.sh
```

Open `http://<raspberry-pi-address>:8120`, select the second receiver and save.

## AIS-catcher viewer plugin

The installer copies `plugins/ais_atis_bridge.pjs` to the managed AIS-catcher
plugin directory when `/etc/AIS-catcher/plugins` exists. Restart the
AIS-catcher viewer after installation. The plugin adds an **ATIS Bridge** item
to the selected vessel card and opens the local page with the MMSI selected.

## Architecture

AIS-catcher and AIS-ATIS Bridge never share receiver ownership. RTLSDR-Airband owns
only the selected voice receiver. The bridge reads AIS-catcher data read-only.
Configuration changes are rejected if no explicit receiver is selected.

## Development

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest
```

## License

GPL-3.0. The ATIS decoder is derived from the validated decoder in FlexGround
SDR, also maintained by EyeVisionsNL.
