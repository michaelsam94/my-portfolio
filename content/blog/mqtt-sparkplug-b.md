---
title: "MQTT Sparkplug B for Industrial Telemetry"
slug: "mqtt-sparkplug-b"
description: "MQTT Sparkplug B for industrial telemetry: birth/death certificates, stateful sessions, the unified namespace, and how it turns plain MQTT into a real OT/IT data backbone."
datePublished: "2026-03-22"
dateModified: "2026-07-17"
tags:
keywords: "MQTT Sparkplug B, industrial MQTT, birth death certificates, state management IIoT, unified namespace, OT IT"
faq:
  - q: "What is MQTT Sparkplug B?"
    a: "MQTT Sparkplug B is an open specification that defines how to use MQTT for industrial telemetry with well-known topic structures, an efficient binary payload, and explicit state management. It adds birth and death certificates so consumers always know whether a device is online and what its current values are, turning plain MQTT — which says nothing about payloads or state — into an interoperable industrial data protocol."
  - q: "Why isn't plain MQTT enough for industrial use?"
    a: "Plain MQTT only defines transport: topics and publish/subscribe. It says nothing about topic naming, payload format, or how to know if a device is alive and what its last-known values are. In industrial settings that ambiguity is fatal, so every integration becomes bespoke. Sparkplug B standardizes topics, payloads, and state so any consumer can understand any Sparkplug device without custom mapping."
  - q: "What are birth and death certificates in Sparkplug B?"
    a: "A birth certificate (NBIRTH/DBIRTH) is a retained message a node or device publishes on connect that declares all its metrics and their current values. A death certificate (NDEATH/DDEATH) is registered as an MQTT Last Will and Testament so the broker publishes it automatically if the device disconnects unexpectedly. Together they let consumers always know the online/offline state and the full current context of every device."
---
Plain MQTT is a fantastic transport and a terrible protocol — by which I mean it tells you exactly nothing about what a message contains, how topics are named, or whether the device that should be publishing is even alive. In a chat app that's fine. On a factory floor with hundreds of devices feeding SCADA, MES, and analytics systems, that ambiguity means every integration is a bespoke, brittle mapping exercise. MQTT Sparkplug B fixes this by layering convention on top of MQTT: standardized topic namespaces, an efficient binary payload, and — the crucial part — explicit state management through birth and death certificates. It's what turns MQTT into an actual industrial data backbone.

I've worked on both raw-MQTT industrial pipelines and Sparkplug-based ones, and the difference in how much glue code you write is stark. Sparkplug's whole value is that it makes state and structure part of the protocol instead of tribal knowledge.

## The problem Sparkplug solves: state

The deepest issue with plain MQTT in industry isn't payload format — it's that MQTT is stateless from a consumer's perspective. If a temperature sensor hasn't published in five minutes, is it broken, or is the temperature just stable? You can't tell. Did you miss the last value because you connected late? Possibly. MQTT's retained messages help a little but don't give you a coherent model of "here is every device, whether it's online, and its current value."

Sparkplug's answer is the certificate model:

- **NBIRTH / DBIRTH** — when an edge node or device comes online, it publishes a *birth certificate*: a message listing every metric it will report and each one's current value and datatype. Consumers now know the full picture immediately.
- **NDEATH / DDEATH** — the node registers a *death certificate* as its MQTT Last Will and Testament. If it drops unexpectedly, the broker publishes the death automatically. Consumers instantly know the device is gone.
- **NDATA / DDATA** — normal telemetry updates, sent by exception (only when values change).

Because of this, any Sparkplug consumer always knows two things it can never know with plain MQTT: which devices are alive right now, and the current value of every metric — even ones that haven't changed since the consumer connected. That's the feature that makes it usable for control-room dashboards where "unknown state" is unacceptable.

## The topic namespace and unified namespace

Sparkplug prescribes a topic structure so you don't have to invent one:

```text
spBv1.0/{group_id}/{message_type}/{edge_node_id}/{device_id}

# examples
spBv1.0/PlantA/NBIRTH/Line3Gateway
spBv1.0/PlantA/DDATA/Line3Gateway/Pump7
spBv1.0/PlantA/DDEATH/Line3Gateway/Pump7
```

