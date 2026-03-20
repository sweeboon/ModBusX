from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox, 
    QSpinBox, QLineEdit, QTextEdit, QPushButton, QGroupBox, QMessageBox,
    QCheckBox, QTabWidget, QWidget, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, pyqtSignal
from modbusx.services.register_validator import MODBUS_REGISTER_TYPES, RegisterValidator
from modbusx.services.register_validator import ValidationError
from modbusx.models.register_map import RegisterMap
from modbusx.ui.widgets import AddressInputWidget
from typing import Dict, List, Tuple, Optional

class RegisterGroupTemplates:
    """Predefined register group templates for common ModBus applications."""
    
    TEMPLATES = {
        "Basic I/O": {
            "description": "Mixed coils and discrete inputs for basic I/O control",
            "groups": [
                {"type": "co", "start": 1, "size": 16, "value": 0, "name": "Digital Outputs"},
                {"type": "di", "start": 1, "size": 16, "value": 0, "name": "Digital Inputs"}
            ]
        },
        "Analog Sensors": {
            "description": "Input registers for analog sensor readings",
            "groups": [
                {"type": "ir", "start": 1, "size": 10, "value": 0, "name": "Sensor Readings"}
            ]
        },
        "Control Registers": {
            "description": "Holding registers for setpoints and commands",
            "groups": [
                {"type": "hr", "start": 1, "size": 20, "value": 0, "name": "Control Parameters"}
            ]
        },
        "Process Control": {
            "description": "Complete process control setup with all register types",
            "groups": [
                {"type": "co", "start": 1, "size": 8, "value": 0, "name": "Output Controls"},
                {"type": "di", "start": 1, "size": 8, "value": 0, "name": "Status Inputs"},
                {"type": "ir", "start": 1, "size": 16, "value": 0, "name": "Process Variables"},
                {"type": "hr", "start": 1, "size": 16, "value": 100, "name": "Setpoints"}
            ]
        },
        "Custom Range": {
            "description": "User-defined register type and address range",
            "groups": []
        }
    }

