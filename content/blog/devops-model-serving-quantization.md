---
title: "Model Quantization for Production Inference"
slug: "devops-model-serving-quantization"
description: "Apply INT8/FP16 quantization with accuracy validation before deploy."
datePublished: "2026-08-21"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Model Serving"
  - "MLOps"
keywords: "model quantization"
faq:
  - q: "PTQ vs QAT for production?"
    a: "Post-training quantization first with calibration data matching production segments; quant-aware training when accuracy gates fail on critical cohorts."
  - q: "What breaks INT8 without calibration?"
    a: "Score drift on tail segments—holiday traffic, new product categories—not visible on aggregate offline eval."
  - q: "How pin TensorRT engines safely?"
    a: "Engine digest tied to CUDA, TensorRT, and GPU architecture; rebuild in CI before server upgrade; keep FP32 URI for instant rollback."
  - q: "Shadow compare before cutover?"
    a: "Online score distribution FP32 vs INT8 with alert on KL divergence threshold—aggregate accuracy hides segment regressions."
---
INT8 TensorRT cut p99 latency fifty-eight percent; a stale holiday calibration sample caused silent score drift on gift-card fraud until shadow compare caught KL divergence.

## PTQ pipeline

Export ONNX, calibrate with stratified production sample, build engine, eval gates on segment metrics not only aggregate AUC.

Production teams running model serving quantization learned that ptq pipeline regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for ptq pipeline: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument ptq pipeline with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for ptq pipeline: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for ptq pipeline belongs in the service catalog with named rotation, last drill date, and
known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in ptq pipeline configs.

Capacity note: estimate peak concurrency for ptq pipeline, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving quantization: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for ptq pipeline: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## When QAT is worth it

Business threshold missed after PTQ—budget ML time for quant-aware training on critical models only.

Production teams running model serving quantization learned that when qat is worth it regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for when qat is worth it: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument when qat is worth it with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for when qat is worth it: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for when qat is worth it belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in when qat is worth it configs.

Capacity note: estimate peak concurrency for when qat is worth it, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving quantization: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for when qat is worth it: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Serving pinned artifacts

Engine digest tied to CUDA driver and GPU arch; FP32 model URI kept for one-click rollback in InferenceService.

Production teams running model serving quantization learned that serving pinned artifacts
regressions appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations
until load replay used production timestamps.

Runbook for serving pinned artifacts: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument serving pinned artifacts with low-cardinality metrics tied to user-visible SLIs—error
rate, tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for serving pinned artifacts: quarterly staging injection with rollback under fifteen
minutes using linked runbook only—update runbook with what broke.

Ownership for serving pinned artifacts belongs in the service catalog with named rotation, last
drill date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in serving pinned artifacts configs.

Capacity note: estimate peak concurrency for serving pinned artifacts, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving quantization: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for serving pinned artifacts: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Online shadow compare

Route sample traffic through FP32 and INT8; alert on score distribution divergence before full cutover.

Production teams running model serving quantization learned that online shadow compare regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for online shadow compare: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument online shadow compare with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for online shadow compare: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for online shadow compare belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in online shadow compare configs.

Capacity note: estimate peak concurrency for online shadow compare, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for model serving quantization: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for online shadow compare: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Compliance records

Log model precision tier per prediction for audit—regulators ask which artifact was live when.

Production teams running model serving quantization learned that compliance records regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for compliance records: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument compliance records with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for compliance records: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for compliance records belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in compliance records configs.

Capacity note: estimate peak concurrency for compliance records, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for model serving quantization: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for compliance records: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.
