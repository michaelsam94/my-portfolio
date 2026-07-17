#!/usr/bin/env python3
"""Append topic-specific depth sections to posts under 1200 words."""
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"

EXPANSIONS = {
    "oauth2-token-introspection-revocation": """

## Multi-region introspection topology

Production authorization servers rarely run as a single pod. When introspection endpoints sit behind geo-routed load balancers, resource servers must not cache "active" across regions longer than revocation propagation time. Patterns that work:

**Central revocation store** — DynamoDB Global Table, Redis Cluster with cross-region replication, or PostgreSQL with logical replication. Introspection workers in each region read the same store; 30-second positive cache is safe if replication lag is monitored and stays under 5 seconds.

**Regional AS with async revocation fan-out** — Revoke in primary region; event bus replicates `jti` to secondaries. Resource servers in EU must not call US introspection on every request if latency matters—local regional introspection endpoint with shared store backend.

```yaml
# Resource server config sketch
introspection:
  endpoints:
    - url: https://as-eu.example.com/oauth/introspect
      region: eu-west-1
    - url: https://as-us.example.com/oauth/introspect
      region: us-east-1
  cache_ttl_active_seconds: 30
  cache_ttl_inactive_seconds: 0
  fail_closed: true
```

Alert when cross-region replication lag exceeds cache TTL—otherwise revoked tokens stay usable in one geography.

## Partner and machine-to-machine introspection

B2B APIs often accept tokens minted by a partner IdP. Two patterns:

**Local JWT validation** with JWKS from partner—fast, no introspection unless token is opaque.

**Delegated introspection** — your AS introspects partner token via RFC 7662 forward (non-standard but common in federations). Document latency budget; partner introspection outage becomes your outage unless cached JWKS path exists for JWT partners.

Machine clients using client credentials typically receive JWT access tokens you validate locally. Reserve introspection for opaque tokens from legacy AS products and for step-up revocation after credential rotation.

## Compliance and audit evidence

SOC2 and ISO audits ask: "When employment terminates, how fast does access end?" Your answer must cite:

- Revocation API called from HRIS webhook within N minutes
- Introspection `active: false` for all outstanding access token `jti`s
- Maximum access token TTL documented (e.g. 15 minutes)
- Logs retained: `{actor, subject, jti, reason, timestamp}` without storing token plaintext

Quarterly drill: revoke test user, assert resource API rejects within TTL + cache window. Save Grafana screenshot for auditors.

## Load testing introspection

Before Black Friday, load test resource servers at 2× peak with introspection enabled. Watch:

- p99 introspection latency vs p99 API latency (should stay <10% of total)
- Cache hit ratio on positive introspection (target >85% at steady state)
- AS introspection endpoint 429 rate—rate limits should scale with registered resource servers, not punish during legitimate traffic spikes

If introspection dominates latency, shorten access token TTL and widen cache carefully—not disable introspection on admin paths without explicit risk acceptance.
""",

    "observability-api-latency-histograms": """

## Comparing histogram quantiles to trace percentiles

Weekly sanity check: export p99 from Prometheus histogram for `checkout` service and p99 from Tempo span metrics for the same route. Divergence >20% means buckets lie or sampling skews traces.

```promql
# Tempo span metrics (if metrics-generator enabled)
histogram_quantile(0.99, sum by (le) (rate(traces_spanmetrics_latency_bucket{service="checkout"}[1h])))
```

Document acceptable drift. During incidents, trust traces for single-request truth; trust histograms for alert firing when traces are sampled.

## Recording rules for dashboard performance

High-cardinality route labels make dashboard queries expensive. Pre-aggregate tier-1 routes:

```yaml
groups:
  - name: latency_recording
    rules:
      - record: route:http_request_duration_seconds:p99
        expr: |
          histogram_quantile(0.99,
            sum by (le, route) (
              rate(http_request_duration_seconds_bucket{route=~"/checkout.*|/login.*"}[5m])
            )
          )
```

Dashboards query recording rules; ad-hoc investigation uses raw metrics with short time range.

## Native histogram migration checklist

When moving to Prometheus native histograms:

1. Enable scrape feature flag on one Prometheus shard
2. Dual-write classic + native histogram metric names during migration (`_bucket` vs `_nhcb`)
3. Compare quantiles in Grafana overlay panel for two weeks
4. Switch alerts to native histogram queries
5. Drop classic buckets after 30-day retention expires

Classic bucket misconfiguration becomes technical debt—native histograms reduce tuning but require Prometheus 2.47+ and compatible exporters throughout the fleet.

## SLO review with product

Histogram buckets should align with product language: if PM says "checkout must feel instant," define instant as <300ms and place bucket boundaries at 100ms, 200ms, 300ms, 500ms so p95 and p99 reflect perceptual thresholds in user research—not arbitrary exponential spacing alone.

Review buckets after major architecture changes (edge caching added, sync path became async). Latency distribution shape shifts; buckets from the monolith era misrepresent serverless or BFF architectures.
""",

    "observability-continuous-profiling-parca": """

## Symbol upload and container builds

Go and Rust binaries stripped in Docker multi-stage builds lose symbols Parca needs. Options:

**Separate debug image** — CI pushes `myapp:1.2.0-debug` with symbols to internal registry; Parca queries debuginfod or symbol server mapped by build ID.

**Build ID in Kubernetes labels** — Pod label `git.sha=abc123`; Parca maps profiles to symbols from object storage path `symbols/abc123/`.

Without symbols, flame graphs show hex addresses—better than nothing, useless for developers who do not carry addr2line in muscle memory.

## Profiling and compliance workloads

Regulated environments may restrict always-on profiling as potential data leakage via stack strings. Mitigations:

- Profile only non-PII code paths (exclude payment handler packages via build tags—not practical usually)
- Restrict Parca UI to VPC-only
- Redact symbol names in UI export for vendor support tickets

Legal review often approves CPU sampling where heap dumps would not pass—document difference for security questionnaires.

## Integrating with CI performance gates

Optional: short k6 load in CI with Parca scrape of staging deploy. Compare top 10 functions vs baseline main branch—fail PR if new hot path adds >5% CPU in `applyDiscounts`. Lightweight guard against algorithmic regressions before production profiles confirm pain.

## Parca vs Pyroscope operational choice

Both use eBPF; Grafana Pyroscope merges into LGTM stack with unified Grafana Explore. Parca remains strong for teams wanting CNCF-aligned OSS without Grafana Cloud coupling. Evaluation criteria: existing object storage (S3 compatibility), team familiarity, and whether Tempo trace-to-profile linking is already on roadmap—Grafana path shortens integration time.
""",

    "observability-continuous-profiling": """

## Flame graph reading for on-call

Train on-call to read icicle charts top-down:

1. **Width** — percentage of samples in that frame
2. **Self vs total** — hover for self time vs cumulative child time
3. **Plateau** — wide flat frames are optimization targets

Runbook snippet: "If `runtime.systemstack` or `syscall` dominates, suspect IO not CPU—switch to trace and pool metrics before optimizing Go code."

## Allocation profiling for GC pressure

CPU profiles miss services spending 40% in GC because allocations are hot. Enable alloc profiling on canary when:

- `go_gc_duration_seconds` spikes correlate with latency
- JVM `jvm.gc.pause` alerts fire without CPU saturation

Parca/Pyroscope heap profiles show `make([]byte)` or JSON marshal paths—fix allocation before tuning `GOGC`.

## Profiling multi-tenant SaaS

Noisy neighbor tenants may dominate profiles without attribution. Label profiles with `tenant_tier` not `tenant_id`—sample pod metadata at scrape time. Enterprise tier latency incident → filter profiles to pods handling enterprise traffic via deployment shard labels.

## Relationship to eBPF network observability

Profiles show CPU in HTTP handler; eBPF flows show retransmit storms. Combined timeline: network packet loss spike → retry loop in handler → CPU profile shows `io.ReadAll` hot. Use both pillars before blaming application algorithm.
""",

    "observability-db-query-tracing-orm": """

## Connection pool spans

Database client instrumentation often misses **pool wait**—time blocked waiting for connection before query executes. Custom span around `pool.acquire()`:

```typescript
await tracer.startActiveSpan("db.pool.acquire", async (span) => {
  const conn = await pool.connect();
  span.end();
  return conn;
});
```

Traces showing 800ms `SELECT` with 750ms pool wait need pool sizing not query indexes.

## Read replica routing visibility

ORM middleware that routes reads to replicas should add span attribute `db.role=replica|primary`. Incidents where stale reads cause user confusion—trace shows read hit replica lagging 30 seconds behind primary.

## Migration from ORM query logs

Teams enabling trace instrumentation should **disable** ORM SQL printf logging in production same release—duplicate IO and PII risk. Keep `log_min_duration_statement` on Postgres for DBA-side slow query capture as complement, not duplicate of every ORM query in app logs.

## CI guardrails for span count

```python
# pytest + opentelemetry test exporter
def test_list_orders_span_budget(client, span_exporter):
    client.get("/orders")
    db_spans = [s for s in span_exporter.get_finished_spans() if s.attributes.get("db.system")]
    assert len(db_spans) <= 3, f"N+1 suspected: {len(db_spans)} db spans"
```

Fails PR when lazy loading regression adds loops—cheaper than production trace discovery.
""",
}

