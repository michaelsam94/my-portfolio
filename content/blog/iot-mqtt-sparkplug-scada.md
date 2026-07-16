---
title: "MQTT Sparkplug B for SCADA"
slug: "iot-mqtt-sparkplug-scada"
description: "Implement MQTT Sparkplug B for industrial SCADA: birth/death certificates, metric definitions, state management, and bridging PLCs to MQTT brokers."
datePublished: "2025-08-24"
dateModified: "2025-08-24"
tags: ["IoT", "Embedded", "Architecture", "Backend"]
keywords: "MQTT Sparkplug B, SCADA MQTT, Sparkplug B protocol, industrial MQTT, birth certificate MQTT, Eclipse Tahu, SCADA IoT integration"
faq:
  - q: "What is MQTT Sparkplug B?"
    a: "Sparkplug B is an open specification (Eclipse Tahu) that defines how industrial devices communicate over MQTT. It standardizes topic namespaces, payload encoding (Protobuf), device lifecycle (birth/death certificates), and metric definitions. It solves MQTT's ambiguity — without Sparkplug, every vendor defines topics differently."
  - q: "What are birth and death certificates in Sparkplug B?"
    a: "When a device (Node) or sensor (Device) comes online, it publishes a BIRTH message containing its metric definitions (name, datatype, alias). When it goes offline (gracefully or via MQTT Last Will), it publishes a DEATH message. Consumers use birth to learn what metrics exist and death to detect offline devices."
  - q: "How is Sparkplug B different from plain MQTT for SCADA?"
    a: "Plain MQTT has no standard for topic structure, payload format, or device state management. Sparkplug B defines all three: topics follow spBv1.0/GROUP/EDGE_NODE/..., payloads are Protobuf-encoded with typed metrics, and birth/death certificates provide device discovery and state tracking out of the box."
---

Plain MQTT in a SCADA context is chaos. One vendor publishes to `factory/line3/temp`, another to `sensors/Temperature_Line3`, a third sends JSON while the fourth sends CSV strings. Your dashboard integration team spends weeks mapping topics per vendor. Sparkplug B fixes this with a rigid topic namespace, Protobuf payloads, and birth/death lifecycle messages that tell you what metrics exist and when devices go offline. It's MQTT with rules — and industrial SCADA desperately needed rules.

## Topic namespace

```
spBv1.0/{group_id}/{message_type}/{edge_node_id}/{device_id}
```

Examples:

```
spBv1.0/FactoryA/NDATA/EdgeNode1/               ← node data (no device)
spBv1.0/FactoryA/NDATA/EdgeNode1/Device1/          ← device data
spBv1.0/FactoryA/NBIRTH/EdgeNode1/               ← node birth certificate
spBv1.0/FactoryA/DBIRTH/EdgeNode1/Device1/       ← device birth certificate
spBv1.0/FactoryA/NDEATH/EdgeNode1/               ← node death (LWT)
spBv1.0/FactoryA/NCMD/EdgeNode1/                 ← command to node
spBv1.0/FactoryA/DCMD/EdgeNode1/Device1/         ← command to device
```

Message types:
- **NBIRTH/DBIRTH** — birth certificates (metric definitions)
- **NDEATH/DDEATH** — death certificates (offline notification)
- **NDATA/DDATA** — metric data updates
- **NCMD/DCMD** — commands to node/device
- **NRECORD/DRECORD** — historical data records

## Birth certificate

When a device comes online, it publishes its metric catalog:

```protobuf
// Payload (Protobuf encoded)
Payload {
  timestamp: 1722000000000
  metrics: [
    { name: "Temperature", datatype: Float, float_value: 23.5 },
    { name: "Pressure", datatype: Float, float_value: 1.02 },
    { name: "Running", datatype: Boolean, boolean_value: true },
    { name: "CycleCount", datatype: Int64, long_value: 14823 }
  ]
  seq: 0
}
```

Consumers parse the birth certificate to learn what metrics the device reports, their types, and initial values. No separate configuration file needed — the device self-describes.

## Data messages

After birth, the device publishes NDATA/DDATA with changed metrics:

