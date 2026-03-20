"""
Connection and Slave Models

Pure data models for connection and slave management.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .register_map import RegisterMap
from .register_group import RegisterGroup
from .multi_type_group import MultiTypeRegisterGroup

@dataclass
class SlaveModel:
    """Represents a ModBus slave device."""
    
    slave_id: int
    name: str = ''
    description: str = ''
    register_map: RegisterMap = field(default_factory=RegisterMap)
    register_groups: List[RegisterGroup] = field(default_factory=list)
    multi_type_groups: List[MultiTypeRegisterGroup] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    is_active: bool = True
    
    def __post_init__(self):
        """Validate slave data."""
        if not (1 <= self.slave_id <= 247):
            raise ValueError(f"Slave ID must be between 1 and 247: {self.slave_id}")
    
    def add_register_group(self, group: RegisterGroup) -> None:
        """Add a register group to this slave."""
        # Check for conflicts
        for existing_group in self.register_groups:
            if existing_group.overlaps_with(group):
                raise ValueError(
                    f"Group overlaps with existing group {existing_group.group_id} "
                    f"at {existing_group.address_range}"
                )
        
        self.register_groups.append(group)
        
        # Generate and add register entries to the register map
        entries = group.generate_register_entries()
        for entry in entries:
            self.register_map.add_register(entry)
    
    def remove_register_group(self, group_id: int) -> bool:
        """Remove a register group by ID. Returns True if removed."""
        for i, group in enumerate(self.register_groups):
            if group.group_id == group_id:
                # Remove registers from map
                for addr in range(group.start_addr, group.end_addr + 1):
                    self.register_map.remove_register(group.reg_type, addr)
                
                # Remove group
                self.register_groups.pop(i)
                return True
        return False
    
    def get_register_group(self, group_id: int) -> Optional[RegisterGroup]:
        """Get a register group by ID."""
        for group in self.register_groups:
            if group.group_id == group_id:
                return group
        return None
    
    def add_multi_type_group(self, multi_group: MultiTypeRegisterGroup) -> None:
        """Add a multi-type register group to this slave."""
        # Validate blocks don't conflict with existing groups
        validation_errors = []
        for block in multi_group.blocks:
            for existing_group in self.register_groups:
                if (existing_group.reg_type == block.reg_type and
                    existing_group.start_addr <= block.end_addr and
                    block.start_addr <= existing_group.end_addr):
                    validation_errors.append(
                        f"Block {block.reg_type.upper()} {block.start_addr}-{block.end_addr} "
                        f"conflicts with group {existing_group.group_id}"
                    )
        
        if validation_errors:
            raise ValueError("Multi-type group conflicts: " + "; ".join(validation_errors))
        
        self.multi_type_groups.append(multi_group)
        
        # Add register entries for each block
        for block in multi_group.blocks:
            self.register_map.add_block(
                block.reg_type, 
                block.start_addr, 
                block.size, 
                block.default_value
            )
    
    def remove_multi_type_group(self, group_id: int) -> bool:
        """Remove a multi-type register group by ID. Returns True if removed."""
        for i, multi_group in enumerate(self.multi_type_groups):
            if multi_group.group_id == group_id:
                # Remove registers from map
                for block in multi_group.blocks:
                    for addr in range(block.start_addr, block.end_addr + 1):
                        self.register_map.remove_register(block.reg_type, addr)
                
                # Remove group
                self.multi_type_groups.pop(i)
                return True
        return False
    
    def get_all_groups(self) -> List[Dict]:
        """Get all groups (single and multi-type) as dictionaries."""
        all_groups = []
        
        # Add single-type groups
        for group in self.register_groups:
            group_data = group.to_dict()
            group_data['group_type'] = 'single_type'
            all_groups.append(group_data)
        
        # Add multi-type groups
        for multi_group in self.multi_type_groups:
            group_data = multi_group.to_dict()
            group_data['group_type'] = 'multi_type'
            all_groups.append(group_data)
        
        return all_groups
    
    def get_statistics(self) -> Dict:
        """Get slave statistics."""
        register_stats = self.register_map.get_statistics()
        
        return {
            'slave_id': self.slave_id,
            'name': self.name,
            'register_groups_count': len(self.register_groups),
            'multi_type_groups_count': len(self.multi_type_groups),
            'total_groups': len(self.register_groups) + len(self.multi_type_groups),
            'is_active': self.is_active,
            **register_stats
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'slave_id': self.slave_id,
            'name': self.name,
            'description': self.description,
            'register_map': self.register_map.to_dict(),
            'register_groups': [group.to_dict() for group in self.register_groups],
            'multi_type_groups': [group.to_dict() for group in self.multi_type_groups],
            'metadata': self.metadata,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SlaveModel':
        """Create from dictionary representation."""
        # Create register map
        register_map = RegisterMap.from_dict(data.get('register_map', {}))
        
        # Create register groups
        register_groups = [
            RegisterGroup.from_dict(group_data) 
            for group_data in data.get('register_groups', [])
        ]
        
        # Create multi-type groups
        multi_type_groups = [
            MultiTypeRegisterGroup.from_dict(group_data)
            for group_data in data.get('multi_type_groups', [])
        ]
        
        return cls(
            slave_id=data['slave_id'],
            name=data.get('name', ''),
            description=data.get('description', ''),
            register_map=register_map,
            register_groups=register_groups,
            multi_type_groups=multi_type_groups,
            metadata=data.get('metadata', {}),
            is_active=data.get('is_active', True)
        )

@dataclass
class ConnectionModel:
    """Represents a ModBus connection with multiple slaves."""
    
    address: str
    port: int
    name: str = ''
    protocol: str = 'tcp'  # 'tcp', 'rtu', 'ascii'
    slaves: List[SlaveModel] = field(default_factory=list)
    is_open: bool = False
    metadata: Dict = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate connection data."""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535: {self.port}")
        
        if self.protocol not in ('tcp', 'rtu', 'ascii'):
            raise ValueError(f"Invalid protocol: {self.protocol}")
    
    @property
    def connection_string(self) -> str:
        """Get connection string representation."""
        return f"{self.address}:{self.port}"
    
    def add_slave(self, slave: SlaveModel) -> None:
        """Add a slave to this connection."""
        # Check for duplicate slave IDs
        for existing_slave in self.slaves:
            if existing_slave.slave_id == slave.slave_id:
                raise ValueError(f"Slave ID {slave.slave_id} already exists")
        
        self.slaves.append(slave)
    
    def remove_slave(self, slave_id: int) -> bool:
        """Remove a slave by ID. Returns True if removed."""
        for i, slave in enumerate(self.slaves):
            if slave.slave_id == slave_id:
                self.slaves.pop(i)
                return True
        return False
    
    def get_slave(self, slave_id: int) -> Optional[SlaveModel]:
        """Get a slave by ID."""
        for slave in self.slaves:
            if slave.slave_id == slave_id:
                return slave
        return None
    
    def get_next_slave_id(self) -> int:
        """Get the next available slave ID."""
        used_ids = {slave.slave_id for slave in self.slaves}
        for slave_id in range(1, 248):
            if slave_id not in used_ids:
                return slave_id
        raise ValueError("No available slave IDs (max 247 slaves)")
    
    def get_statistics(self) -> Dict:
        """Get connection statistics."""
        total_registers = 0
        total_groups = 0
        
        for slave in self.slaves:
            slave_stats = slave.get_statistics()
            total_registers += slave_stats['total_count']
            total_groups += slave_stats['total_groups']
        
        return {
            'connection_string': self.connection_string,
            'protocol': self.protocol,
            'slaves_count': len(self.slaves),
            'total_registers': total_registers,
            'total_groups': total_groups,
            'is_open': self.is_open
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation."""
        return {
            'address': self.address,
            'port': self.port,
            'name': self.name,
            'protocol': self.protocol,
            'slaves': [slave.to_dict() for slave in self.slaves],
            'is_open': self.is_open,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConnectionModel':
        """Create from dictionary representation."""
        slaves = [SlaveModel.from_dict(slave_data) for slave_data in data.get('slaves', [])]
        
        return cls(
            address=data['address'],
            port=data['port'],
            name=data.get('name', ''),
            protocol=data.get('protocol', 'tcp'),
            slaves=slaves,
            is_open=data.get('is_open', False),
            metadata=data.get('metadata', {})
        )