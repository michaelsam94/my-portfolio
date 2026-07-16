---
title: "Data Contracts and Schema Enforcement"
slug: "data-contracts-schema-enforcement"
description: "Data contracts define what producers owe consumers — schema, SLAs, semantics. How to enforce them at the boundary with Avro, Protobuf, and CI gates."
datePublished: "2025-07-11"
dateModified: "2025-07-11"
tags: ["Data Engineering", "Analytics"]
keywords: "data contracts, schema enforcement, Avro schema registry, protobuf, breaking change detection, data mesh"
faq:
  - q: "What is a data contract?"
    a: "A data contract is a formal agreement between a data producer and consumers specifying schema, semantics, quality rules, freshness SLAs, and ownership. It turns implicit assumptions into versioned, testable artifacts — often YAML or IDL files checked into git with CI validation."
  - q: "Where should schema enforcement happen?"
    a: "At the producer boundary before data enters shared storage or streams. Validate on publish to Kafka, on API ingest, or in the warehouse landing zone. Consumer-side checks catch problems late; producer-side enforcement prevents bad data from entering the mesh."
  - q: "How do you handle breaking schema changes?"
    a: "Use expand-contract migration: add optional fields first, deploy consumers, backfill, then remove deprecated fields in a later version. Schema registries with compatibility modes (backward, forward, full) reject incompatible registrations. Communicate deprecation windows in the contract changelog."
---

The incident that sold me on data contracts: a mobile team renamed an event field from `userId` to `user_id`, pushed Friday afternoon, and broke three downstream dbt models plus a finance dashboard nobody knew depended on that stream. Nobody owned the contract because there wasn't one — just a JSON blob and hope.

Contracts exist to make producer obligations explicit and machine-enforceable before damage spreads.

## Anatomy of a contract

A useful contract specifies more than column types:

```yaml
# contracts/events/order_completed/v2.yaml
name: order_completed
version: 2.1.0
owner: team-checkout
domain: commerce

schema:
  format: avro
  file: order_completed.v2.avro.json

semantics:
  order_id: "Unique identifier from orders service. Never null after 2024-01-01."
  revenue_cents: "Gross merchandise value in USD cents, tax inclusive."

quality:
  - name: order_id_not_null
    sql: "order_id IS NOT NULL"
  - name: revenue_non_negative
    sql: "revenue_cents >= 0"

sla:
  freshness: "Events visible in lake within 15 minutes"
  availability: "99.9% daily event volume within 20% of trailing average"

lifecycle:
  deprecated_fields:
    - name: legacy_promo_code
      remove_after: "2025-12-01"
```

Consumers pin `version: 2.x` and get notified on breaking diffs. Producers can't merge without passing contract tests.

## Enforcement layers

**Compile time.** Protobuf and Avro IDLs generate typed bindings. Mobile and backend compile against generated classes — renames fail in CI, not in production.

**Registry time.** Confluent Schema Registry (or AWS Glue, Redpanda schema registry) rejects incompatible schema registrations:

```bash
# BACKWARD compatibility: new schema can read old data
curl -X POST schema-registry/topics/order_completed-value/versions \
  -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  -d @order_completed.v3.avro.json
# Returns 409 if incompatible
```

**Deploy time.** dbt tests, Great Expectations suites, and custom validators run in CI against sample payloads and production snapshots.

**Runtime.** Kafka interceptors or ingestion Lambdas validate each batch against the registered schema. Quarantine or DLQ invalid records; don't poison the lake.

## Expand-contract for schema evolution

Database migration wisdom applies to events:

1. **Expand** — add new optional field `customer_tier`
2. **Migrate** — producers populate it; consumers read with defaults
3. **Contract** — make required once backfill completes
4. **Remove** — drop deprecated field in major version bump

Never rename in place. Add `user_id`, dual-write both fields for one release, deprecate `userId` in the contract changelog, remove after the sunset date.

## Producer vs consumer responsibilities

| Producer | Consumer |
|---|---|
| Publish versioned schema | Pin supported versions |
| Maintain SLA metrics | Handle optional fields gracefully |
| Announce deprecations | Migrate before sunset |
| Run quality checks pre-publish | Report contract violations |

