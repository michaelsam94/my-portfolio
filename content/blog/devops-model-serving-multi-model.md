---
title: "Multi-Model Single GPU Multiplexing"
slug: "devops-model-serving-multi-model"
description: "Multiplex multiple small models on one GPU with memory profiling and MPS."
datePublished: "2026-08-18"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Model Serving"
  - "Cost Optimization"
keywords: "multi-model GPU"
faq:
  - q: "When multiplex models on one GPU?"
    a: "Many small models each under 10–15% GPU memory—Triton raises duty cycle if traffic peaks are uncorrelated."
  - q: "MPS vs MIG for isolation?"
    a: "MPS shares SM for throughput; MIG hard-partitions for compliance or noisy-neighbor SLO on mixed tiers."
  - q: "OOM risk on shared GPU?"
    a: "Profile peak memory sum with overlap load test—one model spike kills neighbors without memory limits."
  - q: "Escape hatch to dedicated pool?"
    a: "Auto-ticket when model exceeds 70% shared memory peak or p99 SLO breaches after multiplexing."
---
Ten GPUs at eight percent memory each after one-model-per-deployment policy; Triton multiplex raised duty cycle to sixty-four percent until one OOM killed four models sharing a node.

## Multiplex economics

Cloud bills GPU-hours not utilization—pack when peak traffic uncorrelated and memory headroom verified.

Production teams running model serving multi model learned that multiplex economics regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for multiplex economics: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument multiplex economics with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for multiplex economics: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for multiplex economics belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in multiplex economics configs.

Capacity note: estimate peak concurrency for multiplex economics, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving multi model: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for multiplex economics: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Memory profiling

model-analyzer peak sum under overlap load test—size shared pool for worst-case concurrent peaks.

Production teams running model serving multi model learned that memory profiling regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for memory profiling: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument memory profiling with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for memory profiling: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for memory profiling belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in memory profiling configs.

Capacity note: estimate peak concurrency for memory profiling, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving multi model: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for memory profiling: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Isolation options

MPS for throughput sharing; MIG for hard isolation on A100/H100 when compliance requires separation.

Production teams running model serving multi model learned that isolation options regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for isolation options: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument isolation options with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for isolation options: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for isolation options belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in isolation options configs.

Capacity note: estimate peak concurrency for isolation options, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving multi model: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for isolation options: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Noisy neighbor alerts

GPU memory and SM utilization per model via Triton metrics—auto-ticket dedicated pool on breach.

Production teams running model serving multi model learned that noisy neighbor alerts regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for noisy neighbor alerts: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument noisy neighbor alerts with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for noisy neighbor alerts: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for noisy neighbor alerts belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in noisy neighbor alerts configs.

Capacity note: estimate peak concurrency for noisy neighbor alerts, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving multi model: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for noisy neighbor alerts: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Rollout

Canary one multiplex host; compare p99 per model against dedicated baseline before fleet cutover.

Production teams running model serving multi model learned that rollout regressions appear when
traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for rollout: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument rollout with low-cardinality metrics tied to user-visible SLIs—error rate, tail latency,
freshness—not vanity gauges that never correlated with past pages.

Game day for rollout: quarterly staging injection with rollback under fifteen minutes using linked
runbook only—update runbook with what broke.

Ownership for rollout belongs in the service catalog with named rotation, last drill date, and known
sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in rollout configs.

Capacity note: estimate peak concurrency for rollout, apply 1.5–2× headroom against cloud quotas
before launch week—not during first outage.

Security review for model serving multi model: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for rollout: attribute cloud spend to owning team via tags; monthly review of cost
drivers prevents silent bill growth after config drift.
