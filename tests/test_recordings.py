import struct

from ais_atis_bridge.recordings import RecentRecordings


def test_recent_recordings_finish_to_valid_wav_and_keep_channel_metadata():
    store = RecentRecordings(sample_rate=1000)
    pcm = struct.pack("<200h", *([1200] * 200))
    store.observe_live(pcm, 10.0)
    recording_id, started = store.observe_gated(pcm, 10.2, {"channel": "VHF61 VTS", "frequency_mhz": 160.675})
    assert started
    assert store.list()[0]["complete"] is False
    assert store.finish_if_idle(11.0)
    row = store.list()[0]
    assert row["id"] == recording_id and row["complete"] is True
    assert row["channel"] == "VHF61 VTS" and row["frequency_mhz"] == 160.675
    wav = store.get_wav(recording_id)
    assert wav is not None and wav[:4] == b"RIFF" and wav[8:12] == b"WAVE"
    assert int.from_bytes(wav[40:44], "little") == len(wav) - 44


def test_recording_store_caps_history_at_four_and_rejects_incomplete_playback():
    store = RecentRecordings(sample_rate=1000)
    pcm = b"\x01\x00" * 200
    ids = []
    for index in range(6):
        moment = float(index * 2)
        recording_id, _ = store.observe_gated(pcm, moment, {"channel": f"VHF{index}", "frequency_mhz": 156.0 + index})
        ids.append(recording_id)
        assert store.finish_if_idle(moment + 1)
    rows = store.list()
    assert len(rows) == 4
    assert [row["id"] for row in rows] == list(reversed(ids[-4:]))
    assert store.get_wav(ids[0]) is None


def test_delayed_scanner_label_updates_only_new_recording():
    store = RecentRecordings(sample_rate=1000)
    store.observe_gated(b'\x01\x00' * 200, 10.0)
    store.resolve_recent_metadata({'channel': 'VHF63', 'frequency_mhz': 160.775}, 10.2)
    assert store.list()[0]['channel'] == 'VHF63'
    store.resolve_recent_metadata({'channel': 'VHF61', 'frequency_mhz': 160.675}, 11.0)
    assert store.list()[0]['channel'] == 'VHF63'
