---
title: "AI Agents: Outbox Pattern Reliable Events"
slug: "agent-outbox-pattern-reliable-events"
description: "Use the transactional outbox so agent run completions and tool side effects publish domain events atomically with Postgres commits — relay workers, idempotent consumers, and why dual-write breaks billing."
datePublished: "2024-11-06"
dateModified: "2024-11-06"
tags: ["AI Agents", "Events", "Distributed Systems", "Postgres"]
keywords: "transactional outbox pattern, agent domain events, reliable event publishing, outbox relay worker, dual write problem"
faq:
  - q: "What problem does the outbox pattern solve for agent platforms?"
    a: "When an agent run completes, you must persist final status in Postgres AND notify webhooks, search indexes, and billing consumers. Updating the DB then publishing to Kafka is two writes — either can fail independently, causing charged-but-not-recorded or recorded-but-not-billed states. Outbox makes both atomic in one transaction."
  - q: "Who reads the outbox table?"
    a: "A dedicated relay process (polling or logical replication) reads unpublished rows, publishes to your broker or invokes webhooks, then marks rows published. It is not application request code — it runs continuously with retries and metrics."
  - q: "At-least-once delivery — is that acceptable?"
    a: "Yes, if downstream consumers are idempotent on `event_id`. Outbox guarantees no lost events after commit; duplicates happen on relay retry. Design consumers with dedupe stores or natural keys, not wishful exactly-once."
  - q: "Outbox vs change data capture (CDC)?"
    a: "CDC streams all table changes — great for analytics sync. Outbox emits curated domain events with explicit payloads and versioning for product workflows. Many agent stacks use both: outbox for `RunCompleted`, CDC for warehouse mirrors."
---

The billing team found four hundred agent runs marked `completed` in Postgres with no corresponding `run.completed` events in Kafka — and eighty-seven webhook deliveries charged twice. Root cause: the orchestrator updated run status, then called `producer.send()`. On process crash between the two, events vanished. On retry after timeout, events duplicated. The fix was not "better retry logic" in the request handler; it was the transactional outbox — one commit, guaranteed relay, idempotent consumers.

## Dual-write failure modes

```
Request handler (broken pattern)
─────────────────────────────────
  BEGIN
    UPDATE agent_runs SET status='completed'
  COMMIT                         ✓ row saved
  kafka.send(run.completed)      ✗ broker timeout → event lost

  OR

  kafka.send()                   ✓ delivered
  UPDATE ...                     ✗ DB down → orphan event, no row
```

Users see completed runs; finance never meters them. Or finance meters ghost runs that rolled back. Agent platforms with tool side effects amplify the damage — downstream automations fire on events, not DB rows product managers query.

## Outbox in one transaction

```
  BEGIN
    UPDATE agent_runs SET status='completed', finished_at=now() WHERE run_id=$1;
    INSERT INTO outbox (event_id, aggregate_type, aggregate_id, payload, created_at)
    VALUES ($2, 'AgentRun', $1, $3, now());
  COMMIT
       │
       ▼
  Relay worker (separate process)
    SELECT * FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT 100
    → publish to Kafka / HTTP webhook
    → UPDATE outbox SET published_at=now() WHERE event_id=$2
```

If the process dies after commit but before relay, rows remain unpublished — picked up on next poll. No lost events.

## Schema

```sql
CREATE TABLE outbox (
  id              BIGSERIAL PRIMARY KEY,
  event_id        UUID NOT NULL UNIQUE,
  aggregate_type  TEXT NOT NULL,
  aggregate_id    UUID NOT NULL,
  event_type      TEXT NOT NULL,
  payload         JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  published_at    TIMESTAMPTZ,
  publish_attempts INT NOT NULL DEFAULT 0
);

CREATE INDEX outbox_unpublished_idx
  ON outbox (id)
  WHERE published_at IS NULL;
```

Partial index keeps relay polls fast as published history grows — archive old rows to cold storage monthly.

