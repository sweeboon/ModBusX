from PyQt5.QtCore import QThread, pyqtSignal
import asyncio
from pymodbus.server import ModbusTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock
from modbusx.logger import global_logger

class MultiUnitModbusServerThread(QThread):
    status_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, port, unit_definitions, parent=None):
        super().__init__(parent)
        self.port = port
        self.unit_definitions = unit_definitions
        self.loop = None
        self._stop_event = None
        self._server = None

    async def start_server(self):
        slaves = {}
        for unit_id, dr in self.unit_definitions.items():
            blocks = {}
            for regtype in ('hr', 'ir', 'co', 'di'):
                if regtype in dr:
                    start, arr = dr[regtype]
                    if arr and len(arr):
                        blocks[regtype] = ModbusSequentialDataBlock(start, arr)
            slaves[unit_id] = ModbusSlaveContext(**blocks)
        
        context = ModbusServerContext(slaves=slaves, single=False)
        self.status_signal.emit(
            f"Starting server on 127.0.0.1:{self.port} units={list(self.unit_definitions.keys())}"
        )
        global_logger.log(
            f"Starting Modbus TCP server on port {self.port}, units={list(self.unit_definitions.keys())}"
        )
        try:
            self._server = ModbusTcpServer(
                context,
                address=("127.0.0.1", self.port),
            )
            await self._server.serve_forever()
        except Exception as e:
            global_logger.log(f"[Modbus Thread ERROR] {e}")
            self.error_signal.emit(str(e))
        finally:
            if self._server:
                try:
                    await self._server.shutdown()
                except Exception as e:
                    global_logger.log(f"[Modbus Thread Shutdown ERROR] {e}")
                    self.error_signal.emit(f"Error on shutdown: {e}")
                self._server = None
            self.status_signal.emit("Server task exit.")

    def run(self):
        try:
            global_logger.log(f"Modbus Thread - RUN, port={self.port}")
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._stop_event = asyncio.Event()
            self.loop.run_until_complete(self.start_server())
        except Exception as e:
            global_logger.log(f"[Modbus Thread RUN ERROR] {e}")
            self.error_signal.emit(str(e))
        finally:
            self.loop.close()
            self.loop = None
            self._stop_event = None

    def stop(self):
        if self.loop and not self.loop.is_closed() and self._server:
            global_logger.log(f"Stopping Modbus TCP server on port {self.port}")
            self.loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self._server.shutdown())
            )