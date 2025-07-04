# modbusx/logger.py

"""
Logging utility for ModbusX app.
Stub: Replace with proper logging (to file, console, GUI) as needed.
"""

import datetime

def log(msg: str):
    print(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")