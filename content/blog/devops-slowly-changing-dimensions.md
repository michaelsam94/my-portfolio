---
title: "Slowly Changing Dimensions Type 1 vs Type 2"
slug: "devops-slowly-changing-dimensions"
description: "Implement SCD patterns with effective dating and surrogate keys."
datePublished: "2026-09-22"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Warehouse"
  - "Data Engineering"
keywords: "SCD Type 2"
faq:
  - q: "When should teams prioritize Slowly Changing Dimensions Type 1 vs Type 2?"
    a: "Dimensions where history matters for reporting or compliance."
  - q: "What is the most common mistake with SCD patterns?"
    a: "Type 2 without end-date maintenance—multiple current rows."
  - q: "Who owns cost vs correctness tradeoffs?"
    a: "Data platform owns defaults and guardrails; domain teams own business SLAs. Document who approves skewed joins, spot nodes, or warehouse upsizes."
  - q: "How do you roll back a bad transform?"
    a: "Versioned tables, idempotent writes, and replay from known-good watermark. Never overwrite production partitions without snapshot or time travel."
---
Customer address history lost—Type 1 overwrite on dimension.

## Scenario worth designing for


Customer address history lost—Type 1 overwrite on dimension.

## Hard constraints


Compliance, latency, and cost caps are constraints — not afterthoughts. Design for rollback and audit evidence from day one.

## Implementation walkthrough


Ship the smallest production slice of Slowly Changing Dimensions Type 1 vs Type 2: one pipeline, one cluster, or one namespace — with rollback documented before widening scope.

Automate the boring steps so on-call never hand-edits SCD patterns settings during an incident. GitOps, versioned checkpoints, and pinned module versions beat runbook heroics.

## How we validate before promote


Integration tests with production-shaped data volumes. Chaos or fault injection for dependency timeouts.

Replay one bad day of production traffic in staging before declaring SCD patterns done.

## Production hardening


Pin versions, restrict break-glass access, and align client timeouts with server queue delays.

Review on-call pages tied to this topic after every incident — even minor ones.

## Closing thought


Good slowly changing dimensions type 1 vs type 2 work is invisible until it saves you from an outage, an audit finding, or a line item on the cloud bill.

## Reference configuration


```python
# Operational hook for SCD patterns
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_slowly_changing_dimensions():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Skew, spill, and warehouse economics

Data jobs fail quietly on skew before they fail loudly on OOM. Watch shuffle bytes, task duration variance, and slot/warehouse credit burn. Right-size executors and distribution keys from production stats — not from notebook samples.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Warehouse Modeling pipelines touch ingestion, serving, and finance. Document interfaces where SCD patterns gates hand off to downstream owners so failures are not bounced without context.

## Operating SCD patterns at scale

After the first successful deploy of slowly changing dimensions type 1 vs type 2, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of SCD patterns settings with the on-call rotation — not only the primary author.

## Further reading

- https://spark.apache.org/docs/latest/
- https://docs.delta.io/
- https://docs.snowflake.com/
