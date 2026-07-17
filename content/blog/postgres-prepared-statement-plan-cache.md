---
title: "Postgres Prepared Statements and Plan Cache"
slug: "postgres-prepared-statement-plan-cache"
description: "Understand prepared statement lifecycle, generic vs custom plans, PgBouncer limitations, and ORM settings that cause plan cache churn or wrong plans."
datePublished: "2026-02-28"
dateModified: "2026-02-28"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
  - "Performance"
keywords: "Postgres prepared statements, plan cache, generic plan, PgBouncer transaction pooling, ORM prepared statements"
faq:
  - q: "Why do prepared statements fail through PgBouncer transaction mode?"
    a: "Prepared statements bind to a session. Transaction pooling returns connections to different clients between transactions, so unnamed prepared statements disappear. Use session pooling, statement pooling disable, or driver `preferQueryMode=simple`."
  - q: "What is the generic plan problem?"
    a: "After five executions Postgres may switch to a generic plan ignoring parameter values — fast for uniform data, catastrophic for skewed columns (status=active vs status=archived). Monitor with `pg_prepared_statements` and `EXPLAIN`."
  - q: "Should Node pg use prepared statements?"
    a: "For OLTP with PgBouncer transaction pool, often no — simple query protocol avoids prepared statement leaks. For session pool or direct connections, prepared statements reduce parse overhead on hot queries."
---

## The PgBouncer surprise

Latency spiked after enabling PgBouncer transaction pooling. Errors: `prepared statement "s0" does not exist`. The Node `pg` driver prepared every query; pooled connections rotated; statements vanished. Fix: `prepare: false` or pool mode `session` for that service.

## Inspecting plan behavior


```sql
PREPARE user_lookup (bigint) AS
  SELECT * FROM orders WHERE user_id = $1;

EXECUTE user_lookup(42);
-- Repeat 5+ times; check if plan uses Index Scan vs Seq Scan for skewed IDs

SELECT name, plans, calls
FROM pg_prepared_statements;
```

## ORM defaults matter

Hibernate, Sequelize, and Prisma make different choices. Document per-service: connection pool mode, prepared statement toggle, and statement timeout. Integration tests should run through the same pooler path as production.

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

Measure before optimizing postgres prepared statement plan cache. Capture baseline p50/p95 latency, error rate, and resource utilization under representative load. Change one variable at a time — pool size, batch size, timeout, cache TTL — and re-measure.

CPU profiling often reveals unexpected hotspots: JSON serialization, regex in middleware, or ORM hydration of wide entities. IO profiling reveals N+1 queries, missing indexes, and pool wait time dominating tail latency.

Cache only what is expensive to compute and safe to stale. Document TTL rationale. Invalidate on write where consistency matters; accept eventual consistency where product allows.

## Rollout and migration

Ship postgres prepared statement plan cache changes behind feature flags when behavior crosses service boundaries. Use canary deploys with automatic rollback on error rate or latency regression.

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

Assign an owner for postgres prepared statement plan cache standards: code templates, lint rules, and onboarding docs. Platform teams provide paved roads; product teams stay responsible for SLOs.

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
