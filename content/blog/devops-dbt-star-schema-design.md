---
title: "Star Schema Design for Analytics Warehouses"
slug: "devops-dbt-star-schema-design"
description: "Design fact and dimension tables with conformed dimensions and grain discipline."
datePublished: "2026-09-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Warehouse"
  - "Data Engineering"
keywords: "star schema design, fact grain, conformed dimensions, dbt marts"
faq:
  - q: "What is fact table grain?"
    a: "One row represents exactly one business event at a declared granularity—ambiguous grain double-counts measures."
  - q: "What are conformed dimensions?"
    a: "Shared dimensions like dim_date and dim_customer reused across marts for consistent joins."
  - q: "When are factless fact tables appropriate?"
    a: "Event tracking without measures—misuse causes join explosions in BI tools."
  - q: "Surrogate vs natural keys in dimensions?"
    a: "Surrogate warehouse keys isolate analytics from source id churn; document natural keys in metadata."
---
Revenue double-counted because fact grain included partial shipment lines twice per order.

## Grain discipline

Declare grain in model meta; test uniqueness on grain columns in CI.

A production team running dbt star schema design discovered that grain discipline failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for grain discipline: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt star schema design, instrument grain discipline with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for grain discipline: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for grain discipline belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt star schema design: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in grain discipline configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for grain discipline, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Conformed dimensions

Shared dim_date and dim_customer across marts—mesh spine not per-team reinvention.

A production team running dbt star schema design discovered that conformed dimensions failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for conformed dimensions: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt star schema design, instrument conformed dimensions with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for conformed dimensions: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for conformed dimensions belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt star schema design: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in conformed dimensions
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for conformed dimensions, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Additivity

Store components for ratios; revenue additive; conversion rate computed not stored pre-averaged.

A production team running dbt star schema design discovered that additivity failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for additivity: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt star schema design, instrument additivity with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for additivity: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for additivity belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt star schema design: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in additivity configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for additivity, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Slowly changing attributes

Explicit Type 1 vs Type 2 choices per attribute—document in model descriptions.

A production team running dbt star schema design discovered that slowly changing attributes failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for slowly changing attributes: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt star schema design, instrument slowly changing attributes with low-cardinality metrics tied
to user-visible outcomes: error rate, tail latency, freshness, or cost per successful
operation—avoid paging on vanity gauges that never correlated with past incidents.

Game day scenario for slowly changing attributes: inject partial outage in staging quarterly, verify
on-call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for slowly changing attributes belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers should deploy a safe canary within one week using
that doc alone.

Change management for dbt star schema design: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in slowly changing attributes
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for slowly changing attributes,
multiply by headroom factor one-point-five to two, compare against cloud quotas and license limits
before launch week—not during the first outage.

## Physical design

Cluster facts on date and high-filter columns matching BI query patterns.

A production team running dbt star schema design discovered that physical design failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for physical design: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt star schema design, instrument physical design with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for physical design: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for physical design belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt star schema design: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in physical design configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for physical design, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

Declare grain in model `meta` and test uniqueness on grain columns in CI. Revenue is additive; conversion rate is not—store numerators and denominators, not pre-averaged ratios in facts.
