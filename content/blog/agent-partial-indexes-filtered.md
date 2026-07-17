---
title: "AI Agents: Partial Indexes Filtered"
slug: "agent-partial-indexes-filtered"
description: "Filtered partial indexes keep agent memory and tool-run tables fast by indexing only hot rows — active sessions, pending approvals, and unsynced embeddings — without maintaining dead weight."
datePublished: "2024-12-01"
dateModified: "2024-12-01"
tags: ["AI", "Agent", "Partial"]
keywords: "partial index PostgreSQL, filtered index, agent memory schema, pgvector index, hot row indexing, agent session metadata"
faq:
  - q: "What is a partial (filtered) index in PostgreSQL?"
    a: "A partial index indexes only rows matching a WHERE predicate — for example `WHERE status = 'active'`. Queries that include the same predicate can use a smaller, faster index while cold archived rows stay on the heap unindexed."
  - q: "Why are partial indexes especially useful for agent workloads?"
    a: "Agent tables skew heavily toward a small hot set: open sessions, queued tool runs, and embeddings awaiting sync. The long tail of completed runs is huge but rarely queried. Partial indexes target the hot set without paying write amplification on every archived insert."
  - q: "Can I combine partial indexes with pgvector?"
    a: "Yes. Create a partial HNSW or IVFFlat index on `(embedding) WHERE status = 'ready' AND deleted_at IS NULL`. Queries must repeat those predicates in SQL or the planner may ignore the index."
  - q: "When should I avoid partial indexes?"
    a: "Skip them when query predicates drift constantly, when more than ~30% of rows match the filter anyway, or when ORMs generate SQL that omits the indexed predicate — an unused partial index is just maintenance overhead with extra confusion in EXPLAIN plans."
---
Agent platforms accumulate rows faster than intuition suggests. A single coding agent run inserts tool call records, retrieval traces, token accounting rows, and embedding queue entries. After ninety days, less than 2% of those rows answer production queries — yet they dominated index size on a project I debugged last winter, where every lookup on `session_id` scanned a bloated B-tree that mostly pointed at archived conversations.

Partial indexes — PostgreSQL calls them *partial*, SQL Server says *filtered*, the idea is the same — index **a slice of the table** defined by a predicate. For agent infrastructure, that slice is almost always the hot path: active sessions, pending work, live embeddings.

## Anatomy of agent table skew

Typical shapes:

| Table | Hot slice | Cold tail |
|-------|-----------|-----------|
| `agent_sessions` | `status IN ('active','awaiting_user')` | millions of `closed` |
| `tool_invocations` | `state = 'pending_approval'` | completed / failed history |
| `embedding_jobs` | `synced_at IS NULL` | successfully synced docs |
| `memory_facts` | `valid_until IS NULL OR valid_until > now()` | expired memories |

Without partial indexes, you choose between indexing everything (slow writes, fat indexes) or indexing nothing (slow reads on the hot slice). Partial indexes split the difference deliberately.

## Creating filtered indexes for session lookup

```sql
-- Full index (avoid): every closed session bloats the tree
-- CREATE INDEX agent_sessions_user_idx ON agent_sessions (user_id, updated_at DESC);

-- Partial: only sessions the agent runtime actually lists
CREATE INDEX CONCURRENTLY agent_sessions_user_active_idx
  ON agent_sessions (user_id, updated_at DESC)
  WHERE status IN ('active', 'awaiting_user');

-- Pending tool approvals — tiny index, high selectivity
CREATE INDEX CONCURRENTLY tool_invocations_pending_idx
  ON tool_invocations (session_id, created_at)
  WHERE state = 'pending_approval';
```

Application queries must mirror the predicate:

```sql
SELECT id, agent_name, updated_at
FROM agent_sessions
WHERE user_id = $1
  AND status IN ('active', 'awaiting_user')
ORDER BY updated_at DESC
LIMIT 20;
```

If a developer drops the `status` filter "to simplify the query," PostgreSQL falls back to a sequential scan or a less selective index. Code review should treat predicate omission as a performance bug.

## Partial indexes with pgvector

Vector search on all historical embeddings is wasteful when only `ready` rows are searchable:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

ALTER TABLE document_chunks
  ADD COLUMN embedding vector(1536),
  ADD COLUMN index_status text NOT NULL DEFAULT 'pending';

CREATE INDEX CONCURRENTLY document_chunks_embedding_ready_idx
  ON document_chunks
  USING hnsw (embedding vector_cosine_ops)
  WHERE index_status = 'ready' AND deleted_at IS NULL;
```

Retrieval query:

```sql
SELECT chunk_id, doc_id, 1 - (embedding <=> $1::vector) AS score
FROM document_chunks
WHERE index_status = 'ready'
  AND deleted_at IS NULL
  AND tenant_id = $2
ORDER BY embedding <=> $1::vector
LIMIT 10;
```

When a chunk is soft-deleted, it falls out of the partial index automatically on the next vacuum — no separate vector deletion job unless your provider requires explicit tombstone handling.

## Predicate design rules

**Match real query filters, not aspirational ones.** The predicate should appear in every production query that needs the index. If analytics sometimes scans all statuses, give analytics a separate reporting replica — do not widen the partial predicate to accommodate rare reports.

**Prefer stable enum values over time functions.** `WHERE status = 'active'` is planner-friendly. `WHERE last_seen > now() - interval '7 days'` works but requires index definitions that align with how you express the filter, and autovacuum stats get noisier.

**Keep predicates sargable.** Avoid functions on indexed columns inside the partial WHERE unless you also express queries identically.

**Watch selectivity.** Partial indexes shine when the filtered set is under ~10–20% of the table. Beyond ~30%, a full index is often simpler and nearly as small relative to heap size.

## Measuring before and after

Workflow that caught a silent regression:

```sql
EXPLAIN (ANALYZE, BUFFERS)
SELECT id FROM agent_sessions
WHERE user_id = 'usr_abc'
  AND status IN ('active', 'awaiting_user')
