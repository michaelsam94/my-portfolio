---
title: "Store-and-Forward at the Edge"
slug: "iot-edge-buffering-store-forward"
description: "Buffer IoT telemetry at the edge when connectivity drops: local storage strategies, store-and-forward queues, backpressure, and sync on reconnect."
datePublished: "2025-07-28"
dateModified: "2025-07-28"
tags: ["IoT", "Embedded", "Architecture", "Performance"]
keywords: "store and forward IoT, edge buffering, offline telemetry, IoT edge storage, SQLite edge buffer, MQTT offline queue"
faq:
  - q: "When do IoT devices need store-and-forward buffering?"
    a: "When connectivity is intermittent — cellular dead zones, Wi-Fi gaps, satellite latency, or industrial sites with scheduled network maintenance. Without buffering, telemetry generated during outages is lost. Store-and-forward writes data to local storage and uploads it when the connection returns."
  - q: "What storage should edge devices use for buffering?"
    a: "SQLite for structured telemetry with query support (replay by timestamp, deduplication). Circular buffers in flash for fixed-size, high-frequency sensor data. File-based JSON lines for simplicity on Linux gateways. Choose based on data volume, query needs, and available storage."
  - q: "How do I prevent buffer overflow during extended outages?"
    a: "Implement tiered retention: keep full-resolution data for N hours, then downsample (averages over 5-minute windows) for the next N days, then drop. Set a hard cap on buffer size. Alert the cloud when buffer utilization exceeds 80% so operators know a device is struggling to sync."
---

A vibration sensor on a remote pump generates 100 readings per second. The cellular link drops for six hours during a storm. That's 2.16 million data points — 200 MB if you're sending raw floats as JSON. Without store-and-forward, every one of those points is gone, and your anomaly detection model has a blind spot exactly when the pump was most likely to fail. Edge buffering isn't optional for devices that can't guarantee connectivity. It's the difference between continuous monitoring and expensive guesswork.

## Architecture

```
Sensors → Edge processor → Local buffer → Connectivity check → Cloud upload
                              ↑                                    │
                              └──── retry on failure ──────────────┘
```

The edge processor writes every reading to local storage before attempting cloud upload. Upload is best-effort; storage is guaranteed.

## SQLite buffer implementation

```python
import sqlite3
import json
import time

class TelemetryBuffer:
    def __init__(self, db_path: str, max_rows: int = 1_000_000):
        self.db = sqlite3.connect(db_path)
        self.max_rows = max_rows
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                topic TEXT NOT NULL,
                payload TEXT NOT NULL,
                uploaded INTEGER DEFAULT 0
            )
        """)
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_upload ON telemetry(uploaded, timestamp)")

    def store(self, topic: str, payload: dict):
        self.db.execute(
            "INSERT INTO telemetry (timestamp, topic, payload) VALUES (?, ?, ?)",
            (time.time(), topic, json.dumps(payload)),
        )
        self._enforce_limit()
        self.db.commit()

    def pending_batch(self, limit: int = 100) -> list:
        rows = self.db.execute(
            "SELECT id, timestamp, topic, payload FROM telemetry WHERE uploaded = 0 ORDER BY timestamp LIMIT ?",
            (limit,),
        ).fetchall()
        return [{"id": r[0], "timestamp": r[1], "topic": r[2], "payload": json.loads(r[3])} for r in rows]

    def mark_uploaded(self, ids: list):
        self.db.executemany("UPDATE telemetry SET uploaded = 1 WHERE id = ?", [(i,) for i in ids])
        self.db.commit()

    def _enforce_limit(self):
        count = self.db.execute("SELECT COUNT(*) FROM telemetry WHERE uploaded = 0").fetchone()[0]
        if count > self.max_rows:
            overflow = count - self.max_rows
            self.db.execute(
                "DELETE FROM telemetry WHERE id IN (SELECT id FROM telemetry WHERE uploaded = 0 ORDER BY timestamp LIMIT ?)",
                (overflow,),
            )
```

## Upload loop with backpressure

