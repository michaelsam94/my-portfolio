---
title: "Kafka Partition Key Design"
slug: "kafka-partitioning-key-design"
description: "Design Kafka partition keys for ordering, fairness, and scale: hash routing, hot partitions, composite keys, and when to add partitions without breaking consumers."
datePublished: "2025-10-28"
dateModified: "2025-10-28"
tags: ["Backend", "Kafka"]
keywords: "Kafka partition key, key design, hot partition, murmur2 hash, ordering guarantee, partition count"
faq:
  - q: "Does Kafka guarantee global ordering?"
    a: "Kafka guarantees order only within a single partition. Records with the same key land on the same partition and retain production order. There is no ordering guarantee across partitions or across topics. If you need all events for entity X processed in sequence, every event for X must share a key that maps to one partition."
  - q: "What makes a bad partition key?"
    a: "Keys with low cardinality—status flags, boolean fields, or a constant null—route most traffic to a handful of partitions and create hot spots. Keys that change over an entity's lifetime break ordering because later events may hash to a different partition than earlier ones."
  - q: "Can I change partition count without breaking key semantics?"
    a: "Adding partitions changes the hash modulus for new keys only if you use the default partitioner—existing keys stay on their original partition index. Consumers rebalance immediately. Do not reduce partition count; that requires migration. Plan key design and partition count together at topic creation."
---

We shipped a fraud-detection pipeline keyed on `country_code`. With 195 possible values and 48 partitions, it looked reasonable. Then 80% of payment volume came from three countries, three partitions ran hot, and p99 latency on those consumers hit eight seconds while the other forty-five partitions idled. The fix was not "add more consumers"—it was re-keying on `merchant_id`, which had millions of distinct values and spread load evenly. Partition key design is load balancing with ordering constraints baked in.

When you produce a record, Kafka hashes the key with murmur2 and selects `hash(key) % partitionCount`. Same key, same partition, strict order within that partition. No key means round-robin assignment—good for load spreading, bad if downstream assumes per-entity ordering.

## Choosing a key: ordering vs parallelism

Start from the question: **what entity must stay ordered?**

- Order lifecycle events → key = `orderId`
- User session analytics → key = `userId` (accept hot users)
- IoT sensor readings → key = `deviceId`
- Audit log fan-out → null key or random UUID for max parallelism

```kotlin
fun publishOrderEvent(producer: Producer<String, OrderEvent>, event: OrderEvent) {
    producer.send(
        ProducerRecord(
            "orders",
            event.orderId,  // ordering per order
            event
        )
    )
}
```

If multiple entity types need ordering, pick the narrowest scope. Payment events keyed on `customerId` serialize all payments for a customer—sometimes required for credit limits, sometimes unnecessarily strict.

## Detecting hot partitions

Hot partitions show up as one consumer lagging while siblings stay flat:

```bash
kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list kafka:9092 --topic payments --time -1
```

Compare end offsets per partition. Sustained skew means skewed keys, not slow consumers.

Mitigations:

1. **Salting** — append `hash(entityId + salt) % N` for high-volume entities only. Downstream must merge salted partitions, so this adds complexity.
2. **Re-key** — move to a higher-cardinality field (`merchantId` instead of `countryCode`).
3. **Dedicated topic** — isolate whale accounts into a separate topic with manual assignment.

Salting example for a known hot merchant:

```kotlin
fun keyFor(merchantId: String, eventId: String): String {
    return if (merchantId in HOT_MERCHANTS) {
        "$merchantId-${eventId.hashCode() % 8}"
    } else {
        merchantId
    }
}
```

Ordering per merchant breaks across salt buckets—only use when business rules allow parallel processing for that merchant.

## Composite and custom keys

Sometimes the natural key is composite:

```kotlin
data class SessionKey(val userId: String, val deviceId: String) {
    fun serialize() = "$userId:$deviceId"
}
```

Keep keys compact strings or bytes. Large JSON blobs as keys waste space in logs and increase hash cost.

Custom partitioners are rarely worth it. The default murmur2 partitioner is battle-tested. Custom logic belongs in routing SMTs or upstream topic selection, not in a bespoke partitioner class that future maintainers must reverse-engineer.

## Null keys and tombstones

Compacted topics use null values as tombstones. The key still determines compaction grouping—a null key tombstone behaves differently and is usually a mistake. For compacted changelog topics, always set a stable business key.

For fire-and-forget telemetry where order does not matter, null keys spread load:

```kotlin
producer.send(ProducerRecord("metrics", null, metricPayload))
```

Document this explicitly so the next developer does not "fix" null keys by adding a constant string—which would route everything to one partition.

## Partition count planning

More partitions increase parallelism ceiling and broker metadata overhead. Rule of thumb: start with enough partitions to meet peak throughput on a single broker's disk and network, then revisit after load tests.

When increasing partitions:

```bash
kafka-topics.sh --bootstrap-server kafka:9092 \
  --alter --topic orders --partitions 96
```

Existing keys stay on partitions 0..N-1 where they already lived. New keys hash across the expanded range. Consumers rebalance; Kafka Streams repartition tasks may rebuild state. Schedule partition increases during maintenance windows.

Never key on fields you do not control from upstream—auto-generated UUIDs per event destroy ordering; timestamps cluster during traffic spikes.

## Tombstone ordering

Compacted topics require tombstone after final update for same key—ordering of tombstone vs last value matters for consumers rebuilding state.


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

- [Kafka partitioning and ordering](https://kafka.apache.org/documentation/#intro_concepts_and_terms) — official semantics for keys and partitions
- [Producer partitioner behavior](https://kafka.apache.org/documentation/#producerconfigs) — default partitioner and sticky batching
- [Confluent: partition strategy](https://www.confluent.io/blog/how-to-choose-the-number-of-topic-partitions/) — sizing partition count with throughput math
- [Handling hot partitions in practice](https://www.confluent.io/blog/optimizing-kafka-producer-performance/) — producer-side tuning when skew appears
