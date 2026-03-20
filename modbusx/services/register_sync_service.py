"""
Register Sync Service

Handles real-time synchronization of register changes between UI and server components.
Ensures that register value changes are immediately propagated to all active ModBus servers
without requiring connection restart.
"""

from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from typing import Dict, List, Optional, Any
from ..models import RegisterMap, RegisterEntry
from ..logger import get_logger


class RegisterChangeNotifier(QObject):
    """Notifies components about register changes."""
    
    # Signals for register changes
    register_value_changed = pyqtSignal(str, int, object)      # reg_type, addr, new_value
    register_created = pyqtSignal(str, int, object)           # reg_type, addr, register_entry
    register_deleted = pyqtSignal(str, int)                   # reg_type, addr
    register_moved = pyqtSignal(str, int, int)                # reg_type, old_addr, new_addr
    
    # Bulk operation signals
    register_group_changed = pyqtSignal(str, int, int, dict)  # reg_type, start_addr, size, changes
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
    
    def notify_value_change(self, reg_type: str, addr: int, new_value: Any):
        """Notify that a register value has changed."""
        self.logger.debug(f"Register value change: {reg_type.upper()}:{addr} = {new_value}")
        self.register_value_changed.emit(reg_type, addr, new_value)
    
    def notify_register_created(self, reg_type: str, addr: int, entry: RegisterEntry):
        """Notify that a new register was created."""
        self.logger.debug(f"Register created: {reg_type.upper()}:{addr}")
        self.register_created.emit(reg_type, addr, entry)
    
    def notify_register_deleted(self, reg_type: str, addr: int):
        """Notify that a register was deleted."""
        self.logger.debug(f"Register deleted: {reg_type.upper()}:{addr}")
        self.register_deleted.emit(reg_type, addr)
    
    def notify_register_moved(self, reg_type: str, old_addr: int, new_addr: int):
        """Notify that a register address was changed."""
        self.logger.debug(f"Register moved: {reg_type.upper()}:{old_addr} -> {new_addr}")
        self.register_moved.emit(reg_type, old_addr, new_addr)
    
    def notify_group_changes(self, reg_type: str, start_addr: int, size: int, changes: Dict):
        """Notify about bulk changes to a register group."""
        self.logger.debug(f"Register group changed: {reg_type.upper()}:{start_addr}-{start_addr+size-1}")
        self.register_group_changed.emit(reg_type, start_addr, size, changes)


