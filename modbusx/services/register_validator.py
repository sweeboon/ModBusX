"""
Register Validation Service

Pure business logic for ModBus register validation.
"""

from typing import Optional, List, Tuple
from ..models import RegisterMap, RegisterEntry

# Modbus register types with proper PLC (1-based) and Protocol (0-based) addressing
MODBUS_REGISTER_TYPES = {
    'CO': {
        'name': 'Coil',
        'description': '01 (0x01) Read Coils ', 
        'code': 'co', 
        'function_codes': [1], 
        'protocol_address_range': (0, 65535),  # 0-based hex addressing
        'plc_address_range': (1, 99999),       # 1-based, max display 099999
        'plc_display_base': 000000,            # PLC display base for 6-digit format
        'plc_display_range': (1, 99999),       # PLC display format limits
        'data_type': 'bit'
    },
    'DI': {
        'name': 'Discrete Input',
        'description': '02 (0x02) Read Discrete Inputs',
        'code': 'di',
        'function_codes': [2],
        'protocol_address_range': (0, 65535),  # 0-based hex addressing
        'plc_address_range': (1, 99999),       # 1-based, max display 199999
        'plc_display_base': 100000,            # PLC display base for 6-digit format
        'plc_display_range': (100001, 199999), # PLC display format limits
        'data_type': 'bit'
    },
    'HR': {
        'name': 'Holding Register',
        'description': '03 (0x03) Read Holding Registers',
        'code': 'hr',
        'function_codes': [3],
        'protocol_address_range': (0, 65535),  # 0-based hex addressing
        'plc_address_range': (1, 99999),       # 1-based, max display 499999
        'plc_display_base': 400000,            # PLC display base for 6-digit format
        'plc_display_range': (400001, 499999), # PLC display format limits
        'data_type': '16-bit'
    },
    'IR': {
        'name': 'Input Register',
        'description': '04 (0x04) Read Input Registers',
        'code': 'ir',
        'function_codes': [4],
        'protocol_address_range': (0, 65535),  # 0-based hex addressing
        'plc_address_range': (1, 99999),       # 1-based, max display 399999
        'plc_display_base': 300000,            # PLC display base for 6-digit format
        'plc_display_range': (300001, 399999), # PLC display format limits
        'data_type': '16-bit'
    }
}

# Global addressing mode setting - can be persisted via settings
ADDRESS_MODE = 'plc'  # 'plc' or 'protocol'

# Protocol display format when ADDRESS_MODE == 'protocol'
# 'hex' => 0xFFFF style, 'dec' => decimal (protocol, 0-based)
PROTOCOL_DISPLAY_FORMAT = 'hex'

def load_address_mode_from_settings():
    """Load addressing mode from application settings if available."""
    try:
        from PyQt5.QtCore import QSettings
        settings = QSettings('ModBusX', 'Application')
        saved_mode = settings.value('address_mode', 'plc')
        if saved_mode in ('plc', 'protocol'):
            global ADDRESS_MODE
            ADDRESS_MODE = saved_mode
        # Load protocol display format
        display_fmt = settings.value('protocol_display', 'hex')
        if display_fmt in ('hex', 'dec'):
            global PROTOCOL_DISPLAY_FORMAT
            PROTOCOL_DISPLAY_FORMAT = display_fmt
    except ImportError:
        # PyQt5 not available, use default
        pass

def save_address_mode_to_settings():
    """Save current addressing mode to application settings."""
    try:
        from PyQt5.QtCore import QSettings
        settings = QSettings('ModBusX', 'Application')
        settings.setValue('address_mode', ADDRESS_MODE)
        settings.setValue('protocol_display', PROTOCOL_DISPLAY_FORMAT)
    except ImportError:
        # PyQt5 not available, can't save
        pass

# Load settings at module import
load_address_mode_from_settings()

class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass

