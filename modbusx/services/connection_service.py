"""
Connection Service

Business logic for connection and slave management.
"""

from typing import Dict, List, Optional, Tuple
from ..models import ConnectionModel, SlaveModel, RegisterMap, RegisterGroup
from .register_validator import RegisterValidator, ValidationError

class ConnectionService:
    """Service for managing connections and slaves."""
    
    def __init__(self, validator: RegisterValidator = None):
        self.validator = validator or RegisterValidator()
        self.connections: Dict[str, ConnectionModel] = {}
    
    def create_connection(
        self, 
        address: str, 
        port: int, 
        name: str = '', 
        protocol: str = 'tcp'
    ) -> ConnectionModel:
        """Create a new connection."""
        
        connection_key = f"{address}:{port}"
        
        # Check for duplicate connections
        if connection_key in self.connections:
            raise ValidationError(f"Connection {connection_key} already exists")
        
        # Create connection with default slave
        connection = ConnectionModel(
            address=address,
            port=port,
            name=name,
            protocol=protocol
        )
        
        # Add default slave (ID 1) with default register group
        default_slave = self._create_default_slave()
        connection.add_slave(default_slave)
        
        self.connections[connection_key] = connection
        return connection
    
    def remove_connection(self, address: str, port: int) -> bool:
        """Remove a connection. Returns True if removed."""
        connection_key = f"{address}:{port}"
        if connection_key in self.connections:
            del self.connections[connection_key]
            return True
        return False
    
    def get_connection(self, address: str, port: int) -> Optional[ConnectionModel]:
        """Get a connection by address and port."""
        connection_key = f"{address}:{port}"
        return self.connections.get(connection_key)
    
    def get_all_connections(self) -> List[ConnectionModel]:
        """Get all connections."""
        return list(self.connections.values())
    
    def add_slave_to_connection(
        self, 
        address: str, 
        port: int, 
        slave_id: Optional[int] = None,
        slave_name: str = ''
    ) -> SlaveModel:
        """Add a new slave to an existing connection."""
        
        connection = self.get_connection(address, port)
        if not connection:
            raise ValidationError(f"Connection {address}:{port} not found")
        
        # Determine slave ID
        if slave_id is None:
            slave_id = connection.get_next_slave_id()
        
        # Create slave with default register group
        slave = SlaveModel(
            slave_id=slave_id,
            name=slave_name or f"Slave {slave_id}"
        )
        
        # Add default register group
        default_group = self._create_default_register_group(slave_id)
        slave.add_register_group(default_group)
        
        connection.add_slave(slave)
        return slave
    
    def remove_slave_from_connection(
        self, 
        address: str, 
        port: int, 
        slave_id: int
    ) -> bool:
        """Remove a slave from a connection. Returns True if removed."""
        
        connection = self.get_connection(address, port)
        if not connection:
            return False
        
        return connection.remove_slave(slave_id)
    
    def get_slave(self, address: str, port: int, slave_id: int) -> Optional[SlaveModel]:
        """Get a slave from a connection."""
        connection = self.get_connection(address, port)
        if not connection:
            return None
        
        return connection.get_slave(slave_id)
    
    def connect_to_device(self, address: str, port: int) -> bool:
        """Connect to a ModBus device."""
        connection = self.get_connection(address, port)
        if not connection:
            raise ValidationError(f"Connection {address}:{port} not found")
        
        try:
            # Map protocol string to enum
            protocol_map = {
                'tcp': ModbusProtocol.TCP,
                'rtu': ModbusProtocol.RTU,
                'ascii': ModbusProtocol.RTU  # ASCII uses same client as RTU
            }
            
            protocol = protocol_map.get(connection.protocol, ModbusProtocol.TCP)
            connection_string = f"{address}:{port}"
            
            # Create client based on protocol
            if protocol == ModbusProtocol.TCP:
                client = self.modbus_client_service.create_client(
                    connection_string, 
                    protocol,
                    host=address,
                    port=port
                )
            elif protocol == ModbusProtocol.RTU:
                # For RTU, address is the serial port
                client = self.modbus_client_service.create_client(
                    connection_string,
                    protocol,
                    port=address,  # Serial port name
                    baudrate=getattr(connection, 'baudrate', 9600),
                    parity=getattr(connection, 'parity', 'N'),
                    stopbits=getattr(connection, 'stopbits', 1),
                    bytesize=getattr(connection, 'bytesize', 8)
                )
            else:
                raise ValidationError(f"Unsupported protocol: {connection.protocol}")
            
            # Attempt connection
            if client.connect():
                connection.is_open = True
                return True
            else:
                connection.is_open = False
                return False
                
        except Exception as e:
            connection.is_open = False
            raise ValidationError(f"Failed to connect to {address}:{port}: {str(e)}")
    
    def disconnect_from_device(self, address: str, port: int) -> bool:
        """Disconnect from a ModBus device."""
        connection = self.get_connection(address, port)
        if not connection:
            return False
        
        connection_string = f"{address}:{port}"
        client = self.modbus_client_service.get_client(connection_string)
        
        if client:
            client.disconnect()
            self.modbus_client_service.remove_client(connection_string)
        
        connection.is_open = False
        return True
    
    def is_device_connected(self, address: str, port: int) -> bool:
        """Check if device is connected."""
        connection = self.get_connection(address, port)
        if not connection:
            return False
        
        connection_string = f"{address}:{port}"
        client = self.modbus_client_service.get_client(connection_string)
        
        if client:
            is_connected = client.is_connected()
            # Update connection status
            connection.is_open = is_connected
            return is_connected
        
        return False
    
    def update_connection_status(self, address: str, port: int, is_open: bool) -> bool:
        """Update connection open/closed status."""
        connection = self.get_connection(address, port)
        if not connection:
            return False
        
        connection.is_open = is_open
        return True
    
    def get_connection_statistics(self, address: str, port: int) -> Optional[Dict]:
        """Get statistics for a connection."""
        connection = self.get_connection(address, port)
        if not connection:
            return None
        
        return connection.get_statistics()
    
    def get_all_statistics(self) -> Dict:
        """Get statistics for all connections."""
        stats = {
            'total_connections': len(self.connections),
            'open_connections': 0,
            'total_slaves': 0,
            'total_registers': 0,
            'total_groups': 0,
            'connections': []
        }
        
        for connection in self.connections.values():
            conn_stats = connection.get_statistics()
            stats['connections'].append(conn_stats)
            
            if connection.is_open:
                stats['open_connections'] += 1
            
            stats['total_slaves'] += conn_stats['slaves_count']
            stats['total_registers'] += conn_stats['total_registers']
            stats['total_groups'] += conn_stats['total_groups']
        
        return stats
    
    def validate_connection_params(self, address: str, port: int, protocol: str = 'tcp') -> bool:
        """Validate connection parameters."""
        
        if not address.strip():
            raise ValidationError("Address cannot be empty")
        
        if not (1 <= port <= 65535):
            raise ValidationError(f"Port must be between 1 and 65535: {port}")
        
        if protocol not in ('tcp', 'rtu', 'ascii'):
            raise ValidationError(f"Invalid protocol: {protocol}")
        
        return True
    
    def find_connections_by_protocol(self, protocol: str) -> List[ConnectionModel]:
        """Find all connections using a specific protocol."""
        return [conn for conn in self.connections.values() if conn.protocol == protocol]
    
    def find_connections_by_status(self, is_open: bool) -> List[ConnectionModel]:
        """Find all connections with a specific status."""
        return [conn for conn in self.connections.values() if conn.is_open == is_open]
    
    # Note: Direct ModBus communication is handled by server components
    # This service focuses on connection and slave management only
    
    def export_connection_config(self, address: str, port: int) -> Optional[Dict]:
        """Export connection configuration."""
        connection = self.get_connection(address, port)
        if not connection:
            return None
        
        return connection.to_dict()
    
    def import_connection_config(self, config_data: Dict) -> ConnectionModel:
        """Import connection configuration."""
        connection = ConnectionModel.from_dict(config_data)
        
        connection_key = f"{connection.address}:{connection.port}"
        if connection_key in self.connections:
            raise ValidationError(f"Connection {connection_key} already exists")
        
        self.connections[connection_key] = connection
        return connection
    
    def _create_default_slave(self) -> SlaveModel:
        """Create a default slave with basic register group."""
        slave = SlaveModel(slave_id=1, name="Slave 1")
        
        # Add default register group
        default_group = self._create_default_register_group(1)
        slave.add_register_group(default_group)
        
        return slave
    
    def _create_default_register_group(self, slave_id: int) -> RegisterGroup:
        """Create a default register group for a slave."""
        return RegisterGroup(
            group_id=1,
            reg_type='hr',
            start_addr=40001,
            size=10,
            name=f"Default Group - Slave {slave_id}",
            description="Default holding register group",
            default_value=0
        )