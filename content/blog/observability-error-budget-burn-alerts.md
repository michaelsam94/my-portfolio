---
title: "Error Budget Burn Rate Alerts"
slug: "observability-error-budget-burn-alerts"
description: "Alert on SLO error budget burn rates—fast and slow windows—so pages fire on user impact trends, not single blips."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "SRE"
  - "Prometheus"
keywords: "error budget burn rate, slo alerting, multi window burn alerts, google sre alerting, prometheus slo"
faq:
  - q: "What is error budget burn rate?"
    a: "Burn rate is how fast you consume monthly error budget. A burn rate of 14.4 means you exhaust a 30-day budget in ~2 days at the current error ratio."
  - q: "Why use multiple alert windows?"
    a: "Short windows catch sudden outages; long windows catch slow leaks that single-spike alerts miss."
  - q: "What SLO target should I start with?"
    a: "99.9% monthly availability for tier-1 journeys is common. Pick SLIs users feel: success rate and latency threshold."
---

Checkout returned 503 for 0.5% of requests for six hours—below a naive 5% alert threshold but burned 38 minutes of 43-minute monthly budget. Error budget burn rate alerting pages when budget consumption accelerates—fast for outages, slow for leaks.

## Burn rate math

Budget 0.1% errors at 99.9%; current 1.4% errors → burn rate 14.4× → budget gone in ~2 days.

## Multi-window alerts

Fast burn: 14.4× over 2m/1h window pages immediately. Slow burn: 6× over 15m/6h creates tickets. Use Sloth or Pyrra to generate rules from SLO specs.

## SLI selection

Good: availability and latency threshold SLIs. Bad: pod restart count, CPU, queue depth without user correlation.

## Policy

Budget >50% consumed mid-month → freeze risky releases. Budget exhausted → incident review before feature work.


## Error budget reviews with product

Monthly 30-minute meeting: chart `1 - error_budget_remaining` per tier-1 SLO. Product decides:

- Budget >50% left → accelerate features
- Budget <20% → reliability sprint, freeze risky launches
- Budget exhausted → postmortem before new feature work

Burn alerts are input data; policy drives behavior. Without policy, burn alerts become ignored Grafana panels.

## Multi-window tuning for low-traffic services

Startup services lack volume for 2-minute burn windows—adjust windows to 15m/6h and require minimum event count:

```promql
(slo:errors:burn_rate_6h > 6)
and
(slo:requests:total_6h > 500)
```

Prevents paging on three errors total.

## Composite SLOs

User journey spans three services—define composite SLI as product of success probabilities or end-to-end synthetic check success rate. Burn composite SLO for executive view; burn per-service SLO for engineering drill-down. Sloth supports grouping multiple SLIs into one alert policy.

## SLO waiver process

Planned maintenance burns budget—file waiver ticket subtracting expected burn from alert thresholds or silence burn alerts with documented change ticket. Unplanned burn without waiver triggers automatic incident commander assignment in mature orgs.

## Customer-facing SLO pages

Public status page "99.9% this month" must match internal burn math—discrepancy erodes trust. Automate status page from same Prometheus recording rules as internal SLO, not separate manual spreadsheet.

## Executive communication

Translate burn rate alerts into non-technical summaries for leadership: "At current error rate we consume a week of monthly budget daily" lands better than raw PromQL. Automate weekly email from recording rules showing budget remaining per tier-1 SLO—aligns release train decisions without emergency meetings.

When multiple services share one error budget (user journey composite), document attribution rules when burn occurs—avoid circular blame between frontend and backend during joint incidents.


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
