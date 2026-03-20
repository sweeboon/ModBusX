"""
Register Group Model

Pure data model representing a logical group of registers.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .register_entry import RegisterEntry

@dataclass
class RegisterGroup:
    """Represents a logical group of registers of the same type."""
    
    group_id: int
    reg_type: str  # "hr", "ir", "co", "di"
    start_addr: int
    size: int
    name: str = ''
    description: str = ''
    default_value: int = 0
    alias_prefix: str = ''
    template_name: str = ''
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate register group data."""
        from ..services.register_validator import RegisterValidator
        RegisterValidator.validate_register_type(self.reg_type)
        
        if self.size <= 0:
            raise ValueError(f"Size must be positive: {self.size}")
        
        if self.start_addr < 0:
            raise ValueError(f"Start address cannot be negative: {self.start_addr}")
    
    @property
    def end_addr(self) -> int:
        """Get the end address of this group."""
        return self.start_addr + self.size - 1
    
    @property
    def address_range(self) -> tuple:
        """Get the address range as (start, end) tuple."""
        return (self.start_addr, self.end_addr)
    
    def contains_address(self, addr: int) -> bool:
        """Check if an address is within this group."""
        return self.start_addr <= addr <= self.end_addr
    
    def get_relative_address(self, addr: int) -> int:
        """Get the relative address within the group (0-based)."""
        if not self.contains_address(addr):
            raise ValueError(f"Address {addr} not in group range {self.address_range}")
        return addr - self.start_addr
    
    def get_absolute_address(self, relative_addr: int) -> int:
        """Get the absolute address from relative address."""
        if not (0 <= relative_addr < self.size):
            raise ValueError(f"Relative address {relative_addr} out of range [0, {self.size-1}]")
        return self.start_addr + relative_addr
    
    def generate_register_entries(self) -> List[RegisterEntry]:
        """Generate register entries for this group."""
        entries = []
        for i in range(self.size):
            addr = self.start_addr + i
            alias = f"{self.alias_prefix}{i+1}" if self.alias_prefix else ""
            
            entry = RegisterEntry(
                addr=addr,
                reg_type=self.reg_type,
                value=self.default_value,
                alias=alias,
                comment=self.description,
                units=''
            )
            entries.append(entry)
        
        return entries
    
    def overlaps_with(self, other: 'RegisterGroup') -> bool:
        """Check if this group overlaps with another group."""
        if self.reg_type != other.reg_type:
            return False
        
        return not (self.end_addr < other.start_addr or other.end_addr < self.start_addr)
    
    def is_adjacent_to(self, other: 'RegisterGroup') -> bool:
        """Check if this group is adjacent to another group."""
        if self.reg_type != other.reg_type:
            return False
        
        return (self.end_addr + 1 == other.start_addr or 
                other.end_addr + 1 == self.start_addr)
    
    def can_merge_with(self, other: 'RegisterGroup') -> bool:
        """Check if this group can be merged with another group."""
        return (self.reg_type == other.reg_type and 
                (self.overlaps_with(other) or self.is_adjacent_to(other)))
    
    def split_at(self, split_addr: int) -> tuple['RegisterGroup', 'RegisterGroup']:
        """Split this group at the specified address, returning two new groups."""
        if not self.contains_address(split_addr):
            raise ValueError(f"Split address {split_addr} not in group range {self.address_range}")
        
        if split_addr == self.start_addr:
            raise ValueError("Cannot split at start address")
        
        if split_addr == self.end_addr:
            raise ValueError("Cannot split at end address")
        
        # First group: start_addr to split_addr-1
        first_size = split_addr - self.start_addr
        first_group = RegisterGroup(
            group_id=self.group_id,
            reg_type=self.reg_type,
            start_addr=self.start_addr,
            size=first_size,
            name=f"{self.name} - Part 1" if self.name else "",
            description=self.description,
            default_value=self.default_value,
            alias_prefix=self.alias_prefix,
            template_name=self.template_name,
            metadata=self.metadata.copy()
        )
        
        # Second group: split_addr to end_addr
        second_size = self.end_addr - split_addr + 1
        second_group = RegisterGroup(
            group_id=self.group_id + 1,  # Increment ID for second group
            reg_type=self.reg_type,
            start_addr=split_addr,
            size=second_size,
            name=f"{self.name} - Part 2" if self.name else "",
            description=self.description,
            default_value=self.default_value,
            alias_prefix=self.alias_prefix,
            template_name=self.template_name,
            metadata=self.metadata.copy()
        )
        
        return (first_group, second_group)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'group_id': self.group_id,
            'reg_type': self.reg_type,
            'start_addr': self.start_addr,
            'size': self.size,
            'name': self.name,
            'description': self.description,
            'default_value': self.default_value,
            'alias_prefix': self.alias_prefix,
            'template_name': self.template_name,
            'metadata': self.metadata,
            'end_addr': self.end_addr
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RegisterGroup':
        """Create from dictionary representation."""
        # Extract known fields and put rest in metadata
        known_fields = {
            'group_id', 'reg_type', 'start_addr', 'size', 'name', 
            'description', 'default_value', 'alias_prefix', 'template_name', 'metadata'
        }
        
        init_data = {}
        metadata = data.get('metadata', {}).copy()
        
        for key, value in data.items():
            if key in known_fields:
                init_data[key] = value
            elif key != 'end_addr':  # Skip calculated field
                metadata[key] = value
        
        init_data['metadata'] = metadata
        return cls(**init_data)