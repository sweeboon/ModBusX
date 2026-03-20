"""
Connection Manager - SOA Architecture

Orchestration layer that manages connection tree operations.
Bridges UI interactions with business services for connection, slave, and register group management.
"""

from PyQt5.QtWidgets import QMessageBox, QTreeView, QMenu, QAction, QInputDialog
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QPixmap, QPainter
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QSize, QCoreApplication
from ..models import RegisterMap
from ..services import RegisterGroupService
from ..services.register_validator import RegisterValidator
from ..logger import get_logger
from ..ui.register_group_dialog import RegisterGroupDialog
from .register_group_manager import RegisterGroupManager
from ..ui.multi_type_group_dialog import MultiTypeGroupDialog
from ..models.multi_type_group import MultiTypeRegisterGroup
from .bulk_operations_manager import BulkOperationsHandler
from typing import Optional, Dict, Any, List

class ConnectionManager(QObject):
    """
    Connection Manager - SOA Orchestration Layer
    
    Manages connection tree operations (connections, slaves, register groups).
    Coordinates between UI interactions and business services.
    """
    
    connection_added = pyqtSignal(str, int, str)  # node_text, port, address
    slave_added = pyqtSignal(int, str)  # slave_id, connection_text
    register_group_added = pyqtSignal(int, str)  # group_id, slave_text
    # New: requests to server manager in MainWindow context
    close_connection_requested = pyqtSignal(dict)     # connection_info
    refresh_connection_requested = pyqtSignal(dict)   # connection_info
    
    def __init__(self, tree_view: QTreeView, tree_model: QStandardItemModel, parent=None):
        super().__init__(parent)
        self.tree_view = tree_view
        self.tree_model = tree_model
        self.group_manager = RegisterGroupManager(self)
        self.bulk_operations = BulkOperationsHandler(self)
        self.logger = get_logger("ConnectionManager")
        
        # Setup context menu
        self._setup_context_menu()
        
        # Connect group manager signals
        self.group_manager.group_duplicated.connect(self._handle_group_duplicated)
        self.group_manager.group_split.connect(self._handle_group_split)
        self.group_manager.group_merged.connect(self._handle_group_merged)
    
    def add_connection(self, port: int, address: str) -> bool:
        """Add a new connection to the tree, with default Slave 1 and Register Group 1."""
        node_text = f"{address}:{port}"
        
        # Prevent duplicate connections
        for i in range(self.tree_model.rowCount()):
            if self.tree_model.item(i, 0).text() == node_text:
                return False
                
        conn_item = QStandardItem(node_text)
        conn_info = {
            'address': address,
            'port': port,
            'slaves': [],
            'is_open': False,
            'item_type': 'connection'
        }
        
        # Set initial status icon (red dot for closed)
        conn_item.setIcon(self._create_status_icon(False))

        # Auto-add first Slave (ID 1) and under it Register Group (ID 1)
        slave_id = 1
        slave_item = QStandardItem(self._format_slave_label(slave_id))

        # The ONE RegisterMap instance for this slave (per comm node)
        register_map = RegisterMap()
        # Add an HR block by default using current addressing mode
        # Use address 1 in current addressing mode (will be converted properly)
        default_addr = 1
        register_map.add_block('hr', default_addr, 10)

        slave_info = {
            "slave_id": slave_id,
            "register_map": register_map,
            "groups": [],  # group metadata for UI tree only
            "item_type": 'slave'
        }

        # Add first register group under this slave
        reg_group_id = 1
        end_addr = default_addr + 10 - 1
        # Create display text based on current addressing mode
        start_display = RegisterValidator.address_to_display(default_addr, 'hr')
        end_display = RegisterValidator.address_to_display(end_addr, 'hr')
        
        group_meta = {
            "register_id": reg_group_id,
            "reg_type": "hr",
            "start_addr": default_addr,
            "size": 10,
            "parent_slave_map": register_map,
            "item_type": 'register_group'
        }
        reg_item = QStandardItem(self._format_register_group_label(reg_group_id, "HR", start_display, end_display))
        reg_item.setData(group_meta, Qt.UserRole)
        # Attach it as child of the slave
        slave_item.appendRow(reg_item)
        # Update slave_info
        slave_info["groups"].append(group_meta)

        slave_item.setData(slave_info, Qt.UserRole)
        conn_item.appendRow(slave_item)
        conn_info['slaves'].append(slave_info)
        conn_item.setData(conn_info, Qt.UserRole)

        self.tree_model.appendRow(conn_item)
        self.tree_view.expand(self.tree_model.indexFromItem(conn_item))
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        
        self.connection_added.emit(node_text, port, address)
        return True
    
    def add_rtu_connection(self, serial_port: str, baudrate: int, protocol: str = 'rtu') -> bool:
        """Add a new RTU/ASCII connection to the tree."""
        node_text = f"{protocol.upper()}: {serial_port} @ {baudrate}"
        
        # Prevent duplicate connections
        for i in range(self.tree_model.rowCount()):
            if self.tree_model.item(i, 0).text() == node_text:
                return False
                
        conn_item = QStandardItem(node_text)
        conn_info = {
            'serial_port': serial_port,
            'baudrate': baudrate,
            'protocol': protocol,
            'slaves': [],
            'is_open': False,
            'item_type': 'connection'
        }
        
        # Set initial status icon (red dot for closed)
        conn_item.setIcon(self._create_status_icon(False))

        # Auto-add first Slave (ID 1) and under it Register Group (ID 1)
        slave_id = 1
        slave_item = QStandardItem(self._format_slave_label(slave_id))

        # The ONE RegisterMap instance for this slave
        register_map = RegisterMap()
        # Add an HR block by default using current addressing mode
        default_addr = 1
        register_map.add_block('hr', default_addr, 10)

        slave_info = {
            "slave_id": slave_id,
            "register_map": register_map,
            "groups": [],  # group metadata for UI tree only
            "item_type": 'slave'
        }

        # Add first register group under this slave
        reg_group_id = 1
        end_addr = default_addr + 10 - 1
        # Create display text based on current addressing mode
        start_display = RegisterValidator.address_to_display(default_addr, 'hr')
        end_display = RegisterValidator.address_to_display(end_addr, 'hr')
        
        group_meta = {
            "register_id": reg_group_id,
            "reg_type": "hr",
            "start_addr": default_addr,
            "size": 10,
            "parent_slave_map": register_map,
            "item_type": 'register_group'
        }
        
        slave_info["groups"].append(group_meta)
        conn_info["slaves"].append(slave_info)

        group_item = QStandardItem(self._format_register_group_label(reg_group_id, "HR", start_display, end_display))
        group_item.setData(group_meta, Qt.UserRole)
        slave_item.appendRow(group_item)
        slave_item.setData(slave_info, Qt.UserRole)

        conn_item.appendRow(slave_item)
        conn_item.setData(conn_info, Qt.UserRole)
        self.tree_model.appendRow(conn_item)

        # Expand the new items by default
        self.tree_view.expand(self.tree_model.indexFromItem(conn_item))
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        
        self.connection_added.emit(node_text, baudrate, serial_port)
        return True
    
    def get_selected_connection_item(self) -> Optional[QStandardItem]:
        """Helper: Returns the connection-level item for current selection, or None."""
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self.tree_view, self.tr("Nothing Selected"), self.tr("Please select a connection node."))
            return None
        item = self.tree_model.itemFromIndex(indexes[0])
        # Ascend to root-level if slave/register is selected
        while item.parent() is not None:
            item = item.parent()
        return item
    
    def get_selected_slave_item(self) -> Optional[QStandardItem]:
        """Return the slave item for current selection, or None."""
        indexes = self.tree_view.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self.tree_view, self.tr("Nothing Selected"), self.tr("Please select a slave node."))
            return None
        item = self.tree_model.itemFromIndex(indexes[0])
        # If not a slave, traverse up tree until child of connection
        while item:
            if self._is_slave_item(item):
                return item
            if item.parent() is None:
                break
            item = item.parent()
        return None
    
    def add_slave_to_selected_connection(self) -> bool:
        """Add a new slave to the selected connection."""
        conn_item = self.get_selected_connection_item()
        if not conn_item:
            return False
            
        conn_info = conn_item.data(Qt.UserRole)
        used_ids = set()
        for i in range(conn_item.rowCount()):
            child_item = conn_item.child(i)
            payload = self._get_item_payload(child_item)
            if payload.get('item_type') == 'slave':
                sid_val = payload.get('slave_id')
                if isinstance(sid_val, int):
                    used_ids.add(sid_val)
        # Suggest next available ID as default
        next_id = 1
        while next_id in used_ids:
            next_id += 1

        # Prompt the user for a Slave ID (1-247 typical Modbus range)
        sid, ok = QInputDialog.getInt(
            self.tree_view,
            self.tr("Add Slave"),
            self.tr("Enter Slave ID (1-247):"),
            next_id, 1, 247, 1
        )
        if not ok:
            return False
        if sid in used_ids:
            QMessageBox.warning(self.tree_view, self.tr("Duplicate ID"), self.tr("Slave ID {} already exists on this connection.").format(sid))
            return False

        slave_item = QStandardItem(self._format_slave_label(sid))
        register_map = RegisterMap()
        # Default group: first HR block for new slave using current addressing mode
        reg_type, start_addr, size = "hr", 1, 8
        register_map.add_block(reg_type, start_addr, size)
        group_meta = {
            "register_id": 1,
            "reg_type": reg_type,
            "start_addr": start_addr,
            "size": size,
            "parent_slave_map": register_map,
            "item_type": 'register_group'
        }
        # Create display text based on current addressing mode
        start_display = RegisterValidator.address_to_display(start_addr, reg_type)
        end_display = RegisterValidator.address_to_display(start_addr + size - 1, reg_type)
        display_name = self._format_register_group_label(1, reg_type.upper(), start_display, end_display)
        reg_item = QStandardItem(display_name)
        reg_item.setData(group_meta, Qt.UserRole)
        slave_item.appendRow(reg_item)
        slave_info = {
            "slave_id": sid,
            "register_map": register_map,
            "groups": [group_meta],
            "item_type": 'slave'
        }
        slave_item.setData(slave_info, Qt.UserRole)
        conn_item.appendRow(slave_item)
        conn_info['slaves'].append(slave_info)
        conn_item.setData(conn_info, Qt.UserRole)
        self.tree_view.expand(self.tree_model.indexFromItem(conn_item))
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        
        QMessageBox.information(self.tree_view, self.tr("Slave Added"), self.tr("Added Slave ID: {}.").format(sid))
        self.slave_added.emit(sid, conn_item.text())
        return True
    
    def add_register_group_to_selected_slave(self) -> bool:
        """Add a new register group to the selected slave using enhanced dialog."""
        slave_item = self.get_selected_slave_item()
        if not slave_item:
            return False
            
        slave_info = slave_item.data(Qt.UserRole)
        register_map = slave_info["register_map"]
        
        # Use enhanced register group dialog
        dialog = RegisterGroupDialog(register_map, self.tree_view)
        dialog.group_created.connect(lambda group_data: self._add_group_from_dialog(slave_item, group_data))
        
        return dialog.exec_() == dialog.Accepted
    
    def add_multi_type_group_to_selected_slave(self) -> bool:
        """Add a new multi-type register group to the selected slave."""
        slave_item = self.get_selected_slave_item()
        if not slave_item:
            return False
            
        slave_info = slave_item.data(Qt.UserRole)
        register_map = slave_info["register_map"]
        
        # Use multi-type group dialog
        dialog = MultiTypeGroupDialog(register_map, self.tree_view)
        dialog.group_created.connect(lambda multi_group: self._add_multi_type_group_from_dialog(slave_item, multi_group))
        
        return dialog.exec_() == dialog.Accepted
    
    def get_connection_info(self, connection_item: QStandardItem) -> Optional[Dict[str, Any]]:
        """Get connection info from a connection item."""
        if not connection_item:
            return None
        return connection_item.data(Qt.UserRole)
    
    def _create_status_icon(self, is_open: bool) -> QIcon:
        """Create a colored dot icon for connection status."""
        # Create a 16x16 pixmap
        pixmap = QPixmap(16, 16)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Set color based on status
        if is_open:
            painter.setBrush(Qt.green)  # Green dot for open/connected
        else:
            painter.setBrush(Qt.red)    # Red dot for closed/disconnected
        
        painter.setPen(Qt.NoPen)
        
        # Draw a circle (dot) centered in the 16x16 area
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        
        return QIcon(pixmap)
    
    def update_connection_status(self, connection_item: QStandardItem, is_open: bool):
        """Update connection status in the tree with visual dot indicator."""
        if not connection_item:
            return
            
        conn_info = connection_item.data(Qt.UserRole)
        if not conn_info:
            return
            
        conn_info["is_open"] = is_open
        
        # Handle different connection types for display text
        if 'protocol' in conn_info and conn_info['protocol'] in ['rtu', 'ascii']:
            # RTU/ASCII connection
            protocol = conn_info['protocol'].upper()
            serial_port = conn_info['serial_port']
            baudrate = conn_info['baudrate']
            base_text = f"{protocol}: {serial_port} @ {baudrate}"
        else:
            # TCP connection
            address = conn_info['address']
            port = conn_info['port']
            base_text = f"{address}:{port}"
        
        status_suffix = ""
        if is_open:
            status_suffix = f" ({self.tr('OPEN')})"
        connection_item.setText(f"{base_text}{status_suffix}")
        
        # Set the status icon
        status_icon = self._create_status_icon(is_open)
        connection_item.setIcon(status_icon)
            
        connection_item.setData(conn_info, Qt.UserRole)
    
    def _setup_context_menu(self):
        """Setup context menu for tree view."""
        self.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_view.customContextMenuRequested.connect(self._show_context_menu)
    
    def _show_context_menu(self, position):
        """Show context menu at the given position."""
        index = self.tree_view.indexAt(position)
        if not index.isValid():
            return
        
        item = self.tree_model.itemFromIndex(index)
        
        menu = QMenu(self.tree_view)
        
        # Determine context based on item type
        if self._is_connection_item(item):
            self._add_connection_menu_actions(menu, item)
        elif self._is_slave_item(item):
            self._add_slave_menu_actions(menu, item)
        elif self._is_register_group_item(item):
            self._add_register_group_menu_actions(menu, item)
        elif self._is_multi_type_group_item(item):
            self._add_multi_type_group_menu_actions(menu, item)
        
        if menu.actions():
            menu.exec_(self.tree_view.mapToGlobal(position))
    
    def _is_connection_item(self, item: QStandardItem) -> bool:
        """Check if item is a connection item."""
        return item.parent() is None
    
    def _get_item_payload(self, item: QStandardItem) -> Dict:
        """Safely get the payload stored on an item."""
        if not item:
            return {}
        data = item.data(Qt.UserRole)
        return data if isinstance(data, dict) else {}
    
    def _is_slave_item(self, item: QStandardItem) -> bool:
        """Check if item is a slave item."""
        parent = item.parent() if item else None
        if parent is None or parent.parent() is not None:
            return False
        data = self._get_item_payload(item)
        if data.get('item_type') == 'slave':
            return True
        text = (item.text() or "")
        return text.startswith("Slave ID:")
    
    def _is_register_group_item(self, item: QStandardItem) -> bool:
        """Check if item is a single-type register group item."""
        if not item or item.parent() is None:
            return False
        data = self._get_item_payload(item)
        if data.get('item_type') == 'register_group':
            return True
        return bool(data.get('reg_type') and not data.get('register_blocks'))
    
    def _is_multi_type_group_item(self, item: QStandardItem) -> bool:
        """Check if item is a multi-type group item."""
        if not item or item.parent() is None:
            return False
        data = self._get_item_payload(item)
        if data.get('item_type') == 'multi_type_group':
            return True
        return bool(data.get('register_blocks'))
    
    def _is_multi_block_item(self, item: QStandardItem) -> bool:
        """Check if item is a register block under multi-type group."""
        data = self._get_item_payload(item)
        if data.get('item_type') == 'register_block':
            return True
        return data.get('is_multi_type_block') is True
    
    def _format_slave_label(self, slave_id: int, slave_name: str = "") -> str:
        """Return translated label for slave items."""
        label = self.tr("Slave ID: {}").format(slave_id)
        if slave_name:
            label += f" ({slave_name})"
        return label
    
    def _format_register_group_label(self, group_id: int, reg_type_upper: str, start_display: str, end_display: str, group_name: str = "") -> str:
        """Return translated label for register groups."""
        label = self.tr("Register Group: {}").format(group_id)
        if group_name:
            label += f" ({group_name})"
        label += f" [{reg_type_upper} {start_display}:{end_display}]"
        return label
    
    def _format_multi_group_label(self, group_id: int, group_name: str = "") -> str:
        """Return translated label for multi-type groups."""
        label = self.tr("Multi-Type Group: {}").format(group_id)
        if group_name:
            label += f" ({group_name})"
        return label
    
    def _format_block_label(self, reg_type_upper: str, start_addr: int, end_addr: int) -> str:
        """Return translated label for register blocks."""
        return self.tr("{} Block: {}:{}").format(reg_type_upper, start_addr, end_addr)
    
    def _add_connection_menu_actions(self, menu: QMenu, item: QStandardItem):
        """Add context menu actions for connection items."""
        add_slave_action = QAction(self.tr("Add Slave"), self.tree_view)
        add_slave_action.triggered.connect(lambda: self._select_item_and_add_slave(item))
        menu.addAction(add_slave_action)
        
        menu.addSeparator()
        
        remove_action = QAction(self.tr("Remove Connection"), self.tree_view)
        remove_action.triggered.connect(lambda: self._remove_connection(item))
        menu.addAction(remove_action)
    
    def _add_slave_menu_actions(self, menu: QMenu, item: QStandardItem):
        """Add context menu actions for slave items."""
        add_group_action = QAction(self.tr("Add Register Group"), self.tree_view)
        add_group_action.triggered.connect(lambda: self._select_item_and_add_group(item))
        menu.addAction(add_group_action)
        
        add_multi_group_action = QAction(self.tr("Add Multi-Type Group"), self.tree_view)
        add_multi_group_action.triggered.connect(lambda: self._select_item_and_add_multi_group(item))
        menu.addAction(add_multi_group_action)
        
        menu.addSeparator()
        
        duplicate_slave_action = QAction(self.tr("Duplicate Slave"), self.tree_view)
        duplicate_slave_action.triggered.connect(lambda: self._duplicate_slave(item))
        menu.addAction(duplicate_slave_action)
        
        bulk_ops_action = QAction(self.tr("Bulk Operations"), self.tree_view)
        bulk_ops_action.triggered.connect(lambda: self._open_bulk_operations(item))
        menu.addAction(bulk_ops_action)
        
        menu.addSeparator()
        
        remove_action = QAction(self.tr("Remove Slave"), self.tree_view)
        remove_action.triggered.connect(lambda: self._remove_slave(item))
        menu.addAction(remove_action)

    def _duplicate_slave(self, item: QStandardItem):
        """Duplicate an existing slave configuration."""
        slave_info = item.data(Qt.UserRole)
        if not slave_info:
            return

        conn_item = item.parent()
        if not conn_item:
            return
            
        # Determine new Slave ID
        used_ids = set()
        for i in range(conn_item.rowCount()):
            child = conn_item.child(i)
            payload = self._get_item_payload(child)
            if payload.get('item_type') == 'slave':
                sid_val = payload.get('slave_id')
                if isinstance(sid_val, int):
                    used_ids.add(sid_val)
        
        new_id = 1
        while new_id in used_ids:
            new_id += 1
            
        if new_id > 247:
            QMessageBox.warning(self.tree_view, self.tr("Error"), self.tr("Cannot duplicate: No available Slave IDs."))
            return

        # Clone logic
        # 1. Create new RegisterMap
        new_register_map = RegisterMap()
        
        # 2. Copy all blocks/entries from old map
        original_map = slave_info['register_map']
        # We manually copy entries to ensure deep independence
        for reg_type in ['hr', 'ir', 'co', 'di']:
            entries = original_map.all_entries(reg_type)
            reg_dict = getattr(new_register_map, reg_type)
            for entry in entries:
                reg_dict[entry.addr] = entry.copy()

        # 3. Create new Slave Info - manually copy groups to avoid deepcopying the RegisterMap inside them
        new_groups = []
        for old_group in slave_info.get('groups', []):
            # Shallow copy the dict
            new_group = old_group.copy()
            # Update the map reference immediately
            new_group['parent_slave_map'] = new_register_map
            new_groups.append(new_group)

        new_slave_info = {
            "slave_id": new_id,
            "register_map": new_register_map,
            "groups": new_groups,
            "item_type": 'slave'
        }
        
        # 4. (Step removed - already done in loop above)

        # 5. Create UI Items
        new_slave_item = QStandardItem(self._format_slave_label(new_id))
        new_slave_item.setData(new_slave_info, Qt.UserRole)
        
        # Recreate group items
        for group in new_slave_info['groups']:
            reg_type = group['reg_type']
            start = group['start_addr']
            size = group['size']
            start_disp = RegisterValidator.address_to_display(start, reg_type)
            end_disp = RegisterValidator.address_to_display(start + size - 1, reg_type)
            name = group.get('group_name', '')
            
            disp_name = self._format_register_group_label(group.get('register_id'), reg_type.upper(), start_disp, end_disp, name)
            group_item = QStandardItem(disp_name)
            group_item.setData(group, Qt.UserRole)
            new_slave_item.appendRow(group_item)

        conn_item.appendRow(new_slave_item)
        
        # Update connection info
        conn_info = conn_item.data(Qt.UserRole)
        conn_info['slaves'].append(new_slave_info)
        conn_item.setData(conn_info, Qt.UserRole)
        
        self.slave_added.emit(new_id, conn_item.text())

    def clear_connections(self):
        """Remove all connections from the tree."""
        self.tree_model.removeRows(0, self.tree_model.rowCount())
        self.tree_model.setHorizontalHeaderLabels([
            QCoreApplication.translate('ConnectionTreeView', 'Connections')
        ])
        try:
            self.tree_view.clearSelection()
        except Exception:
            pass

    def restore_connections(self, connections_data: List[Dict[str, Any]]):
        """Restore full connection tree from serialized configuration."""
        self.clear_connections()
        for conn_data in connections_data or []:
            try:
                self._restore_connection(conn_data)
            except Exception as exc:
                self.logger.error("Failed to restore connection: %s", exc)

    def _restore_connection(self, conn_data: Dict[str, Any]):
        if not isinstance(conn_data, dict):
            return

        is_serial = conn_data.get('type') == 'serial' or bool(conn_data.get('serial_port'))
        conn_info = {
            'slaves': [],
            'is_open': False,
            'item_type': 'connection'
        }

        if is_serial:
            protocol = (conn_data.get('protocol') or 'rtu').lower()
            serial_port = conn_data.get('serial_port', 'COM1')
            baudrate = conn_data.get('baudrate', 9600)
            conn_info.update({
                'protocol': protocol,
                'serial_port': serial_port,
                'baudrate': baudrate
            })
            node_text = f"{protocol.upper()}: {serial_port} @ {baudrate}"
        else:
            address = conn_data.get('address', '127.0.0.1')
            port = conn_data.get('port', 502)
            conn_info.update({
                'address': address,
                'port': port
            })
            node_text = f"{address}:{port}"

        conn_item = QStandardItem(node_text)
        conn_item.setIcon(self._create_status_icon(conn_info['is_open']))

        for slave_data in conn_data.get('slaves', []):
            slave_item = self._restore_slave(slave_data)
            if slave_item:
                conn_item.appendRow(slave_item)
                slave_info = slave_item.data(Qt.UserRole)
                conn_info['slaves'].append(slave_info)

        # Store populated connection info with slave definitions
        conn_item.setData(conn_info, Qt.UserRole)

        self.tree_model.appendRow(conn_item)
        self.tree_view.expand(self.tree_model.indexFromItem(conn_item))

    def _restore_slave(self, slave_data: Dict[str, Any]) -> Optional[QStandardItem]:
        if not isinstance(slave_data, dict):
            return None
        try:
            slave_id = int(slave_data.get('slave_id', 1))
        except Exception:
            slave_id = 1
        name = slave_data.get('name', '')
        register_map_data = slave_data.get('register_map') or {}
        try:
            register_map = RegisterMap.from_dict(register_map_data)
        except Exception:
            register_map = RegisterMap()

        slave_item = QStandardItem(self._format_slave_label(slave_id, name))
        slave_info = {
            "slave_id": slave_id,
            "name": name,
            "register_map": register_map,
            "groups": [],
            "item_type": 'slave'
        }
        slave_item.setData(slave_info, Qt.UserRole)

        self._restore_slave_groups(slave_item, slave_info, slave_data)
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        return slave_item

    def _restore_slave_groups(self, slave_item: QStandardItem, slave_info: Dict[str, Any], slave_data: Dict[str, Any]):
        register_map = slave_info.get("register_map")
        for group_data in slave_data.get('register_groups', []):
            if not isinstance(group_data, dict):
                continue
            reg_type = group_data.get('reg_type')
            start_addr = group_data.get('start_addr')
            size = group_data.get('size')
            if reg_type is None or start_addr is None or size is None:
                continue
            group_id = group_data.get('group_id') or group_data.get('register_id') or 1
            group_meta = {
                "register_id": group_id,
                "reg_type": reg_type,
                "start_addr": start_addr,
                "size": size,
                "parent_slave_map": register_map,
                "group_name": group_data.get('group_name', ''),
                "description": group_data.get('description', ''),
                "template_name": group_data.get('template_name', ''),
                "item_type": 'register_group'
            }
            start_display = RegisterValidator.address_to_display(start_addr, reg_type)
            end_display = RegisterValidator.address_to_display(start_addr + size - 1, reg_type)
            display_name = self._format_register_group_label(group_id, str(reg_type).upper(), start_display, end_display, group_meta.get('group_name', ''))
            group_item = QStandardItem(display_name)
            group_item.setData(group_meta, Qt.UserRole)
            slave_item.appendRow(group_item)
            slave_info["groups"].append(group_meta)

        for multi_group in slave_data.get('multi_type_groups', []):
            self._restore_multi_type_group(slave_item, slave_info, multi_group)

    def _restore_multi_type_group(self, slave_item: QStandardItem, slave_info: Dict[str, Any], multi_group: Dict[str, Any]):
        if not isinstance(multi_group, dict):
            return
        group_id = multi_group.get('group_id', 0)
        group_name = multi_group.get('name', '')
        display_name = self._format_multi_group_label(group_id, group_name)
        multi_item = QStandardItem(display_name)
        multi_data = dict(multi_group)
        multi_data['item_type'] = 'multi_type_group'
        multi_item.setData(multi_data, Qt.UserRole)

        for block in multi_group.get('blocks', []):
            if not isinstance(block, dict):
                continue
            reg_type = block.get('reg_type', 'hr')
            size = block.get('size', 0)
            start_addr = block.get('start_addr', 0)
            end_addr = start_addr + max(size - 1, 0)
            block_display = self._format_block_label(str(reg_type).upper(), start_addr, end_addr)
            block_item = QStandardItem(block_display)
            block_meta = {
                "register_id": group_id,
                "reg_type": reg_type,
                "start_addr": start_addr,
                "size": size,
                "parent_slave_map": slave_info.get("register_map"),
                "group_name": f"{group_name} - {str(reg_type).upper()}",
                "is_multi_type_block": True,
                "parent_multi_group": group_id,
                "item_type": 'register_block'
            }
            block_item.setData(block_meta, Qt.UserRole)
            multi_item.appendRow(block_item)

        slave_item.appendRow(multi_item)
        slave_info["groups"].append(multi_data)
    
    def _add_register_group_menu_actions(self, menu: QMenu, item: QStandardItem):
        """Add context menu actions for register group items."""
        rename_action = QAction(self.tr("Rename Group"), self.tree_view)
        rename_action.triggered.connect(lambda: self._rename_group(item))
        menu.addAction(rename_action)
        
        menu.addSeparator()
        
        duplicate_action = QAction(self.tr("Duplicate Group"), self.tree_view)
        duplicate_action.triggered.connect(lambda: self._duplicate_group(item))
        menu.addAction(duplicate_action)
        
        split_action = QAction(self.tr("Split Group"), self.tree_view)
        split_action.triggered.connect(lambda: self._split_group(item))
        menu.addAction(split_action)
        
        convert_action = QAction(self.tr("Convert Type"), self.tree_view)
        convert_action.triggered.connect(lambda: self._convert_group_type(item))
        menu.addAction(convert_action)
        
        menu.addSeparator()
        
        export_action = QAction(self.tr("Export Group"), self.tree_view)
        export_action.triggered.connect(lambda: self._export_group(item))
        menu.addAction(export_action)
        
        import_action = QAction(self.tr("Import Group"), self.tree_view)
        import_action.triggered.connect(lambda: self._import_group(item))
        menu.addAction(import_action)
        
        menu.addSeparator()
        
        remove_action = QAction(self.tr("Remove Group"), self.tree_view)
        remove_action.triggered.connect(lambda: self._remove_group(item))
        menu.addAction(remove_action)
    
    def _add_multi_type_group_menu_actions(self, menu: QMenu, item: QStandardItem):
        """Add context menu actions for multi-type group items."""
        rename_action = QAction(self.tr("Rename Group"), self.tree_view)
        rename_action.triggered.connect(lambda: self._rename_multi_type_group(item))
        menu.addAction(rename_action)
        
        menu.addSeparator()
        
        export_action = QAction(self.tr("Export Group"), self.tree_view)
        export_action.triggered.connect(lambda: self._export_group(item))
        menu.addAction(export_action)
        
        menu.addSeparator()
        
        remove_action = QAction(self.tr("Remove Group"), self.tree_view)
        remove_action.triggered.connect(lambda: self._remove_group(item))
        menu.addAction(remove_action)
    
    def _select_item_and_add_slave(self, item: QStandardItem):
        """Select item and add slave."""
        index = self.tree_model.indexFromItem(item)
        self.tree_view.setCurrentIndex(index)
        self.add_slave_to_selected_connection()
    
    def _select_item_and_add_group(self, item: QStandardItem):
        """Select item and add register group."""
        index = self.tree_model.indexFromItem(item)
        self.tree_view.setCurrentIndex(index)
        self.add_register_group_to_selected_slave()
    
    def _select_item_and_add_multi_group(self, item: QStandardItem):
        """Select item and add multi-type group."""
        index = self.tree_model.indexFromItem(item)
        self.tree_view.setCurrentIndex(index)
        self.add_multi_type_group_to_selected_slave()
    
    def _remove_connection(self, item: QStandardItem):
        """Remove connection from tree."""
        reply = QMessageBox.question(self.tree_view, self.tr("Confirm Removal"), 
            self.tr("Remove connection {}?").format(item.text()), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # If connection is open, request to close server first
            conn_info = item.data(Qt.UserRole)
            if conn_info and conn_info.get('is_open'):
                try:
                    self.close_connection_requested.emit(conn_info)
                except Exception:
                    pass
            self.tree_model.removeRow(item.row())
    
    def _remove_slave(self, item: QStandardItem):
        """Remove slave from tree."""
        reply = QMessageBox.question(self.tree_view, self.tr("Confirm Removal"), 
            self.tr("Remove {}?").format(item.text()), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Update connection info by removing this slave
            try:
                connection_item = item.parent()
                conn_info = connection_item.data(Qt.UserRole) if connection_item else None
                slave_info = item.data(Qt.UserRole)
                if conn_info and isinstance(conn_info, dict) and 'slaves' in conn_info and isinstance(slave_info, dict):
                    slave_id = slave_info.get('slave_id')
                    if slave_id is not None:
                        # Filter out the slave by ID
                        conn_info['slaves'] = [s for s in conn_info['slaves'] if s.get('slave_id') != slave_id]
                        connection_item.setData(conn_info, Qt.UserRole)
                
                # Optional: clear registers in the removed slave's map to free memory
                if slave_info and 'register_map' in slave_info:
                    try:
                        reg_map = slave_info['register_map']
                        reg_map.clear_all()
                    except Exception:
                        pass
            except Exception:
                pass

            # Refresh server context if connection is open (do this before removing the UI node)
            self._refresh_server_context_if_running(item)

            # Remove from UI tree
            parent_item = item.parent()
            parent_item.removeRow(item.row())
    
    def _remove_group(self, item: QStandardItem):
        """Remove register group from tree and register map."""
        reply = QMessageBox.question(self.tree_view, self.tr("Confirm Removal"), 
            self.tr("Remove {}?").format(item.text()), QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            # Get group data to remove registers from the map
            group_data = item.data(Qt.UserRole)
            if group_data:
                # Get the slave's register map
                slave_item = item.parent()
                slave_info = slave_item.data(Qt.UserRole)
                if slave_info and "register_map" in slave_info:
                    register_map = slave_info["register_map"]
                    
                    # Remove the registers from the map
                    reg_type = group_data.get("reg_type")
                    start_addr = group_data.get("start_addr")
                    size = group_data.get("size", 1)
                    
                    if reg_type and start_addr is not None:
                        for i in range(size):
                            addr = start_addr + i
                            register_map.remove_register(reg_type, addr)
                        
                        self.logger.info("Removed %d %s registers starting at address %d", size, reg_type.upper(), start_addr)
                    
                    # Remove group from slave's group list
                    groups_list = slave_info.get("groups", [])
                    register_id = group_data.get("register_id")
                    if register_id is not None:
                        # Find and remove the group with matching register_id
                        slave_info["groups"] = [g for g in groups_list if g.get("register_id") != register_id]
                        slave_item.setData(slave_info, Qt.UserRole)
            
            # Remove from UI tree
            slave_item = item.parent()
            item.parent().removeRow(item.row())
            
            # Refresh server context if connection is open
            self._refresh_server_context_if_running(slave_item)
    
    def _rename_group(self, item: QStandardItem):
        """Rename register group."""
        group_data = item.data(Qt.UserRole)
        if not group_data:
            return
            
        current_name = group_data.get('group_name', '')
        
        new_name, ok = QInputDialog.getText(
            self.tree_view,
            self.tr("Rename Group"),
            self.tr("Enter new name for the group:"),
            text=current_name
        )
        
        if ok and new_name.strip() != current_name:
            new_name = new_name.strip()
            
            # Update group data
            group_data['group_name'] = new_name
            item.setData(group_data, Qt.UserRole)
            
            # Update slave's group list
            slave_item = item.parent()
            slave_info = slave_item.data(Qt.UserRole)
            if slave_info:
                groups_list = slave_info.get("groups", [])
                register_id = group_data.get("register_id")
                
                # Find and update the group in the slave's list
                for group in groups_list:
                    if group.get("register_id") == register_id:
                        group['group_name'] = new_name
                        break
                
                slave_item.setData(slave_info, Qt.UserRole)
            
            # Update the display text
            reg_type_upper = group_data.get('reg_type', '').upper()
            start_addr = group_data.get('start_addr', 0)
            size = group_data.get('size', 1)
            end_addr = start_addr + size - 1
            register_id = group_data.get('register_id', 1)
            
            start_display = RegisterValidator.address_to_display(start_addr, group_data.get('reg_type', 'hr'))
            end_display = RegisterValidator.address_to_display(end_addr, group_data.get('reg_type', 'hr'))
            display_name = self._format_register_group_label(register_id, reg_type_upper, start_display, end_display, new_name)
            item.setText(display_name)
    
    def _rename_multi_type_group(self, item: QStandardItem):
        """Rename multi-type register group."""
        group_data = item.data(Qt.UserRole)
        if not group_data:
            return
            
        current_name = group_data.get('name', '')
        
        new_name, ok = QInputDialog.getText(
            self.tree_view,
            self.tr("Rename Multi-Type Group"),
            self.tr("Enter new name for the group:"),
            text=current_name
        )
        
        if ok and new_name.strip() != current_name:
            new_name = new_name.strip()
            
            # Update group data
            group_data['name'] = new_name
            item.setData(group_data, Qt.UserRole)
            
            # Update slave's group list
            slave_item = item.parent()
            slave_info = slave_item.data(Qt.UserRole)
            if slave_info:
                groups_list = slave_info.get("groups", [])
                group_id = group_data.get('group_id')
                
                # Find and update the group in the slave's list
                for group in groups_list:
                    if group.get("group_id") == group_id:
                        group['name'] = new_name
                        break
                
                slave_item.setData(slave_info, Qt.UserRole)
            
            # Update the display text
            group_id = group_data.get('group_id', 1)
            display_name = self._format_multi_group_label(group_id, new_name)
            item.setText(display_name)
    
    def _duplicate_group(self, item: QStandardItem):
        """Duplicate register group."""
        group_data = item.data(Qt.UserRole)
        if group_data:
            slave_item = item.parent()
            slave_info = slave_item.data(Qt.UserRole)
            register_map = slave_info["register_map"]
            self.group_manager.duplicate_group(group_data, register_map)
    
    def _split_group(self, item: QStandardItem):
        """Split register group."""
        group_data = item.data(Qt.UserRole)
        if group_data:
            size = group_data['size']
            if size < 2:
                QMessageBox.warning(self.tree_view, self.tr("Cannot Split"), self.tr("Group must have at least 2 registers to split"))
                return
            
            split_point, ok = QInputDialog.getInt(self.tree_view, self.tr("Split Group"), 
                self.tr("Split point (1-{}):").format(size-1), size//2, 1, size-1)
            if ok:
                self.group_manager.split_group(group_data, split_point)
    
    def _convert_group_type(self, item: QStandardItem):
        """Convert register group type."""
        group_data = item.data(Qt.UserRole)
        if group_data:
            old_type = group_data['reg_type']
            # Show dialog to select new type
            from PyQt5.QtWidgets import QInputDialog
            items = ['hr', 'ir'] if old_type in ['hr', 'ir'] else []
            if not items:
                QMessageBox.warning(self.tree_view, self.tr("Cannot Convert"), self.tr("Only HR and IR types can be converted"))
                return
            
            new_type, ok = QInputDialog.getItem(self.tree_view, self.tr("Convert Type"), 
                self.tr("Select new register type:"), items, 0, False)
            if ok and new_type != old_type:
                self.group_manager.convert_group_type(group_data, new_type)
    
    def _export_group(self, item: QStandardItem):
        """Export register group."""
        group_data = item.data(Qt.UserRole)
        if group_data:
            self.group_manager.export_group(group_data)
    
    def _import_group(self, item: QStandardItem):
        """Import register group."""
        from PyQt5.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(self.tree_view, 
            self.tr("Import Register Group"), "", self.tr("JSON Files (*.json);;All Files (*)"))
        if filename:
            slave_item = item.parent()
            slave_info = slave_item.data(Qt.UserRole)
            register_map = slave_info["register_map"]
            self.group_manager.import_group(filename, register_map)
    
    def _open_bulk_operations(self, item: QStandardItem):
        """Open bulk operations dialog."""
        try:
            slave_info = item.data(Qt.UserRole)
            if not slave_info:
                QMessageBox.warning(self.tree_view, self.tr("Error"), self.tr("No slave data found"))
                return
                
            register_map = slave_info.get("register_map")
            if not register_map:
                QMessageBox.warning(self.tree_view, self.tr("Error"), self.tr("No register map found for this slave"))
                return
            
            # Import and create the manual bulk operations dialog (guaranteed to work)
            from modbusx.ui.bulk_operations_manual import ManualBulkOperationsDialog
            
            dialog = ManualBulkOperationsDialog(register_map, self.tree_view)
            dialog.operation_completed.connect(self._on_bulk_operation_completed)
            dialog.exec_()
            
        except Exception as e:
            QMessageBox.critical(self.tree_view, self.tr("Bulk Operations Error"), 
                self.tr("Failed to open bulk operations dialog:\n{}").format(str(e)))
            import traceback
            traceback.print_exc()
    
    def _on_bulk_operation_completed(self, success: bool, message: str):
        """Handle bulk operation completion."""
        if success:
            # Emit signal to refresh UI if needed
            self.register_group_added.emit(-1, "Bulk operation completed")
    
    def _add_group_from_dialog(self, slave_item: QStandardItem, group_data: Dict):
        """Add group from enhanced dialog."""
        slave_info = slave_item.data(Qt.UserRole)
        register_map = slave_info["register_map"]
        
        # Create register group using service directly
        # Use RegisterGroupService directly instead of controller
        try:
            # Final guard: prevent duplicate/overlapping ranges regardless of dialog choices
            try:
                from ..services.register_validator import RegisterValidator
                conflicts = RegisterValidator.check_address_conflicts(
                    register_map,
                    group_data['reg_type'],
                    group_data['start_addr'],
                    group_data['size']
                )
                if conflicts:
                    from PyQt5.QtWidgets import QMessageBox
                    start = group_data['start_addr']
                    end = start + group_data['size'] - 1
                    QMessageBox.warning(
                        self.tree_view,
                        self.tr("Address Conflict"),
                        self.tr("Cannot create group; addresses already in use for {} ({}..{}). Please choose a free range or auto-adjust.").format(group_data['reg_type'].upper(), start, end)
                    )
                    return
            except Exception:
                # If conflict check fails, proceed to service validation
                pass

            service = RegisterGroupService()
            group = service.create_single_type_group(
                register_map=register_map,
                reg_type=group_data['reg_type'].lower(),  # Ensure lowercase for RegisterMap
                start_addr=group_data['start_addr'],
                size=group_data['size'],
                group_name=group_data.get('group_name', ''),
                description=group_data.get('description', ''),
                default_value=group_data.get('default_value', 0),
                alias_prefix=group_data.get('alias_prefix', ''),
                template_name=group_data.get('template_name', ''),
                skip_conflict_check=group_data.get('auto_adjusted', False)
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error("Register group creation error: %s", error_msg)
            self.logger.error("Group data that failed: %s", group_data)
            import traceback
            self.logger.error("Full traceback: %s", traceback.format_exc())
            QMessageBox.warning(self.tree_view, self.tr("Group Creation Error"), self.tr("Failed to create register group:\n{}").format(error_msg))
            group = None
        
        if not group:
            self.logger.warning("Failed to create register group: %s", group_data)
            return
        
        # Apply aliases if provided
        if group_data.get('alias_prefix'):
            reg_dict = getattr(register_map, group_data['reg_type'])
            for i in range(group_data['size']):
                addr = group_data['start_addr'] + i
                if addr in reg_dict:
                    reg_dict[addr].alias = f"{group_data['alias_prefix']}{i+1}"
        
        # Find the next available group ID starting from 1
        existing_ids = {g.get("register_id", 0) for g in slave_info.get("groups", [])}
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        group_meta = {
            "register_id": next_id,
            "reg_type": group_data['reg_type'],
            "start_addr": group_data['start_addr'],
            "size": group_data['size'],
            "parent_slave_map": register_map,
            "group_name": group_data.get('group_name', ''),
            "description": group_data.get('description', ''),
            "template_name": group_data.get('template_name', ''),
            "item_type": 'register_group'
        }
        
        # Create tree item with proper address display format
        reg_type_upper = group_data['reg_type'].upper()
        start_display = RegisterValidator.address_to_display(group_data['start_addr'], group_data['reg_type'])
        end_display = RegisterValidator.address_to_display(group_data['start_addr'] + group_data['size'] - 1, group_data['reg_type'])
        group_name = group_data.get('group_name', '')
        display_name = self._format_register_group_label(next_id, reg_type_upper, start_display, end_display, group_name)
        
        reg_item = QStandardItem(display_name)
        reg_item.setData(group_meta, Qt.UserRole)
        slave_item.appendRow(reg_item)
        slave_info["groups"].append(group_meta)
        slave_item.setData(slave_info, Qt.UserRole)
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        
        self.register_group_added.emit(next_id, slave_item.text())
        
        # Refresh server context if connection is open
        self._refresh_server_context_if_running(slave_item)
    
    def _add_multi_type_group_from_dialog(self, slave_item: QStandardItem, multi_group: MultiTypeRegisterGroup):
        """Add multi-type group from dialog."""
        slave_info = slave_item.data(Qt.UserRole)
        register_map = slave_info["register_map"]
        
        # Create multi-type register group using service directly  
        # Use RegisterGroupService directly instead of controller
        try:
            service = RegisterGroupService()
            # Convert blocks to proper format
            blocks_data = []
            for block in multi_group.register_blocks:
                blocks_data.append({
                    'reg_type': block.reg_type.lower(),  # Ensure lowercase for RegisterMap
                    'start_addr': block.start_addr,
                    'size': block.size,
                    'name': block.name,
                    'default_value': block.default_value
                })
            
            created_group = service.create_multi_type_group(
                register_map=register_map,
                group_name=multi_group.name,
                description=multi_group.description,
                blocks=blocks_data
            )
        except Exception as e:
            error_msg = str(e)
            self.logger.error("Multi-type register group creation error: %s", error_msg)
            QMessageBox.warning(self.tree_view, self.tr("Group Creation Error"), self.tr("Failed to create multi-type register group:\n{}").format(error_msg))
            created_group = None
        
        if not created_group:
            self.logger.warning("Failed to create multi-type register group: %s", multi_group.name)
            return
        
        # Find the next available group ID starting from 1
        existing_ids = {g.get("register_id", 0) for g in slave_info.get("groups", [])}
        next_id = 1
        while next_id in existing_ids:
            next_id += 1
        display_name = self._format_multi_group_label(next_id, multi_group.name)
        
        multi_item = QStandardItem(display_name)
        multi_data = multi_group.to_dict()
        multi_data['item_type'] = 'multi_type_group'
        multi_item.setData(multi_data, Qt.UserRole)
        
        # Add sub-items for each register block
        for block in multi_group.register_blocks:
            reg_type_upper = block['reg_type'].upper()
            end_addr = block['start_addr'] + block['size'] - 1
            block_name = self._format_block_label(reg_type_upper, block['start_addr'], end_addr)
            block_item = QStandardItem(block_name)
            
            # Create individual group metadata for compatibility
            block_meta = {
                "register_id": next_id,
                "reg_type": block['reg_type'],
                "start_addr": block['start_addr'],
                "size": block['size'],
                "parent_slave_map": register_map,
                "group_name": f"{multi_group.name} - {reg_type_upper}",
                "is_multi_type_block": True,
                "parent_multi_group": multi_group.group_id
            }
            block_meta["item_type"] = 'register_block'
            block_item.setData(block_meta, Qt.UserRole)
            multi_item.appendRow(block_item)
        
        slave_item.appendRow(multi_item)
        slave_info["groups"].append(multi_group.to_dict())
        slave_item.setData(slave_info, Qt.UserRole)
        self.tree_view.expand(self.tree_model.indexFromItem(slave_item))
        self.tree_view.expand(self.tree_model.indexFromItem(multi_item))
        
        self.register_group_added.emit(next_id, slave_item.text())
        
        # Refresh server context if connection is open
        self._refresh_server_context_if_running(slave_item)
    
    def _handle_group_duplicated(self, group_data: Dict):
        """Handle group duplication completion."""
        # Find the slave item and add the new group
        current_index = self.tree_view.currentIndex()
        if current_index.isValid():
            current_item = self.tree_model.itemFromIndex(current_index)
            if current_item and self._is_register_group_item(current_item):
                slave_item = current_item.parent()
                self._add_group_from_dialog(slave_item, group_data)
    
    def _handle_group_split(self, group_list: List[Dict]):
        """Handle group split completion."""
        current_index = self.tree_view.currentIndex()
        if current_index.isValid():
            current_item = self.tree_model.itemFromIndex(current_index)
            if current_item and self._is_register_group_item(current_item):
                slave_item = current_item.parent()
                # Remove original group
                current_item.parent().removeRow(current_item.row())
                # Add new groups
                for group_data in group_list:
                    self._add_group_from_dialog(slave_item, group_data)
    
    def _handle_group_merged(self, group_data: Dict):
        """Handle group merge completion."""
        current_index = self.tree_view.currentIndex()
        if current_index.isValid():
            current_item = self.tree_model.itemFromIndex(current_index)
            if current_item and self._is_register_group_item(current_item):
                slave_item = current_item.parent()
                self._add_group_from_dialog(slave_item, group_data)
    
    def _refresh_server_context_if_running(self, slave_item: QStandardItem):
        """Refresh server context if connection is open."""
        # Find the connection item (parent of slave_item)
        connection_item = slave_item.parent()
        if not connection_item:
            return
            
        connection_info = connection_item.data(Qt.UserRole)
        if not connection_info:
            return
        
        # Check if connection is open
        if not connection_info.get('is_open', False):
            return
            
        try:
            # Debug: Show which slave is triggering the refresh
            slave_info = slave_item.data(Qt.UserRole)
            unit_id = slave_info.get('unit_id', 'Unknown') if slave_info else 'Unknown'
            self.logger.info(f"Triggering server context refresh for Unit ID {unit_id}")
            # Emit to MainWindow, which owns the ServerManager instance
            try:
                self.refresh_connection_requested.emit(connection_info)
            except Exception:
                pass
        except Exception as e:
            self.logger.error(f"Error refreshing server context: {e}")

    def refresh_register_group_addresses(self):
        """Refresh all register group address displays in tree for current address mode."""
        self.logger.debug("Refreshing register group addresses for address mode change")
        
        for i in range(self.tree_model.rowCount()):
            connection_item = self.tree_model.item(i, 0)
            if not connection_item:
                continue
                
            # Iterate through slaves
            for j in range(connection_item.rowCount()):
                slave_item = connection_item.child(j, 0)
                if not slave_item:
                    continue
                    
                # Iterate through register groups  
                for k in range(slave_item.rowCount()):
                    group_item = slave_item.child(k, 0)
                    if not group_item:
                        continue
                        
                    group_meta = group_item.data(Qt.UserRole)
                    if isinstance(group_meta, dict) and "reg_type" in group_meta:
                        # Update the display text with new address format
                        self._update_register_group_label(group_item, group_meta)

    def _update_register_group_label(self, group_item: QStandardItem, group_meta: Dict):
        """Update register group label with current address format."""
        reg_type = group_meta['reg_type']
        start_addr = group_meta['start_addr'] 
        size = group_meta['size']
        register_id = group_meta.get('register_id', 1)
        group_name = group_meta.get('group_name', '')
        
        # Use RegisterValidator to get proper display format
        start_display = RegisterValidator.address_to_display(start_addr, reg_type)
        end_display = RegisterValidator.address_to_display(start_addr + size - 1, reg_type)
        
        # Build display name matching the format used in _add_group_from_dialog
        reg_type_upper = reg_type.upper()
        
        display_name = self._format_register_group_label(register_id, reg_type_upper, start_display, end_display, group_name)
        group_item.setText(display_name)

    def retranslate_ui(self):
        """Refreshes the tree view strings after language change."""
        self.tree_model.setHorizontalHeaderLabels([
            QCoreApplication.translate('ConnectionTreeView', 'Connections')
        ])
        
        # Iterate over connections
        for i in range(self.tree_model.rowCount()):
            conn_item = self.tree_model.item(i, 0)
            if not conn_item: continue
            
            # Refresh connection status (icon/text)
            conn_info = conn_item.data(Qt.UserRole)
            if conn_info:
                self.update_connection_status(conn_item, conn_info.get('is_open', False))
            
            # Iterate over slaves
            for j in range(conn_item.rowCount()):
                slave_item = conn_item.child(j, 0)
                if not slave_item: continue
                
                slave_info = slave_item.data(Qt.UserRole)
                if slave_info:
                    sid = slave_info.get('slave_id', '?')
                    name = slave_info.get('name', '')
                    # Update Slave ID text
                    slave_item.setText(self._format_slave_label(sid, name))
                
                # Iterate over groups
                for k in range(slave_item.rowCount()):
                    group_item = slave_item.child(k, 0)
                    if not group_item: continue
                    
                    group_meta = group_item.data(Qt.UserRole)
                    if isinstance(group_meta, dict):
                        if "reg_type" in group_meta and not group_meta.get("is_multi_type_block"):
                            self._update_register_group_label(group_item, group_meta)
                        elif group_meta.get("is_multi_type_block"):
                            start_addr = group_meta.get('start_addr', 0)
                            size = group_meta.get('size', 1)
                            end_addr = start_addr + size - 1
                            reg_type_upper = group_meta.get('reg_type', '').upper()
                            group_item.setText(self._format_block_label(reg_type_upper, start_addr, end_addr))
                        elif "register_blocks" in group_meta:
                            # Multi-type group root
                            group_id = group_meta.get('group_id', 1)
                            name = group_meta.get('name', '')
                            group_item.setText(self._format_multi_group_label(group_id, name))