## Application code — completing a run

```python
import json
import uuid
from dataclasses import dataclass

@dataclass
class RunCompleted:
    run_id: str
    tenant_id: str
    input_tokens: int
    output_tokens: int

def complete_run(conn, run: RunCompleted) -> None:
    event_id = str(uuid.uuid4())
    payload = {
        "event_type": "agent.run.completed",
        "event_id": event_id,
        "run_id": run.run_id,
        "tenant_id": run.tenant_id,
        "input_tokens": run.input_tokens,
        "output_tokens": run.output_tokens,
    }
    with conn.transaction():
        conn.execute(
            """
            UPDATE agent_runs
            SET status = 'completed', finished_at = now(), updated_at = now()
            WHERE run_id = %s AND status = 'running'
            """,
            (run.run_id,),
        )
        conn.execute(
            """
            INSERT INTO outbox (event_id, aggregate_type, aggregate_id, event_type, payload)
            VALUES (%s, 'AgentRun', %s, 'agent.run.completed', %s::jsonb)
            """,
            (event_id, run.run_id, json.dumps(payload)),
        )
```

Status transition and event insert share the transaction boundary — the handler never touches Kafka directly.

## Relay worker

```python
import time
import psycopg
from kafka import KafkaProducer

producer = KafkaProducer(bootstrap_servers="kafka:9092")

def relay_batch(conn) -> int:
    with conn.transaction():
        rows = conn.execute(
            """
            SELECT id, event_id, event_type, payload
            FROM outbox
            WHERE published_at IS NULL
            ORDER BY id
            FOR UPDATE SKIP LOCKED
            LIMIT 50
            """
        ).fetchall()

        if not rows:
            return 0

        for row in rows:
            producer.send(
                topic="agent.events",
                key=row.payload["run_id"].encode(),
                value=json.dumps(row.payload).encode(),
                headers=[("event_id", row.event_id.encode())],
            )
            conn.execute(
                "UPDATE outbox SET published_at = now(), publish_attempts = publish_attempts + 1 WHERE id = %s",
                (row.id,),
            )
        producer.flush()
    return len(rows)

while True:
    with psycopg.connect(DSN) as conn:
        n = relay_batch(conn)
    time.sleep(0.5 if n else 2)
```

`FOR UPDATE SKIP LOCKED` lets multiple relay instances partition work without double-publish in the same batch. Duplicates still possible if crash occurs after Kafka ack but before `published_at` update — consumers must dedupe.

## Idempotent consumer

```typescript
const seen = new Set<string>(); // production: Redis SET with TTL

async function handleRunCompleted(payload: RunCompletedEvent) {
  if (await dedupe.exists(payload.event_id)) {
    return; // already processed
  }

  await billing.recordUsage({
    tenantId: payload.tenant_id,
    runId: payload.run_id,
    tokens: payload.input_tokens + payload.output_tokens,
  });

  await webhooks.dispatch("run.completed", payload);
  await dedupe.mark(payload.event_id, 86400 * 7);
}
```

Natural keys (`run_id` for billing) provide second-line idempotency if `event_id` dedupe store evicts entries.

## Payload versioning

Agent event schemas evolve — add `schema_version` in payload:

```json
{
  "schema_version": 2,
  "event_type": "agent.run.completed",
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "run_id": "…",
  "tool_calls": [{"name": "github.merge", "status": "ok"}]
}
```

Consumers switch on version; old relays can still publish v1 events until drained. Never mutate published payload shape in place.

## Operational metrics

| Metric | Alert when |
|--------|------------|
| `outbox_unpublished_count` | > 1000 for 5 min — relay stuck |
| `outbox_oldest_unpublished_age_sec` | > 300 — SLA breach for webhooks |
| `relay_publish_errors_total` | spike — broker auth, schema rejection |
| Consumer `duplicate_event_skipped` | sudden drop — dedupe broken, investigate double billing |

