---
title: "AI Agents: Fact Table Grain Design"
slug: "agent-fact-table-grain-design"
description: "Fact table grain for agent analytics — one row per what, transaction vs snapshot facts, degenerate dimensions, aggregation traps, and designing warehouse tables that match how you measure LLM sessions and tool calls."
datePublished: "2025-02-25"
dateModified: "2025-02-25"
tags: ["AI", "Agent", "Fact"]
keywords: "fact table grain, dimensional modeling, star schema, agent analytics, data warehouse, LLM metrics, Kimball"
faq:
  - q: "What does grain mean for a fact table?"
    a: "Grain is the definition of one row — the atomic business event you measure. 'One row per agent session' vs 'one row per tool invocation' are different grains. Every metric in the fact table must be meaningful at that grain. Mixing grains in one fact table double-counts revenue, tokens, and conversions."
  - q: "Should agent token usage live in the same fact table as session outcomes?"
    a: "Usually no. Token usage is often captured per LLM API call (finer grain); session outcomes (resolved, escalated) belong at session grain. Model a call-level fact table and a session-level fact table, then join or roll up through conformed dimensions (session_id, user_id, date). Avoid stuffing call-level sums into session rows without clear aggregation rules."
  - q: "What is a degenerate dimension?"
    a: "A dimension attribute stored directly in the fact table without a separate dimension table — typically high-cardinality IDs like order_number, ticket_id, or agent_session_id. Use degenerate dimensions for identifiers you filter on but do not need to hierarchically roll up."
  - q: "How do snapshot facts apply to agent monitoring?"
    a: "Snapshot facts capture periodic state — e.g., one row per queue per day for open ticket count, or one row per agent deployment per hour for model version in serving. They complement transaction facts (each tool call) when you need point-in-time inventory metrics rather than event sums."
---
Finance asked for cost per resolved ticket. Product wanted tool success rate by model version. Data engineering built `fct_agent_events` with one row per… something. Session IDs duplicated across rows. Token counts did not sum to the invoice. Dashboards showed 140% resolution rate.

The root cause was grain — never declared, never enforced. Fact table grain design is the foundation of trustworthy agent analytics. Get it wrong and every downstream metric, experiment, and executive dashboard inherits the lie.

## Declare grain in plain English first

Before SQL, write the sentence:

> "One row in `fct_agent_session` represents **one completed agent conversation** identified by `session_id`, including aggregated measures from all LLM calls and tool invocations within that session."

Or:

> "One row in `fct_agent_llm_call` represents **one request/response pair** to the model API, including token counts and latency for that call only."

If you cannot finish the sentence without "and sometimes," split the fact table.

| Fact table | Grain | Example measures |
|------------|-------|------------------|
| `fct_agent_session` | 1 row / session | resolved_flag, duration_sec, total_tokens, escalation_flag |
| `fct_agent_llm_call` | 1 row / API call | prompt_tokens, completion_tokens, latency_ms, model_version |
| `fct_agent_tool_invocation` | 1 row / tool call | success_flag, latency_ms, error_code |
| `fct_agent_queue_snapshot` | 1 row / queue / day | open_sessions, p95_wait_sec |

Kimball's rule: **choose the lowest grain you need for the finest analysis, then aggregate up.** Do not cram call-level and session-level events into one table because JOINs feel expensive — duplicate dimensions correctly instead.

## Transaction facts for agent events

Transaction facts record business events at a point in time:

```sql
CREATE TABLE fct_agent_llm_call (
    llm_call_sk          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    call_id              VARCHAR(64) NOT NULL UNIQUE,  -- degenerate dimension
    session_sk           BIGINT NOT NULL REFERENCES dim_session(session_sk),
    user_sk              BIGINT NOT NULL REFERENCES dim_user(user_sk),
    model_sk             BIGINT NOT NULL REFERENCES dim_model(model_sk),
    date_sk              INT NOT NULL REFERENCES dim_date(date_sk),
    call_ts              TIMESTAMPTZ NOT NULL,

    -- facts at call grain only
    prompt_tokens        INT NOT NULL,
    completion_tokens    INT NOT NULL,
    total_tokens         INT NOT NULL,
    latency_ms           INT NOT NULL,
    cost_usd             NUMERIC(12, 6) NOT NULL,

    CONSTRAINT grain_one_row_per_call UNIQUE (call_id)
);

COMMENT ON TABLE fct_agent_llm_call IS
    'Grain: one row per LLM API request/response (call_id).';
```

