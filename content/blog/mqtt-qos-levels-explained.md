---
title: "MQTT QoS Levels, Explained"
slug: "mqtt-qos-levels-explained"
description: "Understand MQTT QoS 0, 1, and 2: delivery guarantees, handshake flows, when each level fits IoT workloads, and common misconfigurations that waste bandwidth."
datePublished: "2025-07-24"
dateModified: "2025-07-24"
tags: ["IoT", "MQTT", "Messaging", "Protocol"]
keywords: "MQTT QoS levels, QoS 0 1 2, MQTT delivery guarantee, at most once, exactly once, IoT messaging"
faq:
  - q: "Which MQTT QoS level should I use for sensor telemetry?"
    a: "QoS 0 for high-frequency, loss-tolerant readings where the next sample arrives in seconds. QoS 1 when gaps matter — energy meters, inventory counts — and you can tolerate occasional duplicates. Reserve QoS 2 for financial or command-and-control where duplicate processing has real cost."
  - q: "Does QoS 2 guarantee exactly-once end-to-end?"
    a: "QoS 2 guarantees exactly-once delivery between one publisher and one broker, and between that broker and one subscriber, via four-step handshake. It does not span multiple brokers in a bridge chain, and your application must still handle duplicate processing if it crashes after ack but before commit."
  - q: "Why does QoS 1 sometimes deliver duplicates?"
    a: "The publisher or broker may retry PUBLISH if PUBACK is lost. Subscribers that don't deduplicate by message ID or application sequence will process the same payload twice. QoS 1 is at-least-once, not exactly-once."
---

A temperature sensor publishing every second at QoS 2 generated four MQTT control packets per reading. Across 2,000 devices, the broker spent more CPU on handshakes than on payload delivery — and we still saw duplicate furnace shutoff commands because the PLC app didn't idempotently handle replays. MQTT QoS isn't a quality slider you max out; it's a contract with bandwidth and latency costs that most IoT teams misread.

## The three QoS levels at a glance

| QoS | Name | Guarantee | Control packets (typical) |
|-----|------|-----------|---------------------------|
| 0 | At most once | Fire and forget | PUBLISH |
| 1 | At least once | Acknowledged delivery | PUBLISH → PUBACK |
| 2 | Exactly once | Four-way handshake | PUBLISH → PUBREC → PUBREL → PUBCOMP |

QoS is negotiated per **publish** (and per **subscribe** in MQTT 5 subscription options). The effective QoS is the minimum of publish QoS and subscription QoS.

## QoS 0: at most once

Publisher sends PUBLISH; no acknowledgment. Message may be lost if:
- Client disconnects mid-send
- Broker crashes before routing
- Network drops the packet

```python
# Paho Python — QoS 0 telemetry burst
client.publish("sensors/temp/line-3", payload=json.dumps(reading), qos=0)
```

**Use when:** readings are frequent and self-healing (next sample in ≤5s), loss of individual points doesn't trigger actions, bandwidth is constrained (LPWAN backhaul).

**Avoid when:** each reading triggers billing, safety logic, or irreversible actuation.

## QoS 1: at least once

Publisher sends PUBLISH with packet ID. Broker responds PUBACK. If PUBACK doesn't arrive within timeout, publisher retries with same packet ID.

Subscriber side mirrors: deliver to app → send PUBACK → if app crashes before ack, broker redelivers.

```
Publisher                    Broker                    Subscriber
   │ PUBLISH (id=42) ────────►│
   │◄────────────── PUBACK ───│
   │                          │ PUBLISH (id=42) ────────►│
   │                          │◄────────────── PUBACK ──│
```

**Duplicates happen** when PUBACK is lost and retry succeeds — subscriber sees id=42 twice.

**Use when:** you need reliable delivery and can deduplicate in application logic (store last `(device_id, seq)` in Redis, ignore replays).

```javascript
// Dedup guard in consumer
const key = `${deviceId}:${payload.sequence}`;
if (await redis.set(key, '1', 'NX', 'EX', 3600) === null) return; // duplicate
await processReading(payload);
```

## QoS 2: exactly once (between two parties)

Four-step handshake ensures neither side duplicates nor loses the message in the MQTT layer:

