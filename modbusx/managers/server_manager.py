"""
Server Manager - SOA Architecture

Orchestration layer that manages ModBus server lifecycle.
Bridges UI server control requests with async server services.
"""

from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, Optional, Any

from modbusx.server import AsyncModbusServer, ServerConfig, ServerProtocol
from modbusx.bridge import get_async_server_manager
from modbusx.logger import global_logger
from modbusx.services.register_sync_service import get_register_sync_service


class ServerManager(QObject):
    """
    Server Manager - SOA Orchestration Layer
    
    Manages async Modbus servers through proper orchestration.
    Coordinates UI server control requests with async server services.
    """
    
    # Maintain same signal interface for compatibility
    server_started = pyqtSignal(str, int)  # address, port
    server_stopped = pyqtSignal(str, int)  # address, port
    server_error = pyqtSignal(str)  # error message
    server_status = pyqtSignal(str)  # status message
    frame_received = pyqtSignal(str, bytes, str)  # direction, raw_frame, protocol
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Use the global async server manager
        self.async_manager = get_async_server_manager()
        
        # Connect async manager signals to our signals for UI compatibility
        self.async_manager.server_started.connect(self._on_async_server_started)
        self.async_manager.server_stopped.connect(self._on_async_server_stopped)
        self.async_manager.server_error.connect(self._on_async_server_error)
        self.async_manager.server_status.connect(self._on_async_server_status)
        self.async_manager.frame_received.connect(self.frame_received)

        # Track active servers for compatibility
        self._active_servers: Dict[str, AsyncModbusServer] = {}
        
        # Get sync service for real-time register updates
        self.sync_service = get_register_sync_service()
    
    def _on_async_server_started(self, server_key: str, description: str):
        """Handle async server started signal."""
        global_logger.log(f"Server started: {server_key} - {description}")
        
        # Register server with sync service for real-time updates
        if server_key in self._active_servers:
            async_server = self._active_servers[server_key]
            # Support both legacy 'unit_definitions' and current 'live_slaves'
            units = None
            if hasattr(async_server, 'unit_definitions'):
                units = getattr(async_server, 'unit_definitions')
            elif hasattr(async_server, 'live_slaves'):
                units = getattr(async_server, 'live_slaves')
            if isinstance(units, dict):
                for unit_id, unit_data in units.items():
                    register_map = unit_data.get('register_map') if isinstance(unit_data, dict) else None
                    if register_map:
                        sync_server_id = f"{server_key}_{unit_id}"
                        self.sync_service.register_server(sync_server_id, async_server, register_map)
                        global_logger.log(f"Registered server {sync_server_id} with sync service")
                # register all units (no break)
        
        # Clear any error dialog timing for this server since it started successfully
        if hasattr(self, '_error_dialog_times') and server_key in self._error_dialog_times:
            del self._error_dialog_times[server_key]
        
        # Show success dialog now that server actually started
        QMessageBox.information(None, "Connection Started",
            f"Started Modbus {description}.")
        
        # Parse server key to emit compatible signals
        if ':' in server_key:  # TCP
            parts = server_key.split(':')
            address = parts[0]
            port = int(parts[1])
            self.server_started.emit(address, port)
        else:  # Serial
            # For serial, we'll emit the port name and baudrate
            parts = server_key.split('@')
            port_name = parts[0]
            baudrate = int(parts[1]) if len(parts) > 1 else 9600
            self.server_started.emit(port_name, baudrate)
    
    def _on_async_server_stopped(self, server_key: str, description: str):
        """Handle async server stopped signal."""
        global_logger.log(f"Server stopped: {server_key} - {description}")
        
        # Unregister server from sync service
        if server_key in self._active_servers:
            async_server = self._active_servers[server_key]
            # Unregister all units for this server
            units = None
            if hasattr(async_server, 'unit_definitions'):
                units = getattr(async_server, 'unit_definitions')
            elif hasattr(async_server, 'live_slaves'):
                units = getattr(async_server, 'live_slaves')
            if isinstance(units, dict):
                for unit_id in units.keys():
                    sync_server_id = f"{server_key}_{unit_id}"
                    self.sync_service.unregister_server(sync_server_id)
                    global_logger.log(f"Unregistered server {sync_server_id} from sync service")
            
            # Remove from our tracking
            del self._active_servers[server_key]
        
        # Parse server key to emit compatible signals  
        if ':' in server_key:  # TCP
            parts = server_key.split(':')
            address = parts[0]
            port = int(parts[1])
            self.server_stopped.emit(address, port)
        else:  # Serial
            parts = server_key.split('@')
            port_name = parts[0]
            baudrate = int(parts[1]) if len(parts) > 1 else 9600
            self.server_stopped.emit(port_name, baudrate)
    
    def _on_async_server_error(self, server_key: str, error_message: str):
        """Handle async server error signal."""
        global_logger.log(f"Server error: {server_key} - {error_message}")
        
        # Show error dialog for server failures (prevent rapid duplicates)
        # Check if we've already shown an error for this server recently
        import time
        if not hasattr(self, '_error_dialog_times'):
            self._error_dialog_times = {}
        
        current_time = time.time()
        last_error_time = self._error_dialog_times.get(server_key, 0)
        
        # Only show dialog if it's been more than 2 seconds since last error dialog for this server
        # OR if this is a new connection attempt (cleared in start_server)
        if (current_time - last_error_time > 2.0) and (
            "could not open port" in error_message or 
            "Serial connection error" in error_message or
            "Connection error" in error_message
        ):
            # Mark the time we showed error for this server
            self._error_dialog_times[server_key] = current_time
            # Parse server description from key
            if '@' in server_key:  # Serial
                parts = server_key.split('@')
                port_name = parts[0]
                baudrate = parts[1] if len(parts) > 1 else '9600'
                description = f"Serial port {port_name} @ {baudrate} baud"
            else:  # TCP  
                description = f"TCP {server_key}"
                
            QMessageBox.critical(None, "Connection Failed", 
                f"Failed to start Modbus server on {description}.\n\n"
                f"Error: {error_message}\n\n"
                f"Please check that the port is available and not in use.")
        
        # Remove failed server from our tracking
        if server_key in self._active_servers:
            del self._active_servers[server_key]
        
        # Note: We don't clear _error_dialog_times here to prevent rapid duplicate
        # error dialogs, but new connection attempts will clear it
        
        self.server_error.emit(f"{server_key}: {error_message}")
    
    def _on_async_server_status(self, server_key: str, status_message: str):
        """Handle async server status signal."""
        self.server_status.emit(f"{server_key}: {status_message}")
    
    def _create_server_key(self, connection_info: Dict) -> str:
        """Create server key from connection info."""
        if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
            # Serial connection
            return f"{connection_info['serial_port']}@{connection_info['baudrate']}"
        else:
            # TCP connection
            address = connection_info.get('address', 'localhost')
            port = connection_info.get('port', 502)
            return f"{address}:{port}"
    
    def _create_server_config(self, connection_info: Dict) -> ServerConfig:
        """Create ServerConfig from connection info."""
        if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
            # Serial connection
            protocol = ServerProtocol.RTU if connection_info['protocol'] == 'rtu' else ServerProtocol.ASCII
            return ServerConfig(
                protocol=protocol,
                serial_port=connection_info['serial_port'],
                baudrate=connection_info.get('baudrate', 9600),
                parity=connection_info.get('parity', 'N'),
                stopbits=connection_info.get('stopbits', 1),
                bytesize=connection_info.get('bytesize', 8)
            )
        else:
            # TCP connection
            return ServerConfig(
                protocol=ServerProtocol.TCP,
                address=connection_info.get('address', 'localhost'),
                port=connection_info.get('port', 502)
            )
    
    def start_server(self, connection_info: Dict, unit_definitions: Dict) -> bool:
        """
        Start a Modbus server for the given connection.
        
        Orchestrates server startup through async architecture.
        """
        server_key = self._create_server_key(connection_info)
        
        # Clear any previous error dialog timing for new connection attempts
        if hasattr(self, '_error_dialog_times') and server_key in self._error_dialog_times:
            del self._error_dialog_times[server_key]
        
        # Check if server is already running
        if self.async_manager.is_server_running(server_key):
            if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
                server_desc = f"{connection_info['protocol'].upper()} on {connection_info['serial_port']} @ {connection_info['baudrate']} baud"
            else:
                address = connection_info.get('address', 'localhost')
                port = connection_info.get('port', 502)
                server_desc = f"TCP on {address}:{port}"
            
            QMessageBox.information(None, "Already Running", 
                f"Server {server_desc} is already running.")
            return False
        
        try:
            # Create server configuration
            config = self._create_server_config(connection_info)
            
            # Log unit definitions for debugging (same as old version)
            for unit_id, slave in unit_definitions.items():
                global_logger.log(f"Unit {unit_id}:")
                reg_map = slave["register_map"]
                for regtype in ('hr', 'ir', 'co', 'di'):
                    entries = reg_map.all_entries(regtype)
                    if entries:
                        addrs = [e.addr for e in entries]
                        global_logger.log(
                            f"  {regtype.upper()} Start={min(addrs)} End={max(addrs)} (length={len(addrs)})"
                        )
            
            # Create async server
            async_server = AsyncModbusServer(config, unit_definitions)
            self._active_servers[server_key] = async_server
            
            # Start the server using async manager
            # NOTE: This only means the task was created, not that server actually started
            task_created = self.async_manager.start_server(server_key, async_server)
            
            if task_created:
                # Don't show success dialog immediately - wait for actual success/failure
                # The success dialog will be shown by the _on_async_server_started callback
                # if the server actually starts successfully
                global_logger.log(f"Server task created for {server_key}, waiting for actual start...")
                return True
            else:
                # Task creation failed immediately
                if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
                    server_desc = f"{connection_info['protocol'].upper()} on {connection_info['serial_port']} @ {connection_info['baudrate']} baud"
                else:
                    address = connection_info.get('address', 'localhost')
                    port = connection_info.get('port', 502)
                    server_desc = f"TCP on {address}:{port}"
                
                QMessageBox.critical(None, "Connection Failed",
                    f"Failed to create server task for Modbus {server_desc}.")
                
                # Remove from our tracking if failed
                if server_key in self._active_servers:
                    del self._active_servers[server_key]
                
                return False
            
        except Exception as e:
            error_msg = f"Failed to start server {server_key}: {e}"
            global_logger.log(error_msg)
            self.server_error.emit(error_msg)
            
            # Clean up on failure
            if server_key in self._active_servers:
                del self._active_servers[server_key]
                
            return False
    
    def refresh_server_context(self, connection_info: Dict) -> bool:
        """
        Refresh the server context to reflect updated register groups.
        This should be called whenever register groups are modified.
        """
        server_key = self._create_server_key(connection_info)
        
        # Check if server is running
        if not self.async_manager.is_server_running(server_key):
            global_logger.log(f"Server {server_key} not running, cannot refresh context")
            return False
        
        # Get the active server
        if server_key in self._active_servers:
            server = self._active_servers[server_key]
            try:
                global_logger.log(f"Refreshing server context for {server_key}...")
                
                # Debug: Show current live slaves before refresh
                if hasattr(server, 'live_slaves'):
                    current_units = list(server.live_slaves.keys())
                    global_logger.log(f"Current live slaves before refresh: {current_units}")
                
                # First, update the server's live_slaves with current data
                # We need to get the current unit_definitions from the connection
                current_unit_definitions = self._get_current_unit_definitions(connection_info)
                if current_unit_definitions:
                    server.live_slaves = current_unit_definitions
                    global_logger.log(f"Updated server live_slaves with current definitions: {list(current_unit_definitions.keys())}")
                
                # Now refresh the server context
                server.refresh_server_context()
                
                # Debug: Show live slaves after refresh
                if hasattr(server, 'live_slaves'):
                    refreshed_units = list(server.live_slaves.keys())
                    global_logger.log(f"Live slaves after refresh: {refreshed_units}")
                
                global_logger.log(f"Server context refreshed successfully for {server_key}")
                return True
            except Exception as e:
                global_logger.log(f"Failed to refresh server context for {server_key}: {e}")
                import traceback
                global_logger.log(f"Refresh error traceback: {traceback.format_exc()}")
                return False
        else:
            global_logger.log(f"Server {server_key} not found in active servers")
            global_logger.log(f"Available servers: {list(self._active_servers.keys())}")
            return False
    
    def _get_current_unit_definitions(self, connection_info: Dict) -> Optional[Dict]:
        """Get current unit definitions from the connection."""
        try:
            # Import here to avoid circular imports
            from ..services.connection_service import ConnectionService
            
            # Create connection service directly
            connection_service = ConnectionService()
            
            # Get current slaves for this connection
            connection_name = connection_info.get('name', '')
            if connection_name:
                # Get the connection data
                all_connections = connection_service.get_all_connections()
                current_connection = None
                
                for conn in all_connections:
                    if conn.get('name') == connection_name:
                        current_connection = conn
                        break
                
                if current_connection and 'slaves' in current_connection:
                    # Convert to unit_definitions format
                    unit_definitions = {}
                    for slave in current_connection['slaves']:
                        unit_id = slave.get('unit_id', 1)
                        unit_definitions[unit_id] = {
                            'register_map': slave.get('register_map'),
                            'slave_info': slave
                        }
                    
                    global_logger.log(f"Retrieved current unit definitions: {list(unit_definitions.keys())}")
                    return unit_definitions
                else:
                    global_logger.log(f"No current connection found for '{connection_name}'")
            else:
                # Fallback: build from provided connection_info (UI-driven path)
                if 'slaves' in connection_info and isinstance(connection_info['slaves'], list):
                    unit_definitions = {}
                    for slave in connection_info['slaves']:
                        unit_id = slave.get('slave_id') or slave.get('unit_id') or 1
                        unit_definitions[unit_id] = {
                            'register_map': slave.get('register_map'),
                            'slave_info': slave,
                        }
                    global_logger.log(f"Using UI connection_info for unit definitions: {list(unit_definitions.keys())}")
                    return unit_definitions
                global_logger.log("No connection name in connection_info and no inline slaves found")
                
        except Exception as e:
            global_logger.log(f"Error getting current unit definitions: {e}")
            import traceback
            global_logger.log(f"Traceback: {traceback.format_exc()}")
            
        return None
    
    def stop_server(self, connection_info: Dict) -> bool:
        """
        Stop the Modbus server for the given connection.
        
        Orchestrates server shutdown through async architecture.
        """
        server_key = self._create_server_key(connection_info)
        
        # Check if server is running
        if not self.async_manager.is_server_running(server_key):
            if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
                server_desc = f"{connection_info['protocol'].upper()} on {connection_info['serial_port']} @ {connection_info['baudrate']} baud"
            else:
                address = connection_info.get('address', 'localhost')
                port = connection_info.get('port', 502)
                server_desc = f"TCP on {address}:{port}"
                
            QMessageBox.information(None, "Already Stopped", 
                f"Server {server_desc} is already stopped.")
            return False
        
        try:
            # Stop the server using async manager
            success = self.async_manager.stop_server(server_key)
            
            if success:
                # Remove from our tracking
                if server_key in self._active_servers:
                    del self._active_servers[server_key]
                
                # Clear error dialog timing for this server
                if hasattr(self, '_error_dialog_times') and server_key in self._error_dialog_times:
                    del self._error_dialog_times[server_key]
                
                # Show success message
                if 'protocol' in connection_info and connection_info['protocol'] in ['rtu', 'ascii']:
                    server_desc = f"{connection_info['protocol'].upper()} on {connection_info['serial_port']} @ {connection_info['baudrate']} baud"
                else:
                    address = connection_info.get('address', 'localhost')
                    port = connection_info.get('port', 502)
                    server_desc = f"TCP on {address}:{port}"
                
                # Show non-blocking success message
                from PyQt5.QtCore import QTimer
                def show_success():
                    QMessageBox.information(None, "Connection Closed",
                        f"Closed Modbus {server_desc}.")
                QTimer.singleShot(100, show_success)
            
            return success
            
        except Exception as e:
            error_msg = f"Failed to stop server {server_key}: {e}"
            global_logger.log(error_msg)
            self.server_error.emit(error_msg)
            return False
    
    def is_server_running(self, connection_info: Dict) -> bool:
        """Check if server is running for the given connection."""
        server_key = self._create_server_key(connection_info)
        return self.async_manager.is_server_running(server_key)
    
    def shutdown_all_servers(self):
        """Shutdown all active servers."""
        
        # Clear our tracking
        self._active_servers.clear()
        
        # Clear error dialog timing
        if hasattr(self, '_error_dialog_times'):
            self._error_dialog_times.clear()
        
        # Shutdown async manager
        self.async_manager.shutdown_all()
