"""
Qt-Asyncio Integration Bridge

Provides a bridge between Qt's event system and asyncio to run async code
from the Qt main thread without blocking the UI.
"""

import asyncio
from typing import Optional, Callable, Any, Coroutine, Dict
from PyQt5.QtCore import QObject, QTimer, pyqtSignal, QThread
from PyQt5.QtWidgets import QApplication
from modbusx.logger import global_logger


class AsyncioEventLoop(QObject):
    """Integrates asyncio event loop with Qt event system."""
    
    # Signals for communicating with Qt from async code
    status_update = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._process_events)
        self.running = False
        
    def start_loop(self, interval_ms: int = 10):
        """Start the asyncio event loop integration."""
        if self.running:
            global_logger.log("AsyncioEventLoop already running")
            return
            
        try:
            # Create new event loop if none exists
            try:
                self.loop = asyncio.get_event_loop()
                if self.loop.is_closed():
                    raise RuntimeError("Event loop is closed")
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
                
            self.running = True
            self.timer.start(interval_ms)  # Process events every interval_ms milliseconds
            global_logger.log(f"AsyncioEventLoop started with {interval_ms}ms interval")
            
        except Exception as e:
            global_logger.log(f"Failed to start AsyncioEventLoop: {e}")
            self.error_occurred.emit(f"Failed to start async loop: {e}")
    
    def stop_loop(self):
        """Stop the asyncio event loop integration."""
        if not self.running:
            return
            
        self.timer.stop()
        self.running = False
        
        if self.loop and not self.loop.is_closed():
            # Cancel all pending tasks
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()
                
            # Close the loop
            try:
                self.loop.close()
            except Exception as e:
                global_logger.log(f"Error closing asyncio loop: {e}")
                
        global_logger.log("AsyncioEventLoop stopped")
    
    def _process_events(self):
        """Process asyncio events from Qt timer."""
        if not self.loop or self.loop.is_closed():
            return
            
        try:
            # Process ready callbacks without stopping/starting the loop
            # Use a different approach that doesn't interfere with running tasks
            if not self.loop.is_running():
                # If loop is not running, run pending tasks with minimal sleep
                try:
                    self.loop.run_until_complete(asyncio.sleep(0))
                except RuntimeError:
                    # Loop might be running in different context, ignore
                    pass
        except Exception as e:
            # Don't log every minor exception to avoid spam
            pass
    
    def run_coroutine(self, coro: Coroutine) -> asyncio.Task:
        """Schedule a coroutine to run on the asyncio loop."""
        if not self.loop or self.loop.is_closed():
            raise RuntimeError("AsyncioEventLoop not running")
            
        return self.loop.create_task(coro)
    
    def call_soon_threadsafe(self, callback: Callable, *args):
        """Call a function on the asyncio loop thread-safely."""
        if not self.loop or self.loop.is_closed():
            raise RuntimeError("AsyncioEventLoop not running")
            
        self.loop.call_soon_threadsafe(callback, *args)


