---
title: "Inbox Pattern Dedup for Agent Event Processing"
slug: "agent-inbox-pattern-dedup"
description: "Implement the transactional inbox pattern for agent pipelines—deduplicate webhook and queue deliveries, co-locate outbox writes with domain state, and consume exactly-once semantics on at-least-once brokers."
datePublished: "2024-11-08"
dateModified: "2024-11-08"
tags: ["AI Agents", "Event-Driven", "PostgreSQL", "Reliability"]
keywords: "inbox pattern, message deduplication, transactional inbox, agent event processing, at-least-once delivery, outbox inbox"
faq:
  - q: "How is the inbox pattern different from a generic dedup table?"
    a: "The inbox stores incoming message IDs inside the same database transaction as domain writes—accept ticket, create run row, mark message processed atomically. A standalone dedup cache can claim a message then crash before business logic completes, leaving inconsistent state. Inbox couples receipt with effect."
  - q: "What should the inbox dedup key be for agent events?"
    a: "Prefer upstream message_id from the broker or webhook (SQS MessageId, Kafka record headers, GitHub X-GitHub-Delivery). Fall back to hash(source, event_type, stable_payload_fields). Never use wall-clock time or consumer offset alone."
  - q: "Can inbox and outbox live in the same service?"
    a: "Yes—common in agent orchestrators. Inbox ingests external triggers; outbox publishes downstream run-step events. Both use the same Postgres instance and transaction boundaries. Keep tables separate; do not reuse message IDs across directions."
  - q: "When should processed inbox rows be deleted?"
    a: "Archive or partition by processed_at after retention window (7–30 days). Deletes enable replay only through explicit re-ingestion with new IDs. For compliance, move to cold storage instead of hard delete if audit requires proof of handling."
---

Slack delivered the same `app_mention` event twice. Our agent posted two identical replies, started two runs, and billed two inference calls. The consumer had **at-least-once** delivery — correct behavior. Our handler had read-check-insert dedup in Redis — **not** in the same transaction as `INSERT INTO agent_runs`. The crash window between dedup claim and run creation was milliseconds wide and happened every deploy.

The **transactional inbox pattern** fixes this: record the incoming message ID in an inbox table **in the same database transaction** that creates the run. Duplicate deliveries hit a primary key conflict and exit without side effects. At-least-once upstream becomes effectively-once downstream.

## Inbox vs outbox — when to use which

| Pattern | Direction | Solves |
|---------|-----------|--------|
| Outbox | Internal → broker | Reliable publish after DB commit |
| Inbox | External → internal | Reliable dedup on consume |
| Inbox + outbox | Bidirectional agent hub | End-to-end saga consistency |

Agent platforms ingest webhooks (GitHub, Slack, Zendesk) and queue messages (SQS, Kafka). Each delivery is a candidate duplicate. The inbox is the gate before any LLM spend.

## Schema design

```sql
CREATE TABLE inbox_messages (
  message_id      TEXT NOT NULL,
  source          TEXT NOT NULL,          -- slack, github, sqs
  event_type      TEXT NOT NULL,
  payload         JSONB NOT NULL,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  processed_at    TIMESTAMPTZ,
  status          TEXT NOT NULL DEFAULT 'pending',  -- pending | processed | failed
  error           TEXT,
  run_id          UUID,
  PRIMARY KEY (source, message_id)
);

CREATE INDEX inbox_pending_idx ON inbox_messages (received_at)
  WHERE status = 'pending';

CREATE INDEX inbox_processed_at_idx ON inbox_messages (processed_at)
  WHERE status = 'processed';
```

Composite primary key `(source, message_id)` prevents cross-source collision. Slack and GitHub both generate UUID-like IDs — namespace by source.

Domain table links optionally:

```sql
ALTER TABLE agent_runs ADD COLUMN inbox_message_id TEXT;
ALTER TABLE agent_runs ADD COLUMN inbox_source TEXT;
CREATE UNIQUE INDEX agent_runs_inbox_unique
  ON agent_runs (inbox_source, inbox_message_id)
  WHERE inbox_message_id IS NOT NULL;
```

## Transactional ingest flow

