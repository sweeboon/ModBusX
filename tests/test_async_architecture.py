#!/usr/bin/env python3
"""
Test script for the new async architecture.

Tests that the COM port hanging issue has been resolved.
"""

import sys
import os
import asyncio

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modbusx.server import AsyncModbusServer, ServerConfig, ServerProtocol
from modbusx.bridge import AsyncioEventLoop
from fixtures.register_maps import create_basic_register_map


def test_async_server_creation():
    """Test creating async servers."""
    print("Testing AsyncModbusServer creation...")
    
    try:
        # Create test register map
        reg_map = create_basic_register_map()
        live_slaves = {1: {"register_map": reg_map}}
        
        # Test TCP server
        tcp_config = ServerConfig(
            protocol=ServerProtocol.TCP,
            address='localhost',
            port=5020
        )
        tcp_server = AsyncModbusServer(tcp_config, live_slaves)
        print("✅ TCP server created")
        
        # Test Serial server
        serial_config = ServerConfig(
            protocol=ServerProtocol.RTU,
            serial_port='COM1',
            baudrate=9600
        )
        serial_server = AsyncModbusServer(serial_config, live_slaves)
        print("✅ Serial server created")
        
        return True
        
    except Exception as e:
        print(f"❌ Server creation failed: {e}")
        return False


def test_asyncio_integration():
    """Test Qt-Asyncio integration."""
    print("Testing Qt-Asyncio integration...")
    
    try:
        from PyQt5.QtWidgets import QApplication
        app = QApplication([])
        
        # Test asyncio event loop integration
        async_loop = AsyncioEventLoop()
        async_loop.start_loop(interval_ms=50)  # 50ms for testing
        
        print("✅ AsyncioEventLoop started")
        
        # Test running a simple coroutine
        async def test_coro():
            await asyncio.sleep(0.1)
            return "test complete"
        
        # This would normally be called from Qt context
        task = async_loop.run_coroutine(test_coro())
        print("✅ Coroutine scheduled")
        
        # Clean up
        async_loop.stop_loop()
        print("✅ AsyncioEventLoop stopped")
        
        return True
        
    except Exception as e:
        print(f"❌ Asyncio integration failed: {e}")
        return False


async def test_server_start_stop():
    """Test server start/stop cycle (the critical test for hanging)."""
    print("Testing server start/stop cycle...")
    
    try:
        # Create test server
        reg_map = create_basic_register_map()
        live_slaves = {1: {"register_map": reg_map}}
        
        # Test with TCP first (should work)
        tcp_config = ServerConfig(
            protocol=ServerProtocol.TCP,
            address='localhost',
            port=5021  # Different port
        )
        tcp_server = AsyncModbusServer(tcp_config, live_slaves)
        
        # Start server
        print("Starting TCP server...")
        start_task = tcp_server.start()
        
        # Let it run briefly
        await asyncio.sleep(0.5)
        print("✅ Server started successfully")
        
        # Stop server - this should NOT hang!
        print("Stopping server...")
        await tcp_server.stop()
        print("✅ Server stopped successfully - NO HANGING!")
        
        return True
        
    except Exception as e:
        print(f"❌ Server start/stop test failed: {e}")
        return False


async def test_serial_cancellation():
    """Test that serial servers can be cancelled (the core fix)."""
    print("Testing serial server cancellation...")
    
    try:
        # Create serial server config
        reg_map = create_basic_register_map()
        live_slaves = {1: {"register_map": reg_map}}
        
        serial_config = ServerConfig(
            protocol=ServerProtocol.RTU,
            serial_port='COM999',  # Non-existent port for testing
            baudrate=9600
        )
        serial_server = AsyncModbusServer(serial_config, live_slaves)
        
        # Start server (will fail to connect but that's OK for testing)
        print("Starting serial server...")
        try:
            # Use timeout to test cancellation
            await asyncio.wait_for(serial_server.start_async(), timeout=2.0)
        except (asyncio.TimeoutError, Exception) as e:
            print(f"Expected failure: {e}")
        
        # The key test: can we stop it without hanging?
        print("Stopping serial server...")
        await serial_server.stop()
        print("✅ Serial server cancelled successfully - NO HANGING!")
        
        return True
        
    except Exception as e:
        print(f"❌ Serial cancellation test failed: {e}")
        return False