That rigid structure is a feature. Because everyone follows it, a consumer can subscribe with wildcards and discover the entire plant's topology without prior configuration. This dovetails with the "unified namespace" idea gaining traction in industrial IoT — a single, structured, real-time source of truth for all operational data, where OT (operational technology) and IT systems both read and write through the same broker-backed namespace instead of point-to-point integrations. Sparkplug is the most common concrete way to implement a unified namespace, because its birth/death model gives that namespace live, self-describing state.

## Payload: efficient and self-describing

Sparkplug B uses a Google Protocol Buffers payload rather than JSON. That's a deliberate trade: the binary encoding is far more compact and typed, which matters when you're pushing high-frequency telemetry over constrained industrial links, at the cost of not being human-readable on the wire. Each metric carries a name, datatype, timestamp, and value, so the payload is self-describing — a consumer doesn't need an external schema to interpret it.

The report-by-exception behavior compounds the efficiency. After the birth certificate establishes baseline values, devices only publish metrics that actually changed. On a plant where most process variables are stable most of the time, this slashes traffic compared to periodic full reports — the same bandwidth discipline I described for edge deadband reporting in [Modbus and industrial IoT gateways](https://blog.michaelsam94.com/modbus-industrial-gateways/), where the gateway suppresses unchanged values. In fact, a Modbus-to-Sparkplug gateway is one of the most common bridges you'll build: poll legacy fieldbuses, then publish their normalized values into a Sparkplug namespace.

## Sparkplug vs plain MQTT at a glance

| Concern | Plain MQTT | Sparkplug B |
|---|---|---|
| Topic structure | Anything you invent | Standardized namespace |
| Payload | Opaque bytes | Typed Protobuf metrics |
| Device state | Unknown | Birth/death certificates |
| Discovery | Manual/config | Automatic via births |
| Report by exception | Roll your own | Built in |
| Interoperability | Per-integration glue | Any Sparkplug consumer |

The table makes the pitch obvious, but the honest caveat is that Sparkplug is more opinionated and more work to implement correctly than firing JSON at arbitrary topics. You need a compliant edge node implementation, you need to handle the state machine (rebirth requests, sequence numbers to detect missed messages), and Protobuf tooling is a step up from `JSON.stringify`. For a two-device hobby project it's overkill. For a plant with dozens of systems needing a shared view of hundreds of devices, it's the difference between an architecture and a mess.

## When to use it

I'd choose Sparkplug B when I'm building an industrial data layer where multiple consumers (SCADA, historian, analytics, MES) need a consistent, live view of device state, where interoperability across vendors matters, and where "is this device online and what's its current value" must be answerable at any instant. It's the natural fit whenever you're standing up a unified namespace as the integration backbone.

I'd stick with plain MQTT — using the broader patterns from [MQTT for IoT at scale](https://blog.michaelsam94.com/mqtt-iot-at-scale/) — when the deployment is smaller, consumer-specific, or when I control both ends and don't need the interoperability guarantees. Sparkplug's structure is worth its weight exactly when many independent parties must agree on what the data means.

Sparkplug B is one of those specifications that looks like bureaucracy until you've felt the pain it prevents. The birth/death state model alone justifies it in any control-room context, and the standardized namespace turns a broker into a genuine OT/IT bridge rather than a dumb pipe. Implement the state machine faithfully, use a proven edge node library, and it becomes the reliable spine of an industrial data platform.

## Resources

- [Sparkplug B specification — Eclipse Foundation](https://sparkplug.eclipse.org/specification/)
- [Eclipse Tahu — reference Sparkplug implementation](https://github.com/eclipse/tahu)
- [MQTT 5.0 specification — OASIS](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [Eclipse Mosquitto — MQTT broker](https://mosquitto.org/)
- [Protocol Buffers documentation](https://protobuf.dev/)
- [HiveMQ — Sparkplug and unified namespace resources](https://www.hivemq.com/mqtt/mqtt-sparkplug/)
