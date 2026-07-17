---
title: "Postgres Table Inheritance Patterns"
slug: "postgres-table-inheritance-patterns"
description: "Choose between legacy table inheritance and declarative partitioning for time-series, multi-tenant layouts, and constraint exclusion."
datePublished: "2026-03-06"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres table inheritance, declarative partitioning, constraint exclusion, ONLY keyword, partition migration"
faq:
  - q: "What is the difference between table inheritance and declarative partitioning?"
    a: "Legacy inheritance links child tables via INHERITS; queries against parent include all children unless ONLY is specified. Declarative partitioning (PG 10+) is native with PARTITION BY RANGE/LIST/HASH, better planner integration, partition pruning, and automatic INSERT routing. New designs should use declarative partitioning."
  - q: "When does legacy inheritance still make sense?"
    a: "Maintaining existing inheritance hierarchies predating declarative partitioning. Greenfield should not start with INHERITS."
  - q: "How does constraint exclusion work with inherited tables?"
    a: "When constraint_exclusion is on, Postgres skips child tables whose CHECK constraints prove they cannot contain matching rows. Child tables need CHECK constraints on partition key columns. Without them, every child scans."
  - q: "Why must I use ONLY when updating the parent table?"
    a: "UPDATE/DELETE on parent without ONLY can cascade to all inheritors. ONLY targets the parent table alone. Declarative partitioning routes inserts automatically via bound definitions."
---

Before **`PARTITION BY`**, Postgres had **`INHERITS`**: child tables structurally extend a parent, queries against the parent logically union all descendants, and **`CHECK`** constraints on children enable **constraint exclusion** to skip irrelevant tables.

Declarative partitioning superseded most use cases in Postgres 10+, but inheritance still appears in decade-old schemas—and confusing **`ONLY`** behavior still burns teams during migrations.

## Legacy inheritance mechanics

```sql
CREATE TABLE events (
  id         bigint,
  created_at timestamptz NOT NULL,
  payload    jsonb
);

CREATE TABLE events_2026_01 () INHERITS (events);
CREATE TABLE events_2026_02 () INHERITS (events);

ALTER TABLE events_2026_01 ADD CONSTRAINT chk
  CHECK (created_at >= '2026-01-01' AND created_at < '2026-02-01');
```

Query parent:

```sql
SELECT count(*) FROM events WHERE created_at >= '2026-02-10';
```

**`ONLY`** keyword:

```sql
SELECT * FROM ONLY events;
UPDATE ONLY events SET payload = NULL WHERE id = 1;
```

Without **`ONLY`**, **`UPDATE events`** hits parent **and** all inheritors.

**No automatic INSERT routing** into monthly child unless triggers exist. Declarative partitioning fixes this.

## Declarative partitioning (preferred today)

```sql
CREATE TABLE events (
  id         bigint,
  created_at timestamptz NOT NULL,
  payload    jsonb
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_01 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

Benefits: partition pruning, automatic INSERT routing, **`ATTACH`/`DETACH`**, partition-wise join.

```sql
CREATE TABLE events_default PARTITION OF events DEFAULT;
```

## Side-by-side behavior

| Concern | INHERITS | PARTITION BY |
| --- | --- | --- |
| Insert routing | Manual / triggers | Automatic |
| Unique PK across hierarchy | Not global across children | Must include partition key |
| FK referencing parent | Complex | Supported on partitioned table (PG 12+) |
| Drop old data | DROP TABLE child | DETACH + DROP |
| Planner support | Legacy exclusion | Native pruning |

## Unique constraints pain

**`PRIMARY KEY (id)`** on parent **does not** enforce uniqueness across children—duplicate **`id`** in two months possible.

Declarative: **`PRIMARY KEY (id, created_at)`** including partition key.

## Multi-tenant patterns

**Anti-pattern:** **`INHERITS`** per tenant—thousands of children explode catalog size.

**Better:** row-level **`tenant_id`** + RLS, or LIST partition for large isolated tenants only.

## Time-series rolling window

```sql
CREATE OR REPLACE PROCEDURE create_next_month_partition()
LANGUAGE plpgsql AS $$
DECLARE
  start date := date_trunc('month', now()) + interval '1 month';
  end date := start + interval '1 month';
  part text := 'events_' || to_char(start, 'YYYY_MM');
BEGIN
  EXECUTE format(
    'CREATE TABLE IF NOT EXISTS %I PARTITION OF events FOR VALUES FROM (%L) TO (%L)',
    part, start, end
  );
