# modbusx/register_map.py

"""
Utility/data handling for register maps.
"""

def extract_register_values(slave, reg_type_name):
    """Extracts all register values of a certain type (e.g. 'Holding Register') from all register groups of a slave.
    Returns a list of (address, value) sorted by address.
    """
    values = []
    for reg_group in slave.get('register_groups', []):
        for addr, info in reg_group['registers'].items():
            if info['type'] == reg_type_name:
                values.append((addr, info['value']))
    values.sort()  # order by register address
    return values

def dense_register_list(entries):
    """Given a list of (addr, value), produce a contiguous list covering the full range, filling unused with 0."""
    if not entries:
        return []
    # Only keep 2-tuples
    entries = [t for t in entries if isinstance(t, (tuple, list)) and len(t) == 2]
    if not entries:
        return []
    addresses, vals = zip(*entries)
    addr_min, addr_max = min(addresses), max(addresses)
    addr_to_val = dict(entries)
    return [addr_to_val.get(a, 0) for a in range(addr_min, addr_max + 1)]

def default_register_block(register_type: str, start_addr: int, size: int, start_value: int = 0):
    """
    Returns a register group dict, mapping address -> info dict.
    Args:
        register_type: 'HR', 'IR', 'DI', 'CO', etc.
        start_addr:    starting modbus address (eg. 40001 for HR, 30001 for IR)
        size:          number of registers
        start_value:   initial value for all registers (int)
    Returns:
        dict: {address: {'type', 'alias', 'value', 'comment'}}
    """
    result = {}
    for i in range(size):
        addr = start_addr + i
        result[addr] = {
            'type': register_type,
            'alias': '',
            'value': start_value,
            'comment': ''
        }
    return result

def default_hr_block(start_addr: int = 40001, size: int = 10, value: int = 0):
    return default_register_block('hr', start_addr, size, value)

def default_ir_block(start_addr: int = 30001, size: int = 10, value: int = 0):
    return default_register_block('ir', start_addr, size, value)

def default_di_block(start_addr: int = 10001, size: int = 10, value: int = 0):
    return default_register_block('di', start_addr, size, value)

def default_co_block(start_addr: int = 1, size: int = 10, value: int = 0):
    return default_register_block('co', start_addr, size, value)