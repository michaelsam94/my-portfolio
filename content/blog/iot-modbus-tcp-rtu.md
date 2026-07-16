---
title: "Modbus TCP and RTU Integration"
slug: "iot-modbus-tcp-rtu"
description: "Integrate Modbus TCP and RTU devices into IoT systems: register maps, polling strategies, pymodbus, serial gateway setup, and common industrial integration patterns."
datePublished: "2025-08-21"
dateModified: "2025-08-21"
tags: ["IoT", "Embedded", "Architecture", "Backend"]
keywords: "Modbus TCP, Modbus RTU, pymodbus, industrial IoT integration, Modbus register map, RS485 Modbus, PLC integration"
faq:
  - q: "What is the difference between Modbus RTU and Modbus TCP?"
    a: "Modbus RTU runs over serial (RS-485/RS-232) with binary framing and CRC error checking — common on PLCs, energy meters, and legacy devices. Modbus TCP wraps the same protocol in TCP/IP packets on port 502 — used by modern industrial Ethernet devices. The register addressing and function codes are identical; only the transport differs."
  - q: "What are Modbus function codes?"
    a: "Function codes define the operation: FC03 reads holding registers (read/write values), FC04 reads input registers (read-only), FC01 reads coils (digital outputs), FC02 reads discrete inputs (digital inputs), FC06 writes a single register, FC16 writes multiple registers. Most IoT integrations use FC03 for sensor data and FC06/FC16 for commands."
  - q: "How do I connect Modbus RTU devices to a cloud IoT platform?"
    a: "Use a serial-to-Ethernet gateway (Moxa NPort, Advantech ADAM) that exposes RTU devices as Modbus TCP slaves. Or connect a USB-RS485 adapter to an edge gateway running pymodbus, poll RTU devices locally, and publish to MQTT. Never expose serial Modbus directly to the internet."
---

Modbus is 40 years old and everywhere. Every PLC, energy meter, VFD, and building controller in an industrial facility speaks it. It doesn't do discovery, security, or metadata — it's a table of numbered registers you read and write. That simplicity is why it outlived a dozen "better" protocols. Your IoT platform probably speaks MQTT or HTTP. Something in the middle has to poll register 40001 every 10 seconds and turn it into `{"temperature": 23.5}`. That something is your Modbus integration.

## Protocol basics

Modbus address space:

| Type | Address range | Function codes | Access |
|------|--------------|----------------|--------|
| Coils | 00001-09999 | FC01 (read), FC05/FC15 (write) | Read/Write |
| Discrete Inputs | 10001-19999 | FC02 | Read only |
| Input Registers | 30001-39999 | FC04 | Read only |
| Holding Registers | 40001-49999 | FC03 (read), FC06/FC16 (write) | Read/Write |

Note: pymodbus and most libraries use 0-based addressing. Register 40001 = address 0 in code.

## Modbus RTU over RS-485

Physical layer:
- RS-485 bus: A+, B-, GND
- Up to 32 devices (without repeaters), 1200m max cable length
- Termination resistors (120Ω) at both bus ends
- Baud rate: 9600 (common default), 19200, 115200

```python
from pymodbus.client import ModbusSerialClient

client = ModbusSerialClient(
    port="/dev/ttyUSB0",
    baudrate=9600,
    parity="E",       # even parity (most common)
    stopbits=1,
    bytesize=8,
    timeout=1,
)

client.connect()

# Read holding register 0 (40001) from slave ID 1
result = client.read_holding_registers(address=0, count=1, slave=1)
if not result.isError():
    raw_value = result.registers[0]
    temperature = raw_value / 10.0  # scale factor from device manual
    print(f"Temperature: {temperature}°C")
```

Each device on the bus has a unique **slave ID** (1-247). The master polls them sequentially.

## Modbus TCP

Same protocol, TCP transport, port 502:

