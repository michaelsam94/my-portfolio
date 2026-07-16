---
title: "The Idempotent Consumer Pattern"
slug: "backend-idempotent-consumer-pattern"
description: "Message consumers must handle duplicate delivery without double-charging or double-writing. Implement idempotent consumers with deduplication keys, upserts, and exactly-once semantics at the application layer."
datePublished: "2024-10-15"
dateModified: "2024-10-15"
tags: ["Backend", "Architecture", "Messaging"]
keywords: "idempotent consumer, message deduplication, exactly once semantics, Kafka consumer idempotency, duplicate message handling"
faq:
  - q: "Why do message brokers deliver duplicates?"
    a: "Brokers guarantee at-least-once delivery by default — a consumer crashes after processing but before acknowledging, and the message redelivers. Network retries, producer retries, and consumer rebalances all cause duplicates. Your consumer must be idempotent: processing the same message twice produces the same result as once."
  - q: "How do I implement idempotent message processing?"
    a: "Store a deduplication key (message ID or business idempotency key) in a database with a unique constraint. Before processing, attempt to insert the key — if it already exists, skip processing and ack the message. Alternatively, use upsert operations where the natural key makes repeats harmless."
  - q: "Is exactly-once delivery possible?"
    a: "True exactly-once end-to-end requires transactional outbox, idempotent consumers, and broker transactions — complex and broker-specific. Practical systems achieve effectively-once semantics: at-least-once delivery plus idempotent consumers. Design for duplicates from day one."
---

Your payment consumer processes a `PaymentCompleted` event, credits the user's account, and crashes before committing the Kafka offset. The message redelivers. Without idempotency, the user gets double credit. Every message broker — Kafka, SQS, RabbitMQ, Pub/Sub — delivers duplicates under failure scenarios. "At-least-once" is a feature, not a bug. The idempotent consumer pattern makes duplicates harmless.

## The failure scenario

```
1. Consumer receives msg-123 (pay $50 to account A)
2. UPDATE accounts SET balance = balance + 50 WHERE id = A  ✓
3. Consumer crashes before offset commit
4. Consumer restarts, receives msg-123 again
5. Without idempotency: balance += 50 again  ✗
```

## Deduplication table pattern

