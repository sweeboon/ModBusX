"""
Modbus Function Handlers

Eliminates duplicate code for handling different Modbus function codes
by extracting common patterns into reusable handlers.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class ModbusRequest:
    """Common request data structure for all Modbus functions"""
    unit_id: int
    function_code: int
    start_addr: int
    quantity: int
    raw_data: bytes


@dataclass
class ModbusResponse:
    """Common response data structure for all Modbus functions"""
    unit_id: int
    function_code: int
    data: bytes
    needs_crc: bool = True


class BaseFunctionHandler(ABC):
    """Base class for Modbus function handlers - eliminates duplicate logic"""
    
    def __init__(self, logger):
        self.logger = logger
        
    @abstractmethod
    def get_register_type_code(self) -> int:
        """Return the register type code for slave_context.getValues()"""
        pass
        
    @abstractmethod
    def get_function_name(self) -> str:
        """Return human-readable function name for logging"""
        pass
        
    @abstractmethod
    def build_response_data(self, values: List[int], quantity: int) -> bytes:
        """Build the function-specific response data (registers vs bits)"""
        pass
    
    def handle_request(self, request: ModbusRequest, slave_context) -> Optional[ModbusResponse]:
        """Common request handling logic - eliminates duplication"""
        self.logger.debug(f"{self.get_function_name()}: start={request.start_addr}, count={request.quantity}")
        
        try:
            # Common value reading logic (was duplicated 8 times)
            values = []
            for i in range(request.quantity):
                addr = request.start_addr + i
                value = slave_context.getValues(self.get_register_type_code(), addr, 1)[0]
                values.append(value)
            
            # Function-specific response building
            response_data = self.build_response_data(values, request.quantity)
            
            return ModbusResponse(
                unit_id=request.unit_id,
                function_code=request.function_code,
                data=response_data
            )
            
        except Exception as e:
            self.logger.error(f"Error in {self.get_function_name()}: {e}")
            return None


class ReadCoilsHandler(BaseFunctionHandler):
    """Handler for Read Coils (0x01) - bit-packed response"""
    
    def get_register_type_code(self) -> int:
        return 1  # Coils
        
    def get_function_name(self) -> str:
        return "Read Coils"
        
    def build_response_data(self, values: List[int], quantity: int) -> bytes:
        """Build bit-packed response for coils"""
        byte_count = (quantity + 7) // 8  # Pack 8 bits per byte
        response = bytearray([byte_count])
        
        # Pack bits into bytes (was duplicated in TCP and Serial)
        for byte_idx in range(byte_count):
            byte_value = 0
            for bit_idx in range(8):
                value_idx = byte_idx * 8 + bit_idx
                if value_idx < len(values) and values[value_idx]:
                    byte_value |= (1 << bit_idx)
            response.append(byte_value)
            
        return bytes(response)


class ReadDiscreteInputsHandler(BaseFunctionHandler):
    """Handler for Read Discrete Inputs (0x02) - bit-packed response"""
    
    def get_register_type_code(self) -> int:
        return 2  # Discrete inputs
        
    def get_function_name(self) -> str:
        return "Read Discrete Inputs"
        
    def build_response_data(self, values: List[int], quantity: int) -> bytes:
        """Build bit-packed response for discrete inputs"""
        byte_count = (quantity + 7) // 8
        response = bytearray([byte_count])
        
        # Same bit-packing logic as coils
        for byte_idx in range(byte_count):
            byte_value = 0
            for bit_idx in range(8):
                value_idx = byte_idx * 8 + bit_idx
                if value_idx < len(values) and values[value_idx]:
                    byte_value |= (1 << bit_idx)
            response.append(byte_value)
            
        return bytes(response)


class ReadHoldingRegistersHandler(BaseFunctionHandler):
    """Handler for Read Holding Registers (0x03) - word-packed response"""
    
    def get_register_type_code(self) -> int:
        return 3  # Holding registers
        
    def get_function_name(self) -> str:
        return "Read Holding Registers"
        
    def build_response_data(self, values: List[int], quantity: int) -> bytes:
        """Build word-packed response for holding registers"""
        byte_count = quantity * 2
        response = bytearray([byte_count])
        
        # Pack 16-bit values (was duplicated in TCP and Serial)
        for value in values:
            response.append((value >> 8) & 0xFF)  # High byte
            response.append(value & 0xFF)         # Low byte
            
        return bytes(response)


class ReadInputRegistersHandler(BaseFunctionHandler):
    """Handler for Read Input Registers (0x04) - word-packed response"""
    
    def get_register_type_code(self) -> int:
        return 4  # Input registers
        
    def get_function_name(self) -> str:
        return "Read Input Registers"
        
    def build_response_data(self, values: List[int], quantity: int) -> bytes:
        """Build word-packed response for input registers"""
        byte_count = quantity * 2
        response = bytearray([byte_count])
        
        # Same word-packing logic as holding registers
        for value in values:
            response.append((value >> 8) & 0xFF)
            response.append(value & 0xFF)
            
        return bytes(response)