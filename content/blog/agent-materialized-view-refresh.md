---
title: "Materialized View Refresh Strategies for Agent Analytics"
slug: "agent-materialized-view-refresh"
description: "Keep agent run metrics, token spend rollups, and eval dashboards fresh—CONCURRENT refresh, incremental MVs, CDC-driven invalidation, and staleness SLOs without locking your Postgres OLTP path."
datePublished: "2024-12-03"
dateModified: "2024-12-03"
tags: ["AI Agents", "PostgreSQL", "Analytics", "Data Engineering"]
keywords: "materialized view refresh, CONCURRENTLY refresh, agent analytics, token spend rollup, incremental materialized view, Postgres CDC"
faq:
  - q: "When should agent platforms use materialized views instead of live queries?"
    a: "Use MVs when dashboards aggregate millions of agent_run rows (token spend by tenant, p95 latency by model, eval pass rate by week) and live GROUP BY queries exceed your OLTP latency budget. Skip MVs for real-time billing meters that must be exact to the second—those need streaming aggregation or row-level ledger tables."
  - q: "Does REFRESH MATERIALIZED VIEW CONCURRENTLY block writes?"
    a: "CONCURRENTLY avoids exclusive locks on the MV during refresh, but it requires a UNIQUE index on the MV and runs two scans—slower and heavier on I/O. Base table writes continue; readers may see stale data until refresh completes. Schedule heavy refreshes off peak or use incremental strategies."
  - q: "How stale can agent metrics safely be?"
    a: "Ops dashboards: 1–5 minutes is usually acceptable if you label as-of timestamps. Executive rollups: 15–60 minutes. Real-time alerting on SLO burn should not rely on MVs—use streaming windows or raw event tables with indexed time ranges. Document staleness SLOs per dashboard."
  - q: "Can you refresh materialized views from change data capture?"
    a: "Yes. Debezium or logical replication can drive partial re-aggregation: maintain delta tables or use incremental MV extensions (pg_ivm in Postgres, or rollups in ClickHouse). Full REFRESH on large MVs every minute does not scale; CDC-triggered incremental updates do."
---

The exec dashboard showed token spend flat for six hours while finance watched the OpenAI invoice climb. The materialized view `mv_tenant_daily_spend` had not refreshed since a failed cron job at 04:00—silent failure, no alert, and the UI never surfaced **as-of** time. Engineers ran `REFRESH MATERIALIZED VIEW` manually during peak; it took eleven minutes and held an access exclusive lock on the old non-concurrent path. Agent run inserts backed up. The fix was not "delete the MV." It was **refresh strategy**: CONCURRENTLY, incremental rollups, staleness metrics, and separating OLTP from analytics read paths.

Agent platforms generate high-cardinality telemetry: every run, tool call, token count, eval score, and guardrail flag. Product wants dashboards; finance wants rollups; on-call wants SLO charts. Scanning raw `agent_runs` for each page load collapses under tenant growth. Materialized views pre-compute aggregates—but **refresh** is where teams bleed: locks, stale data, and jobs that fail quietly.

## What to materialize for agent workloads

Good MV candidates share traits: **read-heavy**, **append-mostly source**, **tolerable staleness**, **expensive aggregation**.

| MV | Source tables | Typical grain | Staleness target |
|----|---------------|---------------|------------------|
| Daily token spend | `agent_runs`, `billing_events` | tenant × day × model | 5 min |
| Tool success rate | `tool_invocations` | tool × hour | 2 min |
| Eval regression | `eval_results` | suite × version × day | 15 min |
| Queue depth snapshot | `run_queue` | status × minute | 30 sec (borderline—consider streaming) |

Avoid MVs that join wide JSONB tool payloads unless you extract columns first—refresh cost tracks MV row width, not just row count.

Example base MV for tenant daily spend:

```sql
CREATE MATERIALIZED VIEW mv_tenant_daily_spend AS
SELECT
  tenant_id,
  date_trunc('day', started_at AT TIME ZONE 'UTC') AS day,
  model_id,
  COUNT(*) AS run_count,
  SUM(input_tokens + output_tokens) AS total_tokens,
  SUM(estimated_cost_usd) AS cost_usd,
  PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms
FROM agent_runs
WHERE started_at >= now() - interval '90 days'
GROUP BY 1, 2, 3;

CREATE UNIQUE INDEX ON mv_tenant_daily_spend (tenant_id, day, model_id);
```

