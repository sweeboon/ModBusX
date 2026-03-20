"""
ModBusX UI Package

Contains pure UI components and legacy UI modules.
"""

# Pure UI Components (MVC compliant)
from . import components

# Bulk Operations Dialog (recommended)
from .bulk_operations_manual import ManualBulkOperationsDialog

# Legacy UI modules (for backward compatibility)
# These modules will be deprecated in future versions

__all__ = [
    'components',
    'ManualBulkOperationsDialog'
]