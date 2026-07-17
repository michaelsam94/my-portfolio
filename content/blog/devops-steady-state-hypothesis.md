---
title: "Steady-State Hypotheses for Chaos Experiments"
slug: "devops-steady-state-hypothesis"
description: "Define measurable steady-state before and during chaos experiments."
datePublished: "2026-06-27"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Chaos Engineering"
  - "SRE"
keywords: "steady-state hypothesis"
faq:
  - q: "When should teams prioritize Steady-State Hypotheses for Chaos Experiments?"
    a: "Every chaos experiment design phase."
  - q: "What is the most common mistake with steady-state metrics?"
    a: "Hypothesis uses vanity metrics—not user-visible SLIs."
  - q: "Game day in prod or staging?"
    a: "Start staging with production-shaped traffic. Prod experiments need blast-radius limits, executive comms, and automated stop when error budget burns."
  - q: "How do we know Steady-State Hypotheses for Chaos Experiments is working?"
    a: "Define a leading metric tied to steady-state metrics health and a lagging metric tied to incidents or audit findings. If only lagging metrics exist, you discover problems after customers do."
---
Chaos experiment stopped early—no baseline metric defined. This post is about making steady-state hypotheses for chaos experiments boring in the best way — predictable under load, auditable under review, and reversible under stress.

## The incident that forced a redesign


Chaos experiment stopped early—no baseline metric defined.

The post-mortem was not about steady-state metrics being unknown — it was about steady-state metrics sitting adjacent to the critical path. Define measurable steady-state before and during chaos experiments. Teams had a green CI badge and a broken invariant in production.

## Architecture that matches how data actually flows


A durable steady-state hypotheses for chaos experiments design names three boundaries: **ingress** (who triggers work), **enforcement** (where invariants are checked), and **evidence** (what you log for audits and replay).

For Chaos Engineering workloads, keep enforcement as close to the write path as possible. Advisory checks that run only in notebooks do not count as gates.

## Implementation walkthrough


Ship the smallest production slice of Steady-State Hypotheses for Chaos Experiments: one pipeline, one cluster, or one namespace — with rollback documented before widening scope.

Automate the boring steps so on-call never hand-edits steady-state metrics settings during an incident. GitOps, versioned checkpoints, and pinned module versions beat runbook heroics.

## Day-two operations


Day-two steady-state hypotheses for chaos experiments work is ownership rotation, capacity headroom, and alert hygiene. Page on symptoms customers feel — SLA misses, queue age, failed reconciliations — not vanity pod counts.

Run quarterly drills: credential expiry, dependency slow-down, partial region loss. Update internal docs with what broke, not generic vendor copy.

## Failure modes worth rehearsing


The recurring failure: Hypothesis uses vanity metrics—not user-visible SLIs. Bake detection into CI, admission, or plan-time policy so the mistake fails before merge.

Secondary failures include retry storms, silent partial writes, and dashboards that stay green while downstream consumers read corrupt partitions.

## Metrics and alerts that catch regressions early


Track leading indicators for steady-state metrics: validation pass rate, queue lag, reconciliation errors, error budget burn. Lagging indicators: incidents, audit findings, invoice surprises.

Slice metrics by environment and tenant during rollout — global averages hide bad canaries.

## Reference configuration


```python
# Operational hook for steady-state metrics
@task(retries=3, retry_delay=timedelta(minutes=5))
def run_steady_state_hypothesis():
    validate_preconditions()
    execute()
    emit_lineage(run_id=ctx.run_id)
```

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Handoff to adjacent teams

Chaos Engineering pipelines touch ingestion, serving, and finance. Document interfaces where steady-state metrics gates hand off to downstream owners so failures are not bounced without context.

## Operating steady-state metrics at scale

After the first successful deploy of steady-state hypotheses for chaos experiments, most incidents trace to assumptions that stopped being true: traffic doubled, schemas drifted, or credentials rotated without updating consumers. Schedule a quarterly review of steady-state metrics settings with the on-call rotation — not only the primary author.

## Further reading

- https://opentelemetry.io/docs/
