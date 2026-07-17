---
title: "CronJob Timezone and DST-Safe Scheduling"
slug: "devops-cronjob-timezone-dst"
description: "Run CronJobs with correct timezones and avoid DST duplicate/skipped runs."
datePublished: "2026-03-16"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "SRE"
keywords: "CronJob, timezone, DST"
faq:
  - q: "When should teams prioritize CronJob Timezone and DST-Safe Scheduling?"
    a: "For finance, billing, or compliance jobs tied to local midnight."
  - q: "What is the most common mistake with CronJob timeZone?"
    a: "UTC-only CronJobs that ignore business timezone requirements."
  - q: "How do we know CronJob Timezone and DST-Safe Scheduling is working?"
    a: "Define a leading metric tied to CronJob timeZone health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---
Billing CronJob ran twice on DST fall-back—double charges until rollback.

## What broke first on dashboards


Billing CronJob ran twice on DST fall-back—double charges until rollback.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to utc-only cronjobs that ignore business timezone requirements.

CronJob timeZone was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move CronJob timeZone into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```python
# Operational hook for CronJob timeZone
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_cronjob_timezone_dst():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put CronJob timeZone on the critical path for one tier-1 workflow and measure what it catches.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where CronJob timeZone gates hand off to downstream owners so failures are not bounced without context.

## Operating CronJob timeZone at scale

After the first successful deploy of cronjob timezone and dst-safe scheduling, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of CronJob timeZone settings with the on-call rotation — not only the primary author.

## Further reading

- https://opentelemetry.io/docs/
