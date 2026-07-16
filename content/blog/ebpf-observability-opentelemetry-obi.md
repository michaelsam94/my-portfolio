---
title: "eBPF Observability with OpenTelemetry OBI"
slug: "ebpf-observability-opentelemetry-obi"
description: "How eBPF and OpenTelemetry OBI deliver zero-code observability: automatic RED metrics and traces from the kernel, with no app instrumentation or redeploys."
datePublished: "2026-06-26"
dateModified: "2026-06-26"
tags: ["Observability", "eBPF", "OpenTelemetry", "Infrastructure"]
keywords: "eBPF, OpenTelemetry OBI, zero-code observability, kernel observability, auto-instrumentation, RED metrics, tracing"
faq:
  - q: "What is eBPF observability?"
    a: "eBPF observability uses small programs running safely in the Linux kernel to observe application behavior — network calls, latency, request/response patterns — without modifying or instrumenting the application code. It captures telemetry at the kernel level, so you get metrics and traces from services you never touched."
  - q: "What is OpenTelemetry OBI?"
    a: "OBI (OpenTelemetry eBPF Instrumentation) is the OpenTelemetry project that uses eBPF to automatically generate metrics and traces from running applications with zero code changes. It attaches to processes at the kernel level and emits standard OTLP telemetry, so you get RED metrics and spans without adding SDKs."
  - q: "Does eBPF observability replace manual instrumentation?"
    a: "No — it complements it. eBPF gives you broad, automatic coverage of every service's HTTP/gRPC/SQL calls with no effort, which is excellent for the RED metrics baseline. Manual instrumentation still adds the business-level spans and attributes eBPF can't infer, like which customer or which feature flag was involved."
---

The reason so many services go uninstrumented isn't that engineers don't value observability — it's that instrumenting them is work, and the work never gets prioritized. Adding an OpenTelemetry SDK, wrapping handlers, threading context, and redeploying across dozens of services is a project. eBPF-based observability sidesteps that entirely: it observes your applications from *inside the Linux kernel*, so you get metrics and traces from services you never modified and can't easily modify — including that critical Go binary nobody wants to touch and the third-party process you don't have source for.

OpenTelemetry OBI (eBPF Instrumentation) is the project that packages this into the OTel ecosystem. Here's what it actually does, how, and where its limits are.

## What eBPF gives you at the kernel level

eBPF lets you run small, sandboxed, verified programs inside the Linux kernel, attached to hooks — syscalls, network events, function entry/exit. The kernel verifier guarantees these programs can't crash the system or loop forever, which is what makes running code in kernel space safe enough for production. For observability, this means you can watch every network read and write, every incoming connection, every request and response boundary, without the application knowing or cooperating.

Because it sees traffic at the kernel boundary, eBPF can reconstruct application-level behavior — an HTTP request came in, took 240 ms, returned a 500 — purely by observing the sockets. No SDK, no code change, no redeploy. That's the "zero-code" property, and for a fleet of heterogeneous services it's transformative: you point the agent at the host and telemetry starts flowing for everything on it.

## What OBI produces automatically

OBI attaches to your processes via eBPF and emits standard OpenTelemetry (OTLP) data, so it drops into whatever backend you already use — Grafana, Prometheus/Tempo, Jaeger, a commercial vendor. Out of the box, with no instrumentation, you get:

- **RED metrics** — Rate, Errors, Duration — for HTTP and gRPC services. This is the golden-signals baseline most dashboards are built on.
- **Latency histograms** per endpoint, so you can see p50/p95/p99 without adding a single timer.
- **Spans/traces** for requests flowing through instrumented processes, including some ability to follow context across services.
- **Protocol awareness** for common protocols (HTTP/1.1, HTTP/2, gRPC, and SQL-level visibility) so metrics are grouped by route/operation, not just raw sockets.

Running it is closer to deploying an agent than writing code:

```yaml
# Point OBI at a service and ship OTLP to your collector — no app changes
otel_ebpf:
  open_port: 8080                 # discover the service on this port
  service_name: checkout-api
otel:
  endpoint: http://otel-collector:4317
```

