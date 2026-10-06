import numpy as np

from ais_atis_bridge.smart_gain import analyze_iq, choose_gain, supported_gains


def test_smart_gain_uses_reference_when_no_clear_signal():
    gain, measurement = choose_gain([{"signal_dbfs": -70, "snr_db": 1}], [0, 4, 12.5, 25.4, 28])
    assert gain == 12.5
    assert measurement is None
    assert supported_gains([0, 12.5, 25.4, 49.6]) == [0, 12.5, 25.4]


def test_smart_gain_selects_bounded_fixed_gain_for_clear_signal():
    gain, strongest = choose_gain([{"signal_dbfs": -42, "snr_db": 12}], [0, 4, 12.5, 20, 25.4, 28])
    assert gain == 20.0
    assert strongest["snr_db"] == 12


def test_iq_analyzer_reports_finite_channel_measurement():
    rng = np.random.default_rng(3)
    count = 8192
    index = np.arange(count)
    signal = 22 * np.exp(2j * np.pi * 80 * index / count)
    noise = rng.normal(0, 4, count) + 1j * rng.normal(0, 4, count)
    iq = signal + noise + 127.5 + 127.5j
    payload = np.empty(count * 2, dtype=np.uint8)
    payload[::2] = np.clip(iq.real, 0, 255).astype(np.uint8)
    payload[1::2] = np.clip(iq.imag, 0, 255).astype(np.uint8)
    result = analyze_iq(payload.tobytes())
    assert set(result) == {"signal_dbfs", "noise_dbfs", "snr_db"}
    assert all(np.isfinite(value) for value in result.values())
