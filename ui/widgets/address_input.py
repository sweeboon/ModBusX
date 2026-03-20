"""
Custom Address Input Widget for ModBus addressing modes.
Handles PLC (6-digit) and Protocol (0x prefixed hex) addressing automatically.
"""

from PyQt5.QtWidgets import QLineEdit, QWidget
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QValidator
from ...services.register_validator import RegisterValidator, ValidationError

class AddressInputWidget(QLineEdit):
    """Custom address input widget that adapts to PLC/Protocol modes."""
    
    addressChanged = pyqtSignal(str)  # Emits the raw address value
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reg_type = 'hr'
        self.validator = AddressValidator(self)
        self.setValidator(self.validator)
        
        # Connect signals
        self.textChanged.connect(self._on_text_changed)
        # Normalize on commit (focus out / Return)
        try:
            from PyQt5.QtWidgets import QLineEdit
            if hasattr(self, 'editingFinished'):
                self.editingFinished.connect(self._on_editing_finished)
        except Exception:
            pass
        
        # Initialize based on current mode
        self._update_for_mode()
    
    def set_register_type(self, reg_type):
        """Set the register type for this input."""
        old_reg_type = self.reg_type
        self.reg_type = reg_type
        self.validator.set_register_type(reg_type)
        
        # If register type changed, update the default address
        if old_reg_type != reg_type:
            self._update_default_for_register_type()
        
        self._update_for_mode()
    
    def _update_default_for_register_type(self):
        """Update the default address when register type changes."""
        mode = RegisterValidator.get_address_mode()
        
        if mode == 'plc':
            self._set_default_plc_address()
        else:
            # Protocol mode - set default hex address
            self.setText('0x0000')
            self.setPlaceholderText('0x0000')
    
    def _update_for_mode(self):
        """Update widget appearance and behavior based on current addressing mode."""
        mode = RegisterValidator.get_address_mode()
        
        if mode == 'protocol':
            # Protocol mode - hex with locked 0x prefix
            self._setup_protocol_mode()
        else:
            # PLC mode - 6-digit format
            self._setup_plc_mode()
    
    def _setup_protocol_mode(self):
        """Setup for protocol mode. Allow hex (0x####) or decimal while typing."""
        # Do not force 0x while editing; normalize on commit
        self.setPlaceholderText('0x0000 or decimal')
        self.setMaxLength(10)  # allow up to 5 decimal digits or 0xFFFF
    
    def _setup_plc_mode(self):
        """Setup for PLC (6-digit) mode with locked prefix."""
        # Clear any 0x prefix if switching from protocol mode
        current_text = self.text()
        if current_text.startswith('0x'):
            try:
                # Convert from hex to internal address, then to PLC display format
                hex_val = int(current_text[2:], 16)
                # hex_val is the protocol address (0-based), convert to internal (1-based) first
                internal_addr = hex_val + 1
                display_addr = RegisterValidator.address_to_display(internal_addr, self.reg_type, 'plc')
                self.setText(display_addr)
            except (ValueError, ValidationError):
                # Set default PLC address
                self._set_default_plc_address()
        elif not current_text or not current_text.isdigit():
            self._set_default_plc_address()
        else:
            # Ensure existing text has correct prefix
            self._ensure_plc_prefix()
        
        self.setMaxLength(6)  # 6-digit PLC format
    
    def _set_default_plc_address(self):
        """Set default PLC address based on register type."""
        try:
            default_addr = RegisterValidator.address_to_display(1, self.reg_type, 'plc')
            self.setText(default_addr)
            self.setPlaceholderText(f'e.g., {default_addr}')
        except (ValidationError, KeyError):
            self.setText('400001')
            self.setPlaceholderText('e.g., 400001')
    
    def keyPressEvent(self, event):
        """Handle key press events, especially for locked prefixes."""
        mode = RegisterValidator.get_address_mode()
        cursor_pos = self.cursorPosition()
        
        if mode == 'protocol':
            # If text starts with 0x, keep the prefix intact; otherwise allow free editing
            if self.text().startswith('0x'):
                if cursor_pos <= 2:  # Within 0x prefix
                    if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
                        return
                    elif event.key() == Qt.Key_Left and cursor_pos <= 2:
                        return
                    elif event.key() == Qt.Key_Home:
                        self.setCursorPosition(2)
                        return
        elif mode == 'plc':
            # In PLC mode, prevent deletion/modification of register type prefix
            prefix = self._get_plc_prefix()
            prefix_len = len(prefix)
            
            if cursor_pos < prefix_len:  # Within prefix
                if event.key() in (Qt.Key_Backspace, Qt.Key_Delete):
                    # Don't allow deletion of prefix
                    return
                elif event.key() == Qt.Key_Left and cursor_pos <= 1:
                    # Don't allow cursor to go before prefix
                    return
        
        # Handle Home key for PLC mode (do this before super() call)
        if mode == 'plc' and event.key() == Qt.Key_Home:
            prefix_len = len(self._get_plc_prefix())
            self.setCursorPosition(prefix_len)
            return
        elif mode == 'plc':
            # Handle digit input in prefix area
            prefix_len = len(self._get_plc_prefix())
            if cursor_pos < prefix_len and event.text() and event.text().isdigit():
                # If user types a digit in prefix area, move to after prefix
                self.setCursorPosition(prefix_len)
        
        super().keyPressEvent(event)
        
        # After key press, ensure PLC prefix
        if mode == 'plc':
            self._ensure_plc_prefix()
    
    def _get_plc_prefix(self):
        """Get the locked PLC prefix for the current register type."""
        try:
            from ...services.register_validator import MODBUS_REGISTER_TYPES
            reg_type_upper = self.reg_type.upper()
            if reg_type_upper in MODBUS_REGISTER_TYPES:
                base = MODBUS_REGISTER_TYPES[reg_type_upper]['plc_display_base']
                # Extract the first digit(s) as the locked prefix
                if reg_type_upper == 'CO':
                    return '0'  # 0xxxxx
                elif reg_type_upper == 'DI':
                    return '1'  # 1xxxxx  
                elif reg_type_upper == 'IR':
                    return '3'  # 3xxxxx
                elif reg_type_upper == 'HR':
                    return '4'  # 4xxxxx
        except:
            pass
        return '4'  # Default to HR prefix

    def _ensure_plc_prefix(self):
        """Ensure PLC prefix is maintained and cursor is positioned correctly."""
        current_text = self.text()
        prefix = self._get_plc_prefix()
        prefix_len = len(prefix)
        
        if not current_text.startswith(prefix):
            # Extract all numeric part and rebuild with correct prefix
            numeric_part = ''.join(c for c in current_text if c.isdigit())
            
            # Remove the incorrect prefix digit if it exists
            if len(numeric_part) >= 6:
                # Take the last 5 digits (skip the first digit which was the wrong prefix)
                numeric_part = numeric_part[-5:]
            
            # Ensure we have exactly 5 digits after prefix (total 6 digits)
            if len(numeric_part) < 5:
                numeric_part = numeric_part.ljust(5, '0')  # Pad with zeros to make 5 digits
            elif len(numeric_part) > 5:
                numeric_part = numeric_part[:5]  # Truncate to 5 digits
            
            new_text = prefix + numeric_part  # Total: 6 digits
            
            # Preserve cursor position relative to the editable part
            old_cursor = self.cursorPosition()
            self.blockSignals(True)
            self.setText(new_text)
            self.blockSignals(False)
            
            # Position cursor in the editable area
            new_cursor = max(prefix_len, min(old_cursor, len(new_text)))
            self.setCursorPosition(new_cursor)

    def focusInEvent(self, event):
        """Handle focus in event."""
        super().focusInEvent(event)
        mode = RegisterValidator.get_address_mode()
        
        if mode == 'protocol':
            # In protocol mode, position cursor after 0x
            if self.text() == '0x' or self.cursorPosition() < 2:
                self.setCursorPosition(2)
        elif mode == 'plc':
            # In PLC mode, position cursor after prefix
            prefix_len = len(self._get_plc_prefix())
            if self.cursorPosition() < prefix_len:
                self.setCursorPosition(prefix_len)
    
    def _on_text_changed(self, text):
        """Handle text changes."""
        mode = RegisterValidator.get_address_mode()
        
        if mode == 'protocol':
            # Allow both hex and decimal while typing; normalization happens on commit
            pass
        elif mode == 'plc':
            # Ensure PLC prefix is maintained
            prefix = self._get_plc_prefix()
            if not text.startswith(prefix):
                self.blockSignals(True)
                self._ensure_plc_prefix()
                self.blockSignals(False)
                return
        
        # Emit the address change signal
        self.addressChanged.emit(text)

    def _on_editing_finished(self):
        """Normalize protocol-mode decimal input to hex display on commit."""
        try:
            mode = RegisterValidator.get_address_mode()
            if mode != 'protocol':
                return
            txt = self.text().strip()
            if not txt:
                return
            if not txt.lower().startswith('0x'):
                # Convert decimal to normalized protocol hex display
                try:
                    internal = RegisterValidator.display_to_address(txt, self.reg_type, mode='protocol')
                    normalized = RegisterValidator.address_to_display(internal, self.reg_type, mode='protocol')
                    self.blockSignals(True)
                    self.setText(normalized)
                    self.blockSignals(False)
                    self.addressChanged.emit(self.text())
                except ValidationError:
                    # Keep as-is; dialog validation will handle errors later
                    pass
        except Exception:
            pass
    
    def get_address_value(self):
        """Get the address value as an integer."""
        try:
            return RegisterValidator.display_to_address(self.text(), self.reg_type)
        except ValidationError:
            raise ValueError(f"Invalid address: {self.text()}")
    
    def set_address_value(self, addr):
        """Set the address value from an integer."""
        try:
            display_addr = RegisterValidator.address_to_display(addr, self.reg_type)
            self.setText(display_addr)
        except ValidationError as e:
            raise ValueError(f"Cannot set address {addr}: {e}")
    
    def update_mode(self):
        """Update widget for current addressing mode - call when mode changes."""
        self._update_for_mode()

class AddressValidator(QValidator):
    """Validator for address input based on current mode."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.reg_type = 'hr'  # Default register type
    
    def set_register_type(self, reg_type):
        """Set the register type for validation."""
        self.reg_type = reg_type
    
    def validate(self, input_str, pos):
        """Validate input based on current addressing mode."""
        if not input_str:
            return QValidator.Intermediate, input_str, pos
            
        mode = RegisterValidator.get_address_mode()
        
        try:
            if mode == 'protocol':
                # Allow either hex (0x####) or decimal input
                if input_str.lower().startswith('0x'):
                    hex_part = input_str[2:]
                    if hex_part:
                        int(hex_part, 16)
                else:
                    int(input_str)
            else:
                # PLC mode - should be numeric
                int(input_str)
                
            # Try to validate with RegisterValidator
            RegisterValidator.display_to_address(input_str, self.reg_type)
            return QValidator.Acceptable, input_str, pos
            
        except (ValueError, ValidationError):
            return QValidator.Intermediate, input_str, pos