# Additional expansions for remaining slugs - part 2
EXPANSIONS.update({
    "observability-ebpf-network-observability": """

## Correlating Hubble flows with application traces

When flow shows `DROPPED` between checkout and payments, grab `trace_id` from checkout logs and verify HTTP client span never received response—confirms network drop vs application timeout misconfiguration.

Teach on-call: **Hubble first for connection refused / policy denied**; **traces first for slow OK responses**.

## Multi-cluster and mesh boundaries

Service mesh mTLS hides payload from eBPF L7 parsers on some platforms—flows show encrypted bytes only. Combine mesh telemetry (Istio access logs) with eBPF L4 for packet drops on node. Document which tool owns which failure mode in runbook matrix.

## Cost of flow log retention

Full L7 flow logs at 100k RPS overwhelm storage. Retention tiers:

- **24 hours** full L4+L7 for incident window
- **7 days** aggregated flow counts only
- **Metrics** (`hubble_flows_processed_total`) for 90 days

Tune Hubble `--enable-l7-proxy-visibility` only on namespaces under active network debugging—not entire cluster indefinitely.
""",

    "observability-error-budget-burn-alerts": """

## Error budget reviews with product

Monthly 30-minute meeting: chart `1 - error_budget_remaining` per tier-1 SLO. Product decides:

- Budget >50% left → accelerate features
- Budget <20% → reliability sprint, freeze risky launches
- Budget exhausted → postmortem before new feature work

Burn alerts are input data; policy drives behavior. Without policy, burn alerts become ignored Grafana panels.

## Multi-window tuning for low-traffic services

Startup services lack volume for 2-minute burn windows—adjust windows to 15m/6h and require minimum event count:

```promql
(slo:errors:burn_rate_6h > 6)
and
(slo:requests:total_6h > 500)
```

Prevents paging on three errors total.

## Composite SLOs

User journey spans three services—define composite SLI as product of success probabilities or end-to-end synthetic check success rate. Burn composite SLO for executive view; burn per-service SLO for engineering drill-down. Sloth supports grouping multiple SLIs into one alert policy.
""",

    "observability-exemplars-traces-metrics": """

## Mimir exemplar limits in production

Configure per-tenant exemplar limits before enabling fleet-wide:

```yaml
limits:
  max_global_exemplars_per_user: 200000
  max_exemplars_per_series: 10
```

Exceeding limits drops exemplars silently—monitor `cortex_discarded_exemplars_total`.

## OpenMetrics exemplar format

Prometheus remote write to Mimir must use OpenMetrics 1.0 text format for exemplar retention. Verify otel-collector `prometheus` exporter `enable_open_metrics: true` when metrics originate from OTel SDK histograms with exemplars attached.

## Debugging workflow automation

Grafana annotation webhook on alert includes deep link:

```
/explore?left={"queries":[{"refId":"A","expr":"..."}],"range":{"from":"now-15m"}}
```

On-call lands on heatmap with exemplars visible—remove manual dashboard hunting from runbook step 2.
""",

    "observability-grpc-status-code-metrics": """

## Interceptor ordering in Go

Register metrics interceptor **after** auth interceptor so rejected unauthenticated requests still count toward `UNAUTHENTICATED` metrics—otherwise blind spot on attack traffic volume.

```go
grpc.ChainUnaryInterceptor(
  authInterceptor,
  grpcMetrics.UnaryServerInterceptor(),
  loggingInterceptor,
)
```

## protobuf service versioning

When `inventory.v2.Inventory` ships alongside v1, labels must include `grpc_service` separately—dashboards filter v2 canary error rates without v1 noise.

## Envoy sidecar gRPC stats

If using Istio/Envoy, validate sidecar stats match application stats—Envoy may report `upstream_rq_200` while app returns gRPC `INTERNAL` mapped to HTTP 200 (gRPC over HTTP/2 framing). Trust application-level `grpc_server_handled_total` for SLOs, Envoy for network layer.
""",

    "observability-kafka-consumer-lag-slo": """

## Lag vs processing time SLO

Offset lag conflates publish rate with consume rate. Prefer **end-to-end latency** histogram: `event_processed_timestamp - event_published_timestamp`. Kafka lag becomes secondary alert when processing latency SLO already fires.

## Compact topics and lag interpretation

Compacted topics delete old offsets—lag metrics behave differently. Document which consumer groups use compacted topics; Burrow config excludes them from false ERR status.

## Autoscaling on lag

KEDA ScaledObject on `kafka lag`:

```yaml
triggers:
  - type: kafka
    metadata:
      consumerGroup: order-indexer
      lagThreshold: "1000"
      activationLagThreshold: "100"
```

Scale-down cooldown prevents flapping when lag hovers near threshold. Max replicas capped at partition count.
""",

    "observability-log-trace-correlation": """

## OpenTelemetry Logs Bridge

OTel 1.24+ logs SDK correlates automatically when logs emitted inside active span context. Prefer OTel logs exporter → Loki over ad-hoc trace_id injection when greenfield—one propagation path.

## Log volume vs trace sampling

At 10% trace sampling, 90% of logs carry trace_ids with no backend trace—acceptable for log filtering by id when sampled. Document in runbook: "trace_id not found → check sampling; use log context alone."

## Cross-vendor correlation

Datadog logs + traces: use `dd.trace_id` attribute. Hybrid cloud during migration may need dual fields temporarily—normalize in log pipeline to single `trace_id` for query UX.
""",

    "observability-metrics-cardinality": """

## Otel Collector cardinality limiter

```yaml
processors:
  cardinality/drop:
    metric_names:
      match_type: regexp
      regexp: ".*"
    label_limits:
      label_name: user_id
      max_label_values: 0  # drop label
```

Reject at ingest before TSDB crash—pair with CI lint on application metric definitions.

## Ownership model

Each metric `__name__` in top 50 series count has named owner in catalog. Weekly Slack bot posts cardinality leaderboard—shame works better than surprise 28GB RAM Prometheus.

## Downsampling vs dropping labels

Cortex/Mimir downsampling reduces long-term retention cost but does not fix cardinality explosion—still need label hygiene at source.
""",

    "observability-oncall-runbook-automation": """

## Runbook metrics in incident review

Post-incident: was `runbook_id` attached to alert? Did diagnose script run? Track `% pages with automated diagnosis completed in 5 min` as operational KPI.

## Security of remediation scripts

Remediate scripts run with production credentials—store in locked repo, require CODEOWNERS approval, audit every execution to SIEM with incident id.

## Staged automation maturity

Level 0: static URL
Level 1: diagnose webhook
Level 2: ChatOps approval remediate
Level 3: auto-remediate with rollback on error rate increase

Most teams stall at Level 1 for years— that alone cuts MTTR measurably.
""",

    "observability-service-graph-topology": """

## Service graph in deployment pipelines

Post-deploy smoke: compare service graph edge error rates for canary vs stable. Automated rollback if new version introduces edge to deprecated `legacy-tax` service—architecture regression caught before full traffic shift.

## Graph density management

Graphs with 200 nodes are unreadable. Filter to depth-2 from entry service `checkout` during incidents; full graph for quarterly architecture reviews only.

## Missing instrumentation ticket bot

Weekly job: edges in service catalog expected graph but absent in trace graph → create Jira tickets to owning teams. Closes observability gaps systematically.
""",

    "observability-structured-log-schema": """

## Schema registry integration

Publish log schemas to internal registry (similar to Avro for Kafka). CI of each service validates against latest compatible schema version—breaking changes require major bump approval.

## OpenTelemetry log attributes mapping

Map schema fields to OTel log record attributes when using Logs Bridge—`service.name` resource attribute duplicates JSON `service.name`; pick one source of truth to avoid double-indexing in backends.

## Log schema for audit events

Separate `event` namespace `security.*` with immutability requirements—append-only index, longer retention, stricter schema (who, what, when, resource, action, result). Distinct from debug application logs.
""",

    "observability-structured-logging": """

## Dynamic log level per request

Support toggling DEBUG for one user session via header `X-Debug-Session: <signed-token>` validated at edge—avoid global DEBUG in production. Signed token expires in 15 minutes; all debug logs include `debug_session_id` for audit.

## Log shipping backpressure

When Loki ingest falls behind, loggers block or drop—configure async appenders with bounded queue and `drop_on_full` policy for INFO while ERROR sync-writes. Monitor agent buffer depth.

## OpenTelemetry logs vs JSON stdout

Kubernetes collects stdout JSON; OTel logs exporter adds vendor flexibility. Either works—do not duplicate both paths without sampling. Single exit point reduces cost and schema drift.
""",

    "observability-synthetic-monitoring-apis": """

## Multi-step journey teardown

Synthetic create-order flows must delete test data in `finally` block—orphan orders pollute analytics and inventory. Use dedicated `synthetic_tenant_id` filtered from business dashboards.

## Private API probing

APIs not on public internet: deploy synthetic probes **inside VPC** (Grafana Private Probe, self-hosted k6 in cluster) while also probing public edge for split-brain detection.

## SLA reporting

Monthly uptime report for customers cites synthetic success rate from external probes—not internal kubelet health. Aligns contractual SLA with measurement method legal expects.
""",

    "observability-tail-sampling-otel": """

## Collector HA and tail sampling

Run collector gateway in StatefulSet with persistent queue (Kafka/Pulsar backing) if trace loss during collector restart is unacceptable—memory-only tail sampling trades simplicity for durability.

## Policy testing in staging

Export `tail_sampling_decision` metric per policy—assert error policy `decision=sampled` count matches injected fault count in chaos tests.

## Cost projection

Stored traces per day ≈ `QPS × sample_rate × avg_span_count × bytes_per_span`. Tail sampling at 1% success + 100% errors often lands 5–20× cheaper than 100% head sampling with better debuggability—model before Tempo storage commit.
""",

    "observability-trace-context-w3c-baggage": """

## Baggage size limits at gateway

Strip or truncate baggage exceeding 4KB at API gateway—prevent client-supplied baggage DOS on downstream header parsing.

## W3C vs AWS X-Ray

Hybrid AWS migration: OTel propagator `xray` alongside tracecontext during Lambda → EKS transitions. Document header precedence in shared library—dual context bugs split traces for weeks.

## Propagation integration tests in CI

Testcontainers spin mock services A→B→C; assert trace-id unchanged and baggage key survives—all services must pass before deploy to production mesh.
""",
})

