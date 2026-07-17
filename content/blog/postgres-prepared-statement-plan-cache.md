---
title: "Postgres Prepared Statements and Plan Cache"
slug: "postgres-prepared-statement-plan-cache"
description: "Understand prepared statement lifecycle, generic vs custom plans, PgBouncer limitations, and ORM settings that cause plan cache churn or wrong plans."
datePublished: "2026-02-28"
dateModified: "2026-07-17"
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


## Prepared statements and PgBouncer

Named prepared statements tied to backend connection — transaction pooling incompatible unless unnamed one-shot prepare. JDBC prepareThreshold default 5 — tune per pool mode.

## Generic vs custom plans

Postgres may switch to generic plan after five executes — bad for skewed data. plan_cache_mode force_custom_plan session-level for known skew queries.

## ORM statement cache sizing

Hibernate statement cache unbounded grows memory — set max statements. Restart pool after schema migration to flush stale plans.

## Deallocate after DDL

Migration changes column type — prepared plans invalid until deallocate. Migration runner executes DEALLOCATE ALL on deploy.

## Measuring plan cache hit rate

log_planner_stats or pg_stat_statements plan time vs execution time divergence suggests replanning overhead. Spikes after statistics change — correlate with ANALYZE schedule and autovacuum.

## Connection pool churn

PgBouncer max_client_conn high with low server conn causes prepare on wrong backend — disable prepare or use session mode for ORMs that aggressively prepare. Document decision in service runbook for on-call.

## JDBC and Node pg behavior

pg driver prepares by default after few executions — with PgBouncer transaction pooling set `{ prepare: false }` in node-postgres pool config. Document in service README — new hire copying Stack Overflow pool config re-enables prepares and causes prod flakes.

## SPI and prepared plans in functions

PL/pgSQL functions may cache plans differently — dynamic SQL EXECUTE still replans. Do not assume app-level prepare fixes slow function — EXPLAIN ANALYZE the function call itself.

## Measuring prepare overhead

log_min_duration_statement with log_duration on staging — compare first vs fifth execution latency. If fifth is 10x faster, prepare helps; if flat, prepare adds round trip without benefit on short queries.

## EFM/prepare in SQLAlchemy

create_engine(..., connect_args={"prepare_threshold": None}) disables prepare entirely for PgBouncer transaction mode compatibility. SQLAlchemy 2.0 execution_options prepared_statement_cache_size per connection — tune when session pooling without PgBouncer.

## Caching invalidation on schema change

Flyway migrate runs DEALLOCATE ALL via afterMigrate callback — prevents first-request-after-deploy errors. Liquibase equivalent custom changeset runs on deployment hook before traffic shift.

## Prepared statements and RLS

RLS policy qual evaluated per execution — prepared plan must account for parameter values affecting policy if using session variables — rare footgun when SET app.user_id changes mid-connection in session pool mode.

## Named prepared statement leak

Connection returned to pool with prepared statements still open — next client gets wrong plan association on PgBouncer transaction mode. DISCARD ALL on connection checkout from pool optional heavy hammer; prefer prepare_threshold None in drivers.

## Python psycopg3 autocommit and prepare

Autocommit single-statement transactions still benefit from unnamed prepare on repeated SELECT — different from PgBouncer interaction; test psycopg3 prepare_threshold with your pooler mode in staging load test.

## Measuring parse/plan vs execute

pg_stat_statements shows planning time separately PG13+ — if planning_time dominates, prepared statements or plan cache warm helps. If execution dominates, index or query rewrite needed not more prepare.

## Citus and prepared statements

Distributed Postgres may route prepared to coordinator differently — verify Citus docs for prepare support on reference vs distributed tables before enabling ORM prepare globally in sharded deployment.

## Server-side prepare protocol flow

Extended query protocol: Parse, Bind, Execute, Sync — PgBouncer transaction mode drops named statement between transactions. Use unnamed prepared statements only or disable prepare in client — document in connection string comment every service repo README header.

## Node postgres.js prepare:false

Pool config `{ max: 10, options: '-c statement_timeout=30000' }` plus prepare false — verify with pg_stat_activity query showing no prepared statement names accumulating on backend connections through pooler.

## JDBC prepareThreshold=0

Java services on WebLogic or Spring Boot set prepareThreshold=0 in DataSource URL when behind PgBouncer — Spring Boot 3.x documents property spring.datasource.hikari.data-source-properties.prepareThreshold=0.

## Watch ORM upgrades

Minor Hibernate upgrade changed default prepare behavior — caused production incident after harmless dependabot PR. Add integration test asserting no named prepared statements when integration test runs through Testcontainers PgBouncer sidecar in transaction mode mimicking prod.

## Custom plan vs generic for IN lists

Prepared statement with ARRAY parameter expands to generic plan — sometimes worse than literal IN list plan for small arrays. benchmark both; ORM array binding may need unset prepare for specific reporting queries only via native query escape hatch documented in code comment.

## Summary

Match client prepare behavior to pooler mode documented in platform ADR; verify with pg_stat_statements and pg_prepared_statements view after deploy; disable prepare when PgBouncer uses transaction pooling unless using unnamed one-shot prepare only.

## Closing notes

Document prepare strategy per service in ADR: disabled for PgBouncer transaction mode, enabled for direct Postgres session pool — new microservice copies ADR template not neighboring service config blindly.

## Additional guidance

Platform documentation links PgBouncer mode decision tree to ORM prepare settings for Node, Java, Python, and Go drivers — single internal page prevents each team rediscovering prepared statement already exists failure mode during first production load test before launch deadline pressure forces disabling pooler entirely removing connection multiplexing benefit.

Comprehensive driver matrix for platform wiki table: Node pg prepare false with PgBouncer transaction mode; Java prepareThreshold zero same; Python psycopg3 prepare_threshold None; Go pgx default compatible with simple protocol option DisablePreparedStatements when using pooler transaction mode. Go services historically missed this setting causing rare production flakes only under concurrent load when fifth execution prepared on wrong backend connection reassigned by pooler between Parse and Execute extended protocol messages.

Verification query run after deploy from CI job connecting through same pooler config as production: SELECT name FROM pg_prepared_statements should return zero rows when prepare disabled correctly; non-zero rows trigger deploy rollback alert hook integrated with Argo Rollouts analysis template referencing custom prometheus metric from postgres_exporter prepared statement count scrape.

Platform ADR mandates prepare disabled through PgBouncer transaction pool — CI smoke test asserts zero pg_prepared_statements rows after deploy via pooler sidecar identically configured to production connection string secrets.

Run pg_prepared_statements count check from CI through PgBouncer sidecar after every backend deploy — non-zero count pages platform team before connection pooler enters production traffic with incompatible prepare setting.

Document in service README which PgBouncer pool mode staging uses — mismatch between staging session mode and production transaction mode hides prepare incompatibility until launch week load test when intermittent prepared statement already exists errors appear under concurrent checkout traffic only in production pooler configuration.

Spring Boot spring.datasource.hikari.data-source-properties.prepareThreshold=0 belongs in platform Helm chart default values — services inherit unless explicit override documented in service platform.yaml with justification for direct Postgres connection without pooler.

Add PgBouncer mode and prepare setting to service catalog metadata — platform on-call filters incidents by misconfigured prepare without reading each repo connection string during connection pooler outage.

Verify settings in staging load test before every major sale event.

## Resources

- [PostgreSQL documentation](https://www.postgresql.org/docs/)
- [Microservices patterns](https://microservices.io/patterns/)
- [OpenTelemetry docs](https://opentelemetry.io/docs/)
- [12-Factor App](https://12factor.net/)
