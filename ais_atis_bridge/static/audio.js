(() => {
  const button = document.getElementById('audio-toggle');
  const volume = document.getElementById('audio-volume');
  const output = document.getElementById('audio-volume-value');
  const status = document.getElementById('audio-message');
  let session = null;

  function stop(text = 'Audio off. ATIS decoding continues.') {
    const old = session;
    session = null;
    if (old) {
      clearTimeout(old.timer);
      old.abort?.abort();
      old.context.close().catch(() => {});
    }
    button.textContent = 'Audio: off';
    button.setAttribute('aria-pressed', 'false');
    status.textContent = text;
  }

  async function poll(active) {
    if (session !== active) return;
    const abort = new AbortController();
    active.abort = abort;
    const timeout = setTimeout(() => abort.abort(), 3000);
    try {
      const query = active.cursor === null ? '' : '?after=' + active.cursor;
      const response = await fetch('/api/audio.pcm' + query, {cache: 'no-store', signal: abort.signal});
      if (!response.ok) throw new Error('Audio unavailable');
      const bytes = await response.arrayBuffer();
      if (session !== active) return;
      const cursor = Number(response.headers.get('X-Audio-Sequence'));
      const rate = Number(response.headers.get('X-Audio-Rate'));
      if (!Number.isSafeInteger(cursor) || cursor < 0 || rate !== 16000 || bytes.byteLength % 2) throw new Error('Invalid audio');
      active.cursor = cursor;
      if (active.context.state !== 'running') {
        stop('Audio paused by the browser. Click Audio to resume.');
        return;
      }
      if (bytes.byteLength) {
        const buffer = active.context.createBuffer(1, bytes.byteLength / 2, rate);
        const samples = buffer.getChannelData(0);
        const view = new DataView(bytes);
        for (let i = 0; i < samples.length; i++) samples[i] = view.getInt16(i * 2, true) / 32768;
        // Skip queued latency instead of letting slow/background tabs accumulate it.
        if (active.next > active.context.currentTime + 0.75) {
          status.textContent = 'Listening live';
        } else {
          const source = active.context.createBufferSource();
          source.buffer = buffer;
          source.connect(active.gain);
          active.next = Math.max(active.next, active.context.currentTime + 0.10);
          source.start(active.next);
          active.next += buffer.duration;
          status.textContent = 'Listening live';
        }
      } else {
        status.textContent = response.headers.get('X-Receiver-Running') === '1'
          ? 'Listening — waiting for audio' : 'Waiting for receiver. Select SDR and Save and start.';
      }
    } catch (_) {
      if (session === active) {
        active.cursor = null;
        status.textContent = 'Audio connection lost; reconnecting…';
      }
    } finally {
      clearTimeout(timeout);
      if (session === active) active.timer = setTimeout(() => poll(active), 150);
    }
  }

  button.addEventListener('click', async () => {
    if (session) { stop(); return; }
    const Audio = window.AudioContext || window.webkitAudioContext;
    if (!Audio) { status.textContent = 'This browser does not support live audio.'; return; }
    let active = null;
    try {
      const context = new Audio();
      active = {context, gain: context.createGain(), cursor: null, next: 0, timer: null, abort: null};
      session = active;
      active.gain.gain.value = Number(volume.value) / 100;
      active.gain.connect(context.destination);
      button.textContent = 'Audio: on';
      button.setAttribute('aria-pressed', 'true');
      status.textContent = 'Connecting audio…';
      await context.resume();
      if (session === active) poll(active);
    } catch (_) {
      if (session === active) stop('Could not start audio. Click Audio to try again.');
    }
  });
  volume.addEventListener('input', () => {
    output.textContent = volume.value + '%';
    if (session) session.gain.gain.value = Number(volume.value) / 100;
  });
  window.addEventListener('pagehide', () => stop());
})();