# Fix red-metrics expansion (was placeholder)
EXPANSIONS["observability-red-metrics-method"] = """

## USE metrics for saturation complement

RED on methods tells you requests fail or slow; **USE** (Utilization, Saturation, Errors) on resources explains why:

| Resource | Utilization | Saturation |
|----------|-------------|------------|
| DB pool | connections_active / max | wait_time in traces |
| Event loop | eventloop delay gauge | request queue depth |
| CPU | container CPU / limit | throttling seconds |

Dashboard row: RED for `POST /checkout` adjacent to pool wait p99—on-call sees method errors correlate with pool saturation without separate incident.

## GraphQL and RED

GraphQL single HTTP endpoint breaks naive RED per route—label by `graphql.operation.name` from parsed query or persisted query id:

```javascript
const operationName = parseOperationName(req.body.query);
labels.route = `graphql:${operationName}`;
```

Without this, all GraphQL traffic masquerades as `POST /graphql` one blob.

## Recording rules for alert stability

Alert on 5-minute recorded error ratio per method—smoother than raw counter spikes from deploy pod churn:

```yaml
- record: method:http_errors:ratio5m
  expr: |
    sum by (route) (rate(http_requests_total{status_class="5xx"}[5m]))
    /
    sum by (route) (rate(http_requests_total[5m]))
```

Pages link to method-level dashboard row, not whole-service aggregate hiding broken coupon endpoint.
"""

