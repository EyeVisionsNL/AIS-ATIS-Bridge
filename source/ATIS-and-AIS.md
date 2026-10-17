# ATIS and AIS
## From voice to vessel
The Bridge receives marine VHF audio, validates a 10-digit ATIS identity, and compares it with vessels in AIS-catcher’s local feed. ATIS supplies the identity; AIS supplies vessel information and position.

ATIS validation uses RAINWAT symbol checks, time diversity and ECC. A decoded number is not automatically accepted as a vessel match.

## Why a match can be missing
The Bridge requires a fresh validated ATIS record, a unique matching vessel, a valid MMSI and position, and sufficiently recent AIS data. AIS records can be up to **30 minutes old**, matching AIS-catcher’s default retention window. That allowance does not remove the ATIS freshness checks.

Ambiguous, stale or invalid records do not trigger map selection. A ship being audible does not guarantee that it also appears in the current AIS feed.

## Dutch callsign fallback
When standard matching finds no candidate, Dutch ATIS identities with MID 244, 245 or 246 can also match an exact normalized AIS callsign. The result is reported as `callsign_exact_fallback`.

Duplicate callsigns and invalid or stale data remain rejected. An ambiguous or rejected standard match is not bypassed, and foreign callsigns are not guessed.

## Open the AIS map
Click **Show on AIS map** for a fresh, uniquely matched vessel. Allow the map pop-up when prompted by your browser.

Click **Auto: off** to enable automatic following. The same named AIS-catcher window is reused for subsequent fresh matches. Turning Auto off stops following; closing the map also stops Auto.

## Viewer integration
The installer copies the optional viewer plugin when `/etc/AIS-catcher/plugins` exists. Restart the AIS-catcher viewer afterward. A selected vessel card then offers **ATIS Bridge**, opening the local Bridge page.

The defaults are `http://127.0.0.1:8119/ships.json` for the feed and `http://127.0.0.1:8119/` for the viewer. If the local viewer uses a different port or path, adjust `ais_ships_url` and `ais_viewer_url` in `/etc/ais-atis-bridge/config.json`. Both must use a localhost URL. The map link replaces localhost with the browser-facing hostname.
