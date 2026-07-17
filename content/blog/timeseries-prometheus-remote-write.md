---
title: "Long-Term Storage with Remote Write"
slug: "timeseries-prometheus-remote-write"
description: "Configure Prometheus remote write for durable long-term metrics storage: receiver options, relabeling, backpressure, downsampling, and query federation patterns."
datePublished: "2026-02-05"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Prometheus remote write, long-term storage, Thanos, Mimir, Cortex, VictoriaMetrics, metrics retention"
faq:
  - q: "Why does Prometheus need remote write for long-term storage?"
    a: "Prometheus stores metrics in a local time-series database optimized for recent, high-resolution data. Its default retention is 15 days, and extending local retention increases memory and disk pressure on the scraper itself. Remote write ships samples to an external store designed for durability, compression, and long retention — freeing Prometheus to focus on scraping and alerting while history lives elsewhere."
  - q: "What are the main remote write receiver options?"
    a: "The most common receivers are Thanos Receive, Grafana Mimir, Cortex, and VictoriaMetrics. Thanos adds object-storage-backed blocks and a unified query layer. Mimir is Grafana's horizontally scalable, multi-tenant metrics backend. Cortex is the CNCF project Mimir forked from. VictoriaMetrics is a single-binary option with excellent compression. All accept Prometheus remote write protocol and integrate with Grafana for querying."
  - q: "How do I handle remote write backpressure and data loss?"
    a: "Prometheus buffers samples in a WAL-backed queue when the remote endpoint is slow or unavailable. Configure queue capacity and retry behavior in the remote_write block. Monitor the prometheus_remote_storage_samples_failed_total and prometheus_remote_storage_queue_highest_sent_timestamp_seconds metrics. If the queue fills, samples drop — so size the receiver for peak ingest and run it with redundancy. Never treat remote write as fire-and-forget without alerting on failures."
---

Prometheus crashed twice in one quarter at a company I consulted for, and both times the post-mortem had the same line: "we lost three months of metrics history." Local TSDB retention was set to 90 days on a single instance with no remote write configured. When the disk filled during a cardinality spike, Prometheus refused to start and the WAL was corrupted. Alerting recovered in an hour. The metrics history did not. Remote write isn't an optional nice-to-have for any team that treats historical metrics as operational data.

The architecture separates concerns: Prometheus scrapes, evaluates alerting rules, and serves recent queries. A remote write receiver stores everything long-term, handles compaction and downsampling, and federates queries back through Grafana or Thanos Query. Prometheus stays lean; history survives instance failures.

## How remote write works

After each scrape, Prometheus appends samples to its local TSDB and simultaneously enqueues them for remote write. The remote write client batches samples, Snappy-compresses them, and POSTs to the receiver's `/api/v1/push` endpoint (or vendor equivalent). The receiver indexes and stores them in its own backend — object storage, distributed blocks, or columnar files.

```yaml
# prometheus.yml
remote_write:
  - url: "http://mimir-distributor:8080/api/v1/push"
    queue_config:
      capacity: 10000
      max_shards: 50
      min_shards: 1
      max_samples_per_send: 2000
      batch_send_deadline: 5s
    write_relabel_configs:
      - source_labels: [__name__]
        regex: 'expensive_high_cardinality_.*'
        action: drop
```

The `write_relabel_configs` block is critical. It's your last chance to drop expensive series before they leave Prometheus and land in long-term storage, where they multiply storage cost.

## Receiver landscape

| Receiver | Deployment | Strengths |
|---|---|---|
| Thanos Receive | K8s, object storage | Unified query, global view, CNCF ecosystem |
| Grafana Mimir | K8s, microservices | Multi-tenant, Grafana-native, horizontally scalable |
| Cortex | K8s | Mature, CNCF, multi-tenant |
| VictoriaMetrics | Single binary or cluster | Extreme compression, simple ops |

For a team already on Grafana Cloud, Mimir (or Grafana Cloud Metrics) is the path of least resistance. For self-hosted Kubernetes with S3, Thanos is battle-tested. For teams that want one binary and minimal operational surface, VictoriaMetrics is hard to beat on compression ratio and ingest throughput.

## Relabeling: control what leaves Prometheus

Not every scraped metric deserves long-term storage. Apply `write_relabel_configs` to:

- **Drop high-cardinality labels** before they reach the receiver
- **Keep only recording rules** for expensive raw metrics
- **Filter by namespace or team** for multi-tenant cost allocation

```yaml
write_relabel_configs:
  # Drop per-request metrics; keep only aggregated recording rules
  - source_labels: [__name__]
    regex: 'http_request_duration_seconds_bucket'
    action: drop
  # Add a tenant label for multi-tenant receivers
  - target_label: tenant
    replacement: 'production'
```