EXPANSIONS.update({
    "oauth2-token-introspection-revocation__p2": """

## Token introspection caching anti-patterns

**Negative caching inactive tokens** — Never cache `active: false` longer than zero. Attackers probing revoked tokens could theoretically trigger cache poisoning in poorly designed caches—always re-introspect or use zero TTL for inactive.

**Shared cache across environments** — Staging introspection responses cached in Redis instance also used by prod resource servers causes spectacular cross-environment auth bugs. Separate cache namespaces by `environment` label minimum.

**Logging introspection responses** — Full JSON includes `sub`, `scope`, sometimes `username`. Redact in log pipeline; log hash of token instead of token parameter.

## Federation logout cascades

OIDC back-channel logout notifies RPs when session ends. Pair with:

1. Revoke refresh tokens (RFC 7009)
2. Mark access token JTIs inactive
3. Introspection returns false within cache TTL

Test federated logout quarterly—partners depending on your introspection must see consistent `active` state within documented SLA (typically <60 seconds).
""",

    "observability-api-latency-histograms__p2": """

## Edge CDN and origin histogram separation

CDN caches hide origin latency in user-facing metrics. Instrument **origin-only** histogram on API servers and **edge** histogram on CDN logs separately. SLO dashboards for API team use origin; product NPS correlates with edge. Comparing both during cache miss storms explains "users slow, origin fine" paradox.

## Histograms for async work

HTTP returns 202 immediately while work continues—histogram on HTTP misleading. Emit separate histogram `job_processing_duration_seconds` for queue workers with same bucket design process as API latency doc. Alert on worker histogram SLO, not HTTP 202 latency.
""",

    "observability-continuous-profiling-parca__p2": """

## Retention and legal hold

Profile blobs may contain function names revealing unreleased features—align S3 retention with code release policy. Legal hold on incident dates: snapshot profile object storage prefix for postmortem evidence alongside traces.

## On-call training exercise

Quarterly: inject CPU loop in staging service, on-call must find hot function in Parca within 15 minutes without SSH. Failure means runbook or access gaps—fix before production incident.
""",

    "observability-continuous-profiling__p2": """

## Vendor vs self-hosted decision matrix

| Factor | Self-hosted Parca/Pyroscope | Datadog CP |
|--------|----------------------------|------------|
| Ops burden | You run object storage + agents | Vendor |
| Data residency | Full control | Vendor region |
| Trace correlation | DIY Tempo linking | Integrated APM |
| Cost at 500 pods | Infra + eng time | Per-host fee |

Document decision in ADR when adopting continuous profiling—revisit when pod count 10×.
""",

    "observability-db-query-tracing-orm__p2": """

## Prepared statement and ORM cache effects

ORM L2 cache hits produce no DB span—traces show fast handler mysteriously. Add span attribute `cache.hit=true` on short path for debugging "sometimes slow" tickets. Without it, compare trace with missing DB spans vs many DB spans for same endpoint.

## Sharding and cross-shard queries

ORM spanning shards may emit sequential spans to multiple hosts—trace shape looks like N+1 but is architectural. Label spans with `db.shard=id` for clarity in architecture reviews.
""",

    "observability-ebpf-network-observability__p2": """

## IPv6 dual-stack clusters

Hubble must resolve IPv6 pod addresses—verify flow maps show same edges as IPv4 during dual-stack migration. Mixed stacks cause "missing edge" when CSMS or legacy monitors IPv4-only.

## Incident timeline reconstruction

Export Hubble flows to PCAP-less timeline CSV during postmortem: `{timestamp, src, dst, verdict, bytes}`. Attach to incident doc—faster than screenshot gallery for auditors.
""",

    "observability-error-budget-burn-alerts__p2": """

## SLO waiver process

Planned maintenance burns budget—file waiver ticket subtracting expected burn from alert thresholds or silence burn alerts with documented change ticket. Unplanned burn without waiver triggers automatic incident commander assignment in mature orgs.

## Customer-facing SLO pages

Public status page "99.9% this month" must match internal burn math—discrepancy erodes trust. Automate status page from same Prometheus recording rules as internal SLO, not separate manual spreadsheet.
""",

    "observability-exemplars-traces-metrics__p2": """

## Heatmap panel configuration gotchas

Grafana heatmap requires `format: heatmap` on Prometheus query and `Exemplars: true` in panel options—easy to miss in JSON dashboard provisioning. Lint dashboards in CI with grafonnet or jsonnet tests asserting exemplar config on tier-1 latency panels.

## Mobile and high-latency clients

Mobile apps may show user latency >> server histogram if network slow—exemplars on server heatmap still valuable but pair with RUM for complete story. Do not argue server SLO green while mobile RUM red without acknowledging client/network path.
""",

    "observability-grpc-status-code-metrics__p2": """

## Reflection and health service noise

gRPC health checks and reflection RPCs inflate `grpc_server_started_total`—exclude from SLO denominators via label `grpc_method!~"Check|ServerReflectionInfo"` or separate service port for health on different registration.

## Streaming backpressure signals

Client-side `RESOURCE_EXHAUSTED` on streaming RPC may indicate consumer slower than producer—track per-method stream duration and message rate metrics alongside unary RED.
""",

    "observability-kafka-consumer-lag-slo__p2": """

## Exactly-once and lag semantics

Transactions and idempotent consumers may commit offset after side effect—lag drops only after slow processing completes. Document expected lag during large replay after consumer downtime; avoid false pages during intentional catch-up with raised threshold window.

## MirrorMaker lag

Cross-cluster replication adds second lag dimension—alert on MM2 lag separately from consumer group lag. Users see stale data if MM2 falls behind even when downstream consumer is current on secondary cluster.
""",

    "observability-log-trace-correlation__p2": """

## Serverless and trace context

Lambda cold starts must extract traceparent from API Gateway event headers and inject into logger before first log line—or entire invocation orphaned. AWS Distro for OpenTelemetry layer handles this if stdout JSON includes trace fields automatically.

## Log-based trace reconstruction (last resort)

When trace backend lost but logs retain trace_id, reconstruct partial timeline by sorting logs on trace_id—ugly but saves incident when Tempo retention expired. Argues for log trace_id retention ≥ trace retention.
""",

    "observability-metrics-cardinality__p2": """

## PromQL subquery cardinality explosions

`group by (user_id) (...)` in ad-hoc queries does not create series—but recording rules accidentally grouping by high-cardinality label do. Review recording rule PRs for forbidden labels same as instrumentation PRs.

## Federation and remote write duplicates

Dual remote write to two vendors accidentally with different label rewrite rules duplicates effective cardinality cost—audit remote_write configs quarterly.
""",

    "observability-oncall-runbook-automation__p2": """

## Runbook localization

Global on-call may need runbook sections in multiple languages for follow-the-sun—automate diagnose script output in English with machine translation disclaimer for internal tiers, not customer-facing text.

## Integration with status page

Auto-update status page component when synthetic check fails AND runbook confirms user impact—semi-automated with human ack prevents premature public incident declaration on flaky synthetic.
""",

    "observability-red-metrics-method__p2": """

## Worker queue RED

Background workers are not HTTP—apply RED to `{queue_name}`:

- Rate: jobs processed / sec
- Errors: jobs failed / total
- Duration: job handler histogram

Same dashboard patterns as HTTP; different instrumentation hook in worker framework middleware.

## API versioning in route label

`/api/v1/users` vs `/api/v2/users` must be distinct normalized routes during migration—both active simultaneously. Collapsing to `/api/:ver/users` preserves version breakdown for canary analysis.
""",

    "observability-service-graph-topology__p2": """

## Cost of span metrics generation

Tempo metrics-generator derives RED from spans—increases Tempo CPU. Size generator pods for peak trace ingest; disable span metrics on dev environments to save cost while keeping prod service graph enabled.

## Graph-driven capacity planning

Edge weight `rps` growth month-over-month on `checkout→fraud` edge justifies scaling fraud service before checkout peak season—graph becomes capacity planning input, not just incident tool.
""",

    "observability-structured-log-schema__p2": """

## Schema for mobile clients

Mobile apps logging to same pipeline need schema fields `client.os`, `client.app_version`—version as semver string for comparison queries. Crash logs separate schema extension `mobile.crash.*` with symbolication metadata.

## Breaking change communication

Schema major version bump triggers Slack notification to all service owners via CI—30-day dual-write window before enforcement. Silence breaks downstream SIEM parsers.
""",

    "observability-structured-logging__p2": """

## Log-based metrics caution

Loki metric queries (`metric queries`) on high-cardinality labels recreate cardinality problem in logs backend—prefer Prometheus counters for rates, logs for drill-down only.

## Exception formatting

Language stack traces as structured `error.stack` array of frames `{file, line, function}` parse better in SIEM than multiline string—optional enhancement for JVM and .NET loggers.
""",

    "observability-synthetic-monitoring-apis__p2": """

## Certificate expiry synthetic

Dedicated probe validates TLS cert expiry >14 days on all public API hostnames—catches Let's Encrypt renewal failures before users see browser warnings. Separate from journey synthetics but same on-call routing.

## Webhook inbound synthetic

Payment providers callback your webhook—synthetic cannot easily simulate unless provider offers test mode webhook replay. Document gap; use provider status page + manual quarterly webhook drill.
""",

    "observability-tail-sampling-otel__p2": """

## Tail sampling and compliance retention

Regulated industries may require 100% retention for financial transaction traces—apply tail policy exception `service=payments AND span.name=CaptureFunds` always sample regardless of success. Legal overrides cost optimization.

## Debugging dropped traces

Export `otelcol_processor_tail_sampling_count_traces_dropped` — spike during traffic surge may indicate `num_traces` buffer too small, not intentional sampling. Size buffers for peak complete trace rate × decision_wait.
""",

    "observability-trace-context-w3c-baggage__p2": """

## Service mesh and traceparent

Istio/Linkerd generate sidecar spans—traceparent arriving at app container may differ from edge. Consistent service graph requires telemetry API or mesh config propagating same trace IDs—consult mesh docs for YOUR mesh version; misconfiguration common during Istio upgrades.

## Baggage and GDPR

Right-to-erasure requests: baggage must not cache user identifiers across async jobs—stateless propagation only; do not write baggage keys to durable queues without TTL and legal review.
""",
})


def expand_file(slug: str, text: str) -> str:
    for key, addition in EXPANSIONS.items():
        if key.endswith("__p2"):
            base = key.replace("__p2", "")
            if slug != base:
                continue
        elif key.endswith("__"):
            continue
        elif slug != key:
            continue
        addition = addition.strip()
        if addition in text:
            continue
        if "## Resources" in text:
            text = text.replace("\n## Resources", f"\n{addition}\n\n## Resources", 1)
        else:
            text = text + "\n" + addition + "\n"
    return text


def main():
    slugs = set()
    for key in EXPANSIONS:
        slugs.add(key.replace("__p2", ""))
    for slug in sorted(slugs):
        path = BLOG / f"{slug}.md"
        if not path.exists():
            print(f"MISSING {slug}")
            continue
        raw = path.read_text()
        new = expand_file(slug, raw)
        if new != raw:
            path.write_text(new)
        wc = len(new.split())
        flag = "OK" if wc >= 1200 else "SHORT"
        print(f"{flag} {wc:5} {slug}")


if __name__ == "__main__":
    main()
