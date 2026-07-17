---
title: "Anycast DNS Failover: Health Checks, TTL, and Split-Brain Avoidance"
slug: "rag-anycast-dns-failover"
description: "Running global DNS with anycast POPs — probe design, stale record risks, and coordinated failover with load balancers."
datePublished: "2025-05-29"
dateModified: "2026-07-17"
tags:
  - "Networking"
  - "DNS"
  - "Reliability"
keywords: "anycast, dns failover, health checks, global traffic management"
faq:
  - q: "How fast can anycast DNS failover propagate?"
    a: "Depends on TTL and resolver caching — often minutes even when origin is healthy; critical paths need low TTL plus active health withdrawal at edge, not DNS alone."
  - q: "What kills anycast failover drills?"
    a: "Monitoring probes that hit origin directly while customers use anycast edge — false confidence when only the anycast path failed."
  - q: "Should TTL be zero for production?"
    a: "No — TTL zero increases resolver load and latency; use 30–60s for failover-critical records with health-checked anycast withdrawal as primary mechanism."
---
Anycast DNS advertises the same IP from multiple POPs; routing pulls users to nearest healthy edge. Failover sounds automatic until stale caches, asymmetric probes, and split-brain between DNS and application load balancers cause traffic to black-hole. Architects need health check design that matches customer paths, TTL strategy, and runbooks for partial POP loss.

## Anycast versus geo-DNS routing

Anycast leverages BGP path selection; geo-DNS returns different answers by region. Anycast simplifies IP management but POP loss affects all resolvers still caching routes differently.

Document which monitoring probes use anycast IP versus direct origin — mismatch here causes false confidence during anycast routing incidents.

## Health check design

Probe from external synthetic monitors through anycast IP — not direct origin bypass. Match protocol and Host header customers use. Layer 7 checks catch TLS cert regressions L4 misses.

## TTL and cache poisoning resilience

Low TTL speeds failover at cost of QPS to authoritative servers. Combine with rapid route withdrawal at anycast edge when origin fails — DNS TTL then bounds stale tail, not whole outage duration.

## Coordinating with GSLB and origin pools

DNS failover to standby region useless if origin pool not pre-warmed. Automate database read replica promotion before DNS swing for stateful tiers.

## Split-brain during partial failures

Two POPs healthy, one sick — ensure BGP communities withdraw sick POP without flapping. Document manual override when automation disagrees with human incident assessment.

## Game day scenarios

Practice single POP loss, authoritative DNS provider outage, and stale resolver simulation. Measure time to restore SLO — target under business RTO.

## Resolver diversity in monitoring

Run synthetic checks from multiple resolver networks — public Google, Cloudflare, ISP resolvers — because failover timing differs by cache position. Customer impact reports should include resolver geography when DNS-related incidents strike regional ISPs hardest.

## Split horizon and internal versus external DNS

Internal resolvers may cache stale anycast routes after POP recovery — flush or lower internal TTL for critical records. Split DNS returning different answers internally causes debug confusion during incidents.

## DDoS and anycast absorption

Anycast spreads attack volume — still need origin protection when attack saturates POP uplink. Coordinate with provider scrubbing center activation thresholds in playbook.

Anycast DNS failover is BGP plus caching psychology, not magic. Probe what users probe, pair DNS with edge withdrawal, rehearse POP loss, and keep TTL honest about stale tail risk.

After failover drill, verify internal monitoring and customer-facing paths both recovered — asymmetric recovery causes split-brain customer impact reports.

Design review checklist item 1 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for anycast DNS failover: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in anycast DNS failover often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for anycast DNS failover should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for anycast DNS failover documents escalation when primary and secondary on-call roles are unreachable.

## Field checklist for anycast dns failover

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.
