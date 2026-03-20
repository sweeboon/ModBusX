"""Scripting Service facade."""

from __future__ import annotations
from typing import Any, Dict, Optional
from modbusx.logger import get_logger
from .parser import load_scenario
from .runtime import ScriptingRuntime


class ScriptingService:
    def __init__(self):
        self.logger = get_logger("ScriptingService")
        self._scenario: Optional[Dict[str, Any]] = None
        self._runtime: Optional[ScriptingRuntime] = None

    def run_from_file(self, path: str) -> bool:
        try:
            scenario = load_scenario(path)
            self._scenario = scenario
            self._runtime = ScriptingRuntime(scenario)
            self._runtime.start()
            self.logger.info(f"Started script: {scenario.get('name','scenario')} from {path}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start script: {e}")
            return False

    def stop(self) -> None:
        if self._runtime:
            self._runtime.stop()
            self.logger.info("Stopped script")
        self._runtime = None
        self._scenario = None

    def status(self) -> Dict[str, Any]:
        if self._runtime and self._scenario:
            return {
                "name": self._scenario.get("name"),
                "steps": len(self._scenario.get("steps", [])),
                "running": self._runtime.is_running(),
            }
        return {"name": None, "steps": 0, "running": False}


_scripting_service: Optional[ScriptingService] = None


def get_scripting_service() -> ScriptingService:
    global _scripting_service
    if _scripting_service is None:
        _scripting_service = ScriptingService()
    return _scripting_service

