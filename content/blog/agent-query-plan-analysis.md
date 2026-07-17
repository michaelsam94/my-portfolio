---
title: "AI Agents: Query Plan Analysis"
slug: "agent-query-plan-analysis"
description: "How to read EXPLAIN plans for agent tool queries, catch sequential scans on vector metadata tables, and wire plan telemetry into your observability stack before latency spikes hit users."
datePublished: "2024-11-26"
dateModified: "2024-11-26"
tags: ["AI", "Agent", "Query"]
keywords: "EXPLAIN ANALYZE agent queries, PostgreSQL query plan, agent tool SQL latency, index advisor RAG metadata, sequential scan detection"
faq:
  - q: "When should an agent pipeline run EXPLAIN on generated SQL?"
    a: "Run EXPLAIN (not necessarily ANALYZE) on every new tool schema in CI, and run EXPLAIN ANALYZE on sampled production queries weekly. Agent-generated SQL varies by phrasing; a plan that looked fine in staging may regress when the model chooses a different join order after a prompt update."
  - q: "What is the most common bad plan in agent retrieval stacks?"
    a: "Nested loop over a large filtered result because the planner underestimated selectivity on JSONB metadata filters (tenant_id, document_status). The fix is usually a partial index matching the agent's default WHERE clause, not rewriting the LLM prompt."
  - q: "Should agents be allowed to run ANALYZE or CREATE INDEX?"
    a: "No. Give agents read-only roles with statement_timeout and a row limit. Plan analysis belongs in your middleware: parse the query, EXPLAIN in a sandbox replica, reject or rewrite before execution. Letting the model mutate schema is an incident waiting to happen."
  - q: "How do you alert on plan regressions without parsing every query?"
    a: "Track pg_stat_statements mean_exec_time and shared_blks_read per normalized query fingerprint. Alert when p95 latency doubles or shared_blks_read jumps 10x for the same fingerprint. Pair with auto_explain for queries exceeding 500ms."
---

The support ticket said the agent was "slow sometimes." p50 latency on the tool-calling path looked fine. p99 told a different story: three seconds on `search_documents`, then 40ms on everything else. The agent wasn't hallucinating — it was issuing perfectly valid SQL that PostgreSQL chose to answer with a sequential scan across 18 million embedding metadata rows because `status = 'published'` wasn't selective enough after last week's bulk import.

Query plan analysis for agent systems is not database DBA cosplay. It is how you keep autonomous tool loops from amplifying a bad join into a quota-burning retry storm.

## What agents do to your query planner

Traditional apps emit SQL from hand-written repositories. Agents emit SQL from natural language, often with:

- **Dynamic filters** — optional JSONB predicates the planner sees for the first time at runtime
- **Wide SELECT lists** — the model asks for `SELECT *` unless you constrain the tool schema
- **Repeated similar queries** — each turn may re-run retrieval with slightly different LIMIT or ORDER BY
- **Fan-out** — one user message triggers five tool calls, each hitting the same table differently

The planner caches statistics, not intentions. When the model shifts from `WHERE tenant_id = $1 AND tag = 'policy'` to `WHERE tenant_id = $1 AND metadata->>'department' = 'legal'`, you may fall off an index cliff without any schema migration.

## Reading EXPLAIN like an on-call engineer

Start with `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` on production-shaped data volumes, not empty dev tables.

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT d.id, d.title, d.chunk_text
FROM document_chunks d
JOIN documents doc ON doc.id = d.document_id
WHERE doc.tenant_id = 'tn_8f2a'
  AND doc.status = 'published'
  AND d.embedding <=> $1::vector < 0.35
ORDER BY d.embedding <=> $1::vector
LIMIT 20;
```

Red flags in agent workloads:

| Node type | Symptom | Typical agent cause |
|-----------|---------|---------------------|
| Seq Scan on large heap | Buffers: shared read in thousands | Missing partial index on `(tenant_id, status)` |
| Nested Loop + Seq Scan inner | Loops: 50000+ | FK join where inner side lacks index |
| Sort + Limit | Sort Method: external merge Disk | ORDER BY expression not indexed |
| Bitmap Heap Scan with high rows removed | Rows Removed by Filter high | JSONB path filter not indexed |

The vector distance operator often dominates cost. If you see an index scan on `embedding` followed by a filter that rejects 90% of rows, your **post-index filter** is the problem — tighten the WHERE clause in the tool definition or add a composite access path.

## Middleware: plan gate before execution

Never trust the model to self-correct slow SQL. Insert a plan review step in your tool executor:

```typescript
type PlanVerdict = "allow" | "rewrite" | "reject";

interface PlanGateConfig {
  maxSeqScanRows: number;
  maxEstimatedCost: number;
  forbiddenNodes: string[];
}

async function gateQuery(
  sql: string,
  params: unknown[],
  cfg: PlanGateConfig
): Promise<{ verdict: PlanVerdict; plan: string; sql: string }> {
  const planRows = await sandboxDb.query(
    `EXPLAIN (FORMAT JSON) ${sql}`,
    params
  );
  const plan = planRows[0]["QUERY PLAN"][0];

  const seqScan = findNode(plan, (n) => n["Node Type"] === "Seq Scan");
  if (seqScan && (seqScan["Plan Rows"] ?? 0) > cfg.maxSeqScanRows) {
    return {
      verdict: "reject",
      plan: JSON.stringify(plan, null, 2),
      sql,
    };
  }

  if ((plan["Total Cost"] ?? 0) > cfg.maxEstimatedCost) {
    const rewritten = injectTenantPredicate(sql); // deterministic rewrite
    return { verdict: "rewrite", plan: JSON.stringify(plan, null, 2), sql: rewritten };
  }

  return { verdict: "allow", plan: JSON.stringify(plan, null, 2), sql };
}
```

Run EXPLAIN against a **sandbox replica** with production statistics (or use `hypopg` for hypothetical indexes in CI). `EXPLAIN ANALYZE` mutates nothing but executes the query — use it only on sampled, rate-limited traffic with read-only roles.

## Instrumentation that catches regressions early

Wire these into the same dashboard as agent token usage:

```sql
-- pg_stat_statements: top agent tool fingerprints
SELECT
  queryid,
  left(query, 120) AS sample,
  calls,
  mean_exec_time,
  shared_blks_read,
  rows
