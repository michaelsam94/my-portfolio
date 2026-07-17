---
title: "GitOps Drift Detection and Self-Heal"
slug: "devops-gitops-drift-detection"
description: "Configure self-heal, diff alerts, and ignore differences for secrets."
datePublished: "2026-05-21"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "GitOps"
  - "SRE"
keywords: "GitOps drift, self-heal"
faq:
  - q: "Self-heal tradeoff?"
    a: "Self-heal reverts intentional break-glass kubectl patches during incidents—use sync windows or disable with ticket."
  - q: "Diff alerts?"
    a: "Notify on OutOfSync beyond threshold—do not rely on manual argocd app diff during incidents."
  - q: "Ignore differences?"
    a: "Ignore Deployment replica counts for HPA-managed apps; do not ignore Secret data hashes blindly."
  - q: "Drift metrics?"
    a: "Track manual sync frequency—high rate indicates Git not source of truth culturally."
---
On-call kubectl patched Deployment during incident; self-heal reverted fix mid-outage until sync window disabled with ticket annotation.

## Self-heal tradeoffs

Self-heal enforces Git; break-glass needs sync disable or ignore difference with expiry.

Production teams running gitops drift detection learned that self-heal tradeoffs regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for self-heal tradeoffs: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument self-heal tradeoffs with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for self-heal tradeoffs: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for self-heal tradeoffs belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in self-heal tradeoffs configs.

Capacity note: estimate peak concurrency for self-heal tradeoffs, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for gitops drift detection: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for self-heal tradeoffs: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Diff alerts

OutOfSync duration alert—not only manual argocd app diff during firefighting.

Production teams running gitops drift detection learned that diff alerts regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for diff alerts: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument diff alerts with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for diff alerts: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for diff alerts belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in diff alerts configs.

Capacity note: estimate peak concurrency for diff alerts, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for gitops drift detection: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for diff alerts: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Ignore rules

Ignore replica count for HPA-managed Deployments; never ignore Secret wholesale.

Production teams running gitops drift detection learned that ignore rules regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ignore rules: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ignore rules with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ignore rules: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ignore rules belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ignore rules configs.

Capacity note: estimate peak concurrency for ignore rules, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for gitops drift detection: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ignore rules: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Drift metrics

Manual sync rate and override count—cultural Git drift indicator.

Production teams running gitops drift detection learned that drift metrics regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for drift metrics: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument drift metrics with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for drift metrics: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for drift metrics belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in drift metrics configs.

Capacity note: estimate peak concurrency for drift metrics, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for gitops drift detection: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for drift metrics: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Audit

Record who disabled self-heal and when—forty-eight hour retrospective required.

Production teams running gitops drift detection learned that audit regressions appear when traffic
mix shifts—uniform staging QPS missed Black Friday combinations until load replay used production
timestamps.

Runbook for audit: confirm blast radius, identify last config change, execute single-step rollback,
capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument audit with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for audit: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for audit belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in audit configs.

Capacity note: estimate peak concurrency for audit, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for gitops drift detection: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for audit: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

```yaml
syncPolicy:
  automated:
    selfHeal: true
  syncOptions:
    - RespectIgnoreDifferences=true
```
Ignore `/spec/replicas` for HPA-managed Deployments only—document each ignore rule owner.