The unique index is mandatory for `REFRESH ... CONCURRENTLY` in Postgres.

## Full refresh vs incremental

**Full refresh** recomputes the entire MV. Simple, correct, expensive:

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_tenant_daily_spend;
```

Use full refresh when:

- MV definition changes
- Source had bulk backfills or deletes that invalidate incremental bookkeeping
- Data volume is small enough (< few million aggregated rows)

**Incremental refresh** updates only changed keys. Patterns:

1. **Rolling window MV** — Definition filters `WHERE started_at >= now() - interval '90 days'`. Nightly full refresh; hourly merge of today's partition from a staging aggregate query.
2. **Delta table** — CDC appends `(tenant_id, day, model_id, delta_tokens, delta_cost)`; refresh job upserts into MV table (often a regular table mimicking MV, not native MV).
3. **pg_ivm** — Immediate maintenance on base table changes; trade write amplification on hot paths.

For agent runs append streams, **partition by day** on the source table first. Refresh today's partition every minute; refresh historical partitions daily.

```sql
-- Staging aggregate for today only (cheap)
INSERT INTO mv_tenant_daily_spend_staging
SELECT tenant_id, date_trunc('day', started_at) AS day, model_id, ...
FROM agent_runs
WHERE started_at >= date_trunc('day', now())
GROUP BY 1, 2, 3;

-- Merge into MV-backed table
INSERT INTO tenant_daily_spend AS t
SELECT * FROM mv_tenant_daily_spend_staging
ON CONFLICT (tenant_id, day, model_id) DO UPDATE SET
  run_count = EXCLUDED.run_count,
  total_tokens = EXCLUDED.total_tokens,
  cost_usd = EXCLUDED.cost_usd,
  p95_latency_ms = EXCLUDED.p95_latency_ms,
  refreshed_at = now();
```

## Scheduling and orchestration

Cron alone is insufficient— you need **observable jobs**:

```python
from datetime import datetime, timezone
import psycopg

