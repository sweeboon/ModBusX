"""
Manual Bulk Operations Dialog

This is a fallback implementation that creates the bulk operations dialog 
programmatically without relying on the .ui file, in case there are issues
with UI file loading.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget, QGroupBox,
    QGridLayout, QLabel, QComboBox, QSpinBox, QPushButton, QLineEdit,
    QProgressBar, QCheckBox, QSpacerItem, QSizePolicy, QMessageBox
)
from PyQt5.QtCore import pyqtSignal
from modbusx.managers.bulk_operations_manager import BulkOperationsHandler
from modbusx.models import RegisterMap
from modbusx.services.register_validator import MODBUS_REGISTER_TYPES
from typing import Optional


class ManualBulkOperationsDialog(QDialog):
    """Manually created bulk operations dialog as fallback."""
    
    operation_completed = pyqtSignal(bool, str)
    
    def __init__(self, register_map: Optional[RegisterMap] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Operations")
        self.setFixedSize(600, 500)
        
        # Create the UI programmatically
        self._create_ui()
        
        # Initialize bulk operations handler
        self.bulk_handler = BulkOperationsHandler(self)
        self.bulk_handler.operation_completed.connect(self.operation_completed)
        
        # Connect widgets to handler
        self._connect_handler()
        
        # Connect close button
        self.close_btn.clicked.connect(self.accept)
        
        # Set register map if provided
        if register_map:
            self.set_register_map(register_map)
    
    def _create_ui(self):
        """Create the UI programmatically."""
        main_layout = QVBoxLayout(self)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Create tabs
        self._create_batch_tab()
        self._create_renumber_tab()
        self._create_convert_tab()
        self._create_pattern_tab()
        
        # Validation options
        validation_group = QGroupBox("Validation Options")
        validation_layout = QHBoxLayout(validation_group)
        
        self.validate_ranges_cb = QCheckBox("Validate address ranges")
        self.validate_ranges_cb.setChecked(True)
        validation_layout.addWidget(self.validate_ranges_cb)
        
        self.confirm_operations_cb = QCheckBox("Confirm operations")
        self.confirm_operations_cb.setChecked(True)
        validation_layout.addWidget(self.confirm_operations_cb)
        
        main_layout.addWidget(validation_group)
        
        # Status and progress
        self.status_label = QLabel("Ready")
        main_layout.addWidget(self.status_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # Buttons
        button_layout = QHBoxLayout()
        spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)
        button_layout.addItem(spacer)
        
        self.cancel_btn = QPushButton("Cancel Operation")
        self.cancel_btn.setVisible(False)
        button_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        button_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(button_layout)
    
    def _create_batch_tab(self):
        """Create batch value setting tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        group = QGroupBox("Batch Value Settings")
        grid = QGridLayout(group)
        
        # Register type
        grid.addWidget(QLabel("Register Type:"), 0, 0)
        self.batch_reg_type_combo = QComboBox()
        self._populate_combo(self.batch_reg_type_combo)
        grid.addWidget(self.batch_reg_type_combo, 0, 1)
        
        # Start address
        grid.addWidget(QLabel("Start Address:"), 1, 0)
        self.batch_start_addr_spin = QSpinBox()
        self.batch_start_addr_spin.setRange(1, 49999)
        self.batch_start_addr_spin.setValue(40001)
        grid.addWidget(self.batch_start_addr_spin, 1, 1)
        
        # End address
        grid.addWidget(QLabel("End Address:"), 2, 0)
        self.batch_end_addr_spin = QSpinBox()
        self.batch_end_addr_spin.setRange(1, 49999)
        self.batch_end_addr_spin.setValue(40010)
        grid.addWidget(self.batch_end_addr_spin, 2, 1)
        
        # New value
        grid.addWidget(QLabel("New Value:"), 3, 0)
        self.batch_new_value_spin = QSpinBox()
        self.batch_new_value_spin.setRange(0, 65535)
        grid.addWidget(self.batch_new_value_spin, 3, 1)
        
        # Apply button
        self.batch_apply_btn = QPushButton("Apply Batch Value")
        grid.addWidget(self.batch_apply_btn, 4, 1)
        
        layout.addWidget(group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Batch Value Setting")
    
    def _create_renumber_tab(self):
        """Create address renumbering tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        group = QGroupBox("Address Renumbering Settings")
        grid = QGridLayout(group)
        
        # Register type
        grid.addWidget(QLabel("Register Type:"), 0, 0)
        self.renumber_reg_type_combo = QComboBox()
        self._populate_combo(self.renumber_reg_type_combo)
        grid.addWidget(self.renumber_reg_type_combo, 0, 1)
        
        # Current start
        grid.addWidget(QLabel("Current Start Address:"), 1, 0)
        self.renumber_current_start_spin = QSpinBox()
        self.renumber_current_start_spin.setRange(1, 49999)
        self.renumber_current_start_spin.setValue(40001)
        grid.addWidget(self.renumber_current_start_spin, 1, 1)
        
        # Current end
        grid.addWidget(QLabel("Current End Address:"), 2, 0)
        self.renumber_current_end_spin = QSpinBox()
        self.renumber_current_end_spin.setRange(1, 49999)
        self.renumber_current_end_spin.setValue(40010)
        grid.addWidget(self.renumber_current_end_spin, 2, 1)
        
        # New start
        grid.addWidget(QLabel("New Start Address:"), 3, 0)
        self.renumber_new_start_spin = QSpinBox()
        self.renumber_new_start_spin.setRange(1, 49999)
        self.renumber_new_start_spin.setValue(40021)
        grid.addWidget(self.renumber_new_start_spin, 3, 1)
        
        # Apply button
        self.renumber_apply_btn = QPushButton("Apply Renumbering")
        grid.addWidget(self.renumber_apply_btn, 4, 1)
        
        layout.addWidget(group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Address Renumbering")
    
    def _create_convert_tab(self):
        """Create type conversion tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        group = QGroupBox("Type Conversion Settings")
        grid = QGridLayout(group)
        
        # Old type
        grid.addWidget(QLabel("Current Type:"), 0, 0)
        self.convert_old_type_combo = QComboBox()
        self._populate_combo(self.convert_old_type_combo)
        grid.addWidget(self.convert_old_type_combo, 0, 1)
        
        # Start address
        grid.addWidget(QLabel("Start Address:"), 1, 0)
        self.convert_start_addr_spin = QSpinBox()
        self.convert_start_addr_spin.setRange(1, 49999)
        self.convert_start_addr_spin.setValue(40001)
        grid.addWidget(self.convert_start_addr_spin, 1, 1)
        
        # End address
        grid.addWidget(QLabel("End Address:"), 2, 0)
        self.convert_end_addr_spin = QSpinBox()
        self.convert_end_addr_spin.setRange(1, 49999)
        self.convert_end_addr_spin.setValue(40010)
        grid.addWidget(self.convert_end_addr_spin, 2, 1)
        
        # New type
        grid.addWidget(QLabel("New Type:"), 3, 0)
        self.convert_new_type_combo = QComboBox()
        self._populate_combo(self.convert_new_type_combo)
        grid.addWidget(self.convert_new_type_combo, 3, 1)
        
        # New start
        grid.addWidget(QLabel("New Start Address:"), 4, 0)
        self.convert_new_start_spin = QSpinBox()
        self.convert_new_start_spin.setRange(1, 49999)
        self.convert_new_start_spin.setValue(30001)
        grid.addWidget(self.convert_new_start_spin, 4, 1)
        
        # Apply button
        self.convert_apply_btn = QPushButton("Apply Conversion")
        grid.addWidget(self.convert_apply_btn, 5, 1)
        
        layout.addWidget(group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Type Conversion")
    
    def _create_pattern_tab(self):
        """Create pattern fill tab."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        group = QGroupBox("Pattern Fill Settings")
        grid = QGridLayout(group)
        
        # Register type
        grid.addWidget(QLabel("Register Type:"), 0, 0)
        self.pattern_reg_type_combo = QComboBox()
        self._populate_combo(self.pattern_reg_type_combo)
        grid.addWidget(self.pattern_reg_type_combo, 0, 1)
        
        # Start address
        grid.addWidget(QLabel("Start Address:"), 1, 0)
        self.pattern_start_addr_spin = QSpinBox()
        self.pattern_start_addr_spin.setRange(1, 49999)
        self.pattern_start_addr_spin.setValue(40001)
        grid.addWidget(self.pattern_start_addr_spin, 1, 1)
        
        # End address
        grid.addWidget(QLabel("End Address:"), 2, 0)
        self.pattern_end_addr_spin = QSpinBox()
        self.pattern_end_addr_spin.setRange(1, 49999)
        self.pattern_end_addr_spin.setValue(40010)
        grid.addWidget(self.pattern_end_addr_spin, 2, 1)
        
        # Pattern values
        grid.addWidget(QLabel("Pattern Values:"), 3, 0)
        self.pattern_values_edit = QLineEdit()
        self.pattern_values_edit.setPlaceholderText("e.g., 100,200,300")
        grid.addWidget(self.pattern_values_edit, 3, 1)
        
        # Apply button
        self.pattern_apply_btn = QPushButton("Apply Pattern")
        grid.addWidget(self.pattern_apply_btn, 4, 1)
        
        layout.addWidget(group)
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Pattern Fill")
    
    def _populate_combo(self, combo: QComboBox):
        """Populate a combo box with register types."""
        combo.clear()
        for info in MODBUS_REGISTER_TYPES.values():
            combo.addItem(f"{info['description']}", info['code'])
        print(f"Populated combo with {combo.count()} items")
    
    def _connect_handler(self):
        """Connect all UI widgets to the bulk operations handler."""
        widget_dict = {
            # Main widgets
            'tab_widget': self.tab_widget,
            'progress_bar': self.progress_bar,
            'status_label': self.status_label,
            'cancel_btn': self.cancel_btn,
            'close_btn': self.close_btn,
            'validate_ranges_cb': self.validate_ranges_cb,
            'confirm_operations_cb': self.confirm_operations_cb,
            
            # Tab 1: Batch Value Setting
            'batch_reg_type_combo': self.batch_reg_type_combo,
            'batch_start_addr_spin': self.batch_start_addr_spin,
            'batch_end_addr_spin': self.batch_end_addr_spin,
            'batch_new_value_spin': self.batch_new_value_spin,
            'batch_apply_btn': self.batch_apply_btn,
            
            # Tab 2: Address Renumbering
            'renumber_reg_type_combo': self.renumber_reg_type_combo,
            'renumber_current_start_spin': self.renumber_current_start_spin,
            'renumber_current_end_spin': self.renumber_current_end_spin,
            'renumber_new_start_spin': self.renumber_new_start_spin,
            'renumber_apply_btn': self.renumber_apply_btn,
            
            # Tab 3: Type Conversion
            'convert_old_type_combo': self.convert_old_type_combo,
            'convert_start_addr_spin': self.convert_start_addr_spin,
            'convert_end_addr_spin': self.convert_end_addr_spin,
            'convert_new_type_combo': self.convert_new_type_combo,
            'convert_new_start_spin': self.convert_new_start_spin,
            'convert_apply_btn': self.convert_apply_btn,
            
            # Tab 4: Pattern Fill
            'pattern_reg_type_combo': self.pattern_reg_type_combo,
            'pattern_start_addr_spin': self.pattern_start_addr_spin,
            'pattern_end_addr_spin': self.pattern_end_addr_spin,
            'pattern_values_edit': self.pattern_values_edit,
            'pattern_apply_btn': self.pattern_apply_btn
        }
        
        # All widgets should be available since we created them manually
        print(f"Connecting {len(widget_dict)} widgets to handler")
        self.bulk_handler.connect_widgets(widget_dict)
    
    def set_register_map(self, register_map: RegisterMap):
        """Set the register map for bulk operations."""
        self.bulk_handler.set_register_map(register_map)
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Use the handler's close method to check for running operations
        self.bulk_handler.close_dialog()
        event.accept()


# Example usage function
def show_manual_bulk_operations_dialog(register_map: RegisterMap = None, parent=None):
    """Show the manual bulk operations dialog."""
    dialog = ManualBulkOperationsDialog(register_map, parent)
    return dialog.exec_()