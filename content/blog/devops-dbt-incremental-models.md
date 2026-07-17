---
title: "dbt Incremental Model Strategies"
slug: "devops-dbt-incremental-models"
description: "Choose merge, delete+insert, and micro-batch incremental strategies correctly."
datePublished: "2026-09-10"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "dbt"
  - "Data Engineering"
keywords: "dbt incremental models, merge strategy, delete+insert, microbatch, unique_key"
faq:
  - q: "When use incremental instead of table materialization?"
    a: "Large tables (100GB+) or hourly refresh where full scans are too costly."
  - q: "merge vs delete+insert incremental strategy?"
    a: "Merge upserts by unique_key; delete+insert replaces partitions when cheaper on your warehouse."
  - q: "Why is unique_key required for merge incrementals?"
    a: "Retries without unique_key duplicate rows silently on partial failure replay."
  - q: "How handle late-arriving facts incrementally?"
    a: "Include a lookback window in the incremental predicate and merge duplicates within that window."
---
Nightly full scan on a ten terabyte fact—materialization stayed table instead of merge incremental.

## Strategy matrix

Append for immutable events; merge with unique_key for upserts; delete+insert for partition replaces.

A production team running dbt incremental models discovered that strategy matrix failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for strategy matrix: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt incremental models, instrument strategy matrix with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for strategy matrix: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for strategy matrix belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt incremental models: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in strategy matrix configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for strategy matrix, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Incremental predicates

is_incremental branch filters on watermark; include lookback for late-arriving facts.

A production team running dbt incremental models discovered that incremental predicates failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for incremental predicates: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt incremental models, instrument incremental predicates with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for incremental predicates: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for incremental predicates belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt incremental models: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in incremental predicates
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for incremental predicates, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Idempotent retries

unique_key required for merge—without it duplicates silently replay after failed runs.

A production team running dbt incremental models discovered that idempotent retries failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for idempotent retries: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt incremental models, instrument idempotent retries with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for idempotent retries: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for idempotent retries belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt incremental models: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in idempotent retries configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for idempotent retries, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Testing

Unit test SQL for is_incremental true/false; integration test retry produces identical row counts.

A production team running dbt incremental models discovered that testing failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for testing: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt incremental models, instrument testing with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for testing: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for testing belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt incremental models: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in testing configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for testing, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Operations

Alert on merge bytes processed ten times baseline—often missing predicate or accidental full refresh.

A production team running dbt incremental models discovered that operations failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for operations: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt incremental models, instrument operations with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for operations: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for operations belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt incremental models: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in operations configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for operations, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

```sql
{% if is_incremental() %}
  where event_time >= (select max(event_time) - interval '3 days' from {{ this }})
{% endif %}
```

Choose merge with explicit `unique_key` for idempotent retries. Monitor merge bytes processed—ten× baseline often indicates missing incremental predicate or full-refresh accident.
