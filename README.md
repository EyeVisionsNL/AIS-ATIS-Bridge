# AIS-ATIS Bridge

Marine VHF voice, validated ATIS identities and AIS vessel matching for an AIS-catcher station.
AIS-ATIS Bridge uses a second RTL-SDR, so AIS-catcher keeps exclusive ownership of its own receiver.

The first RTL-SDR remains exclusively owned by AIS-catcher. AIS-ATIS Bridge lets
you select another RTL-SDR, receive selected marine VHF channels, validate the
10-digit ATIS identity and correlate it with fresh vessels from AIS-catcher's
local `ships.json` endpoint.

> For monitoring and experimentation only. Never use for navigation or safety.

## First release scope

- Raspberry Pi OS 64-bit and Ubuntu 24.04/26.04
- RTL-SDR inventory and explicit second-receiver selection
- fixed-channel and multi-channel NFM scanning through RTLSDR-Airband
- one-shot Smart Gain probe followed by a bounded, fixed tuner gain
- up to four recent squelch-open Marine recordings, held in memory
- the SDRCC-aligned Marine Voice workbook (133 unique analogue voice carriers), with Excel import and export
- RAINWAT ATIS validation (10-unit symbols, time diversity and ECC)
- exact, fail-closed ATIS-to-AIS matching
- optional, on-demand vessel thumbnails after a validated live match
- SDRCC-inspired dashboard, update channel selector and verified updater
- optional AIS-catcher target-card link plugin
- systemd service and uninstall script

RTLSDR-Airband is built from pinned commit
`61c5c4061967752da6b491a924664d72184b38fa` when it is not already installed.

## Requirements

- a running AIS-catcher viewer exposing `http://127.0.0.1:8119/ships.json`
- a second RTL-SDR that is not used by AIS-catcher
- Debian/Raspberry Pi OS 64-bit or Ubuntu

## 🚢 Marine Voice meets AIS

Select marine VHF channels, listen to live audio, decode and validate ATIS, then
compare it with current AIS-catcher vessel data. The dashboard provides recent
transmission replays, Smart Gain, the maintained Marine voice list and optional
vessel photos.

## 📷 Vessel photos

Photo lookup runs only when enabled and a validated live ATIS/AIS match is
available. Sources are checked in this order: Binnenvaartspotter, De Binnenvaart,
Mark Prummel, then Wikimedia Commons. The Google Images option opens a search
page; it does not download or reuse Google's results.

A photo must match the vessel identity through its ENI, IMO or MMSI. A ship name
alone is not enough. Photo cards retain the photographer credit and source link;
Binnenvaartspotter results are thumbnails, and original watermarks are kept.

## Marine voice catalog (0.1.13)

Version 0.1.13 aligns AIS-ATIS Bridge with SDRCC's voice-only Dutch Marine
catalog. The maintained bank contains 133 unique analogue receive carriers,
including the Dutch supplementary/private channels and both relevant sides of
duplex voice channels. VHF55L/56L are supported by widening the accepted Marine
range to 155.775–162.600 MHz.

Data-only carriers are deliberately excluded from Voice: AIS1/AIS2, VHF70 DSC,
ASM1/ASM2 and the VDES/satellite allocations on 24/25/26 and 84/85/86. AIS
continues to be handled by AIS-catcher. Existing installations migrate by
frequency, retain scan choices and custom voice channels, and remove obsolete
data-only entries.

## Update startup fix (0.1.12)

The service's `NoNewPrivileges=true` setting blocked the restricted sudo
updater helper. Version 0.1.12 allows that existing no-argument helper to run;
the Bridge still runs as `aisatis`, and the other filesystem protections remain.
Update errors now remain visible during automatic dashboard refreshes.

If the update button reports sudo's "no new privileges" flag, install this
repair once from the terminal, because the blocked updater cannot repair its
own service settings:

```bash
cd ~/AIS-ATIS-Bridge
git fetch origin
git switch develop
git pull --ff-only origin develop
sudo ./install.sh
```

Then refresh the dashboard. Subsequent compatible beta releases use the update
button again. Native service elevation still needs validation on the target Pi.

## Develop / beta 0.1.25

Beta 0.1.25 aligns the Bridge photo matching policy with SDRCC, including ENI
identity checks and stricter Binnenvaartspotter thumbnail validation. It also
updates the README and photo regression tests. Existing Smart Gain, four recent
recordings, the Marine channel list, updater and dashboard remain part of the beta.

### Upgrade an existing checkout

Run the installer once to install the new updater as well:

```bash
cd ~/AIS-ATIS-Bridge
git fetch origin
git switch develop
git pull --ff-only origin develop
sudo ./install.sh
```

Existing receiver and channel settings are preserved. Future compatible beta
updates can be installed through **Bridge updates** in the dashboard.

### Fresh beta installation

```bash
git clone --branch develop https://github.com/EyeVisionsNL/AIS-ATIS-Bridge.git
cd AIS-ATIS-Bridge
sudo ./install.sh
```

### Validation status

The 37 targeted photo policy and source tests pass without external website
requests. The existing Bridge release baseline passed 85 automated Python
tests and browser-control checks; the install and updater tests used simulated
host services. Test the update and radio reception on the target Pi before
relying on native systemd or live SDR operation.

