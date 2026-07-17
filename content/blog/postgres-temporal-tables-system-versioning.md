---
title: "Postgres Temporal Tables and System Versioning"
slug: "postgres-temporal-tables-system-versioning"
description: "Implement system-versioned temporal tables with tstzrange, history partitions, and queries for point-in-time and as-of reporting."
datePublished: "2026-03-08"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "temporal tables, system versioning, tstzrange, point in time query, postgres history table"
faq:
  - q: "Does Postgres have built-in SQL temporal tables like SQL:2011?"
    a: "Postgres does not ship native SYSTEM VERSIONING syntax through PG 16. You implement temporal patterns with triggers: current table plus history table, transaction time stored as tstzrange, and queries using range operators for as-of semantics."
  - q: "What is the difference between transaction time and valid time?"
    a: "Transaction time (system time) records when the database knew about a row version. Valid time (application time) records when a fact was true in the real world. Postgres temporal designs often start with transaction time; valid time requires separate columns and business rules."
  - q: "How do I query what a row looked like at a specific timestamp?"
    a: "SELECT from history where tstzrange contains the timestamp, union current rows where sys_period contains timestamp. Index sys_period with GiST for range queries."
  - q: "How do I prevent history tables from growing without bound?"
    a: "Partition history by month on lower(sys_period), detach and archive cold partitions per compliance policy. VACUUM history aggressively; consider BRIN on time columns for append-only scans."
---

Regulators and support teams ask: **what did we know at 3 PM last Tuesday?** Not what we know now after three corrections—a **point-in-time** view of row state. SQL:2011 standardized **system-versioned temporal tables**; Postgres implements the pieces (**`tstzrange`**, triggers) but not **`FOR SYSTEM_TIME AS OF`** keywords out of the box.

A explicit **current + history** design with **`tstzrange`** gives full control, works with replication and logical decoding, and survives ORM mapping better than black-box engine magic.

## Reference architecture

```sql
CREATE TABLE employees (
  employee_id   int PRIMARY KEY,
  name          text NOT NULL,
  department    text NOT NULL,
  salary        numeric(12,2) NOT NULL,
  sys_period    tstzrange NOT NULL DEFAULT tstzrange(now(), NULL, '[)')
);

CREATE TABLE employees_history (LIKE employees);

CREATE INDEX employees_history_period_gist
  ON employees_history USING gist (employee_id, sys_period);
```

**`sys_period`**: half-open range **`[start, end)`** — NULL upper bound on current row means still active.

## Trigger-based versioning

```sql
CREATE OR REPLACE FUNCTION employees_versioning()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    INSERT INTO employees_history
    SELECT OLD.employee_id, OLD.name, OLD.department, OLD.salary,
           tstzrange(lower(OLD.sys_period), now(), '[)');
    NEW.sys_period := tstzrange(now(), NULL, '[)');
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    INSERT INTO employees_history
    SELECT OLD.employee_id, OLD.name, OLD.department, OLD.salary,
           tstzrange(lower(OLD.sys_period), now(), '[)');
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$;

CREATE TRIGGER employees_versioning_trg
BEFORE UPDATE OR DELETE ON employees
FOR EACH ROW EXECUTE FUNCTION employees_versioning();
```

Use **`BEFORE`** trigger so application sees correct period on NEW row.

## AS OF query (system time)

```sql
WITH snapshot AS (
  SELECT employee_id, name, department, salary
  FROM employees
  WHERE sys_period @> $1::timestamptz

  UNION ALL

  SELECT employee_id, name, department, salary
  FROM employees_history
  WHERE sys_period @> $1::timestamptz
)
SELECT * FROM snapshot;
```

Timeline for one employee:

```sql
SELECT employee_id, name, sys_period
FROM (
  SELECT * FROM employees WHERE employee_id = $1
  UNION ALL
  SELECT * FROM employees_history WHERE employee_id = $1
) u
ORDER BY lower(sys_period);
```

## Valid-time (business time) extension

Add **`valid_period tstzrange`** separate from **`sys_period`**. Query "who was in Engineering on 2025-06-01" uses **`valid_period @> date`**, not transaction time.

## Bi-temporal modeling sketch

Track both **`sys_period`** and **`valid_period`**. Queries specify both dimensions for audit vs business reporting. Start uni-temporal until product demands valid-time.

## Preventing overlapping current versions

```sql
ALTER TABLE employees ADD CONSTRAINT employees_no_overlap
EXCLUDE USING gist (employee_id WITH =, sys_period WITH &&);
```

## temporal_tables extension

Community extension wraps boilerplate with **`versioning_setup`**. Evaluate maintenance for your Postgres version; roll-your-own triggers transparent for audits.

## Partitioning history

```sql
CREATE TABLE employees_history (
  LIKE employees INCLUDING DEFAULTS
) PARTITION BY RANGE (lower(sys_period));
```

Monthly partition job; detach >7 years to archive per policy.

## Integration with application ORMs

- Map **`employees`** only for CRUD
- AS OF queries via raw SQL repository
- Revoke UPDATE/DELETE on history from app role

```sql
REVOKE UPDATE, DELETE ON employees_history FROM app_role;
```

