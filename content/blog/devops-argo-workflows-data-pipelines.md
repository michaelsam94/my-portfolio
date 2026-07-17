---
title: "Argo Workflows for Data and ML Pipelines"
slug: "devops-argo-workflows-data-pipelines"
description: "Run batch and ML pipelines with Argo Workflows on Kubernetes."
datePublished: "2026-05-03"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "CI/CD"
  - "MLOps"
keywords: "Argo Workflows, data pipelines"
faq:
  - q: "When should teams prioritize Argo Workflows for Data and ML Pipelines?"
    a: "When migrating batch/ML jobs to Kubernetes-native orchestration."
  - q: "What is the most common mistake with Argo Workflows?"
    a: "Workflow templates without retry limits—runaway pod creation."
  - q: "Should Argo Workflows block deploy or only warn?"
    a: "Block promotion to production tables and downstream consumers that cannot tolerate silent corruption. Warn on staging and dev with the same suite so expectations stay aligned. Finance and ML feature tables should fail closed."
  - q: "How do you test Argo Workflows without slowing every commit?"
    a: "Run lightweight expectations on samples in PR CI; run full-partition suites on schedule and before merge to main. Cache validation artifacts and parallelize by partition key."
---
Cron-based ML training on Jenkins agent ran out of disk silently. This post is about making argo workflows for data and ml pipelines boring in the best way — predictable under load, auditable under review, and reversible under stress.

## Why this shows up under real load


Cron-based ML training on Jenkins agent ran out of disk silently. That is the difference between demo-grade Argo Workflows and production-grade Argo Workflows.

Prioritize Argo Workflows for Data and ML Pipelines when migrating batch/ml jobs to kubernetes-native orchestration.

## Decision guide for platform teams


| Situation | Do | Avoid |
|-----------|-----|-------|
| Tier-1 downstream | Fail closed on Argo Workflows | Warn-only gates |
| Staging parity | Same suite as prod, smaller data | Different expectations |
| Incident response | One-click rollback path | Manual console edits |

## Configuration patterns that survived review


Patterns we kept for Argo Workflows:

## Rollout without blocking the business


Roll out in waves: internal consumers, 10% traffic or partitions, soak 48h, then full promote. Keep previous artifact version hot-swappable for one release cycle.

Pair rollout with shadow validation where possible — run new checks without blocking, compare results, then enforce.

## Monitoring and on-call signals


Dashboards for Argo Workflows belong in the same folder on-call opens first. Link runbooks from alert annotations — not a wiki nobody trusts.

Delete alerts that never fire; add thresholds that would have caught your last incident.

## Lessons from production


Argo Workflows for Data and ML Pipelines is load-bearing once traffic and teams scale. Treat changes like any tier-1 deploy: feature flags, observability, rollback.

Document org-specific decisions — CIDRs, cluster names, approval gates — in internal docs that stay current.

## Reference configuration


```python
# Operational hook for Argo Workflows
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_argo_workflows_data_pipelines():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Partition-level validation

Sample-only expectations miss full-partition violations — null keys on edge partitions, timezone-boundary duplicates, and late-arriving facts. Schedule full scans before promote and incremental expectations on every run. Store validation results as queryable tables so analysts see history, not only pass/fail in Slack.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

CI/CD pipelines touch ingestion, serving, and finance. Document interfaces where Argo Workflows gates hand off to downstream owners so failures are not bounced without context.

## Operating Argo Workflows at scale

After the first successful deploy of argo workflows for data and ml pipelines, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of Argo Workflows settings with the on-call rotation — not only the primary author.

## Further reading

- https://greatexpectations.io/
- https://docs.dagster.io/
- https://openlineage.io/