class RegisterSyncService(QObject):
    """Service for real-time register synchronization."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        
        # Change notifier for broadcasting updates
        self.notifier = RegisterChangeNotifier(self)
        
        # Track active servers that need updates
        self.active_servers: Dict[str, Any] = {}  # server_id -> server_instance
        self.server_register_maps: Dict[str, RegisterMap] = {}  # server_id -> register_map
        
        # Debounce timer for bulk operations
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self._process_pending_updates)
        self.pending_updates: Dict[str, Dict] = {}  # server_id -> pending changes
        
        # Connect to change notifications
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect to change notification signals."""
        self.notifier.register_value_changed.connect(self._on_register_value_changed)
        self.notifier.register_created.connect(self._on_register_created)
        self.notifier.register_deleted.connect(self._on_register_deleted)
        self.notifier.register_moved.connect(self._on_register_moved)
        self.notifier.register_group_changed.connect(self._on_register_group_changed)
    
    def register_server(self, server_id: str, server_instance: Any, register_map: RegisterMap):
        """Register a ModBus server for real-time updates."""
        self.logger.info(f"Registering server for sync: {server_id}")
        self.active_servers[server_id] = server_instance
        self.server_register_maps[server_id] = register_map
    
    def unregister_server(self, server_id: str):
        """Unregister a ModBus server from real-time updates."""
        self.logger.info(f"Unregistering server from sync: {server_id}")
        self.active_servers.pop(server_id, None)
        self.server_register_maps.pop(server_id, None)
        self.pending_updates.pop(server_id, None)
    
    def get_registered_servers(self) -> List[str]:
        """Get list of registered server IDs."""
        return list(self.active_servers.keys())
    
    def propagate_register_change(self, reg_type: str, addr: int, new_value: Any, 
                                  source_register_map: RegisterMap = None):
        """Propagate a register change to all active servers immediately."""
        self.logger.debug(f"Propagating register change: {reg_type.upper()}:{addr} = {new_value}")
        
        # Notify via signals first
        self.notifier.notify_value_change(reg_type, addr, new_value)
        
        # Update all registered servers
        for server_id, server_instance in self.active_servers.items():
            server_register_map = self.server_register_maps.get(server_id)
            
            # Skip the source register map to avoid circular updates
            if server_register_map is source_register_map:
                continue
                
            try:
                # Update the register map
                if server_register_map:
                    register_dict = getattr(server_register_map, reg_type, None)
                    if register_dict and addr in register_dict:
                        register_dict[addr].value = new_value
                        self.logger.debug(f"Updated server {server_id}: {reg_type.upper()}:{addr} = {new_value}")
                
                # If server has a data block, update it directly
                if hasattr(server_instance, 'update_register_value'):
                    server_instance.update_register_value(reg_type, addr, new_value)
                elif hasattr(server_instance, 'datablock'):
                    # Update the server's datablock directly
                    datablock = getattr(server_instance, 'datablock', None)
                    if datablock and hasattr(datablock, 'update_register'):
                        datablock.update_register(reg_type, addr, new_value)
                        
            except Exception as e:
                self.logger.error(f"Failed to update server {server_id}: {e}")
    
    def propagate_bulk_changes(self, changes: List[Dict], debounce_ms: int = 100):
        """Propagate multiple register changes with optional debouncing."""
        self.logger.debug(f"Propagating {len(changes)} bulk changes")
        
        if debounce_ms > 0:
            # Add to pending updates and start debounce timer
            for change in changes:
                server_id = change.get('server_id', 'all')
                if server_id not in self.pending_updates:
                    self.pending_updates[server_id] = []
                self.pending_updates[server_id].append(change)
            
            self.update_timer.stop()
            self.update_timer.start(debounce_ms)
        else:
            # Process immediately
            for change in changes:
                self.propagate_register_change(
                    change['reg_type'],
                    change['addr'],
                    change['value'],
                    change.get('source_register_map')
                )
    
    def _process_pending_updates(self):
        """Process all pending updates (called by debounce timer)."""
        self.logger.debug("Processing pending register updates")
        
        for server_id, changes in self.pending_updates.items():
            for change in changes:
                self.propagate_register_change(
                    change['reg_type'],
                    change['addr'],
                    change['value'],
                    change.get('source_register_map')
                )
        
        # Clear pending updates
        self.pending_updates.clear()
    
    def sync_register_map(self, source_map: RegisterMap, target_server_id: str = None):
        """Synchronize entire register map to servers."""
        self.logger.info("Synchronizing register map to servers")
        
        target_servers = [target_server_id] if target_server_id else self.active_servers.keys()
        
        for server_id in target_servers:
            if server_id not in self.active_servers:
                continue
                
            server_map = self.server_register_maps.get(server_id)
            if not server_map:
                continue
            
            try:
                # Sync all register types
                for reg_type in ['co', 'di', 'ir', 'hr']:
                    source_dict = getattr(source_map, reg_type, {})
                    target_dict = getattr(server_map, reg_type, {})
                    
                    # Update all registers in target
                    for addr, entry in source_dict.items():
                        if addr in target_dict:
                            target_dict[addr].value = entry.value
                            target_dict[addr].alias = entry.alias
                            target_dict[addr].comment = entry.comment
                            target_dict[addr].units = entry.units
                
                self.logger.debug(f"Synchronized register map to server {server_id}")
                
            except Exception as e:
                self.logger.error(f"Failed to sync register map to server {server_id}: {e}")

    # ----- Convenience helpers for external services (e.g., scripting) -----
    def apply_to_server(self, server_id: str, reg_type: str, addr: int, value: Any) -> None:
        """Apply a single register value to a registered server's map.

        Policy: update-only. If the register does not exist, do nothing.
        """
        if server_id not in self.server_register_maps:
            return
        try:
            reg_map = self.server_register_maps[server_id]
            reg_dict = getattr(reg_map, reg_type)
            if addr not in reg_dict:
                # Update-only policy: skip missing entries
                self.logger.debug(
                    f"apply_to_server skipped (missing): {server_id} {reg_type}:{addr}")
                return
            reg_dict[addr].value = int(value)
        except Exception as e:
            self.logger.error(f"apply_to_server failed for {server_id} {reg_type}:{addr} -> {e}")

    def apply_bulk_to_server(self, server_id: str, changes: list) -> None:
        """Apply a list of changes {reg_type, addr, value} to a registered server.

        Policy: update-only. Skip any missing registers.
        """
        if server_id not in self.server_register_maps:
            return
        try:
            reg_map = self.server_register_maps[server_id]
            for c in changes:
                reg_type = c['reg_type']
                addr = int(c['addr'])
                value = int(c['value'])
                reg_dict = getattr(reg_map, reg_type)
                if addr not in reg_dict:
                    self.logger.debug(
                        f"apply_bulk_to_server skipped (missing): {server_id} {reg_type}:{addr}")
                    continue
                reg_dict[addr].value = value
        except Exception as e:
            self.logger.error(f"apply_bulk_to_server failed for {server_id}: {e}")
    
    # Signal handlers
    def _on_register_value_changed(self, reg_type: str, addr: int, new_value: Any):
        """Handle register value change notifications."""
        # This is called when the notifier emits the signal
        # Additional processing can be added here if needed
        pass
    
    def _on_register_created(self, reg_type: str, addr: int, entry: RegisterEntry):
        """Handle register creation notifications."""
        # Propagate register creation to all servers
        for server_id, server_map in self.server_register_maps.items():
            try:
                register_dict = getattr(server_map, reg_type, None)
                if register_dict is not None:
                    # Create a copy of the register entry
                    new_entry = RegisterEntry(
                        addr=entry.addr,
                        reg_type=entry.reg_type,
                        value=entry.value,
                        alias=entry.alias,
                        comment=entry.comment,
                        units=entry.units
                    )
                    register_dict[addr] = new_entry
                    self.logger.debug(f"Created register in server {server_id}: {reg_type.upper()}:{addr}")
            except Exception as e:
                self.logger.error(f"Failed to create register in server {server_id}: {e}")
    
    def _on_register_deleted(self, reg_type: str, addr: int):
        """Handle register deletion notifications."""
        # Propagate register deletion to all servers
        for server_id, server_map in self.server_register_maps.items():
            try:
                register_dict = getattr(server_map, reg_type, None)
                if register_dict is not None and addr in register_dict:
                    del register_dict[addr]
                    self.logger.debug(f"Deleted register in server {server_id}: {reg_type.upper()}:{addr}")
            except Exception as e:
                self.logger.error(f"Failed to delete register in server {server_id}: {e}")
    
    def _on_register_moved(self, reg_type: str, old_addr: int, new_addr: int):
        """Handle register address change notifications."""
        # Propagate register move to all servers
        for server_id, server_map in self.server_register_maps.items():
            try:
                register_dict = getattr(server_map, reg_type, None)
                if register_dict is not None and old_addr in register_dict:
                    entry = register_dict.pop(old_addr)
                    entry.addr = new_addr
                    register_dict[new_addr] = entry
                    self.logger.debug(f"Moved register in server {server_id}: {reg_type.upper()}:{old_addr} -> {new_addr}")
            except Exception as e:
                self.logger.error(f"Failed to move register in server {server_id}: {e}")
    
    def _on_register_group_changed(self, reg_type: str, start_addr: int, size: int, changes: Dict):
        """Handle register group change notifications."""
        # Process bulk changes with debouncing
        bulk_changes = []
        for i in range(size):
            addr = start_addr + i
            if addr in changes:
                bulk_changes.append({
                    'reg_type': reg_type,
                    'addr': addr,
                    'value': changes[addr]
                })
        
        if bulk_changes:
            self.propagate_bulk_changes(bulk_changes, debounce_ms=50)  # 50ms debounce for bulk ops


# Global instance for application-wide register synchronization
_register_sync_service = None

def get_register_sync_service() -> RegisterSyncService:
    """Get the global register sync service instance."""
    global _register_sync_service
    if _register_sync_service is None:
        _register_sync_service = RegisterSyncService()
    return _register_sync_service
