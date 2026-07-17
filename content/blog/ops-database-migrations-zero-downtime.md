---
title: "Zero-Downtime Migrations in CD"
slug: "ops-database-migrations-zero-downtime"
description: "Run database migrations in CI/CD without downtime: expand-contract pattern, migration ordering, backward-compatible deploys, and tooling with Flyway and Liquibase."
datePublished: "2026-01-06"
dateModified: "2026-07-17"
tags: ["DevOps", "Database", "CI/CD", "SRE"]
keywords: "zero downtime migration, database CI CD, expand contract pattern, Flyway migrations, backward compatible schema"
faq:
  - q: "Can you run database migrations during a rolling deployment?"
    a: "Only if migrations are backward compatible with the previous app version. Add columns as nullable, avoid renaming or dropping columns until a later release, and never change column types in place. The old pods must keep working against the new schema until all pods roll over."
  - q: "Should migrations run before or after deploying new application code?"
    a: "Backward-compatible migrations run before the new code deploys. Destructive migrations (dropping columns, tightening constraints) run after all old code is gone — often one or two releases later in an expand-contract sequence."
  - q: "How do you test zero-downtime migrations in CI?"
    a: "Spin up the old schema + old app, apply migration, verify old app still passes integration tests, deploy new app, verify new tests. Tools like Testcontainers make this a pipeline stage, not a manual checklist."
---

The deploy failed at 2 AM because someone added `NOT NULL` to a column the old API version still writes without. Postgres locked the table for four minutes. Checkout returned 503. The migration ran in the same pipeline stage as the container push — "it's automated" — with no backward compatibility check.

Zero-downtime migrations aren't about faster tools. They're about ordering: schema changes, app deploys, and schema cleanup as separate releases.

## The expand-contract lifecycle

Every breaking schema change splits into three releases:

**Release N — Expand**
- Add new column/table/index
- Keep old path working
- Migration is additive only

**Release N+1 — Migrate**
- Deploy app that dual-writes or reads new column
- Backfill data asynchronously
- Old app version still runs if rollback needed

**Release N+2 — Contract**
- Remove old column after confirming zero reads/writes
- Drop deprecated indexes

Example: rename `email` to `email_address`.

```sql
-- Release N: expand (run BEFORE new app deploy)
ALTER TABLE users ADD COLUMN email_address TEXT;

-- Release N+1: backfill (job, not blocking deploy)
UPDATE users SET email_address = email WHERE email_address IS NULL;

-- App now writes to both columns (deploy new version)

-- Release N+2: contract (run AFTER old app fully retired)
ALTER TABLE users DROP COLUMN email;
```

Never `ALTER TABLE users RENAME COLUMN email TO email_address` in a single deploy. Old pods break instantly.

## Migration ordering in the pipeline

Our GitHub Actions pipeline stages:

```
1. lint + unit tests
2. integration tests (current schema)
3. migration dry-run against ephemeral DB
4. apply migration to staging
5. integration tests (old app vs new schema)  ← catches compatibility breaks
6. deploy new app to staging
7. smoke tests
8. (manual promote) migration + deploy to prod
```

```yaml
# Simplified pipeline stage
migrate-staging:
  steps:
    - run: flyway migrate -url=$STAGING_DB_URL
    - run: ./scripts/test-old-app-against-new-schema.sh
    - run: kubectl rollout status deployment/api
```

`test-old-app-against-new-schema.sh` runs the *previous release's* Docker image against the migrated database. If it fails, the pipeline stops before prod.

## Flyway and Liquibase in CD

**Flyway** — SQL-first, versioned files (`V001__add_users.sql`). Simple, reviewable in PRs.

```sql
-- V042__add_email_address.sql
ALTER TABLE users ADD COLUMN IF NOT EXISTS email_address TEXT;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email_address
  ON users (email_address);
```

Use `CONCURRENTLY` for index creation on Postgres — standard `CREATE INDEX` locks writes.

**Liquibase** — XML/YAML/SQL changesets with rollback blocks. Rollbacks are seductive and often untested; we use forward-only migrations with expand-contract instead of `rollback` in prod.

Lock migration execution to one runner. Flyway's `flyway_schema_history` table prevents double-apply; still use a pipeline mutex so two branches don't race.

