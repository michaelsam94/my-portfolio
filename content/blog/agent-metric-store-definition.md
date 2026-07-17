---
title: "AI Agents: Metric Store Definition"
slug: "agent-metric-store-definition"
description: "How to define agent metrics once in a metric store so eval dashboards, cost alerts, and product analytics stop disagreeing on what success means."
datePublished: "2025-03-11"
dateModified: "2025-03-11"
tags: ["AI", "Agent", "Metric"]
keywords: "metric store, semantic metrics, agent observability, dbt metrics, LLM eval definitions, single source of truth, agent KPIs"
faq:
  - q: "What belongs in a metric store versus a raw events table?"
    a: "Events capture what happened (tool calls, tokens, latency samples). The metric store captures how you aggregate those events into named, versioned KPIs with explicit grain, filters, and owners. Dashboards and alerts should reference metric names, not re-implement SQL in every repo."
  - q: "How do agent-specific metrics differ from web analytics metrics?"
    a: "Agent metrics usually combine retrieval quality, tool success, human override rate, and cost per resolved task. They are often session-scoped rather than page-scoped, and they need lineage to prompt versions and model IDs so regressions are attributable."
  - q: "When should we block a deploy if a metric definition changes?"
    a: "Block when the change is breaking: renamed metric, altered grain, or a filter that removes historical comparability. Non-breaking additive dimensions can ship with a minor version bump. Treat metric YAML like API schema—consumers depend on stable semantics."
  - q: "Can one metric store serve both product analytics and ML eval?"
    a: "Yes, if you define separate metric namespaces (product vs eval) with shared dimensions like tenant_id and agent_version. The failure mode is forcing one SQL definition to serve incompatible audiences; split metrics, share dimensions."
---
The incident started quietly. Finance opened a ticket because "cost per resolved ticket" jumped 40% week over week. Support's dashboard showed flat resolution rates. The agent team's LangSmith export said quality was up. Three teams, three numbers, one executive question—and nobody could explain the gap in under an hour.

The root cause was not model drift. It was metric drift. Each team had written its own SQL for "resolved," "cost," and "session." Same English words, different filters, different grains. That is the problem a metric store definition solves: one authoritative, versioned definition that downstream dashboards, alerts, eval pipelines, and agent orchestration code can reference without re-deriving semantics in every repository.

## Why agent stacks sprout duplicate metrics

Agent products emit noisy telemetry. A single user turn might produce embedding calls, retrieval hits, tool invocations, streaming tokens, and a human thumbs-down three minutes later. Without a metric store, each squad picks the slice they care about:

- Platform engineers track p95 latency and error codes.
- ML engineers track eval scores on golden sets.
- Product tracks task completion in the application database.
- Finance tracks invoice line items from the model provider.

All of these are legitimate. The failure mode is when someone stitches them together in a slide deck using column names that sound alike. `task_completed` in Postgres might mean "user clicked Done," while `task_resolved` in the warehouse might mean "agent emitted a terminal tool result with no escalation." Those are not the same event.

A metric store sits above raw tables and below dashboards. It answers: given our agreed business logic, what is the SQL (or equivalent) that computes `agent_cost_per_resolved_task` at daily grain for tenant X, and who owns it?

## Anatomy of a metric definition

Think of each metric as a small contract with five non-negotiable fields:

| Field | Question it answers |
|-------|---------------------|
| **Name** | Stable identifier used in code and alerts |
| **Grain** | One row per what? (session, turn, tenant-day) |
| **Measure** | Sum, rate, percentile, ratio—explicit |
| **Filters** | What counts and what is excluded |
| **Dimensions** | Safe group-bys (model, prompt version, plan tier) |

For agent workloads, also document **attribution lag**. Human feedback arrives late. If your metric mixes same-session labels with next-day corrections, your "accuracy rate" will move when backfills run—not when behavior changes.

Here is a minimal YAML-style definition you might check into git and validate in CI:

```yaml
# metrics/agent_resolved_task_rate.yaml
version: 2
owner: agent-platform@company.com
metric: agent_resolved_task_rate
description: >
  Share of agent sessions that reach a terminal success state without
  human handoff within 30 minutes of session start.
grain: session
type: ratio
numerator:
  sql: |
    count(distinct case
      when terminal_status = 'success'
       and handoff_at is null
      then session_id end)
denominator:
  sql: count(distinct session_id)
filters:
  - agent_version >= '2.4.0'
  - environment = 'production'
dimensions:
  - tenant_id
  - model_id
  - prompt_bundle_id
sla:
  freshness_hours: 6
  breaking_change_requires: platform-approval
```

The point is not YAML specifically—dbt MetricFlow, Transform, Looker's LookML, or an internal registry all work. The point is that the definition is **reviewable**, **diffable**, and **owned**.

## Wiring definitions into agent runtime

Definitions only matter if production code references them. Two patterns work well:

**Push metrics at the edge.** Instrument the agent orchestrator to emit pre-labeled counters that match store names (`agent_tool_failure_total{tool="calendar"}`). Cheap at query time, but you must keep label sets aligned with store dimensions.

