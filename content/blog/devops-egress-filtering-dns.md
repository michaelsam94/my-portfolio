---
title: "Egress Filtering and DNS Logging for Compliance"
slug: "devops-egress-filtering-dns"
description: "Filter egress with firewall rules and log DNS for exfil detection."
datePublished: "2026-10-14"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Networking"
  - "Security"
keywords: "egress filtering DNS"
faq:
  - q: "Allowlist vs log-only egress?"
    a: "Log-only fails compliance; regulated workloads need default-deny with alert on deny for exfil detection."
  - q: "Why log DNS for security?"
    a: "Query logs reveal C2 domains before TCP connects—correlate with proxy deny events."
  - q: "How roll out default-deny egress?"
    a: "Monitor mode inventory first, then tighten allowlists with documented break-glass domain tickets."
  - q: "What about hostNetwork exceptions?"
    a: "Document every hostNetwork workload bypassing NetworkPolicy—review quarterly for necessity."
---
Nightly DNS queries to suspicious TLDs had no egress or DNS log correlation for security investigation.

## Default deny tiers

Production strict allowlist; staging monitor-mode with anomaly detection before tighten.

A production team running egress filtering dns discovered that default deny tiers failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for default deny tiers: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For egress filtering dns, instrument default deny tiers with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for default deny tiers: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for default deny tiers belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress filtering dns: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in default deny tiers configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for default deny tiers, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## DNS logging

CoreDNS or NodeLocal forward to SIEM with retention meeting PCI ninety-day evidence.

A production team running egress filtering dns discovered that dns logging failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for dns logging: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress filtering dns, instrument dns logging with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for dns logging: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for dns logging belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for egress filtering dns: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in dns logging configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for dns logging, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## SOAR response

High-entropy domain scores ticket automatically—auto-block only after false-positive baseline.

A production team running egress filtering dns discovered that soar response failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for soar response: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress filtering dns, instrument soar response with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for soar response: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for soar response belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for egress filtering dns: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in soar response configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for soar response, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## hostNetwork audit

Quarterly review of workloads bypassing NetworkPolicy egress controls.

A production team running egress filtering dns discovered that hostnetwork audit failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for hostnetwork audit: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress filtering dns, instrument hostnetwork audit with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for hostnetwork audit: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for hostnetwork audit belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress filtering dns: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in hostnetwork audit configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for hostnetwork audit, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Developer unblock

Domain allowlist ticket workflow with SLA for legitimate SaaS dependencies.

A production team running egress filtering dns discovered that developer unblock failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for developer unblock: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For egress filtering dns, instrument developer unblock with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for developer unblock: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for developer unblock belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for egress filtering dns: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in developer unblock configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for developer unblock, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

Default-deny egress with DNS query logging to SIEM reveals C2 lookups before TCP connects. Start monitor-mode allowlist inventory, then tighten tiers—PCI assessors want deny evidence, not log-only aspiration.
