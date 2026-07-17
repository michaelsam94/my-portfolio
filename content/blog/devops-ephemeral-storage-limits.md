---
title: "Ephemeral Storage Limits and Eviction"
slug: "devops-ephemeral-storage-limits"
description: "Set ephemeral-storage requests/limits and monitor emptyDir pressure."
datePublished: "2026-03-22"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "SRE"
keywords: "ephemeral storage, eviction"
faq:
  - q: "Why set ephemeral-storage limits?"
    a: "Unbounded emptyDir or logs can fill node disk; kubelet evicts unrelated pods unpredictably."
  - q: "requests vs limits for ephemeral-storage?"
    a: "Both affect scheduling and eviction ordering—set both on log-heavy or download workloads."
  - q: "What metrics signal disk pressure?"
    a: "container_fs_usage_bytes from kubelet stats; alert before node-level eviction storms."
  - q: "Do sidecars share ephemeral quota?"
    a: "Yes—emptyDir shared between app and log shipper counts toward the same pod limit."
---
A log-heavy pod filled node disk—kubelet evicted unrelated production pods on the same node.

## Limit both request and limit

ephemeral-storage on emptyDir download and log workloads—scheduling and eviction both matter.

A production team running ephemeral storage limits discovered that limit both request and limit
failures show up only when upstream dependencies shift traffic mix—staging load tests with uniform
QPS missed the regression until Black Friday.

Runbook entry for limit both request and limit: confirm blast radius (single namespace vs fleet-
wide), identify last config change, roll back via documented single step, then capture metrics
screenshots for postmortem—not ad-hoc dashboard hunting.

For ephemeral storage limits, instrument limit both request and limit with low-cardinality metrics
tied to user-visible outcomes: error rate, tail latency, freshness, or cost per successful
operation—avoid paging on vanity gauges that never correlated with past incidents.

Game day scenario for limit both request and limit: inject partial outage in staging quarterly,
verify on-call can execute rollback in under fifteen minutes using only the linked runbook, update
runbook with what actually broke.

Ownership for limit both request and limit belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers should deploy a safe canary within one week using
that doc alone.

Change management for ephemeral storage limits: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in limit both
request and limit configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for limit both request and limit,
multiply by headroom factor one-point-five to two, compare against cloud quotas and license limits
before launch week—not during the first outage.

## Eviction ordering

Guaranteed QoS for tier-one pods; best-effort log scrapers evicted first under pressure.

A production team running ephemeral storage limits discovered that eviction ordering failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for eviction ordering: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ephemeral storage limits, instrument eviction ordering with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for eviction ordering: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for eviction ordering belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for ephemeral storage limits: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in eviction
ordering configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for eviction ordering, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Alternatives

Stdout logging or sized PVCs instead of unbounded emptyDir caches on shared nodes.

A production team running ephemeral storage limits discovered that alternatives failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for alternatives: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ephemeral storage limits, instrument alternatives with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for alternatives: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for alternatives belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ephemeral storage limits: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in alternatives
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for alternatives, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Monitoring

container_fs_usage_bytes alerts before node-level disk pressure evictions cascade.

A production team running ephemeral storage limits discovered that monitoring failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for monitoring: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ephemeral storage limits, instrument monitoring with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for monitoring: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for monitoring belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ephemeral storage limits: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in monitoring
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for monitoring, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Load testing

Fill emptyDir to limit in staging; document OOMKilled versus evicted behavior for on-call.

A production team running ephemeral storage limits discovered that load testing failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for load testing: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ephemeral storage limits, instrument load testing with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for load testing: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for load testing belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ephemeral storage limits: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in load testing
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for load testing, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

Set both requests and limits on `ephemeral-storage` for emptyDir log and download workloads. Prefer stdout logging or sized PVCs over unbounded emptyDir on shared nodes—kubelet evictions are nondeterministic for neighbors.
