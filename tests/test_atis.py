import numpy as np

from ais_atis_bridge import atis


def ten_unit(value: int) -> list[int]:
    return list(atis._ten_unit_bits(value))


def packet_symbols(letter_group: int = 2) -> list[int]:
    groups = [92, 44, letter_group, 36, 55]
    ecc = 121
    for value in groups:
        ecc ^= value
    ecc ^= 127
    return [
        125, 111, 125, 110, 125, 109, 125, 108,
        125, 107, 125, 106, 121, 105, 121, 104,
        groups[0], 121, groups[1], 121, groups[2], groups[0],
        groups[3], groups[1], groups[4], groups[2], 127, groups[3],
        ecc, groups[4], 127, 127, 127, ecc,
    ]


def packet_bits(letter_group: int = 2) -> np.ndarray:
    return np.asarray(
        [bit for symbol in packet_symbols(letter_group) for bit in ten_unit(symbol)],
        dtype=np.int8,
    )


def synthesize(*, tone_offset_hz: float = 0.0) -> np.ndarray:
    prefix = [1, 0] * 10
    bits = packet_bits().tolist()
    framed = np.asarray(prefix + bits + [1] * 40, dtype=np.int8)
    count = int(len(framed) * atis.SAMPLE_RATE_HZ / atis.BIT_RATE)
    indexes = np.minimum(
        (np.arange(count) * atis.BIT_RATE / atis.SAMPLE_RATE_HZ).astype(int),
        len(framed) - 1,
    )
    frequencies = np.where(
        framed[indexes] == 1, atis.LOW_TONE_HZ, atis.HIGH_TONE_HZ,
    ) + float(tone_offset_hz)
    phase = np.cumsum(2.0 * np.pi * frequencies / atis.SAMPLE_RATE_HZ)
    noise = np.random.default_rng(4).standard_normal(count) * 0.018
    return (0.32 * np.sin(phase) + noise).astype(np.float32)


def discriminator_for(letter_group: int) -> np.ndarray:
    bits = packet_bits(letter_group)
    units = np.where(bits == 1, 0.90, -0.90).astype(np.float64)
    step = atis.SAMPLE_RATE_HZ / atis.BIT_RATE
    length = int(np.ceil((len(units) + 2) * step)) + 4
    discriminator = np.zeros(length, dtype=np.float64)
    for index, value in enumerate(units):
        start = max(0, int(np.floor(index * step)))
        end = min(length, int(np.ceil((index + 1) * step)) + 1)
        discriminator[start:end] = value
    return discriminator


def test_shared_decoder_profile():
    assert atis.DECODER_VERSION == 4
    assert atis.DECODER_PROFILE == "sdrcc-atis-v4"


def test_dutch_identity_projection():
    result = atis.identity_projection([92, 44, 2, 36, 55])
    assert result["atis_code"] == "9244023655"
    assert result["mid"] == 244
    assert result["country"] == "Netherlands"
    assert result["callsign"] == "PB3655"


def test_foreign_identity_is_decoded_without_guessing_callsign():
    result = atis.identity_projection([92, 11, 1, 48, 21])
    assert result["atis_code"] == "9211014821"
    assert result["mid"] == 211
    assert result["country"] == "Germany"
    assert result["callsign"] is None
    assert result["callsign_projection"] == "ais_correlation"


def test_tone_offset_packet_decodes():
    decoded = atis.decode_samples(synthesize(tone_offset_hz=25.0))
    assert len(decoded) == 1
    assert decoded[0]["atis_code"] == "9244023655"
    assert decoded[0]["decoder_profile"] == "sdrcc-atis-v4"


def test_ambiguous_f_g_soft_correction_is_rejected():
    discriminator = discriminator_for(6)
    step = atis.SAMPLE_RATE_HZ / atis.BIT_RATE
    for symbol_position in (21, 26):
        for unit_offset in (0, 9):
            unit_index = (symbol_position - 1) * 10 + unit_offset
            start = max(0, int(np.floor(unit_index * step)))
            end = min(len(discriminator), int(np.ceil((unit_index + 1) * step)) + 1)
            discriminator[start:end] = 0.0
    decoded = atis._decode_packet(
        discriminator, 0.0, atis.SAMPLE_RATE_HZ, atis.BIT_RATE, 0.90,
    )
    assert decoded is None


def test_invalid_identity_is_rejected():
    assert atis.identity_projection([1, 2, 3]) is None
