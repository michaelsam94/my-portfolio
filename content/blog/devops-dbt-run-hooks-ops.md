---
title: "dbt Run Hooks and On-Run-End Operations"
slug: "devops-dbt-run-hooks-ops"
description: "Use run hooks for grants, notifications, and post-run validation safely."
datePublished: "2026-09-16"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "dbt"
  - "Data Engineering"
keywords: "dbt run hooks, on-run-end, on-run-start, grants, post-hooks"
faq:
  - q: "When use on-run-end vs on-run-start hooks?"
    a: "on-run-start for session setup; on-run-end for grants, notifications, and validation after models exist."
  - q: "Why must dbt hooks be idempotent?"
    a: "Failed runs retry; non-idempotent grants or inserts double-apply without IF NOT EXISTS guards."
  - q: "Should a failed grant hook fail the whole dbt run?"
    a: "Yes for security grants; optional for notifications—document hard vs soft hooks explicitly."
  - q: "What belongs in hooks vs macros?"
    a: "Hooks run every invocation—keep them minimal; macros are called explicitly from models."
---
on-run-end GRANT failed silently in logs—BI could not query new models until manual DBA fix Monday.

## Grant automation

Generate GRANT SELECT from meta roles via adapter macros—security hooks must fail the run.

A production team running dbt run hooks ops discovered that grant automation failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for grant automation: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt run hooks ops, instrument grant automation with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for grant automation: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for grant automation belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt run hooks ops: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in grant automation configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for grant automation, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Idempotency

IF NOT EXISTS patterns; retries must not double-apply privileges or duplicate Slack posts.

A production team running dbt run hooks ops discovered that idempotency failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for idempotency: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt run hooks ops, instrument idempotency with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for idempotency: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for idempotency belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt run hooks ops: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in idempotency configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for idempotency, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Validation hooks

Assert row counts on critical marts before consumers schedule queries against empty tables.

A production team running dbt run hooks ops discovered that validation hooks failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for validation hooks: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt run hooks ops, instrument validation hooks with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for validation hooks: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for validation hooks belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt run hooks ops: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in validation hooks configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for validation hooks, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Performance

Log hook duration; slow hooks block job SLAs while models appear healthy.

A production team running dbt run hooks ops discovered that performance failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for performance: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt run hooks ops, instrument performance with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for performance: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for performance belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt run hooks ops: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in performance configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for performance, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Hard vs soft hooks

Document which hooks are allowed to warn-only versus fail-closed for compliance.

A production team running dbt run hooks ops discovered that hard vs soft hooks failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for hard vs soft hooks: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt run hooks ops, instrument hard vs soft hooks with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for hard vs soft hooks: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for hard vs soft hooks belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt run hooks ops: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in hard vs soft hooks configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for hard vs soft hooks, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

```sql
-- on-run-end (idempotent)
grant select on all tables in schema {{ target.schema }} to role bi_readonly;
```

Grant failures must fail the run for security hooks; Slack notifications can be soft-fail with logged warnings. Log hook duration—slow hooks block job SLAs silently.
