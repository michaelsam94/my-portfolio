---
title: "Why You Should Track p99 Latency"
slug: "performance-latency-percentiles"
description: "Average latency hides user pain — track p50, p95, and p99 SLIs, set SLOs on tail latency, and fix the outliers that drive support tickets and churn."
datePublished: "2026-02-09"
dateModified: "2026-07-17"
tags: ["Performance", "SRE", "Observability", "Latency"]
keywords: "p99 latency, latency percentiles, tail latency SLO, histogram metrics, Apdex performance"
faq:
  - q: "What does p99 latency mean?"
    a: "99% of requests complete faster than this value; 1% are slower. If p99 is 2 seconds, one in every hundred users waits at least 2 seconds. For a site with 10,000 daily active users each making 20 requests, that's thousands of slow experiences per day."
  - q: "Why is average latency misleading?"
    a: "A few extremely slow requests skew the mean, but a healthy average can hide that 5% of users consistently wait 3+ seconds. Median (p50) tells you the typical experience; p99 tells you the worst realistic case users hit regularly."
  - q: "What p99 target should a web API aim for?"
    a: "Context-dependent, but a common starting point is p99 under 500ms for read APIs and under 1s for writes under normal load. Interactive UI actions often need p99 under 200ms. Set SLOs based on user journey requirements, not industry vanity numbers."
---

Our Grafana dashboard showed API latency at 45ms average. Support tickets said checkout "randomly freezes." The p99 was 4.8 seconds — one in fifty checkout attempts hit a lock wait on inventory reservation. Average lied because 95% of requests were cache hits on product browse. The users who noticed were the ones paying.

Percentiles describe distributions. Averages describe almost nothing useful about user experience.

## Percentiles in plain terms

| Percentile | Meaning | Use |
|------------|---------|-----|
| p50 (median) | Half faster, half slower | Typical experience |
| p95 | 5% slower | Near-worst regular case |
| p99 | 1% slower | Tail latency — incident detector |
| p999 | 0.1% slower | Outliers, often bugs or cold starts |

If p50 = 80ms and p99 = 3s, most users are happy and a steady minority isn't. That minority posts reviews.

## Histograms, not averages

Prometheus histograms (or OpenTelemetry exponential histograms) bucket request durations:

```yaml
# Prometheus histogram metric
http_request_duration_seconds_bucket{le="0.1"} 8500
http_request_duration_seconds_bucket{le="0.5"} 9800
http_request_duration_seconds_bucket{le="1.0"} 9950
http_request_duration_seconds_bucket{le="+Inf"} 10000
http_request_duration_seconds_count 10000
```

Query p99 in PromQL:

```promql
histogram_quantile(0.99,
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le, route)
)
```

Never compute percentiles by averaging pre-aggregated averages from multiple sources — you lose the distribution. Aggregate histogram buckets or use a system that merges sketches (Datadog DDSketch, HdrHistogram).

## SLOs on tail latency

Error budgets apply to latency too:

```
SLO: 99% of checkout requests complete in < 800ms over 30 days
```

Burn rate alerts when p99 degrades sustained — not just when average ticks up.

Pair latency SLO with error rate SLO. Slow responses that eventually 504 count as both failures.

```yaml
# Sloth or custom SLO example
slos:
  - name: checkout-latency
    objective: 99.0
    sli:
      events:
        error_query: sum(rate(http_request_duration_seconds_count{route="/checkout"}[5m]))
        total_query: sum(rate(http_request_duration_seconds_bucket{route="/checkout",le="0.8"}[5m]))
```

## What causes bad p99 (that p50 hides)

**Lock contention.** Row-level locks on hot inventory rows — p50 fine, p99 terrible during flash sales.

**GC pauses.** JVM or Go STW collections hit tail. p99 correlates with heap size.

**Cold paths.** Cache miss triggers full aggregation; 95% hit cache, 5% miss.

**Noisy neighbors.** Shared Kubernetes nodes — your pod's p99 spikes when neighbor runs batch job.

**N+1 queries.** First request after deploy warms pool; sustained N+1 hits tail on complex pages.

**External dependency tails.** Payment gateway p99 becomes your p99 if you wait synchronously.

