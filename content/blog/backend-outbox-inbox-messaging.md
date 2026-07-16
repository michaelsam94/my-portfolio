---
title: "Outbox and Inbox Messaging Patterns"
slug: "backend-outbox-inbox-messaging"
description: "The transactional outbox guarantees reliable event publishing from database writes. The inbox pattern deduplicates incoming messages. Implement both with Postgres and a message broker for consistent distributed systems."
datePublished: "2024-10-30"
dateModified: "2024-10-30"
tags: ["Backend", "Architecture", "Messaging", "Databases"]
keywords: "transactional outbox pattern, inbox pattern, reliable event publishing, dual write problem, outbox table Postgres, message deduplication"
faq:
  - q: "What problem does the transactional outbox solve?"
    a: "The dual-write problem: you need to update a database AND publish a message, but one can succeed while the other fails. The outbox writes the event to an outbox table in the same database transaction as the business write. A separate relay process publishes from the outbox to the broker — guaranteeing at-least-once publish if the transaction commits."
  - q: "What is the inbox pattern?"
    a: "The inbox pattern stores incoming message IDs in a database table before processing. If the same message arrives twice (at-least-once delivery), the duplicate insert fails on the unique constraint and processing is skipped. It's the receiving-side counterpart to the outbox."
  - q: "Can I use Change Data Capture instead of polling the outbox?"
    a: "Yes. Debezium or Postgres logical replication can stream outbox table inserts to Kafka directly, eliminating poll latency. CDC is more operationally complex but scales better than a polling relay at high throughput."
---

Updating an order row and publishing `OrderCreated` to Kafka are two writes to two systems. The DB commit succeeds, the broker is down, and now your warehouse never ships the order. Or the message publishes, the DB rolls back, and you notify a customer about an order that doesn't exist. The transactional outbox eliminates this by making event publishing a database write — same transaction, same ACID guarantee.

## Outbox pattern

```sql
CREATE TABLE outbox (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID NOT NULL,
    event_type   VARCHAR(100) NOT NULL,
    payload      JSONB NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now(),
    published_at TIMESTAMPTZ
);

CREATE INDEX idx_outbox_unpublished ON outbox(created_at)
    WHERE published_at IS NULL;
```

Business write + outbox insert in one transaction:

```typescript
async function createOrder(input: CreateOrderInput): Promise<Order> {
  return db.transaction(async (tx) => {
    const [order] = await tx.insert(orders).values(input).returning();

    await tx.insert(outbox).values({
      aggregateId: order.id,
      eventType: 'order.created',
      payload: {
        orderId: order.id,
        customerId: order.customerId,
        total: order.total,
      },
    });

    return order;
  });
}
```

Relay process polls unpublished rows:

```typescript
async function relayOutbox(): Promise<void> {
  const events = await db
    .select()
    .from(outbox)
    .where(isNull(outbox.publishedAt))
    .orderBy(outbox.createdAt)
    .limit(100)
    .for('update', { skipLocked: true });

  for (const event of events) {
    await kafka.send({
      topic: 'orders',
      messages: [{ key: event.aggregateId, value: JSON.stringify(event.payload) }],
    });
    await db
      .update(outbox)
      .set({ publishedAt: new Date() })
      .where(eq(outbox.id, event.id));
  }
}
```

`FOR UPDATE SKIP LOCKED` lets multiple relay workers run safely.

## Inbox pattern

Receiving side — deduplicate before processing:

```sql
CREATE TABLE inbox (
    message_id   VARCHAR(255) PRIMARY KEY,
    received_at  TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ
);
```

```typescript
async function handleOrderCreated(message: KafkaMessage): Promise<void> {
  await db.transaction(async (tx) => {
    const inserted = await tx
      .insert(inbox)
      .values({ messageId: message.headers['message-id'] as string })
      .onConflictDoNothing()
      .returning();

    if (inserted.length === 0) return; // duplicate

    await tx.insert(shipments).values({
      orderId: message.value.orderId,
      status: 'pending',
    });

    await tx
      .update(inbox)
      .set({ processedAt: new Date() })
      .where(eq(inbox.messageId, message.headers['message-id'] as string));
  });
}
```

Outbox + inbox together give you reliable end-to-end messaging with at-least-once semantics and no duplicate side effects.

## CDC alternative

Instead of polling:

```
Postgres outbox table → Debezium → Kafka topic
```

Debezium captures WAL changes and streams new outbox rows to Kafka within milliseconds. Eliminates relay polling but requires running Kafka Connect and managing connector state.

## Ordering guarantees

Outbox relay publishes in `created_at` order per aggregate:

```typescript
.orderBy(outbox.createdAt)
```

Use aggregate ID as Kafka partition key so all events for one order land in one partition in order.

## Cleanup

Archive published outbox rows older than 7 days. Inbox rows can TTL after 30 days (longer than max redelivery window).

## Pattern comparison

