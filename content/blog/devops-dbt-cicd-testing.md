---
title: "dbt CI/CD: Slim CI and State Comparison"
slug: "devops-dbt-cicd-testing"
description: "Run dbt slim CI with defer and state:modified+ on pull requests."
datePublished: "2026-09-09"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "dbt"
  - "CI/CD"
keywords: "dbt CI/CD, slim CI, state:modified, dbt defer, manifest.json"
faq:
  - q: "What is dbt slim CI?"
    a: "Running state:modified+ on pull requests to rebuild only changed models and downstream dependents, often with --defer to production relations."
  - q: "Why does slim CI fail with defer errors?"
    a: "Missing, stale, or dbt-version-mismatched production manifest.json used for state comparison."
  - q: "How should production manifests be published for CI?"
    a: "Upload target/manifest.json after every successful production dbt run to durable object storage as manifest-latest."
  - q: "What should slim CI still run besides selected models?"
    a: "dbt parse, SQL lint, and schema tests on affected nodes; nightly full runs catch drift PR slim CI misses."
---
A README typo triggered a two-hour full dbt run on four hundred models—zero SQL changed.

## state:modified+

Select changed models and downstream dependents vs prod manifest. Plus suffix is essential for column renames propagating.

A production team running dbt cicd testing discovered that state:modified+ failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for state:modified+: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt cicd testing, instrument state:modified+ with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for state:modified+: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for state:modified+ belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt cicd testing: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in state:modified+ configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for state:modified+, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## defer in CI

Unresolved refs bind to production relations for unchanged upstream; CI schema builds subgraph only.

A production team running dbt cicd testing discovered that defer in ci failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for defer in ci: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt cicd testing, instrument defer in ci with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for defer in ci: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for defer in ci belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt cicd testing: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in defer in ci configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for defer in ci, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Manifest publishing

Upload target/manifest.json after every prod run to manifest-latest; pin dbt version to producer.

A production team running dbt cicd testing discovered that manifest publishing failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for manifest publishing: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dbt cicd testing, instrument manifest publishing with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for manifest publishing: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for manifest publishing belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt cicd testing: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in manifest publishing configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for manifest publishing, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Merge queue

Refresh manifest from main after merge queue completes to avoid stale state comparisons on batched PRs.

A production team running dbt cicd testing discovered that merge queue failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for merge queue: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt cicd testing, instrument merge queue with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for merge queue: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for merge queue belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dbt cicd testing: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in merge queue configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for merge queue, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Slim CI metrics

Track PR duration, selected model count, defer failures—alert when selection hits root facts.

A production team running dbt cicd testing discovered that slim ci metrics failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for slim ci metrics: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dbt cicd testing, instrument slim ci metrics with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for slim ci metrics: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for slim ci metrics belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dbt cicd testing: require peer review from someone outside the authoring team
before production promotion—fresh eyes catch assumptions embedded in slim ci metrics configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for slim ci metrics, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Slim CI pipeline sketch

```bash
aws s3 cp s3://dbt-artifacts/prod/manifest-latest.json prod-state/manifest.json
dbt run --select state:modified+ --defer --state ./prod-state --target ci
dbt test --select state:modified+ --state ./prod-state
```

Pin dbt version to manifest producer. Refresh manifest-latest after each merge queue completion on main. Alert when slim selection count spikes—large refactors touching root models need human review.