```python
async def sync_loop(buffer: TelemetryBuffer, mqtt_client):
    while True:
        if not mqtt_client.is_connected():
            await asyncio.sleep(5)
            continue

        batch = buffer.pending_batch(limit=50)
        if not batch:
            await asyncio.sleep(1)
            continue

        uploaded_ids = []
        for record in batch:
            try:
                mqtt_client.publish(record["topic"], record["payload"], qos=1)
                uploaded_ids.append(record["id"])
            except Exception:
                break  # stop batch on first failure, retry later

        if uploaded_ids:
            buffer.mark_uploaded(uploaded_ids)

        # Backpressure: slow down if buffer is growing
        pending = buffer.pending_count()
        if pending > 100_000:
            await asyncio.sleep(0)  # full speed
        elif pending > 10_000:
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(1)
```

Upload oldest-first (FIFO). Stop the batch on first failure to avoid skipping records. Accelerate when buffer is full.

## Tiered retention

For extended outages, downsample rather than drop:

```python
def downsample_old_records(buffer, age_hours=24, interval_seconds=300):
    cutoff = time.time() - (age_hours * 3600)
    rows = buffer.db.execute(
        "SELECT * FROM telemetry WHERE uploaded = 0 AND timestamp < ? ORDER BY timestamp",
        (cutoff,),
    ).fetchall()

    buckets = {}
    for row in rows:
        bucket_key = int(row["timestamp"] // interval_seconds)
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        buckets[bucket_key].append(row)

    for bucket_rows in buckets.values():
        avg_payload = compute_average(bucket_rows)
        keep_id = bucket_rows[0]["id"]
        buffer.update_payload(keep_id, avg_payload)
        buffer.delete([r["id"] for r in bucket_rows[1:]])
```

Full resolution for 24 hours, 5-minute averages for the next 7 days, then drop. Configurable per device type.

## Embedded constraints

On MCUs with limited flash (no SQLite):

```c
typedef struct {
    uint32_t timestamp;
    float value;
    uint16_t sensor_id;
} __attribute__((packed)) reading_t;

// Circular buffer in external flash
reading_t buffer[MAX_READINGS];
uint32_t write_head = 0;
uint32_t read_head = 0;
uint32_t count = 0;

void store_reading(float value, uint16_t sensor_id) {
    buffer[write_head] = (reading_t){ time(NULL), value, sensor_id };
    write_head = (write_head + 1) % MAX_READINGS;
    if (count < MAX_READINGS) count++;
    else read_head = (read_head + 1) % MAX_READINGS;  // overwrite oldest
}
```

Fixed-size circular buffer. No malloc. Overwrites oldest on overflow. Sync reads from `read_head` forward.

## Cloud-side considerations

When replaying buffered data:

- **Timestamps** — use original sensor timestamp, not upload time. Tag with `ingestion_type: "buffered_replay"`.
- **Deduplication** — cloud should dedupe by (device_id, timestamp, sensor_id) in case of partial upload retries.
- **Out-of-order** — time-series databases handle this natively (InfluxDB, TimescaleDB). Stream processors may need watermarking.
- **Alerting** — alert when a device's buffer age exceeds threshold (data is stale even if it eventually arrives).

## Common production mistakes

Teams get edge buffering store forward wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

IoT deployments of edge buffering store forward fail in the field when firmware assumes stable Wi-Fi, OTA rollback is untested, and device certificates expire without automated renewal.

## Debugging and triage workflow

When edge buffering store forward misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [SQLite on Embedded Linux](https://www.sqlite.org/embedded.html) — SQLite configuration for resource-constrained devices
- [Eclipse Mosquitto persistence](https://mosquitto.org/man/mosquitto-conf-5.html) — MQTT broker-side message persistence
- [AWS IoT Core offline operation](https://docs.aws.amazon.com/iot/latest/developerguide/mqtt.html#mqtt-protocol) — QoS 1 persistence and session management
- [InfluxDB out-of-order writes](https://docs.influxdata.com/influxdb/v2/write-data/best-practices/optimize-writes/) — handling delayed telemetry ingestion
