---
title: "Zero-Downtime Database Migrations"
seoTitle: "Zero-Downtime Database Migrations: Expand-Contract Pattern"
slug: "zero-downtime-database-migrations"
description: "Zero-downtime migrations use expand-contract: add the new shape, dual-write, backfill, switch reads, then drop the old — no maintenance window required."
datePublished: "2026-05-20"
dateModified: "2026-07-17"
tags: ["Database", "Migrations", "DevOps", "Backend"]
keywords: "zero downtime migration, expand contract pattern, database migration, blue green deployment, schema migration, backwards compatible migration, online DDL"
faq:
  - q: "What is the expand-contract pattern?"
    a: "Expand-contract migrates a schema in three phases: expand (add new column/table without breaking old code), migrate data, then contract (remove old column/table once all code uses the new shape). Each phase is a separate deploy."
  - q: "Can I rename a column with zero downtime?"
    a: "Not in one step. Add the new column, dual-write to both, backfill, switch reads to the new column, then drop the old one. Four deploys, zero downtime."
  - q: "What database operations are safe to run in production?"
    a: "Adding nullable columns, adding tables, and adding indexes CONCURRENTLY are safe. Dropping columns, adding NOT NULL to existing columns, and renaming are not safe in a single step while traffic is live."
---

Zero-downtime database migrations are not about clever DDL tricks. They're about **never deploying a schema change and a code change in the same direction at the same time.** One side must always tolerate the other being behind. The expand-contract pattern — add the new, migrate the data, remove the old — is how you rename a column on a table that handles live charging sessions without a maintenance window. I've applied this on Postgres databases backing real-time systems where "stop the world for 20 minutes" means 20 minutes of drivers staring at a spinner at a charging station.

## Why migrations break production

The failure mode is always the same:

1. Deploy migration that renames `status` → `session_status`.
2. Old code (still running on half the instances during rolling deploy) queries `status`.
3. Database returns "column does not exist."
4. Incident.

Or the reverse: deploy code that reads `session_status` before the migration runs. Same crash, different order.

The fix is **backwards-compatible migrations** — every schema change must work with both the old code and the new code during the rolling deploy window.

## The expand-contract pattern

Every non-trivial migration follows three phases, each a separate deploy:

```
Phase 1: EXPAND          Phase 2: MIGRATE         Phase 3: CONTRACT
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│ Add new column   │     │ Dual-write both  │     │ Drop old column  │
│ Old code: uses   │ ──▶ │ Backfill data    │ ──▶ │ New code: uses   │
│ old column only  │     │ Switch reads     │     │ new column only  │
│ New code: not    │     │                  │     │                  │
│ deployed yet     │     │                  │     │                  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
   Deploy 1                Deploy 2 + 3              Deploy 4
```

### Example: rename `status` to `session_status`

**Deploy 1 — Expand:**

```sql
ALTER TABLE sessions ADD COLUMN session_status TEXT;
-- Old code still reads/writes `status`. New column exists but is unused.
```

**Deploy 2 — Dual-write (new code):**

```python
def update_session_status(session_id, new_status):
    db.execute(
        "UPDATE sessions SET status = %s, session_status = %s WHERE id = %s",
        (new_status, new_status, session_id)
    )
```

Old instances write `status` only. New instances write both. Both work.

**Deploy 3 — Backfill + switch reads:**

```sql
-- Backfill (run as batch job, not in migration)
UPDATE sessions SET session_status = status WHERE session_status IS NULL;

-- New code now reads session_status
```

```python
def get_session(session_id):
    row = db.fetchone("SELECT session_status, ... FROM sessions WHERE id = %s", session_id)
    return Session(status=row.session_status, ...)
```

**Deploy 4 — Contract:**

```sql
ALTER TABLE sessions DROP COLUMN status;
-- Only new code remains. Old column gone.
```

Four deploys. Zero downtime. No rollback panic.

## Safe vs unsafe operations

