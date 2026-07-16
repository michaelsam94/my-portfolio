---
title: "Projections and Read Models"
slug: "event-sourcing-projections-read-models"
description: "Build and rebuild event-sourced read models: synchronous vs asynchronous projections, idempotent consumers, catch-up subscriptions, and schema migration."
datePublished: "2026-02-05"
dateModified: "2026-02-05"
tags: ["Backend", "Event Sourcing", "CQRS", "Architecture"]
keywords: "event sourcing projections, read models CQRS, projection rebuild, asynchronous projector, catch-up subscription, idempotent projection, EventStore subscription"
faq:
  - q: "What is a projection in event sourcing?"
    a: "A projection is a process that consumes events from the event store and updates a read model optimized for queries — SQL tables, Elasticsearch indexes, materialized views. Read models are disposable: delete and rebuild from the event log if logic was wrong."
  - q: "Should projections run synchronously or asynchronously?"
    a: "Synchronous (inline) projections update read models in the same transaction as event append — strong consistency, simpler UX, tighter coupling and write latency. Asynchronous projections scale reads independently but introduce eventual consistency lag you must monitor and design UI around."
  - q: "How do I rebuild a projection after fixing a bug?"
    a: "Stop consumers, truncate or drop the read model storage, reset projector checkpoint to position zero (or snapshot boundary), replay all events through fixed handler, validate counts against golden metrics, resume live subscription from tail. Use blue-green read models for zero-downtime rebuilds in production."
---

The bug lived in the projector for six weeks — every `OrderShipped` event double-counted revenue in the dashboard table while the event log was perfectly correct. Fixing the handler took an hour; rebuilding the read model from three million events took a weekend because nobody had documented checkpoint semantics or tested idempotent replays. Projections are where event-sourced systems meet reality: users query PostgreSQL, not your event JSON. Get projection design wrong and you inherit distributed systems problems without gaining audit benefits — get it right and you can redeploy query schemas faster than competitors migrate monolith tables.

## CQRS split recap

```
Write side: Command → Aggregate → Event Store
Read side:  Events → Projector → Read Model → Query API
```

Multiple projections can consume the same stream:

- `OrderListProjection` → Postgres for admin UI
- `SearchProjection` → Elasticsearch for full-text
- `AnalyticsProjection` → BigQuery for BI

Each optimized independently; same source events.

## Projection handler pattern

```csharp
public class OrderListProjector : IEventHandler
{
    public async Task Handle(OrderPlaced e, CancellationToken ct)
    {
        await db.ExecuteAsync("""
            INSERT INTO order_list (id, customer_id, total, status, placed_at)
            VALUES (@Id, @CustomerId, @Total, 'placed', @At)
            ON CONFLICT (id) DO NOTHING
            """, e, ct);
    }

    public async Task Handle(OrderShipped e, CancellationToken ct)
    {
        await db.ExecuteAsync("""
            UPDATE order_list SET status = 'shipped', shipped_at = @At
            WHERE id = @OrderId
            """, e, ct);
    }
}
```

`ON CONFLICT DO NOTHING` or version columns make handlers safe under at-least-once delivery.

## Checkpoints and subscriptions

Track progress:

```sql
CREATE TABLE projection_checkpoints (
    projector_name TEXT PRIMARY KEY,
    position       BIGINT NOT NULL,  -- global sequence or commit position
    updated_at     TIMESTAMPTZ NOT NULL
);
```

EventStoreDB catch-up subscription:

```csharp
var sub = client.SubscribeToAll(
    EventPosition.Start,
    async (resolved, ct) =>
    {
        await dispatcher.Dispatch(resolved.Event);
        await checkpoint.Save(resolved.OriginalPosition);
    });
```

Batch checkpoint every N events or N seconds — trade crash replay duplication vs write amplification.

## Eventual consistency UX

Async lag of 200ms–2s means:

- **Write-then-read** — API returns event accepted; UI polls or uses WebSocket for confirmation
- **Read-your-writes** — route post-command reads to write-side aggregate or synchronous projection for that request only
- **Display pending state** — "Processing…" beats showing stale data silently

Monitor **projection lag** alert: `now() - last_event_processed_at > 30s`.

## Rebuild strategies

**Big bang rebuild (maintenance window):**

1. Stop projector worker
2. `TRUNCATE order_list`
3. Reset checkpoint to 0
4. Replay from `$all` or category stream
5. Validate row counts vs `SELECT count(*) FROM events WHERE type IN (...)`
6. Start worker

