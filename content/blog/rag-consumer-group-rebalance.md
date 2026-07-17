---
title: "Kafka Consumer Group Rebalance: Causes and Mitigations"
slug: "rag-consumer-group-rebalance"
description: "Survive Kafka consumer group rebalances in agent pipelines—cooperative sticky assignors, partition revocation hooks, offset commit ordering, and LLM work that survives stop-the-world pauses."
datePublished: "2025-01-30"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Consumer"]
keywords: "Kafka consumer group rebalance, cooperative sticky assignor, partition revocation, agent event processing, consumer lag, rebalance listener"
faq:
  - q: "Why do agent pipelines feel rebalance pain more than CRUD consumers?"
    a: "Agent handlers often hold long-running LLM calls, open WebSocket tool sessions, and in-memory conversation state tied to partition keys. A classic rebalance revokes partitions mid-flight, causing duplicate tool invocations or orphaned runs when offsets commit out of order. Short poll intervals do not help if processing takes minutes."
  - q: "Should agent consumers use cooperative or eager rebalancing?"
    a: "Prefer cooperative-sticky assignors (Kafka 2.4+) so consumers finish in-flight work on partitions they retain before losing others. Eager rebalance stops the world—every consumer drops all partitions, flushing partial agent runs. Cooperative reduces duplicate processing and tail latency spikes during deploys."
  - q: "When is it safe to commit offsets during rebalance?"
    a: "Commit only for partitions you still own and only after side effects are durable. On revocation callback, stop reading new messages, drain or checkpoint in-flight agent steps, write dedup records, then commit. Never commit offsets for partitions already revoked—another consumer may have started processing."
---
Deploy night looked clean: new agent worker pods passed health checks, consumer lag was flat, and the canary sat at ten percent. Then lag climbed from 200 to 40,000 in twelve minutes—not because throughput dropped, but because every pod entered a rebalance loop. Each worker lost partitions mid-LLM-call, retried from uncommitted offsets, and triggered another group join. The group coordinator was doing its job. Our consumer code was not.

Consumer group rebalance is the hidden scheduler of agent infrastructure. Every scale event, deploy, session timeout, and `max.poll.interval.ms` breach reshuffles which pod owns which agent run queue. If you treat rebalance as a Kafka implementation detail, you will duplicate billable tokens, lose tool results, and wonder why staging never showed the failure.

## What rebalance actually does

A consumer group is a contract: each partition of a subscribed topic is assigned to exactly one consumer instance at a time. When membership changes, the group rebalances—partitions move between consumers.

Common triggers:

- Pod added or removed during HPA or deploy
- Consumer exceeds `max.poll.interval.ms` while waiting on a slow LLM
- Network partition causes session timeout
- Subscription change or manual `partitions.revoke`

Classic **eager** rebalance (range or round-robin assignors) revokes **all** partitions from **all** members, then reassigns. During the pause, no consumption happens group-wide. **Cooperative** protocols revoke only partitions that must move; unaffected consumers keep processing.

For data-intensive workloads measured in seconds to minutes per message, stop-the-world pauses are expensive. Default to `CooperativeStickyAssignor`:

```java
props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
    List.of(CooperativeStickyAssignor.class.getName()));
```

Verify your Kafka broker version and client library support cooperative protocols end-to-end—mixed assignors in one group cause opaque protocol errors.

## The application-specific failure modes

Generic consumers read, transform, write. Agent consumers orchestrate:

```
Partition message → load session → plan → LLM call(s) → tool calls → persist run state → commit offset
                         ↑__________________________________________|
                              may span 30–180 seconds
```

When rebalance revokes a partition mid-run:

| Failure | Symptom |
|---------|---------|
| Offset committed before side effects | Lost agent step on crash |
| Side effects before offset, no dedup | Duplicate tool calls after redelivery |
| In-memory session discarded on revoke | Orphan run stuck in "running" |
| LLM call continues after revoke | Two consumers mutate same external resource |