| Operation | Zero-downtime safe? | Approach |
|---|---|---|
| Add nullable column | Yes (instant) | Single deploy |
| Add column with default (Postgres 11+) | Yes (instant, no table rewrite) | Single deploy |
| Add index | Yes, with `CONCURRENTLY` | Run outside transaction |
| Add table | Yes | Single deploy |
| Rename column | **No** | Expand-contract (4 deploys) |
| Change column type | **No** | Add new column, migrate, drop old |
| Add NOT NULL constraint | **No** | Add nullable, backfill, then set NOT NULL |
| Drop column | **No** | Stop reading first (deploy), then drop (deploy) |
| Split table | **No** | Add new table, dual-write, migrate, drop old |

The pattern on the [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) session table: we never dropped a column until [feature flag telemetry](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) confirmed zero reads from old code paths — usually one full deploy cycle after the switch.

## Index creation without locking

A standard `CREATE INDEX` takes an exclusive lock and blocks writes. On a sessions table with active charging data, that's unacceptable.

```sql
-- Postgres: non-blocking index creation
CREATE INDEX CONCURRENTLY idx_sessions_charger_status
  ON sessions (charger_id, session_status)
  WHERE session_status = 'charging';
```

`CONCURRENTLY` means no exclusive lock, but:

- It takes longer than a regular index build.
- It cannot run inside a transaction (most migration tools wrap in transactions — override this).
- If it fails, you get an invalid index that must be dropped and recreated.

For large tables, create the index before you need it — during low-traffic hours, not during deploy.

## Migration tooling

Raw SQL migrations work. Tools that help:

- **Flyway / Liquibase** — versioned migrations with checksums. Good for teams that want explicit control.
- **Alembic (Python)** — autogenerate from models, but review every migration manually. Autogenerate does not know about expand-contract.
- **golang-migrate** — simple up/down SQL files. The `down` migration is your rollback plan.
- **Atlas / Prisma migrate** — schema diffing with drift detection.

Whatever you pick, enforce these rules in code review:

1. Every migration must be backwards-compatible with the currently deployed code.
2. Destructive changes (DROP, RENAME, ALTER TYPE) require a multi-phase plan in the PR description.
3. Data backfills run as separate batch jobs, not inside the migration transaction.
4. Migrations are tested against a production-size dataset in staging.

## Rollback strategy

Forward-only migrations are safer than reversible ones for expand-contract. During Phase 2 (dual-write), rolling back the *code* is safe — old code reads the old column, which still exists. Rolling back the *migration* during Phase 3 is dangerous — the old column may already be dropped.

Keep a rollback plan per phase:

| Phase | Code rollback safe? | Migration rollback safe? |
|---|---|---|
| Expand | Yes (old column untouched) | Yes (drop new column) |
| Dual-write | Yes (old code uses old column) | No (data in new column would be lost) |
| Switch reads | Risky (new reads, old column stale) | No |
| Contract | No (old column gone) | No |

This is why [trunk-based development with feature flags](https://blog.michaelsam94.com/feature-flags-trunk-based-development/) pairs well with migrations — you can switch read paths behind a flag and roll back the flag without rolling back the migration.

## When a maintenance window is okay

Zero-downtime migrations add complexity. For a pre-launch database with no production traffic, just rename the column. For a table with 500 rows that no real-time system reads, a 2-second lock is fine.

Save expand-contract for tables where downtime has a cost — session state, billing records, user accounts. The charging platform's `sessions` and `transactions` tables always got the full treatment. Configuration tables with 50 rows did not.

## Resources

- [Martin Fowler — Evolutionary Database Design](https://martinfowler.com/articles/evodb.html)
- [Prisma — Expand and Contract pattern](https://www.prisma.io/dataguide/types/expand-and-contract-pattern)
- [Stripe — Online migrations at scale](https://stripe.com/blog/online-migrations)
- [GitHub — Rails migrations at scale (patterns apply broadly)](https://github.blog/engineering/infrastructure-migrations/)
- [PostgreSQL — CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [Flyway documentation](https://flywaydb.org/documentation/)

## Operational checklist (1)

Before promoting Zero Downtime Database Migrations changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Zero Downtime Database Migrations after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Zero Downtime Database Migrations touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Zero Downtime Database Migrations changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Zero Downtime Database Migrations after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Zero Downtime Database Migrations touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.
