---
title: "SLIs, SLOs, and Error Budgets"
slug: "observability-slis-slos-error-budgets"
description: "Define SLIs, SLOs, and error budgets for reliable services: measurement, target setting, burn rate alerting, and balancing reliability with velocity."
datePublished: "2025-10-12"
dateModified: "2026-07-17"
tags: ["DevOps", "SRE", "Observability", "Architecture"]
keywords: "SLI SLO error budget, service level objectives, service level indicators, error budget policy, SRE reliability, burn rate alerting"
faq:
  - q: "What is a good starting SLO for a web API?"
    a: "99.9% availability (8.7 hours downtime per year) is a common starting point for user-facing APIs. 99.99% (52 minutes/year) suits payment and auth services. 99% (3.65 days/year) may be acceptable for internal tools. Set SLOs based on user expectations, not aspiration."
  - q: "What happens when the error budget is exhausted?"
    a: "Stop feature releases and focus engineering on reliability until budget recovers. This is the error budget policy—it creates a data-driven tradeoff between shipping features and maintaining reliability. Without consequences, SLOs are just dashboards."
  - q: "How many SLIs should a service have?"
    a: "Two to four. One availability SLI (success rate), one latency SLI (P99 below threshold), and optionally throughput or data freshness. More than four dilutes focus and makes error budget calculations confusing."
---

"We target 99.99% uptime" appears on every architecture doc. Nobody measures it. Deployments happen Friday at 5 PM. Incidents are post-mortemed but nothing changes. SLIs, SLOs, and error budgets replace aspirational uptime with measured reliability and explicit tradeoffs. An SLI is what you measure. An SLO is the target. An error budget is how much unreliability you can afford before stopping feature work.

## Definitions

| Term | Meaning | Example |
|------|---------|---------|
| SLI | Quantified measure of service behavior | % of requests completing < 500 ms |
| SLO | Target range for an SLI | 99% of requests < 500 ms over 30 days |
| SLA | Contract with consequences for missing SLO | 99.9% or credits (legal, not engineering) |
| Error budget | Allowed unreliability = 100% - SLO | 1% of requests can exceed 500 ms |

## Choosing SLIs

Pick SLIs users actually notice:

**Availability:**

```promql
sum(rate(http_requests_total{status!~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

**Latency:**

```promql
histogram_quantile(0.99,
  sum by (le) (rate(http_request_duration_seconds_bucket[5m]))
)
```

**Correctness (for data pipelines):**

```promql
sum(rate(records_processed_correctly[5m]))
/
sum(rate(records_processed_total[5m]))
```

## Setting SLO targets

Work backward from user tolerance:

1. **What breaks user trust?** Checkout errors > 0.5% → users abandon carts.
2. **What is current performance?** Measure for 30 days without a target.
3. **Set SLO slightly below current** — achievable but not trivially met.

```
Current P99 latency: 320 ms (95th percentile of daily P99s)
SLO target: 99% of requests < 500 ms over 30 days
```

Tighter than current performance guarantees budget burn. Looser provides no improvement incentive.

## Error budget calculation

```
SLO: 99.9% availability over 30 days
Total minutes: 43,200
Allowed downtime: 43,200 × 0.001 = 43.2 minutes

Current month downtime: 12 minutes
Remaining budget: 31.2 minutes (72% remaining)
```

Display budget remaining on a team dashboard. Update hourly.

```promql
# Error budget remaining (30-day window, 99.9% SLO)
1 - (
  (1 - avg_over_time(sli:availability:ratio[30d])) 
  / (1 - 0.999)
)
```

## Burn rate alerting

| Window | Budget consumed | Action |
|--------|----------------|--------|
| 1 hour | 2% (14.4x burn) | Page on-call |
| 6 hours | 5% (6x burn) | Page on-call |
| 3 days | 10% (2.3x burn) | Ticket to reliability team |
| 30 days | Budget exhausted | Freeze feature deploys |

```yaml
- alert: ErrorBudgetFastBurn
  expr: |
    sli:availability:ratio[1h] < 0.9856  # 14.4x burn of 0.1% budget
  for: 2m
  labels:
    severity: page
```

## Error budget policy

Write this down and enforce it:

```markdown
## Error Budget Policy

### When budget > 50% remaining
- Normal feature development and deployments
- Deployments any day, any time with standard review

### When budget 25–50% remaining
- Increase deployment scrutiny (canary required)
- No deployments on Fridays
- Reliability improvements prioritized in sprint planning