## Logical replication and CDC

History inserts replicate as normal inserts. CDC consumers build SCD type 2 warehouse models. Initial load: snapshot export both tables with same **`pg_export_snapshot`**.

## Row-level security with history

Apply matching RLS on **`employees_history`** or security barrier views per tenant. Test trigger path under non-superuser application role—RLS surprises appear at first production update.

## Compliance and corrections

Never delete history in prod for legal hold. New correcting row with new **`sys_period`**; optional **`correction_reason`** column.

## Performance considerations

Every update → insert history—doubles write IO. GiST index on **`(employee_id, sys_period)`** mandatory at scale. Batch imports: staging table + single merge transaction.

## Flashback vs temporal

**PITR** is whole-database time travel. Temporal tables answer row-level questions without multi-TB restore. Choose temporal for frequent narrow audit queries; PITR for catastrophe recovery.

## Testing temporal logic

- Update twice; AS OF midpoints returns intermediate state
- Delete row; AS OF before delete sees row; after reads history only
- Use **`transaction_timestamp()`** in triggers for transaction-time semantics

When audit asks **"show me record 8472 on date X"** without restoring full backup, system-versioned **`tstzrange`** design answers from SQL.



## Clock semantics: statement_timestamp vs clock_timestamp

Triggers should use **`statement_timestamp()`** or **`now()`** SQL stable within transaction for **`sys_period`** bounds—**`clock_timestamp()`** advances between statements and creates overlapping periods under multi-statement transactions. Tests using **`pg_sleep`** expose the difference.

## History table indexing for AS OF at scale

Composite GiST **`(employee_id, sys_period)`** supports **`employee_id = ? AND sys_period @> t`**. For warehouse scans "all rows as of t" without employee filter, BRIN on **`lower(sys_period)`** plus partial index on open ranges helps—query pattern drives index choice.

## Merging current and history in ORMs

Hibernate Envers and similar generate parallel schemas—native Postgres temporal triggers duplicate effort if both active. Pick one audit mechanism; dual writes diverge under failure.

## Temporal vs event sourcing

Event sourcing rebuilds state from immutable events; temporal tables store state snapshots per change. Event sourcing better for complex domain replay; temporal tables better for SQL-native audit and regulatory AS OF without rebuilding from events. Hybrid: events for domain, temporal for relational projection audit.

## Upgrade path to SQL:2011 if ever standardized

Should Postgres adopt **`FOR SYSTEM TIME AS OF`**, migration from trigger pattern likely maps **`sys_period`** to system time columns—design **`sys_period`** naming and half-open convention now to align with standard semantics if added.




## Bulk UPDATE versioning trigger cost

Updating 1M rows fires trigger 1M times—history table explodes. For bulk corrections, disable trigger session-local (superuser), run batch with explicit history insert strategy, re-enable trigger—document break-glass procedure. Prefer staging table swap for mass corrections.

## Foreign keys to temporal current table

FK references **`employees(employee_id)`** on current table only—historical FK to history rare. Deletes move row to history; FK **`ON DELETE RESTRICT`** on child tables still valid while current row exists.




## Retention legal hold workflow

When legal hold activates, stop detach/archive jobs on history partitions overlapping hold period—tag partitions in metadata table **`legal_hold boolean`**. Automate hold checks before **`DROP TABLE`** on detached partitions.

## Comparison with audit trigger logging old row JSON

JSON **`audit_log`** row stores **`OLD.* to_jsonb`** without temporal query syntax—simpler inserts, harder AS OF queries. Temporal **`tstzrange`** wins when regulators ask SQL-standard time travel reports; JSON audit wins when append-only log shipping to SIEM suffices.



## Storage growth projections

History table size approximates update rate times row width times retention—model before enabling triggers on wide JSONB rows. Partition history monthly from day one; retrofitting partition on billion-row history painful. Compression not native in heap—archive cold partitions to columnar warehouse.

## Support tooling for AS OF queries

Build internal admin UI accepting employee_id and timestamp, running parameterized AS OF SQL read-only—support resolves disputes without SQL access. Log each AS OF query for audit of audit queries—meta-audit trail.


## Backup includes history

Ensure pg_dump or physical backup includes history partitions—AS OF useless if history missing after restore. Test AS OF query in restore drill not only COUNT(*) on current table.




## Temporal schema migration

Adding sys_period to existing table requires backfill tstzrange(now(), NULL) and history bootstrap from audit logs if available—greenfield easier than retrofit. Plan maintenance window for trigger creation on high-churn table—first update after trigger fires history insert storm.

## GDPR right to erasure vs history

Erasure requests may require anonymizing history rows not deleting—update history name to REDACTED preserving sys_period audit chain. Legal defines whether sys_period trail itself is personal data subject to erasure.

## Trigger recursion guard

Ensure history table has no versioning trigger—accidental trigger on history duplicates rows infinitely on first update. Code review checklist item for temporal schema migrations.

## Resources

- [Range types](https://www.postgresql.org/docs/current/rangetypes.html)
- [Exclusion constraints](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-EXCLUSION)
- [temporal_tables extension](https://github.com/arkhipov/temporal_tables)
