---
title: "Postgres WAL Compression and Archiving"
slug: "postgres-wal-compression-archiving"
description: "Enable wal_compression, archive to object storage, and monitor archive_command failures before disk fill."
datePublished: "2026-03-10"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "postgres wal compression, wal archiving, archive_command, pg_stat_archiver, point in time recovery"
faq:
  - q: "Does wal_compression reduce durability or recovery safety?"
    a: "No. Compression applies to full-page images stored inside WAL records when a page change would otherwise bloat the log. The WAL stream remains sequential and crash-safe; restore tools decompress transparently. You still need reliable archiving and tested PITR drills."
  - q: "Should I use archive_command or a dedicated tool like pgBackRest or WAL-G?"
    a: "archive_command works for small clusters with simple S3 uploads, but production teams usually adopt pgBackRest or WAL-G for parallel WAL push, retention policies, and integrated base backups. Either way, monitor pg_stat_archiver and never delete files from pg_wal manually."
  - q: "What happens when archive_command fails repeatedly?"
    a: "Postgres keeps recycling WAL segments locally until archive_mode succeeds or wal_keep_size limits are hit. Sustained failures fill the WAL partition, block checkpoints, and can halt writes. Alert on failed_count and last_failed_time from pg_stat_archiver before disk pressure."
---

A checkout service survived a bad deploy because point-in-time recovery rewound forty minutes — but only because WAL segments had been archiving cleanly for six months. The on-call engineer who almost deleted "old" files from `pg_wal` during a disk alert would have made those archives useless. WAL compression and archiving are not backup trivia; they are the difference between a rehearsed restore and a resume-generating outage.

## How WAL flows from checkpoint to archive

Every committed transaction appends to the Write-Ahead Log before dirty buffers hit data files. Checkpoints mark boundaries: segments before the redo pointer can be recycled locally or shipped to cold storage for PITR.

```
Transaction commit
       │
       ▼
  WAL insert ──► pg_wal/000000010000000000000001
       │
       ▼
  Checkpoint ──► redo pointer advances
       │
       ▼
  archive_command ──► s3://backups/wal/...
       │
       ▼
  Segment eligible for local recycle (if archived)
```

Three settings define the contract:

| Setting | Role |
|---------|------|
| `wal_level = replica` (or `logical`) | Enough detail for archiving and replicas |
| `archive_mode = on` | Invoke `archive_command` for completed segments |
| `archive_command` | Shell command that exits 0 only after durable upload |

Inspect live status:

```sql
SELECT archived_count,
       failed_count,
       last_archived_wal,
       last_failed_wal,
       last_failed_time,
       stats_reset
FROM pg_stat_archiver;
```

If `failed_count` climbs while `pg_wal` disk usage grows, you are one traffic spike away from write stalls. Page on `failed_count` delta, not only on "disk 85% full."

## wal_compression: what it actually compresses

Before PostgreSQL 15, `wal_compression` was a boolean. PG15+ adds `wal_compression = pglz | lz4 | zstd` (availability depends on build flags). The setting targets **full-page images** (FPIs) written to WAL when a buffer page first changes after a checkpoint.

Without compression, a single bulk update can flood WAL with 8 KB full-page copies. With compression enabled, Postgres stores a compressed representation; replay decompresses during recovery.

```ini
# postgresql.conf
wal_compression = lz4          # good CPU/ratio tradeoff on most hardware
full_page_writes = on          # keep on unless you deeply understand the risk
```

Measure impact on a staging clone under your heaviest write pattern:

```sql
SELECT wal_records,
       wal_fpi,
       wal_bytes,
       wal_bytes / NULLIF(extract(epoch FROM now() - stats_reset), 0) AS bytes_per_sec
FROM pg_stat_wal;
```

Compare `wal_fpi` and `wal_bytes` before and after toggling compression during a bulk load. Expect 30–60% WAL byte reduction on FPI-heavy workloads; OLTP with small row updates sees smaller gains.

**Do not confuse** `wal_compression` with base-backup compression in pgBackRest (`compress-type=zst`). Each layer solves a different bottleneck.

## wal_compression algorithm selection

| Method | CPU | Ratio on FPI-heavy load | Notes |
|--------|-----|-------------------------|-------|
| `pglz` | Moderate | Good | Default pre-15 boolean true |
| `lz4` | Low | Good | Favored on CPU-constrained instances |
| `zstd` | Higher | Best | PG15+ when built with zstd |

Benchmark on production-like instance class, not laptop. Compression runs on the WAL insert path — pathological regression shows up as elevated `user` CPU during bulk loads, not during SELECT-heavy workloads.

## Building archive_command for object storage

A minimal S3 upload script must be idempotent — re-archiving the same segment after a partial failure must overwrite safely:

```bash
#!/bin/bash
set -euo pipefail
WAL_PATH="$1"
WAL_NAME="$2"
BUCKET="s3://prod-pg-wal/${PGHOST}/${WAL_NAME}"

aws s3 cp "${WAL_PATH}" "${BUCKET}" \
  --storage-class STANDARD_IA \
  --only-show-errors

aws s3api head-object --bucket prod-pg-wal --key "${PGHOST}/${WAL_NAME}"
```

```ini
archive_command = '/usr/local/bin/archive_wal.sh %p %f'
archive_timeout = 300
```

