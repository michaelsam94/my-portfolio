---
title: "Network Policy Audit and Compliance Reporting"
slug: "devops-network-policy-audit"
description: "Continuously audit NetworkPolicy coverage and generate compliance reports."
datePublished: "2026-10-19"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Security"
  - "Kubernetes"
keywords: "network policy audit"
faq:
  - q: "Default deny baseline?"
    a: "Audit starts from deny-all namespace policy—document each allow rule owner and expiry."
  - q: "Policy simulator?"
    a: "kubectl npol test or Cilium policy audit against sample pod labels before apply."
  - q: "Shadow mode?"
    a: "Cilium audit mode logs would-be denies before enforcement—inventory dependencies."
  - q: "Quarterly review?"
    a: "Remove allows for decommissioned SaaS endpoints—stale DNS allows hide exfil paths."
---
Compliance scan found forty-seven egress allows to decommissioned SaaS domains; quarterly NP audit plus Cilium audit mode reduced stale allows.

## Default deny baseline

Namespace deny-all ingress and egress; each allow documents owner and review date.

Production teams running network policy audit learned that default deny baseline regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for default deny baseline: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument default deny baseline with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for default deny baseline: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for default deny baseline belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in default deny baseline configs.

Capacity note: estimate peak concurrency for default deny baseline, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for network policy audit: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for default deny baseline: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Audit mode

Cilium policy audit logs would-be drops before enforcement—dependency inventory.

Production teams running network policy audit learned that audit mode regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for audit mode: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument audit mode with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for audit mode: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for audit mode belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in audit mode configs.

Capacity note: estimate peak concurrency for audit mode, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for network policy audit: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for audit mode: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Simulator

Test pod labels against policy before merge—kubectl npol or cilium policy verify.

Production teams running network policy audit learned that simulator regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for simulator: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument simulator with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for simulator: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for simulator belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in simulator configs.

Capacity note: estimate peak concurrency for simulator, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for network policy audit: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for simulator: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## DNS allow

Explicit kube-dns and NodeLocal DNS IPs—deny-all breaks without.

Production teams running network policy audit learned that dns allow regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for dns allow: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument dns allow with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for dns allow: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for dns allow belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in dns allow configs.

Capacity note: estimate peak concurrency for dns allow, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for network policy audit: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for dns allow: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Review ritual

Quarterly remove expired allows; tie to CMDB decommission events.

Production teams running network policy audit learned that review ritual regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for review ritual: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument review ritual with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for review ritual: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for review ritual belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in review ritual configs.

Capacity note: estimate peak concurrency for review ritual, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for network policy audit: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for review ritual: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
