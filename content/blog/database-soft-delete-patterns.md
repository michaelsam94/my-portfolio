---
title: "Soft Delete: Patterns and Pitfalls"
slug: "database-soft-delete-patterns"
description: "Soft deletes mark rows deleted without removing them. deleted_at columns, unique constraints, query filters, GDPR tension, and when hard delete wins."
datePublished: "2025-09-12"
dateModified: "2025-09-12"
tags: ["Backend", "Databases", "Architecture"]
keywords: "soft delete, deleted_at, logical delete, paranoid deletion, GDPR hard delete, unique constraint soft delete"
faq:
  - q: "What is soft delete?"
    a: "Soft delete marks records as deleted — typically deleted_at timestamp or is_deleted flag — without physically removing rows. Applications filter active rows with WHERE deleted_at IS NULL. Enables undelete, audit trails, and referential integrity without cascade removes."
  - q: "What problems do soft deletes cause?"
    a: "Forgotten query filters leak deleted data; unique constraints conflict when re-creating rows with same natural key; tables grow unbounded; joins slow without partial indexes; GDPR right-to-erasure requires hard delete or anonymization anyway."
  - q: "When should I use hard delete instead?"
    a: "Use hard delete for regulated erasure requests, high-churn ephemeral data, and tables where retention policy mandates physical removal. Use soft delete when undo windows, audit requirements, or foreign key preservation justify retained rows with strict access controls."
---

Soft delete feels like free undo until production queries return competitor data from "deleted" accounts because one repository method forgot `deleted_at IS NULL`. The pattern is widespread; the discipline around it usually isn't.

## Basic implementation

```sql
CREATE TABLE customers (
  id          BIGSERIAL PRIMARY KEY,
  email       VARCHAR(255) NOT NULL,
  deleted_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX customers_active_email_idx
  ON customers (email)
  WHERE deleted_at IS NULL;
```

Delete becomes update:

```sql
UPDATE customers SET deleted_at = now() WHERE id = 42;
```

Application scope:

```python
class CustomerQuery:
    def active(self):
        return self.filter(deleted_at__isnull=True)
```

Centralize filtering — raw SQL and ORM bypasses leak deleted rows.

## Unique constraint hell

User soft-deletes `alice@corp.com`, tries re-register:

```sql
UNIQUE (email)  -- fails: deleted row still holds email
```

Fixes:

**Partial unique index:**

```sql
CREATE UNIQUE INDEX customers_email_active_uniq
  ON customers (email)
  WHERE deleted_at IS NULL;
```

**Composite unique including deleted_at** — allows one active + historical tombstones (messy).

**Email mutation on delete** — append `+deleted_{id}` (audit unfriendly).

Partial indexes are the cleanest Postgres/MySQL 8+ approach.

## ORM "paranoid" mode

Sequelize, TypeORM, GORM offer paranoid deletes — auto-filter and set deletedAt. Danger: raw queries, reporting DB connections, and admin tools bypass ORM.

Global default scopes help; explicit `withDeleted()` for admin restores.

## Undelete and retention

```sql
UPDATE customers SET deleted_at = NULL WHERE id = 42;
```

Define retention — soft-deleted rows hard-purged after 90 days via scheduled job. Without purge, tables bloat and compliance erasure never completes.

## GDPR and soft delete tension

Soft delete ≠ erasure. DSAR requires anonymizing or hard-deleting PII columns:

```sql
UPDATE customers
SET email = 'erased-' || id || '@invalid.local',
    name = 'ERASED',
    deleted_at = coalesce(deleted_at, now())
WHERE id = 42;
```

Document which tables soft-delete vs anonymize vs hard-delete in privacy runbooks.

## Foreign keys and cascades

Soft-deleting parent while children active breaks logical consistency. Options:

- Cascade soft-delete to children in application transaction
- Keep FK hard deletes on child when parent soft-deleted (confusing)
- `ON DELETE SET NULL` with nullable FK

Prefer explicit cascade service over DB triggers hidden from developers.

## Performance

Full table scans ignoring partial indexes when queries omit `deleted_at IS NULL`. Every index should be partial where engine supports it.