Pair this with recording rules that pre-aggregate before remote write:

```yaml
groups:
  - name: aggregations
    interval: 30s
    rules:
      - record: service:http_requests:rate5m
        expr: sum by (service, method) (rate(http_requests_total[5m]))
```

## Querying long-term data

Raw Prometheus serves recent data. Long-term queries go through a federation layer:

- **Thanos Query** fans out to Prometheus (recent) and object storage (historical), deduplicating results.
- **Grafana Mimir** exposes a Prometheus-compatible query API across all ingested data.
- **Grafana data sources** can point to both Prometheus (last 15 days) and Mimir/Thanos (everything) with automatic routing based on time range.

Configure Grafana with two data sources and use `$__interval` or custom variables to route short-range queries to Prometheus and long-range to the remote store. Some setups use a single query frontend (Thanos Query or Mimir query-frontend) that handles routing transparently.

## Monitoring the pipeline

Alert on these metrics from day one:

```
prometheus_remote_storage_samples_failed_total
prometheus_remote_storage_samples_pending
prometheus_remote_storage_queue_highest_sent_timestamp_seconds
```

A growing `samples_pending` with a stale `highest_sent_timestamp` means the receiver is falling behind or unreachable. Failed samples mean data loss. Size the receiver for 2x your peak ingest rate and run at least two receiver replicas behind a load balancer.

## Downsampling in the long-term tier

Receivers compact and downsample over time. Thanos Compact creates 5-minute and 1-hour resolution blocks from raw 2-hour blocks. Mimir and Cortex run similar compaction. Configure retention per resolution tier:

- Raw resolution: 30 days
- 5-minute resolution: 6 months
- 1-hour resolution: 2+ years

This mirrors the tiered retention pattern from downsampling policies, applied at the storage layer rather than the database layer.

## What I'd do on a new setup

1. Set Prometheus local retention to 15 days — enough for alerting and recent debugging.
2. Configure remote write to a receiver with `write_relabel_configs` dropping known high-cardinality series.
3. Create recording rules for dashboards that need aggregated views.
4. Point Grafana at a query frontend that covers both local and remote data.
5. Alert on remote write queue depth and failed samples.

That gives you durable history, controlled cardinality, and a Prometheus instance that stays healthy under load.

## Remote write reliability

Remote write buffers samples during backend outage — monitor buffer size and drop rate. Configure `queue_config` capacity and batch size for your network. HA pairs of Prometheus sending duplicate remote write creates duplicate samples — use deduplication in receiver (Cortex, Mimir) or accept 2x write volume. Test failover by blocking remote write endpoint in staging and verifying local Prometheus retention covers gap duration.

## relabel_configs before remote write

Drop high-cardinality labels at scrape or remote-write relabel — cheaper than storing then dropping in receiver:

```yaml
write_relabel_configs:
  - source_labels: [__name__]
    regex: "debug_.*"
    action: drop
```

Test relabel rules with `promtool test rules` — wrong regex drops production metrics silently.

## HA Prometheus deduplication

Two replicas scraping same targets duplicate samples in remote storage unless receiver dedups by `replica` external label. Thanos Compactor and Mimir ingester handle this — configure `replica` label on Prometheus external labels in HA pairs.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [Prometheus remote write specification](https://prometheus.io/docs/specs/remote_write_spec/)
- [Prometheus remote write configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#remote_write)
- [Thanos Receive](https://thanos.io/tip/components/receive.md/)
- [Grafana Mimir architecture](https://grafana.com/docs/mimir/latest/get-started/about-mimir-architecture/)
- [VictoriaMetrics remote write](https://docs.victoriametrics.com/victoriametrics/vmagent/#remote-write)

## OTLP vs remote write

Metrics from OpenTelemetry Collector can remote_write to same backend — unify scrape and push paths.

## Cardinality limits in Mimir

Configure per-tenant series limits — reject before storage, complement relabel drops.

## Compaction and object storage

Thanos compactor downsamples blocks in object store — separate from Prometheus local retention.

## Alert on remote write

```yaml
- alert: RemoteWriteLag
  expr: time() - prometheus_remote_storage_queue_highest_sent_timestamp_seconds > 300
  for: 10m
```

Page before queue drops samples.

## Cost optimization

S3 lifecycle to Glacier for blocks older than 2y — query latency tradeoff acceptable for compliance archives.

Remote write completes observability stack — local Prometheus for now, durable store for history and compliance.

## Remote write shard tuning

Too many shards increases cardinality labels on receiver — start conservative and scale with HA pair capacity.
