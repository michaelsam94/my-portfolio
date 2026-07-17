---
title: "AI Agents: Partition Assignment Sticky"
slug: "agent-partition-assignment-sticky"
description: "Sticky partition assignment keeps agent event streams co-located with per-session state — fewer rebalance storms, warmer caches, and predictable tool-loop latency in Kafka consumer groups."
datePublished: "2025-02-02"
dateModified: "2025-02-02"
tags: ["AI", "Agent", "Partition"]
keywords: "sticky partition assignment, Kafka cooperative sticky assignor, agent session affinity, consumer group rebalance, partition key agent events"
faq:
  - q: "What does sticky partition assignment mean in Kafka?"
    a: "The cooperative sticky assignor tries to preserve existing partition-to-consumer mappings during rebalance, moving only the minimum partitions needed to restore balance. That reduces stop-the-world pauses compared to range or round-robin reassignment that shuffles most partitions every scale event."
  - q: "Why do agent pipelines care about partition stickiness?"
    a: "Stateful agent workers cache session context, in-flight tool approvals, and partial LLM responses in memory. If rebalance moves partitions frequently, workers cold-start caches, duplicate processing during revocation, and miss ordering guarantees users perceive as 'the agent forgot what it was doing.'"
  - q: "How should I choose partition keys for agent events?"
    a: "Use session_id or conversation_id as the Kafka message key so all turns, tool results, and heartbeat events for one agent session land on one partition. Never key by user_id alone if one user runs parallel sessions — those sessions will serialize unnecessarily."
  - q: "What is the difference between partition stickiness and sticky sessions in HTTP load balancers?"
    a: "HTTP sticky sessions route a client to the same server via cookies. Kafka sticky assignment keeps a partition on the same consumer *when possible* within a consumer group. Both pursue locality, but Kafka stickiness survives only across rebalances that do not force migration — it is cooperative, not absolute."
---
During a routine Kubernetes node drain, our agent orchestrator scaled from twelve consumers to fourteen. The consumer group used the default range assignor. Partitions reshuffled across the entire fleet. For four minutes, half the agent sessions saw duplicated tool invocations; the other half stalled waiting for cold caches to reload retrieval context from Postgres. The drain succeeded. The incident review did not.

The fix paired two ideas: **key messages by session** so related events co-locate, and **sticky assignment** so scaling events move fewer partitions. Together they keep agent workers warm on the data that matters.

## Event locality in agent architectures

A typical agent loop emits a burst of records per user turn:

```
UserMessage → PlannerDecision → ToolRequest → ToolResult → AssistantDelta → RunComplete
```

Downstream consumers include:

- A **state materializer** merging events into session snapshots
- A **billing meter** aggregating token usage
- A **human approval gate** blocking destructive tools
- An **audit archiver** writing immutable logs

The materializer and approval gate are stateful in memory. If partition 7 moves from consumer A to consumer B mid-session, B must rebuild state from compaction topic or SQL before processing the next `ToolResult` — latency spikes exactly when the user is watching the spinner.

Stickiness is not nostalgia for single-server apps. It is a **rebalance cost reducer** that makes stateful stream processing tractable without jumping straight to Kafka Streams or Flink for every workload.

## Partition keys: the prerequisite

Sticky assignment preserves mapping; keys determine mapping semantics.

```python
from confluent_kafka import Producer
import json

producer = Producer({"bootstrap.servers": "kafka:9092"})

def publish_agent_event(session_id: str, event_type: str, payload: dict):
    producer.produce(
        topic="agent.events.v1",
        key=session_id.encode("utf-8"),  # same key → same partition
        value=json.dumps({"type": event_type, **payload}).encode("utf-8"),
        headers=[("schema_version", b"1")],
    )
    producer.flush()
```

Rules that prevented cross-session interference:

