// Keep one AIS-catcher map window for manual selection and automatic ATIS follow.
(() => {
  const show = document.getElementById('show-map');
  const auto = document.getElementById('auto-map');
  const message = document.getElementById('map-message');
  let mapWindow = null, enabled = false, current = null, viewer = null, lastMmsi = '';
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
    url.searchParams.set('zoom', '14');
    return url.href;
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
  show.addEventListener('click', () => { if (current) openMap(); });
  auto.addEventListener('click', () => {
    if (enabled) { setEnabled(false, 'Automatic map following stopped.'); return; }
    if (openMap()) setEnabled(true, current ? 'Following MMSI ' + current.mmsi : 'Waiting for a fresh ATIS/AIS match.');
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
      if (!mapWindow || mapWindow.closed) { setEnabled(false, 'Map window closed. Auto stopped.'); return; }
      if (!current) { message.textContent = 'Waiting for a fresh ATIS/AIS match.'; return; }
      if (current.mmsi === lastMmsi) return;
      try {
        mapWindow.location.href = mapUrl();
        lastMmsi = current.mmsi;
        message.textContent = 'Following MMSI ' + current.mmsi;
      } catch (_) { setEnabled(false, 'Cannot update the map. Click Auto to reopen it.'); }
    },
    offline() {
      current = null; show.disabled = true;
      if (enabled) message.textContent = 'Bridge offline; waiting for fresh data.';
    }
  };
})();
