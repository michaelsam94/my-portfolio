---
title: "Postgres REINDEX CONCURRENTLY and Bloat"
slug: "postgres-reindex-concurrently-bloat"
description: "Detect index bloat, rebuild with REINDEX CONCURRENTLY, and avoid the locking and duplicate-index pitfalls that stall production."
datePublished: "2026-03-02"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "REINDEX CONCURRENTLY, postgres index bloat, pgstatindex, vacuum bloat, index maintenance"
faq:
  - q: "What causes Postgres index bloat and how is it different from table bloat?"
    a: "Index bloat is wasted space in B-tree pages from version churn—updates and deletes leave dead entries until vacuum reclaims them. Table bloat is dead heap tuples; index bloat is dead index tuples. Both correlate but require different remediation."
  - q: "When should I use REINDEX CONCURRENTLY instead of VACUUM FULL or regular REINDEX?"
    a: "REINDEX CONCURRENTLY rebuilds the index without blocking writes. Use when bloat degrades query plans or index size threatens disk but downtime is unacceptable. Regular REINDEX takes ACCESS EXCLUSIVE lock. VACUUM FULL rewrites heap and locks heavily."
  - q: "Can REINDEX CONCURRENTLY fail or leave duplicate indexes?"
    a: "Yes. If build fails mid-flight, an invalid duplicate index (_ccnew suffix) may remain and must be dropped manually. Concurrent builds require two table scans and more WAL. Monitor pg_index.indisvalid and disk space before starting."
  - q: "How do I measure index bloat before reindexing?"
    a: "Use pgstatindex from pgstattuple extension, or compare index size to expected size from row count. Reindex when bloat exceeds 30–50% and autovacuum cannot keep pace, especially on high idx_scan indexes."
---

Indexes are supposed to make queries fast. Bloated indexes make them slow and expensive—they occupy buffer cache with dead entries, widen scans, and sometimes nudge the planner toward sequential scans you thought you'd eliminated. **`VACUUM`** reclaims dead heap tuples and marks index entries dead, but heavy churn can leave B-trees fragmented enough that only a **rebuild** restores lean structure.

**`REINDEX CONCURRENTLY`**, available since Postgres 12, rebuilds an index without holding **`ACCESS EXCLUSIVE`** lock for the entire operation. That makes it the primary online remediation for production bloat—if you respect failure modes, disk appetite, and the difference between fixing indexes versus fixing tables.

## How bloat accumulates

Every `UPDATE` in Postgres is delete + insert at heap level; indexes gain new entries and leave old ones until vacuum cleans them. Factors accelerating bloat:

- High update/delete rate on indexed columns
- Long-running transactions holding xmin horizon
- Low fillfactor without justification
- Wide composite indexes on volatile columns

Symptoms: index size 3× reasonable estimate, `EXPLAIN` Bitmap Index Scan reading far more buffers than rows returned, autovacuum aggressive on same table with little size drop.

## Measuring bloat

```sql
CREATE EXTENSION IF NOT EXISTS pgstattuple;
SELECT * FROM pgstatindex('public.orders_created_at_idx');
```

Practical monitoring:

```sql
SELECT schemaname, indexrelname AS index_name,
       pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
       idx_scan
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(indexrelid) DESC;
```

Cross-check **`idx_scan`**: bloated index with zero scans is a drop candidate, not reindex.

## Regular REINDEX vs CONCURRENTLY

```sql
REINDEX INDEX CONCURRENTLY public.orders_created_at_idx;
REINDEX TABLE CONCURRENTLY public.orders;
```

**`REINDEX CONCURRENTLY`**: creates new index, two passes, swap in catalog. Locks **`Share Update Exclusive`** during phases—writes continue.

**Cannot run inside transaction block.** Failed runs may leave invalid index:

```sql
SELECT indexrelid::regclass, indisvalid
FROM pg_index JOIN pg_class ON pg_class.oid = indexrelid
WHERE NOT indisvalid;
```

```sql
DROP INDEX CONCURRENTLY IF EXISTS orders_created_at_idx_ccnew;
```

## Operational checklist before CONCURRENTLY

1. **Disk space:** need roughly index size free during build
2. **WAL and replication:** watch replica lag during rebuild
3. **maintenance_work_mem:** raise session-local for build speed
4. **One big index at a time** on same table reduces contention
5. **Document rollback** if invalid index left

## fillfactor and prevention

```sql
ALTER INDEX orders_status_idx SET (fillfactor = 90);
REINDEX INDEX CONCURRENTLY orders_status_idx;
```

Only lower fillfactor when updates touch indexed columns.

**Autovacuum tuning** on churn tables:

```sql
ALTER TABLE orders SET (
  autovacuum_vacuum_scale_factor = 0.02,
  autovacuum_analyze_scale_factor = 0.01
);
```

Aggressive vacuum prevents bloat better than monthly reindex firefighting.

## Table bloat: different remedies

| Command | Heap | Indexes | Blocks writes? |
| --- | --- | --- | --- |
| VACUUM | Marks dead reusable | Cleans dead entries | No |
| VACUUM FULL | Rewrites compact | No | Yes |
| REINDEX CONCURRENTLY | No | Rebuilds | Minimal |
| pg_repack | Online rewrite | Optional | Extension |

After **`VACUUM FULL`**, indexes often need **`REINDEX`**.

## GiST, GIN, and BRIN bloat

**GIN** on jsonb inflates from pending list merge lag—watch **`gin_pending_list_limit`**. **BRIN** rarely needs reindex; wrong **`pages_per_range`** is usually the issue.

## Autovacuum vs reindex decision tree

