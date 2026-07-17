---
title: "Postgres Tablespaces for IO Isolation"
slug: "postgres-tablespaces-io-isolation"
description: "Place hot indexes, WAL-adjacent storage, and cold archives on separate tablespaces to isolate IO and simplify tiered storage operations."
datePublished: "2026-03-07"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres tablespaces, IO isolation, storage tiering, pg_tablespace, index tablespace"
faq:
  - q: "What is a Postgres tablespace and what does it not do?"
    a: "A tablespace maps database objects to a directory on the filesystem. CREATE TABLE ... TABLESPACE ts puts heap and indexes on that path by default. Tablespaces do not shard queries across servers—they are single-instance storage layout on one Postgres cluster."
  - q: "When should I use separate tablespaces for IO isolation?"
    a: "When you have physically separate storage pools—NVMe for hot OLTP indexes, SATA for archival partitions—and want Postgres to place objects without manual file moves. Useful on bare metal and VMs with multiple attached volumes."
  - q: "Can I move an existing table to a different tablespace online?"
    a: "ALTER TABLE SET TABLESPACE rewrites the table (blocking). CREATE INDEX CONCURRENTLY can target a tablespace. pg_repack supports moving with reduced locking via extension."
  - q: "How do tablespaces interact with backups and restore?"
    a: "pg_basebackup and pgBackRest capture tablespace mappings. Restore requires matching mount paths or tablespace-map options. Mismatch causes restore failure—document TABLESPACE LOCATION paths in runbooks."
---

Default installs put everything under **`$PGDATA/base`**. That breaks down when historical archive on spinning disks competes with OLTP indexes on the same saturated volume. **Tablespaces** tell Postgres which directory stores which relation files—giving operators a native knob for **IO isolation** and **storage tiering**.

They are not magic on single-volume cloud RDS—they shine when you attach **multiple mounts** with different performance characteristics.

## Creating and using tablespaces

```sql
CREATE TABLESPACE fast_ssd LOCATION '/mnt/nvme/pg_fast';
CREATE TABLESPACE cold_hdd LOCATION '/mnt/sata/pg_cold';

CREATE TABLE orders (
  id bigint PRIMARY KEY,
  created_at timestamptz
) TABLESPACE fast_ssd;

CREATE INDEX orders_created_idx ON orders (created_at)
  TABLESPACE fast_ssd;
```

Directory must exist, owned by **`postgres`**, empty before **`CREATE TABLESPACE`**.

```sql
ALTER SYSTEM SET temp_tablespaces = 'fast_ssd';
```

Heavy sorts benefit from fast temp storage—often bigger win than moving cold tables.

## IO isolation strategies

**Hot/cold split by partition:**

```sql
CREATE TABLE events_2025 PARTITION OF events
  FOR VALUES FROM ('2025-01-01') TO ('2026-01-01')
  TABLESPACE cold_hdd;

CREATE TABLE events_2026 PARTITION OF events
  FOR VALUES FROM ('2026-01-01') TO ('2027-01-01')
  TABLESPACE fast_ssd;
```

**Index-only tiering:** heap on default, hot index on fast tier.

**ETL staging:** bulk COPY to scratch tablespace, promote to prod.

## WAL note

WAL lives in **`pg_wal` under PGDATA**—not assignable to tablespace. IO isolation for WAL requires separate mount at init or symlink. Tablespaces don't move WAL.

## Monitoring per tablespace

```sql
SELECT spcname, pg_size_pretty(pg_tablespace_size(oid)) AS size
FROM pg_tablespace;
```

OS level: **`iostat -x`** per device. Alert when fast tier > 85% capacity.

## Moving objects between tablespaces

Blocking:

```sql
ALTER TABLE orders SET TABLESPACE cold_hdd;
```

Online-ish:

```sql
CREATE INDEX CONCURRENTLY orders_new_idx ON orders (created_at)
  TABLESPACE fast_ssd;
DROP INDEX CONCURRENTLY orders_old_idx;
```

**pg_repack** can rebuild bloated tables on different tablespace.

## Backup and restore implications

```bash
pgbackrest --tablespace-map=/old/path=/new/path restore
```

Fail restore drill if staging only mirrors PGDATA but not cold mount.

## Cloud realities

RDS/Cloud SQL often single data volume—tablespaces cosmetic. EC2 with multiple EBS volumes: tablespaces align with volume boundaries.

Kubernetes: tablespace paths must survive pod reschedule on stable PVC mounts.

## Permissions

```sql
GRANT CREATE ON TABLESPACE fast_ssd TO app_owner;
```

Revoke from public. Paths must not be world-writable.

## pg_stat_io validation (PG 16+)

```sql
SELECT context, reads, writes FROM pg_stat_io ORDER BY reads DESC;
```

Compare before/after moving hot index to fast_ssd.

## Capacity planning across mounts

Maintain 15–20% free space on each mount—**CREATE INDEX CONCURRENTLY** and autovacuum need headroom on same volume.

## Sym linking WAL to fast storage

Some teams place **`$PGDATA/pg_wal`** on dedicated NVMe via symlink—complements tablespace tiering; document in backup runbooks.

## Anti-patterns

- Same physical device, different mount paths—illusory isolation
- Dozens of tablespaces without ownership
- Forgetting temp_tablespaces on saturated disk

## When tablespaces are the wrong tool

- Horizontal scale → replicas, sharding
- Query isolation → separate instances
- Single cloud volume → indexes, partitioning, hardware tier

