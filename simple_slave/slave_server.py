import asyncio
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext, ModbusSequentialDataBlock

async def main():
    store = ModbusSlaveContext(
        hr=ModbusSequentialDataBlock(0, [1234]*10),  # Holding registers initialized to 1234
        ir=ModbusSequentialDataBlock(0, [5678]*10),  # Input registers initialized to 5678
    )
    context = ModbusServerContext(slaves={1: store}, single=False)
    print("Starting Modbus TCP Async Slave on 127.0.0.1:55000 (unit=1)")
    await StartAsyncTcpServer(context, address=("127.0.0.1", 55000))

if __name__ == "__main__":
    asyncio.run(main())