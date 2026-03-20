# modbusx/logger.py

"""
Comprehensive logging utility for ModbusX app.
Provides file, console, and GUI logging with proper levels and formatting.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal

class ModBusXLogger(QObject):
    """ModBusX logging class with Qt signal support for GUI integration."""
    
    # Qt signals for GUI integration
    log_message = pyqtSignal(str, str, str)  # (level, module_name, message)
    debug_message = pyqtSignal(str)
    info_message = pyqtSignal(str)
    warning_message = pyqtSignal(str)
    error_message = pyqtSignal(str)
    
    def __init__(self, name: str = "ModBusX", log_file: Optional[str] = None):
        super().__init__()
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.name = name  # Store name for Qt signals
        
        # Prevent duplicate handlers
        if not self.logger.handlers:
            self._setup_handlers(log_file)
    
    def _setup_handlers(self, log_file: Optional[str] = None):
        """Setup logging handlers for console and file output."""
        
        # Create formatter
        formatter = logging.Formatter(
            '[%(asctime)s] %(levelname)-8s [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_path, mode='a', encoding='utf-8')
            except OSError as exc:
                # Fall back to console-only logging if file handler setup fails
                self.logger.warning("Unable to set up file logging at %s: %s", log_path, exc)
            else:
                file_handler.setLevel(logging.DEBUG)
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
    
    def debug(self, message: str, *args, **kwargs):
        """Log debug message."""
        formatted_msg = message % args if args else message
        self.logger.debug(formatted_msg, **kwargs)
        self.debug_message.emit(formatted_msg)
        self.log_message.emit("DEBUG", self.name, formatted_msg)
    
    def info(self, message: str, *args, **kwargs):
        """Log info message."""
        formatted_msg = message % args if args else message
        self.logger.info(formatted_msg, **kwargs)
        self.info_message.emit(formatted_msg)
        self.log_message.emit("INFO", self.name, formatted_msg)
    
    def warning(self, message: str, *args, **kwargs):
        """Log warning message."""
        formatted_msg = message % args if args else message
        self.logger.warning(formatted_msg, **kwargs)
        self.warning_message.emit(formatted_msg)
        self.log_message.emit("WARNING", self.name, formatted_msg)
    
    def error(self, message: str, *args, **kwargs):
        """Log error message."""
        formatted_msg = message % args if args else message
        self.logger.error(formatted_msg, **kwargs)
        self.error_message.emit(formatted_msg)
        self.log_message.emit("ERROR", self.name, formatted_msg)
    
    def critical(self, message: str, *args, **kwargs):
        """Log critical message."""
        formatted_msg = message % args if args else message
        self.logger.critical(formatted_msg, **kwargs)
        self.error_message.emit(formatted_msg)  # Use error signal for critical too
        self.log_message.emit("CRITICAL", self.name, formatted_msg)
    
    def exception(self, message: str, *args, **kwargs):
        """Log exception with traceback."""
        formatted_msg = message % args if args else message
        self.logger.exception(formatted_msg, **kwargs)
        self.error_message.emit(f"EXCEPTION: {formatted_msg}")
        self.log_message.emit("EXCEPTION", self.name, formatted_msg)
    
    def set_level(self, level: str):
        """Set logging level."""
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL
        }
        if level.upper() in level_map:
            self.logger.setLevel(level_map[level.upper()])
    
    # Legacy compatibility methods
    def log(self, message: str, *args, **kwargs):
        """Legacy log method - maps to info."""
        self.info(message, *args, **kwargs)


# Global logger instance
_global_logger: Optional[ModBusXLogger] = None


def _default_log_file() -> Path:
    """
    Determine a writable default log file location.
    Preference order:
      1. Environment variable MODBUSX_LOG_DIR
      2. User home directory under ~/.modbusx/logs
    """
    env_log_dir = os.environ.get("MODBUSX_LOG_DIR")
    if env_log_dir:
        log_dir = Path(env_log_dir).expanduser()
    else:
        log_dir = Path.home() / ".modbusx" / "logs"
    return log_dir / "modbusxLog.txt"

def initialize_global_logger(log_file: Optional[str] = None) -> ModBusXLogger:
    """Initialize the global logger instance."""
    global _global_logger
    
    if log_file is None:
        # Default log file location
        log_file = _default_log_file()
    else:
        log_file = Path(log_file).expanduser()
    
    _global_logger = ModBusXLogger("ModBusX", str(log_file))
    return _global_logger

class _ModuleLoggerProxy:
    """Proxy that forwards logs to the global logger but preserves module name in GUI."""

    def __init__(self, module_name: str):
        self.module_name = module_name

    def _emit(self, level_name: str, message: str, *args, **kwargs):
        gl = get_logger()  # global logger
        formatted = message % args if args else message
        # Log to handlers using python logging
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
            'EXCEPTION': logging.ERROR,
        }
        level = level_map.get(level_name, logging.INFO)
        gl.logger.log(level, formatted)
        # Emit GUI signal with original module name
        gl.log_message.emit(level_name, self.module_name, formatted)
        # Also emit typed signals for convenience
        if level_name == 'DEBUG':
            gl.debug_message.emit(formatted)
        elif level_name == 'INFO':
            gl.info_message.emit(formatted)
        elif level_name in ('WARNING',):
            gl.warning_message.emit(formatted)
        elif level_name in ('ERROR', 'CRITICAL', 'EXCEPTION'):
            gl.error_message.emit(formatted)

    def debug(self, message: str, *args, **kwargs):
        self._emit('DEBUG', message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs):
        self._emit('INFO', message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs):
        self._emit('WARNING', message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs):
        self._emit('ERROR', message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs):
        self._emit('CRITICAL', message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs):
        self._emit('EXCEPTION', message, *args, **kwargs)

    # Legacy compatibility
    def log(self, message: str, *args, **kwargs):
        self.info(message, *args, **kwargs)


def get_logger(name: Optional[str] = None):
    """Get a logger for modules (GUI-friendly).

    - Without a name: returns the global ModBusXLogger (emits to GUI).
    - With a name: returns a proxy that forwards to the global logger but
      preserves the module name in GUI log_message.
    """
    global _global_logger

    if _global_logger is None:
        initialize_global_logger()

    if name:
        return _ModuleLoggerProxy(name)

    return _global_logger

# Convenience functions for global logging
def debug(message: str, *args, **kwargs):
    """Global debug logging function."""
    get_logger().debug(message, *args, **kwargs)

def info(message: str, *args, **kwargs):
    """Global info logging function."""
    get_logger().info(message, *args, **kwargs)

def warning(message: str, *args, **kwargs):
    """Global warning logging function."""
    get_logger().warning(message, *args, **kwargs)

def error(message: str, *args, **kwargs):
    """Global error logging function."""
    get_logger().error(message, *args, **kwargs)

def critical(message: str, *args, **kwargs):
    """Global critical logging function."""
    get_logger().critical(message, *args, **kwargs)

def exception(message: str, *args, **kwargs):
    """Global exception logging function."""
    get_logger().exception(message, *args, **kwargs)

# Backward compatibility
global_logger = get_logger()
