---
title: "MQTT for IoT at Scale"
slug: "mqtt-iot-at-scale"
description: "How MQTT actually scales for IoT: QoS levels that matter, topic design, retained messages, last will, shared subscriptions, and broker choices for millions of devices."
datePublished: "2026-07-16"
dateModified: "2026-07-17"
tags:
keywords: "MQTT, IoT messaging, MQTT broker, pub sub IoT, MQTT QoS, retained messages, shared subscriptions"
faq:
  - q: "Which MQTT QoS level should I use?"
    a: "QoS 0 (at most once) for high-frequency telemetry where losing a reading doesn't matter, QoS 1 (at least once) for most commands and important data where duplicates are tolerable, and QoS 2 (exactly once) rarely, because its overhead is high. Most production IoT runs on QoS 1 with idempotent handlers."
  - q: "How many devices can an MQTT broker handle?"
    a: "A single well-tuned broker like EMQX or HiveMQ can handle hundreds of thousands to over a million concurrent connections on capable hardware. Beyond that, or for high availability, you cluster brokers and use shared subscriptions to distribute load across consumers."
  - q: "What are retained messages used for?"
    a: "A retained message is stored by the broker and delivered immediately to any new subscriber of that topic. It's ideal for state — the last known status of a device — so a subscriber that connects later instantly gets the current value instead of waiting for the next publish."
---
MQTT earns its place in IoT because it's cheap where IoT is expensive: bandwidth, battery, and unreliable networks. It's a lightweight publish/subscribe protocol over TCP, designed originally for oil pipeline telemetry over satellite links, and that heritage shows — tiny headers, a persistent connection that survives flaky networks, and quality-of-service levels that let each message choose its own reliability. Scaling it to millions of devices is less about the protocol and more about three decisions: QoS discipline, topic design, and broker topology.

I'll go through what actually matters when you move from a demo with ten devices to a fleet. The demo works with any settings. The fleet punishes every lazy choice — a bad topic hierarchy, QoS 2 everywhere, or retained messages you forgot to clear will each show up as a production incident.

## QoS: pick per message, not per system

MQTT's three quality-of-service levels are the first thing people over-think. The trap is picking one globally. The right move is choosing per message based on what the data is worth:

| QoS | Guarantee | Use for | Cost |
| --- | --- | --- | --- |
| 0 | At most once | High-rate telemetry, sensor streams | Cheapest, fire-and-forget |
| 1 | At least once | Commands, important events | One round-trip, possible duplicates |
| 2 | Exactly once | Rare — billing-critical, non-idempotent | Four-way handshake, expensive |

The practical default is **QoS 1 with idempotent handlers.** QoS 1 can deliver duplicates, so you design consumers to tolerate them — dedupe by message ID or make the operation idempotent — and you get reliability without QoS 2's expensive four-packet handshake. QoS 2 sounds appealing ("exactly once!") but its overhead at scale is brutal, and true exactly-once is better solved with idempotency in your application than in the transport. This is the same [idempotency discipline](https://blog.michaelsam94.com/idempotency-distributed-systems/) that any at-least-once messaging system demands.

## Topic design is your API

Topics are the addressing scheme, and a bad hierarchy is nearly impossible to fix once devices are deployed. Design it like a URL structure: hierarchical, specific-to-general left-to-right, and stable.

```
# Good: structured, filterable, scoped
tenant/42/site/cairo-01/device/charger-7/telemetry/power
tenant/42/site/cairo-01/device/charger-7/status

# Bad: flat, unfilterable, encodes data in the topic name
charger7powerreading
```

The hierarchy lets subscribers use wildcards precisely: `tenant/42/site/cairo-01/device/+/status` subscribes to every device's status at one site, `tenant/42/#` gets everything for a tenant. Two rules save you pain: **put identifiers in the topic, not the payload's routing role**, and **never put high-cardinality changing values in topic names** (no timestamps or reading values in the topic — those go in the payload). Get the topic tree right early; it's the contract every device and consumer depends on.

## Retained messages and last will: cheap state

Two MQTT features punch above their weight for IoT.

A **retained message** is stored by the broker and delivered instantly to any new subscriber. Publish a device's status as retained, and a dashboard that connects later immediately sees the current state instead of waiting for the next update. It turns MQTT topics into a lightweight last-known-value store.

The **Last Will and Testament (LWT)** is a message the broker publishes automatically if a device disconnects ungracefully. Combine the two — a device sets its status topic to `online` (retained) on connect and registers an LWT that sets it to `offline` (retained) — and you get reliable presence detection without polling:

```python
client.will_set(
    "tenant/42/device/charger-7/status",
    payload='{"state":"offline"}',
    qos=1, retain=True,
)
client.connect(broker)
client.publish(
    "tenant/42/device/charger-7/status",
    '{"state":"online"}', qos=1, retain=True,
)
```

One gotcha: retained messages persist until overwritten or cleared with an empty retained publish. Forget that and stale state haunts you — a decommissioned device shows `online` forever because nothing ever cleared its retained status.

## Scaling the broker

A single modern broker — [EMQX](https://www.emqx.io/), [HiveMQ](https://www.hivemq.com/), or [Eclipse Mosquitto](https://mosquitto.org/) for smaller loads — handles a lot. EMQX and HiveMQ routinely sustain hundreds of thousands to over a million concurrent connections per node with tuning. You scale past one node, or gain high availability, by clustering.

The feature that makes consumer-side scaling work is **shared subscriptions** (`$share/group/topic`). Normally every subscriber to a topic gets every message; with a shared subscription, the broker load-balances messages across a group of consumers. That's how you scale the *processing* side — run ten instances of your telemetry ingester in a shared-subscription group and the broker fans work across them, giving you the same backpressure relief that any well-designed queue consumer needs.

For real fleets, budget for:

- **Connection storms** — after a network blip, thousands of devices reconnect at once. Use randomized reconnect backoff on devices, or the broker melts.
- **Authentication and authorization** — per-device credentials (ideally client certificates / mutual TLS) and topic-level ACLs so a compromised device can't publish to another tenant's topics.
- **TLS everywhere** — MQTT over TLS on 8883, not plaintext 1883, for anything crossing untrusted networks.

## How MQTT fits the bigger picture

MQTT is a transport, not a system. It gets telemetry off devices efficiently and reliably, but the value is in what consumes it — stream processing, storage, and often a [digital twin](https://blog.michaelsam94.com/digital-twins-architecture/) that maintains the live model of each device from the MQTT feed. It's also frequently the ingest layer feeding [MQTT into scaled WebSocket or event pipelines](https://blog.michaelsam94.com/websocket-architecture-at-scale/) for dashboards.

Keep the QoS honest, the topics disciplined, and the reconnection behavior kind to your broker, and MQTT scales to fleets without drama. The protocol was built for constrained, unreliable environments — lean into that design instead of fighting it, and it holds up remarkably well.

## Resources

- [MQTT.org — protocol home](https://mqtt.org/)
- [OASIS MQTT 5.0 specification](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [HiveMQ MQTT Essentials guide](https://www.hivemq.com/mqtt-essentials/)
- [EMQX broker documentation](https://docs.emqx.com/)
- [Eclipse Mosquitto](https://mosquitto.org/)
- [Eclipse Paho — MQTT client libraries](https://eclipse.dev/paho/)
