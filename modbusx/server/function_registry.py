"""
Function Handler Registry

Centralized registry for all Modbus function handlers.
Eliminates the need for large if-elif chains in protocol handlers.
"""

from typing import Optional, List
from .function_handlers import (
    BaseFunctionHandler, ModbusRequest, ModbusResponse,
    ReadCoilsHandler, ReadDiscreteInputsHandler, 
    ReadHoldingRegistersHandler, ReadInputRegistersHandler
)


class FunctionHandlerRegistry:
    """Registry for all Modbus function handlers"""
    
    def __init__(self, logger):
        self.logger = logger
        self._handlers = {
            0x01: ReadCoilsHandler(logger),           # Read Coils
            0x02: ReadDiscreteInputsHandler(logger),  # Read Discrete Inputs  
            0x03: ReadHoldingRegistersHandler(logger), # Read Holding Registers
            0x04: ReadInputRegistersHandler(logger)   # Read Input Registers
        }
        
    def get_handler(self, function_code: int) -> Optional[BaseFunctionHandler]:
        """Get handler for specific function code"""
        return self._handlers.get(function_code)
        
    def handle_request(self, request: ModbusRequest, slave_context) -> Optional[ModbusResponse]:
        """Handle request using appropriate function handler"""
        handler = self.get_handler(request.function_code)
        if not handler:
            self.logger.warning(f"Unsupported function code: 0x{request.function_code:02X}")
            return None
            
        return handler.handle_request(request, slave_context)
        
    def get_supported_functions(self) -> List[int]:
        """Get list of supported function codes"""
        return list(self._handlers.keys())
        
    def is_supported(self, function_code: int) -> bool:
        """Check if function code is supported"""
        return function_code in self._handlers