---
title: "Kubernetes Network Policies: Default Deny Baseline"
slug: "devops-network-policies-default-deny"
description: "Implement default-deny network policies with explicit egress and ingress allowlists."
datePublished: "2026-03-04"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Security"
keywords: "network policy, default deny"
faq:
  - q: "Where start?"
    a: "One namespace pilot with deny-all ingress and egress, then add allows from inventory."
  - q: "DNS egress allow?"
    a: "kube-system DNS and NodeLocal DNS IP explicit—deny-all breaks without DNS allow."
  - q: "CNI support?"
    a: "Verify CNI enforces NetworkPolicy—some overlay modes need CiliumNetworkPolicy instead."
  - q: "Break-glass?"
    a: "Document emergency namespace label bypass with audit alert—never permanent unlabeled production."
---
Default allow namespace let compromised pod exfiltrate; pilot deny-all plus explicit allows cut lateral movement in red team exercise.

## Pilot rollout

One namespace deny ingress and egress; inventory allows from Hubble or flow logs.

Production teams running network policies default deny learned that pilot rollout regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for pilot rollout: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument pilot rollout with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for pilot rollout: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for pilot rollout belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in pilot rollout configs.

Capacity note: estimate peak concurrency for pilot rollout, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for network policies default deny: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for pilot rollout: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## DNS egress

Allow UDP/TCP 53 to cluster DNS and NodeLocal—most common break on deny-all.

Production teams running network policies default deny learned that dns egress regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for dns egress: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument dns egress with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for dns egress: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for dns egress belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in dns egress configs.

Capacity note: estimate peak concurrency for dns egress, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for network policies default deny: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for dns egress: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## CNI verification

Confirm CNI enforces NetworkPolicy—some overlays need CiliumNetworkPolicy.

Production teams running network policies default deny learned that cni verification regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for cni verification: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument cni verification with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for cni verification: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for cni verification belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in cni verification configs.

Capacity note: estimate peak concurrency for cni verification, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for network policies default deny: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for cni verification: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Break-glass

Emergency label bypass with audit alert and forty-eight hour retrospective.

Production teams running network policies default deny learned that break-glass regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for break-glass: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument break-glass with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for break-glass: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for break-glass belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in break-glass configs.

Capacity note: estimate peak concurrency for break-glass, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for network policies default deny: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for break-glass: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Expand waves

Tier-2 namespaces after pilot metrics on ticket volume and false denies.

Production teams running network policies default deny learned that expand waves regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for expand waves: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument expand waves with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for expand waves: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for expand waves belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in expand waves configs.

Capacity note: estimate peak concurrency for expand waves, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for network policies default deny: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for expand waves: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
