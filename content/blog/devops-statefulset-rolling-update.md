---
title: "StatefulSet Rolling Update Strategies"
slug: "devops-statefulset-rolling-update"
description: "Manage StatefulSet partition updates, OnDelete strategy, and PVC retention."
datePublished: "2026-03-18"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Kubernetes"
  - "SRE"
keywords: "StatefulSet, rolling update"
faq:
  - q: "When should teams prioritize StatefulSet Rolling Update Strategies?"
    a: "For stateful tiers before first in-place version upgrade."
  - q: "What is the most common mistake with StatefulSet?"
    a: "Deleting StatefulSet with wrong PVC retention policy loses data."
  - q: "Namespace-scoped or cluster-wide?"
    a: "Security baselines cluster-wide; workload-specific tuning per namespace. Document exceptions with expiry dates."
  - q: "What signal pages first?"
    a: "User-visible error budget burn or scheduling failures — not average CPU across the cluster."
---
Rolling update restarted all Kafka brokers simultaneously despite partition setting.

## Why this shows up under real load


Rolling update restarted all Kafka brokers simultaneously despite partition setting. That is the difference between demo-grade StatefulSet and production-grade StatefulSet.

Prioritize StatefulSet Rolling Update Strategies for stateful tiers before first in-place version upgrade.

## Decision guide for platform teams


| Situation | Do | Avoid |
|-----------|-----|-------|
| Tier-1 downstream | Fail closed on StatefulSet | Warn-only gates |
| Staging parity | Same suite as prod, smaller data | Different expectations |
| Incident response | One-click rollback path | Manual console edits |

## Configuration patterns that survived review


Patterns we kept for StatefulSet:

## Rollout without blocking the business


Roll out in waves: internal consumers, 10% traffic or partitions, soak 48h, then full promote. Keep previous artifact version hot-swappable for one release cycle.

Pair rollout with shadow validation where possible — run new checks without blocking, compare results, then enforce.

## Monitoring and on-call signals


Dashboards for StatefulSet belong in the same folder on-call opens first. Link runbooks from alert annotations — not a wiki nobody trusts.

Delete alerts that never fire; add thresholds that would have caught your last incident.

## Lessons from production


StatefulSet Rolling Update Strategies is load-bearing once traffic and teams scale. Treat changes like any tier-1 deploy: feature flags, observability, rollback.

Document org-specific decisions — CIDRs, cluster names, approval gates — in internal docs that stay current.

## Reference configuration


```yaml
# Operational hook for StatefulSet
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_statefulset_rolling_update():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Upgrade coordination

Cluster upgrades, node drains, and workload rollouts interact. PodDisruptionBudgets, PriorityClasses, and native sidecars change termination order — test rollouts on production-shaped replica counts and volume attach/detach timing.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Kubernetes pipelines touch ingestion, serving, and finance. Document interfaces where StatefulSet gates hand off to downstream owners so failures are not bounced without context.

## Operating StatefulSet at scale

After the first successful deploy of statefulset rolling update strategies, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of StatefulSet settings with the on-call rotation — not only the primary author.

## Further reading

- https://kubernetes.io/docs/home/
- https://kubernetes.io/docs/concepts/scheduling-eviction/pod-priority-preemption/
