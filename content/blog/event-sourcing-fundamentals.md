---
title: "Event Sourcing Fundamentals"
slug: "event-sourcing-fundamentals"
description: "Learn event sourcing: append-only event logs, aggregates, commands, idempotency, event store design, and when CRUD plus audit table is enough."
datePublished: "2026-02-02"
dateModified: "2026-02-02"
tags: ["Backend", "Event Sourcing", "Architecture", "DDD"]
keywords: "event sourcing fundamentals, event store, domain events, aggregate event sourcing, CQRS event sourcing, append-only log, event-driven architecture, idempotent command handling"
faq:
  - q: "What is event sourcing in simple terms?"
    a: "Event sourcing persists state changes as an append-only sequence of domain events instead of overwriting rows in place. Current state is derived by replaying events (or loading a snapshot plus recent events). The event log is the system of record — databases holding projections are derived and rebuildable."
  - q: "When should I use event sourcing versus traditional CRUD?"
    a: "Use event sourcing when audit history is intrinsic, you need temporal queries (state at any past time), multiple read models from one write model, or complex domain workflows with compensating events. Skip it for simple CRUD entities where event log complexity exceeds business value."
  - q: "How do I handle duplicate commands in event sourcing?"
    a: "Make command handlers idempotent using deterministic event IDs, idempotency keys on commands, or aggregate version checks (optimistic concurrency). Store processed command IDs in the aggregate or a side table; reject or no-op duplicates from client retries and message broker redelivery."
---

Support asks what the account balance was on March 3rd at 2 PM. With CRUD you might have a nullable `updated_at` and hope nobody ran a backfill. With event sourcing you replay `AccountCredited`, `AccountDebited`, and `FeeApplied` until that timestamp — exact, auditable, and the same mechanism that rebuilds read models after a bug fix. Event sourcing stores **what happened** as an immutable log; current state is a fold over that log. The pattern pairs naturally with CQRS and domain-driven design, but it pays for itself only when history and rebuildability are product requirements, not because conference talks said CRUD is boring.

## Core concepts

```
Command → Aggregate → Events → Event Store
                              ↓
                         Projections (read models)
```

- **Command** — intent (`TransferFunds`) validated by aggregate rules
- **Event** — immutable fact (`FundsTransferred`) appended to stream
- **Aggregate** — consistency boundary; loads events, applies new ones, enforces invariants
- **Event store** — append-only per aggregate stream

