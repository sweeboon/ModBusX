# modbusx/core.py

"""
Core data classes and state management for ModbusX.
"""

from typing import Dict, List

class SlaveDevice:
    """Represents the configuration/state of a Modbus slave."""
    def __init__(self, port: int, unit_id: int, hr_value: int, ir_value: int):
        self.port = port
        self.unit_id = unit_id
        self.hr_value = hr_value
        self.ir_value = ir_value
        # Add later: register map, dynamic script info, etc.

class AppState:
    """Global state object (singleton pattern can be used if needed)."""
    def __init__(self):
        self.slaves: List[SlaveDevice] = []