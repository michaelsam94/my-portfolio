---
title: "Prometheus Federation and Hierarchical Scraping"
slug: "devops-prometheus-federation-hierarchy"
description: "Federate metrics from regional Prometheus to global without single point overload."
datePublished: "2026-06-01"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Platform"
keywords: "Prometheus federation"
faq:
  - q: "When should teams prioritize Prometheus Federation and Hierarchical Scraping?"
    a: "When multi-region or multi-cluster metrics need global view."
  - q: "What is the most common mistake with Prometheus federation?"
    a: "Federation without drop rules—duplicate series and cost blowup."
  - q: "Recording rules or raw PromQL in alerts?"
    a: "Pre-aggregate in recording rules when queries exceed five seconds or cardinality is high. Keep alert expressions readable — on-call reads them at 3 a.m."
  - q: "How long do you keep high-resolution metrics?"
    a: "Align retention with incident lookback and compliance — often 15–30 days hot, longer in object storage via remote write."
---
Global Prometheus OOM from scraping all targets directly. This post is about making prometheus federation and hierarchical scraping boring in the best way — predictable under load, auditable under review, and reversible under stress.

## What broke first on dashboards


Global Prometheus OOM from scraping all targets directly.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to federation without drop rules—duplicate series and cost blowup.

Prometheus federation was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move Prometheus federation into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```yaml
# Operational hook for Prometheus federation
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_prometheus_federation_hierarchy():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put Prometheus federation on the critical path for one tier-1 workflow and measure what it catches.

## Cardinality discipline

Recording rules and federation reduce query cost but can hide labels you need for drill-down. Document which labels are allowed on raw metrics vs aggregated series. Drop high-cardinality labels at ingest — do not rely on Grafana alone.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Operating Prometheus federation at scale

After the first successful deploy of prometheus federation and hierarchical scraping, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Prometheus federation settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Observability pipelines touch ingestion, serving, and finance. Document interfaces where Prometheus federation gates hand off to downstream owners so failures are not bounced without context.

## Further reading

- https://prometheus.io/docs/
- https://grafana.com/docs/tempo/latest/
