"""
Register Group Service

Business logic for register group operations.
"""

from typing import Dict, List, Optional, Tuple
import copy
import time
from ..models import RegisterMap, RegisterEntry, RegisterGroup, MultiTypeRegisterGroup, RegisterBlock
from .register_validator import RegisterValidator, ValidationError
from ..logger import get_logger

class RegisterGroupService:
    """Manages register group operations like duplicate, split, merge, etc."""
    
    def __init__(self):
        self.logger = get_logger("RegisterGroupService")
    
    def create_single_type_group(
        self, 
        register_map: RegisterMap,
        reg_type: str,
        start_addr: int,
        size: int,
        group_name: str = '',
        description: str = '',
        default_value: int = 0,
        alias_prefix: str = '',
        template_name: str = '',
        skip_conflict_check: bool = False
    ) -> RegisterGroup:
        """Create a new single-type register group."""
        
        self.logger.info("Creating %s group: addr=%d, size=%d, value=%d", 
                         reg_type.upper(), start_addr, size, default_value)
        
        try:
            # Validate inputs
            self.logger.debug("Validating address range %d-%d for %s", 
                            start_addr, start_addr + size - 1, reg_type.upper())
            RegisterValidator.validate_address_range(start_addr, start_addr + size - 1, reg_type)
            self.logger.debug("Address range validation passed")
            
            self.logger.debug("Validating register value %d for %s", default_value, reg_type.upper())
            RegisterValidator.validate_register_value(default_value, reg_type)
            self.logger.debug("Register value validation passed")
            
            # Check for conflicts (unless explicitly skipped)
            if not skip_conflict_check:
                self.logger.debug("Checking for address conflicts...")
                conflicts = RegisterValidator.check_address_conflicts(register_map, reg_type, start_addr, size)
                if conflicts:
                    self.logger.error("Address conflicts found at: %s", conflicts)
                    # Debug: show existing registers
                    reg_dict = getattr(register_map, reg_type, {})
                    existing_addrs = list(reg_dict.keys())
                    self.logger.debug("Existing %s registers: %s", reg_type.upper(), existing_addrs)
                    raise ValidationError(f"Address conflicts at: {conflicts}")
                self.logger.debug("No address conflicts found")
            else:
                self.logger.debug("Skipping conflict check as requested")
            
            # Create group
            self.logger.debug("Creating RegisterGroup object...")
            group = RegisterGroup(
                group_id=self._generate_group_id(),
                reg_type=reg_type,
                start_addr=start_addr,
                size=size,
                name=group_name,
                description=description,
                default_value=default_value,
                alias_prefix=alias_prefix,
                template_name=template_name
            )
            self.logger.debug("RegisterGroup object created with ID: %d", group.group_id)
            
            # Add registers to map
            self.logger.debug("Adding %d registers to RegisterMap...", size)
            register_map.add_block(reg_type, start_addr, size, default_value)
            self.logger.debug("Registers added to map")
            
            # Apply aliases if provided
            if alias_prefix:
                self.logger.debug("Applying aliases with prefix: %s", alias_prefix)
                self._apply_aliases(register_map, group, alias_prefix)
                self.logger.debug("Aliases applied")
            
            self.logger.info("Successfully created %s group '%s' (ID: %d) at address %d", 
                           reg_type.upper(), group_name, group.group_id, start_addr)
            return group
            
        except Exception as e:
            self.logger.error("Error creating %s group: %s", reg_type.upper(), str(e))
            raise
    
    def create_multi_type_group(
        self,
        register_map: RegisterMap,
        group_name: str,
        description: str,
        blocks: List[Dict]
    ) -> MultiTypeRegisterGroup:
        """Create a new multi-type register group."""
        
        if not group_name.strip():
            raise ValidationError("Group name cannot be empty")
        
        # Create register blocks
        register_blocks = []
        for block_data in blocks:
            # Validate block
            self.validator.validate_address_range(
                block_data['start_addr'], 
                block_data['start_addr'] + block_data['size'] - 1,
                block_data['reg_type']
            )
            
            # Check for conflicts
            conflicts = self.validator.check_address_conflicts(
                register_map, 
                block_data['reg_type'], 
                block_data['start_addr'], 
                block_data['size']
            )
            if conflicts:
                raise ValidationError(
                    f"Address conflicts in {block_data['reg_type'].upper()} block at: {conflicts}"
                )
            
            # Create block
            block = RegisterBlock(
                reg_type=block_data['reg_type'],
                start_addr=block_data['start_addr'],
                size=block_data['size'],
                default_value=block_data.get('default_value', 0),
                block_name=block_data.get('block_name', ''),
                block_description=block_data.get('block_description', '')
            )
            register_blocks.append(block)
        
        # Create multi-type group
        multi_group = MultiTypeRegisterGroup(
            group_id=self._generate_group_id(),
            name=group_name,
            description=description,
            blocks=register_blocks
        )
        
        # Validate no conflicts between blocks
        validation_errors = multi_group.validate_blocks()
        if validation_errors:
            raise ValidationError("; ".join(validation_errors))
        
        # Add all blocks to register map
        for block in register_blocks:
            register_map.add_block(
                block.reg_type,
                block.start_addr,
                block.size,
                block.default_value
            )
        
        return multi_group
    
    def duplicate_group(
        self, 
        source_group: RegisterGroup, 
        register_map: RegisterMap, 
        new_start_addr: Optional[int] = None
    ) -> RegisterGroup:
        """Duplicate an existing register group."""
        
        # Determine new start address
        if new_start_addr is None:
            new_start_addr = self.validator.find_available_address_range(
                register_map, source_group.reg_type, source_group.size
            )
            if new_start_addr is None:
                raise ValidationError(
                    f"Cannot find available address range for {source_group.size} "
                    f"{source_group.reg_type.upper()} registers"
                )
        
        # Validate new address range
        self.validator.validate_address_range(
            new_start_addr, 
            new_start_addr + source_group.size - 1, 
            source_group.reg_type
        )
        
        # Copy register entries
        reg_dict = getattr(register_map, source_group.reg_type)
        for i in range(source_group.size):
            old_addr = source_group.start_addr + i
            new_addr = new_start_addr + i
            
            if old_addr in reg_dict:
                old_entry = reg_dict[old_addr]
                new_entry = old_entry.copy(
                    addr=new_addr,
                    alias=f"Copy_{old_entry.alias}" if old_entry.alias else ""
                )
                register_map.add_register(new_entry)
        
        # Create new group
        new_group = RegisterGroup(
            group_id=self._generate_group_id(),
            reg_type=source_group.reg_type,
            start_addr=new_start_addr,
            size=source_group.size,
            name=f"Copy of {source_group.name}" if source_group.name else "",
            description=source_group.description,
            default_value=source_group.default_value,
            alias_prefix=source_group.alias_prefix,
            template_name=source_group.template_name,
            metadata=source_group.metadata.copy()
        )
        
        return new_group
    
    def split_group(self, source_group: RegisterGroup, split_point: int) -> Tuple[RegisterGroup, RegisterGroup]:
        """Split a register group at the specified point."""
        
        if split_point <= 0 or split_point >= source_group.size:
            raise ValidationError("Invalid split point")
        
        # Create two new groups using the model's split method
        group1, group2 = source_group.split_at(source_group.start_addr + split_point)
        
        # Update group IDs
        group1.group_id = self._generate_group_id()
        group2.group_id = self._generate_group_id()
        
        return (group1, group2)
    
    def merge_groups(self, group1: RegisterGroup, group2: RegisterGroup) -> RegisterGroup:
        """Merge two adjacent register groups of the same type."""
        
        if group1.reg_type != group2.reg_type:
            raise ValidationError("Can only merge groups of the same register type")
        
        # Ensure group1 comes before group2
        if group1.start_addr > group2.start_addr:
            group1, group2 = group2, group1
        
        if not group1.is_adjacent_to(group2):
            raise ValidationError("Groups must be adjacent to merge")
        
        # Create merged group
        merged_group = RegisterGroup(
            group_id=self._generate_group_id(),
            reg_type=group1.reg_type,
            start_addr=group1.start_addr,
            size=group1.size + group2.size,
            name=self._merge_names(group1.name, group2.name),
            description=f"{group1.description}; {group2.description}".strip('; '),
            default_value=group1.default_value,
            alias_prefix=group1.alias_prefix,
            template_name=group1.template_name or group2.template_name,
            metadata={**group1.metadata, **group2.metadata}
        )
        
        return merged_group
    
    def convert_group_type(self, group: RegisterGroup, new_reg_type: str, register_map: RegisterMap) -> RegisterGroup:
        """Convert a register group to a different register type."""
        
        # Validate conversion
        self.validator.validate_type_conversion(group.reg_type, new_reg_type)
        
        # Find available address range in new type
        new_start_addr = self.validator.find_available_address_range(register_map, new_reg_type, group.size)
        if new_start_addr is None:
            # Use default address for the new type
            type_info = self.validator.get_register_type_info(new_reg_type)
            new_start_addr = type_info['address_range'][0]
        
        # Move registers from old type to new type
        old_dict = getattr(register_map, group.reg_type)
        
        # Remove old registers and create new ones
        for i in range(group.size):
            old_addr = group.start_addr + i
            new_addr = new_start_addr + i
            
            if old_addr in old_dict:
                old_entry = old_dict[old_addr]
                register_map.remove_register(group.reg_type, old_addr)
                
                # Create new entry with converted type
                new_entry = old_entry.copy(
                    addr=new_addr,
                    reg_type=new_reg_type
                )
                register_map.add_register(new_entry)
        
        # Create converted group
        converted_group = RegisterGroup(
            group_id=self._generate_group_id(),
            reg_type=new_reg_type,
            start_addr=new_start_addr,
            size=group.size,
            name=group.name,
            description=group.description,
            default_value=group.default_value,
            alias_prefix=group.alias_prefix,
            template_name=group.template_name,
            metadata=group.metadata.copy()
        )
        
        return converted_group
    
    def validate_group_data(self, group_data: Dict) -> bool:
        """Validate group creation data."""
        required_fields = ['reg_type', 'start_addr', 'size']
        
        for field in required_fields:
            if field not in group_data:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate individual fields
        self.validator.validate_address_range(
            group_data['start_addr'],
            group_data['start_addr'] + group_data['size'] - 1,
            group_data['reg_type']
        )
        
        if 'default_value' in group_data:
            self.validator.validate_register_value(group_data['default_value'], group_data['reg_type'])
        
        return True
    
    def _generate_group_id(self) -> int:
        """Generate a unique group ID."""
        return int(time.time() * 1000) % 1000000
    
    def _apply_aliases(self, register_map: RegisterMap, group: RegisterGroup, alias_prefix: str):
        """Apply aliases to registers in a group."""
        reg_dict = getattr(register_map, group.reg_type)
        for i in range(group.size):
            addr = group.start_addr + i
            if addr in reg_dict:
                reg_dict[addr].alias = f"{alias_prefix}{i+1}"
    
    def _merge_names(self, name1: str, name2: str) -> str:
        """Merge two group names."""
        if name1 and name2:
            return f"{name1} + {name2}"
        return name1 or name2