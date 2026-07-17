---
title: "GPU Scheduling for ML Training and Inference"
slug: "devops-gpu-scheduling-ml-workloads"
description: "Schedule GPU jobs with quotas, fractions, and priority for training vs inference."
datePublished: "2026-07-18"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "MLOps"
  - "Kubernetes"
keywords: "GPU scheduling ML"
faq:
  - q: "GPU sharing strategies?"
    a: "Time-slicing, MPS, MIG, or exclusive node pool—match isolation need to technique."
  - q: "Fractional GPU?"
    a: "Device plugin exposing gpu fractions needs memory limit enforcement or OOM affects neighbors."
  - q: "Queueing vs overprovision?"
    a: "Kueue or batch scheduler queues training jobs; inference gets dedicated pool."
  - q: "Node selectors?"
    a: "gpu-type labels for A100 vs L4—scheduler plugin or node affinity prevents wrong silicon."
---
Training jobs starved inference because both shared default GPU pool; Kueue queue plus dedicated inference NodePool fixed SLO and utilization.

## Pool separation

Inference realtime pool versus batch training pool—different instance types and quotas.

Production teams running gpu scheduling ml workloads learned that pool separation regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for pool separation: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument pool separation with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for pool separation: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for pool separation belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in pool separation configs.

Capacity note: estimate peak concurrency for pool separation, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for gpu scheduling ml workloads: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for pool separation: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Sharing techniques

MPS, time-slicing, MIG, exclusive—match isolation to compliance and noisy neighbor risk.

Production teams running gpu scheduling ml workloads learned that sharing techniques regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for sharing techniques: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument sharing techniques with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for sharing techniques: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for sharing techniques belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in sharing techniques configs.

Capacity note: estimate peak concurrency for sharing techniques, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for gpu scheduling ml workloads: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for sharing techniques: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Fractional GPUs

Device plugin fractions need memory enforcement or OOM affects co-tenants.

Production teams running gpu scheduling ml workloads learned that fractional gpus regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for fractional gpus: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument fractional gpus with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for fractional gpus: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for fractional gpus belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in fractional gpus configs.

Capacity note: estimate peak concurrency for fractional gpus, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for gpu scheduling ml workloads: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for fractional gpus: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Queueing

Kueue or Volcano for batch; priority classes prevent training preempting inference.

Production teams running gpu scheduling ml workloads learned that queueing regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for queueing: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument queueing with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for queueing: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for queueing belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in queueing configs.

Capacity note: estimate peak concurrency for queueing, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for gpu scheduling ml workloads: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for queueing: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.

## Labels

gpu-type and workload-class node labels—scheduling gates reject wrong silicon.

Production teams running gpu scheduling ml workloads learned that labels regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for labels: confirm blast radius, identify last config change, execute single-step rollback,
capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument labels with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for labels: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for labels belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in labels configs.

Capacity note: estimate peak concurrency for labels, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for gpu scheduling ml workloads: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for labels: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.
