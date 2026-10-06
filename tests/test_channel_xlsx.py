from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from ais_atis_bridge.channel_xlsx import import_channels


def make_sdrcc_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Channels"
    sheet.append(["Mode", "Channel Bank", "ID", "Name", "Channel MHz", "Frequency MHz", "Scan"])
    sheet.append(["Aviation", "aviation", "air01", "Tower", None, 118.1, "Yes"])
    sheet.append(["Marine", "rotterdam_port", "vhf61", "VHF61 VTS", None, 160.675, "Yes"])
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_import_accepts_sdrcc_scan_header_and_ignores_aviation_rows():
    result = import_channels(make_sdrcc_workbook())
    assert result["channel_bank"] == "rotterdam_port"
    assert result["channels"] == [{
        "id": "vhf61", "label": "VHF61 VTS", "frequency_mhz": 160.675, "scan_enabled": True,
    }]


def test_bundled_rotterdam_workbook_has_133_voice_channels_and_two_scan_defaults():
    path = Path(__file__).parents[1] / "ais_atis_bridge/static/rotterdam-port-channels.xlsx"
    result = import_channels(path.read_bytes())
    assert len(result["channels"]) == 133
    assert {row["id"] for row in result["channels"] if row["scan_enabled"]} == {"vhf61", "vhf63"}
    frequencies = {row["frequency_mhz"] for row in result["channels"]}
    assert 155.775 in frequencies and 162.6 in frequencies
    assert not frequencies & {156.525, 161.95, 162.0, 161.975, 162.025}
