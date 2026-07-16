---
title: "OPC UA for Industrial IoT"
slug: "iot-opc-ua-industrial"
description: "Integrate OPC UA into industrial IoT systems: address space, nodes, subscriptions, security modes, and connecting PLCs to cloud platforms."
datePublished: "2025-08-30"
dateModified: "2025-08-30"
tags: ["IoT", "Embedded", "Architecture", "Security"]
keywords: "OPC UA industrial IoT, OPC Unified Architecture, OPC UA client, OPC UA subscription, PLC integration, open62541, industrial protocol"
faq:
  - q: "What is OPC UA?"
    a: "OPC Unified Architecture is a platform-independent industrial communication protocol for exchanging data between PLCs, SCADA systems, MES, and cloud platforms. Unlike Modbus (flat register tables), OPC UA provides a structured address space with typed nodes, metadata, subscriptions, and built-in security (encryption, authentication, signing)."
  - q: "How is OPC UA different from Modbus?"
    a: "Modbus is a simple register read/write protocol with no metadata, security, or discovery. OPC UA provides a hierarchical address space (objects, variables, methods), self-describing data types, publish/subscribe for efficient updates, and mandatory security (SignAndEncrypt mode). OPC UA is the modern replacement for OPC Classic (DCOM-based)."
  - q: "What security modes does OPC UA support?"
    a: "Three message security modes: None (no encryption — dev only), Sign (integrity verification), SignAndEncrypt (integrity + confidentiality). Three security policies define algorithms: None, Basic256Sha256, Aes256_Sha256_RsaPss. Production must use SignAndEncrypt with Basic256Sha256 or stronger."
---

Modbus tells you that register 40007 contains the value 235. OPC UA tells you that `ns=2;s=Machine1.Temperature` is a Float measured in °C, last updated 200ms ago, with a valid range of -40 to 200, and it's part of the Machine1 object alongside Pressure and Status. That metadata is why OPC UA replaced OPC Classic in every major PLC vendor's roadmap. If you're connecting modern industrial equipment to a cloud IoT platform, OPC UA is the protocol you'll integrate.

## Address space model

OPC UA organizes data as a tree of nodes:

```
Root
├── Objects
│   ├── Machine1
│   │   ├── Temperature (Variable, Float, °C)
│   │   ├── Pressure (Variable, Float, bar)
│   │   ├── Status (Variable, String)
│   │   └── StartMachine (Method)
│   └── Machine2
│       └── ...
└── Types (data type definitions)
```

Node types:
- **Object** — container (like a folder)
- **Variable** — data value (sensor reading, setpoint)
- **Method** — callable function (start, stop, reset)
- **ObjectType** — template for objects

Each node has a **NodeId**: `ns=2;s=Machine1.Temperature` (namespace 2, string identifier).

## Reading data (Python asyncua)

```python
from asyncua import Client

async def read_machine_data():
    async with Client("opc.tcp://192.168.1.100:4840") as client:
        client.set_security_string("Basic256Sha256,SignAndEncrypt,cert.der,key.pem")

        temp = await client.get_node("ns=2;s=Machine1.Temperature")
        value = await temp.read_value()
        print(f"Temperature: {value}°C")

        # Browse address space
        objects = client.get_objects_node()
        machine1 = await objects.get_child("2:Machine1")
        children = await machine1.get_children()
        for child in children:
            name = await child.read_display_name()
            val = await child.read_value()
            print(f"  {name.Text}: {val}")
```

## Subscriptions (efficient updates)

Instead of polling, subscribe to value changes:

```python
from asyncua import Client, ua

class DataChangeHandler:
    def datachange_notification(self, node, val, data):
        print(f"Change: {node} = {val}")

async def subscribe():
    async with Client("opc.tcp://192.168.1.100:4840") as client:
        handler = DataChangeHandler()
        sub = await client.create_subscription(500, handler)  # 500ms publish interval

        temp_node = client.get_node("ns=2;s=Machine1.Temperature")
        pressure_node = client.get_node("ns=2;s=Machine1.Pressure")

        await sub.subscribe_data_change(temp_node)
        await sub.subscribe_data_change(pressure_node)

        await asyncio.sleep(3600)  # listen for 1 hour
```

