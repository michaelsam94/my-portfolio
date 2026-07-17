---
title: "Producer Acknowledgment Tradeoffs"
slug: "llm-producer-acknowledgment-tradeoffs"
description: "Kafka producer acks (0, 1, all) trade durability for latency. How to pick the right setting for agent event pipelines, tool audit logs, and billing streams without silent data loss for teams running LLM features in production."
datePublished: "2025-02-05"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "kafka producer acks, min.insync.replicas, idempotent producer, agent event streaming, durability latency tradeoff, exactly-once semantics"
faq:
  - q: "What does acks=all actually guarantee for agent pipelines?"
    a: "It guarantees the record is written to the log on all in-sync replicas before the producer receives success. It does not guarantee consumers processed the message, that downstream tools executed correctly, or that a retry will not duplicate. Pair acks=all with idempotent producers and consumer deduplication for end-to-end correctness."
  - q: "When is acks=0 acceptable for agent workloads?"
    a: "Only for fire-and-forget telemetry where loss is statistically tolerable: high-volume debug spans, coarse-grained clickstream, or sampling metrics where dropping 1–2% does not change alerts. Never use acks=0 for billing events, audit trails, human feedback signals used in eval loops, or tool invocation records you may need to replay."
  - q: "Why do we see duplicate tool calls after broker failovers?"
    a: "The producer often retried after a timeout even though the first write succeeded. With acks=1, an old leader may have acknowledged before dying; the retry lands on the new leader as a second copy. Enable idempotence (enable.idempotence=true), use acks=all, and ensure min.insync.replicas matches your durability target."
  - q: "How does ack level interact with linger.ms and batching?"
    a: "Higher ack levels add round-trip latency per batch, which makes linger.ms and batch.size more valuable—you amortize the ack cost across many records. For low-volume agent audit topics, small batches with acks=all can feel sluggish; tune linger.ms upward or accept higher per-record latency as the price of durability."
---
A finance reconciliation job flagged the same customer twice for a $240 overage. Support pulled the thread: the agent had invoked a billing adjustment tool once, the user saw one confirmation, but two identical `tool.invoked` events sat in the audit topic with different offsets. The on-call engineer stared at the producer config—`acks=1`, retries enabled, no idempotence—and recognized a pattern from a broker rolling restart six minutes earlier.

The agent did not hallucinate a duplicate charge. The messaging layer did. Producer acknowledgment settings are not a Kafka trivia question; they are the contract between "we think we sent it" and "the cluster durably has it." Agent systems amplify the stakes because tool calls, human feedback, and retrieval cache invalidations all ride the same pipes that web apps use for click logs—except losing or duplicating those events corrupts eval datasets, billing, and incident forensics.

## What acknowledgment means on the wire

When a producer sends a record, it waits for a response from the broker leadership chain. That response is the **acknowledgment**. The `acks` producer property controls how many replicas must confirm the write before your client code unblocks:

| `acks` | Broker behavior | Typical latency | Durability |
|--------|-----------------|-----------------|------------|
| `0` | Producer does not wait for any response | Lowest | Fire-and-forget; loss on client or broker crash |
| `1` | Leader persisted to its local log | Medium | Loss if leader dies before replication |
| `all` (or `-1`) | All in-sync replicas (ISR) acknowledged | Highest | Strongest Kafka-native durability |

None of these modes tells consumers anything. Acknowledgment ends at the broker log tail. Your agent orchestrator still needs idempotent consumers, dedupe keys, or transactional boundaries if tool side effects must happen exactly once.

## Three configurations I see in production

**Telemetry fan-out (acks=0).** Some teams emit token-usage counters and coarse latency histograms with no ack wait. The producer configures aggressive batching and accepts loss during network blips because dashboards aggregate over millions of events.

```python
# High-volume, loss-tolerant agent telemetry
producer = KafkaProducer(
    bootstrap_servers=brokers,
    acks=0,
    linger_ms=20,
    batch_size=65536,
    compression_type="lz4",
    value_serializer=lambda v: json.dumps(v).encode(),
)

producer.send("agent.telemetry.v1", {
    "tenant_id": tenant,
    "model": model_id,
    "input_tokens": usage.prompt,
    "output_tokens": usage.completion,
})
# No flush required for throughput; explicit flush before shutdown
```

**Operational events (acks=1).** Default in many SDKs. Reasonable for retrieval cache purge messages where a missed purge causes stale RAG results but not financial harm—provided consumers tolerate redelivery.

```java
Properties props = new Properties();
props.put("bootstrap.servers", brokers);
props.put("acks", "1");
props.put("retries", 3);
props.put("linger.ms", 5);
props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class);
props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, JsonSerializer.class);

try (KafkaProducer<String, ToolEvent> producer = new KafkaProducer<>(props)) {
    producer.send(new ProducerRecord<>("agent.tools.v1", sessionId, event));
}
```

**Audit and billing (acks=all + idempotence).** This is the configuration that would have prevented the duplicate billing adjustment. The idempotent producer assigns a producer ID and sequence numbers per partition so retries collapse to a single log entry.

```python
producer = KafkaProducer(
    bootstrap_servers=brokers,
    acks="all",
    enable_idempotence=True,  # forces acks=all, retries>0, max.in.flight<=5
    retries=2147483647,
    max_in_flight_requests_per_connection=5,
    key_serializer=lambda k: k.encode(),
    value_serializer=lambda v: json.dumps(v).encode(),
)

future = producer.send(
    "agent.audit.v1",
    key=f"{tenant_id}:{session_id}",
    value={
        "event_type": "tool.invoked",
        "tool": "billing.adjust",
        "args_hash": stable_hash(args),
        "trace_id": trace_id,
    },
)
record_metadata = future.get(timeout=10)  # surface failure to orchestrator
```

