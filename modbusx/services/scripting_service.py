"""
Top-level scripting service shim under Services, matching existing flat layout.
"""

from .scripting.service import ScriptingService, get_scripting_service  # re-export

__all__ = ["ScriptingService", "get_scripting_service"]

