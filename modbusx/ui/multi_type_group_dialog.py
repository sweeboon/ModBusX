from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QSpinBox, QLineEdit, QTextEdit, QPushButton, QGroupBox, QMessageBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from modbusx.models.register_map import RegisterMap
from modbusx.models.register_entry import RegisterEntry
from modbusx.models.multi_type_group import MultiTypeRegisterGroup, RegisterBlock
from modbusx.services.register_validator import MODBUS_REGISTER_TYPES, RegisterValidator
from modbusx.services.register_validator import ValidationError
from typing import Dict, List, Tuple, Optional
import time


class MultiTypeGroupDialog(QDialog):
    """Dialog for creating multi-type register groups."""
    
    group_created = pyqtSignal(object)  # Emits MultiTypeRegisterGroup
    
    def __init__(self, register_map: RegisterMap = None, parent=None):
        super().__init__(parent)
        self.register_map = register_map
        self.current_group = None
        
        self.setWindowTitle("Create Multi-Type Register Group")
        self.setModal(True)
        self.resize(600, 500)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Group metadata
        metadata_group = QGroupBox("Group Information")
        metadata_layout = QGridLayout(metadata_group)
        
        metadata_layout.addWidget(QLabel("Group Name:"), 0, 0)
        self.group_name_edit = QLineEdit()
        self.group_name_edit.setPlaceholderText("e.g., Process Control Group")
        metadata_layout.addWidget(self.group_name_edit, 0, 1)
        
        metadata_layout.addWidget(QLabel("Description:"), 1, 0)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText("Optional description for this multi-type group")
        metadata_layout.addWidget(self.description_edit, 1, 1)
        
        layout.addWidget(metadata_group)
        
        # Register blocks table
        blocks_group = QGroupBox("Register Blocks")
        blocks_layout = QVBoxLayout(blocks_group)
        
        self.blocks_table = QTableWidget()
        self.blocks_table.setColumnCount(5)
        self.blocks_table.setHorizontalHeaderLabels([
            "Register Type", "Start Address", "Size", "Default Value", "Description"
        ])
        self.blocks_table.horizontalHeader().setStretchLastSection(True)
        blocks_layout.addWidget(self.blocks_table)
        
        # Block controls
        block_controls = QHBoxLayout()
        self.add_block_btn = QPushButton("Add Block")
        self.remove_block_btn = QPushButton("Remove Block")
        self.remove_block_btn.setEnabled(False)
        block_controls.addWidget(self.add_block_btn)
        block_controls.addWidget(self.remove_block_btn)
        block_controls.addStretch()
        blocks_layout.addLayout(block_controls)
        
        layout.addWidget(blocks_group)
        
        # Validation options
        validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout(validation_group)
        
        self.validate_addresses_cb = QCheckBox("Validate address conflicts")
        self.validate_addresses_cb.setChecked(True)
        validation_layout.addWidget(self.validate_addresses_cb)
        
        self.auto_adjust_cb = QCheckBox("Auto-adjust conflicting addresses")
        self.auto_adjust_cb.setChecked(True)
        validation_layout.addWidget(self.auto_adjust_cb)
        
        layout.addWidget(validation_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_create = QPushButton("Create Group")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_create)
        layout.addLayout(button_layout)
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.add_block_btn.clicked.connect(self._add_register_block)
        self.remove_block_btn.clicked.connect(self._remove_register_block)
        self.blocks_table.itemSelectionChanged.connect(self._update_remove_button)
        self.btn_create.clicked.connect(self._create_group)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _add_register_block(self):
        """Add a new register block to the table."""
        dialog = RegisterBlockDialog(self.register_map, self)
        if dialog.exec_() == QDialog.Accepted:
            block_data = dialog.get_block_data()
            self._add_block_to_table(block_data)
    
    def _add_block_to_table(self, block_data: Dict):
        """Add a register block to the table widget."""
        row = self.blocks_table.rowCount()
        self.blocks_table.insertRow(row)
        
        reg_type = block_data['reg_type'].upper()
        type_name = MODBUS_REGISTER_TYPES[reg_type]['name']
        
        # Register Type
        type_item = QTableWidgetItem(f"{reg_type} - {type_name}")
        type_item.setData(Qt.UserRole, block_data['reg_type'])
        type_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.blocks_table.setItem(row, 0, type_item)
        
        # Start Address
        addr_item = QTableWidgetItem(str(block_data['start_addr']))
        addr_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.blocks_table.setItem(row, 1, addr_item)
        
        # Size
        size_item = QTableWidgetItem(str(block_data['size']))
        size_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.blocks_table.setItem(row, 2, size_item)
        
        # Default Value
        value_item = QTableWidgetItem(str(block_data['default_value']))
        value_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.blocks_table.setItem(row, 3, value_item)
        
        # Description
        desc_item = QTableWidgetItem(block_data.get('block_description', ''))
        self.blocks_table.setItem(row, 4, desc_item)
        
        # Store full block data
        self.blocks_table.item(row, 0).setData(Qt.UserRole + 1, block_data)
        
        self._update_remove_button()
    
    def _remove_register_block(self):
        """Remove selected register block from the table."""
        current_row = self.blocks_table.currentRow()
        if current_row >= 0:
            self.blocks_table.removeRow(current_row)
            self._update_remove_button()
    
    def _update_remove_button(self):
        """Update the remove button enabled state."""
        self.remove_block_btn.setEnabled(self.blocks_table.rowCount() > 0 and 
                                        self.blocks_table.currentRow() >= 0)
    
    def _create_group(self):
        """Create the multi-type register group."""
        group_name = self.group_name_edit.text().strip()
        if not group_name:
            QMessageBox.warning(self, "Validation Error", "Please enter a group name")
            return
        
        if self.blocks_table.rowCount() == 0:
            QMessageBox.warning(self, "Validation Error", "Please add at least one register block")
            return
        
        # Create the multi-type group
        group = MultiTypeRegisterGroup(
            group_id=self._get_next_group_id(),
            name=group_name,
            description=self.description_edit.toPlainText().strip()
        )
        
        # Collect block data and validate
        conflicts = []
        for i in range(self.blocks_table.rowCount()):
            type_item = self.blocks_table.item(i, 0)
            block_data = type_item.data(Qt.UserRole + 1)
            
            # Validate addresses if requested
            if self.validate_addresses_cb.isChecked() and self.register_map:
                block_conflicts = self._check_address_conflicts(
                    block_data['reg_type'], 
                    block_data['start_addr'], 
                    block_data['size']
                )
                conflicts.extend(block_conflicts)
            
            # Create RegisterBlock object for models version
            register_block = RegisterBlock(
                block_id=int(time.time() * 1000000) + i,  # Generate unique ID
                reg_type=block_data['reg_type'],
                start_addr=block_data['start_addr'],
                size=block_data['size'],
                name='',
                description=block_data.get('block_description', ''),
                default_value=block_data['default_value']
            )
            group.add_block(register_block)
        
        # Handle conflicts if any
        if conflicts and not self._handle_conflicts(conflicts):
            return
        
        self.group_created.emit(group)
        self.accept()
    
    def _check_address_conflicts(self, reg_type: str, start_addr: int, size: int) -> List[Tuple[str, int]]:
        """Check for address conflicts in the register map."""
        conflicts = []
        if not self.register_map:
            return conflicts
            
        reg_dict = getattr(self.register_map, reg_type)
        for addr in range(start_addr, start_addr + size):
            if addr in reg_dict:
                conflicts.append((reg_type, addr))
        
        return conflicts
    
    def _handle_conflicts(self, conflicts: List[Tuple[str, int]]) -> bool:
        """Handle address conflicts. Returns True if user wants to continue."""
        if not conflicts:
            return True
            
        conflict_text = "\n".join([f"{reg_type.upper()}: {addr}" for reg_type, addr in conflicts])
        
        if self.auto_adjust_cb.isChecked():
            reply = QMessageBox.question(self, "Address Conflicts",
                f"The following addresses already exist:\n{conflict_text}\n\n"
                "Continue anyway? (Existing registers will be overwritten)",
                QMessageBox.Yes | QMessageBox.Cancel)
        else:
            reply = QMessageBox.warning(self, "Address Conflicts",
                f"The following addresses already exist:\n{conflict_text}\n\n"
                "Continue anyway? (Existing registers will be overwritten)",
                QMessageBox.Yes | QMessageBox.Cancel)
        
        return reply == QMessageBox.Yes
    
    def _get_next_group_id(self) -> int:
        """Get next available group ID."""
        import time
        return int(time.time() * 1000) % 1000000

