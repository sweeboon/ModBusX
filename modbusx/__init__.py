"""
ModBusX - ModBus Register Manager

A comprehensive ModBus register management tool with MVC architecture.
"""

# Core Packages
from . import models
from . import services  
from . import ui
# Note: controllers package removed (was unused)

# Legacy compatibility imports
from .models import RegisterEntry, RegisterMap
from .services import RegisterValidator, MODBUS_REGISTER_TYPES

__version__ = "2.0.0"
__author__ = "ModBusX Development Team"

__all__ = [
    # Core packages
    'models',
    'services', 
    'ui',
    
    # Legacy compatibility
    'RegisterEntry',
    'RegisterMap',
    'RegisterValidator',
    'MODBUS_REGISTER_TYPES'
]