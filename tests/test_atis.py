from ais_atis_bridge.atis import identity_projection


def test_dutch_identity_projection():
    result=identity_projection([92,44,2,36,55])
    assert result == {"atis_code":"9244023655","mid":244,"callsign":"PB3655"}


def test_invalid_identity_is_rejected(): assert identity_projection([1,2,3]) is None
