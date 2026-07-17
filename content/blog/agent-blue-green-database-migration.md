---
title: "AI Agents: Blue Green Database Migration"
slug: "agent-blue-green-database-migration"
description: "Blue-green database migrations for AI agent platforms — dual-write cutovers, schema versioning for embeddings tables, connection routing, and rollback paths that survive peak traffic."
datePublished: "2024-12-24"
dateModified: "2024-12-24"
tags: ["AI", "Agent", "Blue"]
keywords: "blue-green migration, database migration, zero downtime, agent memory store, dual write, schema migration, PostgreSQL cutover"
faq:
  - q: "When should AI teams use blue-green database migration instead of in-place ALTER?"
    a: "Use blue-green when migrations touch large tables (conversation history, embedding indexes, tool audit logs), require incompatible schema changes, or cannot tolerate write locks during peak agent traffic. In-place migrations are fine for additive nullable columns on small tables during maintenance windows."
  - q: "How do you keep agent memory consistent during a blue-green cutover?"
    a: "Run a dual-write period where every conversation turn, tool result, and embedding metadata writes to both blue and green schemas. Backfill historical rows asynchronously, verify row counts and checksums per tenant, then flip read traffic with a feature flag before decommissioning blue."
  - q: "What is the biggest rollback mistake in blue-green DB migrations?"
    a: "Flipping reads to green before dual-write is stable, then discovering green is missing hours of agent traces. Always keep blue writable and readable for rollback until green passes reconciliation gates — and never drop blue until a full backup restore drill succeeds."
  - q: "How long should the dual-write phase last for agent workloads?"
    a: "Long enough to cover your peak daily cycle plus one weekly batch job (embedding reindex, analytics export). For most production agent platforms that means 48–72 hours minimum, longer if you have global traffic with no true off-peak window."
---
The migration was supposed to be boring: add a JSONB column for tool-call payloads on the agent session table. In-place `ALTER` on PostgreSQL locked the table for eleven minutes during US morning traffic. Conversation writes queued, WebSocket heartbeats stacked, and on-call spent the rest of the day replaying dead-lettered tool results. The schema change was correct; the **cutover strategy** was not.

Agent platforms amplify ordinary database migration risk. Sessions are long-lived, writes are continuous, embeddings tables are huge, and "retry the request" does not undo a half-applied migration. Blue-green database migration — maintaining two parallel schema environments and shifting traffic deliberately — is how teams change the data plane without freezing the agents that depend on it.

## Blue-green for databases: what it actually means

Application blue-green usually means two deployable artifact versions. Database blue-green means two **schema-compatible data planes** (or two physical clusters) where:

- **Blue** serves current production traffic with the existing schema.
- **Green** receives replicated or dual-written data with the target schema.
- **Cutover** moves reads (then writes) to green via connection routing or proxy config.
- **Rollback** reverses the routing flag and continues on blue if green fails validation.

The agent-specific twist: you are not migrating a stateless API. You are migrating **durable agent state** — thread history, RAG cursor positions, pending human approvals, idempotency keys for tool executions.

## When blue-green beats expand-contract alone

Expand-contract (add column → dual-write → backfill → switch reads → drop old) works for many changes. Choose full blue-green when:

| Scenario | Why blue-green |
|----------|----------------|
| Embedding table partition redesign | Rebuild indexes offline on green; swap alias |
| Sharding key change | Cannot incrementally alter distribution on blue |
| Engine swap (Postgres → Cockroach) | Different replication semantics |
| Heavy JSON schema reshape | Backfill transforms CPU-saturate blue |

If your change is additive and backward-compatible, expand-contract on a single cluster is simpler. Do not blue-green for sport — operational surface area doubles.

## Architecture: routing layer

Never hardcode "the database" in agent workers. Introduce a **migration-aware datasource** that reads routing config from a control plane:

```typescript
type DbTarget = "blue" | "green" | "dual";

interface MigrationRouting {
  readTarget: DbTarget;
  writeTarget: DbTarget;
  dualWriteEnabled: boolean;
}

export class AgentSessionRepository {
  constructor(
    private blue: Pool,
    private green: Pool,
    private routing: () => MigrationRouting,
  ) {}

  private poolForRead(): Pool {
    const { readTarget } = this.routing();
    if (readTarget === "green") return this.green;
    if (readTarget === "blue") return this.blue;
    // dual read: prefer green with blue fallback — only after validation
    return this.green;
  }

  async insertTurn(sessionId: string, turn: AgentTurn): Promise<void> {
    const { writeTarget, dualWriteEnabled } = this.routing();
    const payload = serializeTurn(turn);

    if (writeTarget === "blue" || dualWriteEnabled) {
      await this.blue.query(
        `INSERT INTO agent_turns (session_id, payload, schema_ver) VALUES ($1, $2, 1)`,
        [sessionId, payload],
      );
    }
    if (writeTarget === "green" || dualWriteEnabled) {
      await this.green.query(
        `INSERT INTO agent_turns_v2 (session_id, payload, tool_calls, schema_ver) VALUES ($1, $2, $3, 2)`,
        [sessionId, payload.body, payload.toolCalls],
      );
    }
  }
}
```

Feature flags or config service keys (`db.migration.read=green`) let you flip cohorts — internal tenants first, then 5%, then 100% — without redeploying agents.

## Phase plan for agent data migrations

