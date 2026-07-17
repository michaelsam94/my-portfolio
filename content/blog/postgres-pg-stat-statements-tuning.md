---
title: "Postgres pg_stat_statements for Query Tuning"
slug: "postgres-pg-stat-statements-tuning"
description: "Enable pg_stat_statements, interpret total_time vs mean_time, find regressions after deploys, and reset safely in production."
datePublished: "2026-02-25"
dateModified: "2026-02-25"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
  - "Observability"
keywords: "pg_stat_statements, query performance Postgres, top queries by total time, shared_blks_read"
faq:
  - q: "total_time or mean_time for prioritization?"
    a: "Rank by total_time (or total_exec_time) to find queries consuming the most cluster capacity. mean_time finds slow individual executions; a fast query run millions of times dominates total_time."
  - q: "How do I reset pg_stat_statements in prod?"
    a: "Use `pg_stat_statements_reset()` for specific queryids after fixing a query, or snapshot to a metrics table before reset. Avoid global reset during incidents — you lose comparison baseline."
  - q: "Does pg_stat_statements show prepared statement text?"
    a: "It normalizes parameters to `$1`, `$2`. Use `queryid` to track the same logical query across ORM versions that change whitespace."
---

## Finding the real CPU hogs


```sql
SELECT queryid,
       calls,
       round(total_exec_time::numeric, 2) AS total_ms,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       rows,
       shared_blks_read
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

## Regression detection workflow

Export top 50 queryids nightly to Prometheus or ClickHouse. Alert when mean_exec_time doubles for a stable queryid. Pair with deploy markers — ORM upgrades change query text but often preserve queryid.

## IO vs CPU bound queries

High `shared_blks_read` relative to calls indicates cache misses — index missing or working set exceeds shared_buffers. High mean time with low blocks suggests CPU-heavy sorts or JSON parsing in SQL.

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

Measure before optimizing postgres pg stat statements tuning. Capture baseline p50/p95 latency, error rate, and resource utilization under representative load. Change one variable at a time — pool size, batch size, timeout, cache TTL — and re-measure.

CPU profiling often reveals unexpected hotspots: JSON serialization, regex in middleware, or ORM hydration of wide entities. IO profiling reveals N+1 queries, missing indexes, and pool wait time dominating tail latency.

Cache only what is expensive to compute and safe to stale. Document TTL rationale. Invalidate on write where consistency matters; accept eventual consistency where product allows.

## Rollout and migration

Ship postgres pg stat statements tuning changes behind feature flags when behavior crosses service boundaries. Use canary deploys with automatic rollback on error rate or latency regression.

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

Assign an owner for postgres pg stat statements tuning standards: code templates, lint rules, and onboarding docs. Platform teams provide paved roads; product teams stay responsible for SLOs.

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
