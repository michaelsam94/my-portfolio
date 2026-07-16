---
title: "Alert on Symptoms, Not Causes"
slug: "observability-alerting-on-symptoms"
description: "Design alerting on user-visible symptoms instead of internal causes: symptom-based SLOs, alert quality, runbook patterns, and reducing pager fatigue."
datePublished: "2025-09-27"
dateModified: "2025-09-27"
tags: ["DevOps", "Observability", "SRE", "Operations"]
keywords: "symptom-based alerting, alert fatigue, SLO alerting, on-call best practices, cause vs symptom alerts, pager duty reduction, monitoring alerts"
faq:
  - q: "What is the difference between a symptom alert and a cause alert?"
    a: "A symptom alert fires when users experience problems—error rate above SLO, checkout latency P99 above 2 seconds. A cause alert fires on internal state—CPU above 80%, a pod restarted, a queue depth increased. Symptoms tell you to act; causes help you diagnose after you are already responding."
  - q: "Should I ever alert on causes?"
    a: "Yes, but as secondary diagnostics linked to symptom alerts, not standalone pages. Alert on disk full only if it will cause user impact within 30 minutes. A pod restart that self-healed in 5 seconds does not need a page—it needs a ticket."
  - q: "How many alerts should fire per on-call shift?"
    a: "Target zero pages for healthy systems. A well-tuned setup pages 1–3 times per week for genuine user-impacting issues. If on-call gets paged daily, you have too many cause-based alerts or thresholds set too low."
---

On-call gets paged at 3 AM because CPU hit 82% on a staging server. Nobody checks staging at 3 AM. The alert auto-resolves in 10 minutes. Meanwhile, checkout errors spiked to 8% for 45 minutes last Tuesday and nobody noticed until customer support escalated. The fix is not more alerts—it is alerting on symptoms users feel, not causes engineers guess at. Google's SRE book calls this "monitoring symptoms, not causes." Most teams understand the concept and still page on disk usage.

## Symptom vs cause examples

| Symptom (page) | Cause (dashboard/ticket) |
|----------------|--------------------------|
| Checkout error rate > 1% for 5 min | Payment service pod OOMKilled |
| API P99 latency > 500 ms for 10 min | Database connection pool exhausted |
| Login success rate < 99% for 5 min | Redis master failover in progress |
| Search returns zero results rate > 0.1% | Elasticsearch shard relocation |
| Video playback failure rate > 2% | CDN edge node packet loss |

Symptoms are user-facing SLIs. Causes are internal telemetry that explains why.

## Defining symptom alerts from SLOs

```yaml
# prometheus alerting rule
groups:
  - name: checkout-symptoms
    rules:
      - alert: CheckoutErrorBudgetBurn
        expr: |
          (
            sum(rate(http_requests_total{service="checkout", status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total{service="checkout"}[5m]))
          ) > 0.01
        for: 5m
        labels:
          severity: page
          team: payments
        annotations:
          summary: "Checkout error rate above 1% for 5 minutes"
          runbook: "https://wiki.example.com/runbooks/checkout-errors"
          dashboard: "https://grafana.example.com/d/checkout"
```

`for: 5m` prevents paging on transient blips. Tune the window to your SLO burn rate.

## Multi-window burn rate alerts

Google's SRE workbook recommends alerting at multiple timescales:

```yaml
# Fast burn — 2% budget consumed in 1 hour
- alert: CheckoutSLOFastBurn
  expr: checkout_error_rate > (14.4 * 0.001)  # 14.4x burn of 0.1% budget
  for: 2m

# Slow burn — 10% budget consumed in 6 hours
- alert: CheckoutSLOSlowBurn
  expr: checkout_error_rate > (6 * 0.001)
  for: 30m
```

Fast burn pages immediately. Slow burn creates a ticket or lower-severity notification.

## Alert quality checklist

Before adding any alert, answer:

1. **Will someone need to act at 3 AM?** If no, make it a dashboard or daily report.
2. **Does this indicate user impact?** If no, it is a cause alert—demote it.
3. **Has this alert fired without action in the last 90 days?** Delete it.
4. **Is there a runbook?** An alert without a runbook is an anxiety notification.
5. **Can the recipient fix it?** Route database alerts to the database team, not frontend.

## Runbook structure

```markdown
# Checkout Error Rate High

## Impact
Users cannot complete purchases. Revenue loss ~$X/minute.

## Diagnosis
1. Check checkout error rate dashboard (link)
2. Identify failing endpoint: /api/checkout vs /api/payment
3. Check payment provider status page (link)

## Common causes
- Payment provider outage → enable maintenance mode
- Database connection exhaustion → scale connection pool
- Bad deployment → rollback (link to deploy history)

## Escalation
- Payment provider: call 1-800-xxx (account #12345)
- Database team: #database-oncall Slack
```

Every page-worthy alert links to a runbook with these four sections.

## Reducing noise from cause alerts

Convert cause alerts to:

- **Dashboard panels** — CPU, memory, queue depth visible during investigation.
- **Daily digests** — "12 pods restarted yesterday" in Slack at 9 AM.
- **Auto-remediation** — pod restart triggers HPA scale-up, not a page.
- **Correlated tickets** — cause alerts attached to symptom alerts as context.

```yaml
# BAD — pages on every pod restart
- alert: PodRestarted
  expr: increase(kube_pod_container_status_restarts_total[5m]) > 0

# BETTER — pages only if restarts correlate with errors
- alert: PodRestartCausingErrors
  expr: |
    increase(kube_pod_container_status_restarts_total[10m]) > 2
    and
    sum(rate(http_requests_total{status=~"5.."}[5m])) > 0.005
  for: 5m
```

## Measuring alert health

Track monthly:
- **Pages per on-call shift** — target < 0.5
- **Actionable page rate** — % of pages where someone took action (target > 80%)
- **MTTA** (mean time to acknowledge) — target < 5 minutes
- **Repeat alerts** — same alert firing 3+ times/week needs tuning or fixing

Review all alerts quarterly. Delete anything that has not caused action in 90 days.

## Symptom-based alerts

Alert on user pain, not causes:

| Bad alert | Good alert |
|-----------|------------|
| CPU > 80% | Checkout error rate > 1% |
| Pod restarted | p99 latency > 2s for 5 min |
| Disk 90% | Job queue depth growing 30 min |

Every alert needs runbook link and severity that maps to response time.

## Common production mistakes

Teams get alerting on symptoms wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Observability for alerting on symptoms fails when dashboards exist but nobody owns alert routing, high-cardinality labels explode metrics cost, and logs lack trace correlation so incidents become grep archaeology.

## Debugging and triage workflow

When alerting on symptoms misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Google SRE Workbook — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/) — multi-window burn rate methodology
- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) — symptoms vs causes
- [Prometheus alerting rules](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) — rule syntax and `for` duration
- [Grafana OnCall alert routing](https://grafana.com/docs/oncall/latest/) — escalation and on-call scheduling
- [PagerDuty event orchestration](https://support.pagerduty.com/docs/event-orchestration) — alert deduplication and routing
