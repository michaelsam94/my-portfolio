---
title: "dbt Snapshots for Slowly Changing Dimensions"
slug: "devops-dbt-snapshot-strategies"
description: "Implement Type 2 history with dbt snapshots and timestamp strategies."
datePublished: "2026-09-11"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "dbt"
  - "Data Engineering"
keywords: "dbt snapshots, SCD2, timestamp strategy, check strategy"
faq:
  - q: "timestamp vs check snapshot strategy?"
    a: "Timestamp when source has reliable updated_at; check when row hash detects change without trustworthy timestamps."
  - q: "Why does check strategy fail on hard deletes?"
    a: "Deleted source rows leave stale current records unless deletes are tracked separately."
  - q: "How often run snapshots?"
    a: "Balance storage cost against analytics and compliance need for historical dimension state."
  - q: "When full-refresh a snapshot?"
    a: "After strategy mistakes or source corruption—plan storage and downstream temporal join impact."
---
Manual SCD2 effective dates were wrong—check strategy on a source that hard-deleted rows corrupted history.

## Timestamp vs check

Timestamp when updated_at is trustworthy; check only when row hash detects change without deletes.

A production team running dbt snapshot strategies discovered that timestamp vs check failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for timestamp vs check: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt snapshot strategies, instrument timestamp vs check with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for timestamp vs check: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for timestamp vs check belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt snapshot strategies: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in timestamp vs
check configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for timestamp vs check, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Type 2 columns

dbt_valid_from and dbt_valid_to; analytics use as-of joins for point-in-time reporting.

A production team running dbt snapshot strategies discovered that type 2 columns failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for type 2 columns: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt snapshot strategies, instrument type 2 columns with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for type 2 columns: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for type 2 columns belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt snapshot strategies: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in type 2 columns
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for type 2 columns, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Storage planning

Archive old snapshot partitions; monitor table growth month over month.

A production team running dbt snapshot strategies discovered that storage planning failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for storage planning: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt snapshot strategies, instrument storage planning with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for storage planning: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for storage planning belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt snapshot strategies: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in storage planning
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for storage planning, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Downstream contracts

Consumers filter dbt_valid_to is null for current state unless temporal join explicit.

A production team running dbt snapshot strategies discovered that downstream contracts failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for downstream contracts: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt snapshot strategies, instrument downstream contracts with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for downstream contracts: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for downstream contracts belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt snapshot strategies: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in downstream
contracts configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for downstream contracts, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Hard refresh

Full snapshot rebuild after strategy mistakes—plan downstream temporal impact before running.

A production team running dbt snapshot strategies discovered that hard refresh failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for hard refresh: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt snapshot strategies, instrument hard refresh with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for hard refresh: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for hard refresh belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt snapshot strategies: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in hard refresh
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for hard refresh, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

Prefer timestamp strategy when `updated_at` is trustworthy; audit sources for hard deletes before choosing check. Downstream must filter `dbt_valid_to is null` for current-state queries unless doing temporal joins explicitly.
