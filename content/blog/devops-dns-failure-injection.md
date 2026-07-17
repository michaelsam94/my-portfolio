---
title: "DNS Failure Injection and Resolver Fallback"
slug: "devops-dns-failure-injection"
description: "Test behavior when CoreDNS or external DNS fails mid-request."
datePublished: "2026-06-25"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Chaos Engineering"
  - "Networking"
keywords: "DNS failure injection"
faq:
  - q: "Why inject DNS failures in chaos testing?"
    a: "CoreDNS or upstream resolver outages cascade to every hostname-based dependency simultaneously."
  - q: "CoreDNS vs external DNS failures?"
    a: "Test both; applications caching DNS behave differently when TTL expires mid-outage."
  - q: "When run DNS chaos in production?"
    a: "Only with strict blast radius and error-budget stop—continuous staging injection preferred."
  - q: "What application pattern survives DNS blips?"
    a: "Retry with jitter on transient DNS errors—not tight loops that amplify CoreDNS load."
---
CoreDNS CPU spiked during a control plane rollout—cascading timeouts until customers reported errors.

## Failure modes

SERVFAIL, slow responses, NXDOMAIN storms, poisoned caches, negative TTL amplification.

A production team running dns failure injection discovered that failure modes failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for failure modes: confirm blast radius (single namespace vs fleet-wide), identify
last config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dns failure injection, instrument failure modes with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for failure modes: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for failure modes belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dns failure injection: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in failure modes configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for failure modes, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Chaos scope

Litmus or Chaos Mesh DNSChaos limited by namespace labels—not cluster-wide without comms.

A production team running dns failure injection discovered that chaos scope failures show up only
when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for chaos scope: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dns failure injection, instrument chaos scope with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for chaos scope: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for chaos scope belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dns failure injection: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in chaos scope configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for chaos scope, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

## Application retries

Jittered backoff on DNS errors; avoid tight loops that amplify CoreDNS QPS.

A production team running dns failure injection discovered that application retries failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for application retries: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dns failure injection, instrument application retries with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for application retries: inject partial outage in staging quarterly, verify on-
call can execute rollback in under fifteen minutes using only the linked runbook, update runbook
with what actually broke.

Ownership for application retries belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dns failure injection: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in application retries
configs that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for application retries, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## NodeLocal DNSCache

Test chaos with production-like cache enabled—reduces but does not eliminate CoreDNS load.

A production team running dns failure injection discovered that nodelocal dnscache failures show up
only when upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the
regression until Black Friday.

Runbook entry for nodelocal dnscache: confirm blast radius (single namespace vs fleet-wide),
identify last config change, roll back via documented single step, then capture metrics screenshots
for postmortem—not ad-hoc dashboard hunting.

For dns failure injection, instrument nodelocal dnscache with low-cardinality metrics tied to user-
visible outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging
on vanity gauges that never correlated with past incidents.

Game day scenario for nodelocal dnscache: inject partial outage in staging quarterly, verify on-call
can execute rollback in under fifteen minutes using only the linked runbook, update runbook with
what actually broke.

Ownership for nodelocal dnscache belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers should deploy a safe canary within one week using that doc
alone.

Change management for dns failure injection: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in nodelocal dnscache configs
that authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for nodelocal dnscache, multiply by
headroom factor one-point-five to two, compare against cloud quotas and license limits before launch
week—not during the first outage.

## Runbook

Scale CoreDNS; verify upstream forwarder health; correlate with deploying control plane version.

A production team running dns failure injection discovered that runbook failures show up only when
upstream dependencies shift traffic mix—staging load tests with uniform QPS missed the regression
until Black Friday.

Runbook entry for runbook: confirm blast radius (single namespace vs fleet-wide), identify last
config change, roll back via documented single step, then capture metrics screenshots for
postmortem—not ad-hoc dashboard hunting.

For dns failure injection, instrument runbook with low-cardinality metrics tied to user-visible
outcomes: error rate, tail latency, freshness, or cost per successful operation—avoid paging on
vanity gauges that never correlated with past incidents.

Game day scenario for runbook: inject partial outage in staging quarterly, verify on-call can
execute rollback in under fifteen minutes using only the linked runbook, update runbook with what
actually broke.

Ownership for runbook belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers should deploy a safe canary within one week using that doc alone.

Change management for dns failure injection: require peer review from someone outside the authoring
team before production promotion—fresh eyes catch assumptions embedded in runbook configs that
authors no longer notice.

Capacity planning note: estimate peak QPS or job concurrency for runbook, multiply by headroom
factor one-point-five to two, compare against cloud quotas and license limits before launch week—not
during the first outage.

Run DNSChaos scoped to staging namespaces mirroring NodeLocal DNSCache production config. Applications must retry DNS failures with jitter—tight retry loops amplify CoreDNS outages into cluster-wide incidents.