REFRESH_STATEMENTS = [
    ("mv_tenant_daily_spend", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_tenant_daily_spend"),
    ("mv_tool_hourly", "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_tool_hourly"),
]

def refresh_all(conn: psycopg.Connection) -> None:
    for name, sql in REFRESH_STATEMENTS:
        started = datetime.now(timezone.utc)
        with conn.cursor() as cur:
            cur.execute(sql)
        duration = (datetime.now(timezone.utc) - started).total_seconds()
        emit_metric("mv_refresh_duration_seconds", duration, tags={"mv": name})
        emit_metric("mv_refresh_success", 1, tags={"mv": name})

        # Record as-of for UI
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mv_freshness (mv_name, refreshed_at, duration_sec)
                VALUES (%s, now(), %s)
                ON CONFLICT (mv_name) DO UPDATE SET
                  refreshed_at = EXCLUDED.refreshed_at,
                  duration_sec = EXCLUDED.duration_sec
                """,
                (name, duration),
            )
    conn.commit()
```

Run refreshes from a worker with **advisory locks** to prevent overlapping runs:

```sql
SELECT pg_try_advisory_lock(hashtext('refresh_mv_tenant_daily_spend'));
-- if false, skip or alert on overlap
```

Alert when `now() - refreshed_at > staleness_slo` for any MV name in `mv_freshness`.

## CONCURRENTLY pitfalls

`REFRESH MATERIALIZED VIEW CONCURRENTLY`:

- Requires **UNIQUE index** on all MV rows (no partial unique indexes in older Postgres versions for this purpose—verify your version)
- Leaves dead tuples—schedule `VACUUM` on MV or use a table-backed rollup with `DELETE`/`INSERT` batches
- Can fail if unique constraint violated mid-refresh (source duplicates that violate MV grain)—fix upstream dedup
- Slower than non-concurrent—plan duration growth as data grows

Non-concurrent refresh during maintenance window remains valid for small deployments. Document the lock behavior in runbooks before on-call discovers it at 2pm.

## CDC-driven invalidation

When agent runs land via Debezium:

```
agent_runs (Postgres) ──► Kafka topic ──► Flink / consumer
                              │
                              ▼
                    rollup_worker upserts
                    tenant_daily_spend table
```

The consumer maintains aggregates keyed by `(tenant_id, day, model_id)`:

```python
def apply_run_event(event: dict, conn) -> None:
    if event["op"] not in ("c", "u"):
        return
    row = event["after"]
    day = row["started_at"][:10]  # normalize to UTC day bucket
    conn.execute(
        """
        INSERT INTO tenant_daily_spend (tenant_id, day, model_id, run_count, total_tokens, cost_usd)
        VALUES (%s, %s, %s, 1, %s, %s)
        ON CONFLICT (tenant_id, day, model_id) DO UPDATE SET
          run_count = tenant_daily_spend.run_count + 1,
          total_tokens = tenant_daily_spend.total_tokens + EXCLUDED.total_tokens,
          cost_usd = tenant_daily_spend.cost_usd + EXCLUDED.cost_usd,
          refreshed_at = now()
        """,
        (row["tenant_id"], day, row["model_id"], row["tokens"], row["cost"]),
    )
```

Reconcile nightly: compare CDC rollup to full re-aggregate of yesterday's partition; alert on drift > 0.1%.

## Serving layer: do not query MVs from the hot path

Agent run **creation** must never wait on MV refresh. Architecture:

```
OLTP Postgres (agent_runs) ──► API writes
        │
        ├──► CDC ──► rollup tables / MVs ──► Grafana / internal BI
        │
        └──► Redis counters for real-time quota (optional, exact-enough)
```

Dashboard API reads `tenant_daily_spend` with `refreshed_at` in response:

```json
{
  "tenant_id": "ten_abc",
  "day": "2025-06-23",
  "cost_usd": 142.17,
  "as_of": "2025-06-23T14:32:01Z"
}
```

Users forgive minute-old spend; they do not forgive silent lies.

## Eval and experiment MVs

Eval pipelines produce versioned scores. MV grain should include **eval_suite_id** and **prompt_hash_version**, not just date—otherwise you blend incompatible eval sets after a prompt change.

```sql
CREATE MATERIALIZED VIEW mv_eval_pass_rate AS
SELECT
  eval_suite_id,
  agent_version,
  date_trunc('day', evaluated_at) AS day,
  COUNT(*) FILTER (WHERE passed) AS passed,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE passed) / NULLIF(COUNT(*), 0), 2) AS pass_pct
FROM eval_results
WHERE evaluated_at >= now() - interval '180 days'
GROUP BY 1, 2, 3;
```

Refresh after eval batch completes (event-triggered), not on fixed cron—staleness when no evals run is fine.

## Migration: from live queries to MVs

1. Create MV **CONCURRENTLY** in shadow mode; compare outputs to live query in batch job
2. Switch dashboard read path behind feature flag
3. Monitor p95 query time and row counts
4. Drop live aggregate query after seven days of match

When changing MV definition, use **blue-green table swap**:

```sql
CREATE MATERIALIZED VIEW mv_tenant_daily_spend_v2 AS ...;
CREATE UNIQUE INDEX ...;
-- backfill validate
BEGIN;
ALTER MATERIALIZED VIEW mv_tenant_daily_spend RENAME TO mv_tenant_daily_spend_old;
ALTER MATERIALIZED VIEW mv_tenant_daily_spend_v2 RENAME TO mv_tenant_daily_spend;
COMMIT;
DROP MATERIALIZED VIEW mv_tenant_daily_spend_old;
```

## The takeaway

Materialized views make agent analytics affordable, but refresh is production engineering—not a one-line cron. Use CONCURRENTLY with unique indexes, prefer incremental or CDC rollups at scale, expose as-of timestamps, alert on freshness SLO breaches, and keep OLTP off the refresh critical path. The goal is dashboards that are fast, honest, and boring to operate.

## Resources

- [PostgreSQL — REFRESH MATERIALIZED VIEW documentation](https://www.postgresql.org/docs/current/sql-refreshmaterializedview.html)
- [pg_ivm — Incremental View Maintenance extension](https://github.com/sraoss/pg_ivm)
- [Debezium PostgreSQL connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Timescale continuous aggregates (alternative pattern)](https://docs.timescale.com/use-timescale/latest/continuous-aggregates/)
- [Grafana staleness annotations best practices](https://grafana.com/docs/grafana/latest/dashboards/annotations/)
