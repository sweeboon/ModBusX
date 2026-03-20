"""Scenario parser: load/validate/normalize a JSON scripting scenario (v1)."""

from typing import Any, Dict, List
import json
from .schema import parse_duration, normalize_target


def load_scenario(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return normalize_scenario(data)


def normalize_scenario(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("scenario must be an object")
    version = int(data.get("version", 1))
    if version != 1:
        raise ValueError(f"Unsupported scenario version: {version}")
    name = data.get("name") or "scenario"
    defaults = data.get("defaults") or {}
    steps = data.get("steps") or []
    if not isinstance(steps, list) or not steps:
        raise ValueError("scenario.steps must be a non-empty array")

    normalized_steps: List[Dict[str, Any]] = []
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"steps[{idx}] must be an object")
        action = (step.get("action") or "").lower()
        if action not in ("set", "ramp", "pulse", "groupset", "group_set"):
            raise ValueError(f"steps[{idx}].action unsupported: {action}")
        at = parse_duration(step.get("at", "0s"))
        target = normalize_target(defaults, step.get("target") or {})
        params = step.get("params") or {}
        value = step.get("value")
        if action == "set" and value is None:
            raise ValueError(f"steps[{idx}]: set requires 'value'")
        normalized_steps.append({
            "at": float(at),
            "action": "group_set" if action in ("groupset", "group_set") else action,
            "target": target,
            "params": params,
            "value": value,
        })

    normalized_steps.sort(key=lambda s: s["at"])  # schedule by time
    return {
        "name": name,
        "version": version,
        "defaults": defaults,
        "steps": normalized_steps,
    }

