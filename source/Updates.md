# Updates
## Update from the dashboard
1. Open **Bridge updates**.
2. Choose **Stable** for `main` or **Beta** for `develop`.
3. Click **Check for updates**.
4. Review the available version and click **Install update**.
5. Let the Bridge restart, then refresh the dashboard and check its version.

The updater verifies SHA-256 hashes, backs up installed application files and runs a health check. A failed health check triggers rollback.

## Your settings stay yours
Receiver selection, mode, channels, gain, squelch and viewer settings are preserved. Configuration lives at `/etc/ais-atis-bridge/config.json`, outside the application update.

The release-channel preference is saved independently of receiver settings. An explicit switch between Stable and Beta can install the selected branch even if its version is equal or older, provided that branch has an update manifest. Older releases within the currently installed channel remain blocked.

## Upgrade an older checkout
Run the installer once to install the updater and service changes:

```bash
cd ~/AIS-ATIS-Bridge
git fetch origin
git switch main
git pull --ff-only origin main
sudo ./install.sh
```

Preserve any local edits to tracked files before switching or pulling. For Beta, use `develop` instead of `main` in both branch commands.

## “No new privileges” update error
Older service settings could block the updater helper. Run the terminal upgrade above once to repair those settings, then refresh the dashboard. The blocked updater cannot repair its own service configuration.

Future compatible releases can use the dashboard update button again.
