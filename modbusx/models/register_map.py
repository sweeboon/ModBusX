"""
Register Map Model

Pure data model for ModBus register storage and access.
"""

from typing import Dict, List, Optional, Tuple
from .register_entry import RegisterEntry
from ..logger import get_logger

class RegisterMap:
    """
    Holds all registers for ONE slave (unit id).
    Each type is a dict: addr -> RegisterEntry.
    """
    
    def __init__(self):
        self.hr: Dict[int, RegisterEntry] = {}  # Holding Registers
        self.ir: Dict[int, RegisterEntry] = {}  # Input Registers  
        self.di: Dict[int, RegisterEntry] = {}  # Discrete Inputs
        self.co: Dict[int, RegisterEntry] = {}  # Coils
        self.logger = get_logger("RegisterMap")

    def add_register(self, entry: RegisterEntry) -> None:
        """Add a single register entry."""
        reg_dict = getattr(self, entry.reg_type)
        reg_dict[entry.addr] = entry

    def normalize_addresses(self):
        """Normalize addresses to ensure consistency with current addressing mode."""
        from ..services.register_validator import RegisterValidator, MODBUS_REGISTER_TYPES
        
        current_mode = RegisterValidator.get_address_mode()
        
        for reg_type_upper, reg_dict in [('CO', self.co), ('DI', self.di), ('IR', self.ir), ('HR', self.hr)]:
            reg_type = reg_type_upper.lower()
            
            # Get current address range for this mode
            addr_range = RegisterValidator.get_address_range(reg_type)
            
            # Find addresses that are outside current mode's range (indicating mixed addressing)
            mixed_addresses = []
            for addr in list(reg_dict.keys()):
                if not (addr_range[0] <= addr <= addr_range[1]):
                    mixed_addresses.append(addr)
            
            # Remove mixed addresses (they'll be recreated properly)
            for addr in mixed_addresses:
                if addr in reg_dict:
                    self.logger.warning("Removing mixed address %s %d (outside range %d-%d)", 
                                       reg_type_upper, addr, addr_range[0], addr_range[1])
                    del reg_dict[addr]
    
    def add_block(self, reg_type: str, start_addr: int, size: int, default_value: int = 0) -> None:
        """Add a block of registers."""
        from ..services.register_validator import RegisterValidator
        RegisterValidator.validate_register_type(reg_type)
        
        reg_dict = getattr(self, reg_type)
        for i in range(size):
            addr = start_addr + i
            if addr not in reg_dict:
                entry = RegisterEntry(addr=addr, reg_type=reg_type, value=default_value)
                reg_dict[addr] = entry

    def remove_register(self, reg_type: str, addr: int) -> bool:
        """Remove a register. Returns True if removed, False if not found."""
        reg_dict = getattr(self, reg_type)
        if addr in reg_dict:
            del reg_dict[addr]
            return True
        return False

    def get_register(self, reg_type: str, addr: int) -> Optional[RegisterEntry]:
        """Get a register entry by type and address."""
        reg_dict = getattr(self, reg_type)
        return reg_dict.get(addr)

    def get_all_registers(self, reg_type: str) -> List[RegisterEntry]:
        """Get all registers of a specific type."""
        return list(getattr(self, reg_type).values())

    def get_register_range(self, reg_type: str, start_addr: int, end_addr: int) -> List[RegisterEntry]:
        """Get registers in a specific address range."""
        reg_dict = getattr(self, reg_type)
        result = []
        for addr in range(start_addr, end_addr + 1):
            if addr in reg_dict:
                result.append(reg_dict[addr])
        return result

    def update_register_value(self, reg_type: str, addr: int, value: int) -> bool:
        """Update register value. Returns True if updated, False if not found."""
        reg_dict = getattr(self, reg_type)
        if addr in reg_dict:
            reg_dict[addr].value = value
            return True
        return False

    def get_address_range(self, reg_type: str) -> Optional[Tuple[int, int]]:
        """Get min and max addresses for a register type. Returns None if empty."""
        reg_dict = getattr(self, reg_type)
        if not reg_dict:
            return None
        addresses = list(reg_dict.keys())
        return (min(addresses), max(addresses))

    def as_pymodbus_array(self, reg_type: str) -> Tuple[int, List[int]]:
        """
        Returns an array of values for pymodbus DataBlock, covering full contiguous address range.
        Empty registers are filled with 0.
        Returns: (start_address, values_list)
        """
        reg_dict = getattr(self, reg_type)
        if not reg_dict:
            return (0, [0])
        
        addresses = sorted(reg_dict.keys())
        addr_min, addr_max = addresses[0], addresses[-1]
        
        values = []
        for addr in range(addr_min, addr_max + 1):
            if addr in reg_dict:
                values.append(reg_dict[addr].value)
            else:
                values.append(0)
        
        return (0, values)

    def get_statistics(self) -> Dict[str, int]:
        """Get register count statistics."""
        return {
            'hr_count': len(self.hr),
            'ir_count': len(self.ir),
            'di_count': len(self.di),
            'co_count': len(self.co),
            'total_count': len(self.hr) + len(self.ir) + len(self.di) + len(self.co)
        }

    def clear_all(self) -> None:
        """Clear all registers."""
        self.hr.clear()
        self.ir.clear()
        self.di.clear()
        self.co.clear()

    def clear_type(self, reg_type: str) -> None:
        """Clear all registers of a specific type."""
        reg_dict = getattr(self, reg_type)
        reg_dict.clear()

    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'hr': {addr: entry.to_dict() for addr, entry in self.hr.items()},
            'ir': {addr: entry.to_dict() for addr, entry in self.ir.items()},
            'di': {addr: entry.to_dict() for addr, entry in self.di.items()},
            'co': {addr: entry.to_dict() for addr, entry in self.co.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'RegisterMap':
        """Create from dictionary representation."""
        register_map = cls()
        
        for reg_type in ('hr', 'ir', 'di', 'co'):
            if reg_type in data:
                reg_dict = getattr(register_map, reg_type)
                for addr_str, entry_data in data[reg_type].items():
                    addr = int(addr_str)
                    entry = RegisterEntry.from_dict(entry_data)
                    reg_dict[addr] = entry
        
        return register_map
    
    # Legacy compatibility methods
    def find_entry_by_addr(self, reg_type: str, modbus_addr: int) -> Optional[RegisterEntry]:
        """Find entry by address (legacy compatibility)."""
        return self.get_register(reg_type, modbus_addr)
    
    def all_entries(self, reg_type: str) -> List[RegisterEntry]:
        """Get all entries (legacy compatibility)."""
        return self.get_all_registers(reg_type)
    
    def to_meta_list(self):
        """Returns a summary of all registers (for display/debug)."""
        rows = []
        for t in ['co', 'di', 'ir', 'hr']:
            for e in self.all_entries(t):
                rows.append((t, e.addr, e.alias, e.value, e.comment, e.units))
        return rows


# --- Helper functions to quickly create blocks (legacy compatibility) ---
def create_default_block(reg_type: str, start_addr: int, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    """Create a default register block for any register type."""
    dct = {}
    for i in range(size):
        addr = start_addr + i
        dct[addr] = RegisterEntry(addr, reg_type, value=value)
    return dct

def default_hr_block(start_addr: int = 40001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    return create_default_block('hr', start_addr, size, value)

def default_ir_block(start_addr: int = 30001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    return create_default_block('ir', start_addr, size, value)

def default_di_block(start_addr: int = 10001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    return create_default_block('di', start_addr, size, value)

def default_co_block(start_addr: int = 1, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    return create_default_block('co', start_addr, size, value)