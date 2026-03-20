"""
Connection Tree View Component

Pure UI component for displaying connections, slaves, and register groups.
"""

from PyQt5.QtWidgets import QTreeView, QMenu, QAction
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from typing import Optional, Dict, List, Any

class ConnectionTreeView(QTreeView):
    """Pure UI component for connection tree display."""
    
    # UI-only signals (no business logic)
    item_selected = pyqtSignal(str, dict)        # item_type, item_data
    item_double_clicked = pyqtSignal(str, dict)  # item_type, item_data
    context_menu_requested = pyqtSignal(str, dict, object)  # item_type, item_data, position
    
    # Context menu action signals
    add_connection_requested = pyqtSignal()
    add_slave_requested = pyqtSignal(str)        # connection_key
    add_register_group_requested = pyqtSignal(str, int)  # connection_key, slave_id
    add_multi_type_group_requested = pyqtSignal(str, int)  # connection_key, slave_id
    remove_item_requested = pyqtSignal(str, dict)  # item_type, item_data
    open_connection_requested = pyqtSignal(str)  # connection_key
    close_connection_requested = pyqtSignal(str)  # connection_key
    bulk_operations_requested = pyqtSignal(str, int)  # connection_key, slave_id
    duplicate_group_requested = pyqtSignal(dict)  # group_data
    split_group_requested = pyqtSignal(dict)     # group_data
    export_group_requested = pyqtSignal(dict)    # group_data
    import_group_requested = pyqtSignal(str, int)  # connection_key, slave_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        
        # Item tracking
        self._item_data_cache = {}  # Maps model index to item data
    
    def _setup_ui(self):
        """Setup the UI components."""
        # Create model
        self.model = QStandardItemModel(self)
        self.model.setHorizontalHeaderLabels([self.tr('Connections')])
        self.setModel(self.model)
        
        # Configure tree
        self.setRootIsDecorated(True)
        self.setAlternatingRowColors(True)
        self.setExpandsOnDoubleClick(False)  # We handle double-click manually
        
        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
    
    def _connect_signals(self):
        """Connect internal UI signals."""
        self.selectionModel().currentChanged.connect(self._on_selection_changed)
        self.doubleClicked.connect(self._on_double_clicked)
        self.customContextMenuRequested.connect(self._on_context_menu)
    
    def changeEvent(self, event):
        if event.type() == QEvent.LanguageChange:
            try:
                self.model.setHorizontalHeaderLabels([self.tr('Connections')])
            except Exception:
                pass
        super().changeEvent(event)
    
    def populate_connections(self, connections_data: List[Dict[str, Any]]):
        """Populate tree with connection data."""
        self.model.clear()
        self.model.setHorizontalHeaderLabels([self.tr('Connections')])
        self._item_data_cache.clear()
        
        for conn_data in connections_data:
            self._add_connection_item(conn_data)
    
    def add_connection(self, connection_data: Dict[str, Any]) -> QStandardItem:
        """Add a single connection to the tree."""
        return self._add_connection_item(connection_data)
    
    def remove_connection(self, connection_key: str) -> bool:
        """Remove a connection from the tree."""
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if item and self._get_item_data(item).get('connection_key') == connection_key:
                self.model.removeRow(row)
                return True
        return False
    
    def update_connection_status(self, connection_key: str, is_open: bool):
        """Update connection status display."""
        item = self._find_connection_item(connection_key)
        if item:
            conn_data = self._get_item_data(item)
            display_text = connection_key
            if is_open:
                display_text += " (OPEN)"
            item.setText(display_text)
            
            # Update cached data
            conn_data['is_open'] = is_open
            self._set_item_data(item, conn_data)
    
    def add_slave(self, connection_key: str, slave_data: Dict[str, Any]) -> Optional[QStandardItem]:
        """Add a slave to a connection."""
        conn_item = self._find_connection_item(connection_key)
        if not conn_item:
            return None
        
        return self._add_slave_item(conn_item, slave_data)
    
    def remove_slave(self, connection_key: str, slave_id: int) -> bool:
        """Remove a slave from a connection."""
        conn_item = self._find_connection_item(connection_key)
        if not conn_item:
            return False
        
        for row in range(conn_item.rowCount()):
            slave_item = conn_item.child(row)
            slave_data = self._get_item_data(slave_item)
            if slave_data.get('slave_id') == slave_id:
                conn_item.removeRow(row)
                return True
        return False
    
    def add_register_group(self, connection_key: str, slave_id: int, group_data: Dict[str, Any]) -> Optional[QStandardItem]:
        """Add a register group to a slave."""
        slave_item = self._find_slave_item(connection_key, slave_id)
        if not slave_item:
            return None
        
        return self._add_group_item(slave_item, group_data)
    
    def remove_register_group(self, connection_key: str, slave_id: int, group_id: int) -> bool:
        """Remove a register group from a slave."""
        slave_item = self._find_slave_item(connection_key, slave_id)
        if not slave_item:
            return False
        
        for row in range(slave_item.rowCount()):
            group_item = slave_item.child(row)
            group_data = self._get_item_data(group_item)
            if group_data.get('group_id') == group_id:
                slave_item.removeRow(row)
                return True
        return False
    
    def get_selected_item_info(self) -> Optional[tuple]:
        """Get information about the selected item."""
        current_index = self.currentIndex()
        if not current_index.isValid():
            return None
        
        item = self.model.itemFromIndex(current_index)
        item_type = self._determine_item_type(item)
        item_data = self._get_item_data(item)
        
        return (item_type, item_data)
    
    def expand_connection(self, connection_key: str):
        """Expand a connection in the tree."""
        item = self._find_connection_item(connection_key)
        if item:
            index = self.model.indexFromItem(item)
            self.expand(index)
    
    def expand_slave(self, connection_key: str, slave_id: int):
        """Expand a slave in the tree."""
        slave_item = self._find_slave_item(connection_key, slave_id)
        if slave_item:
            index = self.model.indexFromItem(slave_item)
            self.expand(index)
    
    def _add_connection_item(self, connection_data: Dict[str, Any]) -> QStandardItem:
        """Add connection item to tree."""
        connection_key = f"{connection_data['address']}:{connection_data['port']}"
        display_text = connection_key
        if connection_data.get('is_open', False):
            display_text += " (OPEN)"
        
        conn_item = QStandardItem(display_text)
        
        # Store connection data
        item_data = {
            'item_type': 'connection',
            'connection_key': connection_key,
            **connection_data
        }
        self._set_item_data(conn_item, item_data)
        
        # Add slaves
        for slave_data in connection_data.get('slaves', []):
            self._add_slave_item(conn_item, slave_data)
        
        self.model.appendRow(conn_item)
        return conn_item
    
    def _add_slave_item(self, conn_item: QStandardItem, slave_data: Dict[str, Any]) -> QStandardItem:
        """Add slave item to connection."""
        slave_id = slave_data['slave_id']
        slave_name = slave_data.get('name', f"Slave {slave_id}")
        display_text = f"Slave ID: {slave_id}"
        if slave_name != f"Slave {slave_id}":
            display_text += f" ({slave_name})"
        
        slave_item = QStandardItem(display_text)
        
        # Store slave data
        item_data = {
            'item_type': 'slave',
            'slave_id': slave_id,
            'connection_key': self._get_item_data(conn_item).get('connection_key'),
            **slave_data
        }
        self._set_item_data(slave_item, item_data)
        
        # Add register groups
        for group_data in slave_data.get('register_groups', []):
            self._add_group_item(slave_item, group_data)
        
        # Add multi-type groups
        for multi_group_data in slave_data.get('multi_type_groups', []):
            self._add_multi_group_item(slave_item, multi_group_data)
        
        conn_item.appendRow(slave_item)
        return slave_item
    
    def _add_group_item(self, slave_item: QStandardItem, group_data: Dict[str, Any]) -> QStandardItem:
        """Add register group item to slave."""
        group_id = group_data.get('group_id', 0)
        reg_type = group_data.get('reg_type', 'hr').upper()
        start_addr = group_data.get('start_addr', 0)
        size = group_data.get('size', 0)
        end_addr = start_addr + size - 1
        group_name = group_data.get('name', '')
        
        display_text = f"Register Group: {group_id}"
        if group_name:
            display_text += f" ({group_name})"
        display_text += f" [{reg_type} {start_addr}:{end_addr}]"
        
        group_item = QStandardItem(display_text)
        
        # Store group data
        item_data = {
            'item_type': 'register_group',
            'group_id': group_id,
            'connection_key': self._get_item_data(slave_item).get('connection_key'),
            'slave_id': self._get_item_data(slave_item).get('slave_id'),
            **group_data
        }
        self._set_item_data(group_item, item_data)
        
        slave_item.appendRow(group_item)
        return group_item
    
    def _add_multi_group_item(self, slave_item: QStandardItem, multi_group_data: Dict[str, Any]) -> QStandardItem:
        """Add multi-type group item to slave."""
        group_id = multi_group_data.get('group_id', 0)
        group_name = multi_group_data.get('name', '')
        
        display_text = f"Multi-Type Group: {group_id} ({group_name})"
        
        multi_item = QStandardItem(display_text)
        
        # Store multi-group data
        item_data = {
            'item_type': 'multi_type_group',
            'group_id': group_id,
            'connection_key': self._get_item_data(slave_item).get('connection_key'),
            'slave_id': self._get_item_data(slave_item).get('slave_id'),
            **multi_group_data
        }
        self._set_item_data(multi_item, item_data)
        
        # Add sub-items for each block
        for block in multi_group_data.get('blocks', []):
            block_item = self._add_block_item(multi_item, block)
        
        slave_item.appendRow(multi_item)
        return multi_item
    
    def _add_block_item(self, multi_item: QStandardItem, block_data: Dict[str, Any]) -> QStandardItem:
        """Add register block item to multi-type group."""
        reg_type = block_data.get('reg_type', 'hr').upper()
        start_addr = block_data.get('start_addr', 0)
        size = block_data.get('size', 0)
        end_addr = start_addr + size - 1
        
        display_text = f"{reg_type} Block: {start_addr}:{end_addr}"
        
        block_item = QStandardItem(display_text)
        
        # Store block data
        item_data = {
            'item_type': 'register_block',
            'connection_key': self._get_item_data(multi_item).get('connection_key'),
            'slave_id': self._get_item_data(multi_item).get('slave_id'),
            'parent_group_id': self._get_item_data(multi_item).get('group_id'),
            **block_data
        }
        self._set_item_data(block_item, item_data)
        
        multi_item.appendRow(block_item)
        return block_item
    
    def _find_connection_item(self, connection_key: str) -> Optional[QStandardItem]:
        """Find connection item by key."""
        for row in range(self.model.rowCount()):
            item = self.model.item(row)
            if self._get_item_data(item).get('connection_key') == connection_key:
                return item
        return None
    
    def _find_slave_item(self, connection_key: str, slave_id: int) -> Optional[QStandardItem]:
        """Find slave item by connection and slave ID."""
        conn_item = self._find_connection_item(connection_key)
        if not conn_item:
            return None
        
        for row in range(conn_item.rowCount()):
            slave_item = conn_item.child(row)
            slave_data = self._get_item_data(slave_item)
            if slave_data.get('slave_id') == slave_id:
                return slave_item
        return None
    
    def _determine_item_type(self, item: QStandardItem) -> str:
        """Determine the type of tree item."""
        if not item:
            return 'unknown'
        
        item_data = self._get_item_data(item)
        return item_data.get('item_type', 'unknown')
    
    def _get_item_data(self, item: QStandardItem) -> Dict[str, Any]:
        """Get data associated with a tree item."""
        if not item:
            return {}
        
        # Try to get from cache first
        index = self.model.indexFromItem(item)
        cache_key = (index.row(), index.column(), id(index.parent()))
        
        cached_data = self._item_data_cache.get(cache_key)
        if cached_data:
            return cached_data
        
        # Fallback to item data
        data = item.data(Qt.UserRole)
        return data if isinstance(data, dict) else {}
    
    def _set_item_data(self, item: QStandardItem, data: Dict[str, Any]):
        """Set data for a tree item."""
        if not item:
            return
        
        # Store in both cache and item
        index = self.model.indexFromItem(item)
        cache_key = (index.row(), index.column(), id(index.parent()))
        self._item_data_cache[cache_key] = data
        
        item.setData(data, Qt.UserRole)
    
    def _on_selection_changed(self, current, previous):
        """Handle selection change."""
        if current.isValid():
            item = self.model.itemFromIndex(current)
            item_type = self._determine_item_type(item)
            item_data = self._get_item_data(item)
            self.item_selected.emit(item_type, item_data)
    
    def _on_double_clicked(self, index):
        """Handle double-click."""
        if index.isValid():
            item = self.model.itemFromIndex(index)
            item_type = self._determine_item_type(item)
            item_data = self._get_item_data(item)
            self.item_double_clicked.emit(item_type, item_data)
    
    def _on_context_menu(self, position):
        """Handle context menu request."""
        index = self.indexAt(position)
        if not index.isValid():
            # Right-clicked on empty space
            self._show_empty_context_menu(position)
            return
        
        item = self.model.itemFromIndex(index)
        item_type = self._determine_item_type(item)
        item_data = self._get_item_data(item)
        
        self.context_menu_requested.emit(item_type, item_data, position)
        self._show_context_menu(item_type, item_data, position)
    
    def _show_empty_context_menu(self, position):
        """Show context menu for empty area."""
        menu = QMenu(self)
        
        add_conn_action = QAction("Add Connection", self)
        add_conn_action.triggered.connect(self.add_connection_requested)
        menu.addAction(add_conn_action)
        
        menu.exec_(self.mapToGlobal(position))
    
    def _show_context_menu(self, item_type: str, item_data: Dict[str, Any], position):
        """Show context menu based on item type."""
        menu = QMenu(self)
        
        if item_type == 'connection':
            self._add_connection_menu_actions(menu, item_data)
        elif item_type == 'slave':
            self._add_slave_menu_actions(menu, item_data)
        elif item_type == 'register_group':
            self._add_group_menu_actions(menu, item_data)
        elif item_type == 'multi_type_group':
            self._add_multi_group_menu_actions(menu, item_data)
        
        if menu.actions():
            menu.exec_(self.mapToGlobal(position))
    
    def _add_connection_menu_actions(self, menu: QMenu, item_data: Dict[str, Any]):
        """Add context menu actions for connections."""
        connection_key = item_data.get('connection_key', '')
        is_open = item_data.get('is_open', False)
        
        if is_open:
            close_action = QAction("Close Connection", self)
            close_action.triggered.connect(lambda: self.close_connection_requested.emit(connection_key))
            menu.addAction(close_action)
        else:
            open_action = QAction("Open Connection", self)
            open_action.triggered.connect(lambda: self.open_connection_requested.emit(connection_key))
            menu.addAction(open_action)
        
        menu.addSeparator()
        
        add_slave_action = QAction("Add Slave", self)
        add_slave_action.triggered.connect(lambda: self.add_slave_requested.emit(connection_key))
        menu.addAction(add_slave_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove Connection", self)
        remove_action.triggered.connect(lambda: self.remove_item_requested.emit('connection', item_data))
        menu.addAction(remove_action)
    
    def _add_slave_menu_actions(self, menu: QMenu, item_data: Dict[str, Any]):
        """Add context menu actions for slaves."""
        connection_key = item_data.get('connection_key', '')
        slave_id = item_data.get('slave_id', 0)
        
        add_group_action = QAction("Add Register Group", self)
        add_group_action.triggered.connect(lambda: self.add_register_group_requested.emit(connection_key, slave_id))
        menu.addAction(add_group_action)
        
        add_multi_group_action = QAction("Add Multi-Type Group", self)
        add_multi_group_action.triggered.connect(lambda: self.add_multi_type_group_requested.emit(connection_key, slave_id))
        menu.addAction(add_multi_group_action)
        
        menu.addSeparator()
        
        bulk_ops_action = QAction("Bulk Operations", self)
        bulk_ops_action.triggered.connect(lambda: self.bulk_operations_requested.emit(connection_key, slave_id))
        menu.addAction(bulk_ops_action)
        
        import_action = QAction("Import Group", self)
        import_action.triggered.connect(lambda: self.import_group_requested.emit(connection_key, slave_id))
        menu.addAction(import_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove Slave", self)
        remove_action.triggered.connect(lambda: self.remove_item_requested.emit('slave', item_data))
        menu.addAction(remove_action)
    
    def _add_group_menu_actions(self, menu: QMenu, item_data: Dict[str, Any]):
        """Add context menu actions for register groups."""
        duplicate_action = QAction("Duplicate Group", self)
        duplicate_action.triggered.connect(lambda: self.duplicate_group_requested.emit(item_data))
        menu.addAction(duplicate_action)
        
        split_action = QAction("Split Group", self)
        split_action.triggered.connect(lambda: self.split_group_requested.emit(item_data))
        menu.addAction(split_action)
        
        menu.addSeparator()
        
        export_action = QAction("Export Group", self)
        export_action.triggered.connect(lambda: self.export_group_requested.emit(item_data))
        menu.addAction(export_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove Group", self)
        remove_action.triggered.connect(lambda: self.remove_item_requested.emit('register_group', item_data))
        menu.addAction(remove_action)
    
    def _add_multi_group_menu_actions(self, menu: QMenu, item_data: Dict[str, Any]):
        """Add context menu actions for multi-type groups."""
        export_action = QAction("Export Multi-Type Group", self)
        export_action.triggered.connect(lambda: self.export_group_requested.emit(item_data))
        menu.addAction(export_action)
        
        menu.addSeparator()
        
        remove_action = QAction("Remove Multi-Type Group", self)
        remove_action.triggered.connect(lambda: self.remove_item_requested.emit('multi_type_group', item_data))
        menu.addAction(remove_action)