Session-level rollups belong in a separate fact or in a semantic layer with explicit aggregation:

```sql
CREATE TABLE fct_agent_session (
    session_sk             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    session_id             VARCHAR(64) NOT NULL UNIQUE,
    user_sk                BIGINT NOT NULL,
    date_sk                INT NOT NULL,
    session_start_ts       TIMESTAMPTZ NOT NULL,
    session_end_ts         TIMESTAMPTZ NOT NULL,

    -- additive at session grain
    llm_call_count         INT NOT NULL,
    tool_invocation_count  INT NOT NULL,
    total_tokens           INT NOT NULL,
    total_cost_usd         NUMERIC(12, 6) NOT NULL,
    duration_sec           INT NOT NULL,

    -- semi-additive or non-additive — document carefully
    resolved_flag          BOOLEAN NOT NULL,
    escalated_flag         BOOLEAN NOT NULL,
    user_satisfaction_score SMALLINT  -- nullable, survey
);
```

Build session facts from call/tool facts in ETL — do not let analysts `SUM(resolved_flag)` across users without understanding non-additivity.

## Non-additive facts and footguns

Some measures cannot be summed across arbitrary dimensions:

- **Ratios:** success rate = successes / attempts — sum of rates is wrong.
- **Distinct counts:** unique users — sum of daily uniques ≠ weekly unique.
- **Averages:** average latency — use weighted average from sum(latency_ms * call_count) / sum(call_count).

Store components additive at grain; compute ratios in BI or semantic layer:

```yaml
# dbt semantic model excerpt
metrics:
  - name: tool_success_rate
    type: derived
    type_params:
      expr: sum(tool_success_count) / nullif(sum(tool_invocation_count), 0)
    filter: |
      {{ Dimension('fct_agent_tool_invocation__date') }} >= '2025-01-01'
```

Document **non-additive** flags in the data catalog so experiment platforms do not SUM `user_satisfaction_score` across sessions.

## Degenerate dimensions and dimension keys

High-cardinality IDs (`session_id`, `trace_id`, `ticket_id`) usually live as degenerate columns on the fact — no `dim_session` row needed unless you have slowly changing session attributes (assigned team, channel).

Surrogate keys (`session_sk`) isolate facts from source ID churn and enable type-2 history on dimensions without touching facts.

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass(frozen=True)
class GrainContract:
    table_name: str
    grain_description: str
    natural_key: tuple[str, ...]
    allowed_measures: tuple[str, ...]

GRAINS = {
    "fct_agent_llm_call": GrainContract(
        table_name="fct_agent_llm_call",
        grain_description="one row per LLM API call",
        natural_key=("call_id",),
        allowed_measures=(
            "prompt_tokens", "completion_tokens", "latency_ms", "cost_usd"
        ),
    ),
    "fct_agent_session": GrainContract(
        table_name="fct_agent_session",
        grain_description="one completed agent session",
        natural_key=("session_id",),
        allowed_measures=(
            "llm_call_count", "total_tokens", "total_cost_usd",
            "duration_sec", "resolved_flag",
        ),
    ),
}

def validate_row(table: str, row: dict) -> None:
    contract = GRAINS[table]
    for measure in row:
        if measure.endswith("_sk") or measure in contract.natural_key:
            continue
        if measure not in contract.allowed_measures:
            raise ValueError(
                f"{measure} not allowed at grain: {contract.grain_description}"
            )
