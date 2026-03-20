from PyQt5.QtCore import QTimer, QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import QTableView, QAbstractItemView
from typing import Dict, Optional

class DataRefresher(QObject):
    """Handles real-time data refresh for register values."""
    
    data_updated = pyqtSignal()
    
    def __init__(self, table_model, table_view: QTableView, parent=None):
        super().__init__(parent)
        self.table_model = table_model
        self.table_view = table_view
        self.current_reg_group: Optional[Dict] = None
        
        # Setup refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_current_view)
        self.refresh_timer.start(1000)  # Refresh every second
    
    def set_current_register_group(self, reg_group: Optional[Dict]):
        """Set the current register group to refresh"""
        self.current_reg_group = reg_group
    
    def refresh_current_view(self):
        """Refresh the current table view to show live value changes"""
        if not self.current_reg_group or not hasattr(self.current_reg_group, 'get'):
            return
        # Do not overwrite user edits while the table is in edit mode
        if self.table_view.state() == QAbstractItemView.EditingState:
            return
            
        if not isinstance(self.current_reg_group, dict) or "parent_slave_map" not in self.current_reg_group:
            return
            
        reg_map = self.current_reg_group['parent_slave_map']
        reg_type = self.current_reg_group['reg_type']
        start_addr = self.current_reg_group['start_addr']
        size = self.current_reg_group['size']
        
        entries = [
            e for e in reg_map.all_entries(reg_type)
            if start_addr <= e.addr < start_addr + size
        ]
        
        # Update only the value column (column 3), respecting each row's display type
        for row, entry in enumerate(entries):
            if row >= self.table_model.rowCount():
                continue

            model_index = self.table_model.index(row, 3)
            type_index = self.table_model.index(row, 4)
            # Use canonical display type (UserRole) to avoid locale-dependent parsing
            display_type = self.table_model.data(type_index, Qt.UserRole) or 'Unsigned'

            try:
                v = int(entry.value) & 0xFFFF
            except Exception:
                v = 0
            fmt = display_type.lower()
            if fmt == 'signed':
                disp = str(v - 0x10000 if v >= 0x8000 else v)
            elif fmt == 'hex':
                disp = f"0x{v:04X}"
            elif fmt == 'binary':
                disp = f"0b{v:016b}"
            else:
                disp = str(v)

            if self.table_model.data(model_index, Qt.DisplayRole) != disp:
                self.table_model.setData(model_index, disp, Qt.EditRole)

        self.data_updated.emit()
        # Ensure the view repaints even if no signals were processed
        try:
            self.table_view.viewport().update()
        except Exception:
            pass
    
    def start_refresh(self):
        """Start the refresh timer"""
        if not self.refresh_timer.isActive():
            self.refresh_timer.start(1000)
    
    def stop_refresh(self):
        """Stop the refresh timer"""
        self.refresh_timer.stop()
    
    def set_refresh_interval(self, milliseconds: int):
        """Set the refresh interval in milliseconds"""
        was_active = self.refresh_timer.isActive()
        if was_active:
            self.refresh_timer.stop()
        self.refresh_timer.setInterval(milliseconds)
        if was_active:
            self.refresh_timer.start()
