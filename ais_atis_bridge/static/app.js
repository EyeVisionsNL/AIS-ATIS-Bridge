const $ = id => document.getElementById(id);
let loaded = false;
let channelConfig = [];
let recordingsSignature = '';
let updateState = null;
let updateRequestError = '';
let updateRequestPending = false;
let lastMatch = null;
let shipPhotosEnabled = localStorage.getItem('aisAtisBridge.shipPhotos') === '1';
let vesselPhotoMmsi = '';
let vesselPhotoRequest = 0;

async function json(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(data?.error || response.statusText);
  return data;
}

async function receivers(selected) {
  const data = await json('/api/receivers');
  $('receiver').innerHTML = '<option value="">Select receiver</option>' + data.devices
    .map(d => `<option value="${d.serial}" ${d.serial === selected ? 'selected' : ''}>${d.index}: ${d.label} · ${d.serial}</option>`)
    .join('');
}

function renderChannels(settings) {
  channelConfig = settings.channels;
  $('selected_channel').innerHTML = channelConfig
    .map(c => `<option value="${c.id}" ${c.id === settings.selected_channel_id ? 'selected' : ''}>${c.label} · ${c.frequency_mhz.toFixed(6)}</option>`)
    .join('');
  $('channels').innerHTML = channelConfig
    .map(c => `<label><input type="checkbox" data-channel="${c.id}" ${c.scan_enabled ? 'checked' : ''}><span>${c.label}</span><small>${c.frequency_mhz.toFixed(6)}</small></label>`)
    .join('');
}

function details(latest, match) {
  const rows = [];
  if (latest) rows.push(['ATIS code', latest.atis_code], ['Callsign', latest.callsign || '—'], ['Age', `${latest.age_seconds}s`]);
  if (match) rows.push(['AIS status', match.status], ['Ship', match.shipname || '—'], ['MMSI', match.mmsi || '—'], ['Position', match.latitude != null ? `${match.latitude}, ${match.longitude}` : '—']);
  return rows.map(([a, b]) => `<dt>${a}</dt><dd>${b}</dd>`).join('');
}


function updateGoogleImagesLink(match) {
  const link = $('google-images'), mmsi = String(match?.mmsi || '');
  if (!match?.matched || !/^\d{9}$/.test(mmsi)) { link.hidden = true; link.removeAttribute('href'); return; }
  const parts = [match.shipname, match.imo ? ('IMO ' + match.imo) : '', 'MMSI ' + mmsi, 'ship'].filter(Boolean);
  link.href = 'https://www.google.com/search?tbm=isch&q=' + encodeURIComponent(parts.join(' '));
  link.hidden = false;
}

function renderPhotoToggle() {
  $('ship-photos').textContent = shipPhotosEnabled ? 'Ship photos: on' : 'Ship photos: off';
  $('ship-photos').setAttribute('aria-pressed', String(shipPhotosEnabled));
}
function clearVesselPhoto() {
  vesselPhotoRequest += 1; vesselPhotoMmsi = '';
  $('vessel-photo-card').hidden = true; $('vessel-photo').removeAttribute('src');
  $('vessel-photo-source-link').removeAttribute('href');
}
async function renderVesselPhoto(match) {
  if (!shipPhotosEnabled) return;
  const mmsi = String(match?.mmsi || '');
  if (!match?.matched || !/^\d{9}$/.test(mmsi)) { clearVesselPhoto(); return; }
  if (mmsi === vesselPhotoMmsi) return;
  vesselPhotoMmsi = mmsi; const requestId = ++vesselPhotoRequest;
  const name = String(match.shipname || match.callsign || ('MMSI ' + mmsi));
  $('vessel-photo-card').hidden = false; $('vessel-photo').removeAttribute('src');
  $('vessel-photo-source-link').removeAttribute('href');
  $('vessel-photo-name').textContent = name; $('vessel-photo-status').textContent = 'Searching vessel photo…';
  try {
    const result = await json('/api/vessel-photo?mmsi=' + encodeURIComponent(mmsi)
      + '&shipname=' + encodeURIComponent(name) + '&imo=' + encodeURIComponent(match.imo || '')
      + '&eni=' + encodeURIComponent(match.eni || ''));
    if (requestId !== vesselPhotoRequest || !shipPhotosEnabled) return;
    if (!result.ok || !result.image_url) {
      $('vessel-photo').removeAttribute('src');
      $('vessel-photo-source-link').removeAttribute('href');
      $('vessel-photo-status').textContent = result.status === 'unavailable' ? 'Photo source temporarily unavailable.' : 'No vessel photo found.';
      return;
    }
    $('vessel-photo').src = result.image_url; $('vessel-photo').alt = 'Photo of ' + name;
    $('vessel-photo').style.objectFit = result.source === 'De Binnenvaart' ? 'contain' : '';
    if (result.page_url && /^(?:https:\/\/(?:(?:www\.)?binnenvaartspotter|(?:www\.)?debinnenvaart)\.nl\/|https:\/\/(?:markprummel\.nl|commons\.wikimedia\.org)\/)/.test(result.page_url)) {
      $('vessel-photo-source-link').href = result.page_url;
    }
    const credit = $('vessel-photo-status');
    credit.textContent = [result.source, result.artist, /^thumbnail met toestemming/i.test(String(result.license || '').trim()) ? '' : result.license].filter(Boolean).join(' · ') || 'Wikimedia Commons';
    if (result.page_url && /^(?:https:\/\/(?:(?:www\.)?binnenvaartspotter|(?:www\.)?debinnenvaart)\.nl\/|https:\/\/(?:markprummel\.nl|commons\.wikimedia\.org)\/)/.test(result.page_url)) {
      const original = document.createElement('a');
      original.href = result.page_url; original.target = '_blank'; original.rel = 'noopener noreferrer';
      original.textContent = 'View original ↗';
      credit.append(' · ', original);
    }
  } catch (_) {
    if (requestId === vesselPhotoRequest) $('vessel-photo-status').textContent = 'Photo lookup failed.';
  }
}