FROM pg_stat_statements
WHERE query LIKE '%document_chunks%'
ORDER BY mean_exec_time * calls DESC
LIMIT 20;
```

Enable `auto_explain.log_min_duration = 500` and ship logs to your trace backend. Tag spans with `tool_name`, `tenant_id`, and `query_fingerprint` so you can correlate a prompt deploy with a plan change.

For vector-heavy paths, also track **buffers hit ratio** per tool. Agent retrieval that suddenly reads from disk usually means the working set outgrew `shared_buffers` — a capacity signal, not a model quality signal.

## Fixing plans without disabling tools

Ordered remediation that works in production:

1. **Constrain the tool schema** — require `tenant_id`, cap `LIMIT`, ban `SELECT *`, whitelist columns
2. **Add partial indexes** matching default agent filters: `WHERE status = 'published'`
3. **Refresh statistics** after bulk loads — agents hit stale stats more painfully than batch ETL because traffic is bursty
4. **Rewrite prompts last** — prompt changes are non-deterministic; indexes are deterministic

```sql
CREATE INDEX CONCURRENTLY idx_chunks_tenant_published
ON document_chunks (tenant_id, document_id)
WHERE EXISTS (
  SELECT 1 FROM documents d
  WHERE d.id = document_chunks.document_id
    AND d.status = 'published'
);
```

When the agent needs ad-hoc analytics ("count documents by department this quarter"), route to a **read replica or OLAP sink**, not the OLTP path used for RAG. Mixing analytical plans into sub-100ms retrieval SLOs guarantees pain.

## Closing the loop with evals

Add plan-aware checks to your agent eval suite:

- Golden questions must stay under latency budget **and** under buffer read threshold
- Fail CI if EXPLAIN shows Seq Scan on tables over your row threshold
- Store `{question, sql, plan_hash, latency_ms}` for every eval run to diff across model versions

Query plan analysis is unglamorous work. It is also the difference between an agent platform that scales with document count and one where every new customer corpus triggers a latency incident you debug at 2 a.m. by squinting at `EXPLAIN` output in a pager.

## Case study: when the vector index lies

A team shipped HNSW indexes on `embedding` columns and celebrated sub-10ms ANN queries in isolation. Production agent latency stayed at 800ms. EXPLAIN showed the planner choosing a **Bitmap Index Scan** on `(tenant_id)` first, fetching 40,000 chunk IDs, then filtering by vector distance in memory — because the agent's default query always included `tenant_id = $1` and the planner judged that predicate more selective than the approximate nearest-neighbor probe.

The fix was not "better embeddings." They added a two-stage pattern in the tool layer:

```sql
-- Stage 1: cheap candidate set (indexed)
WITH candidates AS (
  SELECT id, embedding
  FROM document_chunks
  WHERE tenant_id = $1 AND document_id = ANY($2::uuid[])
  LIMIT 500
)
-- Stage 2: vector sort on small set
SELECT id, embedding <=> $3 AS dist
FROM candidates
ORDER BY dist
LIMIT 20;
```

Stage one used a partial index on `(tenant_id, document_id)`. Stage two sorted hundreds of rows, not millions. Agent p95 dropped from 820ms to 45ms without changing the model or prompt.

This pattern generalizes: **pre-filter with btree indexes, rank with vector indexes on the reduced set**. Let EXPLAIN confirm the planner isn't reversing that order because of stale `ANALYZE` stats on `tenant_id`.

## CI gate: fail builds on plan regressions

Wire plan checks into the tool-schema test suite:

```yaml
# .github/workflows/agent-tools.yml (excerpt)
- name: Explain golden queries
  run: |
    psql "$TEST_DATABASE_URL" -f tests/golden/agent_retrieval.sql
    python scripts/check_plans.py \
      --max-seq-scan-rows 10000 \
      --forbidden "Seq Scan on document_chunks"
```

`check_plans.py` parses `EXPLAIN (FORMAT JSON)` output and exits non-zero when forbidden nodes appear. Golden SQL files live next to tool definitions — when an engineer adds a new filter column to the tool schema, CI forces them to add an index migration in the same PR.

Store historical plan JSON in object storage keyed by git SHA. Diffing plans across releases surfaces "we didn't change SQL but the planner changed its mind" cases tied to PostgreSQL minor upgrades or statistics drift.

## Resources

- [PostgreSQL EXPLAIN documentation](https://www.postgresql.org/docs/current/sql-explain.html)
- [pg_stat_statements extension](https://www.postgresql.org/docs/current/pgstatstatements.html)
- [HypoPG — hypothetical indexes for plan testing](https://hypopg.readthedocs.io/en/latest/)
- [auto_explain module](https://www.postgresql.org/docs/current/auto-explain.html)
- [pgvector index tuning guide](https://github.com/pgvector/pgvector#indexing)
