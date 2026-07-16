---
title: "MQTT Bridging and Clustering"
slug: "mqtt-bridging-clustering"
description: "Scale MQTT beyond a single broker: bridge topologies, cluster federation, shared subscriptions, and operational patterns for multi-site IoT deployments."
datePublished: "2025-07-21"
dateModified: "2025-07-21"
tags: ["IoT", "MQTT", "Infrastructure", "Messaging"]
keywords: "MQTT bridging, MQTT clustering, EMQX cluster, Mosquitto bridge, IoT message broker scale"
faq:
  - q: "What is the difference between MQTT bridging and clustering?"
    a: "Bridging connects two independent brokers — messages flow between them based on configured topic patterns, often across networks or vendors. Clustering makes multiple broker nodes appear as one logical broker with shared session state and load distribution."
  - q: "Do bridged messages preserve QoS end-to-end?"
    a: "Not reliably across the bridge itself. Each broker enforces QoS on its side of the connection. A QoS 2 publish on broker A may arrive at broker B as QoS 1 depending on bridge config. Design critical flows with idempotent consumers and app-level acks."
  - q: "When should you bridge instead of cluster?"
    a: "Bridge when crossing security boundaries (plant floor to cloud), connecting legacy Mosquitto to EMQX, or linking geographically distant sites with intermittent links. Cluster when you need horizontal scale and HA within one deployment domain."
---

The factory MQTT broker hit 12,000 connected PLCs before CPU pegged at 100%. Adding a second Mosquitto instance didn't help — clients were still pinned to one node with no shared state. We needed bridging to get telemetry into AWS IoT Core without exposing the plant network, and clustering so no single VM became the bottleneck. MQTT scaling is two different problems with overlapping vocabulary; picking the wrong pattern gives you duplicate messages, lost sessions, or a bridge loop that took down staging twice.

## Single broker limits

One broker node handles surprising load — tens of thousands of lightweight clients publishing every 30 seconds. Limits appear in:

- **Connection count** — file descriptors, memory per session
- **Publish throughput** — single-threaded routing in simpler brokers
- **Persistent sessions** — RAM/disk for offline QoS 1/2 queues
- **Topic fan-out** — 1 publish × 5,000 subscribers = 5,000 deliveries

Monitor `messages.publish.received.rate`, heap usage, and `socket` counts before scaling.

## MQTT bridging

A bridge is an MQTT client connection between brokers. Broker A forwards matching topics to Broker B (and optionally reverse).

Mosquitto bridge config (site → cloud):

```
connection bridge-to-cloud
address iot.example.com:8883
bridge_cafile /etc/mosquitto/certs/ca.crt
bridge_insecure false
remote_username bridge-user
remote_password ${BRIDGE_PASSWORD}

topic factory/+/telemetry out 1
topic factory/+/commands in 1
topic $SYS/# out 0

cleansession false
try_private false
notifications_local true
```

Key directives:
- **`topic pattern direction qos`** — `out` publishes from local to remote; `in` subscribes remote to local
- **`cleansession false`** — bridge reconnects without losing inflight state
- **Avoid `#` bridges** — loop risk and bandwidth explosion; be explicit

### Bridge topologies

```
  [Plant Mosquitto] ──bridge──► [Cloud EMQX] ◄── [Mobile apps]
         ▲                              │
         │                              ▼
    [PLCs / sensors]              [Analytics / rules]
```

**Hub-and-spoke:** edge brokers bridge upward; cloud never bridges back to every edge (use commands down one path).

**Peer bridge:** two sites exchange topics — watch for loops. Use separate inbound/outbound topic prefixes (`site-a/`, `site-b/`).

**Protocol bridge:** MQTT ↔ Kafka ↔ AMQP via connector services when brokers can't bridge natively.

## MQTT clustering

Clustered brokers (EMQX, HiveMQ, VerneMQ) share routing tables and often session state via backend (MDB, Raft, or proprietary gossip).

```
                    ┌─────────┐
         Clients ──►│  LB     │
                    └────┬────┘
              ┌──────────┼──────────┐
              ▼          ▼          ▼
          [Node 1]   [Node 2]   [Node 3]
              └──────────┼──────────┘
                    shared state
                   (DB / Raft)
```