class RegisterValidator:
    """Handles validation logic for register addresses and values."""
    
    @staticmethod
    def validate_register_type(reg_type: str) -> None:
        """
        Validate register type string.
        
        Args:
            reg_type: Register type ('hr', 'ir', 'co', 'di')
            
        Raises:
            ValidationError: If register type is invalid
        """
        if reg_type not in ('hr', 'ir', 'co', 'di'):
            raise ValidationError(f"Invalid register type: {reg_type}. Must be one of: hr, ir, co, di")
    
    @staticmethod
    def set_address_mode(mode: str):
        """Set the addressing mode to 'plc' or 'protocol'."""
        global ADDRESS_MODE
        if mode not in ('plc', 'protocol'):
            raise ValidationError(f"Invalid address mode: {mode}. Must be 'plc' or 'protocol'")
        ADDRESS_MODE = mode
        save_address_mode_to_settings()
    
    @staticmethod
    def get_address_mode() -> str:
        """Get the current addressing mode."""
        return ADDRESS_MODE

    @staticmethod
    def set_protocol_display_format(fmt: str):
        """Set protocol display format: 'hex' or 'dec'."""
        global PROTOCOL_DISPLAY_FORMAT
        if fmt not in ('hex', 'dec'):
            raise ValidationError("Invalid protocol display format. Use 'hex' or 'dec'.")
        PROTOCOL_DISPLAY_FORMAT = fmt
        save_address_mode_to_settings()

    @staticmethod
    def get_protocol_display_format() -> str:
        """Get current protocol display format ('hex' or 'dec')."""
        return PROTOCOL_DISPLAY_FORMAT
    
    @staticmethod
    def get_address_range(reg_type: str) -> tuple:
        """Get the address range for a register type based on current mode."""
        reg_type_upper = reg_type.upper()
        if reg_type_upper not in MODBUS_REGISTER_TYPES:
            raise ValidationError(f"Unknown register type: {reg_type}")
            
        range_key = f'{ADDRESS_MODE}_address_range'
        return MODBUS_REGISTER_TYPES[reg_type_upper][range_key]
    
    @staticmethod
    def plc_to_display_address(plc_addr: int, reg_type: str) -> str:
        """Convert PLC address to 6-digit display format (e.g., 430000)."""
        reg_type_upper = reg_type.upper()
        if reg_type_upper not in MODBUS_REGISTER_TYPES:
            raise ValidationError(f"Unknown register type: {reg_type}")
        
        base = MODBUS_REGISTER_TYPES[reg_type_upper]['plc_display_base']
        # Convert internal PLC address (1-based) to display format
        display_addr = base + plc_addr
        return f"{display_addr:06d}"
    
    @staticmethod
    def validate_plc_display_address(display_addr: str, reg_type: str) -> bool:
        """Validate PLC display address is within allowed range (max 499999)."""
        try:
            display_int = int(display_addr)
            reg_type_upper = reg_type.upper()
            if reg_type_upper not in MODBUS_REGISTER_TYPES:
                raise ValidationError(f"Unknown register type: {reg_type}")
            
            # Check against PLC display range limits
            display_range = MODBUS_REGISTER_TYPES[reg_type_upper]['plc_display_range']
            if not (display_range[0] <= display_int <= display_range[1]):
                max_addr = display_range[1]
                raise ValidationError(
                    f"PLC address {display_addr} is out of range for {reg_type_upper}. "
                    f"Maximum allowed: {max_addr}"
                )
                
            return True
        except ValueError:
            raise ValidationError(f"Invalid PLC address format: {display_addr}")

    @staticmethod
    def display_to_plc_address(display_addr: str, reg_type: str) -> int:
        """Convert 6-digit display address to PLC address."""
        try:
            display_int = int(display_addr)
            reg_type_upper = reg_type.upper()
            if reg_type_upper not in MODBUS_REGISTER_TYPES:
                raise ValidationError(f"Unknown register type: {reg_type}")
            
            # First validate the display address is within allowed range
            RegisterValidator.validate_plc_display_address(display_addr, reg_type)
            
            base = MODBUS_REGISTER_TYPES[reg_type_upper]['plc_display_base']
            # Convert display format to internal PLC address (1-based)
            plc_addr = display_int - base
            
            # Additional validation of the resulting internal address
            addr_range = RegisterValidator.get_address_range(reg_type)
            if not (addr_range[0] <= plc_addr <= addr_range[1]):
                raise ValidationError(f"Internal address {plc_addr} is out of range for {reg_type_upper}")
                
            return plc_addr
        except ValueError:
            raise ValidationError(f"Invalid address format: {display_addr}")
    
    @staticmethod
    def protocol_to_display_address(protocol_addr: int, reg_type: str) -> str:
        """Convert protocol address to hexadecimal display format (e.g., 0x7530)."""
        # Protocol addresses are 0-based, so internal address 1 = protocol display 0x0000
        display_addr = protocol_addr - 1 if protocol_addr > 0 else 0
        return f"0x{display_addr:04X}"
    
    @staticmethod
    def display_to_protocol_address(display_addr: str, reg_type: str) -> int:
        """Convert hexadecimal display address to protocol address."""
        try:
            if display_addr.startswith('0x') or display_addr.startswith('0X'):
                display_int = int(display_addr, 16)
            else:
                display_int = int(display_addr)
            
            # Convert display format to internal address (1-based)
            # Protocol display 0x0000 = internal address 1
            internal_addr = display_int + 1
            
            # Validate the resulting internal address is in valid range
            addr_range = RegisterValidator.get_address_range(reg_type)
            if not (addr_range[0] <= internal_addr <= addr_range[1]):
                raise ValidationError(f"Address {display_addr} converts to internal {internal_addr} which is out of range for {reg_type.upper()}")
                
            return internal_addr
        except ValueError:
            raise ValidationError(f"Invalid address format: {display_addr}")
    
    @staticmethod
    def address_to_display(addr: int, reg_type: str, mode: str = None) -> str:
        """Convert address to display format based on current or specified mode."""
        if mode is None:
            mode = ADDRESS_MODE
            
        if mode == 'plc':
            return RegisterValidator.plc_to_display_address(addr, reg_type)
        else:
            # Protocol display uses chosen format (hex or decimal)
            if PROTOCOL_DISPLAY_FORMAT == 'dec':
                # protocol decimal is internal(1-based) - 1
                display_addr = max(0, addr - 1)
                return str(display_addr)
            else:
                return RegisterValidator.protocol_to_display_address(addr, reg_type)
    
    @staticmethod
    def display_to_address(display_addr: str, reg_type: str, mode: str = None) -> int:
        """Convert display address to internal address based on current or specified mode."""
        if mode is None:
            mode = ADDRESS_MODE
        
        # Auto-detect the format if not specified or if format doesn't match expected mode
        if display_addr.startswith('0x') or display_addr.startswith('0X'):
            # Hexadecimal format - protocol mode
            return RegisterValidator.display_to_protocol_address(display_addr, reg_type)
        elif len(display_addr) == 6 and display_addr.isdigit():
            # 6-digit format - likely PLC mode
            try:
                return RegisterValidator.display_to_plc_address(display_addr, reg_type)
            except ValidationError:
                # If PLC parsing fails, try as protocol integer
                return RegisterValidator.display_to_protocol_address(display_addr, reg_type)
        else:
            # Use the specified mode
            if mode == 'plc':
                return RegisterValidator.display_to_plc_address(display_addr, reg_type)
            else:
                return RegisterValidator.display_to_protocol_address(display_addr, reg_type)
    
    @staticmethod
    def is_address_valid_for_register_type(addr: int, reg_type: str) -> bool:
        """Check if address is within valid range for register type."""
        reg_type_upper = reg_type.upper()
        if reg_type_upper not in MODBUS_REGISTER_TYPES:
            return False
            
        addr_range = RegisterValidator.get_address_range(reg_type)
        return addr_range[0] <= addr <= addr_range[1]
    
    @staticmethod
    def validate_address_for_register_type(addr: int, reg_type: str) -> bool:
        """Validate address and raise exception if invalid."""
        if not RegisterValidator.is_address_valid_for_register_type(addr, reg_type):
            reg_type_upper = reg_type.upper()
            addr_range = RegisterValidator.get_address_range(reg_type)
            mode_name = "PLC" if ADDRESS_MODE == 'plc' else "Protocol"
            raise ValidationError(
                f"{reg_type_upper} addresses ({mode_name} mode) must be between {addr_range[0]} and {addr_range[1]}"
            )
        
        # Additional validation for PLC addresses: must follow x000n format where n >= 1
        # This ensures addresses start from x0001, not x0000
        # Note: 'addr' parameter is the internal/PLC address (1-based), not the display address
        if ADDRESS_MODE == 'plc':
            reg_type_upper = reg_type.upper()
            
            # For each register type, check if internal address is valid (1-based)
            # The internal address should be >= 1 for all types in PLC mode
            if addr < 1:
                display_format = ""
                if reg_type_upper == 'HR':
                    display_format = " (display format 40001+)"
                elif reg_type_upper == 'IR':
                    display_format = " (display format 30001+)"
                elif reg_type_upper == 'DI':
                    display_format = " (display format 10001+)"
                elif reg_type_upper == 'CO':
                    display_format = " (display format 00001+)"
                
                raise ValidationError(f"{reg_type_upper} addresses must start from 1, not {addr}{display_format}")
        
        return True
    
    @staticmethod
    def suggest_address_for_register_type(reg_type: str, register_map: RegisterMap) -> int:
        """Suggest a valid, unused address for the given register type."""
        reg_type_upper = reg_type.upper()
        addr_range = RegisterValidator.get_address_range(reg_type)
        
        # Get existing addresses for this register type
        reg_dict = getattr(register_map, reg_type.lower(), None)
        if reg_dict is None:
            raise ValidationError(f"Invalid register type: {reg_type}")
        existing_addrs = set(reg_dict.keys())
        
        # Start from the beginning of the range and find first available address
        # Ensure we start from valid PLC addresses (internal address >= 1)
        start_addr = addr_range[0]
        if ADDRESS_MODE == 'plc':
            # In PLC mode, internal addresses start from 1 for all types
            if start_addr < 1:
                start_addr = 1
        
        for addr in range(start_addr, addr_range[1] + 1):
            if addr not in existing_addrs:
                return addr
                
        # If no free address found, return the (adjusted) start of range
        return start_addr
    
    @staticmethod
    def validate_register_value(value: int, reg_type: str) -> bool:
        """Validate register value and raise exception if invalid."""
        # Handle coils/discrete inputs (0 or 1)
        if reg_type in ('co', 'di'):
            if value not in (0, 1):
                raise ValidationError("Coils and discrete inputs must be 0 or 1")
        else:
            # Handle registers (16-bit values)
            if value < 0 or value > 65535:
                raise ValidationError("Register values must be between 0 and 65535")
        return True
    
    @staticmethod
    def validate_register_value_with_conversion(value_str: str, reg_type: str, parent=None) -> Optional[int]:
        """
        Legacy compatibility method: Validate and convert register value string to int.
        
        This method provides backward compatibility with the old UI code.
        Returns the validated value or None if invalid.
        Error handling should be done by the caller to maintain service layer purity.
        """
        try:
            val = int(value_str)
            
            # Use the main validation method
            RegisterValidator.validate_register_value(val, reg_type)
            return val
                    
        except (ValueError, ValidationError):
            # Service layer should not handle UI concerns
            # Let the caller (UI layer) handle error display
            return None
    
    @staticmethod
    def move_register_entry_with_new_address(
        reg_map: RegisterMap, 
        old_type: str, 
        new_type: str, 
        old_addr: int, 
        new_addr: int
    ) -> bool:
        """
        Move register entry from one type to another with potentially new address.
        
        Args:
            reg_map: The register map containing the entry
            old_type: Source register type ('hr', 'ir', 'co', 'di')
            new_type: Target register type  
            old_addr: Original address
            new_addr: New address
            
        Returns:
            True if successful, False if entry not found
        """
        # Get the register entry from old location
        entry = reg_map.get_register(old_type, old_addr)
        if not entry:
            return False
        
        # Remove from old location
        reg_map.remove_register(old_type, old_addr)
        
        # Update entry properties
        entry.reg_type = new_type
        entry.addr = new_addr
        
        # Add to new location
        reg_map.add_register(entry)
        
        return True
    
    @staticmethod
    def move_register_entry(
        reg_map: RegisterMap, 
        old_type: str, 
        new_type: str, 
        addr: int
    ) -> bool:
        """
        Move register entry from one type to another (same address).
        
        Args:
            reg_map: The register map containing the entry
            old_type: Source register type
            new_type: Target register type
            addr: Address (remains the same)
            
        Returns:
            True if successful, False if entry not found
        """
        return RegisterValidator.move_register_entry_with_new_address(
            reg_map, old_type, new_type, addr, addr
        )
    
    @staticmethod
    def validate_address_range(start_addr: int, end_addr: int, reg_type: str) -> bool:
        """Validate an address range."""
        if start_addr > end_addr:
            raise ValidationError("Start address must be less than or equal to end address")
        
        RegisterValidator.validate_address_for_register_type(start_addr, reg_type)
        RegisterValidator.validate_address_for_register_type(end_addr, reg_type)
        return True
    
    @staticmethod
    def check_address_conflicts(
        register_map: RegisterMap, 
        reg_type: str, 
        start_addr: int, 
        size: int
    ) -> List[int]:
        """Check for address conflicts and return list of conflicting addresses."""
        conflicts = []
        reg_dict = getattr(register_map, reg_type, None)
        if reg_dict is None:
            raise ValidationError(f"Invalid register type: {reg_type}")
        
        for i in range(size):
            addr = start_addr + i
            if addr in reg_dict:
                conflicts.append(addr)
        
        return conflicts
    
    @staticmethod
    def find_available_address_range(
        register_map: RegisterMap, 
        reg_type: str, 
        size: int
    ) -> Optional[int]:
        """Find an available address range for the given size."""
        reg_type_upper = reg_type.upper()
        addr_range = RegisterValidator.get_address_range(reg_type)
        reg_dict = getattr(register_map, reg_type, None)
        if reg_dict is None:
            raise ValidationError(f"Invalid register type: {reg_type}")
        
        for start_addr in range(addr_range[0], addr_range[1] - size + 2):
            # Check if this range is available
            available = True
            for i in range(size):
                if (start_addr + i) in reg_dict:
                    available = False
                    break
            
            if available:
                return start_addr
        
        return None
    
    @staticmethod
    def validate_register_entry(entry: RegisterEntry) -> bool:
        """Validate a complete register entry."""
        RegisterValidator.validate_address_for_register_type(entry.addr, entry.reg_type)
        RegisterValidator.validate_register_value(entry.value, entry.reg_type)
        return True
    
    @staticmethod
    def validate_pattern_values(pattern: List[int], reg_type: str) -> bool:
        """Validate pattern values for pattern fill operations."""
        if not pattern:
            raise ValidationError("Pattern cannot be empty")
        
        for value in pattern:
            RegisterValidator.validate_register_value(value, reg_type)
        
        return True
    
    @staticmethod
    def are_types_convertible(old_type: str, new_type: str) -> bool:
        """Check if two register types can be converted between each other."""
        # Allow conversion between 16-bit register types only
        convertible_pairs = [
            ('hr', 'ir'),
            ('ir', 'hr')
        ]
        return (old_type, new_type) in convertible_pairs or (new_type, old_type) in convertible_pairs
    
    @staticmethod
    def validate_type_conversion(old_type: str, new_type: str) -> bool:
        """Validate type conversion and raise exception if invalid."""
        if old_type == new_type:
            raise ValidationError("Old and new types must be different")
        
        if not RegisterValidator.are_types_convertible(old_type, new_type):
            raise ValidationError(f"Cannot convert from {old_type.upper()} to {new_type.upper()}")
        
        return True
    
    @staticmethod
    def get_register_type_info(reg_type: str) -> dict:
        """Get information about a register type."""
        reg_type_upper = reg_type.upper()
        if reg_type_upper not in MODBUS_REGISTER_TYPES:
            raise ValidationError(f"Unknown register type: {reg_type}")
        
        return MODBUS_REGISTER_TYPES[reg_type_upper].copy()
    
    @staticmethod
    def get_all_register_types() -> dict:
        """Get information about all register types."""
        return MODBUS_REGISTER_TYPES.copy()
    
    @staticmethod
    def suggest_contiguous_address_for_register_type(reg_type: str, register_map: RegisterMap, size: int) -> int:
        """Suggest a valid, unused contiguous address block for the given register type and size."""
        reg_type_upper = reg_type.upper()
        addr_range = RegisterValidator.get_address_range(reg_type)
        
        # Get existing addresses for this register type
        reg_dict = getattr(register_map, reg_type.lower(), None)
        if reg_dict is None:
            raise ValidationError(f"Invalid register type: {reg_type}")
        existing_addrs = set(reg_dict.keys())
        
        # Start from the beginning of the range and find first available contiguous block
        start_addr = addr_range[0]
        if ADDRESS_MODE == 'plc':
            # In PLC mode, internal addresses start from 1 for all types
            if start_addr < 1:
                start_addr = 1
        
        max_addr = addr_range[1]
        
        # Search for a contiguous block of addresses
        for addr in range(start_addr, max_addr - size + 2):
            # Check if we have 'size' contiguous addresses available starting from 'addr'
            block_available = True
            for offset in range(size):
                if (addr + offset) in existing_addrs or (addr + offset) > max_addr:
                    block_available = False
                    break
            
            if block_available:
                return addr
        
        # If no contiguous block found, raise an error
        raise ValidationError(f"Cannot find {size} contiguous addresses for register type {reg_type_upper}")
    
    @staticmethod  
    def suggest_adjusted_address_for_group(reg_type: str, register_map: RegisterMap, preferred_start: int, size: int) -> int:
        """
        Suggest an adjusted address for a register group, trying to stay close to the preferred start.
        First tries the preferred address, then searches for nearest available contiguous block.
        """
        # First check if the preferred range is available
        conflicts = []
        reg_dict = getattr(register_map, reg_type.lower(), {})
        for addr in range(preferred_start, preferred_start + size):
            if addr in reg_dict:
                conflicts.append(addr)
        
        if not conflicts:
            return preferred_start  # Preferred range is available
        
        # Search for closest available contiguous block
        addr_range = RegisterValidator.get_address_range(reg_type)
        max_addr = addr_range[1]
        
        # Try addresses after the preferred start first
        best_distance = float('inf')
        best_address = None
        
        # Search in both directions from preferred start
        max_search_range = min(1000, max_addr - addr_range[0] + 1)  # Limit search to reasonable range
        
        for offset in range(max_search_range):
            # Try after preferred start
            candidate = preferred_start + offset
            if candidate <= max_addr - size + 1:
                if RegisterValidator._is_contiguous_block_available(reg_type, register_map, candidate, size):
                    distance = abs(candidate - preferred_start)
                    if distance < best_distance:
                        best_distance = distance
                        best_address = candidate
                        if distance == 0:  # Found exact match
                            break
            
            # Try before preferred start (only if offset > 0 to avoid duplicate check)
            if offset > 0:
                candidate = preferred_start - offset
                if candidate >= addr_range[0]:
                    if RegisterValidator._is_contiguous_block_available(reg_type, register_map, candidate, size):
                        distance = abs(candidate - preferred_start)
                        if distance < best_distance:
                            best_distance = distance
                            best_address = candidate
        
        if best_address is not None:
            return best_address
        
        # Fallback: use the general contiguous address finder
        return RegisterValidator.suggest_contiguous_address_for_register_type(reg_type, register_map, size)
    
    @staticmethod
    def _is_contiguous_block_available(reg_type: str, register_map: RegisterMap, start_addr: int, size: int) -> bool:
        """Check if a contiguous block of addresses is available."""
        addr_range = RegisterValidator.get_address_range(reg_type)
        if start_addr + size - 1 > addr_range[1]:
            return False
            
        reg_dict = getattr(register_map, reg_type.lower(), {})
        for addr in range(start_addr, start_addr + size):
            if addr in reg_dict:
                return False
        return True
