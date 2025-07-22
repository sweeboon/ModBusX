# modbusx/logger.py

"""
Logging utility for ModbusX app.
Stub: Replace with proper logging (to file, console, GUI) as needed.
"""
from PyQt5.QtCore import QObject, pyqtSignal
import datetime

class Logger(QObject):
    message_signal = pyqtSignal(str)  # Signal for emitting log messages

    def __init__(self):
        super().__init__()

    def log(self, msg: str):
        timestr = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]"
        full_msg = f"{timestr} {msg}"
        print(full_msg)  # Print to console
        self.message_signal.emit(full_msg)  # Emit to any listeners (UI, etc.)

    def debug(self, msg: str):
        timestr = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]"
        full_msg = f"DEBUG: {timestr} {msg}"
        print(full_msg)  # Print to console
        self.message_signal.emit(full_msg)  # Emit to any listeners (UI, etc.)

# Singleton instance
global_logger = Logger()