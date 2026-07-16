---
title: "Schema Registry and Avro Evolution"
slug: "kafka-schema-registry-avro"
description: "Manage Kafka schemas with Confluent Schema Registry and Avro: compatibility modes, backward-compatible evolution, and production patterns for multi-team topics."
datePublished: "2025-11-01"
dateModified: "2025-11-01"
tags: ["Backend", "Kafka"]
keywords: "Schema Registry, Avro, schema evolution, compatibility mode, BACKWARD_TRANSITIVE, Confluent serializer"
faq:
  - q: "What happens if I publish a schema that fails compatibility checks?"
    a: "Schema Registry rejects the registration with a 409 Conflict response. Producers using Confluent serializers fail at startup or first produce if they cannot fetch a valid schema ID. This is intentional—it prevents consumers from breaking on fields they cannot decode."
  - q: "Should I use BACKWARD or FULL compatibility?"
    a: "BACKWARD means new schemas can read old data—consumers upgrade first. FULL adds that old schemas can read new data, which is stricter and slows iteration. Most event pipelines use BACKWARD or BACKWARD_TRANSITIVE for consumer-driven contracts."
  - q: "How do schema IDs appear on the wire?"
    a: "Confluent serializers prepend a magic byte and four-byte schema ID before the Avro payload. Consumers fetch the schema by ID from the registry and deserialize. The ID ties each message to an immutable schema version."
---

A payments team added a required `currency` field to their Avro schema on Friday afternoon. By Saturday, three downstream services written in Go, Kotlin, and Python were throwing deserialization errors because they had not redeployed. Schema Registry did not save them—they had compatibility checks disabled on that subject. The registry is only as good as the compatibility mode you enforce and the discipline around field additions.

Schema Registry is a centralized store for Avro, JSON Schema, and Protobuf definitions used with Kafka. Producers register schemas; consumers resolve by ID. The payoff is **evolution with rules**: you can add fields, but not in ways that silently corrupt readers.

## Avro on the wire

Avro is compact and schema-driven—no field names on the wire, just values in schema order. That efficiency means reader and writer schemas must align through resolution rules.

Typical producer setup:

```kotlin
props["value.serializer"] = KafkaAvroSerializer::class.java.name
props["schema.registry.url"] = "http://schema-registry:8081"
props["auto.register.schemas"] = "false"  // production: explicit registration
```

Register schemas in CI, not at runtime:

```bash
curl -X POST http://schema-registry:8081/subjects/orders-value/versions \
  -H "Content-Type: application/vnd.scroj+json" \
  -d @orders-v2.avsc
```

Subject naming convention matters. TopicNameStrategy (`orders-value`) is default. RecordNameStrategy helps when one topic carries multiple record types.

## Compatibility modes

Set at subject or global level:

| Mode | Rule | Typical use |
|------|------|-------------|
| BACKWARD | New schema reads old data | Consumer upgrades first |
| FORWARD | Old schema reads new data | Producer upgrades first |
| FULL | Both directions | Strict libraries, slow change |
| NONE | Anything goes | Prototypes only |

Production event topics should use at least **BACKWARD**. Multi-team platforms often set **BACKWARD_TRANSITIVE** globally so new schemas must read all prior versions, not just the latest.

Test compatibility before merge:

```bash
curl -X POST http://schema-registry:8081/compatibility/subjects/orders-value/versions/latest \
  -H "Content-Type: application/vnd.scroj+json" \
  -d @orders-v3.avsc
```

Returns `is_compatible: true/false` without registering.

## Safe evolution patterns

**Adding fields** — use defaults so old readers ignore new data:

```json
{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "orderId", "type": "string"},
    {"name": "amount", "type": "long"},
    {"name": "currency", "type": "string", "default": "USD"}
  ]
}
```

**Removing fields** — safe for BACKWARD if consumers no longer need them; old producers still send the field until upgraded. Prefer deprecating in documentation before removal.

**Renaming fields** — Avro treats renames as delete+add unless you use aliases:

```json
{"name": "customerId", "type": "string", "aliases": ["userId"]}
```

**Changing types** — almost never compatible. Create a new topic or subject for breaking changes.

Never reuse field names with different types. Never change union ordering casually.

## Consumer-side schema resolution

Consumers deserialize with their local reader schema against the writer schema embedded via ID:

```kotlin
props["value.deserializer"] = KafkaAvroDeserializer::class.java.name
props["specific.avro.reader"] = "true"
```

Generate specific record classes from `.avsc` in build:

```kotlin
// build.gradle.kts
plugins { id("com.github.davidmc24.gradle.plugin.avro") version "1.9.1" }

dependencies {
    implementation("io.confluent:kafka-avro-serializer:7.6.0")
}
```

Pin generated code versions in lockstep across services. A consumer compiled against v3 fails at runtime on v4 records if compatibility was NONE and a non-default field appeared.

## Operating Schema Registry

Run registry in HA mode (multiple instances backed by Kafka topic `_schemas`). Monitor:

- Registration failure rate
- Schema count per subject (unbounded growth means abandoned subjects)
- Incompatible PR merges caught in CI vs production

Soft-delete and hard-delete APIs exist for GDPR and cleanup. Hard-delete breaks old messages that reference deleted IDs—archive schemas to Git instead.

For multi-datacenter, Schema Registry can replicate read-only or use centralized registration with local caching. Producers should not depend on cross-region registry latency on every send—serializer caches IDs after first lookup.

## When Avro is not the answer

Protobuf offers stronger codegen and gRPC alignment; JSON Schema fits teams already standardized on JSON. Avro remains the Kafka default because of Confluent tooling maturity and compact wire format. Pick one format per organizational boundary, not per team preference.

## Schema ID caching

Producers cache schema IDs; registry outage after cache warm allows producing—new producers fail. Run registry HA and monitor `_schemas` topic health.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Resources

- [Confluent Schema Registry API](https://docs.confluent.io/platform/current/schema-registry/develop/api.html) — REST endpoints for register, compatibility, config
- [Avro specification — schema resolution](https://avro.apache.org/docs/current/spec.html#Schema+Resolution) — formal rules for reader/writer pairing
- [Schema evolution best practices](https://docs.confluent.io/platform/current/schema-registry/avro.html) — Confluent guide on compatible changes
- [Apicurio Registry](https://www.apicur.io/apicurio-registry/) — open-source alternative for non-Confluent stacks
