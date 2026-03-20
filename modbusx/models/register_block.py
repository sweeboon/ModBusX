"""
Register Block Model

Pure data model for a contiguous block of registers.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List
from .register_entry import RegisterEntry

@dataclass
class RegisterBlock:
    """
    Represents a contiguous block of registers of the same type.
    
    A block is a group of consecutive register addresses that can be
    read/written together efficiently.
    """
    
    block_id: int
    reg_type: str  # 'hr', 'ir', 'co', 'di'
    start_addr: int
    size: int
    name: str = ""
    description: str = ""
    default_value: int = 0
    created_at: str = ""
    modified_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate block data after initialization."""
        from ..services.register_validator import RegisterValidator
        RegisterValidator.validate_register_type(self.reg_type)
        
        if self.size <= 0:
            raise ValueError("Block size must be positive")
        
        if self.start_addr < 0:
            raise ValueError("Start address must be non-negative")
    
    @property
    def end_addr(self) -> int:
        """Get the ending address of the block."""
        return self.start_addr + self.size - 1
    
    @property
    def address_range(self) -> tuple:
        """Get the address range as (start, end) tuple."""
        return (self.start_addr, self.end_addr)
    
    # Backward compatibility properties
    @property
    def block_name(self) -> str:
        """Backward compatibility alias for name."""
        return self.name
    
    @property
    def block_description(self) -> str:
        """Backward compatibility alias for description."""
        return self.description
    
    def contains_address(self, addr: int) -> bool:
        """Check if the block contains the given address."""
        return self.start_addr <= addr <= self.end_addr
    
    def overlaps_with(self, other: 'RegisterBlock') -> bool:
        """Check if this block overlaps with another block."""
        if self.reg_type != other.reg_type:
            return False
        
        return not (self.end_addr < other.start_addr or other.end_addr < self.start_addr)
    
    def is_adjacent_to(self, other: 'RegisterBlock') -> bool:
        """Check if this block is adjacent to another block."""
        if self.reg_type != other.reg_type:
            return False
        
        return (self.end_addr + 1 == other.start_addr or 
                other.end_addr + 1 == self.start_addr)
    
    def can_merge_with(self, other: 'RegisterBlock') -> bool:
        """Check if this block can be merged with another block."""
        return (self.reg_type == other.reg_type and
                (self.overlaps_with(other) or self.is_adjacent_to(other)))
    
    def to_register_group(self, group_id: int) -> 'RegisterGroup':
        """Convert this block to a RegisterGroup."""
        from .register_group import RegisterGroup
        return RegisterGroup(
            group_id=group_id,
            reg_type=self.reg_type,
            start_addr=self.start_addr,
            size=self.size,
            name=self.name,
            description=self.description,
            default_value=self.default_value
        )
    
    def split_at(self, split_addr: int) -> tuple['RegisterBlock', 'RegisterBlock']:
        """
        Split the block at the given address.
        
        Args:
            split_addr: Address where to split (exclusive for first block)
            
        Returns:
            Tuple of (first_block, second_block)
        """
        if not self.contains_address(split_addr):
            raise ValueError("Split address must be within block range")
        
        if split_addr == self.start_addr:
            raise ValueError("Cannot split at start address")
        
        if split_addr == self.end_addr:
            raise ValueError("Cannot split at end address")
        
        # Create first block
        first_size = split_addr - self.start_addr
        first_block = RegisterBlock(
            block_id=self.block_id,
            reg_type=self.reg_type,
            start_addr=self.start_addr,
            size=first_size,
            name=f"{self.name}_1" if self.name else "",
            description=f"{self.description} (part 1)" if self.description else "",
            default_value=self.default_value,
            metadata=self.metadata.copy()
        )
        
        # Create second block
        second_size = self.end_addr - split_addr + 1
        second_block = RegisterBlock(
            block_id=self.block_id + 1000,  # Ensure unique ID
            reg_type=self.reg_type,
            start_addr=split_addr,
            size=second_size,
            name=f"{self.name}_2" if self.name else "",
            description=f"{self.description} (part 2)" if self.description else "",
            default_value=self.default_value,
            metadata=self.metadata.copy()
        )
        
        return first_block, second_block
    
    def generate_register_entries(self) -> List[RegisterEntry]:
        """Generate RegisterEntry objects for all addresses in this block."""
        entries = []
        for i in range(self.size):
            addr = self.start_addr + i
            entry = RegisterEntry(
                addr=addr,
                reg_type=self.reg_type,
                value=self.default_value,
                alias=f"{self.name}_{i+1}" if self.name else "",
                comment=f"Generated from block {self.block_id}",
                units=""
            )
            entries.append(entry)
        return entries
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'block_id': self.block_id,
            'reg_type': self.reg_type,
            'start_addr': self.start_addr,
            'size': self.size,
            'name': self.name,
            'description': self.description,
            'default_value': self.default_value,
            'created_at': self.created_at,
            'modified_at': self.modified_at,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RegisterBlock':
        """Create from dictionary representation."""
        return cls(
            block_id=data['block_id'],
            reg_type=data['reg_type'],
            start_addr=data['start_addr'],
            size=data['size'],
            name=data.get('name', ''),
            description=data.get('description', ''),
            default_value=data.get('default_value', 0),
            created_at=data.get('created_at', ''),
            modified_at=data.get('modified_at', ''),
            metadata=data.get('metadata', {})
        )
    
    def __str__(self) -> str:
        """String representation."""
        return (f"RegisterBlock(id={self.block_id}, type={self.reg_type.upper()}, "
                f"range={self.start_addr}:{self.end_addr}, size={self.size})")
    
    def __repr__(self) -> str:
        """Detailed string representation."""
        return (f"RegisterBlock(block_id={self.block_id}, reg_type='{self.reg_type}', "
                f"start_addr={self.start_addr}, size={self.size}, name='{self.name}')")