```python
async def handle_slack_event(event: dict, message_id: str) -> None:
    async with db.transaction():
        # Step 1: claim inbox row — duplicate raises UniqueViolation
        try:
            await db.execute(
                """
                INSERT INTO inbox_messages (message_id, source, event_type, payload, status)
                VALUES ($1, 'slack', $2, $3, 'pending')
                """,
                message_id,
                event["type"],
                json.dumps(event),
            )
        except UniqueViolation:
            metrics.increment("inbox.duplicate_skipped")
            return  # already handled or in progress

        # Step 2: domain logic in same transaction
        run_id = uuid4()
        await db.execute(
            """
            INSERT INTO agent_runs (id, agent_id, trigger_payload, inbox_source, inbox_message_id)
            VALUES ($1, $2, $3, 'slack', $4)
            """,
            run_id,
            "support-agent",
            json.dumps(event),
            message_id,
        )

        # Step 3: mark processed
        await db.execute(
            """
            UPDATE inbox_messages
            SET status = 'processed', processed_at = now(), run_id = $1
            WHERE source = 'slack' AND message_id = $2
            """,
            run_id,
            message_id,
        )

    # Step 4: after commit — enqueue async work (outbox or direct queue)
    await queue.enqueue("execute_run", {"run_id": str(run_id)})
```

If the transaction rolls back, the message was never marked processed — safe redelivery. If commit succeeds, duplicates skip at Step 1.

## Handling in-progress duplicates

Two concurrent deliveries may both pass INSERT before either commits — Postgres serializes one winner. The loser gets `UniqueViolation` and returns. No Redis SETNX race.

For long-running processing, optional **`processing` lease**:

```sql
ALTER TABLE inbox_messages ADD COLUMN locked_until TIMESTAMPTZ;

-- On ingest, if row exists and status=pending and locked_until < now(), reclaim
UPDATE inbox_messages
SET locked_until = now() + interval '5 minutes'
WHERE source = $1 AND message_id = $2 AND status = 'pending'
  AND (locked_until IS NULL OR locked_until < now())
RETURNING *;
```

Use leases only when transaction spans external IO — prefer keeping transactions short and moving LLM work post-commit.

## Webhook handler with inbox dedup

```typescript
// handlers/slack-webhook.ts
import { pool } from "../db";

export async function slackWebhook(req: Request, res: Response) {
  const messageId = req.headers["x-slack-request-timestamp"] + ":" + req.body.event_id;
  // Prefer event_id from payload — unique per event
  const stableId = req.body.event_id as string;

  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    const insert = await client.query(
      `INSERT INTO inbox_messages (message_id, source, event_type, payload)
       VALUES ($1, 'slack', $2, $3)
       ON CONFLICT (source, message_id) DO NOTHING
       RETURNING message_id`,
      [stableId, req.body.type, req.body]
    );

    if (insert.rowCount === 0) {
      await client.query("ROLLBACK");
      res.status(200).json({ ok: true, deduplicated: true });
      return;
    }

    const runResult = await client.query(
      `INSERT INTO agent_runs (agent_id, trigger_payload, inbox_source, inbox_message_id)
       VALUES ($1, $2, 'slack', $3) RETURNING id`,
      ["support-agent", req.body, stableId]
    );

    await client.query(
      `UPDATE inbox_messages SET status = 'processed', processed_at = now(), run_id = $1
       WHERE source = 'slack' AND message_id = $2`,
      [runResult.rows[0].id, stableId]
    );

    await client.query("COMMIT");
    res.status(200).json({ ok: true, run_id: runResult.rows[0].id });

    // Async — outside transaction
    await enqueueRun(runResult.rows[0].id);
  } catch (err) {
    await client.query("ROLLBACK");
    throw err;
  } finally {
    client.release();
  }
}
```

Respond 200 to Slack even on dedup — platforms retry non-2xx indefinitely.

## Queue consumer variant

For SQS/Kafka, extract broker-native IDs:

```python
def inbox_key_from_sqs(record: dict) -> tuple[str, str]:
    return ("sqs", record["messageId"])

async def consume(record: dict) -> None:
    source, message_id = inbox_key_from_sqs(record)
    body = json.loads(record["body"])

    async with db.transaction():
        inserted = await try_inbox_insert(source, message_id, body)
        if not inserted:
            return
        run_id = await create_run_from_payload(body)
        await mark_inbox_processed(source, message_id, run_id)

    await execute_run_async(run_id)
    await ack_sqs(record)
```