Example aggregate handler (conceptual C#):

```csharp
public class Account : AggregateRoot
{
    public void Transfer(Money amount, AccountId destination, IdempotencyKey key)
    {
        if (ProcessedCommands.Contains(key)) return;

        if (Balance < amount)
            throw new InsufficientFundsException();

        Raise(new FundsTransferred(Id, destination, amount, key, DateTime.UtcNow));
    }

    void Apply(FundsTransferred e) => Balance -= e.Amount;
}
```

Events are past tense nouns — facts, not instructions.

## Event store schema

Minimal stream table:

```sql
CREATE TABLE events (
    stream_id     UUID NOT NULL,
    version       BIGINT NOT NULL,
    event_type    TEXT NOT NULL,
    payload       JSONB NOT NULL,
    metadata      JSONB NOT NULL,  -- correlation_id, causation_id, user_id
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (stream_id, version)
);

CREATE INDEX events_type_idx ON events (event_type, occurred_at);
```

`version` enforces optimistic concurrency — append fails if expected version mismatch ( concurrent write).

Global sequence number optional for cross-aggregate ordering in projections.

Commercial options: EventStoreDB, Marten, Axon Server — or PostgreSQL with careful indexing.

## Snapshots for performance

Replaying 50,000 events per load is slow. Periodic snapshots:

```json
{
  "stream_id": "account-123",
  "version": 50000,
  "state": { "balance": 4200.50, "currency": "USD" }
}
```

Load snapshot at v50000 + replay events 50001+.

Snapshot frequency trade-off: storage vs replay time — nightly or every N events.

## Idempotency and at-least-once delivery

Message brokers redeliver. Clients retry on timeout. Without idempotency:

```csharp
// BAD — double spend on retry
Raise(new FundsTransferred(...)); // twice
```

**Fix:** idempotency key in command stored in aggregate or dedup table:

```sql
CREATE TABLE processed_commands (
    idempotency_key TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL
);
```

Or embed key in event and skip if already applied during load.

## Event schema evolution

Events live forever — plan versioning:

```json
{
  "event_type": "FundsTransferred",
  "schema_version": 2,
  "payload": { "amount_cents": 1000, "currency": "USD" }
}
```

Upcast old v1 events to v2 in application layer on read; avoid mutating stored JSON.

Never delete event types from code while streams contain them — tombstone handlers or migration projections.

## When not to event source

- Simple admin CRUD with no audit mandate
- Teams without appetite for projection rebuild ops
- Heavy relational reporting without projection investment
- "Audit table" satisfies compliance cheaper

Event sourcing adds operational surface: projection lag monitoring, schema migrations, debugging distributed replays.

## CQRS pairing with event sourcing

Event sourcing stores writes as events. CQRS separates read models (projections) from write models (aggregates):

```
Command → Aggregate → Events → Event Store
                              ↓
                    Projection handlers → Read models (SQL, Elasticsearch, cache)
                              ↓
Query ← Read model (optimized for queries)
```

Write side optimized for business rules and consistency. Read side optimized for queries — denormalized, indexed, eventually consistent with write side.

Projection lag is normal — document expected lag (typically seconds, not hours). Monitor:

```sql
-- Projection lag check
SELECT
  stream_id,
  max(event_number) AS latest_event,
  projection_checkpoint,
  max(event_number) - projection_checkpoint AS lag
FROM event_streams
JOIN projection_checkpoints USING (stream_id)
WHERE lag > 1000;  -- alert threshold
```

## Snapshotting for replay performance

Replaying 100k events to rebuild aggregate state is slow. Snapshots capture state at a point:

```python
def load_aggregate(stream_id):
    snapshot = snapshot_store.get_latest(stream_id)
    events = event_store.read(stream_id, from_version=snapshot.version + 1)
    aggregate = snapshot.state
    for event in events:
        aggregate = apply(aggregate, event)
    return aggregate
```

Snapshot every N events (100–1000 depending on apply cost). EventStoreDB supports snapshots natively.

## Event store selection

| Store | Best for |
|---|---|
| EventStoreDB | Purpose-built, streams, projections |
| PostgreSQL (custom) | Teams knowing Postgres, moderate volume |
| Kafka (log compaction) | Already on Kafka, high throughput |
| Marten (.NET) | .NET ecosystem, Postgres-backed |

Don't event-source in vanilla MongoDB without append-only discipline — you lose ordering guarantees.

## Failure modes

- **Projection lag unnoticed** — read model stale; users see old state
- **No idempotency on command handling** — duplicate commands create duplicate events
- **Event schema breaking change** — old events can't be replayed; need upcasting
- **Snapshot not taken** — aggregate replay takes seconds; timeout on load
- **Using event sourcing for simple CRUD** — operational overhead without benefit

## Production checklist

- Idempotency keys on all commands
- Event schema versioning with upcasting for old events
- Snapshots every N events for replay performance
- Projection lag monitored and alerted
- Read model rebuild procedure documented and tested
- Event store backup and restore tested
- CQRS read models clearly labeled as eventually consistent

## Common production mistakes

Teams get event sourcing fundamentals wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of event sourcing fundamentals fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [Event Sourcing (Martin Fowler)](https://martinfowler.com/eaaDev/EventSourcing.html)
- [EventStoreDB documentation](https://www.eventstore.com/documentation)
- [Greg Young — CQRS Documents](https://cqrs.files.wordpress.com/2010/11/cqrs_documents.pdf)
- [Marten .NET event store](https://martendb.io/documentation/events)
- [Versioning in an Event Sourced system (Greg Young talk)](https://www.youtube.com/watch?v=ESjbpuYykhw)
