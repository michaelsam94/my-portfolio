---
title: "Postgres pgBackRest Backup Strategy"
slug: "postgres-pgbackrest-backup-strategy"
description: "Configure full, differential, and incremental backups with pgBackRest, PITR, stanza design, and restore drills that actually get run."
datePublished: "2026-02-26"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "pgBackRest, postgres backup, PITR, incremental backup, stanza, restore drill"
faq:
  - q: "What backup types does pgBackRest support and when should I use each?"
    a: "Full backups copy all database files; differential backs up changes since the last full; incremental backs up changes since any prior backup in the chain. Use weekly or monthly fulls as anchors, daily differential or incremental for RPO, and tune retention so restore chains stay short enough to meet RTO."
  - q: "How does pgBackRest differ from pg_basebackup alone?"
    a: "pg_basebackup takes a physical copy at one moment. pgBackRest adds encrypted incremental/differential chains, parallel transfer, stanza management across primaries and replicas, WAL archiving integration, and restore orchestration including point-in-time recovery to a timestamp or transaction ID."
  - q: "Should backups run from the primary or a standby?"
    a: "Prefer a dedicated standby or backup replica when possible to avoid IO and CPU spikes on the primary. pgBackRest supports backup from standby with backup-standby=y; verify WAL archiving still flows from the primary and the standby is sufficiently caught up before backup starts."
  - q: "How often should we run restore drills?"
    a: "Quarterly at minimum for production databases with compliance requirements; monthly if backups have never been tested end-to-end. A backup without a verified restore is a hope, not a strategy. Automate restore to ephemeral instances and run application smoke tests."
---

Backups fail in quiet ways. The cron job succeeds, S3 fills with objects, dashboards show green—and then a restore takes eighteen hours because nobody noticed incrementals chained six months deep, or archive_command was misconfigured, or the encryption passphrase lived in one engineer's password manager until they left.

pgBackRest exists because Postgres physical backup at scale needs more than `pg_basebackup` in a shell script. It manages **stanzas** (named backup sets per cluster), **parallel file transfer**, **incremental chains**, **WAL push/pull**, and **unified restore** to a timestamp. This post is a strategy guide: how to configure it, schedule it, and prove it works before ransomware or operator error makes it urgent.

## Stanza-first mental model

A **stanza** is pgBackRest's name for one Postgres cluster (primary + optional standbys sharing the same data directory lineage). Configuration lives in `/etc/pgbackrest/pgbackrest.conf`:

```ini
[global]
repo1-type=s3
repo1-s3-bucket=prod-pg-backups
repo1-s3-region=us-east-1
repo1-cipher-type=aes-256-cbc
repo1-retention-full=4
repo1-retention-diff=14
process-max=4
start-fast=y
compress-type=zst

[prod]
pg1-path=/var/lib/postgresql/16/main
pg1-port=5432
pg1-user=postgres
pg1-host=pg-primary.internal
```

Initialize once after Postgres is running and archiving is configured:

```bash
sudo -u postgres pgbackrest --stanza=prod stanza-create
sudo -u postgres pgbackrest --stanza=prod check
```

`check` validates WAL archiving and connectivity—run it from monitoring, not only after install.

On replicas:

```ini
pg2-host=pg-replica.internal
pg2-path=/var/lib/postgresql/16/main
backup-standby=y
```

Backup from replica shifts read amplification off the primary; the primary must still archive WAL (`archive_mode = on`, `archive_command` invoking `pgbackrest archive-push`).

## WAL archiving: the non-negotiable half

Physical backup captures files at backup time; **point-in-time recovery** requires continuous WAL:

```sql
archive_mode = on
archive_command = 'pgbackrest --stanza=prod archive-push %p'
```

Monitor `pg_stat_archiver` — failed_count, last_failed_time. If `archive-push` fails silently, your last recoverable moment freezes at the last successful backup—not "now."

## Full, differential, incremental: building the chain

| Type | Base | Size | Restore steps |
| --- | --- | --- | --- |
| Full | — | Largest | 1 |
| Differential | Last full | Medium | Full + diff |
| Incremental | Last backup of any type | Smallest | Full + incr + … |

Typical schedule for 1 TB database, 15-minute RPO target:

- **Full:** Sunday 02:00 UTC (`--type=full`)
- **Incremental:** daily except Sunday (`--type=incr`)

```bash
0 2 * * 0  pgbackrest --stanza=prod --type=full backup
0 2 * * 1-6 pgbackrest --stanza=prod --type=incr backup
```

Retention (`repo1-retention-full=4`) keeps four full backups; associated incrementals prune when anchor full expires. **Tune retention to RPO/RTO**, not arbitrary month counts.

Deep incremental chains hurt RTO: restoring may replay dozens of layers. If restore tests exceed RTO, insert more full backups.

## Encryption, integrity, and offsite copies

Enable `repo1-cipher-type` and store passphrases in a secrets manager with break-glass procedure. pgBackRest verifies checksums per file.

**3-2-1 rule:** three copies, two media types, one offsite. S3 with cross-region replication or a second repo stanza satisfies offsite for many teams. Test DR repo restores independently.

## Point-in-time recovery workflow

Scenario: drop table at 14:32 UTC, need database as of 14:30 UTC.

