---
title: "AI Agents: Feature Flag Database Changes"
slug: "agent-feature-flag-database-changes"
description: "Feature Flag Database Changes: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-12-28"
dateModified: "2024-12-28"
tags: ["AI", "Agent", "Feature"]
keywords: "agent, feature, flag, database, changes, ai, production, engineering, architecture"
faq:
  - q: "Can you ship a database migration and a feature flag in the same release?"
    a: "Yes, but only when the migration is strictly additive and backward-compatible — new nullable columns, new tables unused by old code, new indexes CONCURRENTLY. The flag controls read/write paths on the new schema; old code must run unchanged if the flag is off. Never combine destructive DDL (DROP, NOT NULL on existing rows, type narrowing) with a flag in one deploy."
  - q: "What is the correct order: flag first or migration first?"
    a: "Migration expand first, then deploy code that respects the flag, then enable the flag for a canary cohort, then migrate data, then contract schema in a later release. The anti-pattern is enabling a flag that writes new columns before the migration adds them — that causes runtime SQL errors on every canary request."
  - q: "How do feature flags interact with long-running agent sessions?"
    a: "Bind flag evaluation to session start or use sticky assignment so mid-session flag flips do not switch memory formats. Store schema_version on the session row; workers read version to pick serializers. If you must flip live, drain sessions gracefully or support dual-read on both old and new shapes until sessions complete."
  - q: "When should the feature flag come out after a DB migration succeeds?"
    a: "After contract phase completes: zero reads/writes on legacy columns, metrics flat for two release cycles, rollback no longer requires the old schema. Removing the flag is a separate PR from dropping columns — flags are cheap insurance during contract verification."
---
The team shipped `new_memory_format` behind a LaunchDarkly flag the same night they ran `ALTER TABLE agent_sessions ADD COLUMN memory_v2 JSONB`. Canary at 5% looked healthy until an old pod — still on yesterday's image without the migration-aware repository — handled a flagged user. `INSERT` referenced `memory_v2` on a code path that assumed the column existed; the pod's driver threw `column does not exist` because that replica had not restarted after DDL. Feature flags decouple **logic** from **schema** only when deploy order and expand-contract discipline are explicit.

Agent platforms change schema constantly: conversation memory shapes, tool registry versions, embedding dimensions, eval rubric tables. Feature flags let you route traffic to new behavior without redeploying. Database migrations change the persistence layer both code paths depend on. Combining them without a sequencing model produces the worst class of production bugs — partial writes, incompatible session state, and rollbacks that require restoring dropped columns. This piece covers the expand-flag-migrate-contract rhythm for agent storage.

## The coupling problem

Feature flags assume two code paths coexist. Database migrations often assume **one schema** at a time. The intersection rules:

| Migration type | Safe with flag? | Pattern |
|----------------|-----------------|---------|
| Add nullable column | Yes | Flag picks reader/writer |
| Add table | Yes | Flag gates access to new table |
| Backfill + switch | Yes | Flag controls read source after backfill |
| Rename column | No (in one step) | Expand: add new; flag; contract: drop old |
| Drop column | Only after contract | Flag must be 100% on new path first |
| Change JSON shape in place | No | Version column + dual serializers |

Treat schema like API versioning: additive first, consumers migrate, legacy retires.

## The four-phase release train

```
Release N   — EXPAND DDL (additive only)
Release N+1 — Code with flag OFF default; dual-write optional
Release N+2 — Flag ON for canary; backfill job; parity metrics
Release N+3 — Flag default ON; monitor
Release N+4 — CONTRACT DDL; remove flag branches
```

Never collapse expand and contract because a flag "protects" you. Flags guard **logic**; they do not un-drop columns.

## Example: agent memory format v2

**Goal:** replace flat `messages JSONB` with structured `memory_v2` including tool call envelopes and token counts.

### Phase 1 — Expand (migration only)

```sql
-- 20241228_001_expand_memory_v2.sql
ALTER TABLE agent_sessions
  ADD COLUMN IF NOT EXISTS memory_v2 JSONB,
  ADD COLUMN IF NOT EXISTS memory_schema_version SMALLINT NOT NULL DEFAULT 1;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_sessions_memory_v2
  ON agent_sessions (memory_schema_version)
  WHERE memory_schema_version >= 2;
```

Deploy migration to all environments. No application change required; old code ignores new columns.

### Phase 2 — Dual-path code behind flag

```typescript
// config/flags.ts
export async function useMemoryV2(sessionId: string): Promise<boolean> {
  const ctx = { key: sessionId, custom: { platform: "agent" } };
  return ldClient.variation("agent-memory-v2", ctx, false);
}

// repositories/session-memory.ts
export async function loadMemory(sessionId: string): Promise<Memory> {
  const row = await db.one(
    `SELECT messages, memory_v2, memory_schema_version
     FROM agent_sessions WHERE id = $1`,
    [sessionId],
  );

  const v2Enabled = await useMemoryV2(sessionId);

  if (v2Enabled && row.memory_v2) {
    return deserializeMemoryV2(row.memory_v2);
  }
  return deserializeLegacy(row.messages);
}

export async function saveMemory(sessionId: string, memory: Memory): Promise<void> {
  const v2Enabled = await useMemoryV2(sessionId);

  if (v2Enabled) {
    const payload = serializeMemoryV2(memory);
    await db.query(
      `UPDATE agent_sessions
       SET memory_v2 = $1,
           memory_schema_version = 2,
           messages = $2
       WHERE id = $3`,
      [payload, legacyShim(payload), sessionId],
    );
  } else {
    await db.query(
      `UPDATE agent_sessions SET messages = $1 WHERE id = $2`,
      [serializeLegacy(memory), sessionId],
    );
  }
}
```