ORDER BY updated_at DESC
LIMIT 20;
```

Before partial index: `Seq Scan` with filter removing 480,000 rows. After: `Index Scan using agent_sessions_user_active_idx` with `Buffers: shared hit=4`.

Track index size:

```sql
SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid))
FROM pg_stat_user_indexes
WHERE relname = 'agent_sessions';
```

The partial index should be orders of magnitude smaller than a full `(user_id, updated_at)` index on the same table.

## Write amplification and ingest pipelines

Each index adds work on INSERT/UPDATE. Partial indexes reduce that work for cold rows:

- Archiving a session (`status = 'closed'`) removes it from the partial index on the next update — one index touch instead of maintaining a hot-tree entry forever.
- Completed embedding jobs stop touching the HNSW graph once `index_status` flips to `ready`... actually wait, they stay in the ready index. Better pattern: move synced jobs to `index_status = 'archived'` excluded from the partial index, keeping the HNSW graph small.

```sql
UPDATE embedding_jobs
SET index_status = 'archived', synced_at = now()
WHERE id = $1;
```

Batch archival jobs prevent the hot partial index from creeping toward full-table coverage.

## ORM footguns

Django example — force the filter into the queryset manager:

```python
class ActiveSessionManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(
            status__in=["active", "awaiting_user"]
        )

class AgentSession(models.Model):
    objects = models.Manager()  # full table for admin
    active = ActiveSessionManager()

    class Meta:
        indexes = [
            models.Index(
                fields=["user_id", "-updated_at"],
                name="sessions_user_active_idx",
                condition=models.Q(status__in=["active", "awaiting_user"]),
            )
        ]
```

Prisma and TypeORM lack native partial index DSL — use migration SQL. Document the predicate in a comment block above the model so the next migration does not accidentally recreate a full index with the same name.

## Unique constraints on hot subsets

Partial **unique** indexes enforce invariants only where they matter:

```sql
-- One active run per session
CREATE UNIQUE INDEX CONCURRENTLY one_active_run_per_session
  ON agent_runs (session_id)
  WHERE finished_at IS NULL;
```

This beats application-level checks race-prone under concurrent tool loops.

## Monitoring and maintenance

Alert when:

- `idx_scan` on partial indexes flatlines while related endpoint latency climbs — predicate mismatch
- Partial index size approaches full index size — hot slice definition is too wide
- Autovacuum lag on tables with heavy partial index updates during bulk imports

Reindex partial indexes after large bulk status flips (`UPDATE ... SET status = 'closed' WHERE ...` touching 40% of rows). `REINDEX INDEX CONCURRENTLY` avoids long write locks.

## Comparison to partitioning

Partitioning splits physical storage by key; partial indexes filter logically within one table. They complement each other:

- Partition by month for retention drops
- Partial index within the current month partition for `status = 'active'`

Do not partition solely for hot/cold when a partial index solves read latency with less operational overhead.

## Worked example: agent memory facts table

Consider `memory_facts` where agents store extracted preferences (`"user prefers dark mode"`) with optional expiry:

```sql
CREATE TABLE memory_facts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id   text NOT NULL,
  tenant_id    text NOT NULL,
  fact_key     text NOT NULL,
  fact_value   text NOT NULL,
  valid_until  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Hot path: fetch live facts for prompt assembly
CREATE INDEX CONCURRENTLY memory_facts_session_live_idx
  ON memory_facts (session_id, fact_key)
  WHERE valid_until IS NULL OR valid_until > now();

-- Hot path: tenant-scoped dedupe while fact is live
CREATE UNIQUE INDEX CONCURRENTLY memory_facts_dedupe_live_idx
  ON memory_facts (tenant_id, session_id, fact_key)
  WHERE valid_until IS NULL;
```

Prompt assembly query:

```sql
SELECT fact_key, fact_value
FROM memory_facts
WHERE session_id = $1
  AND (valid_until IS NULL OR valid_until > now());
```

When a fact expires, a nightly job sets `valid_until = now()` on stale rows. Those rows fall out of the partial index on update — no explicit index delete step. Expired facts remain queryable for audit via sequential scan on reporting replicas with different indexes, keeping OLTP paths lean.

## Bottom line

Filtered partial indexes are a precision instrument for agent metadata tables where the hot row count is tiny and the historical pile is enormous. Define predicates from production query text, verify with `EXPLAIN ANALYZE`, and treat ORM queries that omit the filter as defects. The index maintenance you do not do on archived agent runs is latency budget returned to live sessions.

## Resources

- [PostgreSQL partial indexes documentation](https://www.postgresql.org/docs/current/indexes-partial.html)
- [pgvector indexing options](https://github.com/pgvector/pgvector#indexing)
- [PostgreSQL EXPLAIN guide](https://www.postgresql.org/docs/current/using-explain.html)
- [Use The Index, Luke — partial indexes](https://use-the-index-luke.com/sql/where-clause/partial-indexes)
- [PostgreSQL index-only scans and visibility map](https://www.postgresql.org/docs/current/indexes-index-only-scans.html)