function renderState(state) {
  const badge = $('state');
  const value = String(state || 'OFFLINE').toUpperCase();
  badge.textContent = value;
  badge.dataset.state = value.toLowerCase();
}

function syncSquelch() {
  $('squelch_threshold_dbfs').disabled = $('squelch_mode').value !== 'manual';
}

function syncGain() {
  const smart = $('gain_mode').value === 'smart';
  $('gain_db').disabled = smart;
  $('gain-value-wrap').classList.toggle('smart-selected', smart);
  $('smart-gain-status').textContent = smart
    ? 'Smart Gain checks up to 12 selected channels, then holds one safe fixed gain.'
    : 'Manual gain stays fixed at the value below for the whole receiver session.';
}

function syncScanSpeed() {
  const value = Number($('scan_speed').value || 200);
  $('scan_speed_value').textContent = `${Math.round(value)} ms/ch`;
}

function renderRecordings(items) {
  const list = $('recordings');
  const signature = JSON.stringify(items.map(item => [item.id, item.complete, item.channel, item.play_url]));
  if (signature === recordingsSignature) return;
  recordingsSignature = signature;
  list.replaceChildren();
  if (!items.length) return;
  for (const item of items) {
    const row = document.createElement('article');
    row.className = 'recording-row';
    row.setAttribute('role', 'listitem');
    const copy = document.createElement('div');
    copy.className = 'recording-copy';
    const channel = document.createElement('div');
    const title = document.createElement('strong');
    const frequency = Number(item.frequency_mhz);
    title.textContent = (item.channel || 'Marine transmission') + (Number.isFinite(frequency) && frequency > 0 ? ` · ${frequency.toFixed(3)} MHz` : '');
    const detail = document.createElement('small');
    const received = new Date(item.received_at);
    const timeLabel = Number.isFinite(received.getTime()) ? received.toLocaleTimeString() : 'Time unavailable';
    detail.textContent = `${timeLabel} · ${Number(item.duration_seconds || 0).toFixed(1)} s`;
    channel.append(title, detail);
    copy.append(channel);
    row.append(copy);
    if (item.complete && item.play_url) {
      const player = document.createElement('audio');
      player.controls = true;
      player.preload = 'none';
      player.src = item.play_url;
      player.setAttribute('aria-label', `Play ${title.textContent}`);
      row.append(player);
      const save = document.createElement('button');
      save.type = 'button'; save.className = 'button secondary recording-save'; save.textContent = '💾 Save';
      save.addEventListener('click', async () => {
        save.disabled = true;
        try {
          const match = lastMatch?.matched ? lastMatch : {};
          const result = await json('/api/recordings/' + encodeURIComponent(item.id) + '/save', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({mmsi: match.mmsi || null, shipname: match.shipname || null, callsign: match.callsign || null, imo: match.imo || null}),
          });
          save.textContent = '✓ Saved'; $('recordings-message').textContent = 'Saved permanently as ' + result.filename;
        } catch (error) { save.disabled = false; $('recordings-message').textContent = error.message; }
      });
      row.append(save);
    } else {
      const pending = document.createElement('span');
      pending.className = 'recording-pending';
      pending.textContent = 'Recording transmission…';
      row.append(pending);
    }
    list.append(row);
  }
}