| Key choice | Effect |
|------------|--------|
| `session_id` | All turns serialized per session — correct default |
| `tenant_id` | Hot tenants create hot partitions — avoid unless low volume |
| `random UUID` | Round-robin load spread — destroys ordering and cache locality |
| `tool_name` | Bizarre skew — never |

Partition count should exceed peak concurrent sessions divided by target sessions-per-partition, but stay low enough that rebalance work stays bounded. We used 48 partitions for ~2,000 concurrent sessions — roughly 40 sessions per partition average, knowing skew creates hotspots.

## Enabling cooperative sticky assignor

Kafka 2.4+ ships `CooperativeStickyAssignor`. Configure consumers explicitly — defaults still bite:

```python
from confluent_kafka import Consumer

consumer = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "agent-materializer",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
    "partition.assignment.strategy": "cooperative-sticky",
})
consumer.subscribe(["agent.events.v1"])
```

For Java clients:

```java
props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
    List.of(CooperativeStickyAssignor.class.getName()));
```

Verify in consumer group description after deploy — `partition.assignment.strategy` should list cooperative-sticky, not range.

### What changes during rebalance

Classic eager rebalance: revoke **all** partitions, reassign everything, resume. Cooperative sticky: revoke **some** partitions, assign newcomers incrementally, preserve stable mappings where balance allows.

For agent workers, that means a scale-out adds one consumer that receives ~1/N of partitions from incumbents instead of everyone trading partitions.

## Stateful consumption pattern

Combine stickiness with explicit revocation handling:

```python
running_tasks: dict[tuple[str, int], SessionState] = {}

while True:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        handle_error(msg.error())
        continue

    key = (msg.topic(), msg.partition())
    state = running_tasks.get(key)
    if state is None:
        state = SessionState.load_from_store(session_id=msg.key().decode())
        running_tasks[key] = state

    state.apply_event(json.loads(msg.value()))
    consumer.commit(asynchronous=False)

def on_partitions_revoked(revoked):
    for tp in revoked:
        state = running_tasks.pop(tp, None)
        if state:
            state.flush_to_store()
            state.close()
```

Register `on_partitions_revoked` via `consumer.subscribe(..., on_revoke=on_partitions_revoked)` in confluent-kafka or the rebalance listener API in Java. Sticky assignment reduces how often this fires; it does not eliminate the need for correct revocation.

## Static membership and session timeouts

Frequent rolling deploys trigger rebalance even with sticky assignors if consumers churn faster than `session.timeout.ms`. Two mitigations:

**Static group membership** — set `group.instance.id` to a stable pod name (StatefulSet ordinal or deployment pod UID stored in env). The broker treats instance restarts as the same member when the ID returns within session timeout.

```yaml
env:
  - name: KAFKA_GROUP_INSTANCE_ID
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
```

**Tune timeouts** — agent consumers doing long tool calls may need higher `max.poll.interval.ms` so they are not kicked mid-run. Balance against failure detection latency.

## Detecting rebalance pain

Metrics worth dashboarding:

- `kafka_consumer_rebalance_total` — spikes correlating with deploys
- **End-to-end session latency** p99 during scale events
- **Duplicate tool invocation rate** — state lost between revoke and reload
- **Per-partition lag** heatmap — sticky assignment should avoid all lag jumping uniformly

Log partition migrations at INFO during rebalance:

```
Rebalance: lost partitions [(agent.events.v1, 12)]
Rebalance: gained partitions [(agent.events.v1, 31)]
```

If gained set is nearly full partition list after adding one pod, sticky assignor is not active — check config typos and client library versions.

## When stickiness is insufficient

Move to external state store when:

- Sessions exceed memory per consumer
- Workers must survive partition moves without reload pause
- You need exactly-once semantics across multiple topics

Kafka Streams state stores or a Redis/session table keyed by `session_id` decouple processing locality from partition ownership. Sticky assignment still helps by keeping cache hit rates high, but correctness no longer depends on in-memory warmth.

