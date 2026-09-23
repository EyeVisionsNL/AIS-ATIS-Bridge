# AIS-ATIS Bridge

Standalone Marine ATIS decoder and AIS-catcher companion for a second RTL-SDR.

The first RTL-SDR remains exclusively owned by AIS-catcher. AIS-ATIS Bridge lets
you select another RTL-SDR, receive selected marine VHF channels, validate the
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
to the selected vessel card and opens the local Bridge page.

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

### Squelch and map follow

The receiver panel offers automatic noise-tracking squelch (the existing 4 dB SNR setting) or a manual integer threshold from -100 to -1 dBFS. Manual defaults to -47 dBFS; tune it for your antenna and gain. Settings apply to both fixed and scan mode. A threshold below the noise floor can hold the scanner on a channel.

Click **Show on AIS map** for a fresh, uniquely matched vessel, or **Auto: off** to enable automatic following. Allow the map pop-up once. The same named AIS-catcher window is reused for subsequent fresh ATIS/AIS matches; turning Auto off stops following, and closing the map stops Auto. No map selection is made for stale, ambiguous or missing matches. Set `ais_viewer_url` in the service configuration if the viewer uses a different port or path; localhost is replaced with the browser-facing hostname. The plugin still opens the Bridge from a vessel card.

The interface uses the FlexGround SDR / SDRCC dark blue theme. Real SDR reception and the installed AIS-catcher viewer still require an installation/hardware test.

### Listen to marine voice

Select the second SDR, select scan channels or a fixed channel, and click **Save and start**. Then click **Audio: off** to enable listening. Audio plays through the browser device speakers/headphones, not the Raspberry Pi audio output. Adjust **Volume**; 0% mutes playback. Audio is off on page load and requires a click.

The browser receives live mono 16 kHz audio from the same receiver feed used for ATIS decoding. Receiver squelch applies to both. Turning listening off or changing volume does not stop decoding, scanning, or AIS Auto. Brief network interruptions reconnect automatically, without replaying a recording. The live buffer is bounded to one second of returned audio, with no audio files recorded. Browser background suspension can require another click on Audio.

Validation includes a synthetic UDP tone through the receiver, HTTP PCM endpoint and decoder input, plus JavaScript playback/volume/stop tests. Audible reception from a real dongle still needs the Raspberry Pi test.

## AIS retention window (0.1.8)

AIS matches now accept records up to 1800 seconds (30 minutes) old, matching
AIS-catcher's default retention window. Older records remain rejected. This
changes the allowed AIS age only; the received ATIS must still be fresh and
the vessel identity and position must pass the existing checks.

## ATIS callsign fallback (0.1.7)

When standard ATIS matching finds no candidate, Dutch ATIS identities (MID
244, 245 or 246) also match the exact normalized call sign in the AIS feed.
This supports PD4821 / BARENDSZ with Belgian MMSI 205595190. The match reports
`callsign_exact_fallback`; duplicate call signs, invalid MMSI/positions and
unvalidated or stale records remain rejected. The Bridge uses a 30-minute AIS freshness limit, matching the default
AIS-catcher retention window. Foreign call signs are not guessed, and a
rejected or ambiguous standard match is never bypassed.

Update an existing installation with `git pull --ff-only origin main` followed
by `sudo ./install.sh` from its checkout. Live reception needs Marcel's test;
the regression fixture uses the captured AIS data and a reconstructed ATIS code.

## Receiver lifecycle fix (0.1.5)

The Bridge runs RTLSDR-Airband with `-F`, keeping it in the foreground without the textual waterfall. This lets the Bridge correctly monitor, stop and restart the receiver instead of reporting `STOPPED` after RTLSDR-Airband daemonizes.

## Installer verification (0.1.4)

The installer now includes the required LAME/libshout development libraries, grants the service access via plugdev and common RTL2832U udev rules, fixes config-directory ownership, preserves existing settings, excludes checkout/build caches, restarts the installed service and checks its version through HTTP. The Airband build uses two jobs and explicitly enables RTL-SDR/NFM while disabling unused optional backends. Existing rtl_airband installations are reused.

Validation: run `python scripts/validate_install_workflow.py` in a disposable root test environment. It executes first install, reinstall and installation from the installed directory with real wheel installation, configuration and dashboard startup. apt, CMake/git, users/ownership, udev and systemd are simulated; this is not a clean Raspberry Pi OS or native C++ build test. Native package installation is blocked in the development environment. The full Raspberry Pi OS 64-bit installation, USB access and reception remain hardware validation steps.

To retry after a failed installation:

```bash
cd ~/AIS-ATIS-Bridge
git pull --ff-only origin main
sudo ./install.sh
```

If you edited tracked installer files locally, preserve those changes before pulling. The installer does not install or restart AIS-catcher itself.