The fix is not "make LLM faster" alone—it is rebalance-aware lifecycle management.

## RebalanceListener: the hook that matters

Implement `ConsumerRebalanceListener` (Java) or equivalent callbacks in your client wrapper:

```java
@Override
public void onPartitionsRevoked(Collection<TopicPartition> partitions) {
  for (TopicPartition tp : partitions) {
    inFlightTracker.awaitDrain(tp, Duration.ofSeconds(120));
    checkpointStore.flush(tp);
    // commit sync for revoked partitions only
    Map<TopicPartition, OffsetAndMetadata> offsets =
        inFlightTracker.committedOffsetsFor(tp);
    if (!offsets.isEmpty()) {
      consumer.commitSync(offsets);
    }
    inFlightTracker.clear(tp);
  }
}

@Override
public void onPartitionsAssigned(Collection<TopicPartition> partitions) {
  for (TopicPartition tp : partitions) {
    runRegistry.resumeInterruptedRuns(tp);
  }
}
```

**On revoke:** stop accepting new messages for lost partitions, wait for in-flight agent runs to reach a checkpoint or cancel gracefully, commit offsets for completed work, release resources.

**On assign:** reload idempotency state, resume runs that were checkpointed but not finished, warm caches scoped to new partitions.

Never block revoke callbacks longer than broker tolerance—if drain exceeds limits, persist failure state to a dead-letter path and commit through that offset with explicit audit.

## max.poll.interval.ms and long agent steps

Kafka assumes the consumer thread will poll frequently. Agent handlers violate that assumption when they process one message for minutes.

Options:

1. **Decouple poll from processing** — classic queue pattern: poller thread enqueues, worker pool processes, separate committer tracks completion. Poll loop stays hot; workers respect partition ownership flags.

2. **Increase `max.poll.interval.ms`** — acceptable with cooperative rebalance and bounded concurrency, but raises time-to-detection for truly dead consumers.

3. **Break agent runs into smaller events** — emit `step.completed` messages instead of one giant handler. Rebalance then revokes between steps, not mid-tool-call.

```typescript
// Poll thread enqueues; workers check ownership before side effects
async function workerLoop(queue: AsyncQueue<Record>) {
  for await (const record of queue) {
    if (!ownership.owns(record.partition)) continue;
    await processAgentEvent(record);
    if (ownership.owns(record.partition)) {
      await commitOffset(record);
    }
  }
}
```

Most production stacks converge on (1) plus (3): event-sourced steps with short poll loops.

## Sticky assignment and rolling deploys

Sticky assignors minimize partition movement when only one consumer joins or leaves—critical during rolling Kubernetes deploys. Fewer partition moves mean fewer revoke storms and less duplicated LLM spend.

Pair sticky assignment with **gradual rollouts**:

- Surge one new replica before terminating old (`maxUnavailable: 0`)
- Use PodDisruptionBudgets so Kubernetes does not evict half the group at once
- Stagger consumer group member joins with short jitter to avoid thundering herd

Monitor `rebalance.rate` and `rebalance.duration` as first-class SLOs, not debug logs.

## Idempotency across rebalance and redelivery

Rebalance and at-least-once delivery overlap: a revoked consumer may have processed but not committed; the assignee redelivers. Every agent side effect needs an idempotency key stored **before** irreversible work:

```sql
CREATE TABLE agent_step_dedup (
  idempotency_key TEXT PRIMARY KEY,
  partition       INT NOT NULL,
  offset          BIGINT NOT NULL,
  status          TEXT NOT NULL, -- 'started', 'completed', 'failed'
  updated_at      TIMESTAMPTZ NOT NULL
);
```

On redelivery, if status is `completed`, skip processing and commit offset. If `started` without completion, implement recovery policy: resume if checkpoint exists, fail to DLQ if stuck beyond TTL.

Partition key design matters: use `tenant_id` or `run_id` so all steps for one agent run land on one partition—rebalance moves whole runs, not half a conversation.

