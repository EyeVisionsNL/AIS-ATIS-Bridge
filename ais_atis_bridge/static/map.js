// Keep one AIS-catcher map window for manual selection and automatic ATIS follow.
(() => {
  const show = document.getElementById('show-map');
  const auto = document.getElementById('auto-map');
  const message = document.getElementById('map-message');
  const zoomInput = document.getElementById('map-zoom');
  const zoomStorageKey = 'aisAtisBridge.mapZoom';
  let mapWindow = null, enabled = false, current = null, viewer = null, lastMmsi = '', zoom = 14;

  try {
    const saved = Number(window.localStorage?.getItem(zoomStorageKey));
    if (Number.isInteger(saved) && saved >= 3 && saved <= 18) zoom = saved;
  } catch (_) { /* Browser storage is optional. */ }
  if (zoomInput) zoomInput.value = String(zoom);

  function setEnabled(value, text) {
    enabled = value;
    auto.textContent = value ? 'Auto: on' : 'Auto: off';
    auto.setAttribute('aria-pressed', String(value));
    if (text) message.textContent = text;
  }

  function mapUrl() {
    const url = new URL(viewer);
    // The service reads localhost; the browser connects to the receiver host.
    if (url.hostname === 'localhost' || url.hostname === '127.0.0.1') url.hostname = window.location.hostname;
    if (current) url.searchParams.set('mmsi', current.mmsi);
    url.searchParams.set('zoom', String(zoom));
    return url.href;
  }

  function navigateMap() {
    if (!mapWindow || mapWindow.closed || !viewer) return false;
    try {
      mapWindow.location.href = mapUrl();
      lastMmsi = current?.mmsi || '';
      return true;
    } catch (_) {
      return false;
    }
  }

  function openMap() {
    if (!viewer) return false;
    mapWindow = window.open(mapUrl(), 'ais-atis-bridge-map');
    if (!mapWindow) {
      setEnabled(false, 'Allow pop-ups for this page to open the AIS map.');
      return false;
    }
    lastMmsi = current?.mmsi || '';
    mapWindow.focus();
    return true;
  }

  if (zoomInput) {
    zoomInput.addEventListener('change', () => {
      const value = Number(zoomInput.value);
      if (!Number.isInteger(value) || value < 3 || value > 18) {
        zoomInput.value = String(zoom);
        message.textContent = 'Enter a zoom level from 3 to 18.';
        return;
      }
      zoom = value;
      try { window.localStorage?.setItem(zoomStorageKey, String(zoom)); } catch (_) {}
      if (enabled) {
        if (!navigateMap()) {
          setEnabled(false, 'Map window closed. Auto stopped.');
          return;
        }
        message.textContent = current ? `Following MMSI ${current.mmsi} · zoom ${zoom}` : `Auto zoom set to ${zoom}. Waiting for a fresh ATIS/AIS match.`;
      }
    });
  }

  show.addEventListener('click', () => { if (current) openMap(); });
  auto.addEventListener('click', () => {
    if (enabled) {
      setEnabled(false, 'Automatic map following stopped.');
      return;
    }
    if (openMap()) setEnabled(true, current ? `Following MMSI ${current.mmsi} · zoom ${zoom}` : 'Waiting for a fresh ATIS/AIS match.');
  });

  window.atisMap = {
    update(data) {
      viewer = data.settings.ais_viewer_url;
      auto.disabled = false;
      const latest = data.receiver.latest;
      const match = data.ais_match;
      current = latest?.fresh && match?.matched && /^\d{9}$/.test(String(match.mmsi))
        ? {mmsi: String(match.mmsi)} : null;
      show.disabled = !current;
      if (!enabled) return;
      if (!mapWindow || mapWindow.closed) {
        setEnabled(false, 'Map window closed. Auto stopped.');
        return;
      }
      if (!current) {
        message.textContent = 'Waiting for a fresh ATIS/AIS match.';
        return;
      }
      if (current.mmsi === lastMmsi) return;
      if (navigateMap()) {
        message.textContent = `Following MMSI ${current.mmsi} · zoom ${zoom}`;
      } else {
        setEnabled(false, 'Cannot update the map. Click Auto to reopen it.');
      }
    },
    offline() {
      current = null;
      show.disabled = true;
      if (enabled) message.textContent = 'Bridge offline; waiting for fresh data.';
    },
  };
})();