## Patterns that work in production

**Nullable first, enforce later.**
```sql
ALTER TABLE orders ADD COLUMN discount_cents INTEGER;
-- Later release, after backfill:
ALTER TABLE orders ALTER COLUMN discount_cents SET NOT NULL;
ALTER TABLE orders ALTER COLUMN discount_cents SET DEFAULT 0;
```

**Feature flags for read path switches.** App reads `email_address` if flag on, else `email`. Flip flag after backfill completes. Remove flag in contract release.

**Online index creation.** Postgres `CREATE INDEX CONCURRENTLY`, MySQL InnoDB online DDL (still watch lock waits on large tables).

**Avoid table rewrites.** Adding column with default in Postgres 11+ is metadata-only for nullable without default. Adding `DEFAULT` + `NOT NULL` in one statement rewrites the table on older versions.

## When zero-downtime isn't worth it

Maintenance windows are fine for internal tools with scheduled downtime SLAs, databases under 100 MB where locks last seconds, or one-shot data fixes with communicated outage.

For customer-facing APIs with rolling deploys, the expand-contract tax pays for itself the first time you rollback an app without rolling back schema.

## Tooling integration with ORMs

Prisma, Django, and Rails migrations generate SQL that may not be expand-contract friendly out of the box. Review generated SQL in PRs — frameworks happily emit `DROP COLUMN` in the same release as code changes.

For Prisma, split migrations manually when needed: create empty migration, edit SQL to expand-only, deploy app, second migration for contract phase. Django `SeparateDatabaseAndState` helps when model rename should not emit destructive SQL yet.

Document migration class (`expand`, `contract`, `data`) in PR title. Release managers skip contract migrations until deploy metrics confirm zero traffic on old app version.

## Common production mistakes

Teams get database migrations zero downtime wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of database migrations zero downtime fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When database migrations zero downtime misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Expand-contract worked example

Adding `NOT NULL` column without downtime:

**Expand:** `ADD COLUMN status_new TEXT NULL` — deploy app writing both columns
**Migrate:** backfill `status_new` from `status` in batches
**Contract:** `SET NOT NULL` after backfill; deploy app reading new only; drop old

Never `ADD COLUMN ... NOT NULL DEFAULT` on Postgres big tables in one step — locks table, blocks writes.

## Migration job observability

Long backfills need progress metrics:

```sql
UPDATE users SET migrated = true
WHERE id IN (SELECT id FROM users WHERE NOT migrated LIMIT 5000);
-- repeat until rowcount = 0
```

Export `rows_remaining` gauge; pause backfill if replica lag exceeds 30s. Read traffic on lagging replica returns stale data — acceptable briefly, not for hours.

## Lock timeout on migrations

```sql
SET lock_timeout = '5s';
SET statement_timeout = '600s';
```

Long `ACCESS EXCLUSIVE` from careless `ADD COLUMN DEFAULT` fails fast instead of blocking checkout queue overnight.

## ORM migration ordering

Deploy app reading new column before backfill completes only if column nullable — document deploy order in migration ticket template: expand deploy → backfill job → contract deploy.

## Flyway vs Liquibase ordering

Version numbers collide when teams merge migrations — CI check max version monotonic per branch. Out-of-order deploy breaks expand-contract sequencing.

## Shadow columns for rename

Rename column via add-new copy dual-write drop-old — never `ALTER RENAME` on hot table under load. Shadow period length = max app deploy cycle + 24h safety.
## Connection pool storm after migration

Deploy with new column drains old pool slowly — PgBouncer `SERVER_RESET_QUERY` or rolling app restart prevents mixed schema parsers in one pool.

## Resources

- [Flyway documentation](https://flywaydb.org/documentation/)
- [Liquibase best practices](https://docs.liquibase.com/concepts/bestpractices.html)
- [PostgreSQL CREATE INDEX CONCURRENTLY](https://www.postgresql.org/docs/current/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY)
- [Stripe's online migrations blog post](https://stripe.com/blog/online-migrations)
- [Braintree expand-contract approach](https://www.braintreepayments.com/blog/safe-operations-for-high-volume-postgresql/)