You deploy it as a sidecar or a node-level DaemonSet on Kubernetes, tell it which processes or ports to watch, and RED metrics for those services appear in your backend. Compare that to the per-service SDK rollout it replaces and the appeal is obvious.

## Where eBPF fits versus manual instrumentation

The mistake would be treating this as a replacement for all instrumentation. It isn't — it's the wide, automatic base layer, and manual instrumentation is the deep, business-aware layer on top. The division of labor:

| Concern | eBPF / OBI | Manual OTel SDK |
|---|---|---|
| RED metrics for every service | Automatic | Manual, per service |
| HTTP/gRPC/SQL latency | Automatic | Manual |
| Coverage of un-owned binaries | Yes | No (needs source) |
| Business-level spans/attributes | No | Yes |
| "Which customer / which flag" | No | Yes |
| Effort to add | Deploy an agent | Code + redeploy |

eBPF can tell you *that* the checkout endpoint got slow. It can't tell you it got slow *for premium-tier customers using the new payment provider* — that context lives in your business logic and only manual spans and attributes capture it. The right architecture is eBPF for universal baseline coverage, manual instrumentation for the handful of critical paths where you need rich, domain-specific detail. This mirrors the broader point in [designing for observability and SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/): automatic signals get you to "something is wrong," intentional signals get you to "here's why."

## The honest limitations

A few things eBPF observability genuinely can't or doesn't do well, so you plan around them:

- **Encrypted traffic (TLS) is harder.** Since eBPF observes at the socket level, TLS-encrypted payloads are opaque unless the agent hooks into the TLS library (uprobes on OpenSSL and friends). Coverage here depends on language/library support and is the fiddliest part.
- **Deep context propagation is limited.** eBPF can correlate a lot, but end-to-end distributed traces with rich parent/child context across many services are still where SDK-level propagation shines.
- **Kernel and platform constraints.** It needs a modern Linux kernel and appropriate privileges. On some managed platforms your access to the kernel is restricted, which limits what you can attach.
- **No business semantics, by design.** It sees bytes and syscalls, not meaning. Everything domain-specific still requires you to say it explicitly.

None of these are reasons to skip eBPF — they're reasons to pair it with a thin layer of intentional instrumentation rather than expecting it to do everything.

## How I'd adopt it

Start it as the baseline: deploy OBI (or a similar eBPF agent) across your fleet to get RED metrics and latency for every service immediately, and wire it into your existing OTLP collector. Overnight you go from "half our services have no telemetry" to "everything has golden signals," which is usually the biggest coverage gap teams have. Because it emits standard OpenTelemetry, you're not locking into a proprietary agent — you can route the same data anywhere OTLP goes, which keeps you portable in the way the [OpenTelemetry-based observability](https://blog.michaelsam94.com/llm-observability-opentelemetry-genai/) approach is designed for.

Then, incrementally, add manual spans to the critical user journeys and error paths where you need the "why." That two-layer approach — automatic breadth from eBPF, intentional depth from SDKs — gives you the best coverage-to-effort ratio I've found. The kernel does the tedious universal part for free; you spend your instrumentation budget only where domain context actually matters.

## The takeaway

eBPF observability, delivered through OpenTelemetry OBI, closes the oldest gap in observability practice: the services that never got instrumented because instrumenting them was too much work. By observing from the kernel, it produces RED metrics and traces for anything running on the host with zero code changes and standard OTLP output. It doesn't replace intentional instrumentation — it makes it optional for baseline coverage and reserves your effort for the business-level detail eBPF can't see. For most teams, deploying it is the fastest path from "we're flying blind on half our fleet" to a complete golden-signals baseline.

## Resources

- [OpenTelemetry eBPF Instrumentation (OBI)](https://opentelemetry.io/docs/zero-code/obi/)
- [OpenTelemetry documentation](https://opentelemetry.io/docs/)
- [ebpf.io — what is eBPF](https://ebpf.io/what-is-ebpf/)
- [Grafana Beyla / eBPF auto-instrumentation](https://grafana.com/docs/beyla/latest/)
- [The RED method (Grafana)](https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/)
- [Cilium — eBPF-based networking and observability](https://cilium.io/)
