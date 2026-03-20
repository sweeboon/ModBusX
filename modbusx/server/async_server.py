"""
Pure Asyncio Modbus Server Implementation

Replaces the mixed Qt+asyncio architecture with pure asyncio for both TCP and Serial.
Solves the hanging issue with COM port connections. 
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from .datablock import RegisterMapDataBlock
from .function_registry import FunctionHandlerRegistry
from .function_handlers import ModbusRequest
from modbusx.logger import global_logger
from modbusx.utils.checksum import calculate_crc16, calculate_lrc

try:
    import serial_asyncio
    SERIAL_ASYNCIO_AVAILABLE = True
except ImportError:
    serial_asyncio = None
    SERIAL_ASYNCIO_AVAILABLE = False

try:
    from pymodbus.server import ModbusTcpServer
    from pymodbus.server import StartAsyncSerialServer
except ImportError:
    ModbusTcpServer = None
    StartAsyncSerialServer = None


class ServerProtocol(Enum):
    """Server protocol types."""
    TCP = "tcp"
    RTU = "rtu"
    ASCII = "ascii"


@dataclass
class ServerConfig:
    """Server configuration."""
    protocol: ServerProtocol
    # TCP config
    address: Optional[str] = None
    port: Optional[int] = None
    # Serial config  
    serial_port: Optional[str] = None
    baudrate: Optional[int] = None
    parity: Optional[str] = None
    stopbits: Optional[int] = None
    bytesize: Optional[int] = None
    

class AsyncModbusServer:
    """Pure asyncio Modbus server that can handle both TCP and Serial protocols."""
    
    def __init__(self, config: ServerConfig, live_slaves: Dict[int, Any]):
        self.config = config
        self.live_slaves = live_slaves
        self.server_task: Optional[asyncio.Task] = None
        self.stop_event = asyncio.Event()
        self.server_instance = None
        self.server_context: Optional[ModbusServerContext] = None
        
        # Function handler registry eliminates duplicate code
        self.function_registry = FunctionHandlerRegistry(global_logger)
        
        # Callbacks for status updates
        self.on_status: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[str], None]] = None
        self.on_frame: Optional[Callable[[str, bytes, str], None]] = None  # (direction, raw_frame, protocol)
        
    def set_callbacks(self, on_status: Callable[[str], None], on_error: Callable[[str], None],
                      on_frame: Optional[Callable[[str, bytes, str], None]] = None):
        """Set callback functions for status, error, and frame reporting."""
        self.on_status = on_status
        self.on_error = on_error
        self.on_frame = on_frame
        
    def _emit_status(self, message: str):
        """Emit status message."""
        global_logger.log(f"[AsyncModbusServer] {message}")
        if self.on_status:
            self.on_status(message)
            
    def _emit_error(self, message: str):
        """Emit error message."""
        global_logger.log(f"[AsyncModbusServer ERROR] {message}")
        if self.on_error:
            self.on_error(message)

    def _log_comm_frame(self, direction: str, frame: Optional[bytes], protocol: str = None):
        """Emit a normalized RX/TX log line and structured frame data."""
        if not frame:
            return
        try:
            hex_str = frame.hex().upper()
            global_logger.log(f"{direction} {hex_str}")
            if self.on_frame:
                proto = protocol or self.config.protocol.value.upper()
                self.on_frame(direction, bytes(frame), proto)
        except Exception:
            pass
    
    def _create_server_context(self) -> ModbusServerContext:
        """Create the Modbus server context from live slaves."""
        slaves = {}
        
        global_logger.log(f"Creating server context with {len(self.live_slaves)} slaves")
        global_logger.log(f"Live slaves unit IDs: {list(self.live_slaves.keys())}")
        
        for unit_id, slave_info in self.live_slaves.items():
            reg_map = slave_info["register_map"]
            
            self._emit_status(f"Setting up Unit {unit_id}")
            global_logger.log(f"Creating slave context for Unit ID {unit_id}")
            
            # Log register map contents
            for regtype in ['hr', 'ir', 'co', 'di']:
                entries = reg_map.all_entries(regtype)
                if entries:
                    addrs = [e.addr for e in entries]
                    values = [e.value for e in entries]
                    global_logger.log(f"  {regtype.upper()}: addrs={addrs}, values={values}")
            
            # Create slave context with register map datablocks
            slaves[unit_id] = ModbusSlaveContext(
                di=RegisterMapDataBlock(reg_map, 'di'),
                co=RegisterMapDataBlock(reg_map, 'co'),
                hr=RegisterMapDataBlock(reg_map, 'hr'),
                ir=RegisterMapDataBlock(reg_map, 'ir')
            )
            global_logger.log(f"Successfully created slave context for Unit ID {unit_id}")
        
        global_logger.log(f"Final slaves dict keys: {list(slaves.keys())}")
        context = ModbusServerContext(slaves=slaves, single=False)
        global_logger.log(f"Created ModbusServerContext with single={False}")
        
        return context

    # ---------------------- Utility: Modbus ASCII helpers ----------------------
    def _calculate_lrc(self, data: bytes) -> int:
        """Calculate Modbus ASCII LRC (delegates to shared utility)."""
        return calculate_lrc(data)

    def _decode_ascii_frame(self, line: bytes) -> Optional[bytes]:
        """Decode a Modbus ASCII frame line (: ... CRLF) into raw bytes payload without LRC.

        Returns payload bytes (UnitID + Function + Data), or None if invalid.
        """
        try:
            if not line:
                return None
            # Strip whitespace
            s = line
            # Accept both CRLF and LF
            if s.endswith(b"\r\n"):
                s = s[:-2]
            elif s.endswith(b"\n"):
                s = s[:-1]
            s = s.strip()
            if not s or s[0:1] != b":":
                return None
            # Remove leading ':'
            hex_part = s[1:]
            # Hex decode (uppercase/lowercase allowed)
            try:
                raw = bytes.fromhex(hex_part.decode('ascii'))
            except Exception:
                return None
            if len(raw) < 3:
                # Must contain at least unit, function and LRC
                return None
            # Split payload and LRC
            payload, recv_lrc = raw[:-1], raw[-1]
            calc_lrc = self._calculate_lrc(payload)
            if recv_lrc != calc_lrc:
                global_logger.log(f"ASCII LRC mismatch: recv={recv_lrc:02X} calc={calc_lrc:02X}")
                return None
            return payload
        except Exception:
            return None

    def _encode_ascii_frame(self, payload: bytes) -> bytes:
        """Encode payload (UnitID + Function + Data) to Modbus ASCII frame bytes (:..LRC\r\n)."""
        lrc = self._calculate_lrc(payload)
        framed = payload + bytes([lrc])
        hex_str = framed.hex().upper().encode('ascii')
        return b":" + hex_str + b"\r\n"
        
    def _parse_request_common(self, data: bytes, is_tcp: bool = False) -> Optional[ModbusRequest]:
        """Unified request parsing for both TCP and Serial protocols"""
        min_len = 6 if is_tcp else 8
        if len(data) < min_len:
            return None
            
        unit_id = data[0]
        function_code = data[1]
        start_addr = (data[2] << 8) | data[3]
        quantity = (data[4] << 8) | data[5]
        
        return ModbusRequest(unit_id, function_code, start_addr, quantity, data)
        
    def _get_slave_context(self, unit_id: int):
        """Get slave context with fallback methods (will be extracted to utility later)"""
        if self.server_context is None:
            self.server_context = self._create_server_context()
        
        context = self.server_context
        
        # Try multiple access methods (simplified from original duplication)
        access_methods = [
            lambda: context[unit_id],
            lambda: context.slaves[unit_id] if hasattr(context, 'slaves') else None,
            lambda: context.slaves()[unit_id] if hasattr(context, 'slaves') and callable(context.slaves) else None,
            lambda: context.getSlaveContext(unit_id) if hasattr(context, 'getSlaveContext') else None
        ]
        
        for method in access_methods:
            try:
                slave_context = method()
                if slave_context is not None:
                    return slave_context
            except (KeyError, AttributeError, TypeError):
                continue
                
        global_logger.warning(f"Could not find slave context for unit {unit_id}")
        return None
        
    def _build_final_response(self, response, is_tcp: bool = False) -> bytes:
        """Unified response building with optional CRC for serial protocols"""
        if hasattr(response, 'unit_id'):
            # ModbusResponse object from function handler
            response_bytes = bytes([response.unit_id, response.function_code]) + response.data
        else:
            # Raw bytes (for exception responses)
            response_bytes = response
            
        if not is_tcp and hasattr(response, 'needs_crc') and response.needs_crc:
            # Add CRC for serial protocols
            response_array = bytearray(response_bytes)
            crc = self._calculate_crc16(response_array)
            response_array.extend([crc & 0xFF, (crc >> 8) & 0xFF])
            return bytes(response_array)
            
        return response_bytes
    
    def refresh_server_context(self):
        """Refresh the server context with current register data."""
        self._emit_status("Refreshing server context with updated register data")
        self.server_context = self._create_server_context()
    
    async def start_tcp_server(self) -> None:
        """Start async TCP server with custom request logging."""
        self.server_context = self._create_server_context()
        
        try:
            self._emit_status(f"Starting TCP server on {self.config.address}:{self.config.port}")
            
            # Start custom TCP server with logging
            await self._run_async_tcp_server()
            
        except asyncio.CancelledError:
            self._emit_status("TCP server cancelled")
            raise
        except Exception as e:
            self._emit_error(f"TCP server error: {e}")
            raise
            
    async def _run_async_tcp_server(self):
        """Run custom async TCP server with request logging."""
        server = None
        try:
            # Create TCP server socket
            server = await asyncio.start_server(
                self._handle_tcp_client,
                self.config.address,
                self.config.port
            )
            # Track instance for controlled shutdown
            self.server_instance = server
            
            # Emit success status
            self._emit_status(f"TCP server started successfully on {self.config.address}:{self.config.port}")
            
            # Serve clients until cancelled
            async with server:
                await server.serve_forever()
                
        except Exception as e:
            self._emit_error(f"TCP server error: {e}")
            raise
        finally:
            if server:
                server.close()
                await server.wait_closed()
                # Clear reference after closing
                if self.server_instance is server:
                    self.server_instance = None
                
    async def _handle_tcp_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle individual TCP client connections."""
        client_address = writer.get_extra_info('peername')
        global_logger.log(f"TCP client connected from {client_address}")
        
        try:
            while not self.stop_event.is_set():
                try:
                    # Read Modbus TCP frame
                    # TCP frame: [Transaction ID][Protocol ID][Length][Unit ID][Function Code][Data...]
                    header = await asyncio.wait_for(reader.read(6), timeout=0.1)
                    if not header or len(header) != 6:
                        if header:  # Only log if we got partial data
                            global_logger.log("TCP: Incomplete header received")
                        break
                    
                    # Parse MBAP header
                    transaction_id = (header[0] << 8) | header[1]
                    protocol_id = (header[2] << 8) | header[3]  
                    length = (header[4] << 8) | header[5]
                    
                    if protocol_id != 0:  # Should be 0 for Modbus
                        global_logger.log(f"TCP: Invalid protocol ID {protocol_id}")
                        break
                        
                    # Read the PDU (Protocol Data Unit)
                    pdu_data = await asyncio.wait_for(reader.read(length), timeout=0.1)
                    if len(pdu_data) != length:
                        global_logger.log("TCP: Incomplete PDU received")
                        break
                    
                    # Log the full frame
                    full_frame = header + pdu_data
                    global_logger.log(f"Received Modbus TCP request: {full_frame.hex()}")
                    self._log_comm_frame("RX", full_frame, "TCP")

                    # Process the PDU part (unit_id + function_code + data)
                    if len(pdu_data) >= 2:
                        unit_id = pdu_data[0]
                        function_code = pdu_data[1]
                        global_logger.log(f"TCP Unit ID: {unit_id}, Function Code: {function_code}")

                        # Process request using our existing logic (but adapt for TCP)
                        response_pdu = await self._process_tcp_request(pdu_data)

                        if response_pdu:
                            # Build MBAP response header
                            response_length = len(response_pdu)
                            response_header = bytearray([
                                (transaction_id >> 8) & 0xFF, transaction_id & 0xFF,  # Transaction ID
                                0, 0,  # Protocol ID (0 for Modbus)
                                (response_length >> 8) & 0xFF, response_length & 0xFF  # Length
                            ])

                            response_frame = bytes(response_header) + response_pdu
                            global_logger.log(f"Sending TCP response: {response_frame.hex()}")
                            self._log_comm_frame("TX", response_frame, "TCP")
                            
                            writer.write(response_frame)
                            await writer.drain()
                    
                except asyncio.TimeoutError:
                    # Timeout allows checking stop_event
                    continue
                except asyncio.CancelledError:
                    break
                    
        except Exception as e:
            global_logger.log(f"TCP client error: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
                global_logger.log(f"TCP client {client_address} disconnected")
            except Exception as e:
                global_logger.log(f"TCP client cleanup error: {e}")
                
    async def _process_tcp_request(self, pdu_data: bytes) -> Optional[bytes]:
        """Process TCP Modbus request (PDU only, no CRC)."""
        try:
            if len(pdu_data) < 2:
                return None
                
            unit_id = pdu_data[0]
            function_code = pdu_data[1]
            
            # Use current server context (refresh if needed)
            if self.server_context is None:
                self.server_context = self._create_server_context()
            
            context = self.server_context
            
            # Get slave context using same logic as serial
            try:
                slave_context = None
                
                # Method 1: Direct access with unit_id (ModbusServerContext.__getitem__)
                try:
                    slave_context = context[unit_id]
                    global_logger.log(f"TCP: Got slave context via context[{unit_id}]: {type(slave_context)}")
                except (KeyError, AttributeError, TypeError) as e:
                    global_logger.log(f"TCP Method 1 failed: {e}")
                
                # Method 2: Access via slaves dict/attribute
                if slave_context is None:
                    try:
                        if hasattr(context, 'slaves') and hasattr(context.slaves, '__getitem__'):
                            slave_context = context.slaves[unit_id]
                            global_logger.log(f"TCP: Got slave context via slaves[{unit_id}]: {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"TCP Method 2 failed: {e}")
                        
                # Method 3: Try accessing slaves as method then subscript
                if slave_context is None:
                    try:
                        if hasattr(context, 'slaves') and hasattr(context.slaves, '__call__'):
                            slaves_dict = context.slaves()
                            if hasattr(slaves_dict, '__getitem__'):
                                slave_context = slaves_dict[unit_id]
                                global_logger.log(f"TCP: Got slave context via slaves()[{unit_id}]: {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"TCP Method 3 failed: {e}")
                
                # Method 4: Try getSlaveContext method if available
                if slave_context is None:
                    try:
                        if hasattr(context, 'getSlaveContext'):
                            slave_context = context.getSlaveContext(unit_id)
                            global_logger.log(f"TCP: Got slave context via getSlaveContext({unit_id}): {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"TCP Method 4 failed: {e}")
                        
                if slave_context is None:
                    global_logger.log(f"TCP: Could not find slave context for unit {unit_id}")
                    
                    # Debug: Show available units/slaves
                    try:
                        if hasattr(context, 'slaves'):
                            if hasattr(context.slaves, '__call__'):
                                slaves_result = context.slaves()
                                global_logger.log(f"TCP context.slaves() returned: {type(slaves_result)}")
                                if hasattr(slaves_result, 'keys'):
                                    global_logger.log(f"TCP Available slave unit IDs: {list(slaves_result.keys())}")
                    except Exception as debug_e:
                        global_logger.log(f"TCP Debug failed: {debug_e}")
                    
                    return self._build_tcp_exception_response(unit_id, function_code, 0x0B)  # Gateway target failed
                    
            except Exception as e:
                global_logger.log(f"TCP: Error accessing slave context: {e}")
                return None
            
            # Handle Read Coils (0x01)
            if function_code == 0x01:
                if len(pdu_data) < 6:
                    return self._build_tcp_exception_response(unit_id, function_code, 0x03)  # Illegal data value
                    
                start_addr = (pdu_data[2] << 8) | pdu_data[3]
                quantity = (pdu_data[4] << 8) | pdu_data[5]
                
                global_logger.log(f"TCP Read Coils: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(1, addr, 1)[0]  # 1 = coils
                        values.append(value)
                    
                    # Build bit-packed response
                    byte_count = (quantity + 7) // 8  # Pack 8 bits per byte
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    # Pack bits into bytes
                    for byte_idx in range(byte_count):
                        byte_value = 0
                        for bit_idx in range(8):
                            value_idx = byte_idx * 8 + bit_idx
                            if value_idx < len(values) and values[value_idx]:
                                byte_value |= (1 << bit_idx)
                        response.append(byte_value)
                    
                    return bytes(response)
                    
                except Exception as e:
                    global_logger.log(f"TCP: Error reading coils: {e}")
                    return self._build_tcp_exception_response(unit_id, function_code, 0x02)
            
            # Handle Read Holding Registers (0x03)
            elif function_code == 0x03:
                if len(pdu_data) < 6:
                    return self._build_tcp_exception_response(unit_id, function_code, 0x03)  # Illegal data value
                    
                start_addr = (pdu_data[2] << 8) | pdu_data[3]
                quantity = (pdu_data[4] << 8) | pdu_data[5]
                
                global_logger.log(f"TCP Read Holding Registers: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(3, addr, 1)[0]
                        values.append(value)
                    
                    # Build response
                    byte_count = quantity * 2
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    for value in values:
                        response.append((value >> 8) & 0xFF)
                        response.append(value & 0xFF)
                    
                    return bytes(response)
                    
                except Exception as e:
                    global_logger.log(f"TCP: Error reading holding registers: {e}")
                    return self._build_tcp_exception_response(unit_id, function_code, 0x02)
            
            # Handle Read Discrete Inputs (0x02)
            elif function_code == 0x02:
                if len(pdu_data) < 6:
                    return self._build_tcp_exception_response(unit_id, function_code, 0x03)
                    
                start_addr = (pdu_data[2] << 8) | pdu_data[3]
                quantity = (pdu_data[4] << 8) | pdu_data[5]
                
                global_logger.log(f"TCP Read Discrete Inputs: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(2, addr, 1)[0]  # 2 = discrete inputs
                        values.append(value)
                    
                    # Build bit-packed response
                    byte_count = (quantity + 7) // 8  # Pack 8 bits per byte
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    # Pack bits into bytes
                    for byte_idx in range(byte_count):
                        byte_value = 0
                        for bit_idx in range(8):
                            value_idx = byte_idx * 8 + bit_idx
                            if value_idx < len(values) and values[value_idx]:
                                byte_value |= (1 << bit_idx)
                        response.append(byte_value)
                    
                    return bytes(response)
                    
                except Exception as e:
                    global_logger.log(f"TCP: Error reading discrete inputs: {e}")
                    return self._build_tcp_exception_response(unit_id, function_code, 0x02)
            
            # Handle Read Input Registers (0x04)
            elif function_code == 0x04:
                if len(pdu_data) < 6:
                    return self._build_tcp_exception_response(unit_id, function_code, 0x03)
                    
                start_addr = (pdu_data[2] << 8) | pdu_data[3]
                quantity = (pdu_data[4] << 8) | pdu_data[5]
                
                global_logger.log(f"TCP Read Input Registers: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(4, addr, 1)[0]
                        values.append(value)
                    
                    byte_count = quantity * 2
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    for value in values:
                        response.append((value >> 8) & 0xFF)
                        response.append(value & 0xFF)
                    
                    return bytes(response)
                    
                except Exception as e:
                    global_logger.log(f"TCP: Error reading input registers: {e}")
                    return self._build_tcp_exception_response(unit_id, function_code, 0x02)
            
            else:
                global_logger.log(f"TCP: Unsupported function code: {function_code}")
                return self._build_tcp_exception_response(unit_id, function_code, 0x01)
                
        except Exception as e:
            global_logger.log(f"TCP request processing error: {e}")
            return None
    
    def _build_tcp_exception_response(self, unit_id: int, function_code: int, exception_code: int) -> bytes:
        """Build a TCP Modbus exception response (no CRC needed for TCP)."""
        return bytes([unit_id, function_code | 0x80, exception_code])
                    
    async def start_serial_server(self) -> None:
        """Start async serial server with proper cancellation support."""
        if not SERIAL_ASYNCIO_AVAILABLE:
            self._emit_error("pyserial-asyncio not available - falling back to synchronous mode")
            # Fall back to old behavior temporarily
            raise RuntimeError("pyserial-asyncio required for async serial servers")
        
        self.server_context = self._create_server_context()
        context = self.server_context
        
        try:
            server_desc = f"{self.config.protocol.value.upper()} on {self.config.serial_port} @ {self.config.baudrate}"
            self._emit_status(f"Starting {server_desc}")
            
            # Create async serial server - this is the key difference
            # We'll implement our own async serial server loop
            await self._run_async_serial_server(context)
            
        except asyncio.CancelledError:
            self._emit_status("Serial server cancelled")
            raise
        except Exception as e:
            self._emit_error(f"Serial server error: {e}")
            raise
            
    async def _run_async_serial_server(self, context: ModbusServerContext) -> None:
        """Run an async serial server that can be cancelled."""
        
        # Open serial connection asynchronously
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=self.config.serial_port,
                baudrate=self.config.baudrate,
                parity=self.config.parity or 'N',
                stopbits=self.config.stopbits or 1,
                bytesize=self.config.bytesize or 8,
                timeout=1.0  # Important: timeout for cancellation
            )
            
            # Emit success status - this means the serial port opened successfully
            server_desc = f"{self.config.protocol.value.upper()} on {self.config.serial_port} @ {self.config.baudrate}"
            self._emit_status(f"Serial server started successfully: {server_desc}")
            
            # Main server loop - this is cancellable
            # Internal buffer for ASCII line mode
            ascii_line_mode = (self.config.protocol == ServerProtocol.ASCII)
            while not self.stop_event.is_set():
                try:
                    if ascii_line_mode:
                        # Read one ASCII frame terminated by LF (CRLF tolerated)
                        try:
                            line = await asyncio.wait_for(reader.readuntil(b"\n"), timeout=0.1)
                        except (asyncio.IncompleteReadError, asyncio.TimeoutError):
                            # Timeout or partial read: loop back to check stop_event
                            continue
                        if not line:
                            continue
                        global_logger.log(f"Received Modbus ASCII line: {line.strip()}")
                        pdu = self._decode_ascii_frame(line)
                        if not pdu:
                            # Invalid frame; skip
                            continue
                        self._log_comm_frame("RX", pdu, "ASCII")
                        # Reuse TCP PDU processor to get PDU response (unit+fn+data)
                        response_pdu = await self._process_tcp_request(pdu)
                        if response_pdu:
                            frame = self._encode_ascii_frame(response_pdu)
                            global_logger.log(f"Sending ASCII response: {frame.strip()}")
                            self._log_comm_frame("TX", response_pdu, "ASCII")
                            writer.write(frame)
                            await writer.drain()
                    else:
                        # RTU binary mode
                        # Wait for data with timeout to allow cancellation
                        data = await asyncio.wait_for(reader.read(256), timeout=0.1)
                        if data:
                            self._log_comm_frame("RX", data, "RTU")
                            # Process Modbus request using current context
                            response = await self._process_modbus_request(data)
                            if response:
                                self._log_comm_frame("TX", response, "RTU")
                                writer.write(response)
                                await writer.drain()
                except asyncio.TimeoutError:
                    # Timeout is expected - allows checking stop_event
                    continue
                except asyncio.CancelledError:
                    self._emit_status("Serial server loop cancelled")
                    break
                    
        except Exception as e:
            self._emit_error(f"Serial connection error: {e}")
            raise
        finally:
            # Clean up serial connection
            try:
                if 'writer' in locals():
                    writer.close()
                    await writer.wait_closed()
            except Exception as e:
                self._emit_error(f"Serial cleanup error: {e}")
    
    async def _process_modbus_request(self, data: bytes) -> Optional[bytes]:
        """Process a Modbus request and return response."""
        try:
            global_logger.log(f"Received Modbus request: {data.hex()}")
            
            # Manual parsing for RTU frame: 010300000008440c
            # Format: [Unit ID][Function Code][Start Address H][Start Address L][Quantity H][Quantity L][CRC L][CRC H]
            if len(data) < 8:
                global_logger.log("Frame too short")
                return None
                
            unit_id = data[0]
            function_code = data[1]
            
            global_logger.log(f"Unit ID: {unit_id}, Function Code: {function_code}")
            
            # Use current server context (refresh if needed)
            if self.server_context is None:
                self.server_context = self._create_server_context()
            
            context = self.server_context
            
            # Check if we have this unit
            try:
                global_logger.log(f"Context type: {type(context)}, slaves type: {type(context.slaves)}")
                
                # Try different ways to access the slave context
                slave_context = None
                
                # Method 1: Direct access with unit_id (ModbusServerContext.__getitem__)
                try:
                    slave_context = context[unit_id]
                    global_logger.log(f"Got slave context via context[{unit_id}]: {type(slave_context)}")
                except (KeyError, AttributeError, TypeError) as e:
                    global_logger.log(f"Method 1 failed: {e}")
                
                # Method 2: Access via slaves dict/attribute
                if slave_context is None:
                    try:
                        if hasattr(context, 'slaves') and hasattr(context.slaves, '__getitem__'):
                            slave_context = context.slaves[unit_id]
                            global_logger.log(f"Got slave context via slaves[{unit_id}]: {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"Method 2 failed: {e}")
                        
                # Method 3: Try accessing slaves as method then subscript
                if slave_context is None:
                    try:
                        if hasattr(context, 'slaves') and hasattr(context.slaves, '__call__'):
                            # slaves() might return a dict or something subscriptable
                            slaves_dict = context.slaves()
                            if hasattr(slaves_dict, '__getitem__'):
                                slave_context = slaves_dict[unit_id]
                                global_logger.log(f"Got slave context via slaves()[{unit_id}]: {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"Method 3 failed: {e}")
                
                # Method 4: Try getSlaveContext method if available
                if slave_context is None:
                    try:
                        if hasattr(context, 'getSlaveContext'):
                            slave_context = context.getSlaveContext(unit_id)
                            global_logger.log(f"Got slave context via getSlaveContext({unit_id}): {type(slave_context)}")
                    except (KeyError, AttributeError, TypeError) as e:
                        global_logger.log(f"Method 4 failed: {e}")
                
                # Method 5: Debug - show what's actually available
                if slave_context is None:
                    global_logger.log(f"Could not find slave context for unit {unit_id}")
                    
                    # Debug: Show available units/slaves
                    try:
                        if hasattr(context, 'slaves'):
                            if hasattr(context.slaves, '__call__'):
                                slaves_result = context.slaves()
                                global_logger.log(f"context.slaves() returned: {type(slaves_result)} - {slaves_result}")
                                if hasattr(slaves_result, 'keys'):
                                    global_logger.log(f"Available slave unit IDs: {list(slaves_result.keys())}")
                            elif hasattr(context.slaves, 'keys'):
                                global_logger.log(f"Available slave unit IDs: {list(context.slaves.keys())}")
                    except Exception as debug_e:
                        global_logger.log(f"Debug failed: {debug_e}")
                    
                    global_logger.log(f"Available methods on context: {[attr for attr in dir(context) if not attr.startswith('_')]}")
                    return None
                    
            except Exception as e:
                global_logger.log(f"Error accessing slave context for unit {unit_id}: {e}")
                return None
            
            # Handle Read Coils (0x01)
            if function_code == 0x01:
                start_addr = (data[2] << 8) | data[3]  # Big endian
                quantity = (data[4] << 8) | data[5]    # Big endian
                
                global_logger.log(f"Read Coils: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(1, addr, 1)[0]  # 1 = coils
                        values.append(value)
                    
                    # Build bit-packed response
                    byte_count = (quantity + 7) // 8  # Pack 8 bits per byte
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    # Pack bits into bytes
                    for byte_idx in range(byte_count):
                        byte_value = 0
                        for bit_idx in range(8):
                            value_idx = byte_idx * 8 + bit_idx
                            if value_idx < len(values) and values[value_idx]:
                                byte_value |= (1 << bit_idx)
                        response.append(byte_value)
                    
                    # Calculate CRC16 for RTU
                    crc = self._calculate_crc16(response)
                    response.append(crc & 0xFF)        # CRC low byte
                    response.append((crc >> 8) & 0xFF) # CRC high byte
                    
                    response_bytes = bytes(response)
                    global_logger.log(f"Sending Coils response: {response_bytes.hex()}")
                    return response_bytes
                    
                except Exception as e:
                    global_logger.log(f"Error reading coils: {e}")
                    # Send exception response
                    return self._build_exception_response(unit_id, function_code, 0x02)  # Illegal data address
            
            # Handle Read Holding Registers (0x03) - your specific case
            elif function_code == 0x03:
                start_addr = (data[2] << 8) | data[3]  # Big endian
                quantity = (data[4] << 8) | data[5]    # Big endian
                
                global_logger.log(f"Read Holding Registers: start={start_addr}, count={quantity}")
                
                try:
                    # Read values from the slave context
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(3, addr, 1)[0]  # 3 = holding registers
                        values.append(value)
                    
                    # Build response: [Unit ID][Function Code][Byte Count][Data...][CRC]
                    byte_count = quantity * 2  # 2 bytes per register
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    # Add register values (big endian, 16-bit each)
                    for value in values:
                        response.append((value >> 8) & 0xFF)  # High byte
                        response.append(value & 0xFF)         # Low byte
                    
                    # Calculate CRC16 for RTU
                    crc = self._calculate_crc16(response)
                    response.append(crc & 0xFF)        # CRC low byte
                    response.append((crc >> 8) & 0xFF) # CRC high byte
                    
                    response_bytes = bytes(response)
                    global_logger.log(f"Sending response: {response_bytes.hex()}")
                    return response_bytes
                    
                except Exception as e:
                    global_logger.log(f"Error reading holding registers: {e}")
                    # Send exception response
                    return self._build_exception_response(unit_id, function_code, 0x02)  # Illegal data address
            
            # Handle Read Discrete Inputs (0x02)
            elif function_code == 0x02:
                start_addr = (data[2] << 8) | data[3]
                quantity = (data[4] << 8) | data[5]
                
                global_logger.log(f"Read Discrete Inputs: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(2, addr, 1)[0]  # 2 = discrete inputs
                        values.append(value)
                    
                    # Build bit-packed response
                    byte_count = (quantity + 7) // 8  # Pack 8 bits per byte
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    # Pack bits into bytes
                    for byte_idx in range(byte_count):
                        byte_value = 0
                        for bit_idx in range(8):
                            value_idx = byte_idx * 8 + bit_idx
                            if value_idx < len(values) and values[value_idx]:
                                byte_value |= (1 << bit_idx)
                        response.append(byte_value)
                    
                    # Calculate CRC16 for RTU
                    crc = self._calculate_crc16(response)
                    response.append(crc & 0xFF)        # CRC low byte
                    response.append((crc >> 8) & 0xFF) # CRC high byte
                    
                    response_bytes = bytes(response)
                    global_logger.log(f"Sending DI response: {response_bytes.hex()}")
                    return response_bytes
                    
                except Exception as e:
                    global_logger.log(f"Error reading discrete inputs: {e}")
                    return self._build_exception_response(unit_id, function_code, 0x02)
            
            # Handle Read Input Registers (0x04)
            elif function_code == 0x04:
                start_addr = (data[2] << 8) | data[3]
                quantity = (data[4] << 8) | data[5]
                
                global_logger.log(f"Read Input Registers: start={start_addr}, count={quantity}")
                
                try:
                    values = []
                    for i in range(quantity):
                        addr = start_addr + i
                        value = slave_context.getValues(4, addr, 1)[0]  # 4 = input registers
                        values.append(value)
                    
                    byte_count = quantity * 2
                    response = bytearray([unit_id, function_code, byte_count])
                    
                    for value in values:
                        response.append((value >> 8) & 0xFF)
                        response.append(value & 0xFF)
                    
                    crc = self._calculate_crc16(response)
                    response.append(crc & 0xFF)
                    response.append((crc >> 8) & 0xFF)
                    
                    response_bytes = bytes(response)
                    global_logger.log(f"Sending response: {response_bytes.hex()}")
                    return response_bytes
                    
                except Exception as e:
                    global_logger.log(f"Error reading input registers: {e}")
                    return self._build_exception_response(unit_id, function_code, 0x02)
            
            else:
                global_logger.log(f"Unsupported function code: {function_code}")
                return self._build_exception_response(unit_id, function_code, 0x01)  # Illegal function
                
        except Exception as e:
            self._emit_error(f"Request processing error: {e}")
            global_logger.log(f"Request processing error details: {str(e)}")
            return None
    
    def _calculate_crc16(self, data: bytearray) -> int:
        """Calculate CRC16 for Modbus RTU (delegates to shared utility)."""
        return calculate_crc16(bytes(data))
    
    def _build_exception_response(self, unit_id: int, function_code: int, exception_code: int) -> bytes:
        """Build a Modbus exception response."""
        response = bytearray([unit_id, function_code | 0x80, exception_code])
        crc = self._calculate_crc16(response)
        response.append(crc & 0xFF)
        response.append((crc >> 8) & 0xFF)
        return bytes(response)
    
    async def start_async(self) -> None:
        """Start the appropriate server based on protocol."""
        self.stop_event.clear()
        
        try:
            if self.config.protocol == ServerProtocol.TCP:
                await self.start_tcp_server()
            else:  # RTU or ASCII
                await self.start_serial_server()
        except asyncio.CancelledError:
            self._emit_status("Server start cancelled")
            raise
    
    async def stop_async(self) -> None:
        """Stop the server gracefully."""
        self._emit_status("Stopping server...")
        
        # Signal stop
        self.stop_event.set()
        
        # Cancel server task if running
        if self.server_task and not self.server_task.done():
            self.server_task.cancel()
            try:
                await self.server_task
            except asyncio.CancelledError:
                pass
                
        # Cleanup server instance
        if self.server_instance:
            try:
                # Try to close sockets/streams gracefully
                close = getattr(self.server_instance, 'close', None)
                if callable(close):
                    self.server_instance.close()
                wait_closed = getattr(self.server_instance, 'wait_closed', None)
                if callable(wait_closed):
                    await self.server_instance.wait_closed()
            except Exception as e:
                self._emit_error(f"Server shutdown error: {e}")
            finally:
                self.server_instance = None
                
        self._emit_status("Server stopped")
    
    def start(self) -> asyncio.Task:
        """Start the server and return the task."""
        if self.server_task and not self.server_task.done():
            raise RuntimeError("Server is already running")
            
        self.server_task = asyncio.create_task(self.start_async())
        return self.server_task
        
    async def stop(self) -> None:
        """Stop the server."""
        await self.stop_async()
        
    def is_running(self) -> bool:
        """Check if server is running."""
        if self.server_task is None:
            return False
        if self.server_task.done():
            # Check if task completed successfully or failed
            try:
                self.server_task.result()  # Will raise exception if failed
                return False  # Completed successfully but no longer running
            except Exception:
                return False  # Failed, definitely not running
        return True  # Task is still running