## Observability during rebalance

Dashboards should answer: is lag real or rebalance noise?

Track per partition:

- `consumer_lag`
- `in_flight_agent_runs`
- `revoke_drain_seconds`
- `duplicate_step_detected` (dedup hits on processing)

Alert when rebalance frequency exceeds baseline—often signals flapping pods, too-short session timeouts, or LLM-induced poll timeouts.

Structured logs on revoke:

```json
{
  "event": "partitions_revoked",
  "consumer_id": "agent-worker-7",
  "partitions": ["agent-runs-3", "agent-runs-7"],
  "in_flight": 4,
  "drained_ms": 8200,
  "commits": 2
}
```

Correlate with deploy timestamps to distinguish healthy rolls from incident loops.

## Testing rebalance behavior

Unit tests cannot catch rebalance races. Use:

- **Embedded Kafka** integration tests that programmatically revoke partitions during simulated LLM latency
- **Chaos during load tests** — kill random pods while agent throughput is steady; assert duplicate tool rate below threshold
- **Game days** — scale consumers 2× then 0.5× while measuring p99 run completion time

Replay production traffic into staging with production partition counts. A group with three partitions behaves differently than staging's one.

## Configuration reference

Sensible starting point for production consumers (tune with evidence):

```properties
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
max.poll.interval.ms=300000
session.timeout.ms=45000
heartbeat.interval.ms=15000
enable.auto.commit=false
isolation.level=read_committed
```

Disable auto-commit always—pipelines need process-store-commit ordering tied to dedup writes.

## Static membership vs dynamic scaling

Some teams pin consumer group membership during business hours and scale only via partition count changes. That reduces rebalance frequency but sacrifices elastic response to traffic spikes. A hybrid works well for production platforms: keep a stable minimum replica set for baseline throughput, scale up during peak windows with cooperative rebalance, and scale down gradually after queue depth stays low for a cooldown period. Sudden scale-to-zero events are rebalance storms waiting to happen—avoid them on worker pools that hold LLM sessions.

When using Kubernetes, align `terminationGracePeriodSeconds` with your maximum revoke drain time. If the pod receives SIGTERM and exits before `onPartitionsRevoked` finishes draining in-flight agent runs, duplicates and orphaned steps follow. PreStop hooks that signal the consumer to leave the group gracefully—before the kubelet kills the process—buy the seconds cooperative drain needs.

## Related concepts

Rebalance interacts directly with [at-least-once idempotent consumers](https://blog.michaelsam94.com/agent-at-least-once-idempotent-consumers/) and [partition assignment stickiness](https://blog.michaelsam94.com/agent-partition-assignment-sticky/). Read those alongside this when designing agent event backbones.

## The takeaway

Consumer group rebalance is not a rare edge case—it is the normal cost of operating elastic agent workers. Cooperative sticky assignors, rebalance listeners that drain in-flight LLM work, and idempotent step storage turn chaotic partition shuffles into boring deploy noise. Instrument rebalance duration and duplicate detection before the next scale event surprises you.

## Resources

- [Apache Kafka rebalance protocol documentation](https://kafka.apache.org/documentation/#consumerconfigs) — assignor and timeout configuration
- [KIP-429: Cooperative Rebalancing](https://cwiki.apache.org/confluence/display/KAFKA/KIP-429%3A+Kafka+Consumer+Incremental+Rebalance+Protocol) — incremental cooperative design
- [Confluent: Understanding consumer rebalance](https://docs.confluent.io/platform/current/clients/consumer.html) — operational troubleshooting
- [KIP-848: Consumer group protocol (next gen)](https://cwiki.apache.org/confluence/display/KAFKA/KIP-848%3A+The+Next+Generation+of+the+Consumer+Rebalance+Protocol) — upcoming protocol improvements
- [LinkedIn original analysis of stop-the-world rebalance](https://www.confluent.io/blog/cooperative-rebalancing-in-kafka-streams-consumer-ks/) — why cooperative matters for long processing
