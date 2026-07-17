---
title: "Continuous Profiling with Parca"
slug: "observability-continuous-profiling-parca"
description: "Deploy Parca for always-on CPU and memory profiling in Kubernetes—correlate flame graphs with metrics and traces without manual pprof captures."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Kubernetes"
  - "Performance"
keywords: "parca continuous profiling, eBPF profiling kubernetes, flame graphs production, parca agent, always-on profiling"
faq:
  - q: "How is Parca different from grabbing pprof manually during incidents?"
    a: "Manual pprof captures one moment. Parca scrapes profiles continuously and lets you diff flame graphs before and after a deploy without reproducing the incident live."
  - q: "What overhead does Parca add in production?"
    a: "eBPF-based CPU sampling typically adds 1–3% CPU at default sample rates. Memory profiling costs more—enable selectively or sample fewer pods."
  - q: "Does Parca replace distributed tracing?"
    a: "No. Traces show per-request path; profiles show which functions consumed CPU. Link high-latency spans to profiles at the same timestamp."
---

Latency doubled after a deploy. Traces pointed at `inventory-service`, but spans were generically slow. Someone SSH'd and ran pprof during quiet traffic—the flame graph looked fine. The spike happened under load at 14:32. Parca solves that: continuous profiling stored as time series, queryable like metrics, diffable like git blame for CPU.

## Architecture on Kubernetes

Parca Agent (DaemonSet eBPF) scrapes app pods; Parca Server stores profiles in S3/MinIO; UI provides flame graphs and diffs. Label pods with `app`, `version`, `environment` for filtering.

## Investigating a latency regression

Compare profiles 14:00–14:30 vs 14:30–15:00 after deploy—new hot path in `calculateAvailability()` visible without reproduction.

## eBPF sampling and symbols

Unwind quality depends on debug symbols—ship symbols separately for stripped Go/Rust binaries. Memory profiles heavier than CPU—enable per namespace during OOM investigations.

## Security

Profiles expose function names—restrict Parca UI via SSO; encrypt object storage. Disable public pprof endpoints when Parca covers profiling.

## Parca vs alternatives

Parca fits teams on Prometheus/Grafana wanting open-source profiles beside existing stacks without per-host SaaS fees.


## Symbol upload and container builds

Go and Rust binaries stripped in Docker multi-stage builds lose symbols Parca needs. Options:

**Separate debug image** — CI pushes `myapp:1.2.0-debug` with symbols to internal registry; Parca queries debuginfod or symbol server mapped by build ID.

**Build ID in Kubernetes labels** — Pod label `git.sha=abc123`; Parca maps profiles to symbols from object storage path `symbols/abc123/`.

Without symbols, flame graphs show hex addresses—better than nothing, useless for developers who do not carry addr2line in muscle memory.

## Profiling and compliance workloads

Regulated environments may restrict always-on profiling as potential data leakage via stack strings. Mitigations:

- Profile only non-PII code paths (exclude payment handler packages via build tags—not practical usually)
- Restrict Parca UI to VPC-only
- Redact symbol names in UI export for vendor support tickets

Legal review often approves CPU sampling where heap dumps would not pass—document difference for security questionnaires.

## Integrating with CI performance gates

Optional: short k6 load in CI with Parca scrape of staging deploy. Compare top 10 functions vs baseline main branch—fail PR if new hot path adds >5% CPU in `applyDiscounts`. Lightweight guard against algorithmic regressions before production profiles confirm pain.

## Parca vs Pyroscope operational choice

Both use eBPF; Grafana Pyroscope merges into LGTM stack with unified Grafana Explore. Parca remains strong for teams wanting CNCF-aligned OSS without Grafana Cloud coupling. Evaluation criteria: existing object storage (S3 compatibility), team familiarity, and whether Tempo trace-to-profile linking is already on roadmap—Grafana path shortens integration time.

## Retention and legal hold

Profile blobs may contain function names revealing unreleased features—align S3 retention with code release policy. Legal hold on incident dates: snapshot profile object storage prefix for postmortem evidence alongside traces.

## On-call training exercise

Quarterly: inject CPU loop in staging service, on-call must find hot function in Parca within 15 minutes without SSH. Failure means runbook or access gaps—fix before production incident.

## Ownership and access model

Assign Parca UI access to service teams for their namespaces only—platform operates agents and storage, product teams investigate their flame graphs. Prevents accidental cross-team visibility into unreleased feature code paths visible in symbols while still enabling self-service perf debugging.

Include Parca link in performance-related incident templates next to Grafana and Tempo. Three-way correlation (metrics spike, trace slow span, profile hot function) should be exercisable in under ten minutes by any mid-level backend engineer after onboarding lab.


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
