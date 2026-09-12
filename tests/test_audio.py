import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np

from ais_atis_bridge.audio import LiveAudio
from ais_atis_bridge.app import create_app
from ais_atis_bridge.config import validate
from ais_atis_bridge.runtime import ReceiverRuntime


def test_audio_live_cursor_multiple_listeners_and_clipping():
    audio = LiveAudio()
    samples = np.array([-2, -.5, 0, .5, 2, np.nan], dtype=np.float32)
    original = samples.copy()
    audio.publish(samples)
    cursor, initial = audio.read(None)
    assert initial == b''
    audio.publish(samples)
    seq, pcm = audio.read(cursor)
    assert seq == cursor + 1
    assert np.frombuffer(pcm, dtype='<i2').tolist() == [-32767, -16383, 0, 16383, 32767, 0]
    np.testing.assert_equal(samples, original)
    assert audio.read(cursor) == (seq, pcm)  # second browser doesn't consume first
    assert audio.read(seq)[1] == b''
    assert audio.read(seq + 100)[1] == b''  # server restart
    audio.clear()
    assert audio.read(0)[1] == b''


def test_audio_is_bounded_and_discards_stale_packets():
    audio = LiveAudio()
    with patch('ais_atis_bridge.audio.time.monotonic', return_value=100):
        for _ in range(100): audio.publish(np.ones(1600, dtype=np.float32))
        assert len(audio._chunks) == 64
        assert len(audio.read(0)[1]) == 32000
    with patch('ais_atis_bridge.audio.time.monotonic', return_value=102):
        assert audio.read(0)[1] == b''


def test_udp_receiver_audio_reaches_http_and_decoder(monkeypatch, tmp_path):
    # Exercise the real receiver UDP socket and browser endpoint with a tone
    # producer in place of SDR hardware. Decoder sees the same 16 kHz samples.
    runtime = ReceiverRuntime()
    monkeypatch.setenv('AIS_ATIS_CONFIG', str(tmp_path / 'config.json'))
    monkeypatch.setattr('ais_atis_bridge.app.runtime', runtime)
    real_popen = subprocess.Popen
    producer = """
import socket,time,math,struct
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
pcm=struct.pack('<1600f',*[.25*math.sin(2*math.pi*1000*i/16000) for i in range(1600)])
for _ in range(40):
 s.sendto(pcm,('127.0.0.1',49555));time.sleep(.03)
"""
    launched = []
    def launch(*args, **kwargs):
        launched.append(args[0])
        return real_popen([sys.executable, '-c', producer], **kwargs)
    client = create_app().test_client()
    cursor = client.get('/api/audio.pcm').headers['X-Audio-Sequence']
    try:
        with patch('ais_atis_bridge.runtime.subprocess.Popen', side_effect=launch), patch('ais_atis_bridge.runtime.decode_samples', return_value=[]) as decoder:
            runtime.start(validate({'receiver': 'TEST'}))
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if runtime.status()['packets_received'] >= 12: break
                time.sleep(.03)
            assert decoder.called, runtime.status()
            assert launched and launched[0][:2] == ['rtl_airband', '-F']
            response = client.get('/api/audio.pcm?after=' + cursor)
            assert response.status_code == 200
            assert response.headers['X-Audio-Rate'] == '16000'
            assert response.headers['Cache-Control'] == 'no-store'
            pcm = np.frombuffer(response.data, dtype='<i2') / 32768
            assert .15 < np.sqrt(np.mean(pcm**2)) < .20
            decoded_input = decoder.call_args.args[0]
            assert len(decoded_input) == 16000
            assert .24 < np.max(decoded_input) < .26
            assert client.get('/api/audio.pcm?after=bad').status_code == 400
            assert client.get('/api/audio.pcm?after=-1').status_code == 400
    finally:
        runtime.stop()
    assert client.get('/api/audio.pcm?after=0').data == b''