## Anti-patterns observed in production

**Long synchronous tool calls inside poll loop.** Violates `max.poll.interval.ms`; consumer gets evicted; sticky assignment cannot help.

**Auto-commit enabled on stateful paths.** Duplicate processing after crash becomes user-visible double tool calls.

**Key churn mid-session.** Migrating from `user_id` to `session_id` keys reshuffles all partitions once — plan a dual-write window.

**Over-partitioning tiny deployments.** Three consumers with 256 partitions guarantees churn; start with `max(12, 3 × consumer_count)`.

## Testing rebalance behavior before production

Rebalance bugs hide until the second consumer joins. Reproduce in staging with a reduced topic:

```bash
# Create a 12-partition topic mirroring production
kafka-topics --create --topic agent.events.staging \
  --partitions 12 --replication-factor 1 \
  --bootstrap-server localhost:9092

# Start two consumers with cooperative-sticky, publish keyed traffic
kafka-console-producer --topic agent.events.staging \
  --property "parse.key=true" --property "key.separator=:" \
  --bootstrap-server localhost:9092 <<EOF
sess-001:{"type":"UserMessage"}
sess-001:{"type":"ToolRequest"}
sess-002:{"type":"UserMessage"}
EOF
```

Scale from one to three consumers while recording partition ownership per `group.instance.id`. With sticky assignment, adding the third consumer should move roughly four partitions total, not reassign all twelve. Repeat after enabling static membership — restart a single pod and confirm zero partition migration if it rejoins within session timeout.

Inject latency into `on_partitions_revoked` handlers in tests. If flush-to-store takes longer than `max.poll.interval.ms`, the consumer will churn regardless of stickiness — fix handler performance before tuning assignors.

## Ordering guarantees agents actually need

Kafka guarantees order **within a partition**, not across partitions. Agent UX usually requires:

- Tool requests and tool results for the same session stay ordered
- Heartbeats may arrive out of band on a separate topic without keys

Do not publish `AssistantDelta` streaming tokens to a keyed topic if multiple sessions multiplex through one producer thread without flushing key order — batching can reorder within the client library buffer. Per-session producer instances or partition-aware send queues prevented subtle transcript garbling in one deployment.

Sticky assignment preserves which consumer reads that ordered stream; it does not create order where keys were wrong.

## Capacity planning worksheet

Rough seats-per-partition math before go-live:

| Input | Example value |
|-------|---------------|
| Peak concurrent sessions | 3,000 |
| Events per session per minute | 8 |
| Target events/partition/minute | 600 |
| Required partitions (ceil) | `(3000 × 8) / 600 = 40` |

Round up to account for skew — one noisy integration test tenant can double traffic on its key hash bucket. Monitor per-partition byte rate in Kafka; hot partitions survive sticky assignment but still bottleneck single-threaded consumption.

## Closing

Sticky partition assignment is boring Kafka configuration until it is not — usually during the first autoscaling event on a stateful agent consumer. Pair cooperative-sticky with session-scoped message keys, explicit revocation flushing, and static membership where deploy cadence allows. The goal is not permanent affinity forever; it is **minimal partition motion** when the fleet breathes, so agent sessions keep their context without users noticing infrastructure underneath.

## Resources

- [Apache Kafka cooperative rebalancing (KIP-429)](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol)
- [Kafka sticky assignor documentation](https://kafka.apache.org/documentation/#consumerconfigs_partition.assignment.strategy)
- [Confluent consumer configuration reference](https://docs.confluent.io/platform/current/installation/configuration/consumer-configs.html)
- [Static membership in Kafka (KIP-345)](https://cwiki.apache.org/confluence/display/KAFKA/KIP-345%3A+Introduce+Static+Membership+Protocol+to+Reduce+Consumer+Rebalances)
- [Jay Kreps on log compaction and stream processing](https://www.confluent.io/blog/compaction-in-kafka/)
