from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

CHANNEL_MASTER_VERSION = 3
CHANNEL_MASTER_PATH = Path(__file__).with_name("static") / "rotterdam-port-channels.json"

DATA_ONLY_FREQUENCIES = {
    156.525,
    157.2, 161.8,
    157.25, 161.85,
    157.3, 161.9,
    161.95, 162.0,
    157.225, 161.825,
    157.275, 161.875,
    157.325, 161.925,
    161.975, 162.025,
}


def _is_data_only_frequency(value: Any) -> bool:
    try:
        return round(float(value), 6) in DATA_ONLY_FREQUENCIES
    except (TypeError, ValueError):
        return False


def _master_channels() -> list[dict[str, Any]]:
    rows = json.loads(CHANNEL_MASTER_PATH.read_text(encoding="utf-8"))
    return [{
        "id": str(row["id"]),
        "label": str(row["label"]),
        "frequency_mhz": round(float(row["frequency_mhz"]), 6),
        "scan_enabled": bool(row.get("scan_enabled")),
    } for row in rows]


DEFAULT_CHANNELS = _master_channels()
DEFAULTS = {
    "receiver": "", "tuning_mode": "scan", "selected_channel_id": "vhf61",
    "channel_bank": "rotterdam_port", "channels": DEFAULT_CHANNELS,
    "channel_master_version": CHANNEL_MASTER_VERSION,
    "gain_mode": "smart", "gain_db": 12.5, "squelch_mode": "auto",
    "squelch_threshold_dbfs": -47, "scan_interval_ms": 200, "ppm": 0,
    "ais_ships_url": "http://127.0.0.1:8119/ships.json",
    "ais_viewer_url": "http://127.0.0.1:8119/", "web_host": "0.0.0.0",
    "web_port": 8120,
}


def path() -> Path:
    return Path(os.environ.get("AIS_ATIS_CONFIG", "/etc/ais-atis-bridge/config.json"))


def _preserve_user_channels(raw: dict[str, Any]) -> dict[str, Any]:
    """Upgrade old Rotterdam banks by frequency while retaining user choices."""
    try:
        old_channels = raw.get("channels")
        if not isinstance(old_channels, list):
            return raw
        by_frequency = {}
        selected_frequency = None
        for item in old_channels:
            if not isinstance(item, dict):
                continue
            try:
                frequency = round(float(item.get("frequency_mhz")), 6)
            except (TypeError, ValueError):
                continue
            by_frequency[frequency] = item
            if item.get("id") == raw.get("selected_channel_id"):
                selected_frequency = frequency

        merged = []
        master_frequencies = set()
        used_ids = set()
        for master in _master_channels():
            frequency = master["frequency_mhz"]
            prior = by_frequency.get(frequency)
            row = dict(master)
            if prior is not None:
                row["scan_enabled"] = bool(prior.get("scan_enabled"))
            merged.append(row)
            master_frequencies.add(frequency)
            used_ids.add(row["id"])

        # Imported/custom channels remain available if they are not in the new
        # Marine master list. A matching frequency uses the canonical master ID.
        for item in old_channels:
            if not isinstance(item, dict):
                continue
            try:
                frequency = round(float(item.get("frequency_mhz")), 6)
            except (TypeError, ValueError):
                continue
            if frequency in master_frequencies or _is_data_only_frequency(frequency):
                continue
            channel_id = str(item.get("id") or "").strip()
            if not channel_id or channel_id in used_ids:
                continue
            merged.append({
                "id": channel_id,
                "label": str(item.get("label") or "").strip(),
                "frequency_mhz": frequency,
                "scan_enabled": bool(item.get("scan_enabled")),
            })
            used_ids.add(channel_id)

        upgraded = dict(raw)
        upgraded["channels"] = merged
        upgraded["channel_bank"] = "rotterdam_port"
        upgraded["channel_master_version"] = CHANNEL_MASTER_VERSION
        if selected_frequency is not None:
            selected = next((row["id"] for row in merged
                             if row["frequency_mhz"] == selected_frequency), None)
            if selected:
                upgraded["selected_channel_id"] = selected
        return upgraded
    except (OSError, ValueError, KeyError, TypeError):
        return raw


def load() -> dict[str, Any]:
    result = deepcopy(DEFAULTS)
    try:
        raw = json.loads(path().read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            if int(raw.get("channel_master_version", 0) or 0) < CHANNEL_MASTER_VERSION:
                raw = _preserve_user_channels(raw)
            result.update(raw)
    except (OSError, ValueError, TypeError):
        pass
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
        if not 155.775<=frequency<=162.6 or frequency in frequencies: raise ValueError(f"Invalid or duplicate frequency for {channel_id}")
        if _is_data_only_frequency(frequency): raise ValueError(f"Data-only marine frequency is not supported in Voice: {channel_id}")
        ids.add(channel_id); frequencies.add(frequency); channels.append({"id":channel_id,"label":label,"frequency_mhz":frequency,"scan_enabled":bool(item.get("scan_enabled"))})
    if result["tuning_mode"]=="scan" and not any(x["scan_enabled"] for x in channels): raise ValueError("Enable at least one scan channel")
    selected=str(raw.get("selected_channel_id") or ""); result["selected_channel_id"]=selected if selected in ids else channels[0]["id"]; result["channels"]=channels
    # Smart Gain probes once before rtl_airband starts, then holds one fixed
    # tuner gain for the whole receiver session.
    result["gain_mode"]="manual" if str(raw.get("gain_mode") or "").lower()=="manual" else "smart"
    try: result["gain_db"]=max(0.0,min(49.6,float(raw.get("gain_db",12.5))))
    except (ValueError,TypeError) as error: raise ValueError("Gain must be a number from 0 to 49.6 dB") from error
    result["ppm"]=max(-200,min(200,int(raw.get("ppm",0))))
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
    result["web_host"]=str(raw.get("web_host") or DEFAULTS["web_host"]); result["web_port"]=int(raw.get("web_port") or 8120)
    result["channel_master_version"]=CHANNEL_MASTER_VERSION
    return result

def save(raw:dict[str,Any])->dict[str,Any]:
    clean=validate(raw); target=path(); target.parent.mkdir(parents=True,exist_ok=True); temporary=target.with_suffix(".tmp")
    temporary.write_text(json.dumps(clean,indent=2)+"\n",encoding="utf-8"); os.chmod(temporary,0o640); temporary.replace(target); return clean
