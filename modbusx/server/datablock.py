from pymodbus.datastore import ModbusSparseDataBlock
from ..models.register_map import RegisterMap
from modbusx.logger import global_logger

class RegisterMapDataBlock(ModbusSparseDataBlock):
    """
    A Modbus DataBlock that directly uses a RegisterMap's data.
    Handles both 0-based and 1-based addressing by creating a larger address space.
    """

    def __init__(self, register_map: 'RegisterMap', regtype: str):
        self.reg_map = register_map
        self.regtype = regtype

        entries = register_map.all_entries(regtype)
        if not entries:
            # Initialize address attributes for empty register maps
            self.min_user_addr = 0
            self.max_user_addr = 0
            super().__init__({})
            return

        # Find the actual address range from the register map
        user_addrs = [e.addr for e in entries]
        self.min_user_addr = min(user_addrs)
        self.max_user_addr = max(user_addrs)
        
        global_logger.debug(f"RegisterMapDataBlock {regtype.upper()}: user address range {self.min_user_addr} to {self.max_user_addr}")

        # Create address space that maps protocol addresses to register values
        values_dict = {}
        
        for entry in entries:
            # Map user address directly to protocol address (1:1 mapping)
            protocol_addr = entry.addr
            values_dict[protocol_addr] = entry.value
            
            global_logger.debug(f"  User addr {entry.addr} -> protocol addr {protocol_addr} = {entry.value}")

        # Add padding for various client addressing expectations
        max_addr = max(values_dict.keys()) if values_dict else 0
        for addr in range(max_addr + 20):
            if addr not in values_dict:
                values_dict[addr] = 0

        super().__init__(values_dict)

    def _find_register_by_protocol_addr(self, protocol_addr: int):
        """Find the register entry that corresponds to this protocol address"""
        # Map protocol address directly to user address (1:1 mapping)
        user_addr = protocol_addr
        entry = self.reg_map.find_entry_by_addr(self.regtype, user_addr)
        return entry

    def getValues(self, address: int, count: int = 1):
        """Read values from the register map"""
        global_logger.debug(f"RegisterMapDataBlock.getValues: {self.regtype.upper()} address={address}, count={count}")
        
        values = []
        for offset in range(count):
            protocol_addr = address + offset
            entry = self._find_register_by_protocol_addr(protocol_addr)
            
            if entry:
                values.append(entry.value)
                global_logger.debug(f"  Read protocol addr {protocol_addr} -> user addr {entry.addr} = {entry.value}")
            else:
                # Return 0 for unmapped addresses
                values.append(0)
                global_logger.debug(f"  Read protocol addr {protocol_addr} -> unmapped, returning 0")
        
        return values

    def setValues(self, address: int, values: list) -> None:
        """Write values to the register map"""
        global_logger.debug(f"RegisterMapDataBlock.setValues: {self.regtype.upper()} address={address}, values={values}")
        
        for offset, value in enumerate(values):
            protocol_addr = address + offset
            entry = self._find_register_by_protocol_addr(protocol_addr)
            
            if entry:
                old_value = entry.value
                entry.value = value
                global_logger.debug(f"  Write protocol addr {protocol_addr} -> user addr {entry.addr}: {old_value} -> {value}")
            else:
                global_logger.debug(f"  Write to protocol addr {protocol_addr} ignored (unmapped)")
        
        # Update the internal storage
        super().setValues(address, values)

    def validate(self, address: int, count: int = 1) -> bool:
        """Validate that the requested address range is available - always return True to be permissive"""
        global_logger.debug(f"RegisterMapDataBlock.validate: {self.regtype.upper()} address={address}, count={count} - ALLOWING ALL")
        return True