The server publishes only when values change (with configurable deadband). Much more efficient than polling 1000 registers every second.

## Security configuration

Production OPC UA must use encryption:

```python
from asyncua import Client
from asyncua.crypto.security_policies import SecurityPolicyBasic256Sha256

async with Client("opc.tcp://plc.factory:4840") as client:
    await client.set_security(
        SecurityPolicyBasic256Sha256,
        certificate="client_cert.der",
        private_key="client_key.pem",
        server_certificate="server_cert.der",
    )
```

Security checklist:
- **SignAndEncrypt** mode on all connections
- **Basic256Sha256** minimum policy (Aes256 for new deployments)
- **Client certificates** — unique per gateway/consumer
- **Reject** anonymous and username/password without TLS
- **Firewall** — port 4840 only from known gateway IPs

## OPC UA to MQTT bridge

Edge gateway pattern for cloud connectivity:

```python
async def opcua_to_mqtt_bridge():
    async with Client(PLC_URL) as opcua_client:
        mqtt_client = mqtt.Client()
        mqtt_client.connect("mqtt.example.com", 8883)

        class BridgeHandler:
            def datachange_notification(self, node, val, data):
                node_id = str(node)
                topic = f"factory/opcua/{node_id.replace(':', '/').replace(';', '/')}"
                payload = json.dumps({"value": val, "timestamp": time.time()})
                mqtt_client.publish(topic, payload, qos=1)

        sub = await opcua_client.create_subscription(1000, BridgeHandler())
        # Subscribe to all variables under Machine1
        machine = opcua_client.get_node("ns=2;s=Machine1")
        for var in await machine.get_children(nodeclass=ua.NodeClass.Variable):
            await sub.subscribe_data_change(var)
```

## OPC UA vs MQTT Sparkplug B

| Feature | OPC UA | Sparkplug B |
|---------|--------|-------------|
| Discovery | Built-in (mDNS, LDS) | Birth certificates |
| Security | Built-in (certs, encryption) | Depends on MQTT TLS |
| Data model | Rich (objects, types, methods) | Flat metrics |
| Transport | TCP (binary) | MQTT (TCP) |
| Ecosystem | PLCs, SCADA, MES | IoT platforms, cloud |
| Complexity | Higher | Lower |

Use OPC UA at the PLC/SCADA edge. Convert to MQTT/Sparkplug for cloud if needed. Don't force PLCs to speak MQTT natively.

## Historical access and alarms

Beyond live subscriptions, OPC UA provides:

- **Historical reads** — query variable history over a time range from the server's built-in historian
- **Alarm and condition types** — standardized alarm states (Active, Acknowledged, Suppressed) with severity levels
- **Method calls** — invoke PLC functions (reset, start batch) with typed input/output arguments

```python
# Read historical temperature data
history = await client.read_history(
    node_id="ns=2;s=Machine1.Temperature",
    start=datetime(2025, 9, 1),
    end=datetime(2025, 9, 2),
)
```

If the PLC doesn't expose history natively, configure the edge gateway to log subscribed values locally and serve them via a companion OPC UA historian.

## Common production mistakes

Teams get opc ua industrial wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of opc ua industrial fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When opc ua industrial misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OPC Foundation specifications](https://opcfoundation.org/developer-tools/specifications-unified-architecture/) — official UA specs (Part 1-14)
- [asyncua Python library](https://github.com/FreeOpcUa/opcua-asyncio) — async OPC UA client and server
- [open62541 (C OPC UA stack)](https://www.open62541.org/) — open-source embedded OPC UA SDK
- [OPC UA security best practices (OPC Foundation)](https://reference.opcfoundation.org/Core/Part2/v105/docs/4.8) — security modes and policies
