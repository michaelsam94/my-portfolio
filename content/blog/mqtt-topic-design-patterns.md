---
title: "MQTT Topic Design Patterns"
slug: "mqtt-topic-design-patterns"
description: "Design MQTT topic hierarchies that scale: naming conventions, wildcard realities, ACL alignment, and avoiding per-device topic explosions that break brokers."
datePublished: "2025-09-08"
dateModified: "2025-09-08"
tags: ["IoT", "MQTT", "Architecture"]
keywords: "MQTT topic design, MQTT topic hierarchy, MQTT wildcards, MQTT ACL topics, IoT topic naming"
faq:
  - q: "How deep should an MQTT topic hierarchy be?"
    a: "Deep enough to encode identity and purpose for ACLs and subscriptions — typically 4–7 levels — but not so deep that every attribute becomes a segment. Put high-cardinality IDs in a stable position; don't invent a new top-level for every feature."
  - q: "Should device IDs be near the root or the leaf?"
    a: "Common pattern: `tenant/region/device/{deviceId}/telemetry/{metric}`. Putting `deviceId` before wildcards lets you ACL a device to its own subtree. Avoid `telemetry/#` globally for clients that shouldn't see everything."
  - q: "What's wrong with a new topic per message type randomly named?"
    a: "Subscribers and ACLs can't evolve. Standardize verbs (`telemetry`, `command`, `state`, `event`) and payload schemas. Version payloads in the message or a version segment when breaking."
---

MQTT topics are your API. Bad names become ACL spaghetti and subscription storms. Good names make brokers, bridges, and humans predictable. I've inherited fleets where every firmware engineer invented their own top-level (`data`, `Data`, `telemetry`, `tel`) — the broker survived; the ops team did not.

Treat topic design as a public contract: version it, document it, and review changes like API breaking changes.

## A durable pattern

```
{org}/{env}/{domain}/{deviceId}/{channel}/{name}
```

Example for EV chargers:

```
acme/prod/evse/sn-1004/telemetry/power
acme/prod/evse/sn-1004/command/set_limit
acme/prod/evse/sn-1004/state/online
acme/prod/evse/sn-1004/event/fault
```

Why this shape works:

- **`org` / `env`** — hard isolation between tenants and stages; never share prod/test prefixes
- **`domain`** — product line or bounded context (`evse`, `meter`, `gateway`)
- **`deviceId`** — stable hardware identity early enough for ACLs
- **`channel`** — small enum: `telemetry`, `command`, `state`, `event`, `config`
- **`name`** — specific metric or command

Keep `channel` closed-world. If someone needs a fifth channel, debate it — don't invent `misc`.

## Wildcards and blast radius

| Wildcard | Meaning | Typical use |
|---|---|---|
| `+` | Single level | `acme/prod/evse/+/state/online` |
| `#` | Multi-level (trailing only) | `acme/prod/evse/sn-1004/#` |

Rules of thumb:

- Field devices should subscribe narrowly — usually their own `command` and `config` subtrees
- Cloud ingest can use broader subscriptions, but shard by `org`/`region` so one shared subscription doesn't become a single point of overload
- Never give a device credential access to `acme/prod/#`

Shared subscriptions (MQTT 5) help competing cloud consumers; they don't fix a topic layout that dumps the whole fleet into one queue without keys.

## ACL alignment

Design topics so policies are **prefix-based**:

```
# Device sn-1004 identity
publish:   acme/prod/evse/sn-1004/telemetry/#
publish:   acme/prod/evse/sn-1004/state/#
publish:   acme/prod/evse/sn-1004/event/#
subscribe: acme/prod/evse/sn-1004/command/#
subscribe: acme/prod/evse/sn-1004/config/#
```

If your ACL language needs regex hell or per-metric exceptions, the hierarchy is wrong. The topic tree should make the least-privilege story obvious to a human reading the policy file.