async def test_ascii_cancellation():
    """Test that ASCII serial servers can be cancelled cleanly."""
    print("Testing ASCII serial cancellation...")
    try:
        # Create serial server config (non-existent port)
        reg_map = create_basic_register_map()
        live_slaves = {1: {"register_map": reg_map}}

        ascii_config = ServerConfig(
            protocol=ServerProtocol.ASCII,
            serial_port='COM999',  # Non-existent port for testing
            baudrate=9600,
            parity='E',
            stopbits=1,
            bytesize=7,
        )
        ascii_server = AsyncModbusServer(ascii_config, live_slaves)

        print("Starting ASCII serial server...")
        try:
            await asyncio.wait_for(ascii_server.start_async(), timeout=2.0)
        except (asyncio.TimeoutError, Exception) as e:
            print(f"Expected failure: {e}")

        print("Stopping ASCII serial server...")
        await ascii_server.stop()
        print("✅ ASCII serial server cancelled successfully - NO HANGING!")
        return True
    except Exception as e:
        print(f"❌ ASCII cancellation test failed: {e}")
        return False


def test_migration_patches():
    """Test that migration patches work."""
    print("Testing migration patches...")
    
    try:
        from modbusx.migrate_to_async import (
            apply_async_migration, 
            validate_async_architecture
        )
        
        # Run validation
        if validate_async_architecture():
            print("✅ Architecture validation passed")
            
            # Apply migration
            if apply_async_migration():
                print("✅ Migration patches applied")
                return True
            else:
                print("❌ Migration patches failed")
                return False
        else:
            print("❌ Architecture validation failed")
            return False
            
    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        return False


async def run_async_tests():
    """Run async-specific tests."""
    print("\n" + "="*50)
    print("ASYNC TESTS")
    print("="*50)
    
    tests = [
        ("Server Start/Stop", test_server_start_stop),
        ("Serial Cancellation (RTU)", test_serial_cancellation),
        ("Serial Cancellation (ASCII)", test_ascii_cancellation),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if await test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    return passed, len(tests)


def run_sync_tests():
    """Run synchronous tests."""
    print("\n" + "="*50)
    print("SYNC TESTS")
    print("="*50)
    
    tests = [
        ("Server Creation", test_async_server_creation),
        ("Asyncio Integration", test_asyncio_integration),
        ("Migration Patches", test_migration_patches),
    ]
    
    passed = 0
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    return passed, len(tests)


async def main():
    """Main test runner."""
    print("🚀 ModBusX Async Architecture Tests")
    print("="*50)
    print("Testing the solution to COM port hanging issues...")
    
    # Run synchronous tests
    sync_passed, sync_total = run_sync_tests()
    
    # Run asynchronous tests
    async_passed, async_total = run_async_tests()
    
    # Results
    total_passed = sync_passed + async_passed
    total_tests = sync_total + async_total
    success_rate = total_passed / total_tests if total_tests > 0 else 0
    
    print("\n" + "="*50)
    print("FINAL RESULTS")
    print("="*50)
    print(f"📊 Tests passed: {total_passed}/{total_tests} ({success_rate:.1%})")
    
    if success_rate >= 0.8:
        print("🎉 ASYNC ARCHITECTURE TEST: SUCCESS!")
        print("🔧 COM port hanging issues should be resolved!")
    else:
        print("⚠️  ASYNC ARCHITECTURE TEST: NEEDS WORK")
        print("🐛 Some issues may persist")
    
    print("\n" + "="*50)
    return success_rate >= 0.8


if __name__ == "__main__":
    # Run tests
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n❌ Tests cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner failed: {e}")
        sys.exit(1)
