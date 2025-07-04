# modbusx/ui/connect_dialog.py
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5 import uic

class ConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("modbusx/ui/connect_dialog.ui", self)
        self.setWindowTitle("Connect to Modbus Server")
        self.connectButton.accepted.connect(self.accept)
        self.connectButton.rejected.connect(self.reject)
        self.settings = {}

    def on_ok(self):
        port = self.lineEditPort.text()
        address = self.lineEditAddress.text()
        if not port.isdigit() or int(port) < 1025 or int(port) > 65535 or address.isdigit():
            QMessageBox.warning(self, "Input Error", "Port must be a number!")
            return
        
        self.settings["port"] = int(port)
        # Store in self.settings
        self.settings = {"port": port, "address": address}
        self.accept()