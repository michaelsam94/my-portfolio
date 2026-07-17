---
title: "AI Agents: Expand Contract Migrations"
slug: "agent-expand-contract-migrations"
description: "Expand Contract Migrations: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-12-26"
dateModified: "2024-12-26"
tags: ["AI", "Agent", "Expand"]
keywords: "agent, expand, contract, migrations, ai, production, engineering, architecture"
faq:
  - q: "What are expand-contract migrations?"
    a: "A three-phase pattern for zero-downtime schema change: Expand (add new column/table/index without breaking old code), Migrate (dual-write or backfill until new path owns data), Contract (remove old column/code once nothing reads it). You never rename-in-place or drop-before-migrate—each phase is independently deployable and reversible."
  - q: "Why do agent platforms need this more than CRUD apps?"
    a: "Agent stacks accumulate fast-moving schema: conversation memory formats, tool registry versions, embedding dimensions, eval rubrics, and prompt template bindings. Deploys happen daily; sessions run for hours. A breaking migration mid-flight corrupts in-progress agent state. Expand-contract lets old workers finish on old schema while new workers adopt new fields."
  - q: "How long should the expand phase last?"
    a: "Until all running code paths tolerate the new schema and backfill is complete—often 1–3 release cycles for agent systems. Do not contract until metrics show zero reads of deprecated columns (log or query audit), integration tests pass without legacy fields, and no rollback plan requires the old shape. Rushing contract is how you brick rollback during an incident."
  - q: "How does expand-contract apply to prompt and config changes?"
    a: "Same logic, softer schema: expand by adding prompt template v2 alongside v1 with a flag; migrate by routing cohorts to v2; contract by retiring v1 after eval proves parity. For vector indexes, expand means a new index with new dimensions; migrate means dual-write embeddings; contract means dropping the old index after retrieval quality holds."
---
The Friday deploy added `tool_result_schema_version` to `agent_steps` and dropped `raw_tool_output` in the same migration. Rolling deploy hit mixed versions: new pods wrote only the versioned column; old pods still reading `raw_tool_output` returned null to the orchestrator. Live sessions lost tool context mid-run and started hallucinating inventory counts. Rollback failed because the down migration could not restore dropped JSONB for rows written after cutover.

Database migrations for agent platforms fail differently than for stateless APIs. Sessions are long-lived. Workers version-skew during every deploy. Prompt and embedding schemas change weekly. Expand-contract—add before remove, dual-write before switch, verify before drop—is the discipline that lets you evolve agent storage without betting the fleet on a single ALTER.

## The three phases

```
Phase 1 — EXPAND          Phase 2 — MIGRATE           Phase 3 — CONTRACT
─────────────────         ─────────────────           ──────────────────
Add new column/table      Backfill + dual-read/write  Drop old column
Old code ignores it       Feature flag picks path     Remove dead code
Deploy anytime            Measure parity              Only when safe
```

Each phase is a separate PR and deploy. Never combine expand and contract in one release unless traffic is fully stopped—which is not zero-downtime.

## Example: evolving agent step storage

**Today:** `agent_steps.result` is unstructured JSONB.

**Goal:** typed `result_v2` with schema version for safer tool parsing.

### Phase 1 — Expand

```sql
-- migration_001_expand.sql
ALTER TABLE agent_steps
  ADD COLUMN result_v2 JSONB,
  ADD COLUMN result_schema_version SMALLINT DEFAULT 1;

-- No NOT NULL yet; old code unaffected
CREATE INDEX CONCURRENTLY idx_agent_steps_v2
  ON agent_steps (result_schema_version)
  WHERE result_schema_version >= 2;
```

Deploy application code that **writes both** columns on new steps only (optional dual-write starts here) or waits until phase 2—expand alone must not break readers.

### Phase 2 — Migrate

Application changes:

```typescript
// repositories/agent-step.ts
const USE_RESULT_V2 = process.env.FF_RESULT_V2 === "true";

export async function saveStepResult(stepId: string, result: ToolResult): Promise<void> {
  const v2Payload = toResultV2(result);

  if (USE_RESULT_V2) {
    await db.query(
      `UPDATE agent_steps
       SET result_v2 = $1, result_schema_version = 2, result = $2
       WHERE id = $3`,
      [v2Payload, legacyShim(v2Payload), stepId], // dual-write shim for old readers
    );
  } else {
    await db.query(
      `UPDATE agent_steps SET result = $1 WHERE id = $2`,
      [legacyFormat(result), stepId],
    );
  }
}

export function readStepResult(row: AgentStepRow): ToolResult {
  if (row.result_schema_version >= 2 && row.result_v2) {
    return fromResultV2(row.result_v2);
  }
  return fromLegacy(row.result);
}
```

Backfill job for historical rows:

```python
# jobs/backfill_result_v2.py
BATCH = 500

def backfill(conn):
    while True:
        rows = conn.execute(
            """
            SELECT id, result FROM agent_steps
            WHERE result_schema_version = 1 AND result_v2 IS NULL
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (BATCH,),
        ).fetchall()
        if not rows:
            break
        for row in rows:
            v2 = convert_to_v2(row.result)
            conn.execute(
                """
                UPDATE agent_steps
                SET result_v2 = %s, result_schema_version = 2
                WHERE id = %s
                """,
                (v2, row.id),
            )
        conn.commit()
```

Enable `FF_RESULT_V2` for 5% of tenants, compare tool-parse error rates, ramp to 100%. Monitor `legacy_result_reads_total`—should trend to zero on write path; reads may still hit legacy until all rows backfilled.

