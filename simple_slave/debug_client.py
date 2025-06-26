from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("127.0.0.1", port=55000)
client.connect()
rr = client.read_holding_registers(address=0, count=9, slave=1)
print(rr.registers if hasattr(rr, 'registers') else rr)
client.close()