```bash
pgbackrest --stanza=prod --type=time \
  --target="2026-07-17 14:30:00+00" \
  --target-action=promote \
  restore
```

Postgres replays WAL until target, then promotes. Document **timezone** in runbooks.

For **`--target-action=restore`** (pause before promote), inspect cluster, extract data, discard host—useful for forensic recovery without replacing production.

## Performance tuning on large clusters

- **`process-max`:** parallelize backup/restore; increase until disk or network saturates (often 4–8).
- **`start-fast=y`:** force checkpoint at backup start for predictable WAL boundaries.
- **`compress-type=zst`:** better ratio than gzip with acceptable CPU.
- **Tablespace mapping:** restore requires `--tablespace-map` or matching layout—document paths in stanza config.

## Restore drill playbook

Automated monthly drill:

```bash
pgbackrest --stanza=prod restore
pg_ctl -D $PGDATA start
psql -c "SELECT count(*) FROM critical_table;"
```

Success criteria: restore within documented RTO, application smoke tests pass, secrets applied from infrastructure-as-code.

Failed drills get priority equal to production outages—they indicate the next real outage will fail too.

## Failure modes and fixes

**Archive queue backlog:** Primary disk fills with `pg_wal` if push fails. Alert on directory size; fix repo credentials first.

**Stanza out of sync after major version upgrade:** Run `stanza-upgrade` after `pg_upgrade`.

**Backup from stale standby:** Require replica lag < threshold before backup job starts.

**Partial restore of single database:** pgBackRest is physical—restores whole cluster. For table-level recovery, restore to side host and use `pg_dump`/`COPY`.

**Ransomware:** Use immutable S3 Object Lock, separate AWS account for backups, MFA on delete.

## Integration with high availability

Patroni or cloud HA manage failover; pgBackRest manages **data durability outside the cluster**. After failover, re-run `check` after topology changes.

Do not confuse **replication** (live redundancy) with **backup** (time-travel). Replication won't save you from `TRUNCATE` propagated to all nodes; backup will.

## Choosing pgBackRest vs alternatives

| Tool | Strength | Weakness |
| --- | --- | --- |
| pgBackRest | Incremental chains, S3, encryption | Physical only; whole cluster |
| pg_basebackup + wal-g | Lighter, cloud-native | More assembly required |
| Logical pg_dump | Table/schema selective | Slow at TB scale |

For most self-managed production Postgres ≥ 100 GB with PITR requirements, pgBackRest is the default recommendation—if restore drills prove it.

Configure archiving before first full backup. Automate backups with explicit types and retention math tied to RPO/RTO. Run `check` continuously. Test restore to a blank machine quarterly. Only the drill measures recoverability.



## Monitoring backup health day to day

Treat **`pgbackrest info --output=json`** as a first-class metrics source. Parse **`backup`** arrays for **`error`**, **`timestamp`**, **`size`**, and **`delta`**. Alert when no successful backup completes within your RPO window, when incremental size spikes without matching write volume (possible bloat or bulk load), or when **`archive-push`** error counters in **`pg_stat_archiver`** increment. Dashboard backup duration trend lines—gradual doubling often precedes disk saturation on the repo or primary WAL directory.

Run **`pgbackrest --stanza=prod verify`** after any repo migration or credential rotation. Verification reads checksums without restoring—cheap confidence between full restore drills.

## stanza-upgrade and major version migrations

After **`pg_upgrade`** or initializing a new major on the same stanza name, run **`pgbackrest --stanza=prod stanza-upgrade`**. Skipping this leaves metadata incompatible with new **`PGDATA`** layout and produces opaque backup failures at the worst time—during the first post-upgrade cron. Document stanza-upgrade in the same runbook as **`analyze`** and extension updates.

## Tablespace-aware backup and restore

Multi-tablespace clusters require **`pg_tablespace_location(oid)`** documentation in runbooks. pgBackRest records mappings; restore hosts must recreate empty directories with correct ownership before **`restore`**. Teams that mount cold storage only on production forget the archive mount on restore VM—restore succeeds partially then fails mid-stream. Automate directory creation in restore Terraform/Ansible from stanza config exports.

## Compliance retention vs pgBackRest retention

Legal hold may require seven years while **`repo1-retention-full=4`** keeps only four weekly fulls. Map compliance windows to **`repo1-retention-*`** and optional second repo with Object Lock immutability. Incremental chains on immutable buckets need lifecycle policies that never delete legal-hold objects—coordinate with counsel before toggling S3 expiration.

## Incident timeline: archive_command silent failure

Typical failure chain: S3 IAM key rotated Friday; **`archive_command`** fails; **`pg_stat_archiver.failed_count`** climbs but alert threshold too high; Sunday full backup succeeds (point-in-time frozen at Sunday); Monday DBA drops table; Tuesday discovery that PITR cannot reach Monday morning. Fix: page on first archive failure, separate alerts for **`pg_wal`** directory size rate of change, weekly automated **`check`**. pgBackRest **`check`** catches many archive gaps before data loss manifests.


Restore drills should alternate regions and include key retrieval from the secret manager — not only a local repo restore with credentials already exported in the shell.

## Resources

- [pgBackRest user guide](https://pgbackrest.org/user-guide.html)
- [PostgreSQL continuous archiving](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [pgBackRest command reference](https://pgbackrest.org/command.html)