class RegisterGroupDialog(QDialog):
    """Enhanced dialog for creating register groups with templates and customization."""
    
    group_created = pyqtSignal(dict)  # Emits group configuration
    
    def __init__(self, register_map: RegisterMap = None, parent=None):
        super().__init__(parent)
        self.register_map = register_map
        self.setWindowTitle(self.tr("Create Register Group"))
        self.setModal(True)
        self.resize(500, 400)
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        
        # Tab widget for templates vs custom
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Template tab
        self._setup_template_tab()
        
        # Custom tab
        self._setup_custom_tab()
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_create = QPushButton(self.tr("Create Group(s)"))
        self.btn_cancel = QPushButton(self.tr("Cancel"))
        button_layout.addStretch()
        button_layout.addWidget(self.btn_create)
        button_layout.addWidget(self.btn_cancel)
        layout.addLayout(button_layout)
    
    def _setup_template_tab(self):
        """Setup the template selection tab."""
        template_widget = QWidget()
        layout = QVBoxLayout(template_widget)
        
        # Template selection
        template_group = QGroupBox(self.tr("Select Template"))
        template_layout = QVBoxLayout(template_group)
        
        self.template_combo = QComboBox()
        for name, template in RegisterGroupTemplates.TEMPLATES.items():
            self.template_combo.addItem(self.tr(name), name)
        template_layout.addWidget(self.template_combo)
        
        # Description
        self.template_description = QLabel()
        self.template_description.setWordWrap(True)
        self.template_description.setStyleSheet("QLabel { background-color: #f0f0f0; padding: 8px; border-radius: 4px; }")
        template_layout.addWidget(self.template_description)
        
        layout.addWidget(template_group)
        
        # Preview list
        preview_group = QGroupBox(self.tr("Template Preview"))
        preview_layout = QVBoxLayout(preview_group)
        
        self.template_preview = QListWidget()
        preview_layout.addWidget(self.template_preview)
        
        layout.addWidget(preview_group)
        
        self.tab_widget.addTab(template_widget, self.tr("Templates"))
        
        # Update description when selection changes
        self.template_combo.currentIndexChanged.connect(lambda *_: self._update_template_preview())
        self._update_template_preview()
    
    def _setup_custom_tab(self):
        """Setup the custom register group tab."""
        custom_widget = QWidget()
        layout = QVBoxLayout(custom_widget)
        
        # Basic settings
        basic_group = QGroupBox(self.tr("Basic Settings"))
        basic_layout = QGridLayout(basic_group)
        
        basic_layout.addWidget(QLabel(self.tr("Addressing Mode:")), 0, 0)
        self.address_mode_combo = QComboBox()
        self.address_mode_combo.addItem(self.tr("PLC Addressing (0-based)"), 'plc')
        self.address_mode_combo.addItem(self.tr("Protocol Addressing (Modbus standard)"), 'protocol')
        current_mode = RegisterValidator.get_address_mode()
        mode_index = 0 if current_mode == 'plc' else 1
        self.address_mode_combo.setCurrentIndex(mode_index)
        basic_layout.addWidget(self.address_mode_combo, 0, 1)
        
        basic_layout.addWidget(QLabel(self.tr("Register Type:")), 1, 0)
        self.reg_type_combo = QComboBox()
        for reg_type, info in MODBUS_REGISTER_TYPES.items():
            description = info.get('description', '')
            self.reg_type_combo.addItem(self.tr(description), reg_type.lower())
        # Set HR (Holding Registers) as default since it's most commonly used
        hr_index = self.reg_type_combo.findData('hr')
        if hr_index >= 0:
            self.reg_type_combo.setCurrentIndex(hr_index)
        basic_layout.addWidget(self.reg_type_combo, 1, 1)
        
        basic_layout.addWidget(QLabel(self.tr("Start Address:")), 2, 0)
        # Use custom address input widget
        self.start_addr_input = AddressInputWidget()
        # Initialize with default register type (HR) to ensure proper default address
        initial_reg_type = self.reg_type_combo.currentData() or 'hr'
        self.start_addr_input.set_register_type(initial_reg_type)
        basic_layout.addWidget(self.start_addr_input, 2, 1)

        # Add a faint hint label to show alternate representation (hex/decimal)
        self.start_addr_hint = QLabel("")
        self.start_addr_hint.setStyleSheet("color: #888888; font-style: italic;")
        basic_layout.addWidget(self.start_addr_hint, 2, 2)
        
        basic_layout.addWidget(QLabel(self.tr("Size:")), 3, 0)
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 65535)  # Will be updated dynamically based on address range
        self.size_spin.setValue(10)
        basic_layout.addWidget(self.size_spin, 3, 1)
        
        basic_layout.addWidget(QLabel(self.tr("Default Value:")), 4, 0)
        self.default_value_spin = QSpinBox()
        self.default_value_spin.setRange(0, 65535)
        self.default_value_spin.setValue(0)
        basic_layout.addWidget(self.default_value_spin, 4, 1)
        
        layout.addWidget(basic_group)
        
        # Metadata settings
        metadata_group = QGroupBox(self.tr("Metadata"))
        metadata_layout = QGridLayout(metadata_group)
        
        metadata_layout.addWidget(QLabel(self.tr("Group Name:")), 0, 0)
        self.group_name_edit = QLineEdit()
        self.group_name_edit.setPlaceholderText(self.tr("e.g., Process Variables"))
        metadata_layout.addWidget(self.group_name_edit, 0, 1)
        
        metadata_layout.addWidget(QLabel(self.tr("Alias Prefix:")), 1, 0)
        self.alias_prefix_edit = QLineEdit()
        self.alias_prefix_edit.setPlaceholderText(self.tr("e.g., PV_"))
        metadata_layout.addWidget(self.alias_prefix_edit, 1, 1)
        
        metadata_layout.addWidget(QLabel(self.tr("Description:")), 2, 0)
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(60)
        self.description_edit.setPlaceholderText(self.tr("Optional description for this register group"))
        metadata_layout.addWidget(self.description_edit, 2, 1)
        
        layout.addWidget(metadata_group)
        
        # Validation options
        validation_group = QGroupBox(self.tr("Validation"))
        validation_layout = QVBoxLayout(validation_group)
        
        self.validate_addresses_cb = QCheckBox(self.tr("Validate address conflicts"))
        self.validate_addresses_cb.setChecked(True)
        validation_layout.addWidget(self.validate_addresses_cb)
        
        self.auto_adjust_cb = QCheckBox(self.tr("Auto-adjust conflicting addresses"))
        self.auto_adjust_cb.setChecked(True)
        validation_layout.addWidget(self.auto_adjust_cb)
        
        # Status label for warnings
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        validation_layout.addWidget(self.status_label)
        
        layout.addWidget(validation_group)
        
        self.tab_widget.addTab(custom_widget, self.tr("Custom"))
        
        # Update address range when register type or addressing mode changes
        self.address_mode_combo.currentIndexChanged.connect(lambda *_: self._on_address_mode_changed())
        self.reg_type_combo.currentIndexChanged.connect(lambda *_: self._update_address_range())
        self.start_addr_input.addressChanged.connect(self._update_size_limits)
        # Keep the hint in sync with edits/type/mode changes
        self.start_addr_input.addressChanged.connect(self._update_start_addr_hint)
        self.reg_type_combo.currentIndexChanged.connect(lambda *_: self._update_start_addr_hint())
        self.size_spin.valueChanged.connect(self._update_size_limits)
        self._update_address_range()
        self._update_start_addr_hint()
    
    def _connect_signals(self):
        """Connect UI signals."""
        self.btn_create.clicked.connect(self._create_group)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _update_template_preview(self):
        """Update the template preview list."""
        template_key = self.template_combo.currentData()
        template = RegisterGroupTemplates.TEMPLATES.get(template_key, {})
        
        # Update description
        description = template.get("description", "")
        self.template_description.setText(self.tr(description) if description else "")
        
        # Update preview list
        self.template_preview.clear()
        groups = template.get("groups", [])
        
        if not groups:  # Custom Range
            self.template_preview.addItem(self.tr("Configure custom register group in the Custom tab"))
        else:
            for group in groups:
                reg_type = group["type"].upper()
                type_name = MODBUS_REGISTER_TYPES[reg_type]["name"]
                type_name = self.tr(type_name)
                start_display = RegisterValidator.address_to_display(group['start'], group["type"])
                end_display = RegisterValidator.address_to_display(group['start'] + group['size'] - 1, group["type"])
                item_text = self.tr("{} ({}): {} - {} [{} registers]").format(
                    reg_type, type_name, start_display, end_display, group['size']
                )
                if group.get("name"):
                    item_text = f"{self.tr(group['name'])} - {item_text}"
                self.template_preview.addItem(item_text)
    
    def _on_address_mode_changed(self):
        """Handle address mode change."""
        new_mode = self.address_mode_combo.currentData()
        if new_mode:
            RegisterValidator.set_address_mode(new_mode)
            # Update the address input with the new mode and ensure proper default
            self.start_addr_input.update_mode()
            # Also trigger register type update to set proper default address
            current_reg_type = self.reg_type_combo.currentData()
            if current_reg_type:
                self.start_addr_input.set_register_type(current_reg_type)
            self._update_template_preview()  # Refresh template preview with new mode
            # Update hint label for new mode
            self._update_start_addr_hint()
    
    def _update_address_range(self):
        """Update address display when register type changes."""
        reg_type = self.reg_type_combo.currentData()
        
        if reg_type:
            # Update the address input widget with new register type
            self.start_addr_input.set_register_type(reg_type)
            
            # Update value range based on register type
            if reg_type in ('co', 'di'):
                self.default_value_spin.setRange(0, 1)
                self.default_value_spin.setValue(0)
            else:
                self.default_value_spin.setRange(0, 65535)
                self.default_value_spin.setValue(0)
            
            # Update size limits
            self._update_size_limits()
            # Update hint
            self._update_start_addr_hint()

    def _update_start_addr_hint(self):
        """Update the faint hint label to show alternate protocol representation."""
        try:
            mode = RegisterValidator.get_address_mode()
            reg_type = self.reg_type_combo.currentData() or 'hr'
            text = self.start_addr_input.text().strip()
            if not text:
                self.start_addr_hint.setText("")
                return
            if mode == 'protocol':
                # Compute internal then display both forms
                try:
                    internal = RegisterValidator.display_to_address(text, reg_type, mode='protocol')
                    # Protocol decimal is (internal - 1)
                    dec_val = max(0, internal - 1)
                    hex_disp = RegisterValidator.address_to_display(internal, reg_type, mode='protocol')
                    if text.lower().startswith('0x'):
                        # show decimal as hint
                        self.start_addr_hint.setText(f"= {dec_val}")
                    else:
                        # show hex as hint
                        self.start_addr_hint.setText(f"= {hex_disp}")
                except Exception:
                    self.start_addr_hint.setText("")
            else:
                # In PLC mode, no hint for now
                self.start_addr_hint.setText("")
        except Exception:
            self.start_addr_hint.setText("")
    
    def _update_size_limits(self):
        """Update size limits based on current address and register type."""
        try:
            reg_type = self.reg_type_combo.currentData()
            if not reg_type:
                return
                
            # Get current start address
            start_addr = self.start_addr_input.get_address_value()
            
            # Always allow full size range - validation happens at creation time
            self.size_spin.setRange(1, 65535)
            
            # Show a warning if current values would exceed address range
            addr_range = RegisterValidator.get_address_range(reg_type)
            max_addr = addr_range[1]
            # Get the actual current size from the spinbox (real-time value)
            actual_current_size = self.size_spin.value()
            end_addr = start_addr + actual_current_size - 1
            
            if end_addr > max_addr:
                # Update status but don't restrict the spinner
                max_possible_size = max_addr - start_addr + 1
                # Get display format for addresses in the warning
                start_display = RegisterValidator.address_to_display(start_addr, reg_type)
                max_display = RegisterValidator.address_to_display(max_addr, reg_type)
                
                self.status_label.setText(
                    self.tr("⚠ Warning: Size {} with start address {} exceeds max address {}. Max possible size: {}").format(
                        actual_current_size, start_display, max_display, max_possible_size
                    )
                )
                self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.status_label.setText("")
                self.status_label.setStyleSheet("")
                
        except (ValueError, ValidationError):
            # If address is invalid, use default limits
            self.size_spin.setRange(1, 65535)
            self.status_label.setText(self.tr("⚠ Invalid address - please enter a valid start address"))
            self.status_label.setStyleSheet("color: red;")
    
    def _create_group(self):
        """Create the register group(s) based on current settings."""
        if self.tab_widget.currentIndex() == 0:  # Template tab
            self._create_from_template()
        else:  # Custom tab
            self._create_custom_group()
    
    def _create_from_template(self):
        """Create register groups from selected template."""
        template_name = self.template_combo.currentData()
        template = RegisterGroupTemplates.TEMPLATES.get(template_name)
        
        if not template:
            return
            
        if template_name == "Custom Range":
            # Switch to custom tab
            self.tab_widget.setCurrentIndex(1)
            QMessageBox.information(self, self.tr("Template Selection"), 
                self.tr("Please configure your custom register group in the Custom tab."))
            return
        
        groups = template.get("groups", [])
        if not groups:
            return
        
        # Initialize adjusted groups tracker
        self._adjusted_template_groups = None
        
        # Validate addresses if requested
        if self.register_map:
            conflicts = self._check_template_conflicts(groups)
            if conflicts and not self._handle_conflicts(conflicts):
                return
        
        # Use adjusted groups if auto-adjustment was performed, otherwise use original
        groups_to_create = self._adjusted_template_groups if self._adjusted_template_groups else groups
        
        # Create all groups from template
        for group_config in groups_to_create:
            group_data = {
                "reg_type": group_config["type"],
                "start_addr": group_config["start"],
                "size": group_config["size"],
                "default_value": group_config.get("value", 0),
                "group_name": self.tr(group_config.get("name", "")) if group_config.get("name") else "",
                "alias_prefix": "",
                "description": self.tr(template.get("description", "")) if template.get("description") else "",
                "template_name": template_name,
                "auto_adjusted": getattr(self, '_auto_adjustment_performed', False)
            }
            self.group_created.emit(group_data)
        
        self.accept()
    
    def _create_custom_group(self):
        """Create a custom register group."""
        reg_type = self.reg_type_combo.currentData()
        size = self.size_spin.value()
        default_value = self.default_value_spin.value()
        
        # Get and validate address - prioritize adjusted address if auto-adjustment was performed
        if hasattr(self, '_adjusted_start_address') and getattr(self, '_auto_adjustment_performed', False):
            # Use the stored adjusted address from auto-adjustment
            start_addr = self._adjusted_start_address
            try:
                RegisterValidator.validate_address_for_register_type(start_addr, reg_type)
            except (ValidationError, ValueError) as e:
                QMessageBox.warning(self, self.tr("Invalid Adjusted Address"), str(e))
                return
        else:
            # Use address from widget input
            try:
                start_addr = self.start_addr_input.get_address_value()
                RegisterValidator.validate_address_for_register_type(start_addr, reg_type)
            except (ValidationError, ValueError) as e:
                QMessageBox.warning(self, self.tr("Invalid Address"), str(e))
                return
        
        # Check for conflicts if validation enabled
        # Skip validation if we just performed auto-adjustment (addresses should be valid)
        skip_validation = getattr(self, '_auto_adjustment_performed', False)
        
        if self.validate_addresses_cb.isChecked() and self.register_map and not skip_validation:
            conflicts = self._check_address_conflicts(reg_type, start_addr, size)
            if conflicts:
                if not self._handle_conflicts(conflicts):
                    return
                # After handling conflicts, check if auto-adjustment was performed
                if getattr(self, '_auto_adjustment_performed', False) and hasattr(self, '_adjusted_start_address'):
                    start_addr = self._adjusted_start_address
        
        # Validate value range
        if RegisterValidator.validate_register_value_with_conversion(str(default_value), reg_type, self) is None:
            return
        
        # Get the auto-adjustment flag BEFORE resetting it
        auto_adjusted_flag = getattr(self, '_auto_adjustment_performed', False)
        
        group_data = {
            "reg_type": reg_type,
            "start_addr": start_addr,
            "size": size,
            "default_value": default_value,
            "group_name": self.group_name_edit.text().strip(),
            "alias_prefix": self.alias_prefix_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
            "auto_adjusted": auto_adjusted_flag
        }
        
        # Reset the auto-adjustment flag and stored address AFTER using them
        self._auto_adjustment_performed = False
        if hasattr(self, '_adjusted_start_address'):
            delattr(self, '_adjusted_start_address')
        
        self.group_created.emit(group_data)
        self.accept()
    
    def _check_template_conflicts(self, groups: List[Dict]) -> List[Tuple[str, int, int]]:
        """Check for address conflicts in template groups."""
        conflicts = []
        for group in groups:
            reg_type = group["type"]
            start_addr = group["start"]
            size = group["size"]
            conflicts.extend(self._check_address_conflicts(reg_type, start_addr, size))
        return conflicts
    
    def _check_address_conflicts(self, reg_type: str, start_addr: int, size: int) -> List[Tuple[str, int, int]]:
        """Check for address conflicts in the register map."""
        conflicts = []
        if not self.register_map:
            return conflicts
            
        reg_dict = getattr(self.register_map, reg_type)
        for addr in range(start_addr, start_addr + size):
            if addr in reg_dict:
                conflicts.append((reg_type, addr, start_addr))
        
        return conflicts
    
    def _handle_conflicts(self, conflicts: List[Tuple[str, int, int]]) -> bool:
        """Handle address conflicts. Returns True if user wants to continue."""
        if not conflicts:
            return True
            
        conflict_text = "\n".join([f"{reg_type.upper()}: {addr}" for reg_type, addr, _ in conflicts])
        
        if self.auto_adjust_cb.isChecked():
            reply = QMessageBox.question(
                self,
                self.tr("Address Conflicts"),
                self.tr("The following addresses already exist:\n{}\n\nAuto-adjust to find available addresses?").format(conflict_text),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Yes:
                return self._perform_auto_adjustment()
            elif reply == QMessageBox.No:
                return True  # Continue anyway (will overwrite)
            else:
                return False  # Cancel
        else:
            reply = QMessageBox.warning(
                self,
                self.tr("Address Conflicts"),
                self.tr("The following addresses already exist:\n{}\n\nContinue anyway? (Existing registers will be overwritten)").format(conflict_text),
                QMessageBox.Yes | QMessageBox.Cancel
            )
            
            return reply == QMessageBox.Yes
    
    def _perform_auto_adjustment(self) -> bool:
        """Perform auto-adjustment of addresses to avoid conflicts."""
        try:
            if self.tab_widget.currentIndex() == 0:  # Template tab
                return self._auto_adjust_template()
            else:  # Custom tab
                return self._auto_adjust_custom()
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Auto-Adjustment Failed"),
                self.tr("Could not find suitable addresses:\n{}").format(str(e))
            )
            return False
    
    def _auto_adjust_custom(self) -> bool:
        """Auto-adjust the custom register group addresses."""
        reg_type = self.reg_type_combo.currentData()
        size = self.size_spin.value()
        
        try:
            current_start = self.start_addr_input.get_address_value()
        except (ValidationError, ValueError):
            # If current address is invalid, use suggested address
            try:
                adjusted_start = RegisterValidator.suggest_contiguous_address_for_register_type(
                    reg_type, self.register_map, size)
            except ValidationError as e:
                QMessageBox.critical(self, self.tr("Auto-Adjustment Failed"), str(e))
                return False
        else:
            # Try to find adjusted address close to current start
            try:
                adjusted_start = RegisterValidator.suggest_adjusted_address_for_group(
                    reg_type, self.register_map, current_start, size)
            except ValidationError as e:
                QMessageBox.critical(self, self.tr("Auto-Adjustment Failed"), str(e))
                return False
        
        # Update the address input with the adjusted address
        self.start_addr_input.set_address_value(adjusted_start)
        
        # Verify the widget was updated correctly
        try:
            widget_addr = self.start_addr_input.get_address_value()
            if widget_addr != adjusted_start:
                # Force update if there's a mismatch
                self.start_addr_input.setText(RegisterValidator.address_to_display(adjusted_start, reg_type))
        except Exception:
            # Silently continue if widget verification fails - we have the stored address as backup
            pass
        
        # Show confirmation message
        start_display = RegisterValidator.address_to_display(adjusted_start, reg_type)
        end_display = RegisterValidator.address_to_display(adjusted_start + size - 1, reg_type)
        
        QMessageBox.information(
            self,
            self.tr("Auto-Adjustment Complete"),
            self.tr("Adjusted to available address range:\n{} - {} ({} registers)").format(
                start_display, end_display, size
            )
        )
        
        # Set flag to skip validation on group creation and store adjusted address
        self._auto_adjustment_performed = True
        self._adjusted_start_address = adjusted_start
        
        return True
    
    def _auto_adjust_template(self) -> bool:
        """Auto-adjust template register group addresses."""
        template_name = self.template_combo.currentData()
        template = RegisterGroupTemplates.TEMPLATES.get(template_name)
        
        if not template or not template.get("groups"):
            return False
        
        adjusted_groups = []
        adjustment_messages = []
        
        for group_config in template["groups"]:
            reg_type = group_config["type"]
            original_start = group_config["start"]
            size = group_config["size"]
            
            try:
                adjusted_start = RegisterValidator.suggest_adjusted_address_for_group(
                    reg_type, self.register_map, original_start, size)
                
                if adjusted_start != original_start:
                    start_display = RegisterValidator.address_to_display(adjusted_start, reg_type)
                    end_display = RegisterValidator.address_to_display(adjusted_start + size - 1, reg_type)
                    base_name = group_config.get("name") or f"{reg_type.upper()} Group"
                    group_name = self.tr(base_name)
                    adjustment_messages.append(
                        self.tr("{}: {} - {}").format(group_name, start_display, end_display))
                
                # Create adjusted group config
                adjusted_group = group_config.copy()
                adjusted_group["start"] = adjusted_start
                adjusted_groups.append(adjusted_group)
                
            except ValidationError as e:
                base_name = group_config.get('name') or reg_type.upper()
                QMessageBox.critical(
                    self,
                    self.tr("Auto-Adjustment Failed"),
                    self.tr("Failed to adjust {}:\n{}").format(self.tr(base_name), str(e))
                )
                return False
        
        # Update the template groups with adjusted addresses
        self._adjusted_template_groups = adjusted_groups
        
        if adjustment_messages:
            QMessageBox.information(
                self,
                self.tr("Auto-Adjustment Complete"),
                self.tr("Adjusted the following groups to available addresses:\n\n{}").format("\n".join(adjustment_messages))
            )
        
        # Set flag to skip validation on group creation
        self._auto_adjustment_performed = True
        
        return True
