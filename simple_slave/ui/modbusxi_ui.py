import sys
import asyncio
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QLineEdit, QTextEdit, QMessageBox
)
from PyQt5.QtCore import QThread, pyqtSignal

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock

class ModbusServerThread(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self, port, unit_id, hr_value, ir_value, parent=None):
        super().__init__(parent)
        self.port = port
        self.unit_id = unit_id
        self.hr_value = hr_value
        self.ir_value = ir_value
        self._running = True
        self.loop = None

    async def start_server(self):
        store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [self.hr_value]*10),
            ir=ModbusSequentialDataBlock(0, [self.ir_value]*10)
        )
        context = ModbusServerContext(slaves={self.unit_id: store}, single=False)
        self.status_signal.emit(f"Starting Modbus slave on 127.0.0.1:{self.port} (unit={self.unit_id})")
        try:
            await StartAsyncTcpServer(context, address=("127.0.0.1", self.port))
        except Exception as e:
            self.error_signal.emit(f"Modbus server failed: {e}")

    def run(self):
        # Each QThread gets its own event loop
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self._running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

class ModbusXUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModbusX Async Slave Demo")
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # -- Inputs --
        hbox = QHBoxLayout()
        layout.addLayout(hbox)
        hbox.addWidget(QLabel("Port:"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1025, 65535)
        self.port_spin.setValue(55000)
        hbox.addWidget(self.port_spin)
        hbox.addWidget(QLabel("Unit ID:"))
        self.unit_spin = QSpinBox()
        self.unit_spin.setRange(1, 247)
        self.unit_spin.setValue(1)
        hbox.addWidget(self.unit_spin)
        hbox.addWidget(QLabel("HR Value:"))
        self.hr_edit = QLineEdit("1234")
        hbox.addWidget(self.hr_edit)
        hbox.addWidget(QLabel("IR Value:"))
        self.ir_edit = QLineEdit("5678")
        hbox.addWidget(self.ir_edit)
        
        # -- Control Buttons --
        self.start_btn = QPushButton("Start Server")
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setEnabled(False)
        btnbox = QHBoxLayout()
        btnbox.addWidget(self.start_btn)
        btnbox.addWidget(self.stop_btn)
        layout.addLayout(btnbox)
        # -- Status --
        self.status = QTextEdit()
        self.status.setReadOnly(True)
        layout.addWidget(self.status)

        # -- Events --
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn.clicked.connect(self.stop_server)

        self.modbus_thread = None

    def log(self, txt):
        self.status.append(txt)

    def start_server(self):
        port = self.port_spin.value()
        unit_id = self.unit_spin.value()
        try:
            hr_val = int(self.hr_edit.text())
            ir_val = int(self.ir_edit.text())
        except ValueError:
            QMessageBox.warning(self, "Input error", "Register values must be integers!")
            return
        self.modbus_thread = ModbusServerThread(port, unit_id, hr_val, ir_val)
        self.modbus_thread.status_signal.connect(self.log)
        self.modbus_thread.error_signal.connect(self.log)
        self.modbus_thread.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.log("Server starting...")

    def stop_server(self):
        if self.modbus_thread:
            self.modbus_thread.stop()
            self.modbus_thread.quit()
            self.modbus_thread.wait()
            self.log("Server stopped.")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def closeEvent(self, event):
        self.stop_server()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ModbusXUI()
    win.resize(600, 300)
    win.show()
    sys.exit(app.exec_())