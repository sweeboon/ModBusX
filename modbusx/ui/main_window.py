# modbusx/ui/main_window.py

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, 
    QScrollArea, QMainWindow, QDialog
)
from PyQt5 import uic
from .SlaveControl import SlaveControl
from .connect_dialog import ConnectDialog

class MainWindow(QMainWindow):
    """Main PyQt window for ModbusX multi-slave UI."""
    def __init__(self):
        super().__init__()
        
        uic.loadUi("modbusx/ui/main_window.ui", self)
        self.setWindowTitle("ModbusX Multi-Instance Slave Demo")
        self.actionConnect.triggered.connect(self.add_instance)
        self.actionConnect.triggered.connect(self.show_connect_dialog)
        
        self.instance_widgets = []
        self.counter = 1

        #Old
        # self.setWindowTitle("ModbusX Multi-Instance Slave Demo")
        # main_vbox = QVBoxLayout(self)
        # self.setLayout(main_vbox)
        # lbl = QLabel("<b>Multi-Slave Instance Panel</b>")
        # main_vbox.addWidget(lbl)
        # add_hbox = QHBoxLayout()
        # self.add_slave_btn = QPushButton("Add Slave Instance")
        # add_hbox.addWidget(self.add_slave_btn)
        # add_hbox.addStretch()
        # main_vbox.addLayout(add_hbox)

        # # Placeholder for instance widgets
        # self.scroll = QScrollArea()
        # self.scroll.setWidgetResizable(True)
        # main_vbox.addWidget(self.scroll)
        # self.instances_widget = QWidget()
        # self.instances_layout = QVBoxLayout(self.instances_widget)
        # self.instances_layout.addStretch()
        # self.scroll.setWidget(self.instances_widget)
        # # State
        # self.instance_widgets = []
        # self.counter = 1
        # # Hook up add button
        # self.add_slave_btn.clicked.connect(self.add_instance)

    def show_connect_dialog(self):
        dlg = ConnectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            port = dlg.settings["port"]
            address = dlg.settings["address"]
            print(f"Connecting to {address} on port {port}")
            self.add_instance(port, address)

    def add_instance(self, port, address):
        idx = self.counter
        self.counter += 1
        slave = SlaveControl(idx, port, address)
        self.instance_widgets.append(slave)
        self.instances_widget.layout().insertWidget(self.instances_widget.layout().count()-1, slave)
        slave.on_close.connect(self.remove_instance)
        slave.status.append(f"Initialized new slave instance #{idx}.")
        slave.on_close.connect(self.remove_instance)

    def remove_instance(self, slave_widget):
        slave_widget.setParent(None)
        if slave_widget in self.instance_widgets:
            self.instance_widgets.remove(slave_widget)
        slave_widget.deleteLater()

    def closeEvent(self, event):
        for inst in self.instance_widgets:
            inst.stop_server()
        event.accept()