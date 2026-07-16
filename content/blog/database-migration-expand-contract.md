---
title: "Expand-Contract Schema Migrations"
slug: "database-migration-expand-contract"
description: "Expand-contract migrates schemas without downtime by adding before removing. Multi-phase deploys, dual writes, and backfill patterns for zero-downtime changes."
datePublished: "2025-08-31"
dateModified: "2025-08-31"
tags: ["Backend", "Databases", "Architecture"]
keywords: "expand contract migration, zero downtime schema migration, database migration, backward compatible schema change"
faq:
  - q: "What is the expand-contract pattern?"
    a: "Expand-contract splits breaking schema changes into safe phases: expand by adding new schema elements without removing old ones, migrate application and data to use both, then contract by removing deprecated elements once nothing depends on them. Each phase deploys independently without downtime."
  - q: "Why not rename a column in one migration?"
    a: "A single rename breaks running application instances expecting the old name and prevents rollback. Expand-contract adds new_column, dual-writes, switches reads, then drops old_column across separate releases coordinated with code deploys."
  - q: "How long should expand phases stay in production?"
    a: "Until all code paths read the new schema and backfill completes — often one to three release cycles depending on deploy frequency and data volume. Track migration state in feature flags or schema version tables; never drop old columns on the same day you add new ones."
---

The rename that took down checkout for twenty minutes wasn't the SQL — it was deploying `ALTER TABLE RENAME COLUMN` while half the pods still queried `user_id`. Expand-contract treats schema and application as a **joint migration** across multiple releases, never assuming deploys are atomic.

## Three phases

**Expand** — add new structure, keep old:

```sql
ALTER TABLE users ADD COLUMN email_address VARCHAR(255);
-- old column email still exists
```

**Migrate** — application writes both, reads new (or reads new with fallback):

```python
user.email_address = normalized_email
user.email = normalized_email  # dual write
```

Backfill historical rows:

```sql
UPDATE users SET email_address = email WHERE email_address IS NULL;
```

**Contract** — remove old after all consumers updated:

```sql
ALTER TABLE users DROP COLUMN email;
```

Each phase is backward compatible with the previous app version during rolling deploys.

## Rename without downtime

Never `RENAME COLUMN` in production as step one:

1. Add `email_address`
2. Deploy app dual-writing
3. Backfill
4. Deploy app reading `email_address` only
5. Drop `email`

For views and APIs, version the contract (`/v2/users` returns `email_address`).

## NOT NULL and constraints

Adding `NOT NULL` on existing tables requires expand:

```sql
-- Expand: nullable column
ALTER TABLE orders ADD COLUMN currency_code CHAR(3);

-- Backfill default
UPDATE orders SET currency_code = 'USD' WHERE currency_code IS NULL;

-- Contract: enforce NOT NULL after backfill verified
ALTER TABLE orders ALTER COLUMN currency_code SET NOT NULL;
```

Validate `SELECT count(*) WHERE currency_code IS NULL = 0` before constraint.

## Type changes

Changing `VARCHAR` to `INT` or widening types:

1. Add `amount_cents BIGINT`
2. Dual-write computed value
3. Backfill `amount_cents = amount_dollars * 100`
4. Switch reads
5. Drop old column

For Postgres, consider `ADD COLUMN ... GENERATED STORED` as intermediate step.

## Feature flags coordinate code and schema

```python
if settings.use_email_address_column:
    return user.email_address
return user.email
```

Flag off until backfill complete; flag on before contract phase. Same flag gates write path during dual-write.

## Expand-contract for indexes

Add new index `CONCURRENTLY` before dropping old unique constraint — avoids table locks on Postgres:

```sql
CREATE UNIQUE INDEX CONCURRENTLY users_email_address_idx ON users(email_address);
-- deploy switch
ALTER TABLE users DROP CONSTRAINT users_email_key;
ALTER TABLE users ADD CONSTRAINT users_email_address_key UNIQUE USING INDEX users_email_address_idx;
```

## Event schemas and CDC

Database expand-contract pairs with Avro/Protobuf schema evolution — add optional field, deploy consumers, make required, remove old field. Debezium emits both columns during dual-write period.

