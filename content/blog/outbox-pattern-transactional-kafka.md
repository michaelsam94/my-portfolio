---
title: "Outbox Pattern Transactional Kafka"
slug: "outbox-pattern-transactional-kafka"
description: "Publish Kafka messages atomically with database writes using the transactional outbox and idempotent producers."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Architecture"
keywords: "transactional outbox kafka, idempotent producer, exactly-once semantics, dual write problem"
faq:
  - q: "Can Kafka and Postgres participate in a true two-phase commit?"
    a: "Not natively in most application stacks. Kafka transactions (produce/consume/process) cover broker-side atomicity but do not span an external database commit. The transactional outbox avoids dual-write by making the database the single source of truth — the Kafka publish happens in a separate step, with the outbox row bridging the gap."
  - q: "What does Kafka's idempotent producer guarantee?"
    a: "It deduplicates retries within a producer session — if your relay crashes and retries a publish, Kafka accepts the message once per sequence number. It does not prevent duplicate publishes from two different relay workers or replays from the outbox table. Pair idempotent producers with consumer-side deduplication for end-to-end safety."
  - q: "Should the outbox relay delete rows or mark them published?"
    a: "Mark published (UPDATE published_at) when you need an audit trail or when Debezium CDC watches the table. DELETE after confirmed broker ack when you want minimal table size and run polling relay only. Never delete before broker ack — that loses events on publish failure."
---

The dual-write problem is the reason event-driven architectures fail quietly. Your service commits an order to Postgres, then publishes `OrderCreated` to Kafka. If the process crashes between the two operations, you have a shipped order with no downstream notification — or a Kafka message for an order that rolled back. Wrapping both in try/catch does not help; they are separate systems with separate failure domains.

The **transactional outbox pattern** solves this by writing the event to an outbox table in the same database transaction as the domain write. A separate **relay** publishes outbox rows to Kafka. This article focuses on making that Kafka leg reliable: producer configuration, relay design, and the realistic semantics you can achieve (hint: marketing "exactly-once" oversells what most teams actually need).

## Dual write failure modes

```
Scenario A: DB commits, Kafka publish fails
  → Order exists, warehouse never notified

Scenario B: Kafka publish succeeds, DB rolls back
  → Ghost event, downstream creates shipment for nonexistent order

Scenario C: Kafka publish succeeds, mark_published fails
  → Relay retries, duplicate events (usually acceptable with idempotent consumers)
```

The outbox eliminates scenarios A and B by atomicity at the database layer. Scenario C remains and is handled by idempotent producers and consumer deduplication.

## Outbox schema and write path

```sql
CREATE TABLE outbox (
  id             bigserial PRIMARY KEY,
  topic          text NOT NULL,
  partition_key  text NOT NULL,
  headers        jsonb DEFAULT '{}',
  payload        jsonb NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  published_at   timestamptz
);

CREATE INDEX outbox_pending ON outbox (id) WHERE published_at IS NULL;
```

Application write:

```python
def ship_order(order_id: str, db: Connection, kafka_headers: dict):
    with db.transaction():
        db.execute(
            "UPDATE orders SET status = 'shipped' WHERE id = %s",
            [order_id],
        )
        db.execute(
            """
            INSERT INTO outbox (topic, partition_key, headers, payload)
            VALUES ('orders.events', %s, %s, %s)
            """,
            [
                order_id,
                json.dumps({"trace_id": kafka_headers.get("trace_id")}),
                json.dumps({
                    "eventType": "OrderShipped",
                    "orderId": order_id,
                    "shippedAt": datetime.utcnow().isoformat(),
                }),
            ],
        )
    # Transaction committed — event intent is durable
```

No Kafka call in the request path. The HTTP response returns after database commit only.

## Relay worker design

The relay polls (or receives CDC events for) unpublished rows and publishes to Kafka:

```python
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKERS,
    enable_idempotence=True,
    acks='all',
    retries=MAX_INT,
    max_in_flight_requests_per_connection=5,
    compression_type='lz4',
    key_serializer=lambda k: k.encode(),
    value_serializer=lambda v: json.dumps(v).encode(),
)

def relay_batch():
    rows = db.fetch("""
        SELECT id, topic, partition_key, headers, payload
        FROM outbox
        WHERE published_at IS NULL
        ORDER BY id
        LIMIT 200
        FOR UPDATE SKIP LOCKED
    """)

    for row in rows:
        headers = [(k, str(v).encode()) for k, v in row.headers.items()]
        future = producer.send(
            topic=row.topic,
            key=row.partition_key,
            value=row.payload,
            headers=headers,
        )
        # Block for ack before marking published
        future.get(timeout=10)

        db.execute(
            "UPDATE outbox SET published_at = now() WHERE id = %s",
            [row.id],
        )
    db.commit()
```

Critical ordering: **wait for broker ack, then mark published, in separate transactions**. The outbox mark is a new transaction after Kafka confirms receipt.

## Kafka producer configuration explained

**`enable.idempotence=True`**: Enables producer ID assignment and sequence numbers. Broker deduplicates retries from the same producer instance within its session epoch. Required for `max.in.flight.requests.per.connection` up to 5 with ordering guarantees.

**`acks=all`**: Wait for all in-sync replicas to acknowledge. Trade latency for durability. Never use `acks=0` or `acks=1` for domain events.

**`retries=MAX_INT`**: Retry transient broker errors indefinitely (with backoff). Combined with idempotence, retries do not create duplicates at the broker.