```sql
CREATE TABLE processed_messages (
    message_id   VARCHAR(255) PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

```typescript
async function handlePaymentEvent(event: PaymentEvent, messageId: string): Promise<void> {
  await db.transaction(async (tx) => {
    const inserted = await tx
      .insert(processedMessages)
      .values({ messageId })
      .onConflictDoNothing()
      .returning();

    if (inserted.length === 0) {
      // Already processed — ack and return
      return;
    }

    await tx
      .update(accounts)
      .set({ balance: sql`balance + ${event.amount}` })
      .where(eq(accounts.id, event.accountId));
  });
}
```

The unique constraint on `message_id` makes the insert-and-check atomic within the transaction.

## Natural key idempotency

When the business event has a natural idempotency key, skip the dedup table:

```typescript
async function handleOrderCreated(order: OrderEvent): Promise<void> {
  await db
    .insert(orders)
    .values({
      id: order.orderId,        // natural key from upstream
      customerId: order.customerId,
      total: order.total,
    })
    .onConflictDoNothing();
}
```

Inserting the same order twice is a no-op. This works when the side effect is "create record with fixed ID."

## Idempotency key from producer

Producers should attach stable IDs:

```json
{
  "eventId": "evt_8f3a2b1c",
  "type": "payment.completed",
  "idempotencyKey": "pay_intent_pi_abc123",
  "payload": { "amount": 5000, "accountId": "acc_xyz" }
}
```

Use `idempotencyKey` (business-level) over broker `messageId` when the same business event can be republished with a new message envelope.

## Consumer design rules

| Rule | Why |
|------|-----|
| Process + dedup in one transaction | Avoid window between process and record |
| Make side effects upserts | Natural defense against duplicates |
| Ack after successful commit | At-least-once means ack-on-success |
| Log skipped duplicates at INFO | Distinguish from errors in monitoring |
| TTL old dedup keys | Table grows forever otherwise |

```sql
-- Partition or purge keys older than 30 days
DELETE FROM processed_messages WHERE processed_at < now() - interval '30 days';
```

Retention must exceed your broker's max redelivery window.

## Kafka-specific notes

Enable `enable.idempotence=true` on producers to prevent duplicate writes from producer retries — this is broker-level dedup, not consumer-level. Consumers still need application idempotency.

For Kafka Streams, use `reduce` with commutative operations where possible (counts are dangerous; sets and max are safer).

## Testing idempotency

```typescript
test('duplicate message does not double credit', async () => {
  const event = { orderId: 'ord_1', amount: 100, accountId: 'acc_1' };
  await handlePaymentEvent(event, 'msg-001');
  await handlePaymentEvent(event, 'msg-001'); // duplicate

  const account = await db.select().from(accounts).where(eq(accounts.id, 'acc_1'));
  expect(account.balance).toBe(100); // not 200
});
```

Every consumer handler should have this test. Pair with [outbox pattern](https://blog.michaelsam94.com/backend-outbox-inbox-messaging/) for reliable publishing.

## Ordering and exactly-once semantics

Idempotency handles duplicates but not ordering. If `OrderCreated` and `OrderCancelled` arrive out of order, idempotent processing of each individually still produces wrong final state. Solutions:

- **Partition by aggregate key** — Kafka partition key = `orderId` guarantees order per order
- **Version numbers** — reject events with `version <= current_version` in the database
- **State machine guards** — only accept `OrderCancelled` if current state is `confirmed`

```typescript
async function handleOrderEvent(event: OrderEvent): Promise<void> {
  await db.transaction(async (tx) => {
    const inserted = await tx.insert(processedMessages)
      .values({ messageId: event.eventId })
      .onConflictDoNothing()
      .returning();
    if (inserted.length === 0) return;

    const order = await tx.select().from(orders).where(eq(orders.id, event.orderId));
    if (order.version >= event.version) return; // stale event

    await applyTransition(tx, order, event);
  });
}
```

## Partial failure and the outbox boundary

Idempotent consumers work when processing is a single database transaction. When processing spans systems (DB write + external API call), you need the [outbox pattern](https://blog.michaelsam94.com/backend-outbox-inbox-messaging/) or saga:

```
Message → idempotent DB write → outbox event → external call via relay
```

If the external call fails, the outbox retries without re-processing the idempotent DB write. The dedup table and outbox table serve different purposes — dedup prevents double processing; outbox ensures reliable downstream delivery.

## SQS, RabbitMQ, and Pub/Sub variants

**SQS:** Use FIFO queues with deduplication ID for ordering + dedup. Standard queues require application-level dedup table. Visibility timeout must exceed max processing time — otherwise message reappears while still being processed.

**RabbitMQ:** Manual ack after successful processing. Prefetch count = 1 for ordering per consumer. Dead-letter exchange for failed messages after max retries.

**Google Pub/Sub:** Enable message ordering with ordering keys. Ack deadline extension for long-running processing. Dead-letter topic for poison messages.

The dedup table pattern is broker-agnostic — implement it regardless of transport.

## Dedup table operations at scale

The `processed_messages` table grows indefinitely without maintenance:

```sql
-- Partition by month for efficient purge
CREATE TABLE processed_messages (
    message_id VARCHAR(255) NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (message_id, processed_at)
) PARTITION BY RANGE (processed_at);

-- Drop partitions older than retention window
DROP TABLE processed_messages_2024_01;
```

Retention must exceed: max broker redelivery window + max consumer downtime + clock skew buffer. Typical: 30 days for Kafka, 14 days for SQS.

Index size on high-throughput topics (millions/day) makes partitioning essential — a single-table DELETE is too slow.

## Failure modes

- **Dedup check outside transaction** — race between check and process allows double execution
- **Business key vs message ID mismatch** — republished event with new envelope ID bypasses dedup; use business idempotency key
- **TTL too short** — old message redelivers after dedup key purged → double processing
- **Non-idempotent side effects before dedup** — email sent before dedup insert; duplicate sends email twice
- **Assuming broker exactly-once** — Kafka transactions help producers but consumers still need application idempotency

## Production checklist

- Dedup insert and business logic in single database transaction
- Business-level idempotency key preferred over broker message ID
- Dedup table retention exceeds max redelivery window
- Partitioned dedup table for high-throughput consumers
- Duplicate handling tested in CI for every consumer handler
- Ordering enforced via partition key or version numbers where sequence matters
- Skipped duplicates logged at INFO level for monitoring

## Resources

- [Kafka delivery semantics](https://kafka.apache.org/documentation/#semantics)
- [AWS SQS exactly-once processing guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-exactly-once-processing.html)
- [Stripe idempotency keys](https://stripe.com/docs/api/idempotent_requests)
- [Enterprise Integration Patterns — Idempotent Receiver](https://www.enterpriseintegrationpatterns.com/patterns/messaging/IdempotentReceiver.html)
- [PostgreSQL INSERT ON CONFLICT](https://www.postgresql.org/docs/current/sql-insert.html#SQL-ON-CONFLICT)
