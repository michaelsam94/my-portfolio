---
title: "Designing for Observability: SLOs, SLIs, Error Budgets"
slug: "designing-for-observability-slos"
description: "How to design for observability with SLIs, SLOs, and error budgets: choose metrics that reflect user experience, set honest targets, and alert on what matters."
datePublished: "2026-06-13"
dateModified: "2026-06-13"
tags: ["Observability", "SRE", "Reliability", "Backend"]
keywords: "observability, SLO, SLI, error budget, monitoring, SRE, alerting, service level objective"
faq:
  - q: "What's the difference between an SLI, an SLO, and an SLA?"
    a: "An SLI is a measured indicator of service quality, like the percentage of requests served under 300ms. An SLO is your internal target for that SLI, such as 99.9% over 30 days. An SLA is an external contract with financial consequences, and it's usually set looser than your SLO so you have margin."
  - q: "What is an error budget?"
    a: "An error budget is the allowed amount of unreliability implied by your SLO. A 99.9% availability SLO permits 0.1% failure — roughly 43 minutes a month. As long as you're within budget you can ship fast; when you burn through it, you slow down and prioritize reliability."
  - q: "How is observability different from monitoring?"
    a: "Monitoring tells you whether known failure modes are happening via predefined dashboards and alerts. Observability is the ability to ask new questions about your system's behavior from its outputs — metrics, logs, and traces — so you can debug problems you didn't anticipate."
---

Most teams monitor the wrong things. They alert on CPU at 80%, on disk filling, on a pod restarting — machine-level symptoms that may or may not mean a user is having a bad time. Then a real outage happens, every host looks healthy, and nobody gets paged while customers can't check out. The shift that fixes this is designing for observability around the user's experience, expressed as SLIs and SLOs, with an error budget that turns reliability from a vague aspiration into a number you can actually manage.

The core idea from Google's SRE practice is a chain: pick a Service Level Indicator (SLI) that reflects what users feel, set a Service Level Objective (SLO) as your target for it, and derive an error budget — the failure you're allowed — from that target. Everything else, from alerting to release decisions, hangs off this chain.

## Start with what the user feels

An SLI is a carefully chosen metric that tracks one aspect of the user experience. The trap is choosing metrics that are easy to collect rather than meaningful. CPU utilization is trivial to measure and nearly useless as a reliability signal — users don't experience CPU, they experience slow pages and failed requests.

Good SLIs are almost always ratios of good events to valid events, framed from the user's side:

- **Availability:** successful requests / total valid requests
- **Latency:** requests faster than a threshold / total requests
- **Quality:** requests served without degradation / total requests

For a real-time system I've worked on, the SLI that mattered wasn't "is the server up" — it was "did a control command reach the device and get acknowledged within the latency the user perceives as instant." That's user-centric. Pick the two or three indicators that capture whether your service is doing its job, and resist the urge to turn every available metric into an SLI.

## Set an SLO you can defend

An SLO is the target: "99.9% of requests succeed over a rolling 30 days." The most common mistake is reflexively chasing more nines. Each nine is exponentially more expensive, and 100% is the wrong target for everything, because the marginal cost of the last fraction of a percent is enormous and users usually can't even tell.

| SLO | Downtime / 30 days | Downtime / year |
|---|---|---|
| 99% | ~7.2 hours | ~3.65 days |
| 99.9% | ~43 minutes | ~8.76 hours |
| 99.95% | ~22 minutes | ~4.38 hours |
| 99.99% | ~4.3 minutes | ~52 minutes |

The right SLO is the loosest one your users are happy with, because that leaves you the most room to move fast. A background analytics pipeline might be fine at 99%; a payment path might need 99.99%. Set it based on what users actually require, not on how many nines sound impressive in a meeting. And keep any external SLA looser than your internal SLO — the SLO is your early-warning line, the SLA is the cliff.

## The error budget changes behavior

Here's where SLOs stop being a dashboard decoration and start shaping decisions. If your SLO is 99.9%, then 0.1% unreliability is not a failure — it's a *budget*. Over 30 days that's about 43 minutes of allowed downtime, or the equivalent in errors. As long as you're spending within budget, you're meeting your promise, and you should be shipping features aggressively.

When you burn through the budget, the policy flips: reliability work takes priority over features until you're back in the green. This is the mechanism that resolves the eternal dev-versus-ops tension, because it replaces opinion with a number. Nobody argues about whether to slow down; the budget is either spent or it isn't.

```
error_budget = 1 - SLO          # 99.9% -> 0.001 = 0.1%
budget_minutes = 30d * (1 - 0.999) ≈ 43 min / month

if budget_remaining <= 0:
    freeze_risky_launches()      # spend the next cycle on reliability
else:
    ship()                       # you've earned the risk
```

This budget is exactly what makes techniques like [feature flags and progressive rollout](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) safe to use aggressively — you can take calculated risks because you know precisely how much failure you can afford, and a canary that misbehaves spends budget you can measure rather than trust you can't quantify.

## Alert on burn rate, not on every blip

Once you have an SLO, alerting gets dramatically better. Instead of paging on "CPU > 80%" or "one 500 error," you alert on **error budget burn rate** — how fast you're consuming the budget relative to the window. A fast burn (you'll exhaust a month's budget in an hour) pages someone immediately; a slow burn (mild elevation over days) opens a ticket. This is how you escape alert fatigue: the number of pages drops to the ones that actually threaten your objective.

Multi-window, multi-burn-rate alerts are the SRE-recommended shape — combine a fast-burn short-window alert for acute outages with a slow-burn long-window alert for creeping degradation. The result is that a page reliably means "a user-facing promise is at risk," which is the only thing worth waking someone for. Alerting on causes (high CPU) instead of symptoms (budget burn) is what fills rotations with noise nobody trusts, and untrusted alerts are worse than no alerts.

## The three pillars serve the questions

Observability rests on metrics, logs, and traces, but the pillars are a means, not the goal. The goal is being able to answer questions you didn't anticipate when something breaks.

- **Metrics** — cheap, aggregate, always-on. Your SLIs live here, and they tell you *that* something is wrong.
- **Traces** — a request's path across services, showing *where* the latency or error is. Essential once you have more than a couple of services talking over [gRPC or HTTP](https://blog.michaelsam94.com/rest-vs-grpc-vs-graphql-2026/).
- **Logs** — the detailed record of *why*, once a trace has pointed you at the right component.

The connective tissue is correlation: a trace id that threads through logs and links to the metrics for that request. Standardizing on OpenTelemetry gives you vendor-neutral instrumentation across all three, so you're not locked into one backend and can actually follow a request from the SLI that flagged it down to the log line that explains it.

Designing for observability means instrumenting for the user's experience first, expressing reliability as SLIs and SLOs you can defend, and letting the error budget govern how fast you move. Do that and monitoring stops being a wall of graphs nobody reads and becomes a decision-making tool: it tells you when to ship boldly, when to slow down, and — when something breaks — gives you the thread to pull. That discipline underpins every resilient system I've helped build; there's more on that side of my work in [my portfolio](https://michaelsam94.com/).

## Resources

- [Google SRE Book — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/)
- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/)
- [Google SRE Workbook — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)
- [OpenTelemetry — Documentation](https://opentelemetry.io/docs/)
- [Google SRE Book — Embracing Risk (error budgets)](https://sre.google/sre-book/embracing-risk/)
