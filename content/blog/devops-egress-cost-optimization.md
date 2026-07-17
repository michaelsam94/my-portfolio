---
title: "Cloud Egress Cost Optimization"
slug: "devops-egress-cost-optimization"
description: "Reduce cross-AZ, cross-region, and internet egress with topology and CDN."
datePublished: "2026-10-04"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Cost Optimization"
  - "Networking"
keywords: "egress cost optimization"
faq:
  - q: "Why is cross-AZ traffic expensive?"
    a: "Cloud providers charge per GB between availability zones—chatty microservices multiply cost silently."
  - q: "How reduce cross-AZ without losing HA?"
    a: "Locality-aware clients prefer same-AZ endpoints when healthy; fall back cross-AZ on failure only."
  - q: "When is CDN wrong for cost savings?"
    a: "Dynamic APIs with low cache hit rate still pay egress—CDN primarily helps static assets."
  - q: "How measure egress drivers?"
    a: "VPC flow logs, service mesh telemetry bytes by destination AZ, and FinOps chargeback dashboards."
---
Cross-AZ traffic was thirty percent of the cloud bill—microservices chatted across zones by default.

## Locality routing

Prefer same-AZ endpoints when healthy; cross-AZ fallback only on failure.

A production team running egress cost optimization discovered that locality routing failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for locality routing: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress cost optimization, instrument locality routing with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for locality routing: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for locality routing belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress cost optimization: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in locality routing
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for locality routing, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Data placement

Colocate compute with primary datastore AZ for high-chatter services.

A production team running egress cost optimization discovered that data placement failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for data placement: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress cost optimization, instrument data placement with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for data placement: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for data placement belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress cost optimization: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in data placement
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for data placement, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Payload efficiency

Protobuf or compressed JSON on internal APIs; audit verbose logging streams crossing zones.

A production team running egress cost optimization discovered that payload efficiency failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for payload efficiency: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For egress cost optimization, instrument payload efficiency with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for payload efficiency: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for payload efficiency belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress cost optimization: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in payload
efficiency configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for payload efficiency, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## NAT topology

Per-AZ NAT or VPC endpoints reduce hairpin cross-AZ charges through centralized NAT.

A production team running egress cost optimization discovered that nat topology failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for nat topology: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress cost optimization, instrument nat topology with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for nat topology: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for nat topology belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for egress cost optimization: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in nat topology
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for nat topology, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## FinOps cadence

Monthly top talkers dashboard with service owner chargeback and remediation tickets.

A production team running egress cost optimization discovered that finops cadence failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for finops cadence: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress cost optimization, instrument finops cadence with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for finops cadence: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for finops cadence belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress cost optimization: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in finops cadence
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for finops cadence, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

Enable mesh locality-aware routing to prefer same-AZ backends when healthy. Audit internal JSON APIs for verbose payloads; colocate compute with data stores per AZ for high-chatter services before paying cross-AZ gigabyte charges monthly.
