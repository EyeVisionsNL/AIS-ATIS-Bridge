from __future__ import annotations

import json
import re
from typing import Any
from urllib.request import Request, urlopen


def _number(value: Any) -> float | None:
    try:
        number = float(value)
        return number if number == number else None
    except (TypeError, ValueError):
        return None


def _ships(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("ships", "vessels", "targets", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        if isinstance(value, dict):
            return [x for x in value.values() if isinstance(x, dict)]
    if payload and all(isinstance(x, dict) for x in payload.values()):
        return list(payload.values())
    return []


def read_ships(url: str, timeout: float = 0.6) -> Any:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "AIS-ATIS-Bridge/0.1"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310, localhost enforced by config
        return json.loads(response.read(8 * 1024 * 1024).decode("utf-8"))


def codes_for_ship(ship: dict[str, Any]) -> dict[str, str]:
    mmsi = str(ship.get("mmsi") or "").strip().removesuffix(".0")
    if len(mmsi) != 9 or not mmsi.isdigit():
        return {}
    result = {f"9{mmsi}": "mmsi_direct"}
    callsign = str(ship.get("callsign") or "").strip().upper()
    match = re.fullmatch(r"([A-Z]{2,3})([0-9]{4})", callsign)
    if match:
        letters, digits = match.groups()
        for index in (1, 2):
            if index < len(letters):
                result.setdefault(f"9{mmsi[:3]}{ord(letters[index]) - 64:02d}{digits}", "callsign_standard")
    return result


def match_atis(atis_code: str, payload: Any, max_age_seconds: float = 30.0) -> dict[str, Any]:
    code = str(atis_code or "").strip()
    result: dict[str, Any] = {"matched": False, "status": "invalid_atis", "atis_code": code or None}
    if len(code) != 10 or not code.isdigit() or not code.startswith("9"):
        return result
    ships = _ships(payload)
    candidates = [(ship, codes_for_ship(ship).get(code)) for ship in ships]
    candidates = [(ship, method) for ship, method in candidates if method]
    # Dutch ATIS identity may be retained with a foreign AIS MMSI. Only use
    # the decoder's bounded Dutch projection when no standard candidate exists;
    # never bypass an ambiguous or rejected standard match.
    if not candidates and code[1:4] in {"244", "245", "246"}:
        letter = int(code[4:6])
        if 1 <= letter <= 26:
            callsign = f"P{chr(64 + letter)}{code[6:]}"
            candidates = [
                (ship, "callsign_exact_fallback") for ship in ships
                if str(ship.get("callsign") or "").strip().upper() == callsign
            ]
    result.update(status="not_found", candidate_count=len(candidates))
    if len(candidates) != 1:
        if len(candidates) > 1:
            result["status"] = "ambiguous"
        return result
    ship, method = candidates[0]
    age = _number(ship.get("last_signal", ship.get("age")))
    lat, lon = _number(ship.get("lat")), _number(ship.get("lon"))
    validated = _number(ship.get("validated"))
    mmsi = str(ship.get("mmsi") or "").strip().removesuffix(".0")
    if validated != 1:
        result["status"] = "not_validated"
    elif age is None or not 0 <= age <= max_age_seconds:
        result["status"] = "stale"
    elif (len(mmsi) != 9 or not mmsi.isdigit()
          or lat is None or lon is None or not -90 <= lat <= 90 or not -180 <= lon <= 180):
        result["status"] = "invalid_position"
    else:
        result.update({
            "matched": True, "status": "matched", "match_method": method,
            "mmsi": mmsi,
            "callsign": str(ship.get("callsign") or "").strip().upper() or None,
            "shipname": str(ship.get("shipname") or "").strip()[:80] or None,
            "latitude": round(lat, 6), "longitude": round(lon, 6),
            "last_signal_seconds": round(age, 1),
        })
    return result