Dual-write `messages` as a legacy shim so old pods and rollback paths keep working. The flag defaults **false** in production.

### Phase 3 — Backfill and parity checks

Run an async job keyed by `session_id` with idempotent upserts:

```python
# jobs/backfill_memory_v2.py
BATCH = 500

def backfill_batch(session_ids: list[str]) -> int:
    updated = 0
    for sid in session_ids:
        row = fetch_session(sid)
        if row.memory_schema_version >= 2 and row.memory_v2:
            continue
        v2 = convert_legacy_to_v2(row.messages)
        if not parity_check(row.messages, v2):
            log.warning("parity_mismatch", session_id=sid)
            continue
        execute(
            """
            UPDATE agent_sessions
            SET memory_v2 = %s, memory_schema_version = 2, messages = %s
            WHERE id = %s AND memory_schema_version = 1
            """,
            (v2, legacy_shim(v2), sid),
        )
        updated += 1
    return updated
```

Gate flag ramp on: backfill completion %, parity error rate < 0.01%, p95 write latency unchanged.

### Phase 4 — Contract

When metrics show 100% v2 reads for two weeks and no rollback:

```sql
-- Separate release from flag removal
ALTER TABLE agent_sessions DROP COLUMN messages;
-- Then remove legacy serializers and flag branches in application code
```

## Sticky assignment for long sessions

Random per-request flag evaluation breaks agent sessions mid-flight. Options:

**Session-scoped stickiness.** Evaluate flag once at `createSession`; store `memory_schema_version` on the row. Workers honor stored version over live flag for that session.

**User-level stickiness.** Hash `userId` into cohort for gradual rollout — same user always sees v2 during canary.

```typescript
export async function resolveMemoryVersion(session: SessionRow): Promise<2 | 1> {
  if (session.memory_schema_version >= 2) return 2;
  if (session.memory_schema_version === 1 && session.created_at < FLAG_CUTOFF) {
    return 1; // grandfather in-flight sessions
  }
  return (await useMemoryV2(session.id)) ? 2 : 1;
}
```

## Flag store vs database source of truth

Feature flag services (LaunchDarkly, Unleash, split.io) are **control plane**. PostgreSQL is **data plane**. Rules:

- Never store business data only in flag payloads.
- Cache flag evaluations locally with TTL; agent hot paths cannot block on LD outage — fail to default-off for write migrations.
- Log flag key + variation on every schema-touching write for audit.

## Testing matrix

| Test case | Expect |
|-----------|--------|
| Flag off, new code, post-expand DDL | Legacy path only; no v2 writes |
| Flag on, old code (simulated) | Must not crash — old code unaware of flag |
| Flag on, dual-write | Both columns populated; reads consistent |
| Mid-session flag flip with stickiness | Session stays on initial version |
| Rollback: flag off after partial backfill | Reads fall back to legacy column |

Run integration tests in CI against Docker Postgres applying migrations in order. Include a job that deploys `N-1` application against `N` schema (expand-only) — the common rolling-deploy reality.

## Operational dashboards

Track per flag variation:

- `agent_memory_write_total{version=1|2}`
- `agent_memory_deserialize_errors`
- `backfill_lag_sessions_remaining`
- SQL errors tagged `column_missing` (should be zero)

Alert when v2 error rate exceeds v1 baseline by any margin during canary.

## Security and compliance

Schema migrations behind flags still need change-control tickets. Audit who toggled production flags and when — tie to migration IDs. For regulated agents, prove that canary cohort selection does not correlate with protected attributes unless intentionally stratified for fairness eval.

## The takeaway

Feature flags and database migrations solve different problems; combining them requires expand-contract sequencing, session stickiness, dual-write shims, and separate releases for DDL expand and contract. Ship additive schema first, deploy flag-default-off code second, ramp with parity jobs and metrics third, drop legacy schema only when the flag has been fully on and stable. That rhythm lets agent platforms evolve memory and tool storage weekly without betting session integrity on a single deploy.

## Resources

- [Martin Fowler — Parallel Change (expand/contract)](https://martinfowler.com/bliki/ParallelChange.html)
- [LaunchDarkly — Release pipelines](https://docs.launchdarkly.com/home/releases/release-pipelines)
- [Unleash — Feature flag best practices](https://docs.getunleash.io/topics/feature-flags/feature-flag-best-practices)
- [PostgreSQL — CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [Flyway / Liquibase migration ordering guides](https://documentation.red-gate.com/fd)
- [Stripe — Safe database migrations (expand/contract)](https://stripe.com/blog/online-migrations)
