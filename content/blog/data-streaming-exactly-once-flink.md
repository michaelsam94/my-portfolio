---
title: "Exactly-Once with Flink Checkpoints"
slug: "data-streaming-exactly-once-flink"
description: "Apache Flink checkpoints enable fault-tolerant exactly-once processing. Barrier alignment, state backends, sink idempotency, and end-to-end guarantees explained."
datePublished: "2025-08-10"
dateModified: "2025-08-10"
tags: ["Data Engineering", "Analytics"]
keywords: "Apache Flink, exactly-once, checkpoints, stream processing, state backend, Kafka Flink"
faq:
  - q: "What is exactly-once processing in Flink?"
    a: "Exactly-once means each record affects downstream state and sinks as if processed once, even across failures and restarts. Flink achieves this by coupling checkpointed operator state with transactional or idempotent sinks — end-to-end exactly-once also requires sink cooperation."
  - q: "How do Flink checkpoints work?"
    a: "JobManager injects barrier markers into streams. When an operator receives barriers from all inputs, it snapshots state asynchronously and acknowledges. On failure, Flink restores state from the latest completed checkpoint and replays sources from recorded offsets."
  - q: "Does exactly-once in Flink guarantee no duplicates in Kafka output?"
    a: "Only with two-phase commit sinks (Kafka transactional producer, JDBC XA) or idempotent upserts keyed by record ID. At-least-once processing plus non-idempotent sinks can duplicate on failure. Always validate end-to-end semantics, not just Flink's internal mode flag."
---

"Exactly-once" gets thrown around in streaming pitches until the first duplicate charge hits production and someone discovers the JDBC sink wasn't idempotent. Flink's checkpoint mechanism is real and well-engineered — but **end-to-end** exactly-once is a system property, not a checkbox in `StreamExecutionEnvironment`.

## Processing guarantees defined

| Guarantee | Meaning |
|---|---|
| At-most-once | Records may be lost on failure |
| At-least-once | Records may duplicate; none lost |
| Exactly-once | Effect as if each record processed once |

Flink's internal state updates can be exactly-once relative to checkpoint boundaries. External systems need matching semantics.

## Checkpoints and barriers

Enable checkpointing:

```java
env.enableCheckpointing(60_000); // every 60s
env.getCheckpointConfig().setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000);
env.getCheckpointConfig().setTolerableCheckpointFailureNumber(3);
```

JobManager inserts **barriers** into streams. Operators snapshot state when barriers align across inputs (aligned checkpointing). Unaligned mode reduces backpressure latency at cost of larger state — Flink 1.11+ feature for high-lag scenarios.

State lands in configured **state backend**:

```yaml
# flink-conf.yaml
state.backend: rocksdb
state.checkpoints.dir: s3://flink-checkpoints/prod/
state.savepoints.dir: s3://flink-savepoints/prod/
execution.checkpointing.externalized-checkpoint-retention: RETAIN_ON_CANCELLATION
```

RocksDB for large keyed state; heap for small jobs only.

## Kafka source and offset commit

Flink Kafka source stores offsets **in checkpoint state**, not only Kafka consumer commits:

```java
KafkaSource<String> source = KafkaSource.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setTopics("orders")
    .setGroupId("flink-orders")
    .setStartingOffsets(OffsetsInitializer.committedOffsets())
    .setValueOnlyDeserializer(new SimpleStringSchema())
    .build();
```

On restore, source rewinds to checkpointed offsets — no duplicate reads beyond at-least-once window without transactional sinks.

## Sink semantics matter

**Kafka sink with two-phase commit:**

```java
KafkaSink<String> sink = KafkaSink.<String>builder()
    .setBootstrapServers("kafka:9092")
    .setRecordSerializer(...)
    .setDeliveryGuarantee(DeliveryGuarantee.EXACTLY_ONCE)
    .setTransactionalIdPrefix("flink-orders-")
    .build();
```

Transactional IDs tie to checkpoint IDs; aborted transactions roll back on failure.

**JDBC / REST sinks** — use upsert on primary key or outbox pattern. Naive insert duplicates.

**Idempotent dedup** — maintain processed `(event_id)` in Flink state or destination table:

```java
stream
  .keyBy(Event::getEventId)
  .process(new KeyedProcessFunction<String, Event, Void>() {
    ValueState<Boolean> seen;
    // drop if eventId already in state
  });
```

## End-to-end exactly-once checklist

1. Source participates in checkpoint offset storage
2. Operators use checkpointed state, no non-checkpointed side effects
3. Sinks use 2PC or idempotent writes
4. Side effects (email send, payment) use outbox or idempotency keys — Flink won't magically dedupe HTTP POSTs

## Savepoints vs checkpoints

**Checkpoints** — automatic, recovery-focused, may delete after success.

**Savepoints** — user-triggered, portable, for upgrades and rescaling:

```bash
flink savepoint $JOB_ID s3://flink-savepoints/manual/
flink run -s s3://flink-savepoints/manual/savepoint-123 ...
```

Test savepoint restore in staging before Flink version bumps.

## Operational tuning

Checkpoint duration exceeding interval causes backlog — increase interval, tune RocksDB incremental checkpoints, reduce state size with TTL:

