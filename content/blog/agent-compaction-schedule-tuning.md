---
title: "LSM Compaction Schedule Tuning for Agent State Stores"
slug: "agent-compaction-schedule-tuning"
description: "Tune compaction schedules in RocksDB, Cassandra, and Scylla for agent memory and event stores: leveled vs tiered, write amplification, read latency, and operational dashboards."
datePublished: "2025-01-20"
dateModified: "2025-01-20"
tags: ["Databases", "RocksDB", "Performance", "AI Agents"]
keywords: "compaction schedule tuning, LSM compaction, RocksDB compaction, Cassandra compaction strategy, agent state store"
faq:
  - q: "Why does compaction matter for agent memory and tool state stores?"
    a: "Agent frameworks persist conversation turns, tool call results, and checkpoint state in LSM-backed stores (RocksDB, Cassandra, Dynamo-style engines). Writes append to memtables and SSTables; compaction merges them in the background. Poor tuning causes read amplification spikes (slow context retrieval), write stalls (checkpoint failures), and disk bloat that raises cloud bills."
  - q: "Leveled vs tiered compaction — which fits agent workloads?"
    a: "Agent state is usually read-heavy after write bursts (load session → many reads during multi-step run). Leveled compaction (RocksDB LEveled, Cassandra LeveledCompactionStrategy) gives better read latency at higher write amplification. Tiered (STCS, RocksDB universal) suits append-only telemetry with rare reads. Hybrid: leveled for hot agent session column family, tiered for audit logs."
  - q: "What signals indicate compaction schedule is mis-tuned?"
    a: "Rising p95 read latency while SSTable count grows, `pending_compaction_bytes` pegged high in RocksDB, Cassandra `compaction_pending_tasks` backlog, write stalls logged as 'stalling writes', and disk usage climbing faster than ingest rate. Agent symptoms: context load timeouts, checkpoint retry storms."
  - q: "Can you run major compaction during peak agent traffic?"
    a: "Avoid it. Major compactions rewrite large SSTables and steal IOPS. Schedule heavy compactions in tenant-local off-peak windows, throttle `max_background_jobs`, and use incremental / minor compaction between peaks. For 24/7 agents, isolate hot state to dedicated nodes with compaction rate limits tuned per node class."
---

Long-running agents checkpoint state, stream tool outputs, and replay conversation history from embedded or distributed LSM trees. Those stores feel fast on day one because writes land in memory and flush asynchronously. By week three, untuned **compaction schedules** turn context retrieval into multi-second reads and trigger write stalls during burst tool activity.

Compaction is the garbage collection of log-structured merge trees: it merges SSTables, drops tombstones, and reclaims disk. The schedule — when, how much, and which strategy — is the primary knob for balancing write amplification, read amplification, and space amplification. Agent platforms need different schedules for session state (read-heavy, latency-sensitive) than for append-only event logs.

## LSM basics agents inherit

Whether you use RocksDB embedded in LangGraph checkpoints, Cassandra for multi-tenant session tables, or Scylla for high-QPS memory shards, the pattern repeats:

```
write → memtable → flush → L0 SSTables
                              ↓
                    compaction (scheduled)
                              ↓
                         L1 … Ln SSTables
read → bloom filters + block cache → SSTable blocks
```

**Write amplification (WA)**: bytes written to disk per byte ingested. High WA wears SSDs and steals IOPS.

**Read amplification (RA)**: SSTables consulted per read. High RA kills agent context load latency.

**Space amplification (SA)**: disk usage / live data size. High SA inflates cloud storage.

Compaction tuning picks a point on the WA/RA/SA triangle for each column family or table.

## RocksDB: agent checkpoint column family

Embedded RocksDB (common in agent runtime persistence) exposes the richest knobs:

```ini
# agent-state-column-family options
compaction_style=level
level_compaction_dynamic_level_bytes=true
max_bytes_for_level_base=536870912        # 512 MB L1
max_bytes_for_level_multiplier=10
target_file_size_base=67108864            # 64 MB SSTs
max_background_jobs=6
max_subcompactions=4

# throttle write bursts from parallel tool calls
soft_pending_compaction_bytes_limit=68719476736   # 64 GB
hard_pending_compaction_bytes_limit=128849018880  # 120 GB

# reduce read amp for session replay
block_cache=2GB
bloom_filter_bits_per_key=10
```