**Pull metrics in the warehouse.** Land raw events, materialize facts, let the metric store compile definitions into scheduled queries. Better for ratios and late-arriving feedback, at the cost of freshness measured in hours.

Most teams hybridize: low-latency counters for paging, warehouse metrics for executive review. The metric store links them with documented reconciliation queries ("Prometheus counter X should approximate BigQuery metric Y within 5%").

Typed access from application code prevents string drift:

```typescript
// Generated from metric store registry — do not edit by hand
export const AgentMetrics = {
  resolvedTaskRate: {
    id: "agent_resolved_task_rate",
    version: 2,
    requiredDimensions: ["tenant_id", "model_id"] as const,
  },
  costPerSessionUsd: {
    id: "agent_cost_per_session_usd",
    version: 1,
    requiredDimensions: ["tenant_id", "model_id", "prompt_bundle_id"] as const,
  },
} as const;

type MetricEvent = {
  metricId: string;
  metricVersion: number;
  value: number;
  dimensions: Record<string, string>;
  observedAt: string;
};

export function emitMetric(event: MetricEvent): void {
  const spec = Object.values(AgentMetrics).find(
    (m) => m.id === event.metricId && m.version === event.metricVersion
  );
  if (!spec) throw new Error(`Unknown metric: ${event.metricId} v${event.metricVersion}`);
  for (const dim of spec.requiredDimensions) {
    if (!event.dimensions[dim]) {
      throw new Error(`Missing dimension ${dim} for ${event.metricId}`);
    }
  }
  statsd.gauge(event.metricId, event.value, event.dimensions);
}
```

When a data scientist adds a dimension in the warehouse but forgets the orchestrator, CI fails. That is desirable friction.

## Lineage: the hidden half of definitions

Agent metrics without lineage become forensic exercises. Every definition should declare upstream dependencies:

- Raw event tables (`agent_turns`, `tool_invocations`, `billing_usage`)
- Feature flags that gate behavior
- Eval datasets used for offline scores (distinct from production metrics but often confused)

Draw a simple DAG on paper before debating SQL. If `agent_quality_score` depends on `human_labels`, document label provenance and sampling bias. Product teams frequently compare offline eval spikes to production "quality" metrics that use a different label source—then chase ghosts.

```sql
-- Reconciliation query checked into repo: ops/agent_metric_reconciliation.sql
-- Compare streaming counter to warehouse ratio for prior day
with wh as (
  select tenant_id, metric_value as warehouse_rate
  from metric_store.agent_resolved_task_rate
  where metric_date = current_date - 1
),
rt as (
  select tenant_id,
         sum(resolved_sessions)::float / nullif(sum(total_sessions), 0) as realtime_rate
  from realtime.agent_session_counters
  where date_trunc('day', bucket) = current_date - 1
  group by 1
)
select coalesce(wh.tenant_id, rt.tenant_id) as tenant_id,
       warehouse_rate,
       realtime_rate,
       abs(warehouse_rate - realtime_rate) as delta
from wh
full outer join rt using (tenant_id)
where abs(warehouse_rate - realtime_rate) > 0.05;
```

Run this daily. Divergence within tolerance builds trust; silent divergence erodes it.

## Rollout playbook that actually sticks

Week one: pick three metrics that executives already argue about. Not twenty. Write definitions, assign owners, publish a one-page glossary in plain language ("Resolved means the user did not open a human chat within 30 minutes").

Week two: redirect existing dashboards to metric store IDs. Deprecate rogue SQL with lint rules in BI tools where possible.

Week three: tie deploy gates to metric freshness and definition version. If `prompt_bundle_id` is a dimension, prompt promotions must emit it consistently or the deploy fails.

Week four: run a guided incident drill. Change a filter in staging, show how downstream alerts shift, revert with a version bump. Teams remember drills more than policy docs.

Common failure: treating the metric store as a data team side project. Agent metric definitions need on-call rotation from platform engineering, not a quarterly OKR orphan.

## Closing the loop with eval and cost

Once definitions stabilize, agent teams can automate sanity checks:

- **Pre-release:** compare offline eval on golden tasks with production metric baselines by cohort.
- **Post-release:** canary on `agent_cost_per_resolved_task` and `handoff_rate`, not just error logs.
- **FinOps:** attribute spend to `model_id` and `prompt_bundle_id` dimensions so finance does not re-aggregate invoices manually.

The metric store is not glamour work. It is the difference between arguing about SQL in Slack and arguing about product behavior with shared numbers—which is at least a fair fight.

## Resources

- [dbt Labs: About MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow) — semantic layer and metric definitions over warehouse models
- [Transform: Metrics Framework](https://docs.transform.co/docs/metrics-framework) — YAML-centric metric definitions with governance hooks
- [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/specs/semconv/) — standard attribute names for traces and metrics at the edge
- [Google SRE: Monitoring distributed systems](https://sre.google/sre-book/monitoring-distributed-systems/) — choosing user-visible indicators over vanity counters
- [LangSmith evaluation docs](https://docs.smith.langchain.com/evaluation) — offline eval patterns that must stay separate from production metric definitions
