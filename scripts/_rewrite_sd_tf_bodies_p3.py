# Part 3: news feed, metrics monitoring

POSTS["system-design-news-feed"] = {
    "meta": {
        "title": "System Design: News Feed",
        "description": "Design a social news feed system with fan-out on write vs read, ranking algorithms, and pagination for millions of users posting and consuming content.",
        "datePublished": "2025-10-29",
        "tags": ["System Design", "Social", "Architecture", "Backend"],
        "keywords": "news feed system design, fan-out on write, fan-out on read, social feed architecture, timeline generation, feed ranking algorithm",
        "faq": [
            {
                "q": "Should a news feed use fan-out on write or fan-out on read?",
                "a": "Fan-out on write (push) pre-computes each user's feed when a post is created — fast reads, expensive writes for users with millions of followers. Fan-out on read (pull) assembles the feed at request time — cheap writes, slower reads. Hybrid is standard: push for normal users, pull for celebrities with huge follower counts. Twitter uses push for most users and pull for accounts above a follower threshold.",
            },
            {
                "q": "How do you rank feed items beyond chronological order?",
                "a": "Production feeds use multi-signal ranking: recency, engagement velocity (likes/comments in first hour), relationship strength (interaction frequency with poster), content type preferences, and diversity (don't show five posts from the same person). Build a candidate generation stage (fetch recent posts from followed users), then a lightweight ranking model (logistic regression or small neural net) to score and sort candidates.",
            },
            {
                "q": "How do you paginate an infinite feed efficiently?",
                "a": "Use cursor-based pagination with a composite cursor (timestamp + post_id) instead of offset pagination. Offset breaks when new items are inserted during scrolling. Store the cursor client-side and pass it with each request: GET /feed?cursor=1700000000:post_abc123&limit=20. The server returns the next 20 items before that cursor plus a next_cursor for the following page.",
            },
        ],
    },
    "body": r'''
Facebook's feed serves billions of users, each scrolling a unique ordered list assembled from hundreds of followed accounts. The naive query — fetch all posts from everyone you follow, sort by time, return twenty — degrades into multi-second latency for active users. Production feeds are a pipeline: graph traversal, fan-out strategy, candidate generation, ranking, caching, and cursor pagination designed for read-heavy, write-bursty social workloads.

## Fan-out: the central trade-off

**Fan-out on write (push):** when Alice posts, write `post_id` into every follower's precomputed feed cache.

- Read: O(1) — fetch cached feed slice.
- Write: O(followers) — catastrophic for celebrities.

**Fan-out on read (pull):** when Bob opens the app, query recent posts from all accounts Bob follows, merge, rank, return.

- Read: O(following) — slow for users following thousands.
- Write: O(1) — just insert the post.

**Hybrid (production standard):**

```python
FANOUT_THRESHOLD = 10_000

async def publish_post(author_id: str, post: Post) -> None:
    await post_store.save(post)
    followers = await graph.follower_count(author_id)

    if followers < FANOUT_THRESHOLD:
        await fanout_queue.publish(FanoutJob(author_id, post.id))
    else:
        await celebrity_index.add(author_id, post.id)
```

Normal users get push fan-out via async workers. Celebrities stay pull-only — their posts merge at read time.

Fan-out workers shard by follower_id ranges to parallelize. Use bounded concurrency; a micro-influencer with 8,000 followers is 8,000 Redis ZADD operations — batch pipeline them.

## Feed storage

Precomputed feeds in Redis sorted sets:

```
Key: feed:{user_id}
Score: publish_timestamp_ms (or rank_score after ML)
Member: post_id
```

Trim feeds to last N items (e.g., 1000) — nobody scrolls deeper; archival in cold storage if needed.

```python
async def get_feed(user_id: str, cursor: str | None, limit: int = 20):
    max_score = parse_cursor(cursor) if cursor else "+inf"
    cached_ids = await redis.zrevrangebyscore(
        f"feed:{user_id}", max_score, "-inf", start=0, num=limit
    )

    celebrity_ids = await pull_celebrity_posts(user_id, since=cursor)
    candidates = await hydrate_posts(cached_ids + celebrity_ids)
    ranked = rank_feed(user_id, candidates)
    return ranked[:limit], make_cursor(ranked[-1])
```

## Social graph service

Follow relationships stored as adjacency lists or dedicated graph DB for recommendation, but fan-out needs fast follower enumeration:

```
followers:{user_id} → SET of follower user_ids  (for push)
following:{user_id} → SET of followed user_ids  (for pull)
```

Write-through cache; source of truth in sharded Postgres or TiDB. Graph changes (unfollow) do not retroactively delete historical feed entries — acceptable inconsistency; optional cleanup job.

## Ranking pipeline

Chronological order is baseline, not product goal. Multi-stage ranking:

**Stage 1 — candidate generation (cheap):** gather ~500 recent posts from push cache + celebrity pull + ads slot reservations.

**Stage 2 — scoring:** logistic regression or small DNN on features:

| Feature | Signal |
| --- | --- |
| Recency | hours since post |
| Engagement velocity | likes/comments in first 60 min |
| Relationship strength | DM frequency, profile visits |
| Content type affinity | user watches video > photos |
| Negative feedback | hide post, report author |

**Stage 3 — diversity re-ranking:** cap consecutive posts per author, inject suggested content, enforce ad spacing.

Train on impression logs (`shown, clicked, liked, dwelled_ms`). Shadow mode new models before promotion.

## Pagination: cursors, not offsets

```
GET /feed?cursor=1721200000000:post_xyz&limit=20
```

Composite cursor `(timestamp, post_id)` handles duplicate timestamps. Offset pagination breaks when new posts arrive during scroll — users see duplicates or skips.

Return `next_cursor` only if more results exist; client stores locally for session resume.

## Media and post hydration

Feed returns post IDs first; hydration batch-fetches content, author profile, like counts. CDN URLs for images/video thumbnails. Denormalize hot fields (author_name, avatar_url) into post records to avoid N+1 profile fetches.

## Write path latency

Post creation must feel instant — return `201` after durable write to post store; fan-out async. Client optimistically inserts into local UI.

## Consistency and ordering guarantees

Eventual consistency: follower may see post seconds after author published — acceptable. Per-user total order is defined by ranker, not strict global clock.

Deleting posts: remove from author's outbox, fan-out deletion job scrubs from follower feeds (tombstone or ZREM).

## Scaling milestones

| DAU | Fan-out strategy | Feed store |
| --- | --- | --- |
| <1M | Push all | Redis per user |
| 10M+ | Hybrid threshold | Redis + backup on SSD |
| 100M+ | Pull-heavy celebrities | Sharded Redis, custom feed service |

Hot keys for celebrities' pull queries — cache their recent posts globally with short TTL.

## Ads and injected content

Reserve slots (position 3, 7) in ranker output. Ads compete in separate auction; never interleave before safety/moderation checks on organic content.

## Moderation and safety

Pre-publish scan for policy violations on high-reach accounts. Post-publish async classification removes content from feeds via broadcast invalidation message.

## Synthesis

Explain hybrid fan-out, Redis sorted set feeds, celebrity pull merge, multi-stage ranking, cursor pagination. Senior insight: **the feed is a materialized view of the social graph** — choose push vs pull based on who pays the write amplification cost.
''',
}