`%p` is the absolute path; `%f` is the filename only. Use `archive_timeout` so low-traffic databases still produce archivable segments.

For multi-tenant fleets, prefix object keys with cluster identity. IAM policies should allow `PutObject` and `HeadObject` only on the WAL prefix.

## pgBackRest as the production default

Hand-rolled `archive_command` scripts rot quickly. pgBackRest integrates base backups, WAL push, retention, and encryption:

```ini
[prod]
pg1-path=/var/lib/postgresql/16/main
repo1-type=s3
repo1-s3-bucket=prod-pgbackrest
repo1-retention-full=4
compress-type=zst
```

```ini
archive_mode = on
archive_command = 'pgbackrest --stanza=prod archive-push %p'
restore_command = 'pgbackrest --stanza=prod archive-get %f %p'
```

Run `pgbackrest check` and quarterly restore drills. A backup that never restores is folklore.

## Interaction with replication slots

Physical replicas and logical decoding slots pin WAL on the primary until consumers replay it. A healthy archiver can upload segments while replicas lag — but if `pg_replication_slots` shows an inactive forgotten slot, WAL balloons regardless of compression.

```sql
SELECT slot_name, slot_type, active,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained
FROM pg_replication_slots
ORDER BY retained DESC;
```

Drop orphaned slots after confirming no consumer needs them. Compression savings stay on the publishing side; logical subscribers receive decoded row changes, not raw compressed FPIs.

## Monitoring and SLIs

Define an SLI: **99% of completed WAL segments appear in object storage within 120 seconds of segment close.**

Instrument with:

1. `pg_stat_archiver.failed_count` — counter delta alert
2. Object storage uploaded bytes/day vs WAL bytes/day
3. Lag between latest archived WAL name and `pg_current_wal_lsn()`

```sql
SELECT pg_walfile_name(pg_current_wal_lsn()) AS current_wal;
```

During incidents, **never** `rm` files from `pg_wal`. Fix the archiver. Manual deletion creates gaps that restore discovers at 3 AM.

## Restore drill: prove compression end-to-end

Quarterly, restore to an isolated instance:

```bash
pgbackrest --stanza=prod restore --type=time \
  --target="2026-07-01 14:30:00+00" \
  --target-action=promote
```

Confirm compressed WAL replays without error and document wall-clock recovery time.

## Failure scenarios and responses

**Archive credentials expired.** Writes continue; WAL disk fills over hours. Rotate keys; replay failed segments with `pgbackrest archive-push` for each `last_failed_wal`.

**Network partition to S3.** Postgres retries `archive_command`. If failures persist past `wal_keep_size`, primary disk pressure rises.

**Partial upload treated as success.** A buggy script exiting 0 before upload completes creates silent PITR gaps. Always verify object presence inside `archive_command`.

## Sizing WAL disk with compression

Size `pg_wal` mount for **peak WAL generation rate × maximum expected archive outage duration × safety factor**, then reduce slightly if compression cuts bytes 40%+. Pair with `max_wal_size` and `min_wal_size` tuned to checkpoint behavior.

## Legal hold and immutable archives

Regulated industries sometimes require WORM storage for WAL archives. S3 Object Lock in compliance mode prevents deletion until retention expires — pair with pgBackRest repo settings and separate AWS account for backup bucket.

## Closing checklist

- [ ] `wal_compression` benchmarked on bulk-load workload
- [ ] `archive_command` verifies upload before exit 0
- [ ] Alerts on `pg_stat_archiver.failed_count`
- [ ] pgBackRest or equivalent restore tested this quarter
- [ ] Runbook explicitly forbids manual `pg_wal` deletion
- [ ] IAM least privilege on WAL bucket prefix

WAL compression saves bandwidth and disk; reliable archiving saves the company. Measure both, drill restore often, and treat archiver failures as write-path incidents waiting to happen.

## Archive lag during bulk operations

Bulk loads generate WAL faster than archive_command uploads — especially before compression kicks in on FPI-heavy pages. During migration windows, watch both `pg_wal` disk slope and `last_archived_wal` lag. Temporary mitigations include throttling batch jobs, raising archive parallelism via pgBackRest `process-max`, or adding WAL disk headroom for the maintenance window only. Do not disable archiving to "speed up" bulk load — you trade minutes of load time for unrecoverable gaps.

## pg_switch_wal and manual segment rotation

`SELECT pg_switch_wal();` forces current segment closed for testing archive pipeline in staging. In production, use only during controlled drills — unnecessary switches increase archive API calls and S3 LIST costs. Pair with `pg_walfile_name(pg_switch_wal())` in runbooks so engineers verify the segment appears in object storage within SLI window.

## Cross-version restore and compression

Major version upgrades (PG15 → PG16) require restore testing with compressed WAL from the **old** version replayed on the **new** binary. Compression codecs available differ by build. Maintain a staging cluster on target version that restores from production archive monthly — version skew surprises belong in scheduled drills, not production PITR.

## wal_keep_size vs archiving

`wal_keep_size` retains WAL for replicas independent of archiving. A common misconfiguration sets enormous `wal_keep_size` "just in case" while archive fails silently — disk fills despite terabytes of "kept" WAL that were never uploaded. Treat `wal_keep_size` as replica safety margin, not backup substitute. Archiver success is the backup contract.