Notice the explicit `future.get()`. Fire-and-forget sends hide broker backpressure until buffers explode. Agent orchestrators that must gate tool execution on durable audit logs should treat send failures as hard errors, not background noise.

## When acks=1 lies to you

Leader acknowledgment means the record sits on one broker's disk—not necessarily on the followers that will become the new leader after failure. During rack maintenance or an AZ outage, that gap bites:

1. Producer sends record R to leader L.
2. L appends R and acks the producer.
3. L crashes before followers replicate R.
4. Follower F becomes leader without R.
5. Producer retries (because it got a not-leader or timeout) and R appears again—duplicate—or the first copy vanishes—loss.

For agent audit trails, loss is worse than duplication because downstream compliance queries assume completeness. Duplication is fixable with idempotent keys; absence is silent.

`min.insync.replicas` (broker-side) and `acks=all` (producer-side) work as a pair. If ISR size drops below `min.insync.replicas`, producers with `acks=all` fail fast rather than writing to a single replica—a feature, not an outage, when you prefer unavailability over silent weakening of durability.

## Retries without idempotence duplicate side effects

Agent runtimes often wrap tool calls with "emit event, then execute." On retry, you get two events and potentially two Stripe refunds. Ordering fixes:

- **Idempotent producer** at the Kafka layer (sequence dedupe within a producer session).
- **Business-key dedupe** at the consumer: store `(tenant, idempotency_key)` in Redis or Postgres with a TTL covering your retry window.
- **Outbox pattern**: write the event and domain state in one database transaction; a relay process publishes to Kafka—eliminates "tool ran but event lost" races.

```sql
-- Outbox row written in same transaction as tool execution record
INSERT INTO tool_executions (id, tenant_id, tool_name, args_json, status)
VALUES ($1, $2, $3, $4, 'completed');

INSERT INTO outbox (aggregate_id, topic, payload, created_at)
VALUES ($1, 'agent.audit.v1', $5, now());
```

The relay reads `outbox`, publishes with `acks=all`, marks rows published. Your ack tradeoff moves to the relay's producer config—centralized and reviewable.

## Broker settings operators forget

Producers do not live in isolation. File these next to your ack decision:

- **`min.insync.replicas=2`** on critical topics when replication factor is 3. With `acks=all`, a single surviving replica cannot accept writes—preventing acked-but-lost scenarios.
- **`unclean.leader.election.enable=false`**. Unclean election promotes out-of-sync replicas and truncates committed data. Agent eval replay topics have been corrupted this way.
- **Compression (`lz4` or `zstd`)**. Agent payloads (retrieved chunks, tool JSON) are verbose; compression reduces cross-AZ replication time, which indirectly improves ack latency at `acks=all`.

Watch **`request.timeout.ms`** versus broker **`replica.lag.time.max.ms`**. Producers that timeout and retry while the first batch is still replicating cause duplicate sequences unless idempotence is on.

## Choosing ack level by pipeline type

| Pipeline | Suggested acks | Rationale |
|----------|----------------|-----------|
| Debug trace spans | 0 or 1 | Volume high; loss acceptable |
| RAG cache invalidation | 1 + deduping consumer | Stale cache self-heals on TTL |
| Human feedback for eval | all | Drives model selection; loss skews metrics |
| Tool invocation audit | all + idempotence | Forensics and billing disputes |
| Workflow checkpoint events | all | Resume after crash must not skip steps |

Document the choice in your topic registry. New engineers should not rediscover ack semantics per microservice.

## Measuring whether your ack policy works

Dashboards should answer two questions weekly: "Are we losing records?" and "Are we duplicating side effects?" Loss is hard to detect directly—you infer it from reconciliation gaps. Duplication shows up in consumer dedupe hit rate and finance exception queues.

Track producer metrics split by topic and ack mode:

- `record-send-rate` and `record-error-rate` per topic
- `request-latency-avg` at `acks=all`—sudden jumps often precede ISR shrinkage
- Consumer `duplicate_idempotency_key_total`—should be near zero with healthy idempotence

Run a game day: kill a broker while load tests publish audit events. Without idempotence you will count duplicates; with `acks=all` and `min.insync.replicas=2` you should see send failures or retries, not silent holes. Write down observed behavior and compare to the table in your topic registry.

## Closing thought

Acknowledgment tradeoffs are boring until a duplicate tool call reaches production finance. The agent stack does not get a special exemption: if an event gates money, safety, or eval integrity, `acks=all` with idempotence and aligned broker ISR settings is the default—you downgrade intentionally, with a written reason, not the other way around.

## Resources

- [Kafka Producer Configuration — acks](https://kafka.apache.org/documentation/#producerconfigs_acks)
- [Idempotent and Transactional Producers (Confluent docs)](https://docs.confluent.io/kafka/design/idempotent-producer.html)
- [min.insync.replicas and durability](https://kafka.apache.org/documentation/#min.insync.replicas)
- [Transactional Messaging patterns](https://www.confluent.io/blog/transactions-apache-kafka/)
- [CloudEvents spec for agent audit envelopes](https://cloudevents.io/)