function renderUpdate(data) {
  updateState = data;
  const beta = data.source_channel === 'develop';
  const worker = data.worker || {};
  const busy = updateRequestPending || ['queued', 'starting', 'downloading', 'validating', 'backing_up', 'installing', 'restarting'].includes(worker.state);
  $('beta-toggle').checked = beta;
  $('beta-toggle').disabled = busy;
  $('check-update').disabled = busy;
  $('channel-label').textContent = beta ? 'Beta' : 'Stable';
  $('channel-description').textContent = beta ? 'Early features from develop' : 'Recommended release from main';
  $('update-versions').textContent = `Installed ${data.installed_version || '—'} · ${data.installed_channel === 'develop' ? 'Beta' : 'Stable'}${data.latest_version ? ` · ${beta ? 'Beta' : 'Stable'} ${data.latest_version}` : ''}`;
  $('install-update').disabled = busy || !data.update_available;
  if (updateRequestError) $('update-message').textContent = updateRequestError;
  else if (busy) $('update-message').textContent = worker.message || 'Installing update…';
  else if ((worker.state === 'failed' || worker.state === 'interrupted') && worker.branch === data.source_channel) $('update-message').textContent = worker.message || 'The last update did not complete.';
  else if (worker.state === 'complete' && worker.branch === data.source_channel && data.source_channel === data.installed_channel) $('update-message').textContent = `Updated to ${worker.installed_version || data.installed_version} on ${beta ? 'Beta' : 'Stable'}.`;
  else if (data.check_error) $('update-message').textContent = `Could not check for updates: ${data.check_error}`;
  else if (data.update_available) $('update-message').textContent = data.channel_change_pending
    ? `Switching to ${beta ? 'Beta' : 'Stable'} will install version ${data.latest_version}.`
    : `Version ${data.latest_version} is ready on ${beta ? 'Beta' : 'Stable'}.`;
  else if (data.local_ahead) $('update-message').textContent = `Installed version ${data.installed_version} is newer than ${beta ? 'Beta' : 'Stable'} ${data.latest_version || 'release'}.`;
  else if (data.latest_version) $('update-message').textContent = data.channel_change_pending ? 'Channel changed. The same version can be installed from the selected channel.' : 'Bridge is up to date.';
  else $('update-message').textContent = 'Check for an update to see the latest Stable or Beta version.';
}

async function checkForUpdates() {
  updateRequestError = '';
  updateRequestPending = true;
  $('check-update').disabled = true;
  $('update-message').textContent = 'Checking GitHub for the selected release channel…';
  try { renderUpdate(await json('/api/update/status?refresh=1')); }
  catch (error) { updateRequestError = error.message; $('update-message').textContent = updateRequestError; }
  finally { updateRequestPending = false; if (updateState) renderUpdate(updateState); }
}

async function pollUpdate() {
  for (let attempt = 0; attempt < 40; attempt++) {
    await new Promise(resolve => setTimeout(resolve, 2500));
    try {
      const data = await json('/api/update/status');
      renderUpdate(data);
      if (!['queued', 'starting', 'downloading', 'validating', 'backing_up', 'installing', 'restarting'].includes(data.worker?.state)) return;
    } catch (_) { $('update-message').textContent = 'Bridge is restarting after the update…'; }
  }
}