```
PUBLISH → PUBREC → PUBREL → PUBCOMP
```

Broker stores state through the exchange — higher memory and latency per message. Under load, QoS 2 queues dominate RAM on brokers with many offline persistent sessions.

**Use when:** command topics where duplicate execution is dangerous (unlock door twice is fine; charge credit card twice isn't — but you'd still want app-level idempotency keys).

**Often overkill for:** telemetry, status heartbeats, non-critical config updates.

We dropped furnace commands from QoS 2 to QoS 1 with command UUID idempotency — same safety, 60% less broker CPU.



**Persistent sessions and QoS.**

When a client connects with `cleanSession=false` (MQTT 3.1.1) or `cleanStart=false` with session expiry (MQTT 5):

- Broker queues QoS 1 and 2 messages for offline subscribers
- Queue depth per session is broker-configurable — unbounded queues OOM brokers

A fleet of 10,000 devices reconnecting after outage with QoS 1 backlog can stampede. Mitigations:
- Cap `max_queued_messages` per client
- Use shorter session expiry (MQTT 5)
- Prefer QoS 0 for high-rate telemetry even with persistent sessions



**Publish vs subscribe mismatch.**

Client publishes at QoS 2, subscriber requests QoS 0 → delivery happens at QoS 0 (no guarantee).

Client publishes at QoS 0, subscriber requests QoS 2 → delivery at QoS 0.

Always align producer and consumer expectations in your topic contract documentation.



**Choosing QoS by workload.**

| Workload | Recommended QoS | Notes |
|----------|-----------------|-------|
| Temperature every 5s | 0 | Gap-fill in analytics if needed |
| GPS track every 30s | 0–1 | 1 if route billing depends on points |
| Door unlock command | 1 + idempotency key | 2 rarely worth cost |
| OTA firmware chunk | 1 | App verifies hash per chunk |
| Alarm / critical event | 1 | Log + alert on duplicate |
| Payment meter reading | 1 + dedup | QoS 2 if broker load acceptable |



**Broker configuration.**

EMQX/Mosquitto settings that affect QoS behavior:

- **`max_inflight`** — unacknowledged QoS 1/2 publishes per client
- **`retry_interval`** — retransmit timing
- **`max_queued_messages`** — offline queue cap
- **`upgrade_qos`** — some bridges downgrade/upgrade at boundary (document this)

Load test with realistic reconnect storms, not steady-state publish only.



**Application-level guarantees.**

MQTT QoS 2 doesn't survive:
- Bridge hops (often downgraded)
- Consumer crash after PUBCOMP but before DB commit
- Multiple subscribers on same topic (each gets a copy — "exactly once" per subscriber, not globally)

Pattern we use for commands:

```json
{
  "command_id": "550e8400-e29b-41d4-a716-446655440000",
  "action": "set_setpoint",
  "value": 72.5,
  "issued_at": "2025-07-24T12:00:00Z"
}
```

Device stores last 100 `command_id` values; ignores repeats. QoS 1 + idempotency beats QoS 2 alone.

Load-test QoS choices with reconnect storms, not steady publish rates alone. Persistent sessions with QoS 1 backlog multiply during outages — model worst-case queue depth as `(offline_duration / publish_interval) × payload_size × device_count`. Broker tuning (`max_inflight`, `max_queued_messages`) is part of QoS design, not an afterthought. Teach firmware teams that QoS is per-publish: mixing QoS 0 heartbeats with QoS 1 alarms on the same client is fine and often optimal. Document the QoS contract in your topic registry so backend engineers do not upgrade telemetry to QoS 2 "for reliability" without understanding broker cost. Review quarterly as fleet size grows — QoS 1 that worked at 1,000 devices may choke at 50,000.

## Resources

- [OASIS MQTT 5.0 specification — QoS section](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)
- [Eclipse Paho MQTT client libraries](https://www.eclipse.org/paho/)
- [HiveMQ MQTT essentials — QoS](https://www.hivemq.com/mqtt/mqtt-qos/)
- [EMQX QoS design and tuning](https://www.emqx.io/docs/en/latest/design/qos.html)
- [MQTT 5.0 features overview (MQTT.org)](https://mqtt.org/mqtt-specification/)
