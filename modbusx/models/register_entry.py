"""
Register Entry Model

Pure data model representing a single ModBus register.
"""

from typing import Optional
from dataclasses import dataclass

@dataclass
class RegisterEntry:
    """Represents a single ModBus register/coil with metadata."""
    
    addr: int
    reg_type: str  # "hr", "ir", "co", "di"
    value: int = 0
    alias: str = ''
    comment: str = ''
    units: str = ''
    display_type: str = 'Unsigned'
    
    def __post_init__(self):
        """Validate register entry data."""
        from ..services.register_validator import RegisterValidator
        RegisterValidator.validate_register_type(self.reg_type)
        
        if self.addr < 0:
            raise ValueError(f"Address cannot be negative: {self.addr}")
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation."""
        return {
            'addr': self.addr,
            'reg_type': self.reg_type,
            'value': self.value,
            'alias': self.alias,
            'comment': self.comment,
            'units': self.units,
            'display_type': self.display_type
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'RegisterEntry':
        """Create from dictionary representation."""
        return cls(
            addr=data['addr'],
            reg_type=data['reg_type'],
            value=data.get('value', 0),
            alias=data.get('alias', ''),
            comment=data.get('comment', ''),
            units=data.get('units', ''),
            display_type=data.get('display_type', 'Unsigned')
        )
    
    def copy(self, **kwargs) -> 'RegisterEntry':
        """Create a copy with optional field updates."""
        data = self.to_dict()
        data.update(kwargs)
        return self.from_dict(data)