### Phase 3 — Contract

Only when backfill complete and no code reads `result` without fallback:

```sql
-- migration_003_contract.sql — separate release, weeks later
ALTER TABLE agent_steps DROP COLUMN result;
ALTER TABLE agent_steps ALTER COLUMN result_v2 SET NOT NULL;
```

Remove `legacyShim`, `fromLegacy`, and feature flag in the same deploy as contract migration. Order: deploy code that stops writing `result` → verify → drop column.

## Expand-contract for vector embedding dimensions

Model upgrade changes embedding size 1536 → 3072. You cannot ALTER the vector column in place on pgvector without rebuild.

**Expand:** Create `documents_embedding_v2` table or new Pinecone index `prod-v2`.

**Migrate:** Dual-write new embeddings on ingest; background re-embed corpus; retrieval uses weighted blend or shadow-read v2 comparing recall@k.

**Contract:** Flip retrieval flag to v2-only; delete v1 index after 30-day fallback window.

```typescript
async function embedAndStore(doc: Document): Promise<void> {
  const [v1, v2] = await Promise.all([
    embedModelV1(doc.text),
    embedModelV2(doc.text),
  ]);
  await Promise.all([
    vectorStoreV1.upsert(doc.id, v1),
    vectorStoreV2.upsert(doc.id, v2),
  ]);
}
```

Agent answer quality regressions during migrate show up in eval dashboards before you drop v1.

## Prompt template versioning (schema-less expand-contract)

Not every migration is SQL. Prompt templates follow the same rhythm:

| Phase | Action |
|-------|--------|
| Expand | Add `billing_agent_v2.prompt` in registry; v1 remains default |
| Migrate | Route 10% traffic via `template_id` flag; run side-by-side eval |
| Contract | Remove v1 from registry; reject sessions referencing old ID |

Store `template_version` on each session event (event sourcing) or `agent_sessions.prompt_version` so replay and audit know which template produced which behavior.

## Flyway/Liquibase discipline

Number migrations explicitly:

```
V001__expand_result_v2.sql
V002__add_index_result_v2.sql   -- CONCURRENTLY in prod
-- app deploys with dual-read/write between V001 and V003
V003__contract_drop_result.sql
```

Rules:

- **Never edit applied migrations.** New phase = new file.
- **CONCURRENTLY** for indexes on large agent tables—sessions do not pause for `ACCESS EXCLUSIVE`.
- **Reversible expand** always; contract migrations are intentionally irreversible—treat as ceremony with checklist.

## Coordination across services

Agent stacks split across orchestrator, tool workers, retrieval service, and billing consumer. Schema contracts are API contracts:

1. Publish OpenAPI/Protobuf with **additive** fields only during expand.
2. Consumers ignore unknown fields (forward compatibility).
3. Producers populate both old and new field names during migrate (duplicate data is temporary tax).
4. Announce contract date in `#eng-releases`; block deploys that reference dropped fields via CI schema diff.

```yaml
# ci/schema-compat.yml
- name: Check breaking proto changes
  run: buf breaking --against '.git#branch=main'
```

## Rollback strategy per phase

| Phase | Rollback |
|-------|----------|
| Expand | Remove new column only if unused; safe if app ignores it |
| Migrate | Flip feature flag off; dual-written data still in old column |
| Contract | **Cannot restore dropped data** — restore from backup or delay contract |

This asymmetry is why contract waits weeks. If you drop `raw_tool_output` and need rollback, you are restoring snapshots—not running `DOWN` migration.

## Observability during migrate

Track:

- `dual_write_skipped_total` — bug if non-zero during migrate
- `backfill_lag_rows` — remaining rows without v2
- `read_path_legacy_total` vs `read_path_v2_total`
- Agent task success rate split by flag cohort

Alert if legacy read path increases after contract deploy—that signals a missed consumer.

## Testing migrations

**Testcontainers with production-sized fixtures.** Apply V001, run app, apply V002 logic, assert reads work both ways.

**Rollback drill.** Deploy expand only; roll back app; confirm old app still works.

**Contract rehearsal in staging.** Run V003 against staging clone; verify no 500s in integration suite.

Property: for every row, `read(read(write(x)))` preserves semantic equality across v1 and v2 parsers.

## Anti-patterns

**Big bang rename.** `RENAME COLUMN result TO result_deprecated` breaks old pods instantly.

**NOT NULL on day one.** Backfill has not run; deploy inserts fail.

**Contract in Friday deploy.** No engineers to fix skewed workers.

**Shared JSON blob without version field.** You cannot expand-contract what you cannot detect.

## The takeaway

Expand-contract migrations treat schema evolution as a multi-release project, not a single SQL file. Add new shapes before removing old ones, dual-write and backfill with feature flags, measure parity on agent outcomes—not just migration job success—and contract only when rollback no longer needs the deprecated path. Agent systems change too fast for destructive ALTER bravery; they need migrations as boring and reversible as the rest of production engineering.

## Resources

- [Martin Fowler — Evolutionary Database Design](https://martinfowler.com/articles/evodb.html)
- [expand/contract pattern (Pramod Sadalage)](https://www.martinfowler.com/bliki/ParallelChange.html)
- [Flyway migrations best practices](https://flywaydb.org/documentation/concepts/migrations)
- [PostgreSQL CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [StrongDM — Zero-downtime Postgres migrations](https://www.strongdm.com/blog/zero-downtime-postgres-migrations)
