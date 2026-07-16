---
title: "Exactly-Once Semantics in Kafka"
slug: "kafka-exactly-once-semantics"
description: "Kafka exactly-once semantics explained: idempotent producers, transactions, read-process-write patterns, and where EOS ends and your application begins."
datePublished: "2025-10-24"
dateModified: "2025-10-24"
tags: ["Backend", "Kafka"]
keywords: "Kafka exactly once, idempotent producer, transactions, read_committed, EOS, Kafka Streams processing guarantee"
faq:
  - q: "Does Kafka exactly-once mean my entire pipeline is duplicate-free?"
    a: "No. Kafka EOS applies to produce and consume-and-produce within a transactional boundary against Kafka itself. The moment you write to a database, call an HTTP API, or send email, duplicates can reappear unless those side effects are idempotent or participate in the same transaction—which they usually do not."
  - q: "What is the difference between idempotent producers and transactions?"
    a: "Idempotent producers deduplicate retries within a single producer session using sequence numbers per partition. Transactions extend that to atomic multi-partition writes and allow consume-transform-produce loops where offsets and output records commit or abort together."
  - q: "When should I use read_committed isolation?"
    a: "Consumers that must not see uncommitted or aborted transactional records should set isolation.level=read_committed. This adds slight latency because consumers wait for open transactions to complete before delivering data. Analytics pipelines that tolerate duplicates often stay on read_uncommitted."
---

"We need exactly-once delivery." I hear it in every Kafka architecture review. What people usually mean is "no duplicate charges" or "no double inventory decrements." Kafka can get you close inside its own boundaries, but EOS is a bundle of broker features and client settings—not a magic flag that sanitizes your side effects.

Exactly-once in Kafka means: a record appears once in a topic from the perspective of a transactional consumer, even when producers retry and brokers fail over. Outside that contract, you still need idempotent handlers, dedup keys, or outbox patterns.

## Idempotent producers: the foundation

Before transactions, enable idempotence on the producer:

```kotlin
val producer = KafkaProducer<String, OrderEvent>(Properties().apply {
    put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092")
    put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, "true")
    put(ProducerConfig.ACKS_CONFIG, "all")
    put(ProducerConfig.RETRIES_CONFIG, Int.MAX_VALUE)
    put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, "5")
    put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer::class.java)
    put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer::class.java)
})
```

Idempotence assigns a producer ID (PID) and monotonic sequence numbers per partition. If a batch retry arrives after the broker already wrote it, the broker deduplicates. This fixes the classic "network timeout, client retries, two copies land" failure without transactions.

`enable.idempotence=true` forces `acks=all` and caps in-flight requests—do not override those casually.

## Transactions: atomic multi-topic writes

Transactions let you write to multiple partitions atomically and tie consumer offsets to produced output. Configure a transactional producer:

```kotlin
props[ProducerConfig.TRANSACTIONAL_ID_CONFIG] = "order-fanout-1"

val producer = KafkaProducer<String, String>(props)
producer.initTransactions()

try {
    producer.beginTransaction()
    producer.send(ProducerRecord("orders-confirmed", key, value))
    producer.send(ProducerRecord("analytics-events", key, analyticsPayload))
    producer.commitTransaction()
} catch (e: Exception) {
    producer.abortTransaction()
    throw e
}
```

The `transactional.id` must be unique per producer instance. If a producer with the same ID restarts, the broker fences the old instance—preventing zombie writers after failover.

For consume-transform-produce, pass consumer offsets to the producer inside the transaction:

```kotlin
producer.beginTransaction()
records.forEach { record ->
    val output = transform(record)
    producer.send(ProducerRecord("output-topic", record.key(), output))
}
producer.sendOffsetsToTransaction(offsets, consumer.groupMetadata())
producer.commitTransaction()
```

If anything fails, `abortTransaction()` rolls back produced records and offset commits together.

## read_committed and what consumers see

Transactional records are invisible to `read_committed` consumers until commit. Set on the consumer:

```kotlin
props[ConsumerConfig.ISOLATION_LEVEL_CONFIG] = "read_committed"
```

Downstream lag can spike when a transactional producer crashes mid-transaction—the broker aborts open transactions after `transaction.timeout.ms`, but until then consumers block at the aborted batch boundary.

Monitor `transactional-id` fencing events and `LastStableOffset` lag on compacted topics used by Streams.

## Kafka Streams processing guarantees

Kafka Streams exposes three processing guarantees via `processing.guarantee`:

- `at_least_once` — default, duplicates possible on failure
- `exactly_once_v2` — transactional EOS against internal changelog topics

```properties
processing.guarantee=exactly_once_v2
```

EOS v2 uses broker transactions under the hood. Changelog topics multiply; disk and replication load increase. For high-throughput stateful apps, measure before enabling in production.

Streams handles offset commits and repartition topics transactionally. Your `foreach` sink that writes to Postgres still duplicates unless the JDBC write is idempotent.

## Where EOS stops

These side effects need separate design:

| Side effect | EOS coverage | Typical mitigation |
|-------------|--------------|-------------------|
| Kafka → Kafka | Full with transactions | Transactional producer + read_committed |
| Kafka → Postgres | None | Upsert on primary key, outbox table |
| Kafka → HTTP webhook | None | Idempotency-Key header, dedup store |
| Kafka → S3 | Partial | Object keys with version ids, conditional writes |

The **transactional outbox** pattern writes business data and an outbox row in one DB transaction, then a separate connector publishes outbox rows to Kafka. Duplicates shrink to connector retries, which idempotent consumers handle.

## Operational costs of EOS

Transactions add overhead: longer commit paths, additional coordinator state, fencing on producer restart. Run fewer transactional producers with stable IDs rather than creating a new transactional ID per request.

Upgrade brokers and clients together when moving EOS versions—transaction protocol evolved between 2.4 and 3.x. Test failure scenarios: kill producers mid-transaction, bounce brokers, verify consumers never see partial fan-out.

## Producer fencing monitoring

Alert on `ProducerFencedException`—indicates duplicate transactional.id or zombie producer after long GC pause. Fix instance ID assignment, not retries blindly.


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

- [Kafka transactions documentation](https://kafka.apache.org/documentation/#transactions) — broker settings and protocol overview
- [Idempotent producer internals (Confluent)](https://www.confluent.io/blog/idempotent-producer/) — sequence numbers and PID fencing explained
- [Kafka Streams processing guarantees](https://docs.confluent.io/platform/current/streams/developer-guide/config-streams.html#processing-guarantee) — exactly_once_v2 configuration and trade-offs
- [Transactional messaging patterns](https://microservices.io/patterns/data/transactional-outbox.html) — outbox pattern for cross-system consistency
