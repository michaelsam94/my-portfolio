---
title: "Time-Series Ingestion at the Edge"
slug: "iot-time-series-ingestion"
description: "Build time-series ingestion at the IoT edge: local buffering, backpressure, batching, store-and-forward, and sync patterns that survive network outages without data loss."
datePublished: "2025-09-17"
dateModified: "2025-09-17"
tags: ["IoT", "Edge Computing", "Time Series", "Architecture"]
keywords: "IoT time series ingestion, edge time series database, store and forward IoT, TimescaleDB edge, InfluxDB edge gateway"
faq:
  - q: "Should time-series data be stored at the edge or sent directly to cloud?"
    a: "Store at the edge when connectivity is intermittent, bandwidth is costly, or local analytics need sub-second access. Buffer locally, aggregate, then sync upstream. Send directly when the link is reliable and low-latency cloud processing is the primary consumer. Most industrial deployments do both — hot storage at edge, cold archive in cloud."
  - q: "What happens when the edge buffer fills during an outage?"
    a: "Define explicit overflow policy before it happens: drop oldest (ring buffer), downsample (keep min/max/avg per window), prioritize alarm events over routine telemetry, or spill to removable storage. Never block sensor acquisition indefinitely — backpressure should degrade gracefully, not freeze the plant."
  - q: "Which time-series database works at the edge?"
    a: "InfluxDB OSS, TimescaleDB, and SQLite with time-indexed tables are common on gateways. Choose based on query patterns: Influx for high-write tag-based metrics, Timescale for SQL analytics, SQLite for minimal footprint. Match retention and compaction to available eMMC or SD capacity — unbounded retention fills disks."
---

The gateway lost cloud connectivity for eighteen hours during a fiber cut. By hour six, the ingestion daemon blocked on a full outbound queue, sensor reads started timing out, and the SCADA team lost visibility into a production line that was still running. Time-series ingestion at the edge is not "MQTT subscribe and forward." It is a pipeline with local persistence, explicit backpressure, and sync semantics that assume the network will fail at the worst moment — because it will.

## Edge ingestion architecture

```
Sensors → Acquire → Normalize → Local TSDB → Sync Agent → Cloud TSDB
                      ↓              ↓
                   Alarms      Downsampled rollups
```

Each stage has bounded memory and defined failure behavior. The acquire stage never waits on cloud ACK.

## Local buffering strategies

**Ring buffer in RAM** — fast, volatile, size-capped:

```python
from collections import deque

class TelemetryBuffer:
    def __init__(self, maxlen=10_000):
        self._buf = deque(maxlen=maxlen)

    def append(self, point):
        if len(self._buf) == self._buf.maxlen:
            metrics.increment("buffer.dropped_oldest")
        self._buf.append(point)

    def drain_batch(self, n=500):
        batch = []
        while self._buf and len(batch) < n:
            batch.append(self._buf.popleft())
        return batch
```

**Persistent WAL on disk** — survives reboot:

```sql
CREATE TABLE telemetry_wal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL NOT NULL,
    synced INTEGER DEFAULT 0
);
CREATE INDEX idx_wal_unsynced ON telemetry_wal(synced, ts);
```

Sync agent marks rows `synced=1` after cloud ACK, compacts periodically. SQLite handles tens of thousands of writes per second on modern gateways with WAL mode enabled.

## Batching and compression upstream

Do not open one HTTP request per reading. Batch by count or time window:

```python
async def sync_loop(client, wal, batch_size=1000, interval_s=30):
    while True:
        rows = wal.fetch_unsynced(limit=batch_size)
        if not rows:
            await asyncio.sleep(interval_s)
            continue
        payload = compress_protobuf(rows)
        try:
            await client.post("/ingest", content=payload, timeout=30)
            wal.mark_synced([r.id for r in rows])
        except NetworkError:
            metrics.increment("sync.retry")
            await asyncio.sleep(min(interval_s * 2, 300))
```

Exponential backoff on sync failure, but cap it — you still want recovery without manual intervention.

## Backpressure from cloud to sensor

When downstream is slow, pressure propagates backward unless you isolate stages:

| Stage | Backpressure response |
|-------|----------------------|
| Sync agent | Pause drain; WAL grows |
| WAL full | Downsample or drop routine |
| Acquire | Never block — sample at fixed rate, overwrite ring |

Use async channels with bounded capacity between goroutines/tasks. Monitor queue depth as a first-class metric.

## Timestamp and ordering guarantees

Edge ingestion must preserve **event time**, not just **ingest time**:

```json
{
  "metric": "motor.vibration_rms",
  "value": 0.042,
  "ts": "2025-02-18T14:32:01.123Z",
  "ingest_ts": "2025-02-18T14:35:00.000Z",
  "seq": 1847291
}
```

Cloud TSDB should index on `ts` for analytics and store `ingest_ts` for latency monitoring. Sequence numbers detect gaps after reconnect — request retransmit or flag incomplete windows.

## Downsampling at the edge

Reduce upstream volume while preserving signal for operations:

- **Fixed windows** — 1-second raw → 1-minute min/max/avg/count
- **Deadband** — send only when value changes beyond threshold
- **Tiered retention** — 7 days at full resolution locally, 90 days at 1-minute rollups in cloud

```sql
-- TimescaleDB continuous aggregate pattern (gateway or cloud)
CREATE MATERIALIZED VIEW telemetry_1m
WITH (timescaledb.continuous) AS
SELECT time_bucket('1 minute', ts) AS bucket,
       device_id, metric,
       avg(value) AS avg_val,
       min(value) AS min_val,
       max(value) AS max_val
FROM telemetry_raw
GROUP BY bucket, device_id, metric;
```

Run lightweight aggregates on the gateway when uplink is the bottleneck.

## Conflict resolution after partition

When edge and cloud both accepted writes during partition:

1. **Last-write-wins** — simple, loses data
2. **Source authority** — edge wins for field measurements, cloud wins for config
3. **Version vectors** — merge if causality matters

For sensor telemetry, edge measurements usually win — the cloud did not have the readings during outage. Config and commands may be cloud-authoritative with edge caching.

## Observability of the pipeline itself

Instrument the ingester, not just the sensors:

- `buffer_depth`, `sync_lag_seconds`, `wal_size_bytes`
- `points_per_second_in`, `points_per_second_out`
- `oldest_unsynced_age`

Alert when `sync_lag_seconds` exceeds SLA — that is how long your cloud dashboard is lying.

## Time-series write path

```
Device → MQTT → Kafka → TimescaleDB/InfluxDB
                    → cold storage (Parquet) after 90 days
```

Downsample aggregates: raw 1s resolution 7 days, 1min resolution 90 days, 1hour forever. Tag series with device_id, metric, firmware_version.

## Common production mistakes

Teams get time series ingestion wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of time series ingestion fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When time series ingestion misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [InfluxDB edge data collection](https://docs.influxdata.com/influxdb/v2/write-data/)
- [TimescaleDB documentation](https://docs.timescale.com/)
- [SQLite WAL mode](https://www.sqlite.org/wal.html)
- [Apache Kafka store-and-forward patterns](https://kafka.apache.org/documentation/#design)
- [EdgeX Foundry core data](https://docs.edgexfoundry.org/)
