# Troubleshooting
## Dashboard will not open
Check that you are using the Pi’s address and port **8120**, and that your browser can reach that machine. On the Pi, inspect the service:

```bash
systemctl status ais-atis-bridge --no-pager
journalctl -u ais-atis-bridge -n 100 --no-pager
```

The logs are useful when reporting a startup or receiver problem.

## Receiver missing or stopped
Confirm that a second dongle is connected and selected. Do not select the receiver already used by AIS-catcher. Check the service log for USB access or RTLSDR-Airband errors.

Older releases had a receiver lifecycle problem corrected in 0.1.5. Upgrade an old installation before chasing that symptom further.

## Scanner sticks on a channel
A manual squelch threshold below the noise floor can hold the scanner open. Try **Automatic (noise tracking)** or raise the manual threshold, then save and start again.

## Speech, but no vessel match
Speech alone does not guarantee valid ATIS. Check whether an identity was validated, whether AIS-catcher’s local `ships.json` is available, and whether the candidate vessel has fresh, valid and unique AIS data. See [[ATIS and AIS]].

## Map does not open
Allow the browser’s pop-up for the dashboard. Map controls require a fresh unique match. Confirm the viewer URL if you changed AIS-catcher’s port or path.

## Recordings disappeared
The four recent recordings are held in memory and are cleared on a Bridge restart. This is expected. See [[Audio and recordings]].

## Installer or update failed
Use [[Updates]] for the older updater repair and terminal upgrade. From a Stable source checkout, retry with:

```bash
cd ~/AIS-ATIS-Bridge
git pull --ff-only origin main
sudo ./install.sh
```

Preserve local tracked-file edits first. The installer does not install or restart AIS-catcher itself.

## Ask for help
[Open an issue on GitHub](https://github.com/EyeVisionsNL/AIS-ATIS-Bridge/issues) with your Bridge version, operating system, receiver model, selected mode, exact error and relevant service logs. Remove private details before posting.
