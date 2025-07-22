from PyQt5.QtWidgets import (
    QMainWindow, QDialog, QTreeView, QSplitter, QSizePolicy, QMessageBox
)
from PyQt5 import uic
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from .connect_dialog import ConnectDialog
from modbusx.register_map import RegisterEntry, RegisterMap
from modbusx.slave_server import MultiUnitModbusServerThread
from modbusx.logger import global_logger

import modbusx.assets.resources_rc

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("modbusx/ui/main_window.ui", self)
        self.setWindowTitle("ModbusX Multi-Instance Slave Demo")

        # ---- Tree setup ----
        self.treeView = getattr(self, "treeView", None)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels(['Connections'])
        self.treeView.setModel(self.tree_model)
        self.treeView.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # ---- Table setup ----
        self.tableView = getattr(self, "tableView", None)
        self.reg_table_model = QStandardItemModel(self)
        self.reg_table_model.setHorizontalHeaderLabels([
            "Register Type", "Address", "Alias", "Value", "Comment"
        ])
        self.tableView.setModel(self.reg_table_model)

        self.splitter = self.findChild(QSplitter, "splitter")
        if self.splitter:
            self.splitter.setStretchFactor(0, 1)     # treeView scales a bit
            self.splitter.setStretchFactor(1, 3)     # right panel scales more

        # Hide log box by default if desired
        self.statusText.setVisible(self.actionShowLogs.isChecked())
        # Connect toggled signal
        self.actionShowLogs.toggled.connect(self.statusText.setVisible)

        # ---- Connect signals ----
        self.treeView.selectionModel().currentChanged.connect(self.on_tree_selection_changed)

        if hasattr(self, "actionConnect"):
            self.actionConnect.triggered.connect(self.show_connect_dialog)
        if hasattr(self, "actionOpenConnect"):
            self.actionOpenConnect.triggered.connect(self.open_selected_connection)
        if hasattr(self, "actionCloseConnect"):
            self.actionCloseConnect.triggered.connect(self.close_selected_connection)
        if hasattr(self, "actionAddSlave"):
            self.actionAddSlave.triggered.connect(self.add_slave_to_selected_connection)
        if hasattr(self, "actionAddRegisterGroup"):
            self.actionAddRegisterGroup.triggered.connect(self.add_reggroup_to_selected_slave)

        # Connect the logger's signal to append function
        global_logger.message_signal.connect(self.append_to_log_widget)

    def show_connect_dialog(self):
        dlg = ConnectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            port = dlg.settings["port"]
            address = dlg.settings["address"]
            self.add_connection(port, address)

    def add_connection(self, port, address):
        """Add a new connection to the tree, with default Slave 1 and Register Group 1."""
        node_text = f"{address}:{port}"
        # Prevent duplicate connections
        for i in range(self.tree_model.rowCount()):
            if self.tree_model.item(i, 0).text() == node_text:
                return
        conn_item = QStandardItem(node_text)
        conn_info = {
            'address': address,
            'port': port,
            'slaves': [],
            'is_open': False
        }

        # ---- Auto-add first Slave (ID 1) and under it Register Group (ID 1) ----
        slave_id = 1
        slave_item = QStandardItem(f"Slave ID: {slave_id}")

        slave_info = {
            "slave_id": slave_id,
            "register_map": RegisterMap(),
        }

        # The ONE RegisterMap instance for this slave (per comm node)
        register_map = RegisterMap()
        # Add an HR block by default (as the first group, eg. 40001..40010)
        register_map.add_block('hr', 40001, 10)

        slave_info = {
            "slave_id": slave_id,
            "register_map": register_map,
            "groups": []  # group metadata for UI tree only
        }

        # Add first register group under this slave
        reg_group_id = 1
        group_meta = {
            "register_id": reg_group_id,
            "reg_type": "hr",
            "start_addr": 40001,
            "size": 10,
            "parent_slave_map": register_map,
        }
        reg_item = QStandardItem(f"Register Group: {reg_group_id} [HR 40001:40010]")
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
        self.treeView.expand(self.tree_model.indexFromItem(conn_item))
        self.treeView.expand(self.tree_model.indexFromItem(slave_item))

    def _get_selected_connection_item(self):
        """Helper: Returns the connection-level item for current selection, or None."""
        indexes = self.treeView.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "Nothing Selected", "Please select a connection node.")
            return None
        item = self.tree_model.itemFromIndex(indexes[0])
        # Ascend to root-level if slave/register is selected
        while item.parent() is not None:
            item = item.parent()
        return item
    
    def _get_selected_slave_item(self):
        """Return the slave item for current selection, or None."""
        indexes = self.treeView.selectedIndexes()
        if not indexes:
            QMessageBox.warning(self, "Nothing Selected", "Please select a slave node.")
            return None
        item = self.tree_model.itemFromIndex(indexes[0])
        # If not a slave, traverse up tree until child of connection
        while item.parent() is not None:
            parent = item.parent()
            # If the parent is root (connection), and item starts with "Slave ID:"
            if parent.parent() is None and item.text().startswith("Slave ID:"):
                return item
            item = parent
        return None

    def open_selected_connection(self):
        item = self._get_selected_connection_item()
        if not item:
            return
        conn_info = item.data(Qt.UserRole)
        if conn_info is None:
            QMessageBox.warning(self, "Invalid", "No connection info found.")
            return
        if conn_info.get("is_open"):
            QMessageBox.information(self, "Already Open", f"{item.text()} already open.")
            return
        
        # --- BUILD unit_definitions FOR THE MODBUS THREAD ---
        unit_definitions = {}
        for slave in conn_info.get("slaves", []):
            sid = slave["slave_id"]
            reg_map = slave["register_map"]
            unit_definitions[sid] = {
                'hr': reg_map.as_pymodbus_array('hr'),  # (start, arr)
                'ir': reg_map.as_pymodbus_array('ir'),
                'co': reg_map.as_pymodbus_array('co'),
                'di': reg_map.as_pymodbus_array('di'),
            }

        # --- Start backend thread ---
        modbus_thread = MultiUnitModbusServerThread(
            conn_info["port"], unit_definitions
        )
        modbus_thread.status_signal.connect(lambda msg: print(f"[{conn_info['port']}] {msg}"))  # or log to your status widget
        modbus_thread.error_signal.connect(lambda msg: QMessageBox.critical(self, "Modbus Error", msg))
        modbus_thread.start()

        # Keep reference on the connection info
        conn_info["modbus_thread"] = modbus_thread
        conn_info["is_open"] = True
        item.setData(conn_info, Qt.UserRole)
        item.setText(f"{conn_info['address']}:{conn_info['port']} (OPEN)")
        QMessageBox.information(self, "Connection Opened",
            f"Opened Modbus on {conn_info['address']}:{conn_info['port']}.")
        global_logger.log("Creating modbus thread for port=%d unit_definitions:" % conn_info["port"])

    def close_selected_connection(self):
        item = self._get_selected_connection_item()
        if not item:
            return
        conn_info = item.data(Qt.UserRole)
        if not conn_info.get("is_open"):
            QMessageBox.information(self, "Already Closed", f"{item.text()} already closed.")
            return

        # Stop backend thread if present
        modbus_thread = conn_info.get("modbus_thread", None)
        if modbus_thread:
            modbus_thread.stop()
            modbus_thread.wait()
            conn_info["modbus_thread"] = None

        conn_info["is_open"] = False
        item.setData(conn_info, Qt.UserRole)
        item.setText(f"{conn_info['address']}:{conn_info['port']}")
        QMessageBox.information(self, "Connection Closed",
            f"Closed Modbus on {conn_info['address']}:{conn_info['port']}.")

    def add_slave_to_selected_connection(self):
        conn_item = self._get_selected_connection_item()
        if not conn_item:
            return
        conn_info = conn_item.data(Qt.UserRole)
        used_ids = set()
        for i in range(conn_item.rowCount()):
            child_item = conn_item.child(i)
            if child_item.text().startswith("Slave ID:"):
                try:
                    sid = int(child_item.text().split(":")[1].strip())
                    used_ids.add(sid)
                except Exception:
                    pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1

        slave_item = QStandardItem(f"Slave ID: {next_id}")
        register_map = RegisterMap()
        # Default group: first HR block for new slave
        reg_type, start_addr, size = "hr", 40001, 8
        register_map.add_block(reg_type, start_addr, size)
        group_meta = {
            "register_id": 1,
            "reg_type": reg_type,
            "start_addr": start_addr,
            "size": size,
            "parent_slave_map": register_map,
        }
        reg_item = QStandardItem(f"Register Group: 1 [HR 40001:40008]")
        reg_item.setData(group_meta, Qt.UserRole)
        slave_item.appendRow(reg_item)
        slave_info = {
            "slave_id": next_id,
            "register_map": register_map,
            "groups": [group_meta]
        }
        slave_item.setData(slave_info, Qt.UserRole)
        conn_item.appendRow(slave_item)
        conn_info['slaves'].append(slave_info)
        conn_item.setData(conn_info, Qt.UserRole)
        self.treeView.expand(self.tree_model.indexFromItem(conn_item))
        self.treeView.expand(self.tree_model.indexFromItem(slave_item))
        QMessageBox.information(self, "Slave Added", f"Added Slave ID: {next_id}.")

    def add_reggroup_to_selected_slave(self):
        slave_item = self._get_selected_slave_item()
        if not slave_item:
            return
        slave_info = slave_item.data(Qt.UserRole)
        # Extract used group IDs and next available:
        used_ids = set()
        for i in range(slave_item.rowCount()):
            child = slave_item.child(i)
            if child.text().startswith("Register Group:"):
                try:
                    gid = int(child.text().split(":")[1].split()[0])
                    used_ids.add(gid)
                except Exception:
                    pass
        next_id = 1
        while next_id in used_ids:
            next_id += 1
        # For demo, each new group is an HR block starting at next 10s
        reg_type = "hr"
        start_addr = 40001 + 10 * (next_id - 1)
        size = 8
        reg_map = slave_info["register_map"]
        reg_map.add_block(reg_type, start_addr, size)
        group_meta = {
            "register_id": next_id,
            "reg_type": reg_type,
            "start_addr": start_addr,
            "size": size,
            "parent_slave_map": reg_map,
        }
        reg_item = QStandardItem(f"Register Group: {next_id} [HR {start_addr}:{start_addr+size-1}]")
        reg_item.setData(group_meta, Qt.UserRole)
        slave_item.appendRow(reg_item)
        slave_info["groups"].append(group_meta)
        slave_item.setData(slave_info, Qt.UserRole)
        self.treeView.expand(self.tree_model.indexFromItem(slave_item))
        QMessageBox.information(self, "Register Group Added", f"Added Register Group: {next_id}")

    def on_tree_selection_changed(self, current, previous):
        item = self.tree_model.itemFromIndex(current)
        if not item:
            self.reg_table_model.setRowCount(0)
            return
        group_meta = item.data(Qt.UserRole)
        if isinstance(group_meta, dict) and "parent_slave_map" in group_meta:
            reg_map = group_meta['parent_slave_map']
            reg_type = group_meta['reg_type']
            start_addr = group_meta['start_addr']
            size = group_meta['size']
            entries = [
                e for e in reg_map.all_entries(reg_type)
                if start_addr <= e.addr < start_addr + size
            ]
            self.reg_table_model.setRowCount(0)
            for row, entry in enumerate(entries):
                self.reg_table_model.insertRow(row)
                self.reg_table_model.setItem(row, 0, QStandardItem(reg_type.upper()))
                self.reg_table_model.setItem(row, 1, QStandardItem(str(entry.addr)))
                self.reg_table_model.setItem(row, 2, QStandardItem(str(entry.alias)))
                self.reg_table_model.setItem(row, 3, QStandardItem(str(entry.value)))
                self.reg_table_model.setItem(row, 4, QStandardItem(str(entry.comment)))
        else:
            self.reg_table_model.setRowCount(0)

    def append_to_log_widget(self, msg):
        # slot for log messages
        if self.statusText.isVisible():
            self.statusText.append(msg)