| Pattern | Solves | Tradeoff |
|---------|--------|----------|
| Outbox | Reliable publish after DB write | Relay lag (ms–seconds) |
| Inbox | Duplicate message handling | Extra table per consumer |
| Idempotent consumer | Same as inbox, lighter | Requires upsert-friendly ops |
| Saga | Cross-service consistency | Complex orchestration |

Combine outbox publishing with [idempotent consumers](https://blog.michaelsam94.com/backend-idempotent-consumer-pattern/) on the receiving side.

## The dual-write problem in detail

The dual-write problem has three failure modes, not two:

1. **DB commits, broker fails** — event never published (most common)
2. **Broker publishes, DB rolls back** — ghost event for non-existent data
3. **Both succeed, but consumer processes before DB read replica catches up** — consumer sees stale state

The outbox solves #1 and #2 by making the event write part of the DB transaction. #3 requires read-your-writes consistency or consumer-side retry with backoff.

```typescript
// Anti-pattern: dual write without outbox
async function createOrder(input) {
  const order = await db.insert(orders).values(input);  // succeeds
  await kafka.send({ topic: 'orders', value: order });   // fails — event lost
}

// Correct: outbox in same transaction
async function createOrder(input) {
  return db.transaction(async (tx) => {
    const order = await tx.insert(orders).values(input);
    await tx.insert(outbox).values({ eventType: 'order.created', payload: order });
    return order;
  });
  // Relay publishes asynchronously — at-least-once, never lost after commit
}
```

## Relay implementation patterns

**Polling relay** — simple, works everywhere:

```typescript
// Run every 1-5 seconds via cron or setInterval
async function relayOutbox() {
  const batch = await db.select().from(outbox)
    .where(isNull(outbox.publishedAt))
    .orderBy(outbox.createdAt)
    .limit(100)
    .for('update', { skipLocked: true });

  for (const event of batch) {
    try {
      await broker.publish(event.eventType, event.payload);
      await db.update(outbox).set({ publishedAt: new Date() }).where(eq(outbox.id, event.id));
    } catch (e) {
      // Leave publishedAt null — retry next poll
      logger.error('Relay failed', { eventId: event.id, error: e });
    }
  }
}
```

**CDC relay (Debezium)** — lower latency, higher ops complexity:

```
Postgres WAL → Debezium connector → Kafka Connect → Kafka topic
```

Configure Debezium outbox event router transform to map outbox rows to proper Kafka messages with routing keys. Eliminates polling lag but requires Kafka Connect cluster management.

**Transactional messaging (Kafka transactions)** — publish in same transaction as DB write using Kafka's transactional API. Broker-specific, complex error handling, and ties you to Kafka. Outbox is more portable.

## Inbox vs idempotent consumer

The inbox pattern is the heavy version of idempotent consumption — a dedicated table per consumer service. Lighter alternatives:

| Approach | When to use |
|---|---|
| Inbox table | Strict dedup audit trail needed; regulated industries |
| Natural key upsert | Event creates record with fixed ID — insert on conflict do nothing |
| Dedup table only | General-purpose; see idempotent consumer pattern |
| Broker-native dedup | SQS FIFO with deduplication ID; Kafka idempotent producer |

Use inbox when you need to prove a message was received and processed for compliance. Use natural key upsert when the business operation itself is inherently idempotent.

## Outbox schema evolution

As events evolve, outbox payloads need versioning:

```sql
ALTER TABLE outbox ADD COLUMN schema_version INT NOT NULL DEFAULT 1;
```

Consumers handle multiple versions during migration. Never mutate published events — publish a new event type (`order.created.v2`) and deprecate the old one.

## Failure modes

- **Relay marks published before broker confirms** — event lost if broker rejects after DB update; publish first, then mark
- **Outbox table bloat** — unpublished events accumulate when broker is down; alert on unpublished count
- **No SKIP LOCKED** — multiple relay workers double-publish; use row-level locking
- **Large payloads in outbox** — JSONB blobs slow relay; store blob in S3, pass reference in outbox
- **Inbox without TTL** — table grows forever; partition and purge
- **Ordering violations** — relay publishes out of order; sort by created_at, partition by aggregate key

## Production checklist

- Business write and outbox insert in single database transaction
- Relay uses FOR UPDATE SKIP LOCKED for concurrent workers
- Published_at set only after broker confirms receipt
- Unpublished outbox count monitored and alerted
- Outbox rows archived/purged after retention period (7–30 days)
- Inbox/dedup retention exceeds max broker redelivery window
- CDC alternative evaluated if polling lag exceeds SLA
- Event schema version tracked in outbox payload

## Resources

- [Microservices.io — Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html)
- [Debezium outbox event router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [PostgreSQL FOR UPDATE SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
- [Inbox pattern (Chris Richardson)](https://microservices.io/patterns/data/transactional-outbox.html)
- [AWS — Dual writes and outbox pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)