**`max.in.flight.requests.per.connection=5`**: With idempotence enabled, up to 5 unacknowledged batches preserve per-partition ordering while allowing pipelining. Set to 1 only if you need strict ordering without idempotence (not recommended).

## Kafka transactions vs outbox

Kafka's transactional API (`init_transactions`, `begin_transaction`, `commit_transaction`) provides atomic produce-and-consume within Kafka — useful for stream processing, not for spanning Postgres:

```python
# This does NOT atomically commit with Postgres
producer.init_transactions()
producer.begin_transaction()
producer.send('orders.events', value=payload)
producer.commit_transaction()  # Atomic within Kafka only
```

Some teams attempt **change data capture with Kafka Connect** using Debezium's transactional delivery — the outbox row INSERT triggers a Kafka message via WAL, which is closer to end-to-end consistency but still at-least-once at the consumer.

Realistic semantics for outbox + Kafka:

| Layer | Guarantee |
| --- | --- |
| Domain write + outbox INSERT | Exactly-once (single DB transaction) |
| Outbox relay → Kafka | At-least-once (mark after ack) |
| Kafka broker (idempotent producer) | Deduped retries per producer session |
| Consumer processing | At-least-once unless consumer implements exactly-once with transactional reads |

## Consumer-side idempotency

Downstream services must handle duplicate events:

```python
def handle_order_shipped(event: dict, db: Connection):
    idempotency_key = f"OrderShipped:{event['orderId']}:{event.get('shippedAt')}"

    inserted = db.execute("""
        INSERT INTO processed_events (idempotency_key)
        VALUES (%s)
        ON CONFLICT DO NOTHING
        RETURNING idempotency_key
    """, [idempotency_key])

    if not inserted:
        return  # already processed

    db.execute(
        "INSERT INTO shipments (order_id, status) VALUES (%s, 'pending')",
        [event['orderId']],
    )
```

Alternatively, design handlers to be naturally idempotent: `UPDATE inventory SET qty = qty - 1 WHERE order_id = $1` with a unique constraint on `order_id` in the inventory deduction table.

## Partition key selection

Use aggregate ID as Kafka message key:

```python
partition_key = order_id  # all events for this order go to same partition
```

Same-partition ordering ensures `OrderCreated` arrives before `OrderShipped` for a given order. Cross-aggregate ordering is not guaranteed and should not be assumed.

## Header propagation

Pass trace context through outbox headers:

```python
headers = {
    "trace_id": current_trace_id(),
    "event_id": str(outbox_row_id),
    "content_type": "application/json",
}
```

Consumers extract `trace_id` for distributed tracing continuity across the async boundary.

## Scaling the relay

**Multiple relay workers**: `FOR UPDATE SKIP LOCKED` distributes rows across workers. Ordering per partition_key is not preserved if multiple workers publish events for the same key concurrently — acceptable if consumers handle out-of-order within an aggregate, or use a single worker per topic partition.

**CDC instead of polling**: Debezium watches outbox INSERTs via logical replication — lower latency, no poll queries. See companion article on polling vs WAL.

**Batching**: Accumulate 200 rows, publish in parallel with `flush()`, batch UPDATE published_at. Reduces round trips at cost of slightly higher latency per event.

## Monitoring and alerting

Metrics:

- `outbox_pending_count` — unpublished rows (lag indicator)
- `outbox_oldest_pending_age_seconds` — SLO on publish latency
- `relay_publish_errors_total` — broker connectivity issues
- `relay_batch_duration_seconds` — relay throughput

Alert when oldest pending age exceeds 30 seconds for user-facing flows. A growing pending count with flat publish rate indicates relay capacity exhaustion.

Dashboard query:

```sql
SELECT count(*) AS pending,
       min(created_at) AS oldest,
       now() - min(created_at) AS max_lag
FROM outbox
WHERE published_at IS NULL;
```

## Failure recovery runbook

**Relay crash mid-batch**: Unpublished rows remain (published_at IS NULL). Next relay iteration retries. Idempotent producer prevents broker duplicates from same relay instance.

**Kafka cluster unavailable**: Relay logs errors, rows accumulate. Alert fires on pending age. When Kafka recovers, relay drains backlog — consumers see burst traffic; ensure consumer autoscaling handles catch-up.

**Duplicate events after recovery**: Expected under at-least-once. Verify consumer idempotency keys work.

**Outbox table bloat**: Schedule DELETE of published rows older than retention period:

```sql
DELETE FROM outbox
WHERE published_at IS NOT NULL
  AND published_at < now() - interval '14 days'
LIMIT 10000;
```

## Anti-patterns to avoid

**Publishing to Kafka inside the database transaction**: Requires XA or custom protocol — fragile, slow, and unsupported by standard Kafka clients in request handlers.

**Deleting outbox rows before broker ack**: Event loss on publish failure.

**No partial index on unpublished rows**: Full table scan on every poll as published rows accumulate.

**Ignoring consumer idempotency because "Kafka is exactly-once"**: Broker idempotence ≠ end-to-end exactly-once.

## Summary

The transactional outbox with Kafka separates atomic domain persistence from async event delivery. Write events to the outbox in the same database transaction as your business logic; relay with an idempotent producer configured for `acks=all`; mark rows published only after broker acknowledgment; and implement consumer-side deduplication for the at-least-once reality. This pattern does not achieve mythical cross-system exactly-once, but it eliminates the dangerous dual-write failure modes that cause silent data inconsistency in production.