class RegisterBlockDialog(QDialog):
    """Dialog for adding a single register block to a multi-type group."""
    
    def __init__(self, register_map: RegisterMap = None, parent=None):
        super().__init__(parent)
        self.register_map = register_map
        self.setWindowTitle("Add Register Block")
        self.setModal(True)
        self.resize(400, 250)
        
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Register block settings
        settings_group = QGroupBox("Register Block Settings")
        settings_layout = QGridLayout(settings_group)
        
        settings_layout.addWidget(QLabel("Register Type:"), 0, 0)
        self.reg_type_combo = QComboBox()
        for info in MODBUS_REGISTER_TYPES.values():
            self.reg_type_combo.addItem(f"{info['description']}", info['code'])
        settings_layout.addWidget(self.reg_type_combo, 0, 1)
        
        settings_layout.addWidget(QLabel("Start Address:"), 1, 0)
        self.start_addr_spin = QSpinBox()
        self.start_addr_spin.setRange(1, 49999)
        self.start_addr_spin.setValue(40001)
        settings_layout.addWidget(self.start_addr_spin, 1, 1)
        
        settings_layout.addWidget(QLabel("Size:"), 2, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 1000)
        self.size_spin.setValue(10)
        settings_layout.addWidget(self.size_spin, 2, 1)
        
        settings_layout.addWidget(QLabel("Default Value:"), 3, 0)
        self.default_value_spin = QSpinBox()
        self.default_value_spin.setRange(0, 65535)
        self.default_value_spin.setValue(0)
        settings_layout.addWidget(self.default_value_spin, 3, 1)
        
        settings_layout.addWidget(QLabel("Description:"), 4, 0)
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("Optional description for this block")
        settings_layout.addWidget(self.description_edit, 4, 1)
        
        layout.addWidget(settings_group)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        self.btn_add = QPushButton("Add Block")
        self.btn_cancel = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_add)
        layout.addLayout(button_layout)
        
        # Update address range when register type changes
        self.reg_type_combo.currentTextChanged.connect(self._update_address_range)
        self._update_address_range()
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.btn_add.clicked.connect(self._add_block)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _update_address_range(self):
        """Update start address based on selected register type."""
        reg_type = self.reg_type_combo.currentData()
        if reg_type:
            reg_type_upper = reg_type.upper()
            addr_range = RegisterValidator.get_address_range(reg_type)
            self.start_addr_spin.setRange(addr_range[0], addr_range[1])
            self.start_addr_spin.setValue(addr_range[0])
            
            # Update value range based on register type
            if reg_type in ('co', 'di'):
                self.default_value_spin.setRange(0, 1)
                self.default_value_spin.setValue(0)
            else:
                self.default_value_spin.setRange(0, 65535)
                self.default_value_spin.setValue(0)
    
    def _add_block(self):
        """Validate and add the register block."""
        reg_type = self.reg_type_combo.currentData()
        start_addr = self.start_addr_spin.value()
        size = self.size_spin.value()
        default_value = self.default_value_spin.value()
        
        # Validate address range
        try:
            RegisterValidator.validate_address_for_register_type(start_addr, reg_type)
        except ValidationError as e:
            QMessageBox.warning(self, "Invalid Address", str(e))
            return
        
        # Validate value range
        if RegisterValidator.validate_register_value_with_conversion(str(default_value), reg_type, self) is None:
            return
        
        self.accept()
    
    def get_block_data(self) -> Dict:
        """Get the register block data."""
        return {
            'reg_type': self.reg_type_combo.currentData(),
            'start_addr': self.start_addr_spin.value(),
            'size': self.size_spin.value(),
            'default_value': self.default_value_spin.value(),
            'block_description': self.description_edit.text().strip()
        }