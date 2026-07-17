---
title: "eBPF Observability with Cilium Hubble"
slug: "devops-ebpf-observability-cilium"
description: "Use Hubble for L3/L7 flow visibility and policy verification."
datePublished: "2026-06-14"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Security"
keywords: "Cilium Hubble, eBPF"
faq:
  - q: "How is Hubble different from tcpdump?"
    a: "Hubble aggregates L3/L7 flows with policy verdict labels cluster-wide—not one interface at a time."
  - q: "How verify NetworkPolicy with Hubble?"
    a: "Compare flows marked forwarded vs dropped against intended selectors—hostNetwork pods may bypass expected policy."
  - q: "What is a Hubble metrics retention mistake?"
    a: "Short debug retention without Prometheus export—incidents need trend context beyond minutes."
  - q: "Does eBPF observability add overhead?"
    a: "Usually low, but monitor drop counters on high packets-per-second nodes during rollout."
---
NetworkPolicy YAML looked correct—Hubble showed DNS traffic bypass via a hostNetwork pod.

## Hubble relay

Aggregate flows cluster-wide; search by pod labels during policy incidents.

A production team running ebpf observability cilium discovered that hubble relay failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for hubble relay: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ebpf observability cilium, instrument hubble relay with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for hubble relay: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for hubble relay belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ebpf observability cilium: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in hubble relay
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for hubble relay, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Verdict analysis

Compare FORWARDED vs DROPPED against intended selectors—hostNetwork exceptions documented.

A production team running ebpf observability cilium discovered that verdict analysis failures show
up only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for verdict analysis: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ebpf observability cilium, instrument verdict analysis with low-cardinality metrics tied to
user-visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid
paging on vanity gauges that never correlated with past incidents.

Game day scenario for verdict analysis: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for verdict analysis belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for ebpf observability cilium: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in verdict analysis
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for verdict analysis, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## L7 visibility

HTTP visibility requires pod annotations—balance cardinality against debug value.

A production team running ebpf observability cilium discovered that l7 visibility failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for l7 visibility: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ebpf observability cilium, instrument l7 visibility with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for l7 visibility: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for l7 visibility belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ebpf observability cilium: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in l7 visibility
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for l7 visibility, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Alerting

Unexpected egress to non-allowlisted CIDR from tier-one namespaces.

A production team running ebpf observability cilium discovered that alerting failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for alerting: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ebpf observability cilium, instrument alerting with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for alerting: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for alerting belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ebpf observability cilium: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in alerting configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for alerting, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Retention

Export Hubble metrics to Prometheus with retention matching post-incident review—not minutes only.

A production team running ebpf observability cilium discovered that retention failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for retention: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For ebpf observability cilium, instrument retention with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for retention: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for retention belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for ebpf observability cilium: require peer review from someone outside the
authoring team before production promotion—fresh eyes catch assumptions embedded in retention
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for retention, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

Use Hubble to compare NetworkPolicy verdicts against intended selectors—hostNetwork pods may bypass policies that YAML suggests block traffic. Export Hubble metrics to Prometheus with retention matching incident review needs, not minutes-long UI defaults only.
