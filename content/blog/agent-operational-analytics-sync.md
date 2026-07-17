---
title: "AI Agents: Operational Analytics Sync"
slug: "agent-operational-analytics-sync"
description: "Sync agent run telemetry from operational Postgres into analytics warehouses — CDC with Debezium, idempotent fact tables, schema contracts, and lag SLOs product teams actually trust."
datePublished: "2025-03-18"
dateModified: "2025-03-18"
tags: ["AI Agents", "Analytics", "Data Engineering", "CDC"]
keywords: "operational analytics sync, agent telemetry warehouse, Debezium CDC Postgres, agent run metrics ETL, analytics lag SLO"
faq:
  - q: "Why not query production Postgres directly for agent dashboards?"
    a: "Operational databases serve live agent orchestration — heavy analytical scans contend with tool-call writes, inflate replica lag, and bypass row-level security models analytics teams need. Sync decouples OLTP from OLAP and lets you denormalize for BI without touching runtime schema."
  - q: "CDC or nightly batch for agent run events?"
    a: "Use CDC when product needs sub-hour freshness on token spend, success rates, or tenant usage billing. Batch works for executive summaries where T+1 is acceptable. Most agent platforms start batch, hit pain at month-end close, then migrate hot paths to CDC."
  - q: "How do you handle schema changes in agent event tables?"
    a: "Treat the operational `agent_runs` table as a contract: additive columns only in production, Avro/Protobuf schemas in a registry for downstream topics, and dbt tests that fail CI when warehouse columns drift from source."
  - q: "What lag SLO is reasonable for operational analytics?"
    a: "For usage metering and cost allocation, aim p95 sync lag under 5 minutes. For exploratory product analytics, 15–30 minutes is often fine. Publish the number — stakeholders treat synced data as truth and will escalate if lag silently grows."
---

Finance asked why March agent token spend in Looker disagreed with the invoice from your LLM provider by twelve percent. The investigation took three days: a nightly batch job had skipped rows where `finished_at` was null (runs still streaming), duplicate `run_id` keys in the warehouse double-counted retries, and a timezone bug shifted UTC timestamps into the previous billing day. None of this was malice — it was what happens when you treat operational analytics sync as a cron script instead of a product surface with SLOs.

## The data you are actually syncing

Agent platforms generate high-cardinality operational facts:

- **Run lifecycle** — `run_id`, tenant, model, prompt hash, status, latency, token in/out
- **Tool invocations** — tool name, success, duration, external API cost attribution
- **Human approvals** — who approved, wait time, override reason codes
- **Errors and guardrail hits** — policy violations, rate limits, content filters

These rows land in normalized OLTP tables optimized for inserts and point lookups. Analytics wants wide fact tables partitioned by `event_date`, conformed dimensions for tenant and model, and idempotent upserts so retries do not inflate metrics.

The sync pipeline's job is not copying tables — it is **proving** that every billable event in Postgres appears exactly once in the warehouse within your lag budget.

## Architecture sketch

```
┌─────────────────┐     WAL/CDC      ┌──────────────┐     stream     ┌─────────────┐
│ Postgres OLTP   │ ───────────────► │ Kafka topic  │ ─────────────► │ Flink/dbt   │
│ agent_runs      │   Debezium       │ agent.runs   │   transform    │ staging     │
│ tool_calls      │                  │ agent.tools  │                └──────┬──────┘
└─────────────────┘                  └──────────────┘                       │
                                                                            ▼
                                                                    ┌─────────────┐
                                                                    │ BigQuery /  │
                                                                    │ Snowflake   │
                                                                    └─────────────┘
```

Batch-only variant replaces Kafka with object storage snapshots — acceptable until someone needs intraday spend caps.

## Source table design that survives sync

Before tuning Debezium, fix the OLTP schema:

```sql
CREATE TABLE agent_runs (
  run_id          UUID PRIMARY KEY,
  tenant_id       UUID NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
  model           TEXT NOT NULL,
  input_tokens    INT,
  output_tokens   INT,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ,  -- nullable while streaming; analytics must handle NULL
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  billing_day     DATE GENERATED ALWAYS AS ((started_at AT TIME ZONE 'UTC')::date) STORED
);

CREATE INDEX agent_runs_updated_at_idx ON agent_runs (updated_at);
```

`updated_at` on every state transition gives batch jobs a reliable cursor. `billing_day` as a generated column removes timezone arguments in the warehouse — store UTC, derive business dates once.

## CDC connector configuration

Debezium on Postgres with logical replication:

```json
{
  "name": "agent-platform-cdc",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "pg-primary.internal",
    "database.port": "5432",
    "database.user": "debezium",
    "database.password": "${secrets:debezium_password}",
    "database.dbname": "agents",
    "topic.prefix": "cdc",
    "table.include.list": "public.agent_runs,public.tool_calls",
    "plugin.name": "pgoutput",
    "publication.autocreate.mode": "filtered",
    "slot.name": "debezium_agent_runs",
    "heartbeat.interval.ms": "10000",
    "transforms": "unwrap",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.drop.tombstones": "false"
  }
}
```

Monitor replication slot lag — if the warehouse consumer stalls, Postgres retains WAL and disk fills. Alert on `pg_replication_slots` lag bytes, not just consumer heartbeats.

## Warehouse merge: idempotent upsert

Streaming duplicates are normal. Merge on natural key:

