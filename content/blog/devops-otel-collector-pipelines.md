---
title: "OpenTelemetry Collector Pipeline Design"
slug: "devops-otel-collector-pipelines"
description: "Route traces, metrics, and logs through OTel collectors with processors and exporters."
datePublished: "2026-06-04"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Platform"
keywords: "OpenTelemetry Collector, pipelines"
faq:
  - q: "Agent vs gateway collector?"
    a: "Agent on node for telemetry + batch; gateway for tail sampling and export fanout."
  - q: "Processor order matters?"
    a: "memory_limiter before batch; attributes before tail_sampling; filter early to drop noise."
  - q: "Exporter overload?"
    a: "Queue settings and retry—collector OOM drops spans silently without memory_limiter."
  - q: "Pipeline per tenant?"
    a: "Separate exporters for PCI vs non-PCI telemetry—never mix in one pipeline without scrubbing."
---
Collector OOM dropped spans during peak; processor order fix—memory_limiter before batch—and separate PCI pipeline stopped compliance scramble.

## Agent vs gateway

DaemonSet agent receivers plus batch; gateway tail sampling and multi-exporter fanout.

Production teams running otel collector pipelines learned that agent vs gateway regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for agent vs gateway: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument agent vs gateway with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for agent vs gateway: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for agent vs gateway belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in agent vs gateway configs.

Capacity note: estimate peak concurrency for agent vs gateway, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for otel collector pipelines: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for agent vs gateway: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Processor chain

memory_limiter, attributes, filter, batch, tail_sampling order documented—wrong order drops or duplicates.

Production teams running otel collector pipelines learned that processor chain regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for processor chain: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument processor chain with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for processor chain: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for processor chain belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in processor chain configs.

Capacity note: estimate peak concurrency for processor chain, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for otel collector pipelines: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for processor chain: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.

## Exporter backpressure

queue and retry settings; monitoring dropped spans metric on collector.

Production teams running otel collector pipelines learned that exporter backpressure regressions
appear when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load
replay used production timestamps.

Runbook for exporter backpressure: confirm blast radius, identify last config change, execute
single-step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during
Sev-1.

Instrument exporter backpressure with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for exporter backpressure: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for exporter backpressure belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in exporter backpressure configs.

Capacity note: estimate peak concurrency for exporter backpressure, apply 1.5–2× headroom against
cloud quotas before launch week—not during first outage.

Security review for otel collector pipelines: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for exporter backpressure: attribute cloud spend to owning team via tags; monthly
review of cost drivers prevents silent bill growth after config drift.

## Pipeline isolation

PCI telemetry separate exporters—scrubbing processor on shared pipeline risky.

Production teams running otel collector pipelines learned that pipeline isolation regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for pipeline isolation: confirm blast radius, identify last config change, execute single-
step rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument pipeline isolation with low-cardinality metrics tied to user-visible SLIs—error rate,
tail latency, freshness—not vanity gauges that never correlated with past pages.

Game day for pipeline isolation: quarterly staging injection with rollback under fifteen minutes
using linked runbook only—update runbook with what broke.

Ownership for pipeline isolation belongs in the service catalog with named rotation, last drill
date, and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in pipeline isolation configs.

Capacity note: estimate peak concurrency for pipeline isolation, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for otel collector pipelines: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for pipeline isolation: attribute cloud spend to owning team via tags; monthly review
of cost drivers prevents silent bill growth after config drift.

## Scaling gateway

HPA on collector gateway CPU and queue depth—not only agent count.

Production teams running otel collector pipelines learned that scaling gateway regressions appear
when traffic mix shifts—uniform staging QPS missed Black Friday combinations until load replay used
production timestamps.

Runbook for scaling gateway: confirm blast radius, identify last config change, execute single-step
rollback, capture SLI screenshots for postmortem—not ad-hoc dashboard search during Sev-1.

Instrument scaling gateway with low-cardinality metrics tied to user-visible SLIs—error rate, tail
latency, freshness—not vanity gauges that never correlated with past pages.

Game day for scaling gateway: quarterly staging injection with rollback under fifteen minutes using
linked runbook only—update runbook with what broke.

Ownership for scaling gateway belongs in the service catalog with named rotation, last drill date,
and known sharp edges—new engineers deploy safe canary within one week using that doc.

Change management: peer review from outside authoring team before prod promote—fresh eyes catch
embedded assumptions in scaling gateway configs.

Capacity note: estimate peak concurrency for scaling gateway, apply 1.5–2× headroom against cloud
quotas before launch week—not during first outage.

Security review for otel collector pipelines: least privilege on automation roles, short-lived
credentials, immutable audit logs for production changes—break-glass expires in forty-eight hours
with mandatory retrospective.

FinOps tie-in for scaling gateway: attribute cloud spend to owning team via tags; monthly review of
cost drivers prevents silent bill growth after config drift.
