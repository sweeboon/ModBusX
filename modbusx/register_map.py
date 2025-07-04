# modbusx/register_map.py

"""
Utility/data handling for register maps.
For now, supports dummy HR/IR patterns; expand as needed!
"""

def default_hr_block(value: int, size: int = 10):
    return [value] * size

def default_ir_block(value: int, size: int = 10):
    return [value] * size