Archive published outbox rows older than thirty days to `outbox_archive` — keeps partial index small.

## Outbox vs inbox (related pattern)

**Outbox** — you emit events reliably after local commit.

**Inbox** — you ingest external events idempotently (partner webhook → inbox table → process once).

Agent platforms often need both: outbox for `RunCompleted`, inbox for Stripe webhooks feeding agent resume. Do not conflate the tables.

## When outbox is overkill

If agent runs are fire-and-forget with no billing or external automations, a simple status column suffices. The moment finance, SLAs, or customer webhooks depend on completion signals, dual-write becomes technical debt with invoice-shaped interest.

The four hundred missing events backfilled from outbox unpublished rows after relay deploy — zero manual SQL. The eighty-seven duplicates stopped when consumers keyed billing on `event_id`. One pattern, two incident classes resolved.

## Ordering guarantees downstream cares about

Outbox relay publishes in primary-key order — usually fine for `RunCompleted` events where each `run_id` is independent. If you emit sequenced events for the same aggregate (`RunStarted` before `RunCompleted`), keep them in one transaction as two outbox rows with monotonic `id` — relay order preserves causal sequence per process.

Cross-aggregate ordering (tenant A before tenant B) is **not** guaranteed and rarely needed. Document that webhooks may arrive out of order; consumers reconcile by reading latest DB state when event order ambiguous.

## Poison messages and dead-letter handling

When `payload` fails schema validation at the broker or consumer permanently rejects an event, do not block the relay forever:

```python
MAX_ATTEMPTS = 10

def relay_row(conn, row):
    try:
        publish(row)
        mark_published(conn, row.id)
    except ValidationError as e:
        conn.execute(
            """
            UPDATE outbox
            SET publish_attempts = publish_attempts + 1,
                last_error = %s
            WHERE id = %s
            """,
            (str(e)[:500], row.id),
        )
        if row.publish_attempts + 1 >= MAX_ATTEMPTS:
            move_to_dead_letter(conn, row)
            mark_published(conn, row.id)  # stop blocking queue
```

Dead-letter table gets human review — fix payload generation bug, replay manually. Alert on any dead-letter insert; silent accumulation means billing holes return.

## Testing the outbox in CI

Spin Postgres + test relay in integration tests:

```python
def test_complete_run_emits_outbox_event(db):
    run_id = create_running_run(db)
    complete_run(db, RunCompleted(run_id, "tenant-1", 100, 50))

    row = db.one("SELECT * FROM outbox WHERE aggregate_id = %s", run_id)
    assert row.event_type == "agent.run.completed"
    assert row.published_at is None

    relay_once(db)
    row = db.one("SELECT * FROM outbox WHERE aggregate_id = %s", run_id)
    assert row.published_at is not None
```

Kill relay mid-batch in chaos tests — verify unpublished count returns to zero after restart without duplicate billing in mock consumer.

## Scaling the relay without reordering chaos

When unpublished outbox depth consistently exceeds five thousand rows, split relay by `aggregate_type` or shard on `id % N` workers — each shard runs `FOR UPDATE SKIP LOCKED` against its slice. Avoid publishing the same `event_id` from two shards by partitioning on primary key ranges, not arbitrary filters. Throughput scales linearly until Kafka or Postgres becomes the bottleneck; watch replication lag on the outbox table if relay and OLTP share the same primary.

## Resources

- [Microservices.io — Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [Debezium Outbox Event Router](https://debezium.io/documentation/reference/stable/transformations/outbox-event-router.html)
- [Enterprise Integration Patterns — Guaranteed Delivery](https://www.enterpriseintegrationpatterns.com/patterns/messaging/GuaranteedMessaging.html)
- [PostgreSQL SELECT FOR UPDATE SKIP LOCKED](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
- [Apache Kafka Producer Documentation](https://kafka.apache.org/documentation/#producerapi)
