---
title: "Stateful Processing with Kafka Streams"
slug: "kafka-streams-stateful-processing"
description: "Build stateful Kafka Streams applications: state stores, changelog topics, repartitioning, Interactive Queries, and recovery behavior you need before production."
datePublished: "2025-11-05"
dateModified: "2025-11-05"
tags: ["Backend", "Kafka"]
keywords: "Kafka Streams, state store, changelog, repartition, Interactive Queries, RocksDB, stateful processing"
faq:
  - q: "Where does Kafka Streams store state?"
    a: "By default, state lives in embedded RocksDB instances on each stream thread, backed by changelog topics on Kafka. On restart or rebalance, tasks rebuild RocksDB by replaying changelog partitions. State is local to the instance holding the task—there is no shared remote database unless you add one."
  - q: "Why did my Streams app create a repartition topic?"
    a: "Operations that change the key—groupByKey, groupBy, join with foreign keys—require records on partitions matching the new key. Streams automatically creates internal repartition topics and shuffles data. Each repartition adds latency and disk use; design topologies to minimize key changes."
  - q: "How long does state restoration take after deploy?"
    a: "Restoration time depends on changelog size, partition count, broker throughput, and restored state store count. Large windowed aggregations over high-cardinality keys can take tens of minutes. Use standby replicas and incremental rebalancing to reduce active restoration during rolling restarts."
---

The dashboard showed consumer lag at zero, yet the fraud alert API returned stale counts for twelve minutes after deploy. Kafka Streams was not stuck consuming—it was **restoring state** from changelog topics into fresh RocksDB directories on new pods. Nobody had modeled restoration time in the runbook. Stateful stream processing works beautifully until the first rolling update on a fat state store.

Kafka Streams is a library for turning Kafka topics into stateful applications: aggregations, joins, windowed counts, and materialized views without operating a separate cluster. State is first-class—stored locally, replicated via changelog topics, and shuffled through repartition topics when keys change.

## Topology basics

A Streams app is a DAG of processors:

```kotlin
val builder = StreamsBuilder()

val orders = builder.stream("orders", Consumed.with(Serdes.String(), orderSerde))

orders
    .groupByKey()
    .aggregate(
        { OrderStats(count = 0, total = 0L) },
        { _, order, stats ->
            stats.copy(
                count = stats.count + 1,
                total = stats.total + order.amount
            )
        },
        Materialized.`as`<String, OrderStats, KeyValueStore<Bytes, ByteArray>>("order-stats-store")
            .withKeySerde(Serdes.String())
            .withValueSerde(orderStatsSerde)
    )

val topology = builder.build()
```

`groupByKey()` assumes records are already keyed correctly—no repartition. `groupBy { it.customerId }` triggers repartition because the key changes.

Run with:

```kotlin
val props = Properties().apply {
    put(StreamsConfig.APPLICATION_ID_CONFIG, "order-stats")
    put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, "kafka:9092")
    put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG, StreamsConfig.EXACTLY_ONCE_V2)
    put(StreamsConfig.NUM_STANDBY_REPLICAS_CONFIG, 1)
}
KafkaStreams(topology, props).start()
```

`application.id` defines the consumer group and changelog topic namespace. Change it and you start fresh state—treat it like a database name.

## Changelog topics and fault tolerance

Every state store gets a compacted changelog topic (`<application-id>-<store-name>-changelog`). Every state update writes to Kafka before acknowledging processing. If a pod dies, another task assigned the same partition replays the changelog from the last checkpoint.

Changelog retention must exceed your maximum acceptable rebuild window or use standby replicas. Standbys (`num.standby.replicas=1`) consume changelog on idle tasks so failover skips cold replay.

Monitor restoration:

```bash
kafka-streams-application-reset --application-id order-stats \
  --input-topics orders  # destructive—dev only
```

In production, watch JMX metric `restore-consumer-records-lag-max`.

## Joins and repartition cost

Stream-stream joins require aligned timestamps and co-partitioned inputs—both topics must share key partitioning strategy. Stream-table joins look up table state locally; the table topic must be keyed on the join field.

KTable-KTable join on different keys forces repartition on both sides. Before adding joins, sketch partition alignment:

```
orders (key=orderId)  ── join on customerId ──►  needs selectKey + repartition
customers (key=customerId)  ───────────────────►  already keyed correctly
```

Use `repartition()` explicitly when you want control over topic names and partition counts rather than relying on auto-generated internals.

## Interactive Queries

Expose state stores through REST:

```kotlin
val streams = KafkaStreams(topology, props)
streams.start()

val provider = streams.store(
    StoreQueryParameters.fromNameAndType(
        "order-stats-store",
        QueryableStoreTypes.keyValueStore<String, OrderStats>()
    )
)

fun lookup(orderId: String): OrderStats? = provider.get(orderId)
```

Queries hit **local** state only. To query any key cluster-wide, use RPC routing that maps key → partition → host (Kafka Streams metadata API). Without routing, load balancers return 404 for keys on other instances.

For read-heavy dashboards, consider materializing to a dedicated KTable topic and serving from a separate read service—decouples query load from processing latency.

## Windowed state and retention

Windowed aggregations retain state until `window size + grace period` expires:

```kotlin
orders
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofMinutes(5)))
    .aggregate(/* ... */)
```

Grace period absorbs late-arriving records. Long grace means larger state and longer changelog replay. Set `retention.ms` on window stores consciously—default stream configs may retain more than you expect.

## Production checklist

- Size disks for RocksDB + changelog replay burst
- Set `commit.interval.ms` vs latency requirements
- Enable exactly-once only after throughput testing
- Pin `num.stream.threads` to partition count boundaries
- Alert on rebalance rate and restoration lag
- Version topology changes—adding a store creates new changelogs

Stateful Streams is operable software, not a fire-and-forget library. Treat changelog topics like database files with replication and backup policies.

## Standby replica lag

Monitor standby consumer lag—if lag grows unbounded, failover restores from changelog on critical path instead of warm standby. Scale disk IOPS for changelog topics.


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

- [Kafka Streams developer guide](https://kafka.apache.org/documentation/streams/) — core concepts and DSL reference
- [State store changelog internals](https://docs.confluent.io/platform/current/streams/architecture.html#state-store) — architecture diagram and fault tolerance model
- [Interactive Queries guide](https://kafka.apache.org/documentation/streams/developer-guide/interactive-queries.html) — metadata routing for distributed lookups
- [RocksDB tuning for Kafka Streams](https://docs.confluent.io/platform/current/streams/developer-guide/memory-mgmt.html) — memory and cache configuration
