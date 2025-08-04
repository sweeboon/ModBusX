# modbusx/register_map.py

"""
Utility/data handling for register maps: full-featured models for all Modbus types
"""

from typing import Dict, List

class RegisterEntry():
    """Represents a single Modbus register/coils, with metadata."""
    def __init__(
        self, addr: int, reg_type: str, value: int = 0, 
        alias: str = '', comment: str = '', units: str = ''
    ):
        self.addr = addr           # e.g. 40001 (for HR), 1 (for CO)
        self.reg_type = reg_type   # "hr", "ir", "co", "di"
        self.value = value
        self.alias = alias
        self.comment = comment
        self.units = units

class RegisterMap():
    """
    Holds all registers for ONE slave (unit id).
    Each type is a dict: addr -> RegisterEntry.
    """
    def __init__(self):
        self.hr = {}  # type: Dict[int, RegisterEntry]
        self.ir = {}
        self.di = {}
        self.co = {}

    def add_block(self, reg_type: str, start_addr: int, size: int, default_value: int = 0):
        t = reg_type.lower()
        if t not in ('hr', 'ir', 'co', 'di'):
            raise ValueError(f"Bad reg_type: {reg_type}")
        dct = getattr(self, t)
        for i in range(size):
            addr = start_addr + i
            # If already exists, skip/overwrite? For now, skip
            if addr not in dct:
                dct[addr] = RegisterEntry(addr, t, default_value)
    
    def as_pymodbus_array(self, reg_type: str) -> List[int]:
        """
        Returns an array of values (for pymodbus DataBlock), for selected type, covering full contiguous address range.
        Empty registers are filled with 0.
        """
        t = reg_type.lower()
        dct = getattr(self, t)
        addresses = sorted(dct.keys())
        if not addresses:
            return (0, [0])
        addr_min, addr_max = addresses[0], addresses[-1]
        arr = []
        for a in range(addr_min, addr_max + 1):
            arr.append(dct.get(a, RegisterEntry(a, t)).value)
        return (0, arr)

    def find_entry_by_addr(self, reg_type: str, modbus_addr: int) -> RegisterEntry:
        # Returns RegisterEntry, or None if not present
        t = reg_type.lower()
        return getattr(self, t).get(modbus_addr, None)

    def all_entries(self, reg_type: str) -> List[RegisterEntry]:
        return list(getattr(self, reg_type.lower()).values())

    def to_meta_list(self):
        # Returns a summary of all registers (for display/debug)
        rows = []
        for t in ['co', 'di', 'ir', 'hr']:
            for e in self.all_entries(t):
                rows.append((t, e.addr, e.alias, e.value, e.comment, e.units))
        return rows

# --- Helper functions to quickly create blocks ---
def default_hr_block(start_addr: int = 40001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    dct = {}
    for i in range(size):
        addr = start_addr + i
        dct[addr] = RegisterEntry(addr, 'hr', value=value)
    return dct

def default_ir_block(start_addr: int = 30001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    dct = {}
    for i in range(size):
        addr = start_addr + i
        dct[addr] = RegisterEntry(addr, 'ir', value=value)
    return dct

def default_di_block(start_addr: int = 10001, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    dct = {}
    for i in range(size):
        addr = start_addr + i
        dct[addr] = RegisterEntry(addr, 'di', value=value)
    return dct

def default_co_block(start_addr: int = 1, size: int = 10, value: int = 0) -> Dict[int, RegisterEntry]:
    dct = {}
    for i in range(size):
        addr = start_addr + i
        dct[addr] = RegisterEntry(addr, 'co', value=value)
    return dct