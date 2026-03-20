# ModBusX Test Suite

This directory contains comprehensive tests for the ModBusX Modbus slave simulator.

## Test Files

### `validate_bulk_operations.py`
**Purpose:** Comprehensive automated validation of bulk operations functionality  
**Type:** Automated test suite (no GUI required)  
**Usage:** `python validate_bulk_operations.py`

**Test Coverage:**
- Component import validation
- Register map creation and manipulation
- Register validator functionality
- Combo box data validation
- Bulk operations service testing

**Features:**
- Detailed test results and statistics
- Pass/fail reporting for each test
- No GUI dependencies for CI/CD integration

### `test_connect_dialog.py`
**Purpose:** Hardware-specific testing of connection dialog COM port functionality  
**Type:** Hardware integration test  
**Usage:** `python test_connect_dialog.py`

**Test Coverage:**
- Connect dialog creation
- COM port detection and enumeration
- Protocol switching functionality
- Selected COM port retrieval

**Features:**
- Tests real hardware COM port detection
- Validates protocol switching behavior
- Non-interactive testing (no GUI required)

## Shared Fixtures

### `fixtures/register_maps.py`
Provides standardized test register maps to eliminate code duplication:

- `create_basic_register_map()` - Full register map with all types
- `create_minimal_register_map()` - Minimal map for simple tests
- `create_bulk_test_register_map()` - Optimized for bulk operations testing
- `STANDARD_REGISTER_CONFIGS` - Common register configurations

## Running Tests

### All Validation Tests
```bash
cd tests
python validate_bulk_operations.py
```

### Connection Dialog Test
```bash
cd tests
python test_connect_dialog.py
```

### Expected Output
Validation tests should report:
- ✓ 5/5 tests passed for full functionality
- Detailed statistics for each component
- Clear pass/fail indicators

## Test Architecture

The test suite follows these principles:

1. **No Code Duplication:** Shared fixtures eliminate repeated setup code
2. **Automated Validation:** Core tests run without user interaction
3. **Hardware Integration:** Specific tests for hardware-dependent features
4. **Clear Organization:** Logical separation of test types and purposes

## CI/CD Integration

The validation tests are designed for continuous integration:
- No GUI dependencies for automated testing
- Clear exit codes (0 = success, 1 = failure)
- Comprehensive coverage reporting
- Structured output for parsing

## Maintenance

When adding new tests:
1. Use shared fixtures from `fixtures/register_maps.py`
2. Follow the established naming conventions
3. Include comprehensive docstrings
4. Ensure tests can run independently
5. Update this README with new test descriptions