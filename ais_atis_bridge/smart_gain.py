"""One-shot Smart Gain probing for the selected second RTL-SDR."""

from __future__ import annotations

import ctypes
import ctypes.util
import math
from typing import Any, Iterable

import numpy as np


REFERENCE_GAIN_DB = 12.5
MIN_GAIN_DB = 0.0
MAX_GAIN_DB = 25.4
TARGET_SIGNAL_DBFS = -28.0
MIN_SIGNAL_SNR_DB = 4.0
SAMPLE_RATE_HZ = 240_000
MAX_PROBE_CHANNELS = 12
READ_BYTES = 65_536


def supported_gains(values: Iterable[float]) -> list[float]:
    valid = set()
    for value in values:
        try:
            gain = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(gain) and MIN_GAIN_DB <= gain <= MAX_GAIN_DB:
            valid.add(round(gain, 1))
    gains = sorted(valid)
    if not gains:
        raise RuntimeError("RTL-SDR has no tuner gain step in Smart Gain's safe 0–25.4 dB range")
    return gains


def analyze_iq(payload: bytes) -> dict[str, float]:
    usable = len(payload) - len(payload) % 2
    if usable < 8192:
        raise ValueError("Smart Gain received too little IQ data")
    raw = np.frombuffer(payload[:usable], dtype=np.uint8).astype(np.float64)
    iq = ((raw[::2] - 127.5) + 1j * (raw[1::2] - 127.5)) / 127.5
    iq -= np.mean(iq)
    window = np.hanning(len(iq))
    spectrum = np.fft.fftshift(np.fft.fft(iq * window))
    power = np.abs(spectrum) ** 2 / max(float(np.sum(window) ** 2), 1e-18)
    frequency = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1 / SAMPLE_RATE_HZ))
    offset = np.abs(frequency)
    channel = offset <= 10_000
    noise = (offset >= 30_000) & (offset <= 100_000)
    if np.count_nonzero(channel) < 4 or np.count_nonzero(noise) < 8:
        raise ValueError("Smart Gain could not measure channel and noise")
    signal_power = float(np.sum(power[channel]))
    noise_power = float(np.median(power[noise]) * np.count_nonzero(channel))
    signal_dbfs = 10 * math.log10(max(signal_power, 1e-18))
    noise_dbfs = 10 * math.log10(max(noise_power, 1e-18))
    return {"signal_dbfs": round(signal_dbfs, 2), "noise_dbfs": round(noise_dbfs, 2),
            "snr_db": round(signal_dbfs - noise_dbfs, 2)}


def choose_gain(measurements: list[dict[str, Any]], gains_db: Iterable[float]) -> tuple[float, dict[str, float] | None]:
    gains = supported_gains(gains_db)
    reference = min(gains, key=lambda gain: (abs(gain - REFERENCE_GAIN_DB), gain))
    clear = [row for row in measurements if float(row.get("snr_db", -999)) >= MIN_SIGNAL_SNR_DB]
    if not clear:
        return reference, None
    strongest = max(clear, key=lambda row: float(row.get("signal_dbfs", -999)))
    adjustment = max(-12.5, min(8.2, TARGET_SIGNAL_DBFS - float(strongest["signal_dbfs"])))
    target = min(MAX_GAIN_DB, max(MIN_GAIN_DB, REFERENCE_GAIN_DB + adjustment))
    return min(gains, key=lambda gain: (abs(gain - target), gain)), strongest


def _library() -> ctypes.CDLL:
    for name in (ctypes.util.find_library("rtlsdr"), "librtlsdr.so.0", "librtlsdr.so"):
        if not name:
            continue
        try:
            return ctypes.CDLL(name)
        except OSError:
            pass
    raise RuntimeError("librtlsdr is not available; using the conservative 12.5 dB gain")


def _check(code: int, operation: str) -> None:
    if int(code) != 0:
        raise RuntimeError(f"RTL-SDR {operation} failed (code {int(code)})")


def _read_sync(library: ctypes.CDLL, device: ctypes.c_void_p, size: int = READ_BYTES) -> bytes:
    buffer = ctypes.create_string_buffer(size)
    received = ctypes.c_int()
    _check(library.rtlsdr_read_sync(device, buffer, size, ctypes.byref(received)), "IQ probe")
    return bytes(buffer.raw[:max(0, received.value)])


