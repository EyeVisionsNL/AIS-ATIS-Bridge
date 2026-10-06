from __future__ import annotations
from io import BytesIO
from typing import Any
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

HEADERS=("Mode","Channel Bank","ID","Name","Channel MHz","Frequency MHz","Scan Enabled")

def export_channels(settings:dict[str,Any])->bytes:
    workbook=Workbook(); sheet=workbook.active; sheet.title="Channels"; sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.fill=PatternFill("solid",fgColor="173746"); cell.font=Font(color="FFFFFF",bold=True); cell.alignment=Alignment(horizontal="center")
    for channel in settings["channels"]: sheet.append(("Marine",settings["channel_bank"],channel["id"],channel["label"],None,channel["frequency_mhz"],channel["scan_enabled"]))
    sheet.freeze_panes="A2"; sheet.auto_filter.ref=f"A1:G{sheet.max_row}"
    for width,column in zip((14,22,22,30,16,18,16),"ABCDEFG"): sheet.column_dimensions[column].width=width
    for cell in sheet["F"][1:]: cell.number_format="0.000000"
    output=BytesIO(); workbook.save(output); return output.getvalue()

def import_channels(data:bytes)->dict[str,Any]:
    if len(data)>2*1024*1024: raise ValueError("Excel file exceeds 2 MB")
    try: workbook=load_workbook(BytesIO(data),read_only=True,data_only=True)
    except Exception as error: raise ValueError("File is not a readable .xlsx workbook") from error
    if "Channels" not in workbook.sheetnames: raise ValueError("Workbook needs a Channels sheet")
    sheet=workbook["Channels"]
    header=tuple(str(v or "").strip().lower() for v in next(sheet.iter_rows(min_row=1,max_row=1,values_only=True)))
    positions={name:index for index,name in enumerate(header) if name}
    required=("mode","channel bank","id","name","frequency mhz")
    if any(name not in positions for name in required):
        raise ValueError("Channels sheet needs Mode, Channel Bank, ID, Name and Frequency MHz columns")
    scan_column=positions.get("scan enabled",positions.get("scan"))
    channels=[]; bank=None
    for row_number,row in enumerate(sheet.iter_rows(min_row=2,values_only=True),start=2):
        values=list(row)
        if not any(v not in (None,"") for v in values): continue
        def value(name, default=None):
            index=positions.get(name)
            return values[index] if index is not None and index<len(values) else default
        # SDRCC's combined workbook includes Aviation rows; the bridge imports
        # only the Marine bank and leaves unrelated modes alone.
        if str(value("mode") or "").strip().lower()!="marine": continue
        row_bank=str(value("channel bank") or "").strip() or "marine"
        if bank is not None and row_bank!=bank: raise ValueError(f"Row {row_number}: Channel Bank must be identical")
        bank=row_bank
        scan_value=value("scan enabled",value("scan",False)) if scan_column is not None else False
        enabled=scan_value if isinstance(scan_value,bool) else str(scan_value or "").strip().lower() in ("1","true","yes","ja","on")
        channels.append({"id":str(value("id") or "").strip(),"label":str(value("name") or "").strip(),"frequency_mhz":value("frequency mhz"),"scan_enabled":enabled})
    if not channels: raise ValueError("Workbook contains no channels")
    return {"channel_bank":bank or "marine","channels":channels}
