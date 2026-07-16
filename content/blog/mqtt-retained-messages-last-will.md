---
title: "Retained Messages and Last Will"
slug: "mqtt-retained-messages-last-will"
description: "Use MQTT retained messages and Last Will and Testament correctly: state topics, birth certificates, graceful offline detection, and pitfalls that corrupt fleet state."
datePublished: "2025-07-27"
dateModified: "2025-07-27"
tags: ["IoT", "MQTT", "Messaging", "Protocol"]
keywords: "MQTT retained messages, MQTT last will testament, LWT, birth certificate, IoT device state"
faq:
  - q: "What is an MQTT retained message?"
    a: "A publish with the retain flag set. The broker stores the last retained message per topic and delivers it immediately to new subscribers — even if the publisher is offline. Used for 'current state' topics like device config or last-known sensor reading."
  - q: "When should you use Last Will and Testament?"
    a: "Configure LWT when subscribers need to detect unexpected disconnects — crash, power loss, network drop — without waiting for keepalive timeout. The broker publishes the will message when the connection dies uncleanly. Don't use LWT for graceful shutdown; publish an explicit offline status first."
  - q: "How do retained messages and LWT work together?"
    a: "Common pattern: retained 'birth' message on connect with status online, LWT publishes retained offline status on unclean disconnect. New subscribers instantly see current presence. Clear retained messages on decommission to avoid ghost devices."
---

Dashboard showed 847 devices online. Field ops counted 812 powered units — the other 35 were retain ghosts from devices swapped six months ago, still publishing `{"status":"online"}` because nobody cleared the retained topic. MQTT retained messages and Last Will and Testament solve real problems — instant state for new subscribers, fast offline detection — but used carelessly they lie to your monitoring stack long after hardware leaves the fleet.

## Retained messages: last known good (or bad)

Normal publish: only current subscribers receive it. **Retained publish:** broker stores one message per topic (per MQTT spec, latest retain replaces previous). Any new subscriber gets it on subscribe.

```python
# Device publishes current firmware version — retained
client.publish(
    "devices/pump-7/meta/firmware",
    payload="2.4.1",
    qos=1,
    retain=True
)
```

New monitoring service subscribes to `devices/+/meta/firmware` and immediately knows all devices' versions without waiting for next heartbeat.

### When retention helps

- **Configuration/state topics** — `home/living-room/light/state` → `ON`
- **Birth certificates** — device metadata on connect
- **Last sensor reading** — new analytics consumer gets current value
- **Feature flags pushed to fleet** — retained until replaced

### When retention hurts

- **High-frequency telemetry** — retain on `sensors/+/temp` every second = broker stores garbage, new subscribers get stale reading
- **Command topics** — new subscriber replays old command (dangerous)
- **Decommissioned devices** — retain persists until explicitly cleared

**Clear retain:** publish empty payload with `retain=True` to same topic:

```python
client.publish("devices/old-pump-7/meta/firmware", payload=None, retain=True)
```

Automate this in your device lifecycle pipeline when hardware is RMA'd or replaced.

## Last Will and Testament (LWT)

Set at **connect time** — broker stores will topic, payload, QoS, retain flag. Published only on **unclean disconnect** (TCP drop, keepalive failure, process kill without DISCONNECT).

```python
client.will_set(
    topic="devices/pump-7/status",
    payload=json.dumps({"status": "offline", "reason": "unexpected"}),
    qos=1,
    retain=True
)
client.connect("mqtt.example.com", 8883)
client.publish("devices/pump-7/status", '{"status":"online"}', qos=1, retain=True)
```

Sequence:
1. Connect with will registered
2. Publish retained online status (birth message)
3. Normal operation
4. Power loss → broker publishes will → subscribers see offline

**Clean disconnect** (`client.disconnect()`) suppresses the will. Graceful shutdown should publish explicit offline *before* disconnect if you want subscribers to distinguish planned vs unplanned — or use a `clean_disconnect` reason code in MQTT 5.

## Birth / will pattern for fleet presence

Standard topic layout:

