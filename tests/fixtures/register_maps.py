"""
Shared register map fixtures for testing.

Provides standardized test register maps to eliminate code duplication
across test files.
"""

import sys
import os

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modbusx.models.register_map import RegisterMap


def create_basic_register_map():
    """Create a basic register map with all register types for testing."""
    register_map = RegisterMap()
    register_map.add_block('hr', 40001, 10, 0)    # Holding registers
    register_map.add_block('ir', 30001, 5, 100)   # Input registers
    register_map.add_block('co', 1, 8, 0)         # Coils
    register_map.add_block('di', 10001, 8, 1)     # Discrete inputs
    return register_map


def create_minimal_register_map():
    """Create a minimal register map for simple tests."""
    register_map = RegisterMap()
    register_map.add_block('hr', 40001, 5, 10)
    return register_map


def create_bulk_test_register_map():
    """Create a register map specifically for bulk operations testing."""
    register_map = RegisterMap()
    register_map.add_block('hr', 40001, 10, 0)
    register_map.add_block('ir', 30001, 5, 100)
    return register_map


# Commonly used test data
STANDARD_REGISTER_CONFIGS = {
    'holding_registers': {'reg_type': 'hr', 'start_addr': 40001, 'size': 10, 'default_value': 0},
    'input_registers': {'reg_type': 'ir', 'start_addr': 30001, 'size': 5, 'default_value': 100},
    'coils': {'reg_type': 'co', 'start_addr': 1, 'size': 8, 'default_value': 0},
    'discrete_inputs': {'reg_type': 'di', 'start_addr': 10001, 'size': 8, 'default_value': 1}
}