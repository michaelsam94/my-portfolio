---
title: "Replication Lag Monitoring"
slug: "llm-replication-lag-monitoring"
description: "Measure PostgreSQL and vector-store replication lag with agent-aware thresholds—so RAG answers, session memory, and tool audit trails do not read stale data after failover or read replica routing for teams running LLM features in production."
datePublished: "2024-12-10"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "PostgreSQL replication lag, read replica routing, pg_stat_replication, agent session consistency, RAG staleness, vector index sync"
faq:
  - q: "What replication lag threshold should block read replica queries for agent memory?"
    a: "For conversational agent memory and tool audit logs, route reads to the primary when lag exceeds 2 seconds or when the session performed a write in the last 30 seconds. RAG document retrieval can tolerate 30–60 seconds on catalog content if you surface as-of timestamps to users."
  - q: "Is bytes_lag or replay_lag the right PostgreSQL metric?"
    a: "Alert on replay_lag (time behind primary) for user-facing SLOs. Track write_lag and flush_lag separately for diagnostics—high write_lag implicates network or primary load; high flush_lag often means replica I/O saturation."
  - q: "How do you monitor lag for managed vector databases with opaque internals?"
    a: "Emit application-level heartbeat documents: write a canary row or vector on the primary, poll the replica until visible, record end-to-end propagation delay. Combine with vendor metrics when exposed; trust your canary when they disagree."
  - q: "Should agents fail closed when all replicas exceed lag budget?"
    a: "Fail closed for consistency-sensitive paths—billing, permission checks, destructive tool gates. Degrade gracefully for retrieval—fall back to primary with rate limits, or return cached answers with a staleness banner rather than silent wrong answers."
---
The agent told a customer their refund was approved. Finance's ledger on the read replica still showed pending—the write had not replayed yet. Support escalated; engineering blamed "eventual consistency" without metrics proving how eventual. Replication lag was invisible until we wired **time-based lag** into read routing and paging. The fix was not faster disks alone; it was treating lag as a first-class SLI every agent query path respects.

## Why agent workloads feel lag differently

Traditional web apps mostly read static catalog data. Agent stacks mix:

- **Session memory** — turns written after each tool call; next turn reads immediately
- **RAG corpora** — bulk ingested embeddings; minutes of lag may be acceptable
- **Permission snapshots** — must be fresh before executing paid tools
- **Audit trails** — compliance reads expect read-your-writes

One global "replica OK" flag lies. Tag each query with a **consistency class** and enforce lag budgets per class.

## PostgreSQL: measure lag that matches user pain

`pg_stat_replication` exposes lag in bytes and time depending on version:

```sql
SELECT
  application_name,
  client_addr,
  state,
  sync_state,
  pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
  EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) AS replay_lag_seconds
FROM pg_stat_replication;
```

Caveats engineers miss:

- `pg_last_xact_replay_timestamp()` is NULL on idle replicas—lag looks zero while disconnected.
- Bytes lag spikes during large index builds on replicas; time lag may stay flat until replay catches up.
- Logical replication lag uses different views (`pg_stat_subscription`, `pg_replication_slots`).

Export metrics every 10–15 seconds; sub-second scraping rarely helps and loads primaries.

```python
# Prometheus exporter sketch
def collect_pg_lag(conn):
    rows = conn.execute(REPLICATION_LAG_QUERY)
    for r in rows:
        yield GaugeMetric(
            "pg_replication_replay_lag_seconds",
            r.replay_lag_seconds or 0,
            labels={"replica": r.application_name},
        )
        if r.replay_lag_seconds is None and r.state != "streaming":
            yield CounterMetric("pg_replication_replica_unhealthy", 1, labels={"replica": r.application_name})
```

## Application canaries: end-to-end truth

Database views measure WAL replay—not necessarily **visibility** to your ORM connection pool:

```python
import uuid, time
from datetime import datetime, timezone

CANARY_TABLE = "replication_canary"

async def measure_e2e_lag(primary, replica) -> float:
    marker = str(uuid.uuid4())
    t0 = time.monotonic()
    await primary.execute(
        f"INSERT INTO {CANARY_TABLE} (marker, created_at) VALUES ($1, $2)",
        marker,
        datetime.now(timezone.utc),
    )
    while time.monotonic() - t0 < 30:
        row = await replica.fetchrow(
            f"SELECT 1 FROM {CANARY_TABLE} WHERE marker = $1", marker
        )
        if row:
            return time.monotonic() - t0
        await asyncio.sleep(0.05)
    raise TimeoutError("canary not visible on replica within 30s")
```

Run canaries per replica pool used by agent services. Chart p50/p95 **application lag** alongside PostgreSQL replay lag—the gap reveals connection pool stickiness bugs and caching layers pretending to be replicas.

## Read routing middleware

```typescript
type ConsistencyClass = "strong" | "session" | "catalog";

interface LagSnapshot {
  replicaName: string;
  replayLagSeconds: number;
  healthy: boolean;
}

const BUDGET: Record<ConsistencyClass, number> = {
  strong: 0,      // primary only
  session: 2,
  catalog: 60,
};

function pickReader(
  cls: ConsistencyClass,
  lags: LagSnapshot[],
  sessionHadWrite: boolean
): "primary" | string {
  if (cls === "strong" || sessionHadWrite) return "primary";
  const budget = BUDGET[cls];
  const candidates = lags.filter((l) => l.healthy && l.replayLagSeconds <= budget);
  if (candidates.length === 0) return "primary";
  return candidates.sort((a, b) => a.replayLagSeconds - b.replayLagSeconds)[0].replicaName;
}
```

