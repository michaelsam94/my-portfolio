---
title: "AI Agents: Partition Pruning Strategies"
slug: "agent-partition-pruning-strategies"
description: "Partition pruning keeps agent telemetry and conversation log queries fast by teaching the planner which time and tenant slices to skip — declarative keys, constraint exclusion, and ORM-safe patterns."
datePublished: "2024-12-06"
dateModified: "2024-12-06"
tags: ["AI", "Agent", "Partition"]
keywords: "partition pruning PostgreSQL, declarative partitioning, agent conversation logs, constraint exclusion, time series agent telemetry, partition key design"
faq:
  - q: "What is partition pruning in database queries?"
    a: "Partition pruning is when the query planner skips scanning partitions whose bounds cannot contain matching rows — typically because the WHERE clause filters on the partition key (date range, tenant_id). Fewer partitions scanned means lower I/O and more predictable latency on large agent log tables."
  - q: "Which partition key works best for agent conversation logs?"
    a: "Composite (tenant_id, event_date) or (tenant_id, month) is common: most agent dashboards query one tenant over a recent time window. Pure time partitioning works for single-tenant installs; pure tenant partitioning creates uneven shard sizes when one customer dominates traffic."
  - q: "Why do ORMs often defeat partition pruning?"
    a: "Wrapping partition key columns in functions — `WHERE date(created_at) = '2024-11-01'` — or using open-ended OR conditions prevents compile-time pruning. ORMs also emit queries without partition key predicates when pagination abstractions hide the filter."
  - q: "How does partition pruning differ from partial indexes?"
    a: "Pruning eliminates whole physical partitions at plan time. Partial indexes filter rows inside one table. Pruning helps retention and bulk drops; partial indexes help selective hot-row lookups. Agent stacks usually need both on different tables."
---
The on-call page fired because the agent analytics dashboard timed out. Postgres was not melting — it was obediently scanning eighteen months of `agent_events` child partitions because a well-meaning intern removed the date filter to "show all history by default." Eighty-seven partitions, 400 ms each, users staring at a spinner. The table was partitioned correctly. The queries were not pruning.

Partition pruning is the planner behavior that makes partitioning worth the operational tax. For agent platforms storing run logs, tool traces, and token meters, pruning is the difference between sub-second dashboards and sequential scans dressed in enterprise clothing.

## Why agent telemetry outgrows single tables

Order-of-magnitude math: 500 agents × 40 events per run × 200 runs per day ≈ 4 million rows daily. Indexes grow linearly; autovacuum fights widen; BRIN and partial indexes help but retention policies still need to drop old data without `DELETE` locking the world.

Declarative partitioning in PostgreSQL splits one logical table into child tables bound by range or list keys. Pruning lets `WHERE event_time >= '2025-07-01'` touch July partitions only.

## Partition layout for multi-tenant agents

```sql
CREATE TABLE agent_events (
  id          bigserial,
  tenant_id   text NOT NULL,
  session_id  text NOT NULL,
  event_time  timestamptz NOT NULL,
  event_type  text NOT NULL,
  payload     jsonb NOT NULL
) PARTITION BY RANGE (event_time);

CREATE TABLE agent_events_2025_07 PARTITION OF agent_events
  FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

CREATE TABLE agent_events_2025_08 PARTITION OF agent_events
  FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Per-partition indexes stay small
CREATE INDEX ON agent_events_2025_07 (tenant_id, session_id);
CREATE INDEX ON agent_events_2025_07 (tenant_id, event_type, event_time DESC);
```

Automate child creation with `pg_partman` or a cron job that creates next month's partition before the first event arrives — inserting into a missing partition fails hard.

### Tenant-heavy skew

When one tenant generates 60% of events, range-only partitioning creates hot partitions. Options:

1. **Sub-partition by list(tenant_id)** for whale tenants — advanced, operational overhead high
2. **Separate tablespace** for large tenants — storage isolation, same pruning rules
3. **Keep range partitioning** but accept skew; optimize queries with `(tenant_id, event_time)` indexes inside each month

Most B2B agent products fit option 3 until a single customer forces option 1.

## Static pruning vs constraint exclusion

**Static pruning** happens at plan time when predicates match partition bounds literally:

```sql
EXPLAIN SELECT count(*)
FROM agent_events
WHERE event_time >= '2025-07-10'
  AND event_time <  '2025-07-11'
  AND tenant_id = 'tenant_acme';
```

Expected plan fragment:

```
Append
  ->  Index Scan on agent_events_2025_07
        Index Cond: ((tenant_id = 'tenant_acme') AND ...)
Partitions pruned: 11 of 12
```

**Constraint exclusion** (legacy inheritance) still appears in older stacks; declarative partitioning replaced most use cases in PostgreSQL 11+. Ensure `enable_partition_pruning = on` (default since PG 12).

## Query patterns that prune reliably

### Dashboard: recent runs for one tenant

```sql
SELECT session_id, max(event_time) AS last_seen
FROM agent_events
WHERE tenant_id = $1
  AND event_time >= now() - interval '7 days'
GROUP BY session_id
ORDER BY last_seen DESC
LIMIT 50;
```

Prunes to current month partition plus maybe previous month if the 7-day window crosses boundary — two partitions, not twelve.

### Session replay: bounded time window

Always require session_id **and** a time hint from session metadata:

```sql
SELECT event_type, payload, event_time
FROM agent_events
WHERE tenant_id = $1
  AND session_id = $2
  AND event_time BETWEEN $3 AND $4  -- session start/end from sessions table
ORDER BY event_time;
```

Without `$3/$4`, Postgres may scan all partitions for that session_id if session IDs are not time-sortable UUIDs.

