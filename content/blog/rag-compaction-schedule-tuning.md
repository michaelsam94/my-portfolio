---
title: "RAG: Compaction Schedule Tuning"
slug: "rag-compaction-schedule-tuning"
description: "Tune Kafka log compaction schedules for RAG state topics—balance min.compaction.lag, segment.ms, and dirty ratio so document metadata changelogs compact without starving consumers or bloating disk."
datePublished: "2025-01-19"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Compaction"]
keywords: "Kafka compaction, log compaction tuning, min.compaction.lag.ms, segment.ms, RAG changelog, compacted topic, dirty ratio"
faq:
  - q: "What happens if Kafka compaction runs too aggressively on RAG state topics?"
    a: "Aggressive compaction (low min.compaction.lag.ms, low segment.ms) removes superseded records before slow consumers read them, causing missed document state updates in RAG index validators. It also increases CPU and I/O on brokers during peak ingestion when compaction competes with produce/consume throughput."
  - q: "How do I know if RAG compacted topics need compaction tuning?"
    a: "Monitor log size vs unique key count ratio (should approach 1:1 for stable state), max compaction lag time, consumer recovery time after restart, and broker disk usage growth despite stable document count. Ratio >>2:1 means compaction is falling behind; consumer recovery >30 min means lag settings are too aggressive."
  - q: "Should RAG document CDC topics use compaction or retention?"
    a: "Use retention (delete) for raw CDC event streams needing full history for audit. Use compaction for derived state topics (latest metadata per doc_id) consumed by index validators and bootstrap jobs. Most RAG pipelines need both topic types with different compaction settings."
---
The `rag.document-state` compacted topic had grown to 400 GB despite only 2 million document keys. Compaction was running but couldn't keep pace—`min.compaction.lag.ms` was set to zero, causing compaction to attempt on every segment while ingestion produced 50 MB/s of updates during bulk reindex. Brokers spent 60% CPU on compaction, consumer lag spiked, and a new index validator took four hours to bootstrap from the compacted topic. Tuning `min.compaction.lag.ms` to 300000 (5 min), `segment.ms` to 3600000 (1 hour), and `min.cleanable.dirty.ratio` to 0.25 reduced topic size to 12 GB and bootstrap time to 18 minutes.

Log compaction schedule tuning is broker configuration that RAG platform teams overlook until compacted topics bloat or consumers miss state. This post covers the parameters that control when and how aggressively Kafka compacts RAG changelog topics.

## Compaction parameters and their effects

| Parameter | Default | Effect on RAG topics |
|-----------|---------|---------------------|
| `min.compaction.lag.ms` | 0 | Min age before record eligible for compaction |
| `max.compaction.lag.ms` | unset | Max age before record force-compacted |
| `segment.ms` | 604800000 (7d) | Time before segment eligible for compaction |
| `segment.bytes` | 1073741824 (1GB) | Size before segment roll |
| `min.cleanable.dirty.ratio` | 0.5 | Dirty ratio to trigger compaction |
| `delete.retention.ms` | 86400000 (24h) | Tombstone visibility window |
| `cleanup.policy` | delete | Must be `compact` or `compact,delete` |

Each parameter interacts with RAG ingestion patterns—bulk reindex produces very different compaction load than steady-state single-document updates.

## min.compaction.lag.ms: protect slow consumers

Prevents compaction from removing superseded records until the lag period elapses:

```properties
# RAG document state topic
min.compaction.lag.ms=300000  # 5 minutes
```

Why 5 minutes for RAG:
- Index validator consumers process 2M keys in ~18 min at 2k keys/sec
- 5 min lag ensures consumers reading from offset 0 see all intermediate states if needed
- During bulk reindex, prevents compaction from deleting version N before validator reads it

Too low (0): compaction races with consumers during bootstrap.
Too high (3600000): topic bloats with superseded records for an hour.

Tune from consumer bootstrap benchmark:

```bash
# Measure bootstrap time at different lag settings
for lag in 0 60000 300000 600000; do
  kafka-configs.sh --alter --entity-type topics \
    --entity-name rag.document-state \
    --add-config min.compaction.lag.ms=$lag
  time python bootstrap_consumer.py
done
```

## segment.ms and segment.bytes: control compaction frequency

Segments are compaction units. Smaller segments = more frequent compaction:

```properties
# Hourly segments — good for moderate update rate
segment.ms=3600000
segment.bytes=536870912  # 512 MB

# For bulk reindex bursts, larger segments reduce compaction frequency
segment.ms=7200000   # 2 hours during reindex windows
segment.bytes=1073741824  # 1 GB
```

During bulk reindex (high produce rate), temporarily increase segment.ms to reduce compaction cycles competing with ingestion throughput. Revert after reindex completes.

Monitor segment count:

```bash
kafka-log-dirs.sh --describe | grep rag.document-state
# High segment count + low compaction rate = tuning needed
```

## min.cleanable.dirty.ratio: compaction trigger threshold

Fraction of log that must be "dirty" (superseded records) before compaction eligible:

```properties
min.cleanable.dirty.ratio=0.25  # compact when 25% dirty
```

