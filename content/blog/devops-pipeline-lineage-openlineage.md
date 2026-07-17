---
title: "Pipeline Lineage with OpenLineage and Marquez"
slug: "devops-pipeline-lineage-openlineage"
description: "Emit OpenLineage events for column-level lineage and impact analysis."
datePublished: "2026-08-28"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Data Pipelines"
  - "Platform"
keywords: "OpenLineage, Marquez"
faq:
  - q: "When should teams prioritize Pipeline Lineage with OpenLineage and Marquez?"
    a: "When data mesh or many consumers depend on shared tables."
  - q: "What is the most common mistake with OpenLineage?"
    a: "Lineage without ownership tags—cannot notify affected teams."
  - q: "Should OpenLineage block deploy or only warn?"
    a: "Block promotion to production tables and downstream consumers that cannot tolerate silent corruption. Warn on staging and dev with the same suite so expectations stay aligned. Finance and ML feature tables should fail closed."
  - q: "How do you test OpenLineage without slowing every commit?"
    a: "Run lightweight expectations on samples in PR CI; run full-partition suites on schedule and before merge to main. Cache validation artifacts and parallelize by partition key."
---
If OpenLineage is not on your promote path today, you do not have pipeline lineage with openlineage and marquez — you have a checklist item.

## Scenario worth designing for


Breaking column rename—no downstream impact analysis, five dashboards broke.

## Hard constraints


Compliance, latency, and cost caps are constraints — not afterthoughts. Design for rollback and audit evidence from day one.

## Implementation walkthrough


Ship the smallest production slice of Pipeline Lineage with OpenLineage and Marquez: one pipeline, one cluster, or one namespace — with rollback documented before widening scope.

Automate the boring steps so on-call never hand-edits OpenLineage settings during an incident. GitOps, versioned checkpoints, and pinned module versions beat runbook heroics.

## How we validate before promote


Integration tests with production-shaped data volumes. Chaos or fault injection for dependency timeouts.

Replay one bad day of production traffic in staging before declaring OpenLineage done.

## Production hardening


Pin versions, restrict break-glass access, and align client timeouts with server queue delays.

Review on-call pages tied to this topic after every incident — even minor ones.

## Closing thought


Good pipeline lineage with openlineage and marquez work is invisible until it saves you from an outage, an audit finding, or a line item on the cloud bill.

## Reference configuration


```python
from openlineage.client.run import RunEvent, RunState
client.emit(RunEvent(
  eventType=RunState.COMPLETE,
  run=Run(runId=run_id, facets={"processing_engine": ...}),
  job=Job(namespace="prod", name="dbt.orders_daily"),
))
```

## Partition-level validation

Sample-only expectations miss full-partition violations — null keys on edge partitions, timezone-boundary duplicates, and late-arriving facts. Schedule full scans before promote and incremental expectations on every run. Store validation results as queryable tables so analysts see history, not only pass/fail in Slack.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Data Pipelines pipelines touch ingestion, serving, and finance. Document interfaces where OpenLineage gates hand off to downstream owners so failures are not bounced without context.

## Operating OpenLineage at scale

After the first successful deploy of pipeline lineage with openlineage and marquez, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of OpenLineage settings with the on-call rotation — not only the primary author.

## Further reading

- https://greatexpectations.io/
- https://docs.dagster.io/
- https://openlineage.io/