Clients connect through a load balancer (TCP passthrough on 8883, not HTTP LB). Sticky sessions help for persistent connections but shouldn't be mandatory if session state is truly shared.

**EMQX cluster** excerpt — nodes discover via static seed or DNS:

```hcl
# emqx.conf
cluster {
  discovery_strategy = static
  static.seeds = ["emqx1@10.0.1.10", "emqx2@10.0.1.11"]
}
```

Adding nodes: join cluster, verify `emqx ctl cluster status`, then add to LB pool. Remove nodes gracefully — `emqx ctl cluster leave` — or clients get abrupt disconnects.



**Shared subscriptions.**

When many backend services subscribe to the same topic, every instance receives every message. **Shared subscriptions** load-balance:

```
$share/analytics-group/factory/+/telemetry
```

Only one member of `analytics-group` gets each message. Supported in EMQX, HiveMQ 4+, MQTT 5 shared subscription spec. Mosquitto requires multiple bridge consumers or an external queue — plan accordingly.



**Bridge plus cluster pattern.**

Our production layout:

1. **Edge:** Mosquitto per line, bridges telemetry to regional EMQX
2. **Regional:** 3-node EMQX cluster behind NLB
3. **Global:** EMQX rule engine republishes aggregates to a central cluster via bridge (filtered topics only)

Rules:
- Edge buffers during WAN outage (`queue_qos0_messages` carefully — memory risk)
- Cloud commands use retained + LWT only on command topics, not telemetry flood
- Idempotent consumers keyed by `(device_id, timestamp, sequence)`



**Failure modes.**

| Symptom | Cause | Fix |
|---------|-------|-----|
| Duplicate telemetry | Bridge + local subscriber both processing | Single consumer path per topic |
| Bridge loop | Bidirectional `#` bridge | Prefix isolation, one-way bridges |
| Session storm on reconnect | `cleansession false` + thousands of clients | Stagger reconnect, increase `max_inflight` |
| Cluster split-brain | Network partition | Odd node count, quorum-backed state store |
| LB idle timeout | NLB kills MQTT keepalive | Tune idle timeout > 1.5× keepalive |



**Choosing components.**

| Broker | Clustering | Bridging | Best fit |
|--------|------------|----------|----------|
| Mosquitto | No (single node) | Yes, mature | Edge, lightweight |
| EMQX | Yes, open source | Yes | Cloud/regional scale |
| HiveMQ | Yes, enterprise | Yes | Large enterprise |
| AWS IoT Core | Managed | Rules/HTTP, not classic bridge | AWS-native fleets |
| VerneMQ | Yes | Yes | Erlang shops, high fan-out |

Managed cloud MQTT removes cluster ops but limits bridge flexibility — evaluate egress costs on bridged volume.

Capacity planning should include bridge bandwidth separately from client fan-in. A site publishing 5 KB/s per device × 2,000 devices is 10 MB/s sustained — compress payloads (CBOR vs JSON) before bridging if WAN links are tight. Run game days: kill one cluster node during peak, disconnect a bridge for 30 minutes, and verify edge buffers drain without OOM. Alert on bridge connection state (`notifications_local` in Mosquitto) so ops knows when cloud is blind to a plant. Document ownership: who rotates bridge credentials, who approves new topic patterns crossing the DMZ, and which team consumes `$share` consumer groups. Without that RACI, bridges become permanent tunnels with stale ACLs. Keep a runbook entry for bridge-silent incidents — verify DNS, TLS cert expiry, and upstream connection limits before restarting edge brokers blindly.

## Common production mistakes

Teams get mqtt bridging clustering wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of mqtt bridging clustering fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MQTT Version 5.0 specification — shared subscriptions](https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html)
- [Eclipse Mosquitto bridge configuration](https://mosquitto.org/man/mosquitto-conf-5.html)
- [EMQX clustering documentation](https://www.emqx.io/docs/en/latest/deploy/cluster/create-cluster.html)
- [HiveMQ bridge documentation](https://docs.hivemq.com/hivemq/latest/user-guide/bridges.html)
- [AWS IoT Core MQTT broker limits](https://docs.aws.amazon.com/general/latest/gr/iot-core.html)