This release is published on `develop` for beta testing. Stable `main` remains
on 0.1.13 and does not include the beta photo-matching changes.

## Install stable

```bash
git clone https://github.com/EyeVisionsNL/AIS-ATIS-Bridge.git
cd AIS-ATIS-Bridge
sudo ./install.sh
```

Open `http://<raspberry-pi-address>:8120`, select the second receiver and save.
Use **Bridge updates** to check Stable (`main`) or Beta (`develop`) and install
an available version. The updater verifies SHA-256 hashes, backs up the
installed application files, restarts the Bridge and rolls back if its health
check fails. `/etc/ais-atis-bridge/config.json` is kept outside the update.

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

GPL-3.0. The ATIS decoder is derived from the validated decoder in SDRCC, also maintained by EyeVisionsNL.

### Squelch and map follow

The receiver panel offers automatic noise-tracking squelch (the existing 4 dB SNR setting) or a manual integer threshold from -100 to -1 dBFS. Manual defaults to -47 dBFS; tune it for your antenna and gain. Settings apply to both fixed and scan mode. A threshold below the noise floor can hold the scanner on a channel.

Click **Show on AIS map** for a fresh, uniquely matched vessel, or **Auto: off** to enable automatic following. Allow the map pop-up once. The same named AIS-catcher window is reused for subsequent fresh ATIS/AIS matches; turning Auto off stops following, and closing the map stops Auto. No map selection is made for stale, ambiguous or missing matches. Set `ais_viewer_url` in the service configuration if the viewer uses a different port or path; localhost is replaced with the browser-facing hostname. The plugin still opens the Bridge from a vessel card.

The interface uses the SDRCC dark blue theme with a radar banner. Real SDR reception and the installed AIS-catcher viewer still require an installation/hardware test.

### Listen to marine voice

Select the second SDR, select scan channels or a fixed channel, and click **Save and start**. Then click **Audio: off** to enable listening. Audio plays through the browser device speakers/headphones, not the Raspberry Pi audio output. Adjust **Volume**; 0% mutes playback. Audio is off on page load and requires a click.

The browser receives live mono 16 kHz audio from the same receiver feed used
for ATIS decoding. A separate squelch-gated feed keeps up to four recent
transmissions (maximum two minutes each) in memory and offers WAV replay after
the signal ends. Recordings are discarded when the Bridge process restarts;
they are not written to disk. Turning live listening off does not stop
decoding, scanning or recording. Browser background suspension can require
another click on Audio.

### Smart Gain and Marine channel list

Smart Gain briefly probes up to twelve selected channels with the second
receiver, chooses one supported gain step between 0 and 25.4 dB and holds it
fixed while receiving. When the probe cannot run or finds no clear signal, it
uses the conservative 12.5 dB reference. Select Manual to set a different
fixed tuner gain. The Marine channel workbook is available from **Marine
channel list**; an SDRCC workbook can also be imported, with Aviation rows
ignored and Marine channels retained.

### Stable and beta updates

Stable follows `main`; Beta follows `develop`. Selecting a channel saves that
preference independently from the receiver configuration. Installing a beta
or stable update does not replace the selected RTL-SDR, scan mode, channel
selections, gain, squelch or AIS viewer settings. The updater only accepts
those two repository branches, verifies the downloaded source against the
branch's SHA-256 manifest, keeps a file backup and runs an HTTP health check
before marking a channel installed. An explicit switch between Stable and Beta
can install the selected branch even when its version is older, provided that
branch contains the new update manifest. Stable 0.1.8 predates this updater;
returning to that release requires its manual installer until main is promoted. Older releases
within the currently installed channel remain blocked.

The installer preserves the existing Bridge configuration, sets up the
RTL-SDR Airband runtime, installs the systemd service and registers the
restricted updater helper. A clean Raspberry Pi OS installation and real USB
reception still need a hardware test.

Validation includes a synthetic UDP tone through the receiver, the HTTP audio
endpoint, channel migration, Smart Gain calculations, bounded replay storage,
spreadsheet import and dashboard controls. Real RTL-SDR reception still needs
a hardware test.

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

Routine updates are available from **Bridge updates** in the dashboard. To
install the beta branch manually, check out `develop` before running
`sudo ./install.sh`; `main` remains the stable branch.

## Receiver lifecycle fix (0.1.5)

The Bridge runs RTLSDR-Airband with `-F`, keeping it in the foreground without the textual waterfall. This lets the Bridge correctly monitor, stop and restart the receiver instead of reporting `STOPPED` after RTLSDR-Airband daemonizes.

## Installer verification (0.1.4)

The installer now includes the required LAME/libshout development libraries, grants the service access via plugdev and common RTL2832U udev rules, fixes config-directory ownership, preserves existing settings, excludes checkout/build caches, restarts the installed service and checks its version through HTTP. The Airband build uses two jobs and explicitly enables RTL-SDR/NFM while disabling unused optional backends. Existing rtl_airband installations are reused.

To retry a failed installation from a source checkout:

```bash
cd ~/AIS-ATIS-Bridge
git pull --ff-only origin main
sudo ./install.sh
```

For Beta, check out `develop` and use `git pull --ff-only origin develop`.

If you edited tracked installer files locally, preserve those changes before pulling. The installer does not install or restart AIS-catcher itself.
