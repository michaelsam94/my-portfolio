---
title: "AI Agents: Progressive Delivery Metrics"
slug: "agent-progressive-delivery-metrics"
description: "Which metrics should gate a canary promotion when you ship agent prompt changes, retrieval configs, or model swaps—and which ones look healthy while quality silently regresses."
datePublished: "2026-03-09"
dateModified: "2026-03-09"
tags: ["AI", "Agent", "Progressive"]
keywords: "progressive delivery metrics, canary analysis, flagger, error budget, agent rollout, golden signals, statistical canary gates"
faq:
  - q: "Why isn't error rate enough to promote an agent canary?"
    a: "HTTP 200 with a worse answer still counts as success. Agent regressions often show up in tool failure rate, human override rate, retrieval empty-hit ratio, or cost per resolved task before traditional error metrics move. A canary gate needs at least one quality proxy aligned to user outcomes."
  - q: "How long should a canary bake before promotion?"
    a: "Long enough to capture diurnal traffic and enough sessions per cohort—often 30–120 minutes for high-traffic services, longer for B2B tenants with sparse usage. Agent workloads need minimum sample sizes on session-level metrics; promoting after 50 requests when your SLO is defined on 10k sessions/day yields false confidence."
  - q: "What is a false-positive rollback in progressive delivery?"
    a: "Automated rollback triggered by noise: a single noisy tenant, an A/B cohort imbalance, or a metric lacking baseline variance estimates. Mitigate with multi-window burn rates, minimum sample thresholds, and segmentation (exclude internal tenants from gates)."
  - q: "Should eval harness scores block production rollouts?"
    a: "Use offline eval as a pre-canary gate, not a substitute for production metrics. Online canaries catch retrieval drift, tool auth expiry, and tenant-specific document corpora that golden sets miss. Pair both: eval blocks obvious regressions; production metrics validate real traffic."
---
The Slack message arrived eleven minutes into a canary: "Rollback complete — p99 latency green, error rate flat." By afternoon, support volume spiked. Users were not hitting 500s; they were hitting a new prompt version that confidently misread date formats in uploaded invoices, triggering wrong tool arguments. The progressive delivery controller had done exactly what we told it to do. We just told it to watch the wrong numbers.

Progressive delivery without metrics tuned to your product is traffic shifting with extra steps. For agent services, the gap between "healthy infrastructure" and "healthy outcomes" is wider than for CRUD APIs because success is semantic, not syntactic. This article is about the measurements that should drive promotion, pause, and rollback when you ship agent changes—not the generic RED dashboard every template copies.

## The promotion decision in one picture

Think of progressive delivery as a state machine fed by measurements:

```
Deploy canary (5% traffic)
        │
        ▼
   Collect metrics ──► Compare canary vs baseline
        │                      │
        │                      ├── Within thresholds → increase weight
        │                      ├── Inconclusive (low N) → hold
        │                      └── Breach → rollback
        ▼
   Repeat until 100% or abort
```

The controller (Flagger, Argo Rollouts, Spinnaker, homegrown) is only as good as the PromQL or Datadog queries you plug in. Agent teams need queries that encode business meaning, not just pod restarts.

## Golden signals, agent edition

Classic golden signals—latency, traffic, errors, saturation—still matter. They tell you the new container is not melting. Add **outcome-adjacent** signals before you wire automation:

| Signal | What it catches | Example query shape |
|--------|-----------------|---------------------|
| Tool error rate | Broken integrations, schema drift | `tool_errors / tool_invocations` by version |
| Empty retrieval rate | Index lag, bad embeddings deploy | `retrieval_hits==0 / retrieval_queries` |
| Human override rate | Wrong answers users reject | `thumbs_down + manual_edits / sessions` |
| Cost per successful task | Runaway token usage | `sum(tokens)*price / tasks_completed` |
| Time-to-first-token p95 | Streaming regressions | histogram quantile on stream start |

Pick two infrastructure signals and two outcome signals minimum for automated promotion. Infrastructure alone optimizes for the invoice-date incident.

## Metrics that lie during canaries

**Global averages hide cohort skew.** If canary traffic routes by user ID hash but enterprise tenants cluster in bucket 3, your 5% slice might be 40% of revenue. Segment gates by `tenant_tier` or run canaries per cohort.

**Low volume triggers false stability.** Agent sessions are long-tailed. A metric like "hallucination reports" with three events in the bake window has unbounded relative error. Enforce `min_samples`:

```yaml
# Flagger MetricTemplate sketch — agent tool error gate
apiVersion: flagger.app/v1beta1
kind: MetricTemplate
metadata:
  name: agent-tool-error-rate
spec:
  provider:
    type: prometheus
    address: http://prometheus:9090
  query: |
    sum(rate(agent_tool_errors_total{version="{{ version }}"}[5m]))
    /
    sum(rate(agent_tool_invocations_total{version="{{ version }}"}[5m]))
```

Pair that rate query with a companion check on `sum(increase(agent_tool_invocations_total[30m])) > 200` before allowing promotion.

**Concurrent experiments pollute baselines.** Shipping a retrieval model canary while a separate feature flag changes UI copy confounds override-rate metrics. Maintain an experiment registry; block overlapping changes on shared outcome metrics.

**SLO burn without directionality.** A canary that is *better* than baseline can still mask rising variance. Track **delta** (canary minus stable) with confidence intervals, not just absolute burn.

## Building a promotion function that scales with you

Start manual, automate second. Week one: a dashboard panel with side-by-side stable vs canary for six charts. Week four: encode thresholds in YAML.