POSTS["system-design-metrics-monitoring"] = {
    "meta": {
        "title": "System Design: Metrics and Monitoring",
        "description": "Design a metrics and monitoring platform collecting time-series data from thousands of services, with alerting, dashboards, and long-term storage at scale.",
        "datePublished": "2025-10-25",
        "tags": ["System Design", "Observability", "Monitoring", "DevOps"],
        "keywords": "metrics monitoring system design, time series database, Prometheus architecture, alerting pipeline, observability platform, Datadog system design",
        "faq": [
            {
                "q": "What is the difference between metrics, logs, and traces?",
                "a": "Metrics are numeric measurements over time — request rate, error rate, latency histograms. Logs are discrete event records with context — error messages, audit trails. Traces follow a single request across services — span timings, dependency maps. Metrics answer 'what is happening?' at aggregate level. Logs answer 'what happened for this specific event?' Traces answer 'why is this request slow across services?' A complete observability stack uses all three.",
            },
            {
                "q": "How do you handle metrics cardinality explosion?",
                "a": "Cardinality is the number of unique time series — metric name plus label combinations. High-cardinality labels (user_id, request_id) on high-frequency metrics create millions of series and crash storage. Limit labels to low-cardinality dimensions (service, endpoint, status_code, region). Use logs or traces for per-request detail. Set cardinality limits in your metrics pipeline and drop or aggregate series that exceed thresholds.",
            },
            {
                "q": "Push vs pull for metrics collection — which is better?",
                "a": "Pull (Prometheus scraping targets) is simpler for Kubernetes — the scraper discovers targets via service discovery and pulls metrics on a schedule. Push (StatsD, OpenTelemetry collector receiving metrics) is necessary for short-lived jobs, serverless functions, and services behind firewalls. Most production systems use both: pull for long-running services, push via a collector gateway for everything else.",
            },
        ],
    },
    "body": r'''
At 3:02 AM the checkout API's p99 latency jumped from 200ms to four seconds. Logs could answer why — after crafting a query across terabytes of JSON and waiting for the search cluster. Traces would show the slow path — if sampling caught those requests. Metrics answered in one Grafana refresh: `http_request_duration_p99{service="checkout",endpoint="/pay"}` spiked across all tenants simultaneously. That is the point of a metrics platform: aggregate failure visibility at human reaction speed.

## Three pillars, one nervous system

**Metrics:** numeric time series — counters, gauges, histograms. Cheap at aggregate scale.

**Logs:** discrete events with rich context. Expensive at volume; indispensable for forensics.

**Traces:** request-scoped spans across services. Sampling-managed cost.

Metrics platforms ingest millions of samples per second, store them with compression, evaluate alert rules continuously, and serve sub-second queries for dashboards.

```
Exporters / SDKs → Collection agents → Ingestion pipeline → TSDB
                                                    ↓
                                          Alert evaluator → PagerDuty
                                                    ↓
                                          Query API → Grafana
```

## Metric types and naming discipline

| Type | Example | Query pattern |
| --- | --- | --- |
| Counter | `http_requests_total` | `rate()` over 5m |
| Gauge | `queue_depth` | direct value |
| Histogram | `http_request_duration_seconds` | `histogram_quantile(0.99, ...)` |
| Summary | pre-computed quantiles | limited aggregatability |

Naming: `namespace_subsystem_unit_suffix` — `http_request_duration_seconds_bucket`.

Labels add dimensions: `{service="checkout", method="POST", status="500", region="eu-west"}`. **Cardinality is the enemy.** Never label high-cardinality values (`user_id`, `order_id`) on request counters — a million users creates a million series and OOMs your TSDB.

Use exemplars (trace_id on histogram samples) to link aggregates to traces sparingly.

## Pull vs push collection

**Pull (Prometheus model):** scraper discovers Kubernetes pods via service discovery, pulls `/metrics` every 15s. Simple, uniform, no agent on app required beyond exporter.

**Push:** StatsD, OpenTelemetry OTLP to collector gateway. Required for Lambda, batch jobs, IoT devices behind NAT.

Hybrid architecture is normal: Prometheus for K8s services, OTel collector receiving push from serverless, unified remote_write to long-term store.

## Ingestion at scale

Millions of samples per second need batching, validation, and cardinality enforcement:

```python
async def ingest(batch: list[Sample]) -> None:
    valid = [s for s in batch if allowed_labels(s) and under_cardinality_budget(s)]
    await hot_storage.write(compress(valid))
    await alert_engine.evaluate(valid)
    if should_roll_up():
        await warm_storage.write(downsample(valid, resolution="5m"))
```

Reject or aggregate samples that exceed per-metric series limits. Log dropped labels for developer feedback.

## Storage tiers

**Hot (0–15 days):** full resolution (15s scrape), SSD or memory. Powers real-time dashboards and alerts. Prometheus local TSDB, VictoriaMetrics, M3.

**Warm (15 days – 1 year):** downsampled to 1m or 5m resolution. Trend analysis, capacity planning.

**Cold (1+ years):** hourly aggregates in object storage (S3 + Parquet). Compliance, YoY comparisons. Query via Thanos, Cortex, or data warehouse.

Remote write protocols (Prometheus remote_write, OTLP) fan out to multiple backends.

## Alerting design

Alert rules query TSDB (PromQL, MetricsQL):

```yaml
- alert: CheckoutHighLatency
  expr: histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{service="checkout"}[5m])) > 2
  for: 5m
  labels: { severity: page }
  annotations:
    summary: "Checkout p99 > 2s for 5 minutes"
```

**`for: 5m`** prevents paging on blips. Route by severity: page on-call for `severity=page`, Slack for `severity=warning`.

Alert fatigue kills on-call — every alert must be actionable. Prefer SLO-based burn rate alerts over static thresholds where possible.

## SLOs and error budgets

Define SLIs: availability = successful requests / total; latency = fraction under 300ms.

SLO target 99.9% monthly → error budget 43 minutes downtime. Burn rate alerts fire when budget consumption accelerates — multi-window, multi-burn-rate approach from Google SRE workbook.

## Dashboards as code

Grafana dashboards JSON in Git; review changes in PR. Standard row per service: RED metrics (Rate, Errors, Duration). USE for infrastructure (Utilization, Saturation, Errors).

## Multi-tenancy and cost control

SaaS observability vendors charge per host, per GB ingested, per custom metric. Tag everything with `team`, `service`, `env` for chargeback. Sampling and aggregation at edge for high-volume debug metrics.

## High availability of monitoring

Monitoring the monitoring stack: meta-alerts when Prometheus scrape failures exceed threshold, when remote_write queue backs up, when alertmanager notification delivery fails. Run dual replicas across AZs.

## Security

Metrics can leak business data (revenue counters). RBAC on Grafana; don't expose admin Prometheus publicly. Redact labels with PII.

## Synthesis

Cover metric types, cardinality control, pull/push hybrid, storage tiers, alert `for` durations, SLO burn rates. The line that sticks: **metrics are the fast layer of observability** — if you cannot see aggregate pain in sixty seconds, you built a logging company with extra steps.
''',
}