Schedule tuning via **periodic compaction** for tombstone-heavy agent state (deleted turns, expired checkpoints):

```cpp
// Conceptual — set in ColumnFamilyOptions
options.periodic_compaction_seconds = 86400;  // daily reshape
options.ttl = 604800;  // 7-day agent session retention
```

When TTL expires keys, compaction must run before disk frees — stale schedules leave ghost SSTables consuming space.

Monitor these RocksDB properties:

```python
import rocksdb

def compaction_health(db: rocksdb.DB) -> dict:
    props = db.get_property
    return {
        "num_running_compactions": int(props("rocksdb.num-running-compactions")),
        "pending_compaction_bytes": int(props("rocksdb.estimate-pending-compaction-bytes")),
        "num_files_at_level0": int(props("rocksdb.num-files-at-level0")),
        "stall_micros": int(props("rocksdb.stall-micros")),
        "actual_delayed_write_rate": int(props("rocksdb.actual-delayed-write-rate")),
    }
```

Alert when `num_files_at_level0 > 20` sustained or `stall_micros` increments during agent peak hours.

## Cassandra / Scylla: table-level strategies

Distributed agent session stores often use Cassandra-compatible APIs. Pick compaction strategy per table:

```sql
-- Hot agent session state: leveled for read predictability
CREATE TABLE agent_checkpoints (
  tenant_id UUID,
  session_id UUID,
  seq INT,
  state_blob BLOB,
  updated_at TIMESTAMP,
  PRIMARY KEY ((tenant_id, session_id), seq)
) WITH compaction = {
  'class': 'org.apache.cassandra.db.compaction.LeveledCompactionStrategy',
  'sstable_size_in_mb': '160',
  'fanout_size': '10'
}
 AND gc_grace_seconds = 864000
 AND default_time_to_live = 604800;

-- Append-only tool telemetry: time window
CREATE TABLE agent_tool_events (
  tenant_id UUID,
  day DATE,
  event_id TIMEUUID,
  payload BLOB,
  PRIMARY KEY ((tenant_id, day), event_id)
) WITH compaction = {
  'class': 'org.apache.cassandra.db.compaction.TimeWindowCompactionStrategy',
  'compaction_window_unit': 'HOURS',
  'compaction_window_size': '1'
}
 AND default_time_to_live = 2592000;
```

**LeveledCompactionStrategy (LCS)**: one SSTable per data size bucket per level — best read performance, highest WA during rewrites.

**SizeTieredCompactionStrategy (STCS)**: merge similar-sized SSTables — low WA, unpredictable read latency as SSTable count grows.

**TimeWindowCompactionStrategy (TWCS)**: drop whole windows after TTL — ideal for immutable agent audit streams partitioned by day/hour.

## Building a compaction schedule

A schedule is not just cron — it is **when compactions run × how much I/O they may consume × which tables**.

Template for 24/7 agent platforms:

| Window (UTC) | Workload | Compaction policy |
|--------------|----------|-------------------|
| 00:00–06:00 | Low agent traffic | Major / leveled L0→L1 flush, TWCS window drops |
| 06:00–22:00 | Peak sessions | Minor compactions only; cap `compaction_throughput_mb_per_sec` |
| 22:00–00:00 | Moderate | Incremental STCS for cold tables |

Scylla example — rate limit during peak:

```yaml
# scylla.yaml excerpt
compaction_static_shares: 100
compaction_dynamic_shares: 1000
compaction_enforce_min_threshold: true
```

RocksDB — dynamic delay writes when backlog exceeds soft limit (automatic stall). Tune soft/hard limits so agent writes degrade gracefully (slow) rather than fail checkpoints.

Automation script concept:

```python
from datetime import datetime, timezone

PEAK_HOURS = range(6, 22)
COMPACTION_THROUGHPUT_PEAK = 32   # MB/s
COMPACTION_THROUGHPUT_OFFPEAK = 256

def desired_throughput_mb_s() -> int:
    hour = datetime.now(timezone.utc).hour
    return COMPACTION_THROUGHPUT_PEAK if hour in PEAK_HOURS else COMPACTION_THROUGHPUT_OFFPEAK

def apply_rocksdb_rate_limit(db, mb_s: int):
    # Set via options API or external tuning agent
    db.set_options({"compaction_options_universal": {"max_read_amp": "-1"}})
    db.set_options({"rate_limiter_bytes_per_sec": mb_s * 1024 * 1024})
```

