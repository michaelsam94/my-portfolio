---
title: "Database Connection Pool Capacity Planning"
slug: "devops-database-connection-pools"
description: "Size PgBouncer and app pools from pod count and query concurrency."
datePublished: "2026-07-04"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Capacity Planning"
  - "Platform"
keywords: "connection pool sizing, PgBouncer, max_connections, Postgres pooling, HikariCP"
faq:
  - q: "Why did doubling Kubernetes pods exhaust Postgres max_connections?"
    a: "Each pod multiplied pool_max connections; total exceeded max_connections without PgBouncer transaction pooling."
  - q: "How should per-pod pool size be chosen?"
    a: "From measured concurrent in-flight queries and pool wait metrics—not default thread counts."
  - q: "What is the difference between PgBouncer transaction and session pooling?"
    a: "Transaction mode multiplexes many clients onto fewer backends but breaks naive prepared statements without ORM tuning."
  - q: "How validate pool sizing before a scale event?"
    a: "Load test at target pod count; watch pg_stat_activity, PgBouncer cl_waiting, and pool acquire p99."
---
Autoscaler added forty pods; Postgres logged too many clients already within ninety seconds.

## Sizing math

pods times pool_max must stay below max_connections minus admin reserve. Document formula before every HPA max increase.

A production team running database connection pools discovered that sizing math failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for sizing math: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For database connection pools, instrument sizing math with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for sizing math: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for sizing math belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for database connection pools: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in sizing math
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for sizing math, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## PgBouncer modes

Transaction pooling multiplexes clients; disable naive prepared statements. Session mode for LISTEN/NOTIFY workloads only.

A production team running database connection pools discovered that pgbouncer modes failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for pgbouncer modes: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For database connection pools, instrument pgbouncer modes with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for pgbouncer modes: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for pgbouncer modes belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for database connection pools: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in pgbouncer modes
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for pgbouncer modes, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Per-service defaults

HTTP APIs often need five to ten connections per pod based on measured pool waits—not thread defaults of thirty.

A production team running database connection pools discovered that per-service defaults failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for per-service defaults: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For database connection pools, instrument per-service defaults with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for per-service defaults: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for per-service defaults belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for database connection pools: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in per-service
defaults configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for per-service defaults, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Kubernetes surges

Rolling deploys briefly double pods; include CronJob pools; separate read-replica pool endpoints.

A production team running database connection pools discovered that kubernetes surges failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for kubernetes surges: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For database connection pools, instrument kubernetes surges with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for kubernetes surges: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for kubernetes surges belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for database connection pools: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in kubernetes
surges configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for kubernetes surges, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Observability

pg_stat_activity, cl_waiting, Hikari active connections, acquire p99—alert before users see timeouts.

A production team running database connection pools discovered that observability failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for observability: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For database connection pools, instrument observability with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for observability: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for observability belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for database connection pools: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in observability
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for observability, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## PgBouncer transaction mode snippet

```ini
[databases]
appdb = host=postgres.internal dbname=appdb pool_mode=transaction
[pgbouncer]
default_pool_size = 50
max_client_conn = 2000
```

Set ORM `prepareThreshold=0` when using transaction pooling. Size `pods × pool_max` before the next HPA max raise—connection math fails before CPU does.
