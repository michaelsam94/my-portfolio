---
title: "DaemonSet Upgrade and Surge Patterns"
slug: "devops-daemonset-upgrade-strategy"
description: "Upgrade DaemonSet agents with maxUnavailable tuning."
datePublished: "2026-03-19"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "Platform"
keywords: "DaemonSet, rolling update"
faq:
  - q: "When should teams prioritize DaemonSet Upgrade and Surge Patterns?"
    a: "Before upgrading CNI, log, or security DaemonSets fleet-wide."
  - q: "What is the most common mistake with DaemonSet?"
    a: "maxUnavailable 100% on single-replica-per-node DaemonSets."
  - q: "How do we know DaemonSet Upgrade and Surge Patterns is working?"
    a: "Define a leading metric tied to DaemonSet health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---

Log agent upgrade left 30% of nodes on old version—blind spot during incident.

## What broke first on dashboards


Log agent upgrade left 30% of nodes on old version—blind spot during incident.

On-call sees green infrastructure metrics while business KPIs diverge — classic sign the gate is not on the critical path.

## Root cause — not the obvious answer


Root cause tied to maxunavailable 100% on single-replica-per-node daemonsets.

DaemonSet was treated as a one-time setup task instead of an operational contract with owners and SLOs.

## Fix path we kept


Move DaemonSet into the promote path with explicit failure semantics. Add partition-level coverage, not sample-only checks.

Add CI enforcement so misconfigurations cannot merge.

## Reference configuration


```python
# Operational hook for DaemonSet
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_daemonset_upgrade_strategy():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Day-two ownership


Assign a named owner team, review thresholds quarterly, and rehearse rollback.

New hires should execute a safe canary using only the runbook within their first week.

## What to do this week


If you only do one thing this week: put DaemonSet on the critical path for one tier-1 workflow and measure what it catches.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Operating DaemonSet at scale

After the first successful deploy of daemonset upgrade and surge patterns, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of DaemonSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where DaemonSet gates hand off to downstream owners so failures are not bounced without context.

## Further reading

- https://opentelemetry.io/docs/
