"""Scripting runtime: schedules scenario steps on the asyncio loop."""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import asyncio

from modbusx.bridge import get_async_server_manager
from modbusx.logger import get_logger, global_logger
from modbusx.services.register_sync_service import get_register_sync_service
from .schema import parse_duration
from .actions import ACTION_BUILDERS
from modbusx.services.register_validator import RegisterValidator
from modbusx.usability_logger import get_usability_logger


class ScriptingRuntime:
    def __init__(self, scenario: Dict[str, Any]):
        self.scenario = scenario
        self.logger = get_logger("ScriptingRuntime")
        self._tasks: List[asyncio.Task] = []
        self._running = False
        self._last_values: Dict[Tuple[str, str, int], int] = {}
        self._loop = get_async_server_manager().async_loop
        self._sync = get_register_sync_service()

    def parse_duration(self, text: str) -> float:
        return parse_duration(text)

    def resolve_server_id(self, server_key: Optional[str], unit: int) -> str:
        return f"{server_key or ''}_{int(unit)}"

    def get_last_value(self, server_id: str, reg_type: str, addr: int) -> int:
        return int(self._last_values.get((server_id, reg_type, addr), 0))

    def resolve_addr(self, reg_type: str, addr_raw: Any) -> int:
        """Resolve script-provided address to internal address.

        - If a string (e.g., "0x0000" or "400001"), use RegisterValidator.display_to_address.
        - If an integer, treat as internal address directly.
        """
        if isinstance(addr_raw, str):
            try:
                return int(RegisterValidator.display_to_address(addr_raw, reg_type))
            except Exception:
                pass
        try:
            return int(addr_raw)
        except Exception as e:
            raise ValueError(f"Invalid address value: {addr_raw}")

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(float(seconds))

    async def apply(self, server_id: str, reg_type: str, addr: Any, value: int) -> None:
        try:
            int_addr = self.resolve_addr(reg_type, addr)
            self._last_values[(server_id, reg_type, int_addr)] = int(value)
            self._sync.apply_to_server(server_id, reg_type, int_addr, value)
            msg = f"SCRIPT APPLY {server_id} {reg_type}:{int_addr}={value}"
            # Emit via module logger and global GUI logger to ensure visibility
            self.logger.info(msg)
            try:
                global_logger.log(msg)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(f"Scripting apply error: {e}")

    async def apply_bulk(self, server_id: str, changes: List[Dict[str, Any]]) -> None:
        try:
            for c in changes:
                int_addr = self.resolve_addr(c['reg_type'], c['addr'])
                self._last_values[(server_id, c['reg_type'], int_addr)] = int(c['value'])
            # Build normalized list with resolved addresses
            norm = []
            for c in changes:
                norm.append({
                    'reg_type': c['reg_type'],
                    'addr': self.resolve_addr(c['reg_type'], c['addr']),
                    'value': int(c['value'])
                })
            self._sync.apply_bulk_to_server(server_id, norm)
            msg = f"SCRIPT BULK {server_id} changes={len(changes)}"
            self.logger.info(msg)
            try:
                global_logger.log(msg)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(f"Scripting bulk error: {e}")

    async def _run_step(self, step: Dict[str, Any]):
        await asyncio.sleep(float(step["at"]))
        builder = ACTION_BUILDERS.get(step["action"])
        if not builder:
            self.logger.error(f"Unknown action: {step['action']}")
            return
        action = builder(step)
        await action.run(self)

    async def _runner(self):
        name = self.scenario.get('name', 'scenario')
        self.logger.info(f"Script started: {name}")
        get_usability_logger().log_event("TASK_START", "ScriptExecution", name)
        
        step_tasks = []
        for st in self.scenario.get("steps", []):
            task = asyncio.create_task(self._run_step(st))
            step_tasks.append(task)
        if step_tasks:
            await asyncio.gather(*step_tasks, return_exceptions=True)
            
        self.logger.info("Script finished")
        get_usability_logger().log_event("TASK_END", "ScriptExecution", f"{name}|SUCCESS")

    def start(self) -> asyncio.Task:
        if self._running:
            raise RuntimeError("Script already running")
        self._running = True
        task = self._loop.run_coroutine(self._runner())
        self._tasks.append(task)
        return task

    def stop(self):
        for t in list(self._tasks):
            try:
                t.cancel()
            except Exception:
                pass
        self._tasks.clear()
        self._running = False

    def is_running(self) -> bool:
        return self._running
