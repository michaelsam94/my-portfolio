---
title: "Event-Driven Architecture and the Outbox Pattern"
slug: "event-driven-outbox-pattern"
description: "The transactional outbox pattern solves the dual-write problem in event-driven systems: how to update a database and publish to Kafka without losing or duplicating events."
datePublished: "2026-05-31"
dateModified: "2026-05-31"
tags: ["Architecture", "Event-Driven", "Kafka", "Distributed Systems"]
keywords: "outbox pattern, event-driven architecture, dual write problem, message queue, eventual consistency, Kafka, transactional outbox, change data capture"
faq:
  - q: "What is the dual-write problem?"
    a: "It's the failure that happens when a service must update its database and publish an event as two separate operations. If the process crashes between them, you either persisted state with no event or published an event that never actually happened. There's no atomic way to do both across two systems."
  - q: "How does the outbox pattern solve it?"
    a: "You write the event into an 'outbox' table in the same local database transaction that changes your business data. Because both writes commit atomically, the event can never be lost. A separate relay process then reads the outbox and publishes to the message broker."
  - q: "Do consumers still need to handle duplicates with an outbox?"
    a: "Yes. The outbox guarantees at-least-once delivery, not exactly-once. The relay can crash after publishing but before marking a row as sent, causing a re-publish, so consumers must be idempotent — typically by tracking processed event ids."
---

Every event-driven system eventually runs into the same quiet bug: an order gets saved to the database, but the `OrderPlaced` event that was supposed to trigger the email, the inventory decrement, and the analytics pipeline never fires. Or the reverse — the event fires, downstream systems react, and then the database transaction rolls back, so everyone acted on an order that doesn't exist. This is the dual-write problem, and the outbox pattern is the standard cure.

The root cause is that a database and a message broker are two independent systems with no shared transaction. You cannot atomically "commit to Postgres and publish to Kafka." Something has to give, and the outbox pattern gives you a way to make the *event* a byproduct of the database commit instead of a second, unreliable step.

## Why you can't just publish after committing

The naive code looks reasonable:

```python
def place_order(order):
    db.insert(order)              # 1. write to database
    kafka.publish("orders", event)  # 2. publish event
```

Now walk the failure modes. If the process dies between line 1 and line 2, the order exists but no event was published — silent data loss that surfaces days later as "why didn't this customer get their confirmation?" If you swap the order and publish first, a database failure on line 1 leaves you having announced an order that was never saved. Wrapping both in a "transaction" doesn't help, because Kafka isn't enrolled in your database's transaction.

Retries don't save you either. If the publish fails and you retry, you might publish twice. If the database commit succeeds but the acknowledgement is lost, you don't know whether to retry. There is no ordering of these two operations that is both safe and simple. The trick is to stop treating them as two writes to two systems.

## The outbox: one atomic write

The outbox pattern collapses the two writes into one. Instead of publishing to the broker inside your business transaction, you insert a row into an `outbox` table *in the same transaction* as your business data:

```sql
BEGIN;
INSERT INTO orders (id, customer_id, total, status)
VALUES ('ord_123', 'cust_9', 4200, 'placed');

INSERT INTO outbox (id, aggregate_id, type, payload, created_at)
VALUES ('evt_456', 'ord_123', 'OrderPlaced',
        '{"orderId":"ord_123","total":4200}', now());
COMMIT;
```

Because both inserts are in one local transaction, they commit together or not at all. If the order is saved, the event is saved. If the transaction rolls back, neither exists. The atomicity you couldn't get across two systems, you get for free within one database.

A separate process — the **relay** or **message relay** — then reads unpublished rows from the outbox, publishes them to Kafka, and marks them sent:

```python
while True:
    rows = db.query(
        "SELECT * FROM outbox WHERE published_at IS NULL "
        "ORDER BY created_at LIMIT 100"
    )
    for row in rows:
        kafka.publish(topic_for(row.type), row.payload, key=row.aggregate_id)
        db.execute(
            "UPDATE outbox SET published_at = now() WHERE id = %s", row.id
        )
```

The business transaction is fast and never touches the broker. Delivery becomes an independent, retryable concern handled by the relay.

## At-least-once, not exactly-once

The outbox guarantees no event is ever lost, but it does not give you exactly-once delivery, and pretending otherwise is where people get burned. Picture the relay publishing a row to Kafka successfully and then crashing before the `UPDATE published_at` commits. On restart it sees the row as unpublished and publishes it again. That's at-least-once: every event is delivered one or more times.

This pushes a requirement onto consumers: they must be **idempotent**. A consumer processing `OrderPlaced` twice must produce the same result as processing it once. The usual approach is to track processed event ids and skip duplicates, which ties directly into broader [idempotency techniques for distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/). Put the event id in the payload, have the consumer record it after processing, and check it on the way in.

## Polling versus change data capture

The relay I sketched polls the outbox table. Polling is simple, easy to reason about, and fine for moderate throughput. Its downsides are latency (bounded by the poll interval) and the load of repeatedly querying for unpublished rows.

The higher-throughput alternative is **change data capture (CDC)**: instead of polling, you tail the database's write-ahead log. A tool like Debezium reads Postgres's WAL, notices inserts into the outbox table, and streams them to Kafka with low latency and no polling load on the database.

| Approach | Latency | DB load | Complexity |
|---|---|---|---|
| Polling relay | poll interval (e.g. 1s) | repeated queries | low |
| CDC (Debezium) | near-real-time | reads WAL | higher (extra infra) |

I reach for polling first and only move to CDC when either the latency or the query load actually becomes a problem. The pattern is identical either way; CDC just changes how rows leave the table.

## Ordering, cleanup, and other sharp edges

A few operational details decide whether an outbox implementation stays healthy:

- **Per-aggregate ordering.** If order-of-events matters (an `OrderUpdated` must not overtake its `OrderPlaced`), use the aggregate id as the Kafka partition key so all events for one entity land on the same partition and stay ordered. Global ordering across all events is neither achievable nor usually needed.
- **Table growth.** The outbox grows forever if you never prune it. Delete or archive rows once they're published and safely past your retention window; an unbounded outbox table eventually slows the very transactions it's meant to protect.
- **Poison messages.** A row that fails to serialize or that the broker keeps rejecting will block a naive relay. Track attempts, and route persistently failing events to a dead-letter table for a human to inspect rather than retrying forever.

## When to reach for it

Use the outbox pattern whenever a service must change its own state *and* tell the outside world about that change, and correctness depends on those two things staying consistent. Order placement, payment state transitions, and the kind of transaction lifecycle I dealt with on an [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) all fit — anywhere a lost or phantom event turns into a billing dispute or a stuck workflow.

It's not free. You take on an extra table, a relay process, and a hard requirement that consumers be idempotent. But compared to the alternative — a distributed system that occasionally, unreproducibly, loses events — that cost is a bargain. The dual-write problem doesn't go away because you ignore it; it just waits.

## Resources

- [microservices.io — Transactional Outbox pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [microservices.io — Polling Publisher](https://microservices.io/patterns/data/polling-publisher.html)
- [Debezium — Outbox event router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Confluent — The dual-write problem](https://www.confluent.io/blog/dual-write-problem/)
- [Apache Kafka documentation](https://kafka.apache.org/documentation/)
- [Martin Fowler — What do you mean by "Event-Driven"?](https://martinfowler.com/articles/201701-event-driven.html)