def probe_receiver_gain(receiver_serial: str, frequencies_mhz: list[float], cancel_event=None) -> dict[str, Any]:
    """Probe up to twelve channels, then release the SDR before rtl_airband starts."""
    frequencies = list(dict.fromkeys(int(round(float(value) * 1_000_000))
                                     for value in frequencies_mhz))[:MAX_PROBE_CHANNELS]
    if not frequencies:
        raise ValueError("Smart Gain needs at least one Marine channel")
    library = _library()
    library.rtlsdr_get_device_count.restype = ctypes.c_uint32
    library.rtlsdr_get_device_usb_strings.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
    library.rtlsdr_get_device_usb_strings.restype = ctypes.c_int
    library.rtlsdr_open.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint32]
    library.rtlsdr_open.restype = ctypes.c_int
    library.rtlsdr_close.argtypes = [ctypes.c_void_p]
    library.rtlsdr_close.restype = ctypes.c_int
    for function, args in (
        ("rtlsdr_set_sample_rate", [ctypes.c_void_p, ctypes.c_uint32]),
        ("rtlsdr_set_center_freq", [ctypes.c_void_p, ctypes.c_uint32]),
        ("rtlsdr_set_direct_sampling", [ctypes.c_void_p, ctypes.c_int]),
        ("rtlsdr_set_tuner_gain_mode", [ctypes.c_void_p, ctypes.c_int]),
        ("rtlsdr_get_tuner_gains", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]),
        ("rtlsdr_set_tuner_gain", [ctypes.c_void_p, ctypes.c_int]),
        ("rtlsdr_reset_buffer", [ctypes.c_void_p]),
        ("rtlsdr_read_sync", [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]),
    ):
        getattr(library, function).argtypes = args
        getattr(library, function).restype = ctypes.c_int

    device = ctypes.c_void_p()
    matched_index = None
    for index in range(int(library.rtlsdr_get_device_count())):
        manufacturer, product, serial = (ctypes.create_string_buffer(256) for _ in range(3))
        if library.rtlsdr_get_device_usb_strings(index, manufacturer, product, serial) == 0:
            if serial.value.decode("utf-8", errors="replace") == str(receiver_serial):
                matched_index = index
                break
    if matched_index is None:
        raise RuntimeError(f"RTL-SDR serial {receiver_serial!r} was not found")
    _check(library.rtlsdr_open(ctypes.byref(device), matched_index), "open for Smart Gain")
    try:
        _check(library.rtlsdr_set_sample_rate(device, SAMPLE_RATE_HZ), "set probe sample rate")
        _check(library.rtlsdr_set_direct_sampling(device, 0), "select tuner mode")
        _check(library.rtlsdr_set_center_freq(device, frequencies[0]), "tune probe channel")
        count = int(library.rtlsdr_get_tuner_gains(device, None))
        if count <= 0:
            raise RuntimeError("RTL-SDR did not report supported tuner gains")
        raw_gains = (ctypes.c_int * count)()
        returned = int(library.rtlsdr_get_tuner_gains(device, raw_gains))
        gains = supported_gains([raw_gains[index] / 10 for index in range(returned)])
        reference = min(gains, key=lambda gain: (abs(gain - REFERENCE_GAIN_DB), gain))
        _check(library.rtlsdr_set_tuner_gain_mode(device, 1), "lock Smart Gain probe")
        _check(library.rtlsdr_set_tuner_gain(device, round(reference * 10)), "set Smart Gain reference")
        _check(library.rtlsdr_reset_buffer(device), "reset probe buffer")
        measurements = []
        for index, frequency in enumerate(frequencies):
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Smart Gain probe cancelled")
            if index:
                _check(library.rtlsdr_set_center_freq(device, frequency), "retune probe channel")
                _check(library.rtlsdr_reset_buffer(device), "reset retuned probe buffer")
            raw = _read_sync(library, device) + _read_sync(library, device)
            if cancel_event is not None and cancel_event.is_set():
                raise RuntimeError("Smart Gain probe cancelled")
            measurements.append({"frequency_mhz": frequency / 1_000_000, **analyze_iq(raw)})
        selected, strongest = choose_gain(measurements, gains)
        return {"gain_db": selected, "reference_gain_db": reference,
                "probed_channels": len(measurements), "measurement": strongest}
    finally:
        library.rtlsdr_close(device)