### Aggregates: push filters inside CTEs

```sql
WITH daily AS (
  SELECT date_trunc('day', event_time) AS day, sum((payload->>'tokens')::int) AS tokens
  FROM agent_events
  WHERE tenant_id = $1
    AND event_time >= $2
    AND event_time <  $3
  GROUP BY 1
)
SELECT * FROM daily ORDER BY day;
```

Avoid wrapping `event_time` in `date_trunc` in the WHERE clause — that kills compile-time pruning. Filter raw timestamps first, truncate in SELECT.

## Application-layer guardrails

TypeScript repository wrapper that refuses unbounded scans:

```typescript
type AgentEventQuery = {
  tenantId: string;
  from: Date;
  to: Date;
  sessionId?: string;
};

export async function fetchEvents(db: Pool, q: AgentEventQuery) {
  const spanDays = (q.to.getTime() - q.from.getTime()) / 86_400_000;
  if (spanDays > 31) {
    throw new Error("agent_events query exceeds 31-day partition window");
  }
  if (q.to <= q.from) {
    throw new Error("invalid time range");
  }

  const sql = `
    SELECT event_type, payload, event_time
    FROM agent_events
    WHERE tenant_id = $1
      AND event_time >= $2
      AND event_time <  $3
      ${q.sessionId ? "AND session_id = $4" : ""}
    ORDER BY event_time
  `;
  const params = q.sessionId
    ? [q.tenantId, q.from, q.to, q.sessionId]
    : [q.tenantId, q.from, q.to];

  return db.query(sql, params);
}
```

Hard limits feel rude until they prevent an outage. Expose "export all history" as an async batch job scanning partitions sequentially with cursor pagination, not an interactive API.

## ORM patterns that break pruning

| Generated SQL | Pruning? |
|---------------|----------|
| `event_time >= ? AND event_time < ?` | Yes |
| `date(event_time) = ?` | Often no |
| `event_time BETWEEN ? AND ? OR tenant_id IS NULL` | Unpredictable |
| Missing time filter entirely | No — full scan |

SQLAlchemy example with explicit bounds:

```python
def events_for_tenant(session, tenant_id: str, start: datetime, end: datetime):
    if (end - start).days > 31:
        raise ValueError("range too wide")
    return (
        session.query(AgentEvent)
        .filter(
            AgentEvent.tenant_id == tenant_id,
            AgentEvent.event_time >= start,
            AgentEvent.event_time < end,
        )
        .order_by(AgentEvent.event_time)
        .all()
    )
```

Use `union_all` across known partition names only in ETL tools — never in request-path ORM code.

## Retention and partition lifecycle

Pruning helps reads; **DETACH/DROP** helps storage:

```sql
-- Archive July after billing close
ALTER TABLE agent_events DETACH PARTITION agent_events_2025_07;
-- Move to cold storage or drop
DROP TABLE agent_events_2025_07;
```

Agent compliance often requires 90-day hot retention, 7-year cold archive. Detached partitions export to Parquet in object storage cheaper than keeping them in primary Postgres.

Schedule drops during low traffic; even DETACH takes an exclusive lock momentarily on parent metadata.

## Cross-partition queries for admin

Internal support tools sometimes need "find session X anywhere." Two strategies:

1. **Lookup table** mapping `session_id → partition_month` at session creation — O(1) partition targeting
2. **Sequential partition scan** with statement timeout — acceptable for rare admin ops, not user APIs

We stored `partition_month` on `agent_sessions` populated at insert:

```sql
ALTER TABLE agent_sessions ADD COLUMN log_partition date;

UPDATE agent_sessions SET log_partition = date_trunc('month', created_at)::date;
```

Replay queries join session metadata for the partition hint:

```sql
SELECT e.*
FROM agent_sessions s
JOIN agent_events e ON e.session_id = s.id
  AND e.event_time >= s.log_partition
  AND e.event_time <  s.log_partition + interval '1 month'
WHERE s.id = $1;
```

Pruning becomes exact even for UUID session IDs.

## Monitoring pruning effectiveness

Log `EXPLAIN` plans in staging for every new analytics query. In production, track:

- `pg_stat_user_tables.n_tup_ins` per child partition — detect missing future partitions
- Query latency vs partition count — slope should stay flat as history grows
- `Partitions pruned` count from auto_explain samples

Enable `auto_explain.log_min_duration = 1000` temporarily after schema changes.

## When not to partition

Skip partitioning if:

- Total row count stays under ~50 million with comfortable index size
- Queries routinely span entire history without natural time bounds
- Team lacks automation for child partition creation

A massive single table with BRIN on `event_time` and aggressive partial indexes may outperform immature partitioning where someone forgets to create next month's child at 00:00 UTC.

## Summary

Partition pruning is not a feature you enable once — it is a contract between schema, query authors, and application APIs. Agent telemetry tables grow without sympathy for dashboard deadlines. Range-partition by time, always filter on the partition key in request-path SQL, store partition hints on session records for replay, and treat unbounded ORM queries as production hazards. Pruning turns partitioning from a storage gimmick into predictable query latency as your agent fleet scales.

## Resources

- [PostgreSQL declarative partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [PostgreSQL partition pruning details](https://www.postgresql.org/docs/current/ddl-partitioning.html#DDL-PARTITION-PRUNING)
- [pg_partman extension](https://github.com/pgpartman/pg_partman)
- [Timescale hypertables for time-series agent metrics](https://docs.timescale.com/use-timescale/latest/hypertables/)
- [PostgreSQL auto_explain module](https://www.postgresql.org/docs/current/auto-explain.html)
