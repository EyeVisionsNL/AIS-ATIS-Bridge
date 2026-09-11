from ais_atis_bridge.channel_xlsx import export_channels, import_channels
from ais_atis_bridge.config import validate

def test_excel_round_trip():
    settings=validate({})
    imported=import_channels(export_channels(settings))
    assert imported["channel_bank"]=="rotterdam_port"
    assert imported["channels"]==settings["channels"]
