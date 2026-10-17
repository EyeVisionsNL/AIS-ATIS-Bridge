# Installation
## Before you start
You need Raspberry Pi OS 64-bit or Ubuntu, a working AIS-catcher viewer and **a second RTL-SDR** for marine voice. The documented Ubuntu targets are 24.04 and 26.04.

AIS-catcher keeps its own receiver. The Bridge uses only the voice receiver you explicitly select and reads AIS data without taking over AIS-catcher.

The default AIS feed is `http://127.0.0.1:8119/ships.json` on the same machine. Check that AIS-catcher is running first.

## Install Stable
Open a terminal on your Pi or Ubuntu machine:

```bash
git clone --branch main https://github.com/EyeVisionsNL/AIS-ATIS-Bridge.git
cd AIS-ATIS-Bridge
sudo ./install.sh
```

The installer sets up the Bridge service, RTLSDR-Airband runtime and updater. If RTLSDR-Airband is missing, it builds the pinned version. Give that step time to finish.

## Open your dashboard
Open `http://<raspberry-pi-address>:8120` in your browser. Replace the placeholder with your Pi’s address; on the Pi itself, use `http://localhost:8120`.

Select the second receiver before saving. Continue with [[First steps]] for your first listening session.

## Already installed?
Use [[Updates]] for dashboard updates or upgrading an older installation. Existing configuration is preserved by the installer.

## What this project is for
This is a listening and identification tool. As the project README states, do not use it for navigation or safety. Reception depends on your hardware, antenna and local signals.