class AsyncServerManager(QObject):
    """Unified AsyncServerManager with backward compatibility for legacy UI code."""
    
    # Modern signals (primary interface)
    server_started = pyqtSignal(str, str)  # server_key, description
    server_stopped = pyqtSignal(str, str)  # server_key, description  
    server_error = pyqtSignal(str, str)    # server_key, error_message
    server_status = pyqtSignal(str, str)   # server_key, status_message
    
    # Frame data signal for CRC/LRC inspector
    frame_received = pyqtSignal(str, bytes, str)  # direction, raw_frame, protocol

    # Legacy compatibility signals for old UI code
    legacy_server_started = pyqtSignal(str, int)  # address, port
    legacy_server_stopped = pyqtSignal(str, int)  # address, port
    legacy_server_error = pyqtSignal(str)         # error_message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.async_loop = AsyncioEventLoop()
        self.async_loop.status_update.connect(self._on_async_status)
        self.async_loop.error_occurred.connect(self._on_async_error)
        
        self.servers: Dict[str, Any] = {}  # server_key -> AsyncModbusServer
        
        # Connect modern signals to emit legacy format automatically
        self.server_started.connect(self._emit_legacy_started)
        self.server_stopped.connect(self._emit_legacy_stopped)
        self.server_error.connect(self._emit_legacy_error)
        
        # Start the asyncio integration
        self.async_loop.start_loop()
    
    def _on_async_status(self, message: str):
        """Handle status updates from async code."""
        global_logger.log(f"Async status: {message}")
        # Parse message to extract server info if needed
        
    def _on_async_error(self, message: str):
        """Handle errors from async code."""
        global_logger.log(f"Async error: {message}")
    
    def _parse_server_key(self, server_key: str) -> tuple:
        """Parse server_key format 'tcp://192.168.1.100:502' -> ('192.168.1.100', 502)"""
        try:
            if "://" in server_key:
                _, addr_port = server_key.split("://", 1)
                if ":" in addr_port:
                    address, port_str = addr_port.rsplit(":", 1)
                    return address, int(port_str)
        except (ValueError, IndexError):
            pass
        return None, None
    
    def _emit_legacy_started(self, server_key: str, description: str):
        """Convert modern server_started signal to legacy format"""
        address, port = self._parse_server_key(server_key)
        if address and port:
            self.legacy_server_started.emit(address, port)
            
    def _emit_legacy_stopped(self, server_key: str, description: str):
        """Convert modern server_stopped signal to legacy format"""
        address, port = self._parse_server_key(server_key)
        if address and port:
            self.legacy_server_stopped.emit(address, port)
            
    def _emit_legacy_error(self, server_key: str, error_message: str):
        """Convert modern server_error signal to legacy format"""
        self.legacy_server_error.emit(error_message)
        
    def start_server(self, server_key: str, async_server) -> bool:
        """Start an async Modbus server."""
        if server_key in self.servers:
            global_logger.log(f"Server {server_key} already running")
            return False
            
        try:
            # Set up callbacks to bridge async -> Qt signals
            def on_status(msg):
                # Use Qt's signal system to safely emit from async code
                self.server_status.emit(server_key, msg)
                
                # If this is a "started successfully" message, emit the server_started signal
                if "started successfully" in msg:
                    description = self._get_server_description(async_server)
                    self.server_started.emit(server_key, description)
                
            def on_error(msg):
                self.server_error.emit(server_key, msg)
                # If server fails, remove from active servers
                if server_key in self.servers:
                    global_logger.log(f"Removing failed server {server_key} from active servers")
                    
                    # Handle the task exception to prevent "Task exception was never retrieved" warning
                    task = self.servers[server_key]['task']
                    if task.done() and not task.cancelled():
                        try:
                            task.result()  # Retrieve the exception to silence the warning
                        except Exception:
                            pass  # We already handled this via the error callback
                    
                    del self.servers[server_key]
                
            def on_frame(direction, raw_frame, protocol):
                self.frame_received.emit(direction, raw_frame, protocol)

            async_server.set_callbacks(on_status, on_error, on_frame)
            
            # Start the server on the async loop and properly set server_task
            task = self.async_loop.run_coroutine(async_server.start_async())
            
            # Manually set the server_task so is_running() works correctly
            async_server.server_task = task
            
            # Add exception callback to handle unhandled exceptions
            def handle_task_exception(task):
                if task.done() and not task.cancelled():
                    try:
                        task.result()  # This will raise the exception if there was one
                    except Exception as e:
                        # Exception was already handled by on_error callback, just silence warning
                        pass
            
            task.add_done_callback(handle_task_exception)
            
            # IMPORTANT: Only add to servers list AFTER we know the task is created
            # The actual success/failure will be handled by the callbacks
            self.servers[server_key] = {
                'server': async_server,
                'task': task,
                'started': False  # Track whether server actually started successfully
            }
            
            # DON'T emit started signal immediately - let the server itself emit it
            # when it actually starts successfully via on_status callback
            
            global_logger.log(f"Created async server task: {server_key}")
            return True  # Task created successfully (not necessarily server started)
            
        except Exception as e:
            error_msg = f"Failed to create server task {server_key}: {e}"
            global_logger.log(error_msg)
            self.server_error.emit(server_key, error_msg)
            return False
    
    def stop_server(self, server_key: str) -> bool:
        """Stop an async Modbus server."""
        if server_key not in self.servers:
            global_logger.log(f"Server {server_key} not running")
            return False
            
        try:
            server_info = self.servers[server_key]
            async_server = server_info['server']
            
            # Request graceful stop to set internal flags and close sockets
            try:
                self.async_loop.run_coroutine(async_server.stop_async())
            except Exception:
                pass
            
            # Also cancel the server task to ensure termination
            task = server_info.get('task')
            if task and not task.done():
                task.cancel()
                # Allow a tiny window for cleanup
                try:
                    self.async_loop.run_coroutine(asyncio.sleep(0.1))
                except Exception:
                    pass
            
            # Remove from active servers immediately
            del self.servers[server_key]
            
            # Emit stopped signal
            description = self._get_server_description(async_server)
            self.server_stopped.emit(server_key, description)
            
            # Server stopped successfully
            return True
            
        except Exception as e:
            error_msg = f"Failed to stop server {server_key}: {e}"
            self.server_error.emit(server_key, error_msg)
            return False
    
    def _get_server_description(self, async_server) -> str:
        """Get a human-readable description of the server."""
        config = async_server.config
        if config.protocol.value == 'tcp':
            return f"TCP on {config.address}:{config.port}"
        else:
            return f"{config.protocol.value.upper()} on {config.serial_port} @ {config.baudrate}"
    
    def is_server_running(self, server_key: str) -> bool:
        """Check if a server is running."""
        if server_key not in self.servers:
            return False
            
        server_info = self.servers[server_key]
        task = server_info['task']
        
        # Check if task is done (completed or failed)
        if task.done():
            # Task is done, check if it failed
            try:
                # This will raise an exception if the task failed
                task.result()
                # If we get here, task completed successfully but server might have stopped
                return server_info['server'].is_running()
            except Exception:
                # Task failed, server is not running
                return False
        
        # Task is still running, check server status
        return server_info['server'].is_running()
    
    def cleanup_failed_tasks(self):
        """Clean up any failed tasks to prevent exception warnings."""
        servers_to_remove = []
        
        for server_key, server_info in self.servers.items():
            task = server_info['task']
            if task.done():
                try:
                    # Retrieve result to handle any unhandled exceptions
                    task.result()
                except Exception:
                    # Task failed, mark for removal
                    servers_to_remove.append(server_key)
        
        # Remove failed servers
        for server_key in servers_to_remove:
            global_logger.log(f"Cleaning up failed server task: {server_key}")
            del self.servers[server_key]
    
    def shutdown_all(self):
        """Shutdown all servers and the asyncio loop."""
        global_logger.log("Shutting down all async servers")
        
        # Clean up any failed tasks first
        self.cleanup_failed_tasks()
        
        # Stop all servers
        for server_key in list(self.servers.keys()):
            self.stop_server(server_key)
            
        # Stop the asyncio loop
        self.async_loop.stop_loop()


# Global instance for application-wide use
_global_async_manager: Optional[AsyncServerManager] = None

def get_async_server_manager() -> AsyncServerManager:
    """Get the global async server manager instance."""
    global _global_async_manager
    if _global_async_manager is None:
        _global_async_manager = AsyncServerManager()
    return _global_async_manager

def shutdown_async_manager():
    """Shutdown the global async server manager."""
    global _global_async_manager
    if _global_async_manager:
        _global_async_manager.shutdown_all()
        _global_async_manager = None
