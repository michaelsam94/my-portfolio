---
title: "Postgres UPSERT Patterns with ON CONFLICT"
slug: "postgres-upsert-on-conflict-patterns"
description: "Master INSERT ON CONFLICT for idempotent writes, partial unique indexes, DO UPDATE vs DO NOTHING, and returning clauses for event-driven sync."
datePublished: "2026-03-09"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "Postgres ON CONFLICT, upsert, DO UPDATE, DO NOTHING, partial unique index upsert"
faq:
  - q: "ON CONFLICT requires what kind of index?"
    a: "A unique constraint or unique index — including partial unique indexes. The conflict target must exactly match the index columns and predicate."
  - q: "DO UPDATE vs DO NOTHING?"
    a: "DO NOTHING for deduplication (webhook idempotency). DO UPDATE for sync (last-write-wins metadata). Always think about which columns should change on conflict."
  - q: "How do I upsert with serializable isolation?"
    a: "Upserts under serializable may retry on serialization failures. Use idempotency keys and application retry with backoff; or lower isolation to read committed for ingest paths with unique constraints."
---

## Idempotent webhook ingest


```sql
CREATE UNIQUE INDEX events_provider_id_idx
  ON inbound_events (provider, external_id);

INSERT INTO inbound_events (provider, external_id, payload)
VALUES ('stripe', 'evt_123', '{"type":"payment"}')
ON CONFLICT (provider, external_id) DO NOTHING
RETURNING id;
-- NULL id in app means duplicate — skip processing
```

## Conditional update on conflict

Use `WHERE` on DO UPDATE to avoid clobbering newer data:


```sql
INSERT INTO inventory (sku, qty, version)
VALUES ('ABC', 10, 1)
ON CONFLICT (sku) DO UPDATE
  SET qty = EXCLUDED.qty,
      version = inventory.version + 1
  WHERE inventory.version < EXCLUDED.version;
```

## Partial unique indexes for soft delete

Unique email only among active users: `UNIQUE (email) WHERE deleted_at IS NULL`. Upsert conflict target must include the same predicate — use `ON CONFLICT ON CONSTRAINT` name for clarity.


## RETURNING clause patterns

INSERT ON CONFLICT DO UPDATE RETURNING id, xmax = 0 AS inserted — distinguishes insert vs update in single round trip.

## Conflict on partial unique index

ON CONFLICT email WHERE deleted_at IS NULL — conflict target must match partial index predicate exactly.

## Batch upsert

Multi-row INSERT with ON CONFLICT reduces round trips — watch lock contention on hot sku row. Retry serialization failures with backoff.

## Idempotency keys table

Separate idempotency_keys with DO NOTHING vs business table upsert — store response blob for replay within 24h window.

## Stripe webhook idempotency pattern

Store event id in inbound_events with DO NOTHING; worker processes only when RETURNING returns id. Duplicate webhook delivery safe without distributed lock — constraint enforces deduplication.

## Monitoring upsert conflict rate

High conflict rate on DO UPDATE may indicate concurrent writers on same key — business logic issue not database tuning. Graph conflicts per minute alongside application retry count.

## EXCLUDED pseudo-table nuances

EXCLUDED refers to proposed insert row in DO UPDATE — cannot reference EXCLUDED in DO NOTHING branch. Column-level update `SET col = COALESCE(EXCLUDED.col, table.col)` preserves existing non-null when incoming null means no-change in partial sync payloads.

## Deadlock risk on concurrent upserts

Two transactions upsert same key in opposite lock order on multiple tables — deadlock detected. Consistent table lock order in application or single-statement upsert per transaction reduces incidence. Retry 40P01 with jitter in worker consumers.

## ORM support gaps

SQLAlchemy on_conflict_do_update, Django bulk_create ignore_conflicts, Prisma upsert — verify generated SQL matches partial index conflict target. ORM abstraction leaking wrong ON CONFLICT columns fails silently at runtime on first conflict.

## INSERT ... ON CONFLICT on partitioned table

Conflict target must include partition key — upsert into monthly partition direct when partition key in INSERT list. Upsert into parent routes to correct partition — constraint must exist on each partition or parent with included partition key.

## Counters with upsert

```sql
INSERT INTO view_counts (page_id, views) VALUES ($1, 1)
ON CONFLICT (page_id) DO UPDATE SET views = view_counts.views + 1;
```

Hot counter row serializes writes — consider batch increment in Redis flush periodic or partition counters by page_id hash to spread lock contention.

## RETURNING for event sourcing

Upsert emitting xmax or (xmax = 0) distinguishes insert event from update event in outbox publisher — single round trip drives event type without extra SELECT.

