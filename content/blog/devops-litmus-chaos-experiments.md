---
title: "Litmus Chaos Experiments on Kubernetes"
slug: "devops-litmus-chaos-experiments"
description: "Run Litmus ChaosEngine experiments for pod, network, and IO faults."
datePublished: "2026-06-19"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Chaos Engineering"
  - "Kubernetes"
keywords: "Litmus, chaos experiments"
faq:
  - q: "When should teams prioritize Litmus Chaos Experiments on Kubernetes?"
    a: "Before peak season or after major architecture change."
  - q: "What is the most common mistake with Litmus?"
    a: "Chaos in prod without blast radius limits—customer-facing blast."
  - q: "How do we know Litmus Chaos Experiments on Kubernetes is working?"
    a: "Define a leading metric tied to Litmus health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---
First prod outage from untested dependency timeout—no chaos coverage. This post is about making litmus chaos experiments on kubernetes boring in the best way — predictable under load, auditable under review, and reversible under stress.

## What broke first on dashboards


First prod outage from untested dependency timeout—no chaos coverage.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to chaos in prod without blast radius limits—customer-facing blast.

Litmus was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move Litmus into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```python
# Operational hook for Litmus
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_litmus_chaos_experiments():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put Litmus on the critical path for one tier-1 workflow and measure what it catches.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where Litmus gates hand off to downstream owners so failures are not bounced without context.

## Operating Litmus at scale

After the first successful deploy of litmus chaos experiments on kubernetes, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Litmus settings with the on-call rotation — not only the primary author.

## Further reading

- https://opentelemetry.io/docs/