```protobuf
Payload {
  timestamp: 1722000060000
  metrics: [
    { name: "Temperature", datatype: Float, float_value: 24.1 },
    { name: "Pressure", datatype: Float, float_value: 1.01 }
  ]
  seq: 1
}
```

Only changed metrics are included (report by exception). Sequence numbers detect missed messages.

## Death certificate

Configured as MQTT Last Will and Testament:

```python
client.will_set(
    topic="spBv1.0/FactoryA/NDEATH/EdgeNode1",
    payload=encode_death_payload(),
    qos=1,
    retain=False,
)
```

If the edge node disconnects ungracefully, the broker publishes the death certificate automatically. SCADA systems mark the node offline immediately.

## Edge node implementation

Using Eclipse Tahu Python:

```python
from sparkplug_b import sparkplug_b as spb

def publish_birth(client, group_id, node_id, metrics):
    topic = f"spBv1.0/{group_id}/NBIRTH/{node_id}"
    payload = spb.Payload()
    payload.timestamp = int(time.time() * 1000)
    for metric in metrics:
        m = payload.metrics.add()
        m.name = metric["name"]
        m.datatype = metric["datatype"]
        if metric["datatype"] == spb.DataType.Float:
            m.float_value = metric["value"]
        elif metric["datatype"] == spb.DataType.Boolean:
            m.boolean_value = metric["value"]
    client.publish(topic, payload.SerializeToString(), qos=1)

def publish_data(client, group_id, node_id, device_id, metrics):
    topic = f"spBv1.0/{group_id}/DDATA/{node_id}/{device_id}"
    payload = spb.Payload()
    payload.timestamp = int(time.time() * 1000)
    payload.seq = get_next_seq()
    # ... add changed metrics
    client.publish(topic, payload.SerializeToString(), qos=0)
```

## Metric aliases for bandwidth

After birth, subsequent messages can use numeric aliases instead of string names:

```protobuf
// Birth: defines alias
{ name: "Temperature", alias: 1, datatype: Float, float_value: 23.5 }

// Data: uses alias only (saves bytes)
{ alias: 1, datatype: Float, float_value: 24.1 }
```

Important on bandwidth-constrained links (cellular, LoRaWAN backhaul).

## SCADA integration pattern

```
PLCs (Modbus) → Edge Node (Sparkplug B) → MQTT Broker → SCADA/Historian
                                                      → Dashboard (Grafana)
                                                      → Alerting
```

The edge node:
1. Polls PLCs via Modbus/BACnet/OPC UA
2. Publishes birth certificates on connect
3. Publishes DDATA on value change
4. Sets LWT death certificate
5. Accepts DCMD for write-back commands

SCADA systems (Ignition, Inductive Automation) have native Sparkplug B support via MQTT Engine module.

## Command and control (NCMD/DCMD)

Sparkplug B isn't read-only. Commands flow downstream:

```
spBv1.0/FactoryA/NCMD/EdgeNode1/
  → { metrics: [{ name: "Reboot", type: Boolean, value: true }] }

spBv1.0/FactoryA/DCMD/EdgeNode1/Device1/
  → { metrics: [{ name: "Setpoint", type: Float, value: 72.5 }] }
```

The edge node receives DCMD, writes to the PLC via Modbus or OPC UA, and confirms with an updated DDATA message. Always validate command ranges at the edge before writing to field devices — the cloud doesn't know the PLC's safe operating limits. Log every command with operator ID and timestamp for audit.

## Common production mistakes

Teams get mqtt sparkplug scada wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of mqtt sparkplug scada fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When mqtt sparkplug scada misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Eclipse Tahu (Sparkplug B) GitHub](https://github.com/eclipse/tahu) — reference implementations in Python, Java, C
- [Sparkplug B specification](https://sparkplug.eclipse.org/specification/) — official specification document
- [Sparkplug B topic namespace reference](https://sparkplug.eclipse.org/specification/version/3.0/documents/sparkplug-specification.pdf) — complete topic and payload definitions
- [Ignition MQTT Engine](https://docs.inductiveautomation.com/docs/8.1/ignition-modules/mqtt-engine) — SCADA integration with Sparkplug B