## Multi-column conflict targets

ON CONFLICT (tenant_id, external_id) matches composite unique — common multitenancy ingest pattern. Partial unique WHERE deleted_at IS NULL requires matching inference specification or constraint name ON CONFLICT ON CONSTRAINT name.

## Write-heavy upsert batch size

Batch 1000 rows per INSERT multi-value upsert — sweet spot before lock duration hurts concurrent readers. Tune batch size per table lock metrics; smaller batches for hot sku counter row.

## Testing upsert idempotency

Two identical webhook payloads parallel POST — assert single row and single side effect (email sent once). Property-based test generates random external_id collisions to verify DO NOTHING path.

## ON CONFLICT DO UPDATE excluded column reference

EXCLUDED.col refers to would-have-been-inserted value — useful for merge sync: SET updated_at = now(), payload = EXCLUDED.payload WHERE table.updated_at < EXCLUDED.updated_at. LWW timestamp column must be source-of-truth timezone UTC.

## Serializable isolation and upsert

Serializable upsert may raise serialization_failure — retry whole transaction. Application idempotency key header plus upsert makes retry safe for webhook consumer — document max retry count and DLQ after N failures.

## Foreign key after upsert

Upsert parent then child in one transaction — child FK references parent id from RETURNING clause. Order matters when both tables upserted — defer FK check CONSTRAINT DEFERRABLE if complex graph insert in single transaction batch job.

## Monitoring duplicate skip rate

DO NOTHING upsert with zero RETURNING rows increments duplicate counter metric — spike normal during webhook replay attack; flatline during outage may mean consumer stopped processing. Alert on absence of duplicates when traffic expected.

## Comparison with MERGE (SQL:2023)

Postgres MERGE statement alternative in PG15+ — upsert readable for multi-action rules. ON CONFLICT still idiomatic; MERGE when conditional update/delete branches complex — team style guide picks one pattern per codebase for review consistency.

## Summary

Choose DO NOTHING for idempotent ingest, DO UPDATE with conditional WHERE for sync, always match conflict target to exact unique index definition including partial predicates, and monitor conflict skip rate plus serialization retries in production metrics.

## Closing notes

Load test concurrent upsert on hot key before flash sale — serialization failure rate and lock wait time inform decision between upsert and queue-serialized updates for inventory counter pattern.

## Additional guidance

Webhook consumers should use upsert RETURNING to detect duplicate delivery versus new event — metric duplicate_rate baseline expected low; alert when zero duplicates during replay test after consumer deploy verifies DO NOTHING path still wired correctly and not accidentally replaced with DO UPDATE clobbering state on redelivered events during broker failure recovery scenario.

Extended webhook idempotency narrative: Stripe sends same event_id at-least-once during network partition recovery — INSERT ON CONFLICT DO NOTHING on events_stripe table with unique event_id returns zero rows on duplicate, worker exits early before side effect email send. Bug shipped when developer used DO UPDATE SET processed_at = now() on every delivery causing duplicate shipment emails when UPDATE path ran on redelivery because RETURNING always returned row — regression test asserts email service called once across two identical webhook POSTs in parallel threads Testcontainers integration suite.

Batch ingest CSV uses multi-row upsert with ON CONFLICT DO UPDATE SET quantity = EXCLUDED.quantity WHERE EXCLUDED.version > table.version optimistic locking — version column incremented only on actual value change reduces write amplification when file contains unchanged rows on nightly supplier sync job processing hundred-thousand SKUs idempotently.

Integration test fires duplicate webhook payloads concurrently — assert single side effect and DO NOTHING path returns null id; prevents DO UPDATE regression re-sending fulfillment email on Stripe replay.

Property-based test generates random external_id collisions verifying ON CONFLICT DO NOTHING idempotency — catches ORM upgrade changing upsert SQL to clobber rows on duplicate webhook delivery.

Partial unique index ON CONFLICT must name constraint explicitly in SQL when predicate involved — ON CONFLICT ON CONSTRAINT uq_events_active_email clearer than column list matching partial index WHERE deleted_at IS NULL and reduces migration failure when duplicate partial indexes exist from manual hotfix.

Monitor lock wait time on hot upsert keys during flash sale — high waits suggest queue-serialized update pattern or sharded counter table better than single-row ON CONFLICT DO UPDATE incrementing shared inventory sku row.

Export conflict_rate metric from upsert RETURNING null count — Grafana panel on webhook consumer dashboard shows duplicate delivery baseline; alert when zero during replay test after deploy.

Verify settings in staging load test before every major sale event.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
