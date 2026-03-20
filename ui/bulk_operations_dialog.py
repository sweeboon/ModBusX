from PyQt5.QtWidgets import QDialog, QWidget
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from modbusx.managers.bulk_operations_manager import BulkOperationsHandler
from modbusx.models import RegisterMap
from typing import Optional
import os

class BulkOperationsDialog(QDialog):
    """Qt Designer-based bulk operations dialog."""
    
    operation_completed = pyqtSignal(bool, str)
    
    def __init__(self, register_map: Optional[RegisterMap] = None, parent=None):
        super().__init__(parent)
        
        self.ui_loaded_successfully = False
        
        try:
            # Load UI file
            ui_path = os.path.join(os.path.dirname(__file__), 'bulk_operations.ui')
            print(f"Loading UI from: {ui_path}")
            
            if not os.path.exists(ui_path):
                print(f"UI file not found: {ui_path}")
                raise FileNotFoundError(f"UI file not found: {ui_path}")
                
            uic.loadUi(ui_path, self)
            print("UI loaded successfully")
            
            # Check if key widgets are available
            key_widgets = ['batch_reg_type_combo', 'renumber_reg_type_combo', 
                          'convert_old_type_combo', 'pattern_reg_type_combo']
            missing = []
            for widget_name in key_widgets:
                if not hasattr(self, widget_name) or getattr(self, widget_name) is None:
                    missing.append(widget_name)
            
            if missing:
                print(f"Key widgets missing: {missing}")
                raise AttributeError(f"Key widgets missing: {missing}")
            
            self.ui_loaded_successfully = True
            print("All key widgets found")
            
        except (FileNotFoundError, AttributeError, Exception) as e:
            print(f"Failed to load UI file: {e}")
            print("Note: Use ManualBulkOperationsDialog as fallback")
            # Don't raise the exception, just mark as failed
            self.ui_loaded_successfully = False
        
        if self.ui_loaded_successfully:
            # Debug: List all child widgets
            print("Available widgets:")
            for child in self.findChildren(QWidget):
                if child.objectName():
                    print(f"  - {child.objectName()} ({type(child).__name__})")
            
            # Initialize bulk operations handler
            self.bulk_handler = BulkOperationsHandler(self)
            self.bulk_handler.operation_completed.connect(self.operation_completed)
            
            # Connect widgets to handler
            self._connect_handler()
            
            # Set register map if provided
            if register_map:
                self.set_register_map(register_map)
        else:
            # If UI loading failed, show error and close
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(parent, "UI Loading Failed", 
                "Failed to load bulk operations dialog.\n\n"
                "Please use the manual dialog instead:\n"
                "from modbusx.ui.bulk_operations_manual import ManualBulkOperationsDialog")
            self.reject()  # Close the dialog
    
    def _connect_handler(self):
        """Connect all UI widgets to the bulk operations handler."""
        widget_dict = {
            # Main widgets
            'tab_widget': getattr(self, 'tab_widget', None),
            'progress_bar': getattr(self, 'progress_bar', None),
            'status_label': getattr(self, 'status_label', None),
            'cancel_btn': getattr(self, 'cancel_btn', None),
            'close_btn': getattr(self, 'close_btn', None),
            'validate_ranges_cb': getattr(self, 'validate_ranges_cb', None),
            'confirm_operations_cb': getattr(self, 'confirm_operations_cb', None),
            
            # Tab 1: Batch Value Setting
            'batch_reg_type_combo': getattr(self, 'batch_reg_type_combo', None),
            'batch_start_addr_spin': getattr(self, 'batch_start_addr_spin', None),
            'batch_end_addr_spin': getattr(self, 'batch_end_addr_spin', None),
            'batch_new_value_spin': getattr(self, 'batch_new_value_spin', None),
            'batch_apply_btn': getattr(self, 'batch_apply_btn', None),
            
            # Tab 2: Address Renumbering
            'renumber_reg_type_combo': getattr(self, 'renumber_reg_type_combo', None),
            'renumber_current_start_spin': getattr(self, 'renumber_current_start_spin', None),
            'renumber_current_end_spin': getattr(self, 'renumber_current_end_spin', None),
            'renumber_new_start_spin': getattr(self, 'renumber_new_start_spin', None),
            'renumber_apply_btn': getattr(self, 'renumber_apply_btn', None),
            
            # Tab 3: Type Conversion
            'convert_old_type_combo': getattr(self, 'convert_old_type_combo', None),
            'convert_start_addr_spin': getattr(self, 'convert_start_addr_spin', None),
            'convert_end_addr_spin': getattr(self, 'convert_end_addr_spin', None),
            'convert_new_type_combo': getattr(self, 'convert_new_type_combo', None),
            'convert_new_start_spin': getattr(self, 'convert_new_start_spin', None),
            'convert_apply_btn': getattr(self, 'convert_apply_btn', None),
            
            # Tab 4: Pattern Fill
            'pattern_reg_type_combo': getattr(self, 'pattern_reg_type_combo', None),
            'pattern_start_addr_spin': getattr(self, 'pattern_start_addr_spin', None),
            'pattern_end_addr_spin': getattr(self, 'pattern_end_addr_spin', None),
            'pattern_values_edit': getattr(self, 'pattern_values_edit', None),
            'pattern_apply_btn': getattr(self, 'pattern_apply_btn', None)
        }
        
        # Filter out None values and connect
        valid_widgets = {name: widget for name, widget in widget_dict.items() if widget is not None}
        self.bulk_handler.connect_widgets(valid_widgets)
    
    def set_register_map(self, register_map: RegisterMap):
        """Set the register map for bulk operations."""
        self.bulk_handler.set_register_map(register_map)
    
    def closeEvent(self, event):
        """Handle dialog close event."""
        # Use the handler's close method to check for running operations
        self.bulk_handler.close_dialog()
        event.accept()