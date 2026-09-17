from __future__ import annotations
import json, os
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_CHANNELS=[("ch16_nood","CH16 Nood/Oproep",156.800,False),("ch13_brug","CH13 Brug/Schip",156.650,False),("ch11_vts","CH11 VTS",156.550,False),("ch14_vts","CH14 VTS",156.700,False),("ch12_haven","CH12 Haven",156.600,False),("ch10_werk","CH10 Werk",156.500,False),("ch09_oproep","CH09 Oproep",156.450,False),("ch08_werk","CH08 Werk",156.400,True),("ch06_sleep","CH06 Sleep",156.300,False),("v01_maasap","V01 Maasmond Approach",160.650,True),("v02_maaspl","V02 Maasvlakte Pilot",160.700,True),("v03_maasmd","V03 Maasmond",160.750,True),("v05_rozbg","V05 Rozenburg",160.850,True),("v60_waalh","V60 Waalhaven",160.625,True),("v61_botlek","V61 Botlek",160.675,True),("v62_oudem","V62 Oude Maas",160.725,True),("v63_eemhv","V63 Eemhaven",160.775,True),("v65_rozbg2","V65 Rozenburg",160.875,True),("v66_europt","V66 Europoort",160.925,True),("v79_dordr","V79 Dordrecht",161.575,True),("v80_maassl","V80 Maassluis",161.625,True),("v81_maasbr","V81 Maasbruggen",161.675,True)]
DEFAULTS={"receiver":"","tuning_mode":"scan","selected_channel_id":"v61_botlek","channel_bank":"rotterdam_port","channels":[{"id":i,"label":n,"frequency_mhz":f,"scan_enabled":e} for i,n,f,e in DEFAULT_CHANNELS],"gain_mode":"auto","gain_db":20.7,"squelch_mode":"auto","squelch_threshold_dbfs":-47,"scan_interval_ms":200,"ppm":0,"ais_ships_url":"http://127.0.0.1:8119/ships.json","ais_viewer_url":"http://127.0.0.1:8119/","web_host":"0.0.0.0","web_port":8120}

def path()->Path: return Path(os.environ.get("AIS_ATIS_CONFIG","/etc/ais-atis-bridge/config.json"))
def load()->dict[str,Any]:
    result=deepcopy(DEFAULTS)
    try:
        raw=json.loads(path().read_text(encoding="utf-8"))
        if isinstance(raw,dict): result.update(raw)
    except (OSError,ValueError,TypeError): pass
    return validate(result)

def validate(raw:dict[str,Any])->dict[str,Any]:
    result=deepcopy(DEFAULTS); result["receiver"]=str(raw.get("receiver") or "").strip()[:80]
    result["tuning_mode"]="fixed" if raw.get("tuning_mode")=="fixed" else "scan"; result["channel_bank"]=str(raw.get("channel_bank") or DEFAULTS["channel_bank"])[:48]
    source=raw.get("channels",DEFAULTS["channels"])
    if not isinstance(source,list) or not 1<=len(source)<=500: raise ValueError("Channel list must contain 1 to 500 rows")
    channels=[]; ids=set(); frequencies=set()
    for item in source:
        if not isinstance(item,dict): raise ValueError("Invalid channel row")
        channel_id=str(item.get("id") or "").strip(); label=str(item.get("label") or "").strip()
        try: frequency=round(float(item.get("frequency_mhz")),6)
        except (TypeError,ValueError) as error: raise ValueError("Invalid channel frequency") from error
        if not channel_id or len(channel_id)>48 or channel_id in ids: raise ValueError(f"Missing or duplicate channel ID: {channel_id}")
        if not label or len(label)>64: raise ValueError(f"Invalid name for channel {channel_id}")
        if not 156.0<=frequency<=163.0 or frequency in frequencies: raise ValueError(f"Invalid or duplicate frequency for {channel_id}")
        ids.add(channel_id); frequencies.add(frequency); channels.append({"id":channel_id,"label":label,"frequency_mhz":frequency,"scan_enabled":bool(item.get("scan_enabled"))})
    if result["tuning_mode"]=="scan" and not any(x["scan_enabled"] for x in channels): raise ValueError("Enable at least one scan channel")
    selected=str(raw.get("selected_channel_id") or ""); result["selected_channel_id"]=selected if selected in ids else channels[0]["id"]; result["channels"]=channels
    result["gain_mode"]="manual" if raw.get("gain_mode")=="manual" else "auto"; result["gain_db"]=max(0.0,min(49.6,float(raw.get("gain_db",20.7)))); result["ppm"]=max(-200,min(200,int(raw.get("ppm",0))))
    mode=raw.get("squelch_mode","auto")
    if mode not in ("auto","manual"): raise ValueError("Invalid squelch mode")
    try: threshold=float(raw.get("squelch_threshold_dbfs",-47))
    except (ValueError,TypeError) as error: raise ValueError("Squelch threshold must be an integer from -100 to -1 dBFS") from error
    if not -100<=threshold<=-1 or not threshold.is_integer(): raise ValueError("Squelch threshold must be an integer from -100 to -1 dBFS")
    result["squelch_mode"]=mode; result["squelch_threshold_dbfs"]=int(threshold)
    try: scan_interval_ms=int(raw.get("scan_interval_ms",200))
    except (ValueError,TypeError) as error: raise ValueError("Scan speed must be 100-500 ms per channel in 50 ms steps") from error
    if scan_interval_ms<100 or scan_interval_ms>500 or scan_interval_ms%50: raise ValueError("Scan speed must be 100-500 ms per channel in 50 ms steps")
    result["scan_interval_ms"]=scan_interval_ms
    for key in ("ais_ships_url","ais_viewer_url"):
        value=str(raw.get(key) or DEFAULTS[key]).strip()
        if not value.startswith(("http://127.0.0.1:","http://localhost:")): raise ValueError(f"{key} must use localhost")
        result[key]=value
    result["web_host"]=str(raw.get("web_host") or DEFAULTS["web_host"]); result["web_port"]=int(raw.get("web_port") or 8120); return result

def save(raw:dict[str,Any])->dict[str,Any]:
    clean=validate(raw); target=path(); target.parent.mkdir(parents=True,exist_ok=True); temporary=target.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean,indent=2)+"\n",encoding="utf-8"); os.chmod(temporary,0o640); temporary.replace(target); return clean
