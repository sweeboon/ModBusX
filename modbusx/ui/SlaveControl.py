# modbusx/ui/controls.py

"""
Reusable PyQt widgets for slave controls.
Each ServerControlWidget corresponds to a Modbus slave process.
"""

from PyQt5.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QSpinBox, QLineEdit, QTextEdit, QMessageBox, QWidget, QTableWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal

from ..slave_server import MultiUnitModbusServerThread  # see previous response for this class

class SlaveControl(QGroupBox):
    on_close = pyqtSignal(object)
    """
    GroupBox controlling a multi-unit Modbus TCP server.
    User can add/remove/edit unit IDs and their register values for this TCP port.
    """
    def __init__(self, port, address):
        super().__init__(f"Modbus TCP Server (Port {port})")
        self.setStyleSheet("QGroupBox { font-weight: bold; } ")

        self.port = port
        self.address = address # Not used in this example, but can be extended
        self.server_thread = None
        self.unit_data = {}  # unit_id: (hr_val, ir_val)

        # ---- LAYOUT ----
        vbox = QVBoxLayout(self)
        
        # Controls row (port entry, start/stop, add unit)
        controls_hbox = QHBoxLayout()
        controls_hbox.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1025, 65535)
        self.port_spin.setValue(self.port)
        controls_hbox.addWidget(self.port_spin)
        self.add_unit_btn = QPushButton("Add Unit")
        controls_hbox.addWidget(self.add_unit_btn)
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setEnabled(False)
        controls_hbox.addWidget(self.start_btn)
        controls_hbox.addWidget(self.stop_btn)
        controls_hbox.addStretch()
        vbox.addLayout(controls_hbox)

        # Table of units/config
        self.unit_table = QTableWidget(0, 4)
        self.unit_table.setHorizontalHeaderLabels(["Unit ID", "HR Value", "IR Value", "Remove"])
        self.unit_table.setColumnWidth(0, 50)
        self.unit_table.setColumnWidth(1, 80)
        self.unit_table.setColumnWidth(2, 80)
        self.unit_table.setColumnWidth(3, 70)
        vbox.addWidget(self.unit_table)

        # Status log
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        self.status.setMaximumHeight(60)
        vbox.addWidget(self.status)

        # ---- SIGNALS ----
        self.add_unit_btn.clicked.connect(self.add_unit_row)
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)

        # Remove server button
        self.remove_server_btn = QPushButton("Remove Server")
        controls_hbox.addWidget(self.remove_server_btn)
        self.remove_server_btn.clicked.connect(self.handle_remove_server)

    def add_unit_row(self):
        used_ids = set()
        for row in range(self.unit_table.rowCount()):
            idspin = self.unit_table.cellWidget(row, 0)
            if idspin:
                used_ids.add(idspin.value())
        unit_id = 1
        while unit_id in used_ids:
            unit_id += 1

        next_row = self.unit_table.rowCount()
        self.unit_table.insertRow(next_row)
        idspin = QSpinBox()
        idspin.setRange(1, 247)
        idspin.setValue(unit_id)
        from PyQt5.QtGui import QIntValidator
        hr_edit = QLineEdit("1000")
        hr_edit.setValidator(QIntValidator())
        ir_edit = QLineEdit("2000")
        ir_edit.setValidator(QIntValidator())
        rem_btn = QPushButton("Remove")
        self.unit_table.setCellWidget(next_row, 0, idspin)
        self.unit_table.setCellWidget(next_row, 1, hr_edit)
        self.unit_table.setCellWidget(next_row, 2, ir_edit)
        self.unit_table.setCellWidget(next_row, 3, rem_btn)
        rem_btn.clicked.connect(lambda _, b=rem_btn: self.remove_unit_row(b))
        idspin.valueChanged.connect(self.check_duplicates)
        hr_edit.textChanged.connect(self.check_ints)
        ir_edit.textChanged.connect(self.check_ints)
        self.check_duplicates()

    def remove_unit_row(self, btn):
        for row in range(self.unit_table.rowCount()):
            if self.unit_table.cellWidget(row, 3) is btn:
                self.unit_table.removeRow(row)
                break
        self.check_duplicates()
        self.check_ints()

    def handle_remove_server(self):
        if self.server_thread is not None and self.stop_btn.isEnabled():
            res = QMessageBox.question(self, "Remove Server", "Server is running. Stop and remove?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if res != QMessageBox.Yes:
                return
        self.stop_server()
        self.on_close.emit(self)

    def get_all_units(self):
        data = {}
        for row in range(self.unit_table.rowCount()):
            idspin = self.unit_table.cellWidget(row, 0)
            hr_edit = self.unit_table.cellWidget(row, 1)
            ir_edit = self.unit_table.cellWidget(row, 2)
            try:
                unit_id = idspin.value()
                hr_val = int(hr_edit.text())
                ir_val = int(ir_edit.text())
                if unit_id in data:
                    raise ValueError("Duplicate unit ID")
                data[unit_id] = (hr_val, ir_val)
            except Exception as e:
                self.log(f"Error in row {row+1}: {e}")
                return None
        return data

    def check_duplicates(self):
        # Optional: highlight duplicates in UI
        ids = []
        for row in range(self.unit_table.rowCount()):
            v = self.unit_table.cellWidget(row, 0).value()
            ids.append(v)
        if len(set(ids)) < len(ids):
            self.status.setText("Duplicate unit IDs detected!")
            self.start_btn.setEnabled(False)
        else:
            self.status.setText("")
            self.start_btn.setEnabled(True)

    def check_ints(self):
        # Disable start if any HR/IR field is not int
        for row in range(self.unit_table.rowCount()):
            try:
                int(self.unit_table.cellWidget(row, 1).text())
                int(self.unit_table.cellWidget(row, 2).text())
            except Exception:
                self.status.setText("Non-integer found in HR/IR.")
                self.start_btn.setEnabled(False)
                return
        self.status.setText("")
        self.start_btn.setEnabled(True)

    def log(self, txt):
        self.status.append(txt)

    def start_server(self):
        self.unit_data = self.get_all_units()
        if not self.unit_data or not len(self.unit_data):
            QMessageBox.warning(self, "Error", "Configure at least one unit!")
            return
        port = self.port_spin.value()
        self.server_thread = MultiUnitModbusServerThread(port, self.unit_data)
        self.server_thread.status_signal.connect(self.log)
        self.server_thread.error_signal.connect(self.log)
        self.server_thread.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.port_spin.setEnabled(False)
        self.add_unit_btn.setEnabled(False)
        self.unit_table.setEnabled(False)
        self.log("Server STARTED on port %d, units: %s" % (port, ",".join(str(u) for u in self.unit_data.keys())))

    def stop_server(self):
        if self.server_thread:
            # Disconnect signals
            self.log("Disconnecting signals...")
            if self.server_thread.status_signal:
                self.server_thread.status_signal.disconnect(self.log)
            if self.server_thread.error_signal:
                self.server_thread.error_signal.disconnect(self.log)
            self.log("Stopping server...")
            self.server_thread.stop()
            self.server_thread.quit()
            self.server_thread.wait()
            self.server_thread = None
            self.log("Server stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.port_spin.setEnabled(True)
        self.add_unit_btn.setEnabled(True)
        self.unit_table.setEnabled(True)

    def closeEvent(self, event):
        self.stop_server()
        event.accept()