## Rollback strategy

Expand phases roll back easily — drop unused new column. Contract phase is **point of no return** — snapshot before drop, delay drop until metrics clean one week.

## Team checklist

- [ ] Migration split into expand / migrate / contract tickets
- [ ] Backfill idempotent and resumable
- [ ] Monitoring on null rates in new column
- [ ] Contract phase scheduled after deploy saturation
- [ ] Communication to analytics on column deprecation

## Real-world expand-contract examples

**Renaming a column used in 12 services:**

The mistake: `ALTER TABLE orders RENAME COLUMN user_id TO customer_id` in one migration. Rolling deploy means old pods query `user_id` against renamed column — 500 errors until all pods restart.

The expand-contract path:
1. Week 1: Add `customer_id`, deploy dual-write, backfill
2. Week 2: Deploy all services reading `customer_id` with fallback to `user_id`
3. Week 3: Remove fallback reads, verify zero queries to `user_id` in logs
4. Week 4: Drop `user_id`

Four releases, zero downtime. Each release is independently rollback-safe.

**Adding NOT NULL to 50M row table:**

```sql
-- Phase 1 (expand): nullable column, no constraint
ALTER TABLE events ADD COLUMN session_id UUID;

-- Phase 2 (backfill): batched updates, resumable
UPDATE events SET session_id = gen_random_uuid()
WHERE session_id IS NULL AND id BETWEEN $start AND $end;

-- Phase 3 (validate): zero nulls
SELECT count(*) FROM events WHERE session_id IS NULL;  -- must be 0

-- Phase 4 (contract): add constraint
ALTER TABLE events ALTER COLUMN session_id SET NOT NULL;
```

Never add `NOT NULL` and backfill in the same deploy — the constraint fails on existing null rows.

## Dual-write implementation patterns

Application-level dual-write needs careful ordering:

```python
def update_user_email(user_id: str, new_email: str):
    user = db.get(user_id)
    user.email = new_email           # old column
    user.email_address = new_email   # new column
    db.commit()
```

Read path during migration:

```python
def get_email(user) -> str:
    if feature_flags.use_email_address:
        return user.email_address or user.email  # fallback during transition
    return user.email
```

Log when fallback path is hit — when hit rate reaches zero, the read migration is complete.

## Coordinating with analytics and CDC

Database expand-contract affects downstream consumers:

- **dbt models** referencing old column name break when contract phase drops column — update dbt first, deploy, then drop
- **Debezium CDC** emits both columns during dual-write period — consumers must handle either field
- **BI dashboards** cached on old column name — audit Metabase/Looker references before contract
- **Data contracts** — publish schema change notification to downstream teams with timeline

Schedule contract phase only after analytics team confirms migration.

## Failure modes

- **Contract before all readers migrated** — dropped column crashes running services
- **Backfill not idempotent** — re-running backfill corrupts data; use `WHERE new_col IS NULL` guard
- **Missing feature flag on read path** — deploy reads new column before backfill completes, returns nulls
- **Same-release expand + contract** — defeats the purpose; minimum one release between phases
- **No monitoring on new column null rate** — silent backfill failure discovered at contract phase

## Production checklist

- Each phase is separate release with independent rollback plan
- Dual-write verified in staging with both old and new app versions
- Backfill idempotent with progress tracking (resume from last ID)
- Feature flag gates read/write path migration
- Null rate monitoring on new column before contract
- Downstream analytics/dbt/CDC notified with deprecation timeline
- Contract phase delayed until zero fallback reads in production logs

## Resources

- [Martin Fowler — Evolutionary Database Design](https://martinfowler.com/articles/evodb.html)
- [Stripe — Online migrations at scale](https://stripe.com/blog/online-migrations)
- [PostgreSQL — ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)
- [Flyway — Repeatable migrations](https://documentation.red-gate.com/fd/repeatable-migrations-273973335.html)
- [Shopify — Deconstructing the monolith (schema patterns)](https://shopify.engineering/deconstructing-monolith-designing-software-maximum-scalability)