async function refresh() {
  try {
    const data = await json('/api/status');
    const state = data.receiver;
    window.atisMap.update(data);
    lastMatch = data.ais_match || null;
    updateGoogleImagesLink(lastMatch);
    renderVesselPhoto(lastMatch);
    renderState(state.state);
    $('identity').textContent = state.latest?.atis_code || 'No validated ATIS received';
    $('details').innerHTML = details(state.latest, data.ais_match);
    if (!loaded) {
      await receivers(data.settings.receiver);
      $('tuning_mode').value = data.settings.tuning_mode;
      $('gain_mode').value = data.settings.gain_mode;
      $('gain_db').value = data.settings.gain_db;
      $('squelch_mode').value = data.settings.squelch_mode;
      $('squelch_threshold_dbfs').value = data.settings.squelch_threshold_dbfs;
      $('scan_speed').value = String(data.settings.scan_interval_ms ?? 200);
      syncSquelch();
      syncGain();
      syncScanSpeed();
      renderChannels(data.settings);
      loaded = true;
    }
    renderRecordings(state.recordings || []);
    if (data.update) renderUpdate(data.update);
    const gain = state.smart_gain || {};
    if (gain.state === 'READY') $('smart-gain-status').textContent = `Smart Gain selected ${Number(gain.gain_db).toFixed(1)} dB from ${gain.probed_channels} probed channels.`;
    else if (gain.state === 'FALLBACK') $('smart-gain-status').textContent = `Smart Gain used the safe ${Number(gain.gain_db).toFixed(1)} dB reference: ${gain.error || 'probe unavailable'}`;
    else if (gain.state === 'MANUAL') $('smart-gain-status').textContent = `Manual gain fixed at ${Number(gain.gain_db).toFixed(1)} dB.`;
    if (state.error) $('message').textContent = state.error;
  } catch (error) {
    renderState('OFFLINE');
    window.atisMap.offline();
  }
}

renderPhotoToggle();
$('ship-photos').addEventListener('click', () => {
  shipPhotosEnabled = !shipPhotosEnabled;
  localStorage.setItem('aisAtisBridge.shipPhotos', shipPhotosEnabled ? '1' : '0');
  renderPhotoToggle();
  if (!shipPhotosEnabled) clearVesselPhoto(); else renderVesselPhoto(lastMatch);
});

$('settings').addEventListener('submit', async event => {
  event.preventDefault();
  $('message').textContent = 'Saving…';
  try {
    const channels = channelConfig.map(c => ({
      ...c,
      scan_enabled: document.querySelector(`[data-channel="${c.id}"]`).checked,
    }));
    await json('/api/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        receiver: $('receiver').value,
        tuning_mode: $('tuning_mode').value,
        selected_channel_id: $('selected_channel').value,
        channels,
        gain_mode: $('gain_mode').value,
        gain_db: Number($('gain_db').value),
        squelch_mode: $('squelch_mode').value,
        squelch_threshold_dbfs: Number($('squelch_threshold_dbfs').value),
        scan_interval_ms: Number($('scan_speed').value),
        ppm: 0,
      }),
    });
    $('message').textContent = 'Receiver started';
  } catch (error) {
    $('message').textContent = error.message;
  }
});

$('stop').addEventListener('click', async () => {
  await json('/api/receiver/stop', {method: 'POST'});
  $('message').textContent = 'Receiver stopped';
});

$('xlsx').addEventListener('change', async event => {
  if (!event.target.files[0]) return;
  const body = new FormData();
  body.append('file', event.target.files[0]);
  try {
    await json('/api/channels/import.xlsx', {method: 'POST', body});
    loaded = false;
    await refresh();
    $('message').textContent = 'Excel channel list imported';
  } catch (error) {
    $('message').textContent = error.message;
  }
  event.target.value = '';
});

$('squelch_mode').addEventListener('change', syncSquelch);
$('gain_mode').addEventListener('change', syncGain);
$('scan_speed').addEventListener('input', syncScanSpeed);
$('check-update').addEventListener('click', checkForUpdates);
$('beta-toggle').addEventListener('change', async () => {
  updateRequestError = '';
  updateRequestPending = true;
  $('update-message').textContent = 'Saving channel and checking GitHub…';
  try {
    renderUpdate(await json('/api/update/channel', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({channel: $('beta-toggle').checked ? 'develop' : 'main'}),
    }));
  } catch (error) { updateRequestError = error.message; $('update-message').textContent = updateRequestError; }
  finally { updateRequestPending = false; if (updateState) renderUpdate(updateState); }
});
$('install-update').addEventListener('click', async () => {
  if (!updateState?.update_available || updateRequestPending) return;
  const channel = updateState.source_channel === 'develop' ? 'Beta' : 'Stable';
  if (!window.confirm(`Install ${channel} ${updateState.latest_version}? The Bridge service will restart. Your receiver and channel settings will be kept.`)) return;
  updateRequestError = '';
  updateRequestPending = true;
  $('install-update').disabled = true;
  $('update-message').textContent = 'Starting the verified update worker…';
  try {
    const result = await json('/api/update/install', {method: 'POST'});
    $('update-message').textContent = result.message || 'Update worker started.';
    pollUpdate();
  } catch (error) { updateRequestError = error.message; $('update-message').textContent = updateRequestError; }
  finally { updateRequestPending = false; if (updateState) renderUpdate(updateState); }
});
refresh();
setInterval(refresh, 2000);
