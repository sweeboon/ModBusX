from PyQt5.QtWidgets import (
    QMainWindow, QAction, QDialog, QDockWidget, QWidget, QApplication, QToolBar,  QTreeView, QTableView, QSplitter
)
from PyQt5 import uic
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from .SlaveControl import SlaveControl
from .add_slave_dialog import AddSlaveDialog

import modbusx.ui.resources.resources_rc

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("modbusx/ui/main_window.ui", self)
        self.setWindowTitle("ModbusX Multi-Instance Slave Demo")

        self.docks = []  # Track QDockWidget instances
        self.counter = 1

        # ---- Tree setup ----
        self.treeView = getattr(self, "treeView", None)
        if self.treeView:
            # One column, with a header
            self.tree_model = QStandardItemModel()
            self.tree_model.setHorizontalHeaderLabels(['Connections'])
            self.treeView.setModel(self.tree_model)
            # Create a root node (e.g., for local connection)
            self.root_item = QStandardItem('Local Connection')
            self.tree_model.appendRow(self.root_item)
        else:
            self.tree_model = None
            self.root_item = None

        self.splitter = self.findChild(QSplitter, "splitter")  # Or whatever name in .ui
        if self.splitter:
            self.splitter.setStretchFactor(0, 0)  # treeView
            self.splitter.setStretchFactor(1, 1)  # tableView
        # Connect menu action (adjust if your .ui names differ)

        if hasattr(self, "actionAddSlave"):
            self.actionAddSlave.triggered.connect(self.show_add_slave_dialog)

        # Optional: create a menu to toggle dock widgets visibility
        if hasattr(self, "menuView"):
            self.menuView = self.menuView
        else:
            self.menuView = self.menuBar().addMenu("View")

    def show_add_slave_dialog(self):
        dlg = AddSlaveDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            port = dlg.settings["port"]
            address = dlg.settings["address"]
            self.add_instance(port, address)

    def add_instance(self, port, address):
        idx = self.counter
        self.counter += 1
        slave = SlaveControl(idx, port, address)

        print(f"Created Slave Widget {idx} for {address} on port {port}")

        if self.root_item:
            slave_item = QStandardItem(f"Slave #{idx} ({address}:{port})")
            self.root_item.appendRow(slave_item)
            setattr(slave, 'tree_item', slave_item)    # Reference for cleanup
            self.treeView.expand(self.tree_model.indexFromItem(self.root_item))  # expand root

        dock = QDockWidget(f"Slave #{idx} (Port {port})", self)
        dock.setWidget(slave)
        
        # Allow users to close docks
        dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.addDockWidget(Qt.TopDockWidgetArea, dock)

        self.docks.append((dock, slave))
        # Remove when closed
        dock.closeEvent = lambda event, s=slave, d=dock: self._on_dock_closed(event, d, s)

        # Add toggle to 'View' menu for convenience
        view_action = dock.toggleViewAction()
        self.menuView.addAction(view_action)

        # Connect SlaveControl's close action (if user presses 'Remove Server' in widget)
        slave.on_close.connect(lambda w=slave: self.remove_instance_by_widget(w))

        slave.status.append(f"Initialized in dock widget (#{idx}).")

    def _on_dock_closed(self, event, dock, slave):
        if hasattr(slave, 'tree_item') and self.root_item:
            self.root_item.removeRow(slave.tree_item.row())
        # Called when dock widget is closed
        if (dock, slave) in self.docks:
            self.docks.remove((dock, slave))
        slave.deleteLater()  # Clean up widget
        dock.deleteLater()
        event.accept()

    def remove_instance_by_widget(self, slave_widget):
        for dock, slave in self.docks:
            if slave is slave_widget:
                # Closing the dock will trigger cleanup
                dock.close()
                break

    def closeEvent(self, event):
        # Gracefully stop all servers on close
        for dock, slave in self.docks:
            slave.stop_server()
        return super().closeEvent(event)