Lower ratio (0.1): compaction runs more often, smaller topic, more broker CPU.
Higher ratio (0.5 default): less frequent compaction, larger topic between cycles.

For RAG state topics with frequent updates to same keys (hot documents re-indexed often):

```properties
# Hot key churn — compact more aggressively
min.cleanable.dirty.ratio=0.2
max.compaction.lag.ms=600000  # force compact after 10 min regardless
```

`max.compaction.lag.ms` guarantees compaction eventually runs even if dirty ratio threshold not met—prevents unbounded growth on low-churn topics with occasional updates.

## delete.retention.ms and tombstones

Document deletions produce tombstone records (null value). Tombstones must remain visible long enough for all consumers to process:

```properties
delete.retention.ms=86400000  # 24 hours
```

RAG deletion flow:
1. Vector index deletes chunks
2. Compacted topic produces tombstone for doc_id
3. All consumers must process tombstone within 24h
4. Compaction removes tombstone after delete.retention.ms

If consumer downtime exceeds delete.retention.ms, deleted documents reappear in consumer state—ghost documents in index validators.

Rule: `delete.retention.ms` > maximum expected consumer downtime.

## Hybrid cleanup.policy for time-bounded state

RAG ephemeral state (session retrieval cache metadata) uses compact + delete:

```properties
cleanup.policy=compact,delete
retention.ms=604800000  # 7 days
min.compaction.lag.ms=60000
```

Records compacted per key AND deleted after 7 days regardless—prevents unbounded growth of session keys that are never updated (tombstoned) after session ends.

## Monitoring compaction health

Key JMX metrics:

```
kafka.log:type=LogCleanerManager,name=max-dirty-percent
kafka.log:type=LogCleaner,name=cleaner-recopy-percent
kafka.log:type=Log,name=Size,topic=rag.document-state,partition=*
```

Derived metrics:

```promql
# Compaction efficiency: log size / unique keys (target ~avg record size)
kafka_log_size_bytes{topic="rag.document-state"}
/ kafka_topic_unique_keys{topic="rag.document-state"}

# Compaction lag
kafka_log_cleaner_max_dirty_percent{topic="rag.document-state"}
```

Alert when:
- Log size growing while unique key count stable (compaction falling behind)
- max-dirty-percent >80% sustained (compaction cannot keep pace)
- Consumer bootstrap time exceeds SLO

## Bulk reindex compaction strategy

Bulk reindex updates every document key rapidly—worst case for compaction:

**Before reindex:**
```properties
# Temporarily relax compaction during bulk update
min.compaction.lag.ms=900000       # 15 min
min.cleanable.dirty.ratio=0.5      # less frequent
segment.bytes=2147483648           # 2 GB segments
```

**After reindex completes:**
```bash
# Force compaction across all segments
kafka-log-dirs.sh --describe  # verify segment count
# Trigger manual compaction via kafka-configs or restart cleaners

# Restore normal settings
min.compaction.lag.ms=300000
min.cleanable.dirty.ratio=0.25
segment.bytes=536870912
```

**Alternative:** write bulk reindex to temporary topic, swap consumer offset to new topic after complete—avoids compaction storm on production state topic.

## Per-partition compaction considerations

Compaction runs per partition. Uneven key distribution causes uneven compaction load:

```python
# Partition by doc_id hash for even distribution
partition = hash(doc_id) % num_partitions
```

Monitor per-partition log size—hot partitions with many updates to keys in same partition compact more aggressively than cold partitions.

## Tuning workflow summary

1. **Baseline:** measure topic size, unique key count, consumer bootstrap time
2. **Set min.compaction.lag.ms** from consumer speed (bootstrap_time / 4)
3. **Set segment.ms** from produce rate (higher rate → larger segments during bursts)
4. **Set min.cleanable.dirty.ratio** from update churn (hot keys → lower ratio)
5. **Set delete.retention.ms** from max consumer downtime
6. **Load test** bulk reindex scenario
7. **Monitor** and iterate

Compaction tuning is iterative—RAG ingestion patterns change with corpus growth, model updates, and tenant onboarding. Review quarterly or after major reindex events.

## Documenting compaction settings per topic

Maintain a topic configuration registry in git documenting every compacted RAG topic, its settings, rationale, and last tuning date. Post-incident reviews of consumer bootstrap failures should check whether compaction settings changed recently. Kafka upgrades sometimes reset topic configs—verify compaction settings after broker upgrades as part of platform checklist.

## Interaction with Kafka broker disk sizing

Compaction temporarily increases disk usage—it writes new clean segments before deleting dirty ones. Size broker disk for 2× steady-state compacted topic size during bulk reindex. Monitor disk usage alert threshold at 70%—compaction stall at 100% disk causes produce failures cascading to RAG ingestion pipeline. Add broker disk before compaction tuning if disk headroom insufficient—tuning cannot fix physical capacity limits.

## Acceptance criteria for compaction schedule tuning

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.

## Resources

- Kafka log compaction documentation
- Confluent: tuning log compaction
- Kafka JMX metrics reference
- Compacted topic consumer bootstrap patterns
