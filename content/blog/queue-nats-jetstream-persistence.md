---
title: "NATS JetStream Persistence"
slug: "queue-nats-jetstream-persistence"
description: "Stream retention, consumer ack wait, and at-least-once redelivery config."
datePublished: "2026-03-15"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "nats jetstream, stream retention, consumer ack wait, at-least-once messaging"
faq:
  - q: "What is the difference between Core NATS and JetStream?"
    a: "Core NATS is fire-and-forget pub/sub with no persistence — subscribers must be online. JetStream adds streams that store messages on disk, consumer state, replay, and at-least-once delivery with explicit acks. Use JetStream when consumers can crash or lag and messages must survive broker restarts."
  - q: "How does ack wait affect redelivery?"
    a: "Each consumer defines ack_wait — if the message is not acked within that interval, JetStream redelivers it to the same or another subscriber on the queue group. Set ack_wait longer than p99 handler time plus downstream timeout, but short enough to recover quickly from crashed consumers."
  - q: "Which retention policy should I use: limits, interest, or work queue?"
    a: "Limits retention keeps messages until byte/count/age limits — good for event logs and replay. Interest retention deletes after all known consumers ack — memory efficient for fan-out. Work queue retention deletes after first ack — use for job dispatch where only one worker should process each message."
---

Core NATS delivered metrics to a Grafana bridge until the bridge pod restarted during a deploy — sixty seconds of host telemetry vanished because nothing persisted. Moving the pipeline to JetStream with a limits-based stream and explicit pull consumers gave at-least-once delivery, replay after outages, and backpressure when the bridge fell behind. JetStream is not "NATS with disk"; it is a different operational contract.

## Stream fundamentals

A **stream** captures subjects and stores messages according to retention and limits:

```bash
nats stream add TELEMETRY \
  --subjects "metrics.host.>" \
  --storage file \
  --retention limits \
  --max-age 72h \
  --max-bytes 50GB \
  --replicas 3 \
  --discard old
```

| Retention | Behavior |
|-----------|----------|
| `limits` | Keep until max age/bytes/count |
| `interest` | Remove after all consumers have acked |
| `workqueue` | Remove after first ack — job queue semantics |

**Storage:** `file` for production durability; `memory` for dev/low-latency ephemeral.

## Consumers: push vs pull

**Push consumer** — server delivers to subscription:

```bash
nats consumer add TELEMETRY HOST_BRIDGE \
  --filter "metrics.host.prod.>" \
  --deliver group host-workers \
  --ack explicit \
  --ack-wait 30s \
  --max-deliver 5
```

**Pull consumer** — client fetches batches:

```go
sub, _ := js.PullSubscribe("metrics.host.>", "HOST_BRIDGE",
    nats.BindStream("TELEMETRY"),
    nats.ManualAck(),
)
msgs, _ := sub.Fetch(10, nats.MaxWait(2*time.Second))
for _, msg := range msgs {
    if err := process(msg.Data); err != nil {
        msg.NakWithDelay(10 * time.Second)
        continue
    }
    msg.Ack()
}
```

Pull suits workers that cannot keep up with push fan-out.

## Ack models and redelivery

| Ack | Meaning |
|-----|---------|
| `Ack()` | Success |
| `Nak()` / `NakWithDelay()` | Retry after delay |
| `Term()` | Poison — stop redelivery |
| `InProgress()` | Reset ack_wait timer for long jobs |

`max_deliver` caps retries before server stops. Monitor `NumRedelivered` in consumer info.

## At-least-once and idempotency

JetStream guarantees **at-least-once**, not exactly-once. Handlers must be idempotent:

```go
func process(msg *nats.Msg) error {
    var evt Event
    json.Unmarshal(msg.Data, &evt)
    inserted, err := db.InsertEventIdempotent(evt.ID, evt.Payload)
    if err != nil { return err }
    return nil
}
```

## Stream limits and disk planning

Watch `Bytes` vs `--max-bytes`, consumer pending counts, and `FirstSeq`/`LastSeq` gaps.

`discard: old` drops oldest when full — preferable for telemetry. `discard: new` rejects publishers when full.

## Cluster durability and DR

Three-node cluster tolerates one loss with R3 streams. Backup with stream snapshot; test restore on staging.

```bash
nats server report jetstream
```

## Subject design and ordering

JetStream preserves order **per subject** within a stream, not globally. Partition hot keys:

```
orders.us-east.12345
orders.us-east.67890
```

Parallel consumers on queue group process different subjects concurrently; same subject serializes.

## Mirror streams and disaster recovery

JetStream supports mirror streams for cross-cluster replication — asynchronous, plan RPO accordingly.

## Ephemeral vs durable consumers

Ephemeral push consumers disappear when client disconnects — messages redeliver. Production always uses durable names.

## Operational gotchas