```java
StateTtlConfig ttl = StateTtlConfig
    .newBuilder(Duration.ofDays(7))
    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
    .build();
```

Monitor `lastCheckpointDuration`, `numberOfFailedCheckpoints`, alignment time. Chronic alignment blocking indicates skew — rebalance keys or isolate hot keys.

## State size management

Unbounded keyed state kills checkpoint performance:

```java
// Bad: state grows forever
stream.keyBy(Event::getUserId)
    .process(new KeyedProcessFunction<String, Event, Void>() {
        ListState<Event> allEvents;  // never cleared
    });

// Good: TTL on state
StateTtlConfig ttl = StateTtlConfig
    .newBuilder(Duration.ofDays(7))
    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
    .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
    .cleanupFullSnapshot()
    .build();
```

Monitor state size via Flink UI — `rocksdb.estimated-num-keys` metric. RocksDB incremental checkpoints help but don't eliminate large state cost.

## Handling late and out-of-order events

Event-time processing with watermarks:

```java
stream.assignTimestampsAndWatermarks(
    WatermarkStrategy.<Event>forBoundedOutOfOrderness(Duration.ofSeconds(10))
        .withTimestampAssigner((event, ts) -> event.getTimestamp())
)
.keyBy(Event::getOrderId)
.window(TumblingEventTimeWindows.of(Duration.ofMinutes(5)))
.allowedLateness(Duration.ofMinutes(1))
.process(new WindowProcessFunction<>() { ... });
```

Late events after watermark + allowed lateness go to side output — don't silently drop without monitoring side output volume.

## Flink vs Kafka Streams choice

| Factor | Flink | Kafka Streams |
|---|---|---|
| State size | RocksDB, terabytes | Local RocksDB, limited by disk |
| Checkpointing | Chandy-Lamport barriers | Offset-based |
| Operational complexity | JobManager + TaskManagers | Embedded in app |
| Exactly-once | Checkpoint + 2PC sinks | Transactional producer |
| Use case | Complex event processing, large state | Kafka-native transforms |

Both achieve exactly-once with proper sink configuration. Flink for complex stateful processing; Kafka Streams when pipeline is Kafka-only and team wants fewer moving parts.

## Failure modes

- **Exactly-once flag without idempotent sink** — duplicates on JDBC/HTTP sinks despite Flink guarantee
- **Unbounded state growth** — checkpoint time increases until job fails
- **Checkpoint interval < checkpoint duration** — checkpoint backlog never completes
- **Hot key skew** — one key gets all traffic; alignment blocking on that operator
- **Side effects outside Flink** — email/payment HTTP calls duplicate on restart
- **Savepoint not tested before upgrade** — incompatible state schema after Flink version bump

## Production checklist

- End-to-end exactly-once validated (source + state + sink)
- Sink uses 2PC (Kafka transactional) or idempotent upsert
- State TTL configured for keyed state
- Checkpoint duration monitored (< 50% of interval)
- Side effects use outbox or idempotency keys
- Savepoint restore tested in staging before upgrades
- Hot key skew monitored and mitigated

## Flink state backend selection

Choose state backend based on state size and recovery requirements:

| Backend | State size | Recovery speed | Best for |
|---|---|---|---|
| HashMapStateBackend | <100GB | Fast (in-memory) | Dev, small jobs |
| RocksDBStateBackend | >100GB | Slower (disk-based) | Production, large state |
| ForStStateBackend | >100GB | Faster than RocksDB | Flink 1.19+ production |

```yaml
# flink-conf.yaml
state.backend: rocksdb
state.backend.rocksdb.memory.managed: true
state.checkpoints.dir: s3://flink-checkpoints/
state.savepoints.dir: s3://flink-savepoints/
execution.checkpointing.interval: 60s
execution.checkpointing.mode: EXACTLY_ONCE
```

RocksDB with managed memory for production. HashMap only for development and small state (<10GB).

## End-to-end exactly-once validation test

Prove exactly-once semantics before production:

```python
def test_exactly_once():
    # 1. Produce N events with unique IDs
    produce_test_events(n=10000, topic="test-input")

    # 2. Run Flink job with intentional failure mid-checkpoint
    job = submit_flink_job()
    wait_for_checkpoint(job, n=2)
    kill_taskmanager(job)  # simulate failure
    wait_for_recovery(job)

    # 3. Verify output count == input count (no duplicates, no losses)
    output_count = count_sink_records("test-output")
    assert output_count == 10000, f"Expected 10000, got {output_count}"
```

Run after every Flink version upgrade and job logic change. Exactly-once is fragile — validate, don't assume.

## Resources

- [Apache Flink — Checkpointing](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/fault-tolerance/checkpointing/)
- [Flink — Kafka exactly-once connector](https://nightlies.apache.org/flink/flink-docs-stable/docs/connectors/datastream/kafka/)
- [Flink — State backends](https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/state_backends/)
- [Transactional outbox pattern (microservices.io)](https://microservices.io/patterns/data/transactional-outbox.html)
- [Google Cloud — Stream processing with Flink](https://cloud.google.com/dataflow/docs/guides/deploy-flink)
