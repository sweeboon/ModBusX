# modbusx/ui/Connect_Dialog.py
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5 import uic

class ConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        uic.loadUi("modbusx/ui/Connect_Dialog.ui", self)
        self.setWindowTitle("Connect to Modbus Server")
        self.connectButton.accepted.connect(self.on_ok)
        self.connectButton.rejected.connect(self.reject)
        self.settings = {}

    def on_ok(self):
        port = self.portNumber.text().strip()
        address = self.ipAddress.text().strip()

        # Validation
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            QMessageBox.warning(self, "Input Error", "Port must be an integer between 1 and 65535.")
            return
        if not address:  # Just check it's not empty; don't block if it's digits.
            QMessageBox.warning(self, "Input Error", "Address must not be empty!")
            return
        
        # Store in self.settings
        self.settings = {"port": int(port), "address": address}
        self.accept()