1. **Consumer not bound to stream** — messages published but never delivered.
2. **Ephemeral vs durable** — production uses durable names.
3. **Ordered consumers + slow handler** — blocks partition; split or use non-ordered for throughput.
4. **Disk full on single node** — alert on JetStream storage usage per server.
5. **Core NATS subscribers mixed with JetStream** — only ingested subjects in stream config persist.

## Prometheus metrics

```
nats_jetstream_stream_messages{stream="TELEMETRY"}
nats_jetstream_consumer_num_pending{stream="TELEMETRY",consumer="HOST_BRIDGE"}
```

Pending growth with flat processing rate signals consumer failure.

JetStream turns NATS into a durable log with consumer-controlled delivery. Configure retention for your data lifecycle, tune `ack_wait` and `max_deliver` for failure modes, design idempotent handlers for at-least-once reality, and monitor stream bytes plus redelivery rates before consumers drown in silent lag.

## Stream sourcing and aggregation

JetStream can source from other streams — aggregate edge telemetry streams into central stream for analytics without dual-publish from agents. Source lag metrics indicate edge-to-core pipeline health; alert separately from consumer lag.

## Consumer max ack pending

Push consumers with high `max_ack_pending` pipeline messages to slow clients — memory grows on server. Tune `max_ack_pending` to match client processing parallelism × average message size. Pull consumers control inflight via fetch batch size — preferred for variable handler duration.

## JetStream Key-Value and Object Store

Related JetStream KV and Object Store APIs share cluster — do not confuse message stream retention with KV TTL for large blob references. Pattern: store payload in Object Store, publish pointer in stream message — keeps stream bytes low while retaining large artifact.

## NATS account isolation

Multi-tenant NATS uses accounts and exports — stream in account A imported by account B requires explicit export/import config. Misconfigured export looks like "messages published but stream empty" from subscriber account perspective.

## Upgrade and server roll

Rolling NATS cluster upgrade with R3 streams requires quorum majority healthy — schedule upgrades during low publish rate. Verify stream leader per cluster after roll: `nats stream report` — unbalanced leaders skew disk IO to one node.

## JetStream domain isolation

Super-cluster JetStream domains isolate stream namespace — disaster recovery domain failover requires stream export/import plan. Test domain switch failover quarterly; DNS or client config must point subscribers to new domain leader.

## Message trace and advisories

Enable JetStream advisories for max deliveries exceeded — publish to `$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES` monitoring subject. Automate ticket when advisory fires with stream, consumer, and sequence number for replay decision.

## Compare to Kafka retention

Kafka log retention by time/size parallels JetStream limits retention — migration from Kafka to JetStream map topic partition to subject plus stream, consumer group to durable pull consumer. Ordering scope changes from partition to subject — revisit hot key design during migration.

## Stream compression (JetStream 2.10+)

Optional stream compression reduces disk for telemetry streams — CPU tradeoff on publish path similar to Postgres wal_compression. Benchmark on representative message size before enabling on high-throughput stream.

## Consumer inactive threshold

Inactive consumer threshold deletes dormant consumers — long-lived pull consumer with typo in durable name recreates fresh consumer losing ack state — alert on consumer create rate. Document durable naming convention `{service}-{stream}-{env}`.

## Pull consumer max bytes

Fetch with MaxBytes prevents OOM on large messages — combine with stream max_msg_size at publish boundary. Consumer processing 10MB messages one at a time should fetch batch size 1 regardless of default fetch 10.

## JetStream vs Core request-reply coexistence

Services using NATS request-reply for sync API and JetStream for async events share cluster — ensure stream subjects do not capture reply inbox subjects accidentally via broad wildcard `>` in stream config. Narrow stream subject to `events.>` not root `>`.

## Storage cleanup and disk alerts

JetStream file store does not shrink immediately after purge — monitor OS free space not only stream byte metrics. Schedule maintenance window for disk reclaim after large purge on busy stream.

## Bench publish rate before production cutover

Load test JetStream stream at expected peak publish rate on three-node cluster — measure publish ack latency p99 and disk write rate. Core NATS benchmarks do not predict JetStream disk saturation; stream add is one-way door for subject capture until reconfigured.

## Consumer pause and resume

Administrative consumer pause stops delivery without deleting consumer — use during downstream maintenance instead of stopping all subscribers. Resume continues from last ack sequence; document pause in runbook instead of deleting durable consumer which loses position semantics depending on config.

## Final operational note

Treat JetStream consumer lag like database replication lag — product reads from stale consumer see old world. Document maximum acceptable lag per stream in SLO; pause publishers only as last resort because backpressure strategy differs from Kafka — publishers may not know stream full until publish error.
Set both max-age and max-bytes on every durable stream; age alone will not save you when average payload size doubles after a schema change.

Document the SLO this setting protects for queue-nats-jetstream-persistence.
