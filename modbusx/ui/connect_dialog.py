# modbusx/ui/Connect_Dialog.py
from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.QtCore import Qt
from PyQt5 import uic
from pathlib import Path
import serial.tools.list_ports

class ConnectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Load UI file from module directory
        ui_file = Path(__file__).resolve().parent / "connect_dialog.ui"
        uic.loadUi(str(ui_file), self)
        
        self.setWindowTitle("Connect to ModBus Device")
        self.setModal(True)
        self.settings = {}
        self._setup_connections()
        
        # Scan and populate COM ports
        self._scan_com_ports()
        
        # Set default values for serial port settings
        self._set_default_serial_settings()
        
        # Ensure protocol combo user data is stable for localization
        self._ensure_protocol_combo_metadata()
        
        # Ensure initial visibility is set correctly
        self._update_ui_for_protocol()

    
    def _setup_connections(self):
        """Setup signal connections."""
        # Disconnect any automatic connections first (if they exist)
        try:
            self.connectButton.accepted.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        
        try:
            self.connectButton.rejected.disconnect()
        except TypeError:
            pass  # No connections to disconnect
        
        # Connect the button box from UI file to custom handlers
        self.connectButton.accepted.connect(self._handle_accept)
        self.connectButton.rejected.connect(self.reject)
        
        # Connect protocol combo to update UI
        self.protocol_combo.currentIndexChanged.connect(lambda *_: self._update_ui_for_protocol())
        
        # Connect to rescan COM ports when Serial Port is selected
        self.protocol_combo.currentIndexChanged.connect(lambda *_: self._on_protocol_changed())

        # When ASCII mode is toggled, adjust sensible defaults (7-E-1)
        try:
            if hasattr(self, 'ascii_radio'):
                self.ascii_radio.toggled.connect(self._apply_ascii_defaults_if_selected)
        except Exception:
            pass
    
    def _set_default_serial_settings(self):
        """Set default values for serial port settings."""
        # Set databits to 8 (index 1) instead of 7 (index 0)
        if hasattr(self, 'databits'):
            # Find the index of "8" in the combo box
            for i in range(self.databits.count()):
                if self.databits.itemText(i) == "8":
                    self.databits.setCurrentIndex(i)
                    break
        
        # Set other common defaults if desired
        # baudrate defaults to 9600 (first item) - this is already correct
        # parity defaults to None (first item) - this is already correct  
        # stopbits defaults to 1 (first item) - this is already correct
        # RTU radio button is already checked by default in UI file
    
    def _ensure_protocol_combo_metadata(self):
        """Assign stable metadata to protocol combo entries for localization."""
        if not hasattr(self, 'protocol_combo'):
            return
        count = self.protocol_combo.count()
        for index in range(count):
            data = self.protocol_combo.itemData(index)
            if data in ('tcp', 'serial'):
                continue
            text = (self.protocol_combo.itemText(index) or "").lower()
            if "serial" in text or "串" in text:
                key = 'serial'
            else:
                key = 'tcp'
            self.protocol_combo.setItemData(index, key)
    
    def _current_protocol_mode(self) -> str:
        """Return logical protocol key independent of localized text."""
        if not hasattr(self, 'protocol_combo'):
            return 'tcp'
        data = self.protocol_combo.currentData()
        if data in ('tcp', 'serial'):
            return data
        text = (self.protocol_combo.currentText() or "").lower()
        if "serial" in text or "串" in text:
            return 'serial'
        return 'tcp'
    
    def _update_ui_for_protocol(self):
        """Enable/disable fields based on selected protocol."""
        protocol_mode = self._current_protocol_mode()
        
        # Enable/disable TCP fields
        tcp_enabled = (protocol_mode == 'tcp')
        if hasattr(self, 'ipAddress'):
            self.ipAddress.setEnabled(tcp_enabled)
        if hasattr(self, 'portNumber'):
            self.portNumber.setEnabled(tcp_enabled)
        if hasattr(self, 'label_3'):
            self.label_3.setEnabled(tcp_enabled)  # IP Address label
        if hasattr(self, 'label_4'):
            self.label_4.setEnabled(tcp_enabled)  # Port label
        
        # Enable/disable Serial Port group
        serial_enabled = (protocol_mode == 'serial')
        if hasattr(self, 'rtu_group'):
            self.rtu_group.setEnabled(serial_enabled)
        
        # Enable/disable COM port dropdown
        if hasattr(self, 'com_port_combo'):
            self.com_port_combo.setEnabled(serial_enabled)
        
        # Also disable individual serial port widgets
        if hasattr(self, 'serial_port'):
            self.serial_port.setEnabled(serial_enabled)
        if hasattr(self, 'baudrate'):
            self.baudrate.setEnabled(serial_enabled)
        if hasattr(self, 'parity'):
            self.parity.setEnabled(serial_enabled)
        if hasattr(self, 'stopbits'):
            self.stopbits.setEnabled(serial_enabled)
        if hasattr(self, 'databits'):
            self.databits.setEnabled(serial_enabled)
        if hasattr(self, 'rtu_radio'):
            self.rtu_radio.setEnabled(serial_enabled)
        if hasattr(self, 'ascii_radio'):
            self.ascii_radio.setEnabled(serial_enabled)
        
        # If switching within Serial Port, ensure ASCII defaults are applied when selected
        if serial_enabled:
            self._apply_ascii_defaults_if_selected()
    
    def _handle_accept(self):
        """Handle accept button click with validation."""
        protocol_mode = self._current_protocol_mode()
        
        # Get connection name
        name = getattr(self, 'connection_name', None)
        connection_name = name.text().strip() if name else ""
        
        if protocol_mode == 'tcp':
            if not self._validate_tcp():
                return
            
            address = self.ipAddress.text().strip()
            port = int(self.portNumber.text().strip())
            
            self.settings = {
                "protocol": "tcp",
                "name": connection_name,
                "address": address,
                "port": port
            }
            
        else:
            if not self._validate_serial():
                return
            
            # Determine mode from radio buttons
            if self.rtu_radio.isChecked():
                mode = "rtu"
            elif self.ascii_radio.isChecked():
                mode = "ascii"
            else:
                mode = "rtu"  # Default fallback
            
            # Map parity names
            parity_map = {"None": "N", "Even": "E", "Odd": "O"}
            # Note: We rely on combo box text for keys. 
            # If we translate combo items, we must map them back.
            # Assuming combo items are English in .ui file or populated here.
            # In Phase 1 we just stick to English keys if UI not translated.
            
            # Get COM port from dropdown or manual entry
            selected_com_port = self._get_selected_com_port()
            if not selected_com_port and hasattr(self, 'serial_port'):
                selected_com_port = self.serial_port.text().strip()
            
            self.settings = {
                "protocol": mode,
                "name": connection_name,
                "port": selected_com_port,  # Serial port
                "baudrate": int(self.baudrate.currentText()),
                "parity": parity_map.get(self.parity.currentText(), 'N'), # Safer get
                "stopbits": int(self.stopbits.currentText()),
                "bytesize": int(self.databits.currentText())
            }
        
        # Call accept to close the dialog
        self.accept()
    
    def accept(self):
        """Accept the dialog - close with accepted result."""
        super().accept()
    
    def _validate_tcp(self):
        """Validate TCP connection parameters."""
        address = self.ipAddress.text().strip()
        port = self.portNumber.text().strip()
        
        if not address:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("IP Address must not be empty!"))
            return False
        
        if not port.isdigit() or not (1 <= int(port) <= 65535):
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Port must be an integer between 1 and 65535."))
            return False
        
        return True
    
    def _validate_serial(self):
        """Validate serial connection parameters."""
        # Get COM port from dropdown or manual entry
        selected_com_port = self._get_selected_com_port()
        if not selected_com_port and hasattr(self, 'serial_port'):
            selected_com_port = self.serial_port.text().strip()
        
        if not selected_com_port:
            QMessageBox.warning(self, self.tr("Input Error"), self.tr("Serial port must be selected or entered!"))
            return False
        
        # Check if selected port contains "Not Connected" warning
        if self.tr("Not Connected") in selected_com_port or "Not Connected" in selected_com_port:
            reply = QMessageBox.question(self, self.tr("Port Warning"), 
                self.tr("The selected port appears to be not connected. Continue anyway?"),
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return False
        
        return True
    
    def _scan_com_ports(self):
        """Scan for available COM ports and populate the dropdown."""
        if not hasattr(self, 'com_port_combo'):
            return
            
        # Clear existing items
        self.com_port_combo.clear()
        
        # Scan for available COM ports and create lookup
        available_ports_dict = {}
        available_ports = serial.tools.list_ports.comports()
        
        for port in available_ports:
            # Store device info by COM port name
            device_name = port.description if port.description else self.tr("Unknown Device")
            com_port = port.device
            available_ports_dict[com_port] = device_name
        
        # Add all COM ports (COM1-COM256) with status
        for i in range(1, 257):
            com_name = f"COM{i}"
            
            if com_name in available_ports_dict:
                # Active port with device description
                device_name = available_ports_dict[com_name]
                
                # Check if device description already contains the COM port name to avoid duplication
                if f"({com_name})" in device_name:
                    display_text = device_name  # Use description as-is since it already contains COM port
                else:
                    display_text = f"{device_name} ({com_name})"  # Add COM port to description
                    
                self.com_port_combo.addItem(display_text, com_name)
            else:
                # Inactive port
                display_text = f"{com_name} ({self.tr('Not Connected')})"
                self.com_port_combo.addItem(display_text, com_name)
        
        # Set to first available active port if any, otherwise first item
        if self.com_port_combo.count() > 0:
            # Try to find first active port
            for i in range(self.com_port_combo.count()):
                if self.tr("Not Connected") not in self.com_port_combo.itemText(i):
                    self.com_port_combo.setCurrentIndex(i)
                    break
            else:
                # No active ports found, set to first item
                self.com_port_combo.setCurrentIndex(0)
    
    def _on_protocol_changed(self):
        """Handle protocol change to rescan COM ports if needed."""
        if self._current_protocol_mode() == 'serial':
            self._scan_com_ports()

    def _apply_ascii_defaults_if_selected(self):
        """If ASCII is selected, apply typical Modbus ASCII defaults (7-E-1)."""
        try:
            if not hasattr(self, 'ascii_radio') or not self.ascii_radio.isChecked():
                return
            # Only override if current settings are RTU-like defaults
            # Databits: set to 7
            if hasattr(self, 'databits'):
                for i in range(self.databits.count()):
                    if self.databits.itemText(i) == "7":
                        self.databits.setCurrentIndex(i)
                        break
            # Parity: set to Even
            if hasattr(self, 'parity'):
                for i in range(self.parity.count()):
                    if self.parity.itemText(i) == "Even":
                        self.parity.setCurrentIndex(i)
                        break
            # Stopbits: set to 1
            if hasattr(self, 'stopbits'):
                for i in range(self.stopbits.count()):
                    if self.stopbits.itemText(i) == "1":
                        self.stopbits.setCurrentIndex(i)
                        break
        except Exception:
            # Non-fatal: leave user selections unchanged on error
            pass
    
    def _get_selected_com_port(self):
        """Get the actual COM port name from the selected item."""
        if not hasattr(self, 'com_port_combo'):
            return ""
        
        current_index = self.com_port_combo.currentIndex()
        if current_index >= 0:
            # Return the user data (actual COM port name)
            com_port = self.com_port_combo.itemData(current_index)
            if com_port:
                return com_port
            
            # Fallback: extract from text
            text = self.com_port_combo.currentText()
            if "(" in text and ")" in text:
                # Extract COM port from "Description (COMX)" format
                start = text.rfind("(") + 1
                end = text.rfind(")")
                if start > 0 and end > start:
                    return text[start:end].strip()
        
        # Fallback: return the current text or empty string
        return self.com_port_combo.currentText().strip()