**Phase 0 — Inventory dependencies.** Map every writer: chat API, async summarizer, embedding pipeline, analytics CDC. Missing one writer causes silent drift.

**Phase 1 — Provision green.** Clone replication topology or restore snapshot + logical replication. Apply target DDL on green only.

**Phase 2 — Dual-write.** All agent paths write to both schemas. Reads still on blue. Monitor dual-write error rate separately — a 0.1% failure rate across millions of turns is thousands of orphaned rows.

**Phase 3 — Backfill.** Historical rows copy from blue to green with transform jobs chunked by `session_id` or time window. Track watermark in a migration metadata table.

**Phase 4 — Reconciliation.** Compare counts, checksums, and spot-check full session replays:

```sql
-- Per-tenant reconciliation query (simplified)
SELECT
  t.tenant_id,
  b.cnt AS blue_count,
  g.cnt AS green_count,
  ABS(b.cnt - g.cnt) AS delta
FROM tenants t
LEFT JOIN (
  SELECT tenant_id, COUNT(*) AS cnt FROM blue.agent_turns GROUP BY 1
) b USING (tenant_id)
LEFT JOIN (
  SELECT tenant_id, COUNT(*) AS cnt FROM green.agent_turns_v2 GROUP BY 1
) g USING (tenant_id)
WHERE ABS(b.cnt - g.cnt) > 0;
```

**Phase 5 — Read cutover.** Flip `readTarget` to green for canary tenants. Compare agent eval replay scores and p95 latency. Agents are sensitive to read latency spikes during connection pool churn.

**Phase 6 — Write cutover.** Disable blue writes; `writeTarget=green` only. Keep blue read-only for rollback window.

**Phase 7 — Decommission blue.** After retention period and successful restore drill, drop old schema or tear down cluster.

## Embeddings and vector indexes

Vector tables break naive copy migrations. Treat the embedding store as its own blue-green surface:

- Build green index from snapshot + CDC stream, not from live re-embed of entire corpus unless necessary.
- Use **index aliases** (`agent_chunks_active`) pointing at blue or green physical index.
- During cutover, pause embedding jobs or route them to both indexes with idempotent document IDs.

Re-embedding everything on cutover night is how teams miss SLA and ship stale retrieval for half the corpus.

## Agent-specific validation gates

Before each phase advance, run automated checks tied to agent behavior:

1. **Session replay** — Rehydrate 1,000 random sessions from green; verify tool-call ordering matches blue exports.
2. **RAG consistency** — Same query set; compare top-k doc IDs between blue and green retrieval (allow minor rank shuffle if scores within epsilon).
3. **Idempotency** — Replay tool execution IDs; green must dedupe identically to blue.
4. **Human-in-the-loop queue** — Pending approvals visible on both sides during dual-write.

Fail the gate → hold phase. Producing agents with missing tool traces is worse than delaying a migration.

## Rollback that actually works

Rollback is routing `readTarget=blue`, `writeTarget=blue`, `dualWriteEnabled=false`. Prerequisites:

- Blue stayed writable through Phase 5 (read cutover), or you accept data loss for green-only writes.
- Runbooks document **maximum green-only write window** — if exceeded, rollback requires merge script, not a flag flip.
- Connection pools pre-warmed on blue so flip does not cold-start thousands of agents.

Practice rollback in staging with production-shaped QPS. The flip itself should complete in under 60 seconds.

## Observability

Dashboard panels worth building before Phase 2:

- Dual-write success/failure rate by service
- Backfill lag (seconds behind head)
- Reconciliation delta by tenant
- Agent error rate correlated with migration phase annotations
- Pool wait time on green vs blue

Alert when reconciliation delta grows monotonically for 15 minutes — that indicates a missed writer, not transient lag.

## Connection pool and latency gotchas

Agent workers hold database connections longer than typical REST handlers because multi-step tool loops interleave reads between LLM calls. During cutover, doubling pools across blue and green can exhaust max connections on the server. Scale `max_connections` on green before Phase 2, then shrink blue pools gradually as traffic shifts. Watch `pg_stat_activity` wait events — `ClientRead` spikes often mean agents timing out mid-turn, not slow queries.

## Security and compliance

Dual environments mean dual access control reviews. Green clones inherit production data — encrypt at rest, restrict network paths, expire green credentials after decommission. Audit logs for migration flag changes (who flipped read traffic, when) belong in immutable storage for SOC2 and GDPR Article 30 records.

## The takeaway

Blue-green database migration for AI agents is a traffic-routing problem wrapped around a data reconciliation problem. Dual-write agent turns, backfill with verifiable checkpoints, cut over reads before writes, and keep blue alive until reconciliation proves green is complete. The schema change is the easy part; proving every conversation and tool trace survived the switch is what keeps agents trustworthy after deploy night.

## Resources

- [PostgreSQL logical replication documentation](https://www.postgresql.org/docs/current/logical-replication.html)
- [Expand and contract pattern (Martin Fowler)](https://martinfowler.com/bliki/ParallelChange.html)
- [Vitess schema migration strategies](https://vitess.io/docs/design-docs/vschema-migration/)
- [AWS Database Migration Service best practices](https://docs.aws.amazon.com/dms/latest/userguide/CHAP_BestPractices.html)
- [Flyway vs Liquibase migration versioning](https://documentation.red-gate.com/fd)