Run every 15 minutes via sidecar or systemd timer — not once at deploy.

## Agent-specific workload patterns

Agent stores differ from generic OLTP:

1. **Burst writes**: parallel tool calls append many small records — L0 fills fast. Increase `max_background_flushes` and lower `write_buffer_size` to spread flushes.
2. **Sequential reads**: replaying conversation order scans a partition key — leveled compaction keeps RA low for range scans.
3. **Tombstone waves**: summarization jobs delete old turns — schedule `tombstone_compaction_interval` (Cassandra) or `periodic_compaction_seconds` (RocksDB) before `gc_grace_seconds` expires.
4. **Large blobs**: checkpoint payloads > 1 MB inflate SSTables. Store blobs in object storage; keep LSM values as pointers.

```typescript
// Checkpoint write pattern — small LSM value
interface CheckpointRef {
  sessionId: string;
  seq: number;
  blobUri: string;   // s3://agent-state/...
  checksum: string;
  sizeBytes: number;
}

async function persistCheckpoint(state: AgentState): Promise<void> {
  const blob = await s3.putObject(compress(state));
  await cf.put({
    sessionId: state.sessionId,
    seq: state.seq,
    blobUri: blob.uri,
    checksum: blob.checksum,
    sizeBytes: blob.size,
  });
}
```

Small LSM values compactor faster and reduce read amplification on session metadata queries.

## Dashboards and alerts

Minimum compaction observability for agent on-call:

```yaml
# Prometheus alert examples
- alert: RocksDBCompactionBacklog
  expr: rocksdb_pending_compaction_bytes > 50e9
  for: 30m
  labels: { severity: warning }
  annotations:
    summary: "Agent state CF compaction backlog high"

- alert: CassandraPendingCompactions
  expr: cassandra_compaction_pending_tasks > 100
  for: 15m

- alert: AgentContextReadLatency
  expr: histogram_quantile(0.95, agent_context_load_seconds) > 2
  for: 5m
```

Correlate read latency alerts with compaction metrics before scaling read replicas — replicas replicate uncompacted data too.

Grafana panel stack:

- SSTable count per level (RocksDB) or per table (Cassandra)
- Compaction bytes in/out per hour
- Write stall duration
- Agent checkpoint success rate overlaid

## Failure modes and mitigations

**Write stall during tool storm**: hard pending compaction bytes exceeded. Mitigation: raise off-peak compaction throughput, add nodes, reduce TTL retention, or split hot column family.

**Read timeout after deploy**: new deployment changed compaction style without major compaction — RA temporarily worse. Run manual `nodetool compact` / RocksDB `CompactRange` off-peak after strategy change.

**Disk full despite TTL**: tombstones not compacted before grace period; `gc_grace_seconds` too long for delete-heavy agent summarization. Shorten grace or force incremental compaction on affected tables.

**Uneven Scylla shards**: partition key skew (one mega-tenant). Compaction piles on hot shards — use tenant sub-partitioning in primary key.

## Testing compaction tuning

Before production schedule changes:

1. **Replay production write load** into staging cluster with identical schema.
2. Measure p95 read after 24h ingest without tuning (baseline).
3. Apply schedule change; run off-peak major compaction once.
4. Compare WA (bytes written / bytes ingested) and p95 context load over 72h.

```bash
# Cassandra stress profile for agent-like writes
cassandra-stress write n=5000000 \
  -col 'size(fixed=512)' \
  -rate threads=50 \
  -node STAGING_IP
```

Validate checkpoint retry rate stays flat during synthetic peak.

## The takeaway

Agent state stores live or die on background compaction. Match strategy to access pattern: leveled for hot session reads, time-window for immutable logs, rate-limit during peak agent hours, and keep large checkpoint blobs out of SSTables. Instrument pending compaction bytes alongside agent context latency — when both spike together, tuning the schedule beats adding read replicas.

## Resources

- [RocksDB compaction wiki](https://github.com/facebook/rocksdb/wiki/Compaction)
- [Apache Cassandra compaction strategies](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/compaction/)
- [ScyllaDB compaction documentation](https://opensource.docs.scylladb.com/stable/architecture/compaction.html)
- [LSM in a Week (Mark Callaghan)](http://smalldatum.blogspot.com/search/label/compaction)
- [Datadog — Monitoring RocksDB compaction](https://www.datadoghq.com/blog/engineering/rocksdb-metrics/)
