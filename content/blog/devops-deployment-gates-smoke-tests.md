---
title: "Deployment Gates and Post-Deploy Smoke Tests"
slug: "devops-deployment-gates-smoke-tests"
description: "Block promotion until smoke tests pass against canary or staging."
datePublished: "2026-05-10"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "CI/CD"
  - "SRE"
keywords: "deployment gates, smoke tests"
faq:
  - q: "What is a deployment gate vs CI test?"
    a: "A gate runs against the deployed artifact in a prod-like environment after build success, before promotion."
  - q: "What makes a smoke test useful?"
    a: "Fast critical-path requests against real read-only dependencies—not /health alone or mocks."
  - q: "How do canary promotion gates work?"
    a: "Automated comparison of error rate and latency canary vs baseline before increasing traffic weight."
  - q: "How handle flaky smoke tests?"
    a: "One retry with jitter; chronic flakes are Sev-2 debt—quarantine and fix, not ignored green builds."
---
Pipeline green; production returned 500 on orders API because smoke tested /health only.

## Smoke design

Three to five read-only API paths with synthetic tenant—represent revenue and auth flows.

A production team running deployment gates smoke tests discovered that smoke design failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for smoke design: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For deployment gates smoke tests, instrument smoke design with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for smoke design: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for smoke design belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for deployment gates smoke tests: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in smoke design
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for smoke design, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## CD gates

Block promotion until smoke passes on canary URL; automatic rollback on failure.

A production team running deployment gates smoke tests discovered that cd gates failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for cd gates: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For deployment gates smoke tests, instrument cd gates with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for cd gates: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for cd gates belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for deployment gates smoke tests: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in cd gates configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for cd gates, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Environment parity

Same secrets resolver and network path as production—not localhost mocks.

A production team running deployment gates smoke tests discovered that environment parity failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for environment parity: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For deployment gates smoke tests, instrument environment parity with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for environment parity: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for environment parity belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for deployment gates smoke tests: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in environment
parity configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for environment parity, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Flake policy

One retry with jitter; chronic flakes are Sev-2 debt tracked to resolution.

A production team running deployment gates smoke tests discovered that flake policy failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for flake policy: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For deployment gates smoke tests, instrument flake policy with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for flake policy: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for flake policy belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for deployment gates smoke tests: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in flake policy
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for flake policy, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Override auditing

Manual gate skips require ticket ID in deploy metadata and alert to platform.

A production team running deployment gates smoke tests discovered that override auditing failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for override auditing: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For deployment gates smoke tests, instrument override auditing with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for override auditing: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for override auditing belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for deployment gates smoke tests: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in override
auditing configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for override auditing, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

Smoke three to five read-only API paths with synthetic tenant context after deploy—`/health` alone misses misconfigured database URLs. Block promotion on canary smoke failure with automatic rollback; manual gate overrides require ticket ID in deploy annotation.
