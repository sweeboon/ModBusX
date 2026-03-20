"""
Multi-Type Register Group Model

Pure data model for groups containing multiple ModBus register types.
"""

from typing import Dict, List, Set
from dataclasses import dataclass, field
from .register_group import RegisterGroup
from .register_block import RegisterBlock


@dataclass
class MultiTypeRegisterGroup:
    """Represents a register group that can contain multiple ModBus register types."""
    
    group_id: int
    name: str
    description: str = ''
    blocks: List[RegisterBlock] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate multi-type group data."""
        if not self.name.strip():
            raise ValueError("Group name cannot be empty")
    
    def add_block(self, block: RegisterBlock) -> None:
        """Add a register block to this group."""
        # Check for conflicts with existing blocks of the same type
        for existing_block in self.blocks:
            if existing_block.reg_type == block.reg_type:
                if self._blocks_overlap(existing_block, block):
                    raise ValueError(
                        f"Block overlaps with existing {block.reg_type.upper()} block "
                        f"at {existing_block.start_addr}-{existing_block.end_addr}"
                    )
        
        self.blocks.append(block)
    
    def remove_block(self, block_index: int) -> RegisterBlock:
        """Remove a block by index and return it."""
        if not (0 <= block_index < len(self.blocks)):
            raise IndexError(f"Block index {block_index} out of range")
        
        return self.blocks.pop(block_index)
    
    def get_blocks_by_type(self, reg_type: str) -> List[RegisterBlock]:
        """Get all blocks of a specific register type."""
        return [block for block in self.blocks if block.reg_type == reg_type]
    
    def get_register_types(self) -> Set[str]:
        """Get set of all register types in this group."""
        return {block.reg_type for block in self.blocks}
    
    def get_total_registers(self) -> int:
        """Get total number of registers across all blocks."""
        return sum(block.size for block in self.blocks)
    
    def get_type_statistics(self) -> Dict[str, int]:
        """Get register count by type."""
        stats = {'hr': 0, 'ir': 0, 'co': 0, 'di': 0}
        for block in self.blocks:
            stats[block.reg_type] += block.size
        return stats
    
    def get_address_ranges(self) -> Dict[str, List[tuple]]:
        """Get address ranges for each register type."""
        ranges = {}
        for block in self.blocks:
            if block.reg_type not in ranges:
                ranges[block.reg_type] = []
            ranges[block.reg_type].append((block.start_addr, block.end_addr))
        return ranges
    
    def contains_address(self, reg_type: str, addr: int) -> bool:
        """Check if an address is contained in any block of the specified type."""
        for block in self.blocks:
            if block.reg_type == reg_type and block.start_addr <= addr <= block.end_addr:
                return True
        return False
    
    def find_block_containing_address(self, reg_type: str, addr: int) -> RegisterBlock:
        """Find the block containing the specified address."""
        for block in self.blocks:
            if block.reg_type == reg_type and block.start_addr <= addr <= block.end_addr:
                return block
        raise ValueError(f"No {reg_type.upper()} block contains address {addr}")
    
    def generate_register_groups(self) -> List[RegisterGroup]:
        """Generate individual RegisterGroup objects for each block."""
        groups = []
        for i, block in enumerate(self.blocks):
            group = block.to_register_group(self.group_id * 1000 + i)  # Unique sub-group ID
            groups.append(group)
        return groups
    
    def validate_blocks(self) -> List[str]:
        """Validate all blocks and return list of error messages."""
        errors = []
        
        # Check for overlaps within each register type
        type_blocks = {}
        for block in self.blocks:
            if block.reg_type not in type_blocks:
                type_blocks[block.reg_type] = []
            type_blocks[block.reg_type].append(block)
        
        for reg_type, blocks in type_blocks.items():
            for i, block1 in enumerate(blocks):
                for j, block2 in enumerate(blocks[i+1:], i+1):
                    if self._blocks_overlap(block1, block2):
                        errors.append(
                            f"Overlapping {reg_type.upper()} blocks: "
                            f"{block1.start_addr}-{block1.end_addr} and "
                            f"{block2.start_addr}-{block2.end_addr}"
                        )
        
        return errors
    
    def _blocks_overlap(self, block1: RegisterBlock, block2: RegisterBlock) -> bool:
        """Check if two blocks overlap."""
        return not (block1.end_addr < block2.start_addr or block2.end_addr < block1.start_addr)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'group_id': self.group_id,
            'name': self.name,
            'description': self.description,
            'blocks': [block.to_dict() for block in self.blocks],
            'metadata': self.metadata,
            'group_type': 'multi_type'
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MultiTypeRegisterGroup':
        """Create from dictionary representation."""
        blocks = [RegisterBlock.from_dict(block_data) for block_data in data.get('blocks', [])]
        
        return cls(
            group_id=data['group_id'],
            name=data['name'],
            description=data.get('description', ''),
            blocks=blocks,
            metadata=data.get('metadata', {})
        )