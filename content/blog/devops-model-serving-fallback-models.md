---
title: "Fallback Models When Primary Fails"
slug: "devops-model-serving-fallback-models"
description: "Route to smaller fallback model when primary times out or errors."
datePublished: "2026-08-22"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Model Serving"
  - "SRE"
keywords: "fallback models"
faq:
  - q: "When route to fallback?"
    a: "Primary timeout budget exhausted—try cheaper CPU model or rules engine before 503 to customer."
  - q: "Fallback capacity sizing?"
    a: "Size for 100% QPS when primary down—not shadow 5% traffic—game day proves redirect volume."
  - q: "Compliance logging?"
    a: "Log tier, model version, and reason header for audit replay—never silent downgrade without trace."
  - q: "Fallback quality floor?"
    a: "Define minimum acceptable accuracy; fallback worse than threshold returns degraded response with flag."
---
Primary LLM timeout returned 500; CPU distil fallback could answer in two hundred milliseconds but routing retried primary until client deadline.

## Tiered routing

Primary budget then fallback with X-Inference-Tier response header and metric labels.

Production teams running model serving fallback models learned that tiered routing regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for tiered routing: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument tiered routing with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for tiered routing: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for tiered routing belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in tiered routing configs.

Capacity note: estimate peak concurrency for tiered routing, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving fallback models: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for tiered routing: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Capacity for redirect

Fallback pool sized for 100% QPS when primary hard-down—game day quarterly.

Production teams running model serving fallback models learned that capacity for redirect
regressions appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations
until load replay used production timestamps.

Runbook for capacity for redirect: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument capacity for redirect with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for capacity for redirect: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for capacity for redirect belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in capacity for redirect configs.

Capacity note: estimate peak concurrency for capacity for redirect, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving fallback models: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for capacity for redirect: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Quality floor

Fallback worse than threshold returns explicit degraded JSON—not silent wrong answer.

Production teams running model serving fallback models learned that quality floor regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for quality floor: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument quality floor with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for quality floor: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for quality floor belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in quality floor configs.

Capacity note: estimate peak concurrency for quality floor, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving fallback models: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for quality floor: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Audit logging

Model version and tier per decision for compliance replay.

Production teams running model serving fallback models learned that audit logging regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for audit logging: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument audit logging with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for audit logging: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for audit logging belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in audit logging configs.

Capacity note: estimate peak concurrency for audit logging, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving fallback models: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for audit logging: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Circuit integration

Open breaker on primary triggers fallback path—not infinite primary retry.

Production teams running model serving fallback models learned that circuit integration regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for circuit integration: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument circuit integration with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for circuit integration: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for circuit integration belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in circuit integration configs.

Capacity note: estimate peak concurrency for circuit integration, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving fallback models: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for circuit integration: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.
