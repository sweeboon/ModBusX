from PyQt5.QtWidgets import (
    QDialog, QMessageBox, QTableWidget, QComboBox, QSpinBox, 
    QLineEdit, QPushButton, QCheckBox, QProgressBar, QLabel,
    QTabWidget, QWidget, QTableWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer
from modbusx.models import RegisterMap, RegisterEntry
from modbusx.services.register_validator import MODBUS_REGISTER_TYPES, RegisterValidator
from typing import Dict, List, Optional, Tuple, Union
import time

class BulkOperationsHandler(QObject):
    """
    Handler class for bulk operations dialog.
    Connect this to your Qt Designer dialog using the specified object names.
    """
    
    operation_completed = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.register_map: Optional[RegisterMap] = None
        self.current_worker: Optional[BulkOperationWorker] = None
        
        # Dialog widgets (to be connected from Qt Designer)
        self.dialog: Optional[QDialog] = None
        self.tab_widget: Optional[QTabWidget] = None
        
        # Tab 1: Batch Value Setting
        self.batch_reg_type_combo: Optional[QComboBox] = None
        self.batch_start_addr_spin: Optional[QSpinBox] = None
        self.batch_end_addr_spin: Optional[QSpinBox] = None
        self.batch_new_value_spin: Optional[QSpinBox] = None
        self.batch_apply_btn: Optional[QPushButton] = None
        
        # Tab 2: Address Renumbering
        self.renumber_reg_type_combo: Optional[QComboBox] = None
        self.renumber_current_start_spin: Optional[QSpinBox] = None
        self.renumber_current_end_spin: Optional[QSpinBox] = None
        self.renumber_new_start_spin: Optional[QSpinBox] = None
        self.renumber_apply_btn: Optional[QPushButton] = None
        
        # Tab 3: Type Conversion
        self.convert_old_type_combo: Optional[QComboBox] = None
        self.convert_start_addr_spin: Optional[QSpinBox] = None
        self.convert_end_addr_spin: Optional[QSpinBox] = None
        self.convert_new_type_combo: Optional[QComboBox] = None
        self.convert_new_start_spin: Optional[QSpinBox] = None
        self.convert_apply_btn: Optional[QPushButton] = None
        
        # Tab 4: Pattern Fill
        self.pattern_reg_type_combo: Optional[QComboBox] = None
        self.pattern_start_addr_spin: Optional[QSpinBox] = None
        self.pattern_end_addr_spin: Optional[QSpinBox] = None
        self.pattern_values_edit: Optional[QLineEdit] = None  # Comma-separated values
        self.pattern_apply_btn: Optional[QPushButton] = None
        
        # Progress and control widgets
        self.progress_bar: Optional[QProgressBar] = None
        self.status_label: Optional[QLabel] = None
        self.cancel_btn: Optional[QPushButton] = None
        self.close_btn: Optional[QPushButton] = None
        
        # Validation options
        self.validate_ranges_cb: Optional[QCheckBox] = None
        self.confirm_operations_cb: Optional[QCheckBox] = None
    
    def connect_widgets(self, dialog_widgets: Dict[str, QWidget]):
        """
        Connect Qt Designer widgets using their object names.
        
        Expected object names for Qt Designer dialog:
        - tab_widget: QTabWidget
        - batch_reg_type_combo, batch_start_addr_spin, batch_end_addr_spin, batch_new_value_spin, batch_apply_btn
        - renumber_reg_type_combo, renumber_current_start_spin, renumber_current_end_spin, renumber_new_start_spin, renumber_apply_btn
        - convert_old_type_combo, convert_start_addr_spin, convert_end_addr_spin, convert_new_type_combo, convert_new_start_spin, convert_apply_btn
        - pattern_reg_type_combo, pattern_start_addr_spin, pattern_end_addr_spin, pattern_values_edit, pattern_apply_btn
        - progress_bar, status_label, cancel_btn, close_btn
        - validate_ranges_cb, confirm_operations_cb
        """
        connected_widgets = []
        missing_widgets = []
        
        for name, widget in dialog_widgets.items():
            if hasattr(self, name):
                setattr(self, name, widget)
                connected_widgets.append(name)
            else:
                missing_widgets.append(name)
        
        # Optional debug output (can be enabled for troubleshooting)
        # print(f"Connected widgets: {connected_widgets}")
        # if missing_widgets:
        #     print(f"Missing widgets: {missing_widgets}")
        
        self._setup_widgets()
        self._connect_signals()
    
    def set_register_map(self, register_map: RegisterMap):
        """Set the register map for bulk operations."""
        self.register_map = register_map
    
    def _setup_widgets(self):
        """Setup widget properties and initial values."""
        # Setup combo boxes with register types
        combo_names = ['batch_reg_type_combo', 'renumber_reg_type_combo', 
                      'convert_old_type_combo', 'convert_new_type_combo',
                      'pattern_reg_type_combo']
        
        for combo_name in combo_names:
            combo = getattr(self, combo_name, None)
            if combo:
                combo.clear()
                for info in MODBUS_REGISTER_TYPES.items():
                    combo.addItem(f"info{'description'}", info['code'])
                # Optional debug: print(f"Added {combo.count()} items to {combo_name}")
            # Optional debug: else: print(f"Warning: {combo_name} widget not found")
        
        # Setup spinboxes with reasonable ranges
        for spin in [self.batch_start_addr_spin, self.batch_end_addr_spin,
                    self.renumber_current_start_spin, self.renumber_current_end_spin, self.renumber_new_start_spin,
                    self.convert_start_addr_spin, self.convert_end_addr_spin, self.convert_new_start_spin,
                    self.pattern_start_addr_spin, self.pattern_end_addr_spin]:
            if spin:
                spin.setRange(1, 49999)
        
        # Setup value spinboxes
        for spin in [self.batch_new_value_spin]:
            if spin:
                spin.setRange(0, 65535)
        
        # Setup progress bar
        if self.progress_bar:
            self.progress_bar.setVisible(False)
            self.progress_bar.setRange(0, 100)
        
        # Setup status label
        if self.status_label:
            self.status_label.setText("Ready")
        
        # Setup cancel button
        if self.cancel_btn:
            self.cancel_btn.setVisible(False)
        
        # Set default validation options
        if self.validate_ranges_cb:
            self.validate_ranges_cb.setChecked(True)
        if self.confirm_operations_cb:
            self.confirm_operations_cb.setChecked(True)
    
    def _connect_signals(self):
        """Connect widget signals."""
        if self.batch_apply_btn:
            self.batch_apply_btn.clicked.connect(self.apply_batch_value_setting)
        if self.renumber_apply_btn:
            self.renumber_apply_btn.clicked.connect(self.apply_address_renumbering)
        if self.convert_apply_btn:
            self.convert_apply_btn.clicked.connect(self.apply_type_conversion)
        if self.pattern_apply_btn:
            self.pattern_apply_btn.clicked.connect(self.apply_pattern_fill)
        
        if self.cancel_btn:
            self.cancel_btn.clicked.connect(self.cancel_operation)
        if self.close_btn:
            self.close_btn.clicked.connect(self.close_dialog)
        
        # Update address ranges when register type changes
        for combo in [self.batch_reg_type_combo, self.renumber_reg_type_combo,
                     self.convert_old_type_combo, self.convert_new_type_combo,
                     self.pattern_reg_type_combo]:
            if combo:
                combo.currentTextChanged.connect(self._update_address_ranges)
    
    def _update_address_ranges(self):
        """Update address ranges based on selected register types."""
        sender = self.sender()
        if not sender:
            return
        
        reg_type = sender.currentData()
        if not reg_type:
            return
        
        reg_type_upper = reg_type.upper()
        addr_range = RegisterValidator.get_address_range(reg_type)
        
        # Update corresponding spinboxes
        if sender == self.batch_reg_type_combo:
            spinboxes = [self.batch_start_addr_spin, self.batch_end_addr_spin]
        elif sender == self.renumber_reg_type_combo:
            spinboxes = [self.renumber_current_start_spin, self.renumber_current_end_spin, self.renumber_new_start_spin]
        elif sender == self.convert_old_type_combo:
            spinboxes = [self.convert_start_addr_spin, self.convert_end_addr_spin]
        elif sender == self.convert_new_type_combo:
            spinboxes = [self.convert_new_start_spin]
        elif sender == self.pattern_reg_type_combo:
            spinboxes = [self.pattern_start_addr_spin, self.pattern_end_addr_spin]
        else:
            return
        
        for spinbox in spinboxes:
            if spinbox:
                spinbox.setRange(addr_range[0], addr_range[1])
                spinbox.setValue(addr_range[0])
    
    def apply_batch_value_setting(self):
        """Apply batch value setting operation."""
        if not self.register_map:
            QMessageBox.warning(None, "Error", "No register map available")
            return
        
        reg_type = self.batch_reg_type_combo.currentData()
        start_addr = self.batch_start_addr_spin.value()
        end_addr = self.batch_end_addr_spin.value()
        new_value = self.batch_new_value_spin.value()
        
        # Check if register type is selected
        if not reg_type:
            QMessageBox.warning(None, "No Selection", "Please select a register type")
            return
            
        if start_addr > end_addr:
            QMessageBox.warning(None, "Invalid Range", "Start address must be less than or equal to end address")
            return
        
        # Validate value
        try:
            RegisterValidator.validate_register_value(new_value, reg_type)
        except Exception as e:
            QMessageBox.warning(None, "Invalid Value", f"Invalid value for {reg_type.upper() if reg_type else 'unknown'} registers: {str(e)}")
            return
        
        addresses = list(range(start_addr, end_addr + 1))
        
        # Confirm operation
        if self.confirm_operations_cb and self.confirm_operations_cb.isChecked():
            reg_type_display = reg_type.upper() if reg_type else 'UNKNOWN'
            reply = QMessageBox.question(None, "Confirm Operation",
                f"Set {len(addresses)} {reg_type_display} registers to value {new_value}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self._start_operation("batch_value_set", {
            'register_map': self.register_map,
            'reg_type': reg_type,
            'addresses': addresses,
            'new_value': new_value
        })
    
    def apply_address_renumbering(self):
        """Apply address renumbering operation."""
        if not self.register_map:
            QMessageBox.warning(None, "Error", "No register map available")
            return
        
        reg_type = self.renumber_reg_type_combo.currentData()
        current_start = self.renumber_current_start_spin.value()
        current_end = self.renumber_current_end_spin.value()
        new_start = self.renumber_new_start_spin.value()
        
        # Check if register type is selected
        if not reg_type:
            QMessageBox.warning(None, "No Selection", "Please select a register type")
            return
            
        if current_start > current_end:
            QMessageBox.warning(None, "Invalid Range", "Current start address must be less than or equal to current end address")
            return
        
        old_addresses = list(range(current_start, current_end + 1))
        
        # Confirm operation
        if self.confirm_operations_cb and self.confirm_operations_cb.isChecked():
            reg_type_display = reg_type.upper() if reg_type else 'UNKNOWN'
            reply = QMessageBox.question(None, "Confirm Operation",
                f"Renumber {len(old_addresses)} {reg_type_display} registers starting from {new_start}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self._start_operation("address_renumber", {
            'register_map': self.register_map,
            'reg_type': reg_type,
            'old_addresses': old_addresses,
            'new_start_addr': new_start
        })
    
    def apply_type_conversion(self):
        """Apply type conversion operation."""
        if not self.register_map:
            QMessageBox.warning(None, "Error", "No register map available")
            return
        
        old_type = self.convert_old_type_combo.currentData()
        new_type = self.convert_new_type_combo.currentData()
        start_addr = self.convert_start_addr_spin.value()
        end_addr = self.convert_end_addr_spin.value()
        new_start = self.convert_new_start_spin.value()
        
        # Check if register types are selected
        if not old_type or not new_type:
            QMessageBox.warning(None, "No Selection", "Please select both old and new register types")
            return
            
        if old_type == new_type:
            QMessageBox.warning(None, "Invalid Conversion", "Old and new types must be different")
            return
        
        if start_addr > end_addr:
            QMessageBox.warning(None, "Invalid Range", "Start address must be less than or equal to end address")
            return
        
        # Check if types are convertible
        convertible_pairs = [('hr', 'ir'), ('ir', 'hr')]
        if (old_type, new_type) not in convertible_pairs:
            old_display = old_type.upper() if old_type else 'UNKNOWN'
            new_display = new_type.upper() if new_type else 'UNKNOWN'
            QMessageBox.warning(None, "Invalid Conversion", 
                f"Cannot convert from {old_display} to {new_display}")
            return
        
        addresses = list(range(start_addr, end_addr + 1))
        
        # Confirm operation
        if self.confirm_operations_cb and self.confirm_operations_cb.isChecked():
            old_display = old_type.upper() if old_type else 'UNKNOWN'
            new_display = new_type.upper() if new_type else 'UNKNOWN'
            reply = QMessageBox.question(None, "Confirm Operation",
                f"Convert {len(addresses)} registers from {old_display} to {new_display}?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self._start_operation("type_conversion", {
            'register_map': self.register_map,
            'old_type': old_type,
            'new_type': new_type,
            'addresses': addresses,
            'new_start_addr': new_start
        })
    
    def apply_pattern_fill(self):
        """Apply pattern fill operation."""
        if not self.register_map:
            QMessageBox.warning(None, "Error", "No register map available")
            return
        
        reg_type = self.pattern_reg_type_combo.currentData()
        start_addr = self.pattern_start_addr_spin.value()
        end_addr = self.pattern_end_addr_spin.value()
        pattern_text = self.pattern_values_edit.text().strip()
        
        # Check if register type is selected
        if not reg_type:
            QMessageBox.warning(None, "No Selection", "Please select a register type")
            return
            
        if start_addr > end_addr:
            QMessageBox.warning(None, "Invalid Range", "Start address must be less than or equal to end address")
            return
        
        if not pattern_text:
            QMessageBox.warning(None, "No Pattern", "Please enter pattern values (comma-separated)")
            return
        
        # Parse pattern
        try:
            pattern = [int(x.strip()) for x in pattern_text.split(',')]
            if not pattern:
                raise ValueError("Empty pattern")
        except ValueError:
            QMessageBox.warning(None, "Invalid Pattern", "Pattern must be comma-separated integers")
            return
        
        # Validate pattern values
        try:
            RegisterValidator.validate_pattern_values(pattern, reg_type)
        except Exception as e:
            reg_type_display = reg_type.upper() if reg_type else 'UNKNOWN'
            QMessageBox.warning(None, "Invalid Pattern Value", f"Invalid pattern values for {reg_type_display} registers: {str(e)}")
            return
        
        addresses = list(range(start_addr, end_addr + 1))
        
        # Confirm operation
        if self.confirm_operations_cb and self.confirm_operations_cb.isChecked():
            reg_type_display = reg_type.upper() if reg_type else 'UNKNOWN'
            reply = QMessageBox.question(None, "Confirm Operation",
                f"Apply pattern {pattern} to {len(addresses)} {reg_type_display} registers?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return
        
        self._start_operation("pattern_fill", {
            'register_map': self.register_map,
            'reg_type': reg_type,
            'addresses': addresses,
            'pattern': pattern
        })
    
    def _start_operation(self, operation_type: str, operation_data: Dict):
        """Start a bulk operation in a background thread."""
        if self.current_worker and self.current_worker.isRunning():
            QMessageBox.warning(None, "Operation in Progress", "Please wait for current operation to complete")
            return
        
        # Setup UI for operation
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
        if self.cancel_btn:
            self.cancel_btn.setVisible(True)
        if self.status_label:
            self.status_label.setText("Starting operation...")
        
        # Disable operation buttons
        for btn in [self.batch_apply_btn, self.renumber_apply_btn, 
                   self.convert_apply_btn, self.pattern_apply_btn]:
            if btn:
                btn.setEnabled(False)
        
        # Start worker
        self.current_worker = BulkOperationWorker(operation_type, operation_data)
        self.current_worker.progress.connect(self._update_progress)
        self.current_worker.finished.connect(self._operation_finished)
        self.current_worker.start()
    
    def cancel_operation(self):
        """Cancel the current operation."""
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.cancel_operation()
            if self.status_label:
                self.status_label.setText("Cancelling...")
    
    def _update_progress(self, value: int, message: str):
        """Update progress bar and status."""
        if self.progress_bar:
            self.progress_bar.setValue(value)
        if self.status_label:
            self.status_label.setText(message)
    
    def _operation_finished(self, success: bool, message: str):
        """Handle operation completion."""
        # Reset UI
        if self.progress_bar:
            self.progress_bar.setVisible(False)
        if self.cancel_btn:
            self.cancel_btn.setVisible(False)
        if self.status_label:
            self.status_label.setText("Ready")
        
        # Re-enable operation buttons
        for btn in [self.batch_apply_btn, self.renumber_apply_btn,
                   self.convert_apply_btn, self.pattern_apply_btn]:
            if btn:
                btn.setEnabled(True)
        
        # Show result
        if success:
            QMessageBox.information(None, "Operation Complete", message)
        else:
            QMessageBox.warning(None, "Operation Failed", message)
        
        # Emit signal for external handlers
        self.operation_completed.emit(success, message)
        
        # Clean up worker
        if self.current_worker:
            self.current_worker.deleteLater()
            self.current_worker = None
    
    def close_dialog(self):
        """Close the bulk operations dialog."""
        if self.current_worker and self.current_worker.isRunning():
            reply = QMessageBox.question(None, "Operation in Progress",
                "An operation is currently running. Cancel and close?",
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.cancel_operation()
                # Wait briefly for cancellation
                QTimer.singleShot(500, self._force_close)
            return
        
        if self.dialog:
            self.dialog.close()
    
    def _force_close(self):
        """Force close the dialog after cancellation."""
        if self.dialog:
            self.dialog.close()

class BulkOperationWorker(QThread):
    """Worker thread for bulk operations to prevent UI freezing."""
    
    progress = pyqtSignal(int, str)  # progress_value, status_message
    finished = pyqtSignal(bool, str)  # success, message
    
    def __init__(self, operation_type: str, operation_data: Dict):
        super().__init__()
        self.operation_type = operation_type
        self.operation_data = operation_data
        self.should_cancel = False
    
    def cancel_operation(self):
        """Cancel the current operation."""
        self.should_cancel = True
    
    def run(self):
        """Execute the bulk operation."""
        try:
            if self.operation_type == "batch_value_set":
                self._batch_value_set()
            elif self.operation_type == "address_renumber":
                self._address_renumber()
            elif self.operation_type == "type_conversion":
                self._type_conversion()
            elif self.operation_type == "pattern_fill":
                self._pattern_fill()
            else:
                self.finished.emit(False, f"Unknown operation type: {self.operation_type}")
        except Exception as e:
            self.finished.emit(False, f"Operation failed: {str(e)}")
    
    def _batch_value_set(self):
        """Set multiple registers to the same value."""
        register_map = self.operation_data['register_map']
        reg_type = self.operation_data['reg_type']
        addresses = self.operation_data['addresses']
        new_value = self.operation_data['new_value']
        
        reg_dict = getattr(register_map, reg_type)
        total = len(addresses)
        
        for i, addr in enumerate(addresses):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            if addr in reg_dict:
                reg_dict[addr].value = new_value
            
            progress = int((i + 1) * 100 / total)
            self.progress.emit(progress, f"Setting value for address {addr}")
            self.msleep(1)  # Small delay to show progress
        
        self.finished.emit(True, f"Successfully updated {total} registers")
    
    def _address_renumber(self):
        """Renumber addresses in sequence."""
        register_map = self.operation_data['register_map']
        reg_type = self.operation_data['reg_type']
        old_addresses = sorted(self.operation_data['old_addresses'])
        new_start_addr = self.operation_data['new_start_addr']
        
        reg_dict = getattr(register_map, reg_type)
        total = len(old_addresses)
        
        # Create temporary storage for entries
        temp_entries = []
        
        # First pass: remove entries and store them
        for i, old_addr in enumerate(old_addresses):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            if old_addr in reg_dict:
                entry = reg_dict[old_addr]
                del reg_dict[old_addr]
                temp_entries.append(entry)
            
            progress = int((i + 1) * 50 / total)  # First 50%
            self.progress.emit(progress, f"Removing address {old_addr}")
            self.msleep(1)
        
        # Second pass: add entries with new addresses
        for i, entry in enumerate(temp_entries):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            new_addr = new_start_addr + i
            entry.addr = new_addr
            reg_dict[new_addr] = entry
            
            progress = int(50 + (i + 1) * 50 / total)  # Second 50%
            self.progress.emit(progress, f"Adding address {new_addr}")
            self.msleep(1)
        
        self.finished.emit(True, f"Successfully renumbered {total} registers")
    
    def _type_conversion(self):
        """Convert registers between compatible types."""
        register_map = self.operation_data['register_map']
        old_type = self.operation_data['old_type']
        new_type = self.operation_data['new_type']
        addresses = self.operation_data['addresses']
        new_start_addr = self.operation_data['new_start_addr']
        
        old_dict = getattr(register_map, old_type)
        new_dict = getattr(register_map, new_type)
        total = len(addresses)
        
        # Create temporary storage
        temp_entries = []
        
        # Remove from old type
        for i, old_addr in enumerate(addresses):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            if old_addr in old_dict:
                entry = old_dict[old_addr]
                del old_dict[old_addr]
                temp_entries.append(entry)
            
            progress = int((i + 1) * 50 / total)
            self.progress.emit(progress, f"Converting {old_type.upper()} address {old_addr}")
            self.msleep(1)
        
        # Add to new type
        for i, entry in enumerate(temp_entries):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            new_addr = new_start_addr + i
            entry.reg_type = new_type
            entry.addr = new_addr
            new_dict[new_addr] = entry
            
            progress = int(50 + (i + 1) * 50 / total)
            self.progress.emit(progress, f"Adding {new_type.upper()} address {new_addr}")
            self.msleep(1)
        
        self.finished.emit(True, f"Successfully converted {total} registers from {old_type.upper()} to {new_type.upper()}")
    
    def _pattern_fill(self):
        """Fill registers with a pattern."""
        register_map = self.operation_data['register_map']
        reg_type = self.operation_data['reg_type']
        addresses = self.operation_data['addresses']
        pattern = self.operation_data['pattern']
        
        reg_dict = getattr(register_map, reg_type)
        total = len(addresses)
        pattern_length = len(pattern)
        
        for i, addr in enumerate(addresses):
            if self.should_cancel:
                self.finished.emit(False, "Operation cancelled by user")
                return
            
            if addr in reg_dict:
                pattern_value = pattern[i % pattern_length]
                reg_dict[addr].value = pattern_value
            
            progress = int((i + 1) * 100 / total)
            self.progress.emit(progress, f"Setting pattern value for address {addr}")
            self.msleep(1)
        
        self.finished.emit(True, f"Successfully applied pattern to {total} registers")