Ack **after** transaction commit — acking before commit loses messages on crash; acking before inbox insert duplicates work.

## Pairing inbox with outbox

After run creation, publish `run.created` reliably:

```python
async with db.transaction():
    # inbox insert + run create (as above)
    await db.execute(
        """
        INSERT INTO outbox_events (aggregate_id, event_type, payload)
        VALUES ($1, 'run.created', $2)
        """,
        run_id,
        json.dumps({"run_id": str(run_id)}),
    )
```

Outbox relay reads `outbox_events` and publishes to Kafka. Inbox guarantees no duplicate runs; outbox guarantees no lost downstream notifications.

## Poison messages and failed inbox rows

When processing fails after inbox insert but before `processed`:

```python
except PermanentError as e:
    await db.execute(
        """
        UPDATE inbox_messages
        SET status = 'failed', error = $1, processed_at = now()
        WHERE source = $2 AND message_id = $3
        """,
        str(e), source, message_id,
    )
    await dlq.send(original_payload)
```

Do not delete inbox rows on failure — status `failed` blocks infinite retry loops. Operators replay from DLQ with a **new synthetic message_id** after fixing the bug, or bump handler version and reset specific rows under change control.

## Retention and partitioning

Inbox tables grow without bounds. Partition by month:

```sql
CREATE TABLE inbox_messages_2025_11 PARTITION OF inbox_messages
  FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
```

Drop partitions after retention. For SOC2, export to S3 before drop.

## Observability

Metrics:

- `inbox.duplicate_skipped` — should correlate with broker redelivery rate
- `inbox.insert_to_process_latency` — transaction duration
- `inbox.failed_total` — poison or schema bugs
- `inbox.pending_age_max` — stuck messages

Alert when pending rows age > 10 minutes — consumer may be down or deadlock.

Trace propagation: attach `message_id` and `run_id` to OpenTelemetry spans from webhook ingress through LLM completion.

## Testing inbox dedup

```python
@pytest.mark.asyncio
async def test_duplicate_webhook_creates_one_run():
    event = {"event_id": "Ev123", "type": "app_mention", "text": "help"}
    await handle_slack_event(event, "Ev123")
    await handle_slack_event(event, "Ev123")  # duplicate delivery

    runs = await db.fetch("SELECT * FROM agent_runs WHERE inbox_message_id = 'Ev123'")
    assert len(runs) == 1

    inbox = await db.fetchrow(
        "SELECT status FROM inbox_messages WHERE source = 'slack' AND message_id = 'Ev123'"
    )
    assert inbox["status"] == "processed"
```

Concurrent test with asyncio.gather on same message_id — expect one success, one duplicate skip.

## Common pitfalls

**Inbox in Redis, runs in Postgres.** Not transactional — the original bug pattern.

**Using payload hash as sole ID when payload includes timestamps.** Every redelivery looks new. Use broker message ID.

**Long transactions including LLM calls.** Holds locks, kills throughput. Inbox + commit + async execute.

**200 OK before commit.** Upstream thinks you handled it; DB rolls back — message lost. Commit then respond.

**Ignoring failed status on replay.** Same bad message loops forever — mark failed, DLQ, alert.

## The takeaway

The inbox pattern gives agent pipelines deduplication that survives crashes and concurrent deliveries: insert the message ID and domain state in one transaction, skip on primary key conflict, process async after commit, and pair with outbox for downstream reliability. At-least-once webhooks and queues stop multiplying runs and LLM bills — duplicates become a metric, not an incident.

## Resources

- [Microservices.io — Transactional inbox pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [Chris Richardson — Idempotent consumer / duplicate detection](https://microservices.io/post/architecture/saga/2020/10/12/duplicate-message-handling.html)
- [PostgreSQL — INSERT ON CONFLICT documentation](https://www.postgresql.org/docs/current/sql-insert.html)
- [AWS — SQS exactly-once processing patterns](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-exactly-once-processing.html)
- [Debezium — Inbox event router SMT](https://debezium.io/documentation/reference/stable/transformations/inbox-event-router.html)