Archive cold soft-deleted rows to history table / cold storage — keeps hot table small.

## Alternatives

**Status enum** — `active | suspended | deleted` instead of timestamp.

**Separate archive table** — move row on delete; active table stays clean.

**Event sourcing** — delete is event; projections rebuild state.

**Hard delete + audit log** — store deleted payload JSON in audit service, not OLTP table.

Pick based on query patterns and compliance, not convention.

## Testing checklist

- Assert all public APIs exclude soft-deleted by default
- Re-registration after delete works
- Admin restore idempotent
- Purge job respects retention
- Analytics warehouse handles deletes (CDC tombstones or hard purge sync)

## ORM bypass and the leak problem

The most common soft-delete bug isn't the delete itself — it's reads that bypass the ORM filter:

```python
# ORM path — filtered correctly
Customer.objects.filter(email="alice@corp.com")  # excludes soft-deleted

# Raw SQL in reporting — LEAKS deleted data
db.execute("SELECT * FROM customers WHERE email = %s", ["alice@corp.com"])

# Admin tool with direct DB connection — LEAKS
# Analytics warehouse synced via CDC — INCLUDES deleted rows unless filtered
```

Mitigations:
- Database views: `CREATE VIEW active_customers AS SELECT * FROM customers WHERE deleted_at IS NULL`
- Row-level security: `CREATE POLICY active_only ON customers USING (deleted_at IS NULL)`
- Code review rule: any raw SQL on soft-deleted tables must include filter
- CDC downstream: filter `op != 'd'` or `deleted_at IS NULL` in warehouse staging models

## Soft delete in event-driven architectures

CDC streams soft deletes as update events (deleted_at set), not delete events:

```json
{
  "op": "u",
  "before": {"id": 42, "email": "alice@corp.com", "deleted_at": null},
  "after": {"id": 42, "email": "alice@corp.com", "deleted_at": "2025-07-15T10:00:00Z"}
}
```

Downstream consumers must handle this as a logical delete — remove from search index, invalidate cache, stop email campaigns. If they only process `op: "d"` hard deletes, soft-deleted records persist in derived systems forever.

## Archive table pattern

For high-churn tables, move soft-deleted rows to archive instead of accumulating:

```sql
-- Scheduled job: move rows deleted > 30 days ago
INSERT INTO customers_archive SELECT * FROM customers
WHERE deleted_at < now() - interval '30 days';

DELETE FROM customers
WHERE deleted_at < now() - interval '30 days';
```

Active table stays small and fast. Archive table is read-only for audit/compliance. Hard delete from archive after retention period (1–7 years depending on regulation).

## Failure modes

- **Missing filter in one query path** — most common bug; one endpoint leaks deleted data
- **Unique constraint without partial index** — re-registration after delete fails
- **Unbounded table growth** — no purge job; soft-deleted rows accumulate forever
- **GDPR request not handled** — soft delete doesn't satisfy erasure; need anonymization
- **CDC downstream ignores soft deletes** — deleted records persist in search/cache/warehouse
- **Cascade not implemented** — parent soft-deleted but children still active

## Production checklist

- Partial unique indexes on active rows only
- ORM default scope filters deleted_at IS NULL
- Raw SQL and admin tools audited for filter compliance
- CDC downstream handles soft delete as logical delete
- Retention policy with scheduled purge or archive job
- GDPR erasure procedure documented (anonymize vs hard delete)
- Re-registration after delete tested in CI

Add partial indexes on `WHERE deleted_at IS NULL` — soft-delete tables without them become full table scans on every query.

## Resources

- [PostgreSQL — Partial indexes](https://www.postgresql.org/docs/current/indexes-partial.html)
- [Paranoid deletion in Sequelize](https://sequelize.org/docs/v6/core-concepts/paranoid/)
- [GDPR — Right to erasure (ICO)](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-to-erasure/)
- [Microsoft — Temporal tables (alternative pattern)](https://learn.microsoft.com/en-us/sql/relational-databases/tables/temporal-tables)
- [Use The Index, Luke — Partial indexes for soft delete](https://use-the-index-luke.com/)
