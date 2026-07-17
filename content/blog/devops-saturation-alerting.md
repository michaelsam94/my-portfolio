---
title: "Saturation Alerting Before Hard Limits"
slug: "devops-saturation-alerting"
description: "Alert on saturation signals: CPU throttling, disk IO wait, connection pools."
datePublished: "2026-07-08"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Capacity Planning"
  - "Observability"
keywords: "saturation alerting"
faq:
  - q: "When should teams prioritize Saturation Alerting Before Hard Limits?"
    a: "When hard limits cause user-visible failures without warning."
  - q: "What is the most common mistake with saturation alerts?"
    a: "Saturation alerts on averages—miss hot pods and nodes."
  - q: "Recording rules or raw PromQL in alerts?"
    a: "Pre-aggregate in recording rules when queries exceed five seconds or cardinality is high. Keep alert expressions readable — on-call reads them at 3 a.m."
  - q: "How long do you keep high-resolution metrics?"
    a: "Align retention with incident lookback and compliance — often 15–30 days hot, longer in object storage via remote write."
---
Alert only on OOM—no warning as memory climbed 90→99%. This post is about making saturation alerting before hard limits boring in the best way — predictable under load, auditable under review, and reversible under stress.

## What changes when you leave the tutorial


Alert on saturation signals: CPU throttling, disk IO wait, connection pools.

Production saturation alerting before hard limits fails on retries, partial outages, and human process gaps — not on the happy-path tutorial.

## Design constraints you cannot ignore


Prefer defaults that fail closed: deny, queue, or degrade safely rather than return silently wrong data.

Document who may change saturation alerts in production, how rollback works, and which environments are allowed to diverge.

## Step-by-step in production order


1. Inventory consumers and SLAs. 2. Implement enforcement on the write/promote path. 3. Add observability. 4. Drill failure modes. 5. Expand scope.

Validate each step with someone who did not write the original saturation alerts config — fresh eyes catch assumptions.

## Edge cases that bypass happy-path tests


Edge cases: late-arriving data, duplicate events, schema drift mid-run, credential rotation during job execution, and traffic spikes during deploy.

For each, document drop vs retry vs dead-letter vs fail-closed — and test it.

## Observability hooks


Structured logs with run_id, partition, and validation outcome. Metrics with bounded labels — never high-cardinality user IDs on Prometheus.

Traces across orchestrator, worker, and warehouse when requests cross team boundaries.

## Summary


Saturation Alerting Before Hard Limits earns its keep when it prevents silent corruption, unsafe deploys, or unbounded cost — not when it decorates a architecture diagram.

## Reference configuration


```yaml
# Operational hook for saturation alerts
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_saturation_alerting():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Cardinality discipline

Recording rules and federation reduce query cost but can hide labels you need for drill-down. Document which labels are allowed on raw metrics vs aggregated series. Drop high-cardinality labels at ingest — do not rely on Grafana alone.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Operating saturation alerts at scale

After the first successful deploy of saturation alerting before hard limits, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of saturation alerts settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Capacity Planning pipelines touch ingestion, serving, and finance. Document interfaces where saturation alerts gates hand off to downstream owners so failures are not bounced without context.

## Further reading

- https://prometheus.io/docs/
- https://grafana.com/docs/tempo/latest/