```
devices/{id}/status     → retained JSON: { "status": "online"|"offline", "ts": "..." }
devices/{id}/telemetry  → QoS 0, not retained
devices/{id}/commands   → QoS 1, not retained
```

Connect flow:

```javascript
const birth = JSON.stringify({ status: 'online', ts: new Date().toISOString(), fw: '2.4.1' });
client.on('connect', () => {
  client.publish(`devices/${deviceId}/status`, birth, { qos: 1, retain: true });
});
```

Will (registered before connect):

```javascript
const will = JSON.stringify({ status: 'offline', ts: new Date().toISOString(), reason: 'lwt' });
// mqtt.js: will option in connect options
```

Subscribers to `devices/+/status` maintain live presence map from retained messages — no database seeding required for new dashboard instances.



**Keepalive vs LWT timing.**

Default keepalive is often 60 seconds. Unclean disconnect detection takes up to 1.5× keepalive before will fires.

| Setting | Effect |
|---------|--------|
| keepalive 30s | Faster offline detection, more ping traffic |
| keepalive 300s | Slow offline detection, LPWAN-friendly |
| LWT retain true | New dashboards see offline state |
| LWT retain false | Offline event only for live subscribers |

For mobile devices on flaky networks, aggressive keepalive causes false offline flapping. We use keepalive 120s + application heartbeat on a separate topic for user-facing presence, LWT for ops alerting only.



**Retained storage at scale.**

Brokers store retains in memory and/or disk. Thousands of devices × multiple retained topics adds up.

Practices:
- **One retained topic per device** for status, not per metric
- **Periodic audit job** — subscribe to `devices/+/status`, compare against asset registry, clear orphans
- **MQTT 5 topic aliases** — reduce wire size, not retain count

EMQX exposes `$SYS/broker/retained/count` — alert if it grows faster than fleet size.



**Common bugs.**

**Will set after connect.** Will must be configured before `CONNECT` packet. Libraries expose `will_set()` or connect options — order matters.

**Retained commands.** OTA trigger retained on `devices/+/cmd/ota` — device reboots, replays OTA. Never retain on command namespaces.

**Same topic for birth and telemetry.** Mixing retained state with streaming data confuses subscribers. Separate topic hierarchies.

**QoS 0 will.** Will may be lost under broker stress. Use QoS 1 for status wills.

**Session takeover.** Same client ID reconnects elsewhere — previous session's retain and will behavior depends on broker `clean start` policy. Use unique client IDs per device (`deviceId + instance`).



**MQTT 5 improvements.**

- **Will delay interval** — defer will publish to absorb brief reconnects
- **Session expiry** — retained session state TTL
- **User properties on will** — attach device metadata without parsing payload
- **Reason codes** — distinguish disconnect causes in logs

Worth upgrading brokers and clients when fleet firmware allows.

Run retained-topic audits monthly: export all retains under `devices/+/status`, diff against your asset CMDB, and clear orphans with an automated empty retain publish. Dashboards should treat LWT offline events as hints, not ground truth — brief Wi-Fi drops trigger wills while devices remain healthy; correlate with last telemetry timestamp before paging on-call. For fleets using MQTT 5 will delay, tune delay to absorb reconnect churn on mobile gateways without masking genuine outages. Train support staff: clearing retain fixes "stuck online" ghosts; it does not replace decommissioning credentials on the broker. Pair birth/will topics with explicit `decommissioned` retain when retiring hardware so analytics pipelines filter correctly.

## Resources

- [MQTT 5.0 — retained messages and will](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)
- [HiveMQ — MQTT retained messages](https://www.hivemq.com/blog/mqtt-essentials-part-8-retained-messages/)
- [HiveMQ — Last Will and Testament](https://www.hivemq.com/blog/mqtt-essentials-part-9-last-will-and-testament/)
- [Eclipse Mosquitto man page — configuration](https://mosquitto.org/man/mosquitto-8.html)
- [EMQX retained message storage](https://www.emqx.io/docs/en/latest/design/retained.html)