**Blue-green rebuild (live):**

1. Build `order_list_v2` parallel table
2. Replay into v2 while v1 serves traffic
3. Flip read routing flag when caught up
4. Drop v1

Replay throughput: parallelize by partition key if events ordered per aggregate only — global ordering limits single-thread replay.

## Schema migration on read models

Read models evolve freely — events do not:

```sql
ALTER TABLE order_list ADD COLUMN region TEXT;
UPDATE order_list SET region = 'unknown';
-- backfill via replay of RegionAssigned events or one-time migration
```

Prefer backfill from event replay for correctness vs ad hoc SQL guesses.

## Testing projections

- **Given-When-Then** event fixtures → assert read model state
- Property test: replay same events twice → identical table
- Chaos: duplicate event delivery in test harness

```python
def test_shipped_updates_status():
    given([OrderPlaced(...), OrderShipped(...)])
    assert read_model.get(order_id).status == "shipped"
```

## Anti-patterns

- Projector calling external APIs during replay — side effects duplicate; emit integration events instead
- Cross-aggregate SQL joins in projector without clear boundary — coupling streams
- No monitoring on lag — finance discovers discrepancy at month close

Projections are code you will run many times on old data — design for replay as the normal recovery path, not disaster rarity.

## Projection versioning in production

When projector logic changes, you need a version strategy:

```python
@dataclass
class ProjectionCheckpoint:
    stream: str
    position: int
    projector_version: int  # bump when handler logic changes

PROJECTOR_VERSION = 3

def handle(event: Event, state: OrderView) -> OrderView:
    if event.type == "OrderShipped":
        state.status = "shipped"
        state.shipped_at = event.timestamp  # added in v3
    return state
```

**Options when version bumps:**

1. **Full replay** — reset checkpoint, rebuild from `$all` (simple, slow)
2. **Migration handler** — v3 reads v2 table, applies delta (fast, error-prone)
3. **Dual write** — run v2 and v3 parallel until v3 catches up, then cut over

Most teams underestimate replay time. Measure events/sec on a staging copy before promising same-day rebuild. A 500M-event store at 5K events/sec is ~28 hours single-threaded.

## Read model consistency guarantees

Projections are eventually consistent by definition. Document what users see:

| Guarantee | User experience | Implementation |
|-----------|-------------------|----------------|
| Eventual | List may lag seconds | Single projector, at-least-once |
| Read-your-writes | User sees own action immediately | Route reads to writer node or cache invalidation |
| Strong per aggregate | Order detail always current | Project from single stream partition |

Cross-aggregate queries ("total revenue today") will always lag unless you maintain a separate aggregate projection fed by integration events — don't join live projectors ad hoc in SQL.

## Operational monitoring

Dashboard every projector:

- **Lag** — events behind head of stream (alert > 10K or > 5 min)
- **Processing rate** — events/sec (drop indicates poison event or DB slowdown)
- **Error rate** — deserialization failures, constraint violations
- **Checkpoint age** — last successful commit timestamp

Poison events block the entire partition if you fail-stop. Prefer skip-and-dead-letter with manual replay after fix:

```python
try:
    apply(event)
except ProjectionError as e:
    dead_letter.publish(event, error=str(e))
    checkpoint.advance()  # don't block the stream forever
```

Pair with [CQRS command-query separation](https://blog.michaelsam94.com/cqrs-command-query-separation/) when deciding which queries belong in read models vs live aggregates.

## Production checklist

- [ ] Projector version bumped and replay tested on schema change
- [ ] Lag, processing rate, and error rate dashboarded
- [ ] Poison events dead-lettered, not blocking stream
- [ ] Blue-green rebuild procedure documented and drilled
- [ ] No external API calls during replay

## Resources

- [EventStoreDB subscriptions](https://www.eventstore.com/documentation/docs/v23.10/features/subscriptions/)
- [Projections in Event Sourcing (Event Store blog)](https://www.eventstore.com/blog/projections-in-event-sourcing)
- [Marten async projections](https://martendb.io/documentation/events/projections/)
- [CQRS Journey (Microsoft patterns)](https://learn.microsoft.com/en-us/previous-versions/msp-n-p/jj554200(v=pandp.10))
- [Kurrent (formerly Event Store) glossary](https://www.kurrent.io/)