### When budget < 25% remaining
- Feature freeze except critical business needs
- All engineering focused on reliability
- Post-incident action items mandatory before new features

### When budget exhausted (0%)
- Complete feature freeze
- Executive notification
- Reliability review before lifting freeze
```

Without policy, error budgets are vanity metrics.

## Multi-SLI services

Combine SLIs with AND logic for the overall budget:

```
Service health = availability SLO met AND latency SLO met
```

If availability is 99.95% but latency SLO is breached, the service is not meeting its commitment. Track each SLI independently; alert on each.

## Reporting

Monthly reliability review:
- SLO attainment per service (met / missed)
- Error budget consumed (%)
- Top incidents by budget burn
- Action items from budget exhaustion events

Share with engineering and product. SLOs create a shared language between reliability and velocity.

## SLI implementation with Prometheus

Define SLIs as PromQL queries:

```yaml
# sloth-spec.yaml
slos:
  - name: api-availability
    objective: 99.9
    sli:
      events:
        error_query: sum(rate(http_requests_total{status=~"5.."}[5m]))
        total_query: sum(rate(http_requests_total[5m]))
    alerting:
      burn_rate:
        - short_window: 5m
          long_window: 1h
          factor: 14.4  # burns 2% budget in 1 hour

  - name: api-latency
    objective: 99.0  # 99% of requests < 200ms
    sli:
      events:
        error_query: sum(rate(http_request_duration_seconds_bucket{le="0.2"}[5m]))
        total_query: sum(rate(http_request_duration_seconds_count[5m]))
```

Sloth generates Prometheus recording rules and alert rules from SLO spec. Burn rate alerts fire before budget exhausted — not after.

## Error budget burn rate alerting

Multi-window burn rate alerts catch fast and slow burns:

```
Fast burn:  2% budget in 1 hour  → page on-call
Slow burn:  5% budget in 6 hours → ticket to team
Critical:   10% budget in 1 day  → feature freeze discussion
```

```promql
# Burn rate = error rate / (1 - SLO target)
# For 99.9% SLO: burn rate 1.0 = consuming budget at sustainable rate
# Burn rate 14.4 = consumes 2% budget in 1 hour
slo:burnrate5m / (1 - 0.999) > 14.4
```

Alert on burn rate, not error rate — a 0.5% error rate is fine for 99% SLO but catastrophic for 99.99% SLO.

## Choosing SLO targets

Don't copy Google's 99.99% — choose based on user impact and cost:

| Service type | Typical SLO | Rationale |
|---|---|---|
| Payment processing | 99.99% | Direct revenue impact |
| Core API | 99.9% | User-facing, high traffic |
| Internal tools | 99% | Low user count, async OK |
| Batch/analytics | 95% | Delayed processing acceptable |

```python
# Cost of nines calculator
def downtime_minutes(slo_percent: float, period_days: int = 30) -> float:
    return (1 - slo_percent / 100) * period_days * 24 * 60

# 99.9%  → 43 min/month downtime budget
# 99.99% → 4.3 min/month
# 99.999% → 26 seconds/month (requires active-active multi-region)
```

Each nine costs roughly 10× in infrastructure complexity. Choose the minimum SLO users actually need.

## Failure modes

- **SLO without error budget policy** — budget exhausted, nothing changes
- **Alerting on error rate not burn rate** — wrong sensitivity for SLO target
- **SLO copied from Google** — 99.99% for internal tool wastes engineering effort
- **Single SLI for complex service** — latency breach hidden by good availability
- **SLO not shared with product** — engineering freezes features, product surprised

## Production checklist

- SLI defined as PromQL query with recording rules
- Multi-window burn rate alerts (fast + slow burn)
- Error budget policy documented with feature freeze thresholds
- SLO target chosen based on user impact, not industry benchmark
- Multiple SLIs tracked independently (availability AND latency)
- Monthly reliability review shared with engineering and product

## Resources

- [Google SRE Workbook — Implementing SLOs](https://sre.google/workbook/implementing-slos/) — step-by-step SLO creation
- [Google SRE Book — Service Level Objectives](https://sre.google/sre-book/service-level-objectives/) — theory and practice
- [Sloth SLO generator](https://sloth.dev/) — Prometheus SLO rules from YAML
- [Pyrra SLO dashboard](https://github.com/pyrra-dev/pyrra) — open-source SLO monitoring
- [OpenSLO specification](https://www.openslo.com/) — vendor-neutral SLO definition format
