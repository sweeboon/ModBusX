"""Scripting actions: set, ramp, pulse, group_set (MVP)."""

from __future__ import annotations
from typing import Any, Dict, Callable


class BaseAction:
    def __init__(self, step: Dict[str, Any]):
        self.step = step

    async def run(self, runtime: "ScriptingRuntime") -> None:
        raise NotImplementedError


class SetAction(BaseAction):
    async def run(self, runtime: "ScriptingRuntime") -> None:
        t = self.step["target"]
        server_id = runtime.resolve_server_id(t.get("server"), t.get("unit"))
        reg_type = t.get("reg_type", "hr")
        addr = int(t["addr"])  # required
        value = int(self.step["value"])  # required
        await runtime.apply(server_id, reg_type, addr, value)


class RampAction(BaseAction):
    async def run(self, runtime: "ScriptingRuntime") -> None:
        t = self.step["target"]
        p = self.step.get("params", {})
        server_id = runtime.resolve_server_id(t.get("server"), t.get("unit"))
        reg_type = t.get("reg_type", "hr")
        addr = int(t["addr"])  # required
        step = int(p.get("step", 1))
        interval = float(runtime.parse_duration(p.get("interval", "1s")))
        duration = float(runtime.parse_duration(p.get("duration", "5s")))
        count = max(1, int(duration / interval))
        for _ in range(count):
            value = runtime.get_last_value(server_id, reg_type, addr) + step
            await runtime.apply(server_id, reg_type, addr, value)
            await runtime.sleep(interval)


class PulseAction(BaseAction):
    async def run(self, runtime: "ScriptingRuntime") -> None:
        t = self.step["target"]
        p = self.step.get("params", {})
        server_id = runtime.resolve_server_id(t.get("server"), t.get("unit"))
        reg_type = t.get("reg_type", "co")
        addr = int(t.get("addr", 1))
        high = int(p.get("high", 1))
        low = int(p.get("low", 0))
        hold = float(runtime.parse_duration(p.get("hold", "500ms")))
        repeats = int(p.get("repeats", 1))
        period = float(runtime.parse_duration(p.get("period", "1s")))
        for _ in range(max(1, repeats)):
            await runtime.apply(server_id, reg_type, addr, high)
            await runtime.sleep(hold)
            await runtime.apply(server_id, reg_type, addr, low)
            await runtime.sleep(max(0.0, period - hold))


class GroupSetAction(BaseAction):
    async def run(self, runtime: "ScriptingRuntime") -> None:
        t = self.step["target"]
        p = self.step.get("params", {})
        server_id = runtime.resolve_server_id(t.get("server"), t.get("unit"))
        reg_type = t.get("reg_type", "hr")
        start = int(t.get("start", 1))
        size = int(t.get("size", 1))
        pattern = p.get("pattern")
        constant = p.get("constant")
        changes = []
        for i in range(size):
            if pattern and i < len(pattern):
                val = int(pattern[i])
            else:
                val = int(constant if constant is not None else 0)
            changes.append({"reg_type": reg_type, "addr": start + i, "value": val})
        await runtime.apply_bulk(server_id, changes)


ACTION_BUILDERS: Dict[str, Callable[[dict], BaseAction]] = {
    "set": lambda s: SetAction(s),
    "ramp": lambda s: RampAction(s),
    "pulse": lambda s: PulseAction(s),
    "group_set": lambda s: GroupSetAction(s),
}