Tablespaces are **layout**, not **architecture**—explicit control over which relations live on which disks when IO profiles differ.



## random_page_cost tuning per tablespace

When hot indexes live on NVMe and heap on SATA, global **`random_page_cost=4`** misleads planner—consider per-tablespace settings unavailable natively; instead lower **`random_page_cost`** session-wide when most queries hit fast tier, or use **`ALTER TABLE ... SET (fillfactor)`** plus proper indexing rather than fighting planner with tablespace alone.

## Tablespace quotas and filesystem limits

Separate mounts prevent cold archive fill from crashing entire **`PGDATA`**—operational win even before IO isolation proves measurable. Monitor inode exhaustion on small-file heavy GiST indexes on cold tier—size-based alerts miss **`ENOSPC`** from inode depletion.

## Read replicas and tablespace paths

Replica must mirror primary tablespace **`LOCATION`** paths—promoting replica fails if mount paths differ. Infrastructure-as-code should template identical mount layout on primary and standby AMIs/containers.

## DROP DATABASE and tablespace cleanup

**`DROP DATABASE`** removes files in each tablespace used by that database—verify no shared tablespace accidentally hosts multiple DBs before drop in shared environments. **`pg_tablespace_size`** per DB requires summing relations—use queries joining **`pg_class`** and **`pg_tablespace`**.




## temp_tablespaces spill monitoring

**`log_temp_files = 0`** logs all temp file creation—correlate large sorts with missing indexes vs need for faster temp tablespace. Moving temp to NVMe cheap win when **`EXPLAIN`** shows **`Sort`** megabytes to disk.

## encrypting tablespace paths

Tablespace directories inherit filesystem encryption (LUKS, EBS encryption)—Postgres TDE at rest separate feature in some enterprise builds. Cloud single-volume encryption does not replace application-level column encryption for PII on any tablespace.




## pg_repack tablespace move runbook sketch

Install extension, run **`pg_repack -k -T fast_ssd -t orders`**, verify size on new mount, drop old bloat on former tablespace, ANALYZE. **`--no-kill-long-queries`** for gentle start; kill blocking sessions if change window tight.

## Cost accounting

Finance charges cold SATA tier pennies per GB; hot NVMe dollars per GB—I/O isolation aligns cost with data temperature when finance asks why database storage grew. Tablespace names in **`pg_tables.tablespace`** feed chargeback reports.

## Single instance multiple tenants

Tablespaces rarely substitute for tenant isolation at security boundary—RLS and separate databases handle authorization; tablespaces handle performance tiering within shared schema designs.




## Verify tablespace placement after restore drill

Post-restore SQL: **`SELECT tablename, tablespace FROM pg_tables WHERE schemaname='public' ORDER BY 2,1`** compared to pre-backup export—catches restore mapping errors before go-live. Include in quarterly restore checklist alongside row counts and extension versions.




## Linux I/O scheduler and tablespace mounts

NVMe tablespace mount: verify **`none`** or **`mq-deadline`** scheduler appropriate; HDD archive: **`bfq`**. Scheduler misconfiguration masks tablespace tiering gains—validate with **`fio`** on each mount before attributing query wins to Postgres placement alone.

## pg_basebackup tablespace mapping file

**`pg_basebackup --tablespace-mapping=OLD=NEW`** required when restore host paths differ—generate mapping file from **`pg_tablespace_location`** query in backup script output stored alongside backup manifest JSON.


## When finance asks why storage costs rose

Tablespace-tiered layouts make cost attribution explicit: hot NVMe volumes carry recent partitions and index-heavy tables; cold tiers hold detached archives. Export monthly **`pg_tablespace_size`** per tablespace to billing dashboards so growth on fast tier triggers capacity review before insert latency degrades.


## Operational ownership model

Assign tablespace mount ownership to platform team—application teams request tier changes via ticket citing table oid and expected size growth. Unauthorized CREATE TABLESPACE on ad hoc NFS mount caused production outages when NFS blipped—ban developer-created tablespaces outside IaC.

## Measuring isolation success

Compare iostat await on fast vs cold device during ETL job—successful isolation shows cold device busy, fast device idle during archive scan. Failed isolation shows both devices saturated—tablespace mapping or query plan not hitting intended tier.


## Filesystem mount options

Use noatime on Postgres data mounts where appropriate; tablespace tiering irrelevant if OS metadata updates saturate disk. Document mount options in same runbook as TABLESPACE LOCATION paths.




## Tablespace and shared_buffers

Hot indexes on NVMe still compete for shared_buffers with cold heap pages—tablespace isolation does not isolate buffer cache. Monitor pg_buffercache extensions for hot relation blocks; consider higher shared_buffers before adding tablespaces.

## Cloud vendor tablespace support matrix

Document whether managed Postgres allows CREATE TABLESPACE at all—some restrict to superuser unavailable to customer, making entire strategy moot. Confirm before architecture review recommends tablespace tiering on RDS custom vs self-managed EC2.

## fstab and boot order

Tablespace mounts must appear in fstab before postgres systemd start—race on reboot leaves database down with missing LOCATION path. Use systemd RequiresMountsFor= on postgres unit.

Label each mount in monitoring with tablespace name—on-call maps alert to cold vs hot tier without guessing from device id alone.

## Resources

- [CREATE TABLESPACE](https://www.postgresql.org/docs/current/sql-createtablespace.html)
- [Storage file layout](https://www.postgresql.org/docs/current/storage-file-layout.html)
