---
title: "Postgres Failover pg_rewind"
slug: "postgres-failover-pg-rewind"
description: "Resync a former primary back into the replication cluster with pg_rewind after failover — requirements, workflow, and pitfalls."
datePublished: "2026-02-23"
dateModified: "2026-07-17"
tags:
  - "PostgreSQL"
  - "Backend"
  - "Database"
keywords: "pg_rewind, postgres failover, timeline fork, reintegrate old primary, streaming replication"
faq:
  - q: "When do I need pg_rewind instead of rebuilding the old primary from scratch?"
    a: "After failover, the old primary has diverged WAL on a forked timeline. pg_rewind copies only changed data blocks from the new primary and rewinds the old primary's WAL to rejoin as a replica — much faster than pg_basebackup for large databases when divergence is small (minutes of writes, not hours)."
  - q: "What prerequisites must be met before running pg_rewind?"
    a: "Both clusters must have wal_log_hints enabled (or data checksums enabled), the target (new primary) must still have WAL back to the divergence point, and you need SSH or file-level access between nodes. pg_rewind requires the old primary to be shut down cleanly before execution."
  - q: "Can pg_rewind fix a split-brain scenario automatically?"
    a: "No. pg_rewind assumes you have identified the correct primary and intentionally reintegrate the old one as a standby. Split-brain requires manual decision on which timeline is authoritative, fencing the old primary from receiving writes, then running pg_rewind or basebackup."
---

Failover promotes a standby to primary. The old primary — if it comes back online — still believes it is primary, holds writes on a forked timeline, and cannot rejoin the cluster with a simple `pg_ctl start`. Rebuilding from `pg_basebackup` works but takes hours on terabyte databases. **pg_rewind** rewinds the old primary to the divergence point and resyncs only changed blocks from the new primary, turning a multi-hour rebuild into a minutes-long operation.

This article covers timeline mechanics, prerequisites, step-by-step workflow, and the failure modes that catch operators during their first real failover.

## Timeline forks after failover

Postgres replication assigns a **timeline** ID to each promotion event:

```
Timeline 1: original primary (node A)
  │
  ├── Failover: standby (node B) promoted → Timeline 2
  │
  └── Old primary (node A) may have accepted writes on Timeline 1
      after B was promoted → divergent history
```

The new primary (node B) on Timeline 2 has a **history file** recording the divergence LSN. pg_rewind reads this history to find where timelines split, then:

1. Reads the old primary's data files
2. Identifies blocks changed on the old primary after divergence
3. Copies correct blocks from the new primary
4. Updates control files and WAL to attach to Timeline 2 as a standby

## Prerequisites

Enable block-level change tracking (required for pg_rewind to know which blocks changed):

```sql
-- Option A: data checksums (enabled at initdb, cannot enable later without rebuild)
-- initdb --data-checksum

-- Option B: wal_log_hints (can enable on existing cluster)
ALTER SYSTEM SET wal_log_hints = on;
-- Requires restart
```

Verify:

```sql
SHOW data_checksums;  -- on or off
SHOW wal_log_hints;     -- on required if checksums off
```

Other requirements:

- Old primary must be **stopped** before pg_rewind runs
- New primary must retain WAL from divergence point (check `wal_keep_size` or archive)
- pg_rewind binary matching Postgres major version on the old primary node
- Network access from old primary to new primary (SSH tunnel or local path via `-R`)

## Step-by-step reintegration workflow

**Context**: Node A was primary. Node B promoted during failover. Node A is now offline with divergent data.

### 1. Fence the old primary

Ensure node A cannot accept writes or become primary again accidentally:

- Load balancer health check removes it
- `pg_ctl stop` on node A (if running)
- STONITH / cloud API stop instance if uncertain

### 2. Verify new primary is healthy

On node B (current primary):

```sql
SELECT pg_is_in_recovery();  -- false
SELECT timeline_id, redo_lsn FROM pg_control_checkpoint();
```

Confirm replication slots and standbys are connected:

```sql
SELECT client_addr, state, sync_state
FROM pg_stat_replication;
```

### 3. Run pg_rewind on old primary

On node A:

```bash
# Stop Postgres if running
pg_ctl -D /var/lib/postgresql/data stop

# Run pg_rewind — target is new primary
pg_rewind --target-server="host=node-b port=5432 user=rewind_user dbname=postgres" \
  --source-server="host=node-b port=5432 user=rewind_user dbname=postgres" \
  -D /var/lib/postgresql/data \
  --progress
```

Note: `--target-server` and `--source-server` flags vary by version. In PG 15+:

```bash
pg_rewind -D /var/lib/postgresql/data \
  --source-server="host=node-b port=5432 user=rewind_user dbname=postgres" \
  --progress
```

Create dedicated rewind user on new primary:

```sql
CREATE USER rewind_user WITH REPLICATION;
GRANT EXECUTE ON FUNCTION pg_read_file(text) TO rewind_user;  -- version-dependent
-- pg_rewind handles most permissions via replication protocol in PG 11+
```

### 4. Configure node A as standby

After pg_rewind completes, create standby signal and replication connection:

```bash
touch /var/lib/postgresql/data/standby.signal

cat >> /var/lib/postgresql/data/postgresql.auto.conf <<EOF
primary_conninfo = 'host=node-b port=5432 user=replicator password=... application_name=node-a'
primary_slot_name = 'node_a_slot'
EOF
```