END;
$$;
```

Schedule via pg_cron. Detach old partitions to cold storage.

## Migrating INHERITS → PARTITION BY

1. Create new partitioned parent
2. ATTACH or copy data during maintenance window
3. Rename swap
4. Recreate indexes, FKs, triggers
5. Drop old hierarchy

Test on clone—inheritance FK graphs are messy.

## Catalog bloat from too many children

500+ monthly children slow planning even with exclusion—migrate to declarative with bounded partitions plus archive DETACH.

## Foreign keys into inherited parents

**`REFERENCES parent(id)`** does not enforce against rows only in children—migration driver to declarative.

## Query patterns and ONLY

Verify plans:

```sql
EXPLAIN SELECT * FROM events WHERE created_at = '2026-02-15';
```

Look for partition pruning or Append with subplans removed.

## Index inheritance

Indexes on parent **are not automatically on children** in legacy inheritance—create per child. Declarative: **`CREATE INDEX ON events (...)`** propagates to partitions.

## Partition-wise operations

**`enable_partitionwise_aggregate`** helps grouped aggregates on declarative partitions at scale.

Table inheritance taught Postgres how partitioned data should behave; declarative partitioning is the implementation for new time-series and large fact tables. Understand **`INHERITS`** to maintain legacy systems and migrate deliberately.



## Trigger-based routing in legacy inheritance

Before declarative partitioning, teams used **`BEFORE INSERT`** triggers on parent inspecting **`NEW.created_at`** and redirecting to child via **`EXECUTE format('INSERT INTO %I ...')`**—fragile, hard to test, breaks **`RETURNING`** semantics. Document these triggers before migration; grep codebase for **`ONLY`** usage and parent table inserts.

## Partition pruning vs constraint exclusion EXPLAIN output

Declarative plans show **`Partition Prune`** nodes; inheritance shows **`Append`** with **`Subplans Removed`**. Operators familiar with one syntax misread the other during incident triage—include example **`EXPLAIN`** snippets in runbooks for each schema generation.

## Default partition operational smell

High insert rate into **`DEFAULT`** partition signals missing monthly maintenance job—alert on row count in default partition > 0 for time-series schemas. **`DEFAULT`** prevents insert failures but hides operational debt until scan performance collapses.

## pg_partman extension

**`pg_partman`** automates declarative partition creation and retention—prefer extension over hand-rolled procedures for new systems. Migration from inheritance: **`partman`** scripts exist for some conversions—evaluate against hand migration for your FK graph complexity.




## Tuple routing and constraint exclusion legacy GUC

**`constraint_exclusion = on`** scans all children—use **`partition`** default. Legacy **`on`** hurts inheritance performance at scale. Confirm **`SHOW constraint_exclusion`** during inheritance maintenance.

## Inheritance in pg_dump restore order

**`pg_dump`** emits child tables after parent; FK between children requires careful restore order. Declarative partitioning dump order cleaner—another migration incentive.




## Time zone and partition bounds

Monthly partition **`FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')`** uses timestamp without time zone—define whether bounds UTC or local; inheritance CHECK constraints same ambiguity caused off-by-one-month bugs in global apps.

## Testing ONLY semantics in CI

Automated test: insert into child, update parent without ONLY expecting child unchanged—fails if ONLY omitted. Guards regression when ORM raw SQL touches parent table name.




## Hash partitioning migration note

When migrating inheritance time-series to **`PARTITION BY HASH`**, pruning differs from range—queries without hash key scan all partitions. Inheritance monthly range maps naturally to declarative range; do not choose hash unless equality on partition key dominates access patterns.




## Row movement between partitions

Declarative **`ATTACH/DETACH`** replaces inheritance manual child create/drop for archival—**`DETACH CONCURRENTLY`** (PG 14+) reduces locking during archive. Plan archive pipeline on declarative even if current state inheritance—migration payoff includes online detach.

## Executor Append vs MergeAppend

Partitioned plans may use **`MergeAppend`** when partition key ordered—inheritance typically **`Append`**. Sort requirements differ; ORM **`ORDER BY created_at`** on inherited parent may sort after append—inherits higher cost than declarative merge append optimization.



## Migration communication template

Tell application teams: parent table inserts will route automatically after declarative migration; remove manual child table names from INSERT statements. Provide list of ONLY-qualified maintenance scripts requiring audit. Schedule migration when partition creation job disabled to avoid race creating inheritance child and declarative partition same month.

## Performance testing inherited vs partitioned

Benchmark identical row count: time SELECT with range filter on partition key. Expect declarative win on planning time and insert path—quantify win for migration ROI slide deck to engineering leadership.


## Documentation for ONLY semantics

Add SQLFluff or lint rule flagging UPDATE/DELETE on inherited parent without ONLY keyword in migration scripts—human review misses during fast releases.




## Constraint naming for exclusion

Child check constraints on inherited tables need distinct names—duplicate constraint names across children break pg_dump restore. Prefix constraint names with child table name in migration generators.

## Global temporary migration flag

Feature flag routes inserts to new partitioned table dual-write period—compare row counts inheritance vs partition before cutover read path. Dual-write complexity buys zero-downtime for large tables.

## Read path cutover checklist

After migration to declarative partitioning, grep application SQL for child table names used in FROM clause—legacy read paths bypass parent pruning and miss new partitions if hardcoded to old child names.

Schema review should reject new INHERITS usage for partitioning; point authors at declarative PARTITION BY with a short example in the contributing guide.

Write the failure mode you accept for postgres table inheritance patterns into the runbook next to the config that enforces it — configuration without narrative decays into cargo cult.

## Resources

- [Table inheritance](https://www.postgresql.org/docs/current/ddl-inherit.html)
- [Declarative partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
