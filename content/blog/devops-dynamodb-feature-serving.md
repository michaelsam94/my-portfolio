---
title: "DynamoDB for Low-Latency Feature Serving"
slug: "devops-dynamodb-feature-serving"
description: "Design DynamoDB tables for feature serving with GSIs and on-demand capacity."
datePublished: "2026-08-02"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Feature Stores"
  - "Platform"
keywords: "DynamoDB feature serving, online features, GSI hot partitions, on-demand capacity"
faq:
  - q: "Why DynamoDB for online feature serving?"
    a: "Single-digit millisecond reads at high QPS with on-demand scaling for launch spikes."
  - q: "What causes GSI hot partitions?"
    a: "Popular entity keys concentrating write/read traffic on one partition—mitigate with sharded suffixes."
  - q: "On-demand vs provisioned capacity?"
    a: "On-demand for unknown spikes; provisioned with auto scaling when traffic is predictable."
  - q: "How keep features fresh?"
    a: "Streams plus Lambda materialization, TTL attributes, and SLAs on staleness—not silent old vectors."
---
Launch day throttled reads on the feature table—provisioned capacity was not switched to on-demand before traffic.

## Key design

Composite pk/sk with sharded suffixes on hot entity keys—avoid monotonic partition concentration.

A production team running dynamodb feature serving discovered that key design failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for key design: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dynamodb feature serving, instrument key design with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for key design: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for key design belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dynamodb feature serving: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in key design
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for key design, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## GSI patterns

Secondary access paths with per-key ConsumedCapacity monitoring during load tests.

A production team running dynamodb feature serving discovered that gsi patterns failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for gsi patterns: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dynamodb feature serving, instrument gsi patterns with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for gsi patterns: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for gsi patterns belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dynamodb feature serving: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in gsi patterns
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for gsi patterns, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## BatchGet limits

Split batches respecting sixteen megabyte and one hundred item limits in inference pipelines.

A production team running dynamodb feature serving discovered that batchget limits failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for batchget limits: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dynamodb feature serving, instrument batchget limits with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for batchget limits: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for batchget limits belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dynamodb feature serving: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in batchget limits
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for batchget limits, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Stream materialization

Warehouse to Dynamo via stream processor with idempotent upsert and freshness SLA.

A production team running dynamodb feature serving discovered that stream materialization failures
show up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed
the regression until Black Friday.

Runbook entry for stream materialization: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dynamodb feature serving, instrument stream materialization with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for stream materialization: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for stream materialization belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dynamodb feature serving: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in stream
materialization configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for stream materialization, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Launch readiness

Switch on-demand before marketing events; stale features flagged explicitly beat silent old vectors.

A production team running dynamodb feature serving discovered that launch readiness failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for launch readiness: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dynamodb feature serving, instrument launch readiness with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for launch readiness: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for launch readiness belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dynamodb feature serving: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in launch readiness
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for launch readiness, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

Shard hot entity keys with suffix buckets in partition key design. Switch to on-demand capacity before marketing launches; throttled reads during spikes degrade models worse than serving slightly stale defaults with explicit staleness flags.
