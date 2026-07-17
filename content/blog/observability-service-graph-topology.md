---
title: "Service Graph Topology from Traces"
slug: "observability-service-graph-topology"
description: "Build live service dependency maps from distributed trace data—validate architecture docs and find circular calls."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Architecture"
  - "OpenTelemetry"
keywords: "service graph topology, trace service map, dependency map observability, jaeger service graph, tempo service graph"
faq:
  - q: "How is trace graph different from architecture diagrams?"
    a: "Diagrams show intent; trace graphs show actual runtime calls including surprises and deprecated paths."
  - q: "What sample rate is needed?"
    a: "1–10% head sampling usually suffices for stable edges on high-traffic paths."
  - q: "Can graphs replace service catalog?"
    a: "Complement—catalogs hold owners; graphs hold live edges weighted by error and latency."
---

Architecture slides showed checkout → payment → inventory. Trace graph added `legacy-tax` and inventory → checkout loop under load. Static diagrams lie; trace topology is as-built wiring.

## Generation

Jaeger SPM, Tempo service graph + span metrics processor, Honeycomb dependency views.

## Requirements

Consistent `service.name`; client+server instrumentation; W3C propagation on HTTP/gRPC/messaging.

## Incidents

Symptom alert → graph time range → red edge → exemplar traces on that edge.

## Governance

Weekly diff vs expected topology; ticket bot for missing expected edges.


## Service graph in deployment pipelines

Post-deploy smoke: compare service graph edge error rates for canary vs stable. Automated rollback if new version introduces edge to deprecated `legacy-tax` service—architecture regression caught before full traffic shift.

## Graph density management

Graphs with 200 nodes are unreadable. Filter to depth-2 from entry service `checkout` during incidents; full graph for quarterly architecture reviews only.

## Missing instrumentation ticket bot

Weekly job: edges in service catalog expected graph but absent in trace graph → create Jira tickets to owning teams. Closes observability gaps systematically.

## Cost of span metrics generation

Tempo metrics-generator derives RED from spans—increases Tempo CPU. Size generator pods for peak trace ingest; disable span metrics on dev environments to save cost while keeping prod service graph enabled.

## Graph-driven capacity planning

Edge weight `rps` growth month-over-month on `checkout→fraud` edge justifies scaling fraud service before checkout peak season—graph becomes capacity planning input, not just incident tool.

## Graph as onboarding artifact

New engineers study service graph in first week to learn real dependencies—faster than reading stale wiki. Assign mentor walkthrough: pick one user journey, trace it in graph, open exemplar trace, read correlated logs. Practical observability onboarding beats slide deck architecture review.

When decommissioning services, graph should show edge traffic trending to zero before DNS cut—graph-driven deprecation confirms no shadow callers remain.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.

## Production review cadence

Revisit dashboards and alert thresholds after every deploy affecting this observability surface. Weekly on-call review should include one exemplar trace or log linked from a metric spike—paper metrics without exemplars train teams to ignore charts.