```

Run validation in ingestion jobs — reject rows with session-level fields on call-level facts.

## Snapshot facts for agent operations

Periodic snapshots capture state that never appears as a discrete event:

```sql
CREATE TABLE fct_agent_queue_snapshot (
    snapshot_date_sk   INT NOT NULL,
    queue_sk           BIGINT NOT NULL,
    snapshot_hour      SMALLINT NOT NULL,  -- 0-23

    open_session_count INT NOT NULL,
    waiting_user_count INT NOT NULL,
    active_agent_count INT NOT NULL,

    PRIMARY KEY (snapshot_date_sk, queue_sk, snapshot_hour)
);
```

Grain: **one row per queue per hour**. Semi-additive — sum across queues within an hour, but not across hours (double-counts persistent queue depth).

Use snapshots for capacity planning; use transaction facts for causal analysis ("did model v3 reduce escalations?").

## Agent-specific grain decisions

**Multi-tool parallel calls:** if one user turn triggers three tools concurrently, grain is one row per tool invocation, not per turn. Add `turn_index` degenerate dimension if turn-level analysis matters.

**Streaming responses:** decide whether partial chunks are facts. Most teams record one LLM call fact at stream completion with total tokens; chunk-level facts are debug-only with TTL.

**Human-in-the-loop:** escalation creates a new session or continues the same? Pick one `session_id` policy and document it — splitting mid-session breaks funnel metrics.

**Experiments:** assign `experiment_variant` at session start on `dim_session` or bridge table — not duplicated differently on call facts.

## ETL idempotency at declared grain

Natural keys enforce idempotent loads:

```sql
INSERT INTO fct_agent_llm_call (call_id, session_sk, ...)
SELECT ...
FROM staging
ON CONFLICT (call_id) DO UPDATE SET
    prompt_tokens = EXCLUDED.prompt_tokens,
    completion_tokens = EXCLUDED.completion_tokens,
    latency_ms = EXCLUDED.latency_ms,
    cost_usd = EXCLUDED.cost_usd;
```

Late-arriving calls after session close trigger session fact **reconciliation jobs** — update `fct_agent_session` totals when new calls land, with `last_updated_ts` for audit.

## Semantic layer and agent eval loops

Experiment analysis joins session facts to variants:

```sql
SELECT
    e.variant_name,
    COUNT(*) AS sessions,
    AVG(CASE WHEN f.resolved_flag THEN 1.0 ELSE 0.0 END) AS resolution_rate,
    SUM(f.total_cost_usd) / NULLIF(COUNT(*), 0) AS cost_per_session
FROM fct_agent_session f
JOIN dim_experiment_assignment e ON f.session_id = e.session_id
WHERE f.date_sk BETWEEN 20250201 AND 20250228
GROUP BY e.variant_name;
```

Resolution rate is computed from counts — not summed flags across pre-aggregated rows. Cost per session divides additive sums — valid at session grain only.

Feed the same definitions to agent offline eval pipelines so warehouse metrics match Python eval scripts.

## Testing grain integrity

1. **Uniqueness tests (dbt):** `unique` + `not_null` on natural keys per fact.
2. **Referential integrity:** every `session_sk` in call facts exists in session dimension or bridge.
3. **Reconciliation:** `SUM(call.total_tokens) GROUP BY session_id` equals `session.total_tokens` ± tolerance.
4. **Documentation test:** every column tagged `measure_type: additive|semi-additive|non-additive`.

## The takeaway

Fact table grain is a contract — one row per clearly defined event. Agent platforms generate nested events (sessions, calls, tools); model each level explicitly, join through conformed dimensions, and keep ratios out of raw facts. Declare grain in comments, enforce it in ETL, and teach analysts which measures sum and which require derived metrics. Trustworthy agent ROI starts with rows that mean one thing.

## Resources

- [The Data Warehouse Toolkit (Kimball & Ross)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/)

- [dbt best practices for grain](https://docs.getdbt.com/best-practices/how-we-structure/1-guide-overview)

- [Star schema vs snowflake (Google Cloud documentation)](https://cloud.google.com/bigquery/docs/star-schema)

- [Semi-additive facts explained (Dimensional Modeling Techniques)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/kimball-techniques/dimensional-modeling-techniques/)

- [MetricFlow / semantic layer concepts](https://docs.getdbt.com/docs/build/about-metricflow)