Data mesh rhetoric puts domain teams in the producer seat. Contracts are how other domains trust their output without weekly sync meetings.

## Tooling landscape

- **Buf** for Protobuf breaking-change detection in CI
- **Schema Registry** compatibility policies for Avro/JSON Schema
- **dbt contracts** (model contracts, enforced columns) for warehouse tables
- **Soda / Great Expectations** for semantic rules beyond types
- **Custom gitops** — contract YAML + diff bot commenting on PRs

Pick one source of truth. Duplicating schema in OpenAPI, Avro, and a wiki guarantees drift.

## Organizational habits

Contracts fail when treated as documentation debt. Embed them in the producer repo, same PR as code changes. Breaking-change PRs require consumer ack from CODEOWNERS files listing downstream teams.

Start with high-blast-radius streams: orders, payments, identity. Template the YAML so new events aren't blank-slate work. Measure violations quarantined at ingress — that number should trend down, not up.

## Contract versioning and compatibility

Schema evolution rules must be explicit in every contract:

```yaml
# orders-created-v2.contract.yaml
schema:
  type: object
  required: [order_id, customer_id, amount_cents, currency]
  properties:
    order_id: { type: string, format: uuid }
    customer_id: { type: string }
    amount_cents: { type: integer, minimum: 0 }
    currency: { type: string, enum: [USD, EUR, GBP] }
    discount_cents: { type: integer, default: 0 }  # added in v2

compatibility:
  backward: true   # new consumers read old events
  forward: false  # old consumers cannot read new events without migration
  version: "2.0.0"
  deprecated_fields:
    - name: total_amount
      sunset: "2025-06-01"
      replacement: amount_cents
```

Backward compatible: add optional fields. Forward compatible: don't remove required fields without deprecation period.

## CI enforcement pipeline

Block breaking changes at PR time:

```yaml
# .github/workflows/data-contracts.yml
- name: Validate schema compatibility
  run: |
    buf breaking --against '.git#branch=main' proto/
    confluent schema-registry compatibility --schema schema.avsc --level BACKWARD
    dbt parse && dbt test --select tag:contract
```

Producer PR that breaks compatibility requires explicit consumer team approval in CODEOWNERS. Automated comment on PR lists affected downstream consumers.

## Quarantine and dead letter handling

Violating events quarantined at ingress — never silently dropped:

```python
async def ingest_event(raw_event: bytes, schema: Schema):
    try:
        validated = schema.validate(raw_event)
        await kafka.produce("orders", validated)
    except SchemaValidationError as e:
        await quarantine_store.save(raw_event, error=str(e), schema_version=schema.version)
        metrics.increment("contract.violations", tags={"schema": schema.name})
        if violation_rate() > 0.01:
            alert("Schema violation rate >1%", severity="P2")
```

Quarantine store enables replay after schema fix. Violation rate trending up indicates producer bug, not consumer issue.

## Failure modes

- **Contract as wiki documentation** — drifts from actual schema within weeks
- **Breaking change without consumer notification** — downstream pipelines fail silently
- **Violations silently dropped** — data loss without alert
- **Schema duplicated in 3 places** — OpenAPI, Avro, dbt; guaranteed drift
- **No compatibility level defined** — producer and consumer disagree on safe changes

## Production checklist

- Contract YAML in producer repo, same PR as schema change
- CI blocks backward-incompatible changes without consumer ack
- Violations quarantined at ingress with alerting on rate >1%
- Single source of truth (Buf/Schema Registry/dbt contracts)
- Deprecation period documented for field removals
- Violation count tracked and trending down over time

## Resources

- [Confluent — Schema Registry compatibility types](https://docs.confluent.io/platform/current/schema-registry/avro.html#schema-evolution-and-compatibility)
- [Buf — Breaking change detection for Protobuf](https://buf.build/docs/breaking/overview)
- [dbt model contracts](https://docs.getdbt.com/docs/collaborate/govern/model-contracts)
- [Chad Sanderson — The Data Contract book and patterns](https://datacontract.com/)
- [Google Cloud — Protobuf schema design best practices](https://protobuf.dev/programming-guides/dos-donts/)
