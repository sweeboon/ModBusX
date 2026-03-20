from PyQt5.QtWidgets import QMessageBox, QInputDialog
from PyQt5.QtCore import QObject, pyqtSignal
from modbusx.models.register_map import RegisterMap
from modbusx.models.register_entry import RegisterEntry
from modbusx.services.register_validator import RegisterValidator, MODBUS_REGISTER_TYPES
from modbusx.services.register_validator import ValidationError
from typing import Dict, List, Optional, Tuple
import copy

class RegisterGroupManager(QObject):
    """Manages advanced register group operations like duplicate, split, merge, export/import."""
    
    group_duplicated = pyqtSignal(dict)  # Emits new group data
    group_split = pyqtSignal(list)  # Emits list of new group data
    group_merged = pyqtSignal(dict)  # Emits merged group data
    group_exported = pyqtSignal(str, dict)  # Emits filename and group data
    group_imported = pyqtSignal(dict)  # Emits imported group data
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def duplicate_group(self, source_group: Dict, register_map: RegisterMap, new_start_addr: Optional[int] = None) -> bool:
        """Duplicate an existing register group with optional new start address."""
        try:
            reg_type = source_group['reg_type']
            old_start = source_group['start_addr']
            size = source_group['size']
            
            # Determine new start address
            if new_start_addr is None:
                new_start_addr = self._find_next_available_address_range(register_map, reg_type, size)
            
            if new_start_addr is None:
                QMessageBox.warning(None, "Duplicate Group", 
                    f"Cannot find available address range for {size} {reg_type.upper()} registers")
                return False
            
            # Validate new address range
            try:
                RegisterValidator.validate_address_for_register_type(new_start_addr, reg_type)
            except ValidationError:
                return False
            
            # Copy register entries
            reg_dict = getattr(register_map, reg_type)
            for i in range(size):
                old_addr = old_start + i
                new_addr = new_start_addr + i
                
                if old_addr in reg_dict:
                    old_entry = reg_dict[old_addr]
                    new_entry = RegisterEntry(
                        addr=new_addr,
                        reg_type=reg_type,
                        value=old_entry.value,
                        alias=f"Copy_{old_entry.alias}" if old_entry.alias else "",
                        comment=old_entry.comment,
                        units=old_entry.units
                    )
                    reg_dict[new_addr] = new_entry
            
            # Create new group metadata
            new_group = copy.deepcopy(source_group)
            new_group.update({
                'start_addr': new_start_addr,
                'register_id': self._get_next_group_id(),
                'parent_slave_map': register_map
            })
            
            # Update group name if it exists
            if 'group_name' in new_group and new_group['group_name']:
                new_group['group_name'] = f"Copy of {new_group['group_name']}"
            
            self.group_duplicated.emit(new_group)
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to duplicate group: {str(e)}")
            return False
    
    def split_group(self, source_group: Dict, split_point: int) -> bool:
        """Split a register group at the specified point."""
        try:
            reg_type = source_group['reg_type']
            start_addr = source_group['start_addr']
            size = source_group['size']
            register_map = source_group.get('parent_slave_map')
            
            if not register_map:
                QMessageBox.critical(None, "Error", "Register map not found")
                return False
            
            if split_point <= 0 or split_point >= size:
                QMessageBox.warning(None, "Split Group", "Invalid split point")
                return False
            
            # Validate that split doesn't break existing register entries
            split_addr = start_addr + split_point
            if register_map.get_register(reg_type, split_addr):
                # Split at this address would break an existing register entry
                QMessageBox.warning(None, "Split Group", 
                    f"Cannot split at address {split_addr} - register entry exists at this address")
                return False
            
            # Create two new groups
            group1_size = split_point
            group2_size = size - split_point
            group2_start = start_addr + split_point
            
            # First group (same start address, reduced size)
            group1 = copy.deepcopy(source_group)
            group1.update({
                'size': group1_size,
                'register_id': self._get_next_group_id()
            })
            if 'group_name' in group1 and group1['group_name']:
                group1['group_name'] = f"{group1['group_name']} - Part 1"
            
            # Second group (new start address)
            group2 = copy.deepcopy(source_group)
            group2.update({
                'start_addr': group2_start,
                'size': group2_size,
                'register_id': self._get_next_group_id()
            })
            if 'group_name' in group2 and group2['group_name']:
                group2['group_name'] = f"{group2['group_name']} - Part 2"
            
            # Validate that new groups have valid address ranges
            try:
                RegisterValidator.validate_address_for_register_type(start_addr, reg_type)
                RegisterValidator.validate_address_for_register_type(start_addr + group1_size - 1, reg_type)
                RegisterValidator.validate_address_for_register_type(group2_start, reg_type)
                RegisterValidator.validate_address_for_register_type(group2_start + group2_size - 1, reg_type)
            except ValidationError as e:
                QMessageBox.critical(None, "Error", f"Invalid address range after split: {str(e)}")
                return False
            
            self.group_split.emit([group1, group2])
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to split group: {str(e)}")
            return False
    
    def merge_groups(self, group1: Dict, group2: Dict) -> bool:
        """Merge two adjacent register groups of the same type."""
        try:
            if group1['reg_type'] != group2['reg_type']:
                QMessageBox.warning(None, "Merge Groups", "Can only merge groups of the same register type")
                return False
            
            if group1['parent_slave_map'] != group2['parent_slave_map']:
                QMessageBox.warning(None, "Merge Groups", "Can only merge groups from the same slave")
                return False
            
            # Ensure group1 comes before group2
            if group1['start_addr'] > group2['start_addr']:
                group1, group2 = group2, group1
            
            end1 = group1['start_addr'] + group1['size']
            start2 = group2['start_addr']
            
            if end1 != start2:
                QMessageBox.warning(None, "Merge Groups", "Groups must be adjacent to merge")
                return False
            
            # Create merged group
            merged_group = copy.deepcopy(group1)
            merged_group.update({
                'size': group1['size'] + group2['size'],
                'register_id': self._get_next_group_id()
            })
            
            # Merge group names
            name1 = group1.get('group_name', '')
            name2 = group2.get('group_name', '')
            if name1 and name2:
                merged_group['group_name'] = f"{name1} + {name2}"
            elif name1 or name2:
                merged_group['group_name'] = name1 or name2
            
            self.group_merged.emit(merged_group)
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to merge groups: {str(e)}")
            return False
    
    def export_group(self, group: Dict, filename: str = None) -> bool:
        """Export register group configuration to a file."""
        try:
            if filename is None:
                filename, _ = QFileDialog.getSaveFileName(
                    None, "Export Register Group", "", "JSON Files (*.json);;All Files (*)"
                )
                if not filename:
                    return False
            
            export_data = {
                'reg_type': group['reg_type'],
                'start_addr': group['start_addr'],
                'size': group['size'],
                'group_name': group.get('group_name', ''),
                'description': group.get('description', ''),
                'registers': []
            }
            
            # Export register values and metadata
            register_map = group['parent_slave_map']
            reg_dict = getattr(register_map, group['reg_type'])
            
            for i in range(group['size']):
                addr = group['start_addr'] + i
                if addr in reg_dict:
                    entry = reg_dict[addr]
                    export_data['registers'].append({
                        'addr': addr,
                        'value': entry.value,
                        'alias': entry.alias,
                        'comment': entry.comment,
                        'units': entry.units
                    })
            
            self.group_exported.emit(filename, export_data)
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to export group: {str(e)}")
            return False
    
    def import_group(self, filename: str, register_map: RegisterMap, target_addr: Optional[int] = None) -> bool:
        """Import register group configuration from a file."""
        try:
            import json
            
            with open(filename, 'r') as f:
                import_data = json.load(f)
            
            reg_type = import_data['reg_type']
            original_start = import_data['start_addr']
            size = import_data['size']
            
            # Determine target address
            if target_addr is None:
                target_addr = self._find_next_available_address_range(register_map, reg_type, size)
                if target_addr is None:
                    target_addr = original_start
            
            # Validate target address
            try:
                RegisterValidator.validate_address_for_register_type(target_addr, reg_type)
            except ValidationError:
                return False
            
            # Import registers
            reg_dict = getattr(register_map, reg_type)
            addr_offset = target_addr - original_start
            
            for reg_data in import_data.get('registers', []):
                new_addr = reg_data['addr'] + addr_offset
                entry = RegisterEntry(
                    addr=new_addr,
                    reg_type=reg_type,
                    value=reg_data.get('value', 0),
                    alias=reg_data.get('alias', ''),
                    comment=reg_data.get('comment', ''),
                    units=reg_data.get('units', '')
                )
                reg_dict[new_addr] = entry
            
            # Create group metadata
            group_data = {
                'reg_type': reg_type,
                'start_addr': target_addr,
                'size': size,
                'register_id': self._get_next_group_id(),
                'group_name': import_data.get('group_name', ''),
                'description': import_data.get('description', ''),
                'parent_slave_map': register_map
            }
            
            self.group_imported.emit(group_data)
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to import group: {str(e)}")
            return False
    
    def convert_group_type(self, group: Dict, new_reg_type: str) -> bool:
        """Convert a register group to a different register type (HR ↔ IR only)."""
        try:
            old_type = group['reg_type']
            
            # Only allow conversion between compatible types
            if not self._are_types_convertible(old_type, new_reg_type):
                QMessageBox.warning(None, "Convert Group Type", 
                    f"Cannot convert from {old_type.upper()} to {new_reg_type.upper()}")
                return False
            
            register_map = group['parent_slave_map']
            start_addr = group['start_addr']
            size = group['size']
            
            # Find available address range in new type
            new_start_addr = self._find_next_available_address_range(register_map, new_reg_type, size)
            if new_start_addr is None:
                # Use default address for the new type
                new_start_addr = RegisterValidator.get_address_range(new_reg_type)[0]
            
            # Move registers from old type to new type
            old_dict = getattr(register_map, old_type)
            new_dict = getattr(register_map, new_reg_type)
            
            addr_offset = new_start_addr - start_addr
            
            for i in range(size):
                old_addr = start_addr + i
                new_addr = new_start_addr + i
                
                if old_addr in old_dict:
                    entry = old_dict[old_addr]
                    del old_dict[old_addr]
                    
                    # Update entry
                    entry.reg_type = new_reg_type
                    entry.addr = new_addr
                    new_dict[new_addr] = entry
            
            # Update group metadata
            group['reg_type'] = new_reg_type
            group['start_addr'] = new_start_addr
            
            return True
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to convert group type: {str(e)}")
            return False
    
    def _find_next_available_address_range(self, register_map: RegisterMap, reg_type: str, size: int) -> Optional[int]:
        """Find the next available address range for the given register type and size."""
        reg_dict = getattr(register_map, reg_type)
        addr_range = RegisterValidator.get_address_range(reg_type)
        
        for start_addr in range(addr_range[0], addr_range[1] - size + 2):
            # Check if this range is available
            available = True
            for i in range(size):
                if (start_addr + i) in reg_dict:
                    available = False
                    break
            
            if available:
                return start_addr
        
        return None
    
    def _get_next_group_id(self) -> int:
        """Get next available group ID."""
        import time
        return int(time.time() * 1000) % 1000000  # Use timestamp-based ID
    
    def _are_types_convertible(self, old_type: str, new_type: str) -> bool:
        """Check if two register types can be converted between each other."""
        # Allow conversion between 16-bit register types only
        convertible_pairs = [
            ('hr', 'ir'),
            ('ir', 'hr')
        ]
        return (old_type, new_type) in convertible_pairs or (new_type, old_type) in convertible_pairs