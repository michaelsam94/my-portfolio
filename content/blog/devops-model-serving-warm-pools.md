---
title: "Warm Pools and Cold Start Mitigation"
slug: "devops-model-serving-warm-pools"
description: "Keep warm inference replicas or preloaded models to meet cold start SLOs."
datePublished: "2026-08-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Model Serving"
  - "Kubernetes"
keywords: "warm pools inference"
faq:
  - q: "When do warm pools beat scale-to-zero?"
    a: "When p99 cold start exceeds SLO—typically model load plus CUDA init over 2–5 seconds—and traffic is bursty but predictable within business hours."
  - q: "What should readiness probes do for GPU models?"
    a: "Run a representative dummy inference, not HTTP 200 alone—otherwise first real requests pay full load latency."
  - q: "How size warm pool cost versus SLO?"
    a: "Model idle GPU hours times spot price against error budget burn from cold starts; finance should see warm pool as explicit line item."
  - q: "Node-level versus pod-level warm pools?"
    a: "Node DaemonSet pre-pull plus minReplicas on InferenceService; combine when weight download dominates cold start."
---
Scale-from-zero took forty-five seconds on first predict; executives saw timeout errors while HPA showed one replica 'ready' because readiness only checked HTTP, not model weights.

## Cold start decomposition

Trace schedule, image pull, weight download from S3, CUDA init, and first JIT compile—dominant term sets fix: pre-pull vs minReplicas vs baked image.

Production teams running model serving warm pools learned that cold start decomposition regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for cold start decomposition: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument cold start decomposition with low-cardinality metrics tied to user-visible SLIs—error
rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for cold start decomposition: quarterly staging injection with rollback under fifteen
minutes using linked runbook only—update runbook with what broke.

Ownership for cold start decomposition belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in cold start decomposition configs.

Capacity note: estimate peak concurrency for cold start decomposition, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving warm pools: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for cold start decomposition: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Readiness that reflects reality

Dummy inference in readinessProbe warms GPU kernels; liveness stays lightweight—avoid marking ready before predict path works.

Production teams running model serving warm pools learned that readiness that reflects reality
regressions appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations
until load replay used production timestamps.

Runbook for readiness that reflects reality: confirm blast radius, identify last config change,
execute single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search
during Sev-1.

Instrument readiness that reflects reality with low-cardinality metrics tied to user-visible
SLIs—error rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for readiness that reflects reality: quarterly staging injection with rollback under
fifteen minutes using linked runbook only—update runbook with what broke.

Ownership for readiness that reflects reality belongs in the service catalog with named rotation,
last drill date, and known sharp edges—new engineers deploy safe canary within one week using that
doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in readiness that reflects reality configs.

Capacity note: estimate peak concurrency for readiness that reflects reality, apply 1.5–2× headroom
against cloud quotas before launch week—not during first outage.

Security review for model serving warm pools: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for readiness that reflects reality: attribute cloud spend to owning team via tags;
monthly review of cost drivers prevents silent bill growth after config drift.

## Node-level pre-pull

DaemonSet or init on GPU nodes pulls model URIs declared in ConfigMap when manifest promotes—cuts pull from critical path.

Production teams running model serving warm pools learned that node-level pre-pull regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for node-level pre-pull: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument node-level pre-pull with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for node-level pre-pull: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for node-level pre-pull belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in node-level pre-pull configs.

Capacity note: estimate peak concurrency for node-level pre-pull, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving warm pools: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for node-level pre-pull: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Cost model for warm idle

Finance line item: warm GPU hours times spot rate versus SLO breach cost—size minReplicas to p99 traffic floor not peak 24/7.

Production teams running model serving warm pools learned that cost model for warm idle regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for cost model for warm idle: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument cost model for warm idle with low-cardinality metrics tied to user-visible SLIs—error
rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for cost model for warm idle: quarterly staging injection with rollback under fifteen
minutes using linked runbook only—update runbook with what broke.

Ownership for cost model for warm idle belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in cost model for warm idle configs.

Capacity note: estimate peak concurrency for cost model for warm idle, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving warm pools: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for cost model for warm idle: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## KServe and Knative tuning

minScale annotation, scale-down delay, and retention period prevent flapping on bursty API—document per tier.

Production teams running model serving warm pools learned that kserve and knative tuning regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for kserve and knative tuning: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument kserve and knative tuning with low-cardinality metrics tied to user-visible SLIs—error
rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for kserve and knative tuning: quarterly staging injection with rollback under fifteen
minutes using linked runbook only—update runbook with what broke.

Ownership for kserve and knative tuning belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in kserve and knative tuning configs.

Capacity note: estimate peak concurrency for kserve and knative tuning, apply 1.5–2× headroom
against cloud quotas before launch week—not during first outage.

Security review for model serving warm pools: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for kserve and knative tuning: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

```yaml
readinessProbe:
  exec:
    command: ["python", "-c", "import tritonclient; tritonclient.infer('warmup')"]
  periodSeconds: 10
  failureThreshold: 3
```
Size `minReplicas` from p99 traffic floor, not peak—warm pool cost is explicit finance line item.