Bridge rules (site ↔ cloud) should rewrite or strip prefixes deliberately — don't bridge `+/+/+/+/command/#` from the internet into the plant network.

## Payloads vs topics

Put **identity and routing** in the topic; put **values and units** in the payload (JSON, CBOR, Protobuf). Anti-pattern:

```
acme/prod/evse/sn-1004/telemetry/power/watts/1234   # value in path — explosion
```

Better:

```
topic:   acme/prod/evse/sn-1004/telemetry/power
payload: {"ts":1710000000,"w":1234,"phase":"l1"}
```

Version breaking payload changes with a field (`schema: 2`) or a rare topic segment (`…/telemetry/v2/power`). Prefer payload versioning so ACLs stay stable.

## Retained messages and LWT

Align retained usage with `state` channels — `state/online` as retained + Last Will is a classic pattern. Don't retain high-frequency `telemetry` (broker memory and stale-read bugs). Document retained/LWT behavior alongside the topic list; see [retained messages and last will](https://blog.michaelsam94.com/mqtt-retained-messages-last-will/).

## Anti-patterns

- **PII in topic segments** — emails, plate numbers, street addresses show up in broker logs and ACL files
- **Unbounded topic creation** — unique topic per event id exhausts broker memory indexes
- **Case and spelling drift** — `Telemetry` vs `telemetry` is two APIs
- **Command topics without authz** — any publisher on the broker namespace should not write `command`
- **Skipping `env`** — one bad test client publishing into prod paths

## Migration without a flag day

When renaming:

1. Publish dual-write to old and new topics for a release
2. Move subscribers
3. Deprecate old paths with metrics on residual traffic
4. Drop old ACLs last

Topic design is security design. Sketch ACLs and fan-in before you ship a million publishers — renaming later is a fleet firmware problem.

## Shared subscription groups

MQTT brokers deliver each message once per subscription group — use for load-balanced consumers:

```
# Three workers share load for same topic pattern
Worker 1: SUBSCRIBE $share/processors/telemetry/+/metrics
Worker 2: SUBSCRIBE $share/processors/telemetry/+/metrics
Worker 3: SUBSCRIBE $share/processors/telemetry/+/metrics
```

Without shared subscriptions, every worker receives every message — triple processing, triple cost. Shared groups require broker support (EMQX, HiveMQ, Mosquitto 2.x with config).

## QoS selection guide

| QoS | Delivery | Use case |
|-----|----------|----------|
| 0 | At most once | Telemetry, metrics (loss OK) |
| 1 | At least once | Commands, state updates (dedupe required) |
| 2 | Exactly once | Billing events, critical config (expensive) |

QoS 2 on high-frequency telemetry will melt broker CPU. Use QoS 0 for 1 Hz sensor data, QoS 1 for commands with idempotent handlers.

## Topic length and broker limits

Most brokers cap topic length at 65535 bytes but practical limit is lower. Keep segments short:

- `t/acme/p1/d42/telemetry` not `tenant/acme-corporation-inc/production/device-serial-ABC123/telemetry/v2/metrics`
- Hash device IDs in topic if privacy matters: `d/a1b2c3/telemetry`

Monitor broker topic count — unbounded unique topics (one per session ID) exhaust memory indexes.

Pair with [IoT OTA updates rollback](https://blog.michaelsam94.com/iot-ota-updates-rollback/) when command topics trigger firmware deployments.

## Common production mistakes

Teams get mqtt topic design patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of mqtt topic design patterns fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MQTT 5.0 specification](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)
- [HiveMQ — MQTT topics & wildcards](https://www.hivemq.com/blog/mqtt-essentials-part-5-mqtt-topics-best-practices/)
- [EMQX — Topic design](https://www.emqx.com/en/blog/advanced-features-of-mqtt-topics)
- [MQTT Sparkplug B](https://sparkplug.eclipse.org/) — industrial topic conventions worth reading even if you don't adopt it
---
