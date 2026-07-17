---
title: "dbt Exposures and Downstream Lineage"
slug: "devops-dbt-exposures-lineage"
description: "Document dashboards and apps as dbt exposures for impact analysis."
datePublished: "2026-09-12"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "dbt"
  - "Platform"
keywords: "dbt exposures, lineage, impact analysis, BI dependencies"
faq:
  - q: "What is a dbt exposure?"
    a: "YAML documenting a downstream dashboard or application that depends on dbt models—for impact analysis in CI and docs."
  - q: "Why do stale exposures hurt?"
    a: "Schema changes merge without knowing a BI tile still references a dropped column exposure would have flagged."
  - q: "How enforce exposures in CI?"
    a: "Fail PRs that drop columns referenced by exposures; require exposure updates in the same PR as dashboard migrations."
  - q: "How do exposures relate to the catalog?"
    a: "dbt exposures version with models in git; export to DataHub or similar for enterprise search and ownership."
---
Merged column drop broke a Looker tile—exposure YAML still listed the old field after dashboard migration.

## Exposure definitions

Type dashboard or application, depends_on refs, owner, url—reviewed in git with model changes.

A production team running dbt exposures lineage discovered that exposure definitions failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for exposure definitions: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt exposures lineage, instrument exposure definitions with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for exposure definitions: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for exposure definitions belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt exposures lineage: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in exposure definitions
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for exposure definitions, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## CI impact analysis

Fail PRs dropping columns referenced by exposures; require exposure updates with BI migrations same release.

A production team running dbt exposures lineage discovered that ci impact analysis failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for ci impact analysis: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt exposures lineage, instrument ci impact analysis with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for ci impact analysis: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for ci impact analysis belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt exposures lineage: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in ci impact analysis configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for ci impact analysis, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Catalog integration

Export exposures to DataHub for search; stale owner fields block merge via lint rules.

A production team running dbt exposures lineage discovered that catalog integration failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for catalog integration: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt exposures lineage, instrument catalog integration with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for catalog integration: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for catalog integration belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt exposures lineage: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in catalog integration
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for catalog integration, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Lineage completeness

Native BI lineage plus git-versioned exposures—PR review catches what UI-only docs miss.

A production team running dbt exposures lineage discovered that lineage completeness failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for lineage completeness: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt exposures lineage, instrument lineage completeness with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for lineage completeness: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for lineage completeness belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt exposures lineage: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in lineage completeness
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for lineage completeness, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Deprecation workflow

Dual-write columns one sprint when needed; exposure records downstream sunset dates.

A production team running dbt exposures lineage discovered that deprecation workflow failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for deprecation workflow: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt exposures lineage, instrument deprecation workflow with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for deprecation workflow: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for deprecation workflow belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt exposures lineage: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in deprecation workflow
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for deprecation workflow, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

```yaml
exposures:
  - name: executive_revenue_dashboard
    type: dashboard
    owner: {name: finance-analytics}
    depends_on: [ref('fct_revenue')]
    url: https://looker.example.com/dashboards/42
```

CI fails PRs dropping columns referenced by exposures. Dashboard migration PRs must update exposures in the same release—stale YAML is how Looker tiles break silently after merged schema changes.
