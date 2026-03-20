"""Scenario schema utilities and duration parsing."""

from typing import Dict, Any

_UNITS = {"ms": 0.001, "s": 1.0}


def parse_duration(text: str) -> float:
    if not isinstance(text, str) or not text:
        raise ValueError("duration must be a string")
    text = text.strip().lower()
    for k, mult in _UNITS.items():
        if text.endswith(k):
            num = float(text[:-len(k)].strip())
            return num * mult
    try:
        return float(text)
    except Exception as e:
        raise ValueError(f"Invalid duration: {text}") from e


def normalize_target(defaults: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    norm = {
        "server": defaults.get("server"),
        "unit": int(defaults.get("unit", 1)),
        "reg_type": (defaults.get("reg_type") or "hr").lower(),
    }
    target = target or {}
    if "server" in target:
        norm["server"] = target["server"]
    if "unit" in target:
        norm["unit"] = int(target["unit"])
    if "reg_type" in target:
        norm["reg_type"] = str(target["reg_type"]).lower()
    if "addr" in target:
        norm["addr"] = int(target["addr"])
    if "start" in target:
        norm["start"] = int(target["start"])
    if "size" in target:
        norm["size"] = int(target["size"])
    return norm

