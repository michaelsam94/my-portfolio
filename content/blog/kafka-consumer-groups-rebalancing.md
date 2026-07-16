---
title: "Kafka Consumer Groups and Rebalancing"
slug: "kafka-consumer-groups-rebalancing"
description: "Understand Kafka consumer group rebalancing: partition assignment, cooperative sticky assignors, static membership, and how to stop unnecessary stop-the-world pauses."
datePublished: "2025-10-20"
dateModified: "2025-10-20"
tags: ["Backend", "Kafka"]
keywords: "Kafka consumer group, rebalancing, cooperative sticky assignor, static membership, partition assignment, consumer lag"
faq:
  - q: "Why does my consumer pause during rebalancing?"
    a: "During a rebalance, partitions are revoked from consumers and reassigned. With the classic eager assignor, all consumers in the group stop fetching until the group coordinator finishes assignment. That stop-the-world window grows with group size. Cooperative and incremental assignors revoke only the partitions that must move, letting unaffected consumers keep processing."
  - q: "What triggers a consumer group rebalance?"
    a: "Common triggers include a consumer joining or leaving the group, session timeout when a consumer stops heartbeating, partition count changes on subscribed topics, and subscription changes. Static membership reduces rebalances when consumers restart with the same group.instance.id because the coordinator treats them as the same member."
  - q: "How many consumers should I run per topic?"
    a: "At most one consumer per partition for a given group. Extra consumers sit idle. If you have 12 partitions and need higher throughput, either add partitions (which triggers a rebalance and may require key redesign) or optimize per-partition processing. Scaling consumers beyond partition count wastes resources."
---

The on-call page fired at 2 a.m. because checkout latency spiked. The root cause was not broker failure—it was a rolling deploy that restarted twelve consumers in a two-minute window. Each restart triggered a full group rebalance, and during every rebalance every consumer stopped reading for four to eight seconds. Multiplied across six restarts, that is nearly a minute of collective idle time on a payment topic. Understanding rebalancing is not academic; it is the difference between a smooth deploy and dropped transactions.

A **consumer group** is a set of consumers sharing a `group.id` that cooperatively read partitions from subscribed topics. Kafka guarantees each partition is consumed by at most one consumer in the group at a time. The group coordinator broker tracks membership and drives **rebalancing** when that assignment must change.

## How partition assignment works

When a consumer calls `subscribe()`, it joins the group and receives an assignment from a **partition assignor**. The default in modern clients is `CooperativeStickyAssignor`, which tries to keep existing assignments stable and only moves partitions that must move.

Classic **RangeAssignor** sorted consumers and partitions alphabetically, then divided partitions in contiguous blocks. It was simple but uneven when partition counts did not divide evenly across consumers.

**StickyAssignor** (eager) minimized partition movement but still revoked all partitions during rebalance. **CooperativeStickyAssignor** (incremental) revokes only partitions being reassigned:

```java
props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
    List.of(CooperativeStickyAssignor.class.getName()));
```

On the Kotlin side with the Java client:

```kotlin
val props = Properties().apply {
    put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092")
    put(ConsumerConfig.GROUP_ID_CONFIG, "order-processor")
    put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer::class.java)
    put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer::class.java)
    put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
        CooperativeStickyAssignor::class.java.name)
}
```

After assignment, the consumer must call `poll()` regularly. Heartbeats flow through the poll loop (or a background thread in newer clients). If the broker misses heartbeats for `session.timeout.ms`, it evicts the consumer and triggers rebalance.

## Static membership and rolling deploys

Without static membership, a restarted consumer looks like a new member. The coordinator reassigns everything. **Static membership** (`group.instance.id`) tells the broker "this is the same logical consumer":

```kotlin
props[ConsumerConfig.GROUP_INSTANCE_ID_CONFIG] = "order-processor-${hostname()}"
```

Pair static IDs with `session.timeout.ms` comfortably above your worst-case restart time and `max.poll.interval.ms` above your worst-case record processing time. If processing a batch takes longer than `max.poll.interval.ms`, the consumer is kicked even though it is alive—classic cause of rebalance storms under load.

## Rebalance listeners and offset commits

Implement `ConsumerRebalanceListener` to commit offsets and release resources cleanly:

```kotlin
consumer.subscribe(topics, object : ConsumerRebalanceListener {
    override fun onPartitionsRevoked(partitions: Collection<TopicPartition>) {
        // Commit sync before losing ownership
        consumer.commitSync(currentOffsets(partitions))
        closePartitionState(partitions)
    }

    override fun onPartitionsAssigned(partitions: Collection<TopicPartition>) {
        loadStateFor(partitions)
    }
})
```

Committing on revoke prevents duplicate processing after reassignment—assuming your downstream is idempotent. With auto-commit enabled, a rebalance mid-batch can double-process records. Manual commit at batch boundaries is safer for exactly-once-ish semantics.

## Diagnosing rebalance storms

Enable INFO logging on `org.apache.kafka.clients.consumer.internals`. Watch for repeated `Revoke previously assigned partitions` followed by `Adding newly assigned partitions` within seconds.

Common fixes:

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Rebalance every few minutes | Processing exceeds `max.poll.interval.ms` | Reduce batch size, offload work, raise interval |
| Rebalance on every deploy | No static membership | Set `group.instance.id` |
| Long rebalance pause | Eager assignor or large group | Switch to cooperative sticky |
| One consumer never gets partitions | Subscription mismatch | Verify all members subscribe to same topics |

Also check broker-side `group.initial.rebalance.delay.ms` in development—it delays the first rebalance so slow-starting consumers join together. Do not copy that to production without reason.

## Capacity planning with groups

Throughput scales with partition count, not consumer count. Before adding consumers, check whether idle members already exist:

```bash
kafka-consumer-groups.sh --bootstrap-server kafka:9092 \
  --describe --group order-processor
```

The `CONSUMER-ID` column shows active members; `#PARTITIONS` per member reveals imbalance. If one consumer holds most partitions while others sit idle, assignment may be skewed or some members failed to join.

Adding partitions requires planning: keys hash to partition index, so new partitions change routing for new keys only—existing keys stay put. That is usually what you want, but consumers will rebalance immediately after partition expansion.

## Static membership and K8s StatefulSet

StatefulSet pods get stable network IDs—pair `group.instance.id` with ordinal for consumers that map partition to pod identity explicitly.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Resources

- [Consumer configs reference](https://kafka.apache.org/documentation/#consumerconfigs) — `session.timeout.ms`, `max.poll.interval.ms`, assignor settings
- [KIP-429: Cooperative Rebalancing](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol) — protocol design for incremental assignment
- [KIP-345: Static Membership](https://cwiki.apache.org/confluence/display/KAFKA/KIP-345%3A+Introduce+Static+Membership+Protocol+to+Reduce+Consumer+Rebalances) — how instance IDs reduce churn
- [Confluent consumer rebalance primer](https://www.confluent.io/blog/cooperative-rebalancing-in-kafka-streams-consumer-ksqldb/) — practical cooperative rebalance walkthrough
