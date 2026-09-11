from __future__ import annotations

import numpy as np

SAMPLE_RATE_HZ = 16_000
BIT_RATE = 1_200.0
LOW_TONE_HZ = 1_300.0
HIGH_TONE_HZ = 2_100.0
PACKET_SYMBOLS = 34
PACKET_BITS = PACKET_SYMBOLS * 10
PHASING_SYMBOLS = (125,111,125,110,125,109,125,108,125,107,125,106,121,105,121,104)


def _ten_bits(value: int) -> tuple[int, ...]:
    bits = [(value >> bit) & 1 for bit in range(7)]
    b_count = bits.count(0)
    return tuple(bits + [1 if b_count & mask else 0 for mask in (4, 2, 1)])


PHASING_BITS = np.asarray([b for symbol in PHASING_SYMBOLS for b in _ten_bits(symbol)], dtype=np.int8)
PHASING_POLARITY = np.where(PHASING_BITS == 1, 1.0, -1.0)


def identity_projection(groups: list[int]) -> dict | None:
    if len(groups) != 5 or any(value < 0 or value > 99 for value in groups):
        return None
    code = "".join(f"{value:02d}" for value in groups)
    if len(code) != 10 or not code.startswith("9"):
        return None
    mid, letter = int(code[1:4]), int(code[4:6])
    callsign = f"P{chr(64 + letter)}{code[6:]}" if mid in (244,245,246) and 1 <= letter <= 26 else None
    return {"atis_code": code, "mid": mid, "callsign": callsign}


def _symbol(bits: np.ndarray, position: int) -> tuple[int | None, bool]:
    units = bits[(position - 1) * 10:position * 10]
    if len(units) != 10:
        return None, False
    value = sum(int(unit) << bit for bit, unit in enumerate(units[:7]))
    expected = np.asarray([1 if int(np.count_nonzero(units[:7] == 0)) & mask else 0 for mask in (4,2,1)])
    return value, bool(np.array_equal(units[7:], expected))


def _choose(symbols: dict, primary: int, repeated: int) -> tuple[int | None, bool]:
    first, first_ok = symbols[primary]; second, second_ok = symbols[repeated]
    if first_ok and second_ok:
        return (first, False) if first == second else (None, False)
    if first_ok: return first, True
    if second_ok: return second, True
    return None, False


def _discriminator(samples: np.ndarray, sample_rate: int) -> np.ndarray:
    length = max(9, int(round(sample_rate / BIT_RATE))) | 1
    offsets, window = np.arange(length), np.hanning(length)
    def energy(frequency: float) -> np.ndarray:
        kernel = window * np.exp(-2j * np.pi * frequency * offsets / sample_rate)
        filtered = np.convolve(samples, kernel[::-1], mode="same")
        return filtered.real ** 2 + filtered.imag ** 2
    low, high = energy(LOW_TONE_HZ), energy(HIGH_TONE_HZ)
    return (low - high) / (low + high + 1e-7)


def decode_samples(samples: np.ndarray, sample_rate: int = SAMPLE_RATE_HZ) -> list[dict]:
    audio = np.clip(np.nan_to_num(np.asarray(samples, dtype=np.float64).reshape(-1)), -1, 1)
    if len(audio) < int((PACKET_BITS + 10) * sample_rate / BIT_RATE): return []
    disc, step, axis = _discriminator(audio, sample_rate), sample_rate / BIT_RATE, np.arange(len(audio))
    candidates = []
    for phase in np.arange(0.0, step, 1.0):
        count = int((len(disc) - phase) / step)
        if count < len(PHASING_BITS): continue
        values = np.interp(phase + (np.arange(count) + .5) * step, axis, disc)
        decided = np.where(values >= 0, 1.0, -1.0)
        matches = np.rint((np.correlate(decided, PHASING_POLARITY, mode="valid") + len(PHASING_BITS)) / 2).astype(int)
        scores = np.correlate(values, PHASING_POLARITY, mode="valid") / (np.correlate(abs(values), np.ones(len(PHASING_BITS)), mode="valid") + 1e-9)
        for index in np.flatnonzero((matches >= len(PHASING_BITS)-10) & (scores >= .85)):
            start = phase + float(index) * step
            if start + (PACKET_BITS + 1) * step < len(disc): candidates.append((start, float(scores[index])))
    results = []
    for start, score in sorted(candidates):
        if results and start - results[-1]["sample_index"] < step: continue
        centers = start + (np.arange(PACKET_BITS) + .5) * step
        bits = np.where(np.interp(centers, np.arange(len(disc)), disc) >= 0, 1, 0).astype(np.int8)
        symbols = {p:_symbol(bits,p) for p in range(1, PACKET_SYMBOLS+1)}
        if any(not symbols[p][1] or symbols[p][0] != value for p,value in enumerate(PHASING_SYMBOLS,1)): continue
        if _choose(symbols,13,18)[0] != 121 or _choose(symbols,15,20)[0] != 121: continue
        groups=[]; corrections=0
        for pair in ((17,22),(19,24),(21,26),(23,28),(25,30)):
            value, corrected = _choose(symbols,*pair)
            if value is None: break
            groups.append(value); corrections += int(corrected)
        if len(groups) != 5 or _choose(symbols,27,32)[0] != 127: continue
        ecc = _choose(symbols,29,34)[0]; calculated = 121
        for value in groups: calculated ^= value
        calculated ^= 127
        identity = identity_projection(groups)
        if ecc != calculated or identity is None: continue
        results.append({**identity,"sample_index":int(round(start)),"phasing_score":round(score,4),"corrected_symbols":corrections,"validation":"ten_unit_time_diversity_ecc"})
    return results