1. Run **`VACUUM (VERBOSE, ANALYZE)`**; recheck index size
2. If **`pgstatindex`** leaf density still poor and **`idx_scan`** high → **`REINDEX CONCURRENTLY`**
3. If **`idx_scan`** near zero → **`DROP INDEX CONCURRENTLY`**
4. If heap dead_pct high → tune autovacuum first

Skipping step four guarantees repeat bloat within weeks.

## Monitoring reindex progress

Postgres 14+:

```sql
SELECT phase, blocks_total, blocks_done
FROM pg_stat_progress_create_index
WHERE relid = 'public.orders'::regclass;
```

Alert on jobs stuck waiting for old snapshots.

## When to drop instead of reindex

Unused per **`idx_scan`**, redundant covering same prefix, partial index predicate obsolete.

## Cadence recommendation

- Weekly: top indexes by size + scan ratio
- Monthly: bloat trend; autovacuum effectiveness
- Quarterly: rehearse CONCURRENTLY on staging clone
- Reactive: reindex when size > 1.5× modeled or planner regression

Bloat is inevitable on write-heavy OLTP; **`REINDEX CONCURRENTLY`** is the scalpel when vacuum cannot keep up.



## pg_repack vs REINDEX CONCURRENTLY tradeoff

**`pg_repack`** rewrites heap online with triggers capturing concurrent changes—repairs table bloat and can relocate tablespace. **`REINDEX CONCURRENTLY`** targets index bloat without full heap rewrite. After prolonged bloat, both heap and indexes suffer—sequence **`VACUUM`**, **`pg_repack`**, then **`REINDEX CONCURRENTLY`** on remaining fat indexes. Do not **`REINDEX`** entire schema concurrently during peak—IO saturation raises commit latency via WAL flush contention.

## Index-only scan invalidation

Reindex rebuilds index statistics implicitly via planner relcache refresh; still run **`ANALYZE`** on table after large reindex campaign—correlation stats drift separately. **`pg_stat_all_indexes`** **`idx_scan`** reset not automatic—compare pre/post **`EXPLAIN`** on top queries saved in **`pg_stat_statements`**.

## Production scheduling windows

Prefer reindex during regional off-peak even though writes continue—catch-up phase on **`REINDEX CONCURRENTLY`** competes with batch ETL. Cancel long-running reindex if replica lag exceeds SLA; resume later. Postgres 16 progress views help estimate ETA for change management tickets.

## Hash index note

Hash indexes (rare) support **`REINDEX`** but not all concurrent variants on older versions—verify docs for your version before automating. Most teams use B-tree; GIN/GiST concurrent reindex widely supported since PG 12.




## Bloat on primary key indexes after UUIDv4 migration

Random UUID PK inserts cause index bloat faster than monotonic bigint—autovacuum may lag on **`pg_stat_user_tables.n_dead_tup`**. Pair UUID PK with aggressive autovacuum or switch to UUIDv7 before reindex becomes weekly chore. **`REINDEX CONCURRENTLY`** on PK during traffic still safer than non-concurrent but plan disk for largest index first.

## Lock interaction with DDL during reindex

**`REINDEX CONCURRENTLY`** blocks some DDL on same table—concurrent **`ADD COLUMN`** may wait. Coordinate schema migrations with index maintenance windows. **`ACCESS EXCLUSIVE`** still taken briefly at end—surprise brief blocking possible.




## Summary checklist before production reindex

Confirm free disk, valid index list, on-call notified, replica lag dashboard open, rollback DROP for **_ccnew** documented, and post-reindex ANALYZE scheduled. One-page checklist prevents 3 AM pages about full disks mid-reindex.



## Post-reindex verification queries

After each REINDEX CONCURRENTLY, capture pg_relation_size before/after, pgstatindex leaf density, and one EXPLAIN ANALYZE from pg_stat_statements top query using that index. Store in ticket—future you proves value to management or catches invalid index left behind. Schedule ANALYZE on parent table same maintenance window.

## Index bloat early warning

Alert when pg_relation_size(index) / NULLIF(pg_relation_size(table),0) exceeds threshold for table class—OLTP narrow indexes ratio lower than JSONB GIN indexes. Per-table thresholds beat global percentage for fewer false pages.


## Coordination with autovacuum

Schedule heavy REINDEX after autovacuum window completes on same table—competing IO lengthens both jobs. Increase autovacuum_vacuum_cost_limit temporarily only with monitoring—aggressive vacuum plus reindex can starve OLTP.





## Invalid index automated cleanup

Cron job queries pg_index indisvalid false, opens ticket with index name, auto-drops _ccnew suffix indexes older than 24h after confirming no valid swap pending. Prevents catalog clutter from aborted concurrent builds blocking future DDL.

## fillfactor on unique indexes

Lower fillfactor on unique indexes still applies—unique constraints on volatile columns benefit from 90 fillfactor plus scheduled REINDEX CONCURRENTLY quarterly on known hot indexes rather than reactive firefighting.

## Wrap-around and reindex urgency

When autovacuum cannot keep pace near wraparound warnings, REINDEX CONCURRENTLY on bloated indexes reduces index scan cost during emergency vacuum operations—coordinate with DBA playbooks for transaction id freeze scenarios.

Document every production REINDEX in change management with index oid, size before/after, and business justification—auditors and future DBAs need history beyond pg_stat progress views.

After every concurrent reindex window, query `pg_index` for `NOT indisvalid` and page if any appear — failed rebuilds leave junk that the next on-call will misdiagnose.

## Resources

- [PostgreSQL REINDEX](https://www.postgresql.org/docs/current/sql-reindex.html)
- [pgstattuple](https://www.postgresql.org/docs/current/pgstattuple.html)
- [Routine vacuuming](https://www.postgresql.org/docs/current/routine-vacuuming.html)