Expose `sessionHadWrite` via request context set after any mutating tool in the same agent session—sticky read-your-writes without hammering primary on every turn.

## Vector stores and dual-write pipelines

Many RAG stacks write Postgres metadata on primary and enqueue embedding upserts async. Monitor **pipeline lag** separately:

```sql
CREATE TABLE ingestion_watermarks (
  document_id   text PRIMARY KEY,
  pg_committed_at timestamptz NOT NULL,
  vector_indexed_at timestamptz
);

-- Lag SLI: documents searchable vs committed
SELECT
  percentile_cont(0.95) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (vector_indexed_at - pg_committed_at))
  ) AS p95_index_lag_seconds
FROM ingestion_watermarks
WHERE pg_committed_at > now() - interval '1 hour'
  AND vector_indexed_at IS NOT NULL;
```

Agent answers citing documents where `vector_indexed_at IS NULL` are stale—block retrieval or downgrade confidence score.

## Alerting tiers

**Page:**

- Any production replica `replay_lag_seconds > 30` for 5 minutes
- Canary p95 > 10s for session-class pools
- All replicas unhealthy—agent read path pinned to primary above CPU threshold

**Ticket:**

- Single replica lagging—plan maintenance
- Catalog lag elevated during bulk reindex—expected, extend banner

Burn-rate alerts on agent errors `StaleReadError` if you emit them when routing refuses replicas.

## Failover and agent session stickiness

During promotion, lag metrics flip abruptly. Agent gateways should:

1. Drain in-flight requests with retryable errors
2. Invalidate replica pool DNS/cache
3. Force `strong` consistency for 60 seconds post-failover
4. Resume session stickiness after canary passes on new replica

Document this in runbooks—on-call should not manually restart agent pods unless primary connection storms persist.

## Dashboard layout that answers one question

Single pane for on-call:

| Panel | Query |
|-------|-------|
| Replay lag by replica | `pg_replication_replay_lag_seconds` |
| E2E canary p95 | `replication_canary_lag_seconds` |
| Primary CPU / WAL rate | infra metrics |
| Agent stale read errors | app counter |
| Vector index pipeline p95 | watermark SQL exported |

Green dashboard with red user errors means you measure the wrong thing—fix before next incident.

## Load tests that reproduce lag

Slow replica replay deliberately:

- Throttle replica disk I/O in staging
- Bulk ingest 1M agent audit rows while running conversational load
- Verify routing shifts traffic to primary before user-visible inconsistency

Replay tests beat theoretical SLOs.

## Logical replication and CDC pipelines

Agent audit events often fan out through Debezium or logical decoding to analytics and search. Monitor **slot lag** separately from physical replica lag:

```sql
SELECT slot_name, active,
       pg_wal_lsn_diff(pg_current_wal_lsn(), confirmed_flush_lsn) AS lag_bytes
FROM pg_replication_slots;
```

Inactive slots with growing lag_bytes will eventually fill disk on the primary—a failure mode that kills agent writes entirely. Alert on `NOT active` slots older than 24 hours and on lag_bytes growth rate, not just absolute lag.

Downstream consumers should expose `last_processed_lsn` metrics. Agent dashboards showing "live" analytics are lying if consumer lag is 20 minutes—label them with consumer freshness.

## Multi-region read paths

Global agent deployments tempt geo-routed read replicas. Session-class consistency across regions needs **primary writes in tenant home region** with local replica reads only when lag SLO holds. Cross-region replica lag routinely exceeds 200 ms—never use distant replicas for permission checks before tool execution.

During regional failover, replication lag metrics on the promoted region reset; run canaries before re-enabling session-class replica reads. Document RPO/RTO numbers finance and legal sign off on—agents quoting stale billing state have regulatory tail risk.

## ORM and pool pitfalls

Prisma, SQLAlchemy, and pgx poolers pin connections to replicas via separate DSNs. A common bug: write on primary DSN, read on replica DSN in the same request handler without passing `sessionHadWrite`. Code review checklist item: every repository method accepts explicit `ReadPreference`.

PgBouncer transaction pooling breaks `SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY` tricks—prefer application-level routing over session GUCs when pooling is enabled.

## Stale RAG answers users actually notice

When catalog-class replica reads serve outdated policy documents, agents confidently cite revoked refund rules. Mitigations beyond lag metrics:

- Embed `document_version` and `indexed_at` in chunk metadata returned to the LLM
- System prompt instructs the model to mention effective dates when versions conflict
- Block answers when `indexed_at` is older than published `policy.effective_date` on primary

Combine replication lag SLIs with **business staleness checks**—lag can be zero while embeddings lag hours behind Postgres commits.

## Resources

- [PostgreSQL Documentation — Monitoring replication](https://www.postgresql.org/docs/current/monitoring-stats.html#MONITORING-PG-STAT-REPLICATION-VIEW) — authoritative definitions of lag columns
- [AWS RDS — Monitoring read replication](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ReadRepl.html#USER_ReadRepl.Monitoring) — managed replica lag metrics and limitations
- [Google Cloud SQL — Replication lag](https://cloud.google.com/sql/docs/postgres/replication/replication-lag) — cross-region lag expectations
- [Patroni — High availability](https://patroni.readthedocs.io/en/latest/) — failover semantics affecting agent connection pools
- [OpenTelemetry — Database metrics semantic conventions](https://opentelemetry.io/docs/specs/semconv/database/database-metrics/) — standard labels for exporting lag SLIs