Fix tail first where revenue concentrates — checkout, login, search — not admin reporting.

## Debugging tail latency

**Trace slow requests.** Sample 100% of requests above p99 threshold (OpenTelemetry tail sampling):

```python
if duration_ms > slo_threshold_ms:
    span.set_attribute("sample.priority", "high")
    exporter.export(span)
```

**Compare p99 by dimension.** Route, region, tenant size, cache hit/miss. One customer with 10M rows shouldn't define global p99 — slice by `tenant_id` for B2B.

**Load test at percentile targets.** k6 and Locust report p95/p99. Assert p99 < budget in CI smoke load tests against staging.

**Flame graphs on tail samples.** Profile requests above threshold — different code paths than median often emerge.

## Reporting to stakeholders

Dashboard layout:
- p50, p95, p99 on same chart, same Y axis
- Separate chart for request volume (context for percentile shifts)
- Annotations for deploys and incidents

"We improved p50 by 10ms" is noise. "Checkout p99 dropped from 4.2s to 600ms — support tickets down 40%" is a launch announcement.

## SLI implementation in code

Instrument at service boundary — HTTP handler exit, not deep in library code — so percentiles reflect user-perceived latency. Include error responses in latency SLI denominator separately from success latency — a fast 500 still fails the user.

Export histograms to Prometheus with consistent bucket boundaries across services so Grafana dashboards compose. Document bucket layout in platform observability guide.

## Operational notes

Define error budget policies tied to latency SLOs the same way availability SLOs burn budgets. Two consecutive weeks of p99 regression should trigger feature freeze on perf-sensitive services until root cause resolved — same discipline as error rate burn.

Rehearse latency incident response: who pulls trace samples, who approves feature flag kill, who communicates to customers. p99 incidents without runbook devolve into simultaneous Grafana staring.

## Common production mistakes

Teams get latency percentiles wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Performance work on latency percentiles regresses when optimizations target p50 only, benchmarks run on laptops not production hardware, and flamegraphs are captured once then never compared after refactors.

## Debugging and triage workflow

When latency percentiles misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Histogram bucket selection

Prometheus default buckets stop at 10s — useless for APIs targeting p99 under 500ms. Customize buckets: 5ms through 10s with density below 500ms. Too few buckets above your SLO flatten p99 curves.

## Multi-window SLO burn alerts

Single 5-minute p99 spike pages on noise. Use multi-burn-rate: fast burn (1h window) and slow burn (6h window) on same SLO. Checkout p99 SLO at 800ms — alert when 14.4x burn rate in 1h OR 6x in 6h.

## User-centric SLIs beyond HTTP

Mobile apps: time from tap to interactive content, not just API RTT. Include client-side queueing — analytics showed 400ms API p99 but 1.2s perceived latency from main-thread JSON parse.

## Apdex as executive summary

Apdex with T=500ms: satisfied if under 500ms, tolerating if under 2s. One number leadership understands while engineers drill p99 by route. Do not replace histograms with Apdex alone.

## Saturation correlates with tail latency

When p99 rises but p50 flat, check connection pool wait, thread pool queue depth, and disk IO saturation — tail often queueing not slow queries.

## Field notes on performance latency percentiles

Teams shipping this in production should baseline metrics before changing defaults, then validate under representative load — not empty staging databases. Document rollback paths alongside forward changes so on-call can revert without improvising. Review configuration quarterly even when dashboards look flat; schema drift and traffic growth change optimal settings silently until an incident exposes them. Pair automated checks with occasional game-day exercises that rehearse failure modes specific to this component rather than generic outage drills.

## Resources

- [Google SRE — SLIs, SLOs, SLAs](https://sre.google/sre-book/service-level-objectives/)
- [Prometheus histogram documentation](https://prometheus.io/docs/practices/histograms/)
- [OpenTelemetry metrics semantic conventions](https://opentelemetry.io/docs/specs/semconv/http/http-metrics/)
- [Gil Tene on latency percentiles (YouTube)](https://www.youtube.com/watch?v=lJ8ydBuGBBI)
- [Datadog percentile aggregation guide](https://docs.datadoghq.com/metrics/distributions/)
