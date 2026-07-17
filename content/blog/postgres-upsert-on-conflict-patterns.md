---
title: "Postgres UPSERT Patterns with ON CONFLICT"
slug: "postgres-upsert-on-conflict-patterns"
description: "Master INSERT ON CONFLICT for idempotent writes, partial unique indexes, DO UPDATE vs DO NOTHING, and returning clauses for event-driven sync."
datePublished: "2026-03-09"
dateModified: "2026-03-09"
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

## Common production mistakes

Teams ship backend changes without rehearsing failure modes: missing `lock_timeout` on migrations, connection pools sized for app count not PgBouncer multiplexing, and assuming staging EXPLAIN plans match production statistics after a traffic pattern shift. Document trade-offs explicitly — if you chose availability over strict consistency, write that down for the next engineer on call.

## Debugging and triage workflow

When production misbehaves, work top-down:

1. **Confirm scope** — one tenant, region, or deployment stage?
2. **Check recent changes** — deploys, flag flips, schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, traffic vs baseline.
4. **Reproduce minimally** — smallest input that triggers failure; capture traces with correlation IDs.
5. **Fix forward or rollback** — rollback first during incident if faster than root cause.
6. **Add a guard** — alert, integration test, or circuit breaker for this failure class.

## Operational checklist

- **Staging parity** — failure paths (timeouts, retries, partial outages) exercised before prod.
- **Observability** — dashboards and alerts for metrics discussed above; on-call knows where to look.
- **Rollback** — documented revert path without improvising.
- **Load test** — evidence about behavior at expected peak plus headroom, not intuition.

## Performance tuning notes

Measure before optimizing postgres upsert on conflict patterns. Capture baseline p50/p95 latency, error rate, and resource utilization under representative load. Change one variable at a time — pool size, batch size, timeout, cache TTL — and re-measure.

CPU profiling often reveals unexpected hotspots: JSON serialization, regex in middleware, or ORM hydration of wide entities. IO profiling reveals N+1 queries, missing indexes, and pool wait time dominating tail latency.

Cache only what is expensive to compute and safe to stale. Document TTL rationale. Invalidate on write where consistency matters; accept eventual consistency where product allows.

## Rollout and migration

Ship postgres upsert on conflict patterns changes behind feature flags when behavior crosses service boundaries. Use canary deploys with automatic rollback on error rate or latency regression.

For schema changes, prefer expand-contract over big-bang DDL. Never assume maintenance windows are available — design for online migration.

Maintain rollback runbooks: previous container image digest, down migration forward-fix, and feature flag disable path tested quarterly.

## Testing recommendations

Unit test pure domain logic without database. Integration test against real Postgres/Redis/Kafka in CI with Testcontainers.

Contract test API boundaries with Pact or schema fixtures. Chaos test dependency timeouts and verify circuit breakers open.

Load test before marketing launches — synthetic traffic shapes miss fan-out and queue backlog effects seen in production.

## Incident patterns we see

Connection pool exhaustion masquerading as slow queries — graph active connections vs pool max.

Missing idempotency on webhook or queue consumers causing duplicate side effects during at-least-once delivery.

Migration holding ACCESS EXCLUSIVE lock because lock_timeout was not set — traffic pile-up and cascading timeouts.

Retry storms amplifying outage — uncapped retries on 503 increase load on failing dependency.

## Team ownership

Assign an owner for postgres upsert on conflict patterns standards: code templates, lint rules, and onboarding docs. Platform teams provide paved roads; product teams stay responsible for SLOs.

Review this pattern in architecture reviews when touching money, auth, or personal data. Security and compliance questions early beat retrofitting controls later.


## Capacity and cost considerations

Postgres tuning decisions interact with cloud bill line items: larger instances buy more shared_buffers and IO throughput but do not fix N+1 query patterns. Right-size after measuring — a doubled instance hiding missing indexes is wasted spend. Track cost per thousand requests alongside p95 latency when evaluating pooling, caching, and read replica additions.

## Cross-region and DR implications

Replication lag, connection pooler failover, and DNS TTL determine how quickly traffic shifts during regional failure. Rehearse failover quarterly; document whether your pattern favors RPO over RTO or vice versa. Clients with aggressive timeouts may fail over before the database promotion completes — coordinate cutover windows with application drain policies.

## Compatibility matrix

Maintain an internal matrix of validated versions: Postgres major, pooler mode, driver version, and ORM release tested together. Upgrades outside the matrix require explicit sign-off and extended soak in staging with production-shaped load.

## Review cadence

Revisit configuration quarterly even when metrics look flat. Schema drift, new query patterns from product features, and tenant growth change optimal settings silently until an incident exposes them.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