```typescript
// Rollout gate evaluator — pure logic, easy to unit test
type CohortMetrics = {
  toolErrorRate: number;
  emptyRetrievalRate: number;
  overrideRate: number;
  p95LatencyMs: number;
  sessionCount: number;
};

type GateThresholds = {
  maxToolErrorDelta: number;      // e.g. 0.02 = +2 percentage points
  maxOverrideDelta: number;
  maxLatencyDeltaMs: number;
  minSessions: number;
};

export function evaluateCanaryPromotion(
  stable: CohortMetrics,
  canary: CohortMetrics,
  thresholds: GateThresholds,
): "promote" | "hold" | "rollback" {
  if (canary.sessionCount < thresholds.minSessions) return "hold";

  if (canary.toolErrorRate - stable.toolErrorRate > thresholds.maxToolErrorDelta) {
    return "rollback";
  }
  if (canary.overrideRate - stable.overrideRate > thresholds.maxOverrideDelta) {
    return "rollback";
  }
  if (canary.p95LatencyMs - stable.p95LatencyMs > thresholds.maxLatencyDeltaMs) {
    return "rollback";
  }
  return "promote";
}
```

Keep business rules in testable functions; keep PromQL in metric templates. Mixing them produces runbooks nobody trusts.

For **multi-step progressive delivery** (5% → 25% → 50% → 100%), tighten thresholds at higher weights. A +1% override delta at 5% might be noise; at 50% it is revenue.

## Agent-specific dimensions to label every metric

Without labels, canaries cannot compare apples to apples. Standardize:

- `agent_version` or `prompt_hash`
- `model_id` (including retrieval embedding model)
- `deployment_id` / `rollout_id`
- `tenant_id` (for segmentation, not always in high-cardinality alerts)

Emit these from the orchestration layer, not from ad hoc log parsing later. Retrofitting labels after an incident is painful.

Trace exemplars help: link a spike in `tool_error_rate` to three failing traces with the same `tool_name=calendar.create`. That shortens rollback postmortems from hours to minutes.

## Wiring metrics into CI before production

Progressive delivery is not only a prod concern. Block merges when offline checks fail, then use online metrics as confirmation:

1. **Pre-merge**: golden eval set regression > 2% on primary metric → fail CI.
2. **Post-deploy canary**: online tool error delta → auto rollback.
3. **Post-promotion**: 24-hour burn rate alert on cost per task.

```bash
# Example: compare eval artifact from main vs branch before deploy
python scripts/compare_eval.py \
  --baseline artifacts/eval-main.json \
  --candidate artifacts/eval-branch.json \
  --max-regression 0.02 \
  --primary-metric task_success_rate
```

The script exits non-zero; the deploy pipeline never reaches the cluster. Canary metrics then guard against surprises your golden set missed.

## A dashboard layout that on-call actually uses

Row 1: **Traffic split** (stable vs canary RPS, session count).  
Row 2: **Infrastructure** (p95 latency, 5xx rate, CPU).  
Row 3: **Agent outcomes** (tool errors, empty retrieval, overrides).  
Row 4: **Economics** (tokens per session, cost estimate).  
Row 5: **Rollout state** (weight, time in stage, last gate decision).

Annotate deploy timestamps on every panel. On-call engineers should not correlate by memory.

## When to roll back manually despite green metrics

Automate most rollbacks, but keep human override for:

- Legal or safety reports referencing the new version
- Sudden spikes in a metric you forgot to gate (add it tomorrow)
- Qualitative feedback from a design partner tenant in the canary slice

Progressive delivery metrics are a living list. Each incident should add one query or one label, not one emergency policy exception.

## Statistical rigor without a PhD

You do not need Bayesian A/B platforms on day one, but avoid eyeballing two line charts. Practical middle ground:

**Fixed-horizon comparison.** Decide bake duration before deploy (e.g. 45 minutes). Compare canary vs stable only at the end. Peeking early invites false rollbacks.

**Relative uplift caps.** Define rollback when canary exceeds stable by X% **relative** for rate metrics: `(canary - stable) / stable > 0.15` on override rate, not absolute 0.5% which means different things at low base rates.

**Sequential sampling guard.** If your controller supports it, require minimum exposures:

```promql
sum(increase(agent_sessions_total{variant="canary"}[45m])) >= 500
```

Below 500 sessions, gate returns `hold` regardless of deltas—prevents a single enterprise tenant from dominating the decision.

**Holm-Bonferroni for multiple metrics.** Checking six metrics at α=0.05 inflates false positives. Either prioritize one primary metric for automation and treat others as advisory, or adjust alpha downward when gating on multiple queries simultaneously.

Document which metrics are **blocking** versus **informational** in the Rollout CRD README. On-call should not debate philosophy during a rollback.

## Post-rollout learning loop

After every automated rollback, capture:

1. Which query fired
2. Canary and stable values at decision time
3. Session count and top tenant contributors
4. Whether manual investigation confirmed a real regression

Feed confirmed regressions into offline eval sets. Feed false positives into threshold tuning tickets. Progressive delivery metrics mature through this loop—not through copying another team's PromQL verbatim.

## Resources

- [Flagger — Canary CRD and metric templates](https://docs.flager.app/usage/how-it-works/)
- [Argo Rollouts — Analysis runs](https://argo-rollouts.readthedocs.io/en/stable/features/analysis/)
- [Google SRE — Alerting on SLOs](https://sre.google/workbook/alerting-on-slos/)
- [Prometheus histograms and quantiles](https://prometheus.io/docs/practices/histograms/)
- [LaunchDarkly — Release Guardians (metric-driven flags)](https://docs.launchdarkly.com/home/releases/release-guardians)