Create replication slot on primary before starting standby:

```sql
SELECT pg_create_physical_replication_slot('node_a_slot');
```

### 5. Start node A

```bash
pg_ctl -D /var/lib/postgresql/data start
```

Verify on primary:

```sql
SELECT application_name, client_addr, state, sync_state
FROM pg_stat_replication
WHERE application_name = 'node-a';
-- state: streaming
```

## What pg_rewind does NOT do

- **Does not merge conflicting writes**: If both nodes accepted writes after divergence, data from the old primary's post-divergence writes is discarded
- **Does not replace pg_basebackup for large divergence**: If WAL history is unavailable or divergence spans days, full rebuild is faster and safer
- **Does not handle logical replication**: Physical replication only
- **Does not fix corrupted pages**: Checksum failures require different recovery

## When to use pg_basebackup instead

| Scenario | pg_rewind | pg_basebackup |
| --- | --- | --- |
| Minutes of divergence after failover | Preferred | Overkill |
| Hours/days of divergence | WAL may be gone | Required |
| Old primary never had wal_log_hints | Cannot run | Required |
| Major version upgrade during reintegration | Not supported | Required |
| Corruption suspected | Not safe | Required |

## Automation with Patroni / repmgr

HA frameworks automate pg_rewind:

**Patroni**: When a former primary rejoins, Patroni detects timeline divergence and invokes pg_rewind automatically if `pg_rewind` is configured in the DCS:

```yaml
postgresql:
  use_pg_rewind: true
  parameters:
    wal_log_hints: 'on'
```

**repmgr**: `repmgr node rejoin` wraps pg_rewind with configuration validation.

Manual pg_rewind is primarily for operators without HA frameworks or during framework recovery.

## WAL retention for rewind success

pg_rewind needs WAL on the source (new primary) back to the divergence LSN:

```sql
-- Ensure sufficient WAL retention
ALTER SYSTEM SET wal_keep_size = '2GB';  -- PG13+
-- Or use archive_command to S3/backup
```

If required WAL is missing:

```
pg_rewind: error: source server does not have the required WAL segment
```

Recovery: pg_basebackup from new primary, or restore WAL from archive to source before retry.

## Split-brain prevention

Split-brain occurs when both nodes accept writes believing they are primary. pg_rewind is a recovery tool, not prevention:

Prevention layers:

1. **STONITH/fencing**: Old primary loses connectivity or power during promotion
2. **Synchronous replication with quorum**: Promotion requires majority witness
3. **Leader election (Patroni/etcd)**: Only one node holds leader lock
4. **Load balancer health checks**: Route traffic only to confirmed primary

After split-brain is resolved manually, pg_rewind reintegrates the losing node.

## Monitoring after reintegration

Watch for:

```sql
-- Replication lag on reintegrated node
SELECT pg_wal_lsn_diff(
  pg_current_wal_lsn(),
  replay_lsn
) AS lag_bytes
FROM pg_stat_replication
WHERE application_name = 'node-a';
```

Temporary elevated lag is normal as the standby catches up. Persistent lag indicates network or resource issues on node A.

Verify timeline alignment:

```sql
-- On standby (node A)
SELECT pg_is_in_recovery(), pg_last_wal_replay_lsn();

-- On primary (node B)
SELECT pg_current_wal_lsn();
```

## Testing pg_rewind in staging

Rehearse failover quarterly:

1. Promote standby in staging
2. Write data to old primary after promotion (simulate split-brain)
3. Stop old primary
4. Run pg_rewind
5. Verify data consistency: row counts, checksum queries
6. Measure rewind duration vs basebackup duration

Document timing — this informs incident response expectations.

## Common errors

**`pg_rewind: error: target server must be shut down cleanly`**
Run `pg_ctl stop` before pg_rewind. Crash recovery must complete first.

**`pg_rewind: error: data checksums are not enabled and wal_log_hints is off`**
Enable wal_log_hints, restart, run checkpoint, then failover scenario can use pg_rewind going forward. Existing divergent nodes still need basebackup.

**Permission denied on source server**
Ensure rewind user has replication privilege and pg_rewind-compatible permissions for your PG version.

## Post-rewind validation queries

After reintegration, run consistency checks before returning node A to the connection pool:

```sql
-- Timeline alignment
SELECT pg_is_in_recovery(), pg_last_wal_replay_lsn();

-- Compare row counts on critical tables (on both nodes)
SELECT 'orders' AS tbl, count(*) FROM orders
UNION ALL SELECT 'customers', count(*) FROM customers;

-- Verify replication slot is active
SELECT slot_name, active, restart_lsn FROM pg_replication_slots;
```

Schedule application smoke tests against the reintegrated standby before adding it to read load balancers. A successful pg_rewind does not guarantee application-level consistency if divergent writes occurred before fencing — business validation catches edge cases block-level sync misses.

## Summary

pg_rewind fast-tracks reintegrating a former primary as a standby after failover by copying only divergent blocks instead of rebuilding the entire data directory. Enable wal_log_hints or data checksums before you need it, retain sufficient WAL on the new primary, fence the old primary before rewinding, and automate with Patroni when possible. pg_rewind is not a split-brain cure — it is the last mile of a carefully executed failover recovery plan.