```sql
-- BigQuery merge example
MERGE analytics.fact_agent_runs AS t
USING staging.agent_runs_delta AS s
ON t.run_id = s.run_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN
  UPDATE SET
    status = s.status,
    input_tokens = s.input_tokens,
    output_tokens = s.output_tokens,
    finished_at = s.finished_at,
    synced_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN
  INSERT (run_id, tenant_id, status, model, input_tokens, output_tokens,
          started_at, finished_at, billing_day, synced_at)
  VALUES (s.run_id, s.tenant_id, s.status, s.model, s.input_tokens,
          s.output_tokens, s.started_at, s.finished_at, s.billing_day, CURRENT_TIMESTAMP());
```

Runs still `running` with partial token counts should **update** existing rows, not insert siblings. Product dashboards filter `status = 'completed'` for final spend but can show in-flight estimates separately.

## dbt tests that catch the March invoice bug

```yaml
# models/staging/schema.yml
models:
  - name: stg_agent_runs
    columns:
      - name: run_id
        tests: [unique, not_null]
      - name: tenant_id
        tests: [not_null]
    tests:
      - dbt_utils.expression_is_true:
          expression: "finished_at IS NULL OR finished_at >= started_at"
      - dbt_expectations.expect_table_row_count_to_equal_other_table:
          compare_model: source('oltp', 'agent_runs')
          tolerance_percent: 0.1
```

Row-count parity within 0.1% surfaces sync stalls before finance does. Expression tests catch impossible timestamps from bad clock skew on workers.

## Handling streaming runs and late-arriving facts

Agent runs can last minutes — token counts arrive incrementally. Two patterns:

1. **Snapshot updates** — CDC emits every `UPDATE`; warehouse keeps latest row per `run_id`. Dashboards label in-flight runs clearly.
2. **Event append** — separate `agent_run_token_deltas` table; analytics sums deltas. Better audit trail, harder BI queries.

Most teams pick snapshot updates until compliance asks for delta-level proof.

## Batch fallback cursor job

When CDC is overkill for cold paths, cursor batch still needs rigor:

```python
from datetime import datetime, timezone
import psycopg

CURSOR_KEY = "agent_runs_analytics"

def sync_batch(conn, warehouse, watermark: datetime) -> datetime:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, tenant_id, status, model,
                   input_tokens, output_tokens, started_at, finished_at, updated_at
            FROM agent_runs
            WHERE updated_at > %s
            ORDER BY updated_at
            LIMIT 5000
            """,
            (watermark,),
        )
        rows = cur.fetchall()

    if not rows:
        return watermark

    warehouse.upsert_runs(rows)
    new_watermark = max(r.updated_at for r in rows)
    warehouse.save_cursor(CURSOR_KEY, new_watermark)
    return new_watermark
```

Never use `finished_at` as the cursor — open runs never sync. Always `updated_at`, bumped on every token flush.

## Metrics and ownership

| Metric | Purpose |
|--------|---------|
| `analytics_sync_lag_seconds` | Max `now() - updated_at` among recent runs in warehouse vs OLTP |
| `cdc_consumer_offset_lag` | Kafka/Flink backlog |
| `merge_rows_affected` | Detect silent zero-row merges (broken staging) |
| `row_count_drift_ratio` | OLTP vs warehouse counts from dbt |

Dashboard the lag number in the same Slack channel product watches. Assign an owner in the data platform team, not "whoever touched the cron last."

## When sync goes wrong — a short playbook

**Symptom:** Dashboard undercounts today's runs. Check CDC slot lag, then compare `MAX(updated_at)` OLTP vs warehouse. Stalled slot → restart consumer, never drop slot without ops review.

**Symptom:** Duplicate spend. Search merge keys — missing `run_id` uniqueness or treating retries as new inserts.

**Symptom:** Timezone drift in billing. Enforce UTC storage; derive `billing_day` in one place; add dbt test that `billing_day = DATE(started_at)` in UTC.

The twelve percent invoice gap closed after switching the batch cursor to `updated_at`, adding the merge upsert, and publishing a five-minute lag SLO with a PagerDuty route. Finance and product now argue about definitions — not about missing data.

## Partitioning and cost control in the warehouse

Agent telemetry grows faster than most SaaS fact tables — a busy tenant generates thousands of tool-call rows per hour. Partition `fact_agent_runs` by `billing_day` or `started_at` date so backfills touch one day, not the full history. Cluster on `tenant_id` if BI filters by customer ninety percent of the time.

Cold storage policies matter: keep ninety days hot for product dashboards, archive older partitions to cheaper tiers, but retain OLTP or object-store snapshots for seven years if contracts require audit trails. Sync pipelines should tag each row with `sync_batch_id` — when a bad deploy double-writes, you delete by batch instead of hand-crafted `DELETE` guesses.

## Contract testing between OLTP and analytics

Before merging any migration to `agent_runs`, run contract tests in CI:

```python
def test_analytics_contract_sample(pg_conn, sample_run_factory):
    run = sample_run_factory(status="completed", output_tokens=42)
    pg_conn.insert_run(run)
    warehouse.refresh_staging()

    row = warehouse.query_one("SELECT * FROM stg_agent_runs WHERE run_id = %s", run.run_id)
    assert row.output_tokens == 42
    assert row.billing_day == run.started_at.date()
```

Sampling ten synthetic runs through the full pipeline catches column renames analytics was not told about — the classic `model_name` → `model` break that silently NULLs dashboard dimensions.

## Resources

- [Debezium PostgreSQL Connector Documentation](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [dbt Tests Documentation](https://docs.getdbt.com/docs/build/tests)
- [The Data Warehouse Toolkit (Kimball)](https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/books/data-warehouse-dw-toolkit/)
- [PostgreSQL Logical Replication](https://www.postgresql.org/docs/current/logical-replication.html)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