```python
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient("192.168.1.100", port=502)
client.connect()

result = client.read_holding_registers(address=0, count=10, slave=1)
registers = result.registers

# Read input registers (FC04, 30001+)
inputs = client.read_input_registers(address=0, count=5, slave=1)

# Write single register (FC06)
client.write_register(address=10, value=1500, slave=1)

# Write multiple registers (FC16)
client.write_registers(address=20, values=[100, 200, 300], slave=1)
```

Modbus TCP includes a 7-byte MBAP header (transaction ID, protocol ID, length, unit ID) before the standard Modbus PDU.

## Register map documentation

Every Modbus device needs a register map. Document it as configuration:

```yaml
# devices/energy_meter.yaml
device:
  name: "Main Energy Meter"
  slave_id: 1
  protocol: modbus_rtu
  port: /dev/ttyUSB0
  baudrate: 9600

registers:
  - name: voltage_l1
    address: 0        # 40001
    type: holding
    count: 1
    scale: 0.1
    unit: "V"
    function_code: 3

  - name: current_l1
    address: 6        # 40007
    type: holding
    count: 2          # 32-bit value across 2 registers
    scale: 0.001
    unit: "A"
    datatype: int32
    byte_order: big

  - name: total_energy
    address: 72       # 40073
    type: holding
    count: 2
    scale: 0.01
    unit: "kWh"
    datatype: uint32
```

## Polling engine

Production polling with error handling and retry:

```python
import asyncio
import yaml

class ModbusPoller:
    def __init__(self, device_config, client):
        self.config = device_config
        self.client = client
        self.last_values = {}

    async def poll(self):
        readings = {}
        for reg in self.config["registers"]:
            for attempt in range(3):
                try:
                    if reg["function_code"] == 3:
                        result = self.client.read_holding_registers(
                            reg["address"], reg["count"], slave=self.config["device"]["slave_id"]
                        )
                    elif reg["function_code"] == 4:
                        result = self.client.read_input_registers(
                            reg["address"], reg["count"], slave=self.config["device"]["slave_id"]
                        )

                    if result.isError():
                        raise ModbusException(str(result))

                    value = self._decode(result.registers, reg)
                    readings[reg["name"]] = {"value": value, "unit": reg["unit"]}
                    break
                except Exception as e:
                    if attempt == 2:
                        readings[reg["name"]] = {"value": None, "unit": reg["unit"], "error": str(e)}
                    await asyncio.sleep(0.5)

        self.last_values = readings
        return readings

    def _decode(self, registers, reg):
        raw = registers[0]
        if reg.get("count", 1) == 2:
            raw = (registers[0] << 16) | registers[1]
        return raw * reg.get("scale", 1.0)
```

## RTU-to-TCP gateway pattern

When devices are RTU but your IoT platform expects IP:

```
[PLC RTU slave 1] ──RS-485──┐
[Meter RTU slave 2] ────────┤── [Edge Gateway] ──MQTT──► Cloud
[VFD RTU slave 3] ──────────┘    (pymodbus polling)
```

The gateway polls each RTU slave sequentially (RS-485 is half-duplex), normalizes readings, and publishes to MQTT. Never put RS-485 on a shared bus with unrelated equipment without checking termination and grounding.

## Common pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| Timeout on every read | Wrong baud rate or parity | Match device manual exactly |
| Garbage values | Byte order mismatch | Try big-endian vs little-endian, word swap |
| Intermittent errors | Missing termination resistor | Add 120Ω at bus ends |
| Slow polling | Too many devices on one bus | Split buses, increase baud rate, reduce register count |
| Register off-by-one | 0-based vs 1-based addressing | Check if manual uses 40001 (1-based) or 0 (0-based) |

## Common production mistakes

Teams get modbus tcp rtu wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of modbus tcp rtu fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When modbus tcp rtu misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [pymodbus documentation](https://pymodbus.readthedocs.io/) — Python Modbus client and server library
- [Modbus Organization specification](https://modbus.org/specs.php) — official protocol specification (free download)
- [Simply Modbus — addressing guide](https://www.simplymodbus.ca/FAQ.htm) — addressing conventions and common confusions
- [Modbus RTU vs TCP (Real Time Automation)](https://www.rtautomation.com/modbus/) — practical integration guide
