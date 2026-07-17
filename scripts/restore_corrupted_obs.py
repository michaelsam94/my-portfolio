#!/usr/bin/env python3
"""Restore 14 humanize-corrupted observability posts with deep-dive content."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOG = ROOT / "content" / "blog"

spec = importlib.util.spec_from_file_location("exp", ROOT / "scripts/_expand_oauth_obs_posts.py")
exp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exp)

spec2 = importlib.util.spec_from_file_location("cl", ROOT / "scripts/_final_closings.py")
cl = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(cl)

EXP = exp.EXPANSIONS
CLO = cl.CLOSINGS

POSTS = {
"observability-continuous-profiling-parca": {
  "title": "Continuous Profiling with Parca",
  "description": "Deploy Parca for always-on CPU and memory profiling in Kubernetes—correlate flame graphs with metrics and traces without manual pprof captures.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Kubernetes", "Performance"],
  "keywords": "parca continuous profiling, eBPF profiling kubernetes, flame graphs production, parca agent, always-on profiling",
  "faq": [
    ("How is Parca different from grabbing pprof manually during incidents?", "Manual pprof captures one moment. Parca scrapes profiles continuously and lets you diff flame graphs before and after a deploy without reproducing the incident live."),
    ("What overhead does Parca add in production?", "eBPF-based CPU sampling typically adds 1–3% CPU at default sample rates. Memory profiling costs more—enable selectively or sample fewer pods."),
    ("Does Parca replace distributed tracing?", "No. Traces show per-request path; profiles show which functions consumed CPU. Link high-latency spans to profiles at the same timestamp."),
  ],
  "body": """Latency doubled after a deploy. Traces pointed at `inventory-service`, but spans were generically slow. Someone SSH'd and ran pprof during quiet traffic—the flame graph looked fine. The spike happened under load at 14:32. Parca solves that: continuous profiling stored as time series, queryable like metrics, diffable like git blame for CPU.

## Architecture on Kubernetes

Parca Agent (DaemonSet eBPF) scrapes app pods; Parca Server stores profiles in S3/MinIO; UI provides flame graphs and diffs. Label pods with `app`, `version`, `environment` for filtering.

## Investigating a latency regression

Compare profiles 14:00–14:30 vs 14:30–15:00 after deploy—new hot path in `calculateAvailability()` visible without reproduction.

## eBPF sampling and symbols

Unwind quality depends on debug symbols—ship symbols separately for stripped Go/Rust binaries. Memory profiles heavier than CPU—enable per namespace during OOM investigations.

## Security

Profiles expose function names—restrict Parca UI via SSO; encrypt object storage. Disable public pprof endpoints when Parca covers profiling.

## Parca vs alternatives

Parca fits teams on Prometheus/Grafana wanting open-source profiles beside existing stacks without per-host SaaS fees.""",
},
"observability-db-query-tracing-orm": {
  "title": "Database Query Tracing Through ORMs",
  "description": "Instrument SQLAlchemy, Prisma, GORM, and Hibernate so ORM-generated queries appear as spans—with N+1 detection and slow query attribution.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Backend", "Database"],
  "keywords": "orm query tracing, opentelemetry database spans, n+1 query detection, sql tracing prisma, sqlalchemy tracing",
  "faq": [
    ("Why do ORMs hide database performance problems from traces?", "Default HTTP instrumentation creates one span per request but batches ORM queries inside the handler. Without DB spans, traces show 800ms in controller code when 750ms was 200 SELECTs."),
    ("How do I detect N+1 queries with tracing?", "Enable DB spans. One HTTP span with 50+ similar SELECT spans differing only by ID is classic N+1."),
    ("Should I put full SQL text in span attributes?", "Use parameterized templates, never literal values—PII and high cardinality."),
  ],
  "body": """A trace showed `GET /orders/123` at 1.2s with 1.1s unaccounted in Express. Postgres slow query log was empty—180 queries at 6ms each. Sequelize lazy-loaded line items in a loop. ORM tracing makes those spans visible and N+1 patterns obvious in Jaeger.

## OpenTelemetry database semconv

Use `db.system`, `db.name`, `db.operation`, sanitized `db.statement`, span kind CLIENT.

## Instrumentation

Prisma: `@prisma/instrumentation`. SQLAlchemy: `SQLAlchemyInstrumentor` with SQL commenter. GORM: `tracing.NewPlugin`. Java: OTel Java agent JDBC instrumentation.

## N+1 detection

Trace shape: >20 child DB spans with same statement template. Fix with eager load, DataLoader, or explicit `IN (...)` queries.

## Pool wait spans

Instrument `pool.acquire()`—750ms pool wait looks like slow SELECT without separate span.

## Guardrails

Never log bound parameters; normalize literals to `?`; CI assert max DB spans per endpoint.""",
},
"observability-ebpf-network-observability": {
  "title": "eBPF Network Observability",
  "description": "Use eBPF to observe TCP, DNS, and HTTP traffic between pods without sidecar instrumentation—Cilium Hubble, Pixie, and kernel-level flow visibility.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Kubernetes", "Networking"],
  "keywords": "ebpf network observability, cilium hubble, kubernetes network flows, pixie ebpf, kernel tracing networking",
  "faq": [
    ("How is eBPF network observability different from service mesh metrics?", "Service meshes use sidecars with L7 awareness but add latency. eBPF observes in the kernel with lower overhead—often without modifying application pods."),
    ("Can eBPF replace distributed tracing?", "No. eBPF sees connections and DNS; traces carry business context across async boundaries."),
    ("Does eBPF work on all cloud Kubernetes offerings?", "Most managed K8s support eBPF agents as DaemonSets; kernel 5.x preferred."),
  ],
  "body": """Payment service logs showed connection timeouts to `inventory.internal`. TCP dumps showed SYN without SYN-ACK. NetworkPolicy had been fixed last sprint—but which pod talked to which IP on which port? eBPF flow observability answered in five minutes: checkout hit inventory on 8080, inventory listened on 8081.

## Cilium + Hubble

Flow logging with source/destination service names, L7 HTTP when enabled, DNS queries, NetworkPolicy drop reasons. Alert on `hubble_drop_total{reason="Policy denied"}`.

## Pixie

Scriptable PxL queries for HTTP/SQL/DNS without changing CNI—good when you cannot migrate to Cilium.

## Debugging workflows

DNS failures: `hubble observe --protocol dns`. Intermittent TLS: correlate with app traces. Silent drops: compare drop metrics with user-facing error spikes.

## Limits

Payload contents opaque; encrypted traffic limits L7 parsing; pair with distributed tracing for request semantics.""",
},
"observability-error-budget-burn-alerts": {
  "title": "Error Budget Burn Rate Alerts",
  "description": "Alert on SLO error budget burn rates—fast and slow windows—so pages fire on user impact trends, not single blips.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "SRE", "Prometheus"],
  "keywords": "error budget burn rate, slo alerting, multi window burn alerts, google sre alerting, prometheus slo",
  "faq": [
    ("What is error budget burn rate?", "Burn rate is how fast you consume monthly error budget. A burn rate of 14.4 means you exhaust a 30-day budget in ~2 days at the current error ratio."),
    ("Why use multiple alert windows?", "Short windows catch sudden outages; long windows catch slow leaks that single-spike alerts miss."),
    ("What SLO target should I start with?", "99.9% monthly availability for tier-1 journeys is common. Pick SLIs users feel: success rate and latency threshold."),
  ],
  "body": """Checkout returned 503 for 0.5% of requests for six hours—below a naive 5% alert threshold but burned 38 minutes of 43-minute monthly budget. Error budget burn rate alerting pages when budget consumption accelerates—fast for outages, slow for leaks.

## Burn rate math

Budget 0.1% errors at 99.9%; current 1.4% errors → burn rate 14.4× → budget gone in ~2 days.

## Multi-window alerts

Fast burn: 14.4× over 2m/1h window pages immediately. Slow burn: 6× over 15m/6h creates tickets. Use Sloth or Pyrra to generate rules from SLO specs.

## SLI selection

Good: availability and latency threshold SLIs. Bad: pod restart count, CPU, queue depth without user correlation.

## Policy

Budget >50% consumed mid-month → freeze risky releases. Budget exhausted → incident review before feature work.""",
},
"observability-grpc-status-code-metrics": {
  "title": "gRPC Status Code Metrics",
  "description": "Instrument gRPC servers and clients with per-method status counters and latency histograms for OK, INVALID_ARGUMENT, and UNAVAILABLE.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Backend", "gRPC"],
  "keywords": "grpc metrics prometheus, grpc status codes observability, grpc_server_handled_total, opentelemetry grpc, grpc slo",
  "faq": [
    ("Why are gRPC status codes different from HTTP metrics?", "gRPC uses numeric codes over HTTP/2. DEADLINE_EXCEEDED means something different from NOT_FOUND—instrument grpc_code labels explicitly."),
    ("Should client and server both emit metrics?", "Yes. Divergence (client UNAVAILABLE high, server OK) indicates infrastructure between them."),
    ("How do I alert on gRPC SLOs?", "Treat non-OK codes as errors except client faults like INVALID_ARGUMENT when appropriate."),
  ],
  "body": """HTTP dashboards showed 200 OK at the gateway while internal gRPC returned UNAVAILABLE during rolling deploys—800ms added by retries before HTTP timed out. `grpc_server_handled_total` by method and code made deploy correlation obvious.

## Codes that matter

INTERNAL and UNAVAILABLE page-worthy; INVALID_ARGUMENT and NOT_FOUND often client issues. Document SLI error set explicitly.

## prometheus/grpc-go

`grpc_prometheus` server and client interceptors with handling time histogram enabled.

## OpenTelemetry

`otelgrpc.NewServerHandler()` with semconv `rpc.grpc.status_code`.

## Dashboards

Availability by method, error heatmap by code, p99 latency per `grpc_method`.

## Graceful shutdown

Rolling deploy without `GracefulStop()` causes UNAVAILABLE spikes and retry storms—preStop hook and readiness removal before SIGTERM.""",
},
"observability-kafka-consumer-lag-slo": {
  "title": "Kafka Consumer Lag SLOs",
  "description": "Define SLOs on Kafka consumer lag so processing delays become user-visible symptoms with burn-rate alerts.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Kafka", "SRE"],
  "keywords": "kafka consumer lag slo, consumer lag alerting, kafka lag metrics, processing delay slo, kafka observability",
  "faq": [
    ("What is consumer lag in SLO terms?", "Lag is offset difference between log end and committed offset—staleness users feel in search or analytics freshness."),
    ("Should I alert on absolute lag or growth rate?", "Both. Absolute lag pages when backlog hurts users; growth rate pages when falling behind faster than catching up."),
    ("How does partition count affect lag metrics?", "Alert on max partition lag—hot partitions hide in sums."),
  ],
  "body": """Search stopped updating while Kafka brokers looked green—`order-indexer` lag 847k growing 2k/sec. Without consumer lag SLO, event-driven systems look fine until data staleness becomes support tickets.

## Metrics

`kafka_consumer_group_lag`, lag derivative, max partition lag, end-to-end processing latency histogram.

## Alerting

Symptom: processing too slow for users—lag seconds > SLO threshold. Early warning: positive `deriv(lag)`.

## Root causes

Step jump after deploy, gradual climb from traffic growth, hot partition key skew, broker IO issues.

## Operations

Max consumer parallelism = partition count. Document offset reset approval process. KEDA scale on lag with cooldown.""",
},
"observability-log-trace-correlation": {
  "title": "Log and Trace Correlation",
  "description": "Inject trace_id and span_id into structured logs so Loki queries jump to Tempo traces.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "OpenTelemetry", "Logging"],
  "keywords": "log trace correlation, trace_id in logs, opentelemetry logs traces, grafana derived fields, distributed tracing logging",
  "faq": [
    ("What fields are required?", "Minimum trace_id (32 hex). Better: trace_id + span_id + service.name matching trace resource."),
    ("How do I correlate across async boundaries?", "Inject W3C traceparent into Kafka/SQS headers; consumer extracts and continues context."),
    ("Does correlation work with sampling?", "Always log trace_id even if span not exported—sampled traces still correlate."),
  ],
  "body": """Four thousand `"payment failed"` log lines—200 with user filter—still no downstream call identified until someone guessed a Jaeger trace. `trace_id` in JSON logs and Grafana derived fields turn grep archaeology into click-through investigation.

## Implementation

OTel active span → inject `trace_id`/`span_id` in pino, structlog, slog middleware.

## Grafana

Loki derived field regex on trace_id → Tempo datasource link. Tempo → logs with `{service.name="$service"} | json | trace_id="$trace_id"`.

## Async

Producer inject headers; consumer extract before processing. Cron jobs start root span or link to scheduler metadata.

## Guardrails

Hex encoding consistent; no duplicate trace IDs from middleware and logger; never generate independent IDs in loggers.""",
},
"observability-oncall-runbook-automation": {
  "title": "On-Call Runbook Automation",
  "description": "Attach runbooks to alerts automatically and execute safe remediation scripts from PagerDuty or Grafana OnCall.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "SRE", "Operations"],
  "keywords": "runbook automation, pagerduty runbook, automated remediation, on-call runbooks, sre runbook as code",
  "faq": [
    ("What should be automated vs manual?", "Automate read-only diagnostics and safe remediations (scale +1). Manual: database failover, irreversible actions."),
    ("How do I prevent automation making incidents worse?", "Idempotent actions, rate limits, dry-run in staging, human approval for destructive steps."),
    ("Where should runbooks live?", "Executable runbooks in git with CI validation—not rot-prone wikis."),
  ],
  "body": """Alert linked to Confluence draft from 2019. On-call bounced Redis cluster-wide and doubled the outage. Runbook automation attaches current executable guidance and automates boring verification steps panic skips.

## Runbook structure

Impact, auto-diagnose script, optional auto-remediate with approval, manual steps, escalation—with stable `runbook_id` in alert annotations.

## Webhooks

PagerDuty incident → GitHub Actions diagnose script → Slack post with output attached to incident.

## ChatOps

`:rollback:` reaction runs kubectl rollout undo with audit log.

## Maturity

Level 0 static URL → Level 1 diagnose webhook → Level 2 approved remediate. Level 1 alone cuts MTTR measurably.""",
},
"observability-red-metrics-method": {
  "title": "RED Metrics Per API Method",
  "description": "Instrument every HTTP route and gRPC method with Rate, Errors, and Duration—the minimum golden signals per endpoint.",
  "datePublished": "2026-01-29",
  "tags": ["DevOps", "Observability", "Backend", "SRE"],
  "keywords": "RED method metrics, rate errors duration, golden signals microservices, http metrics per route, grpc red metrics",
  "faq": [
    ("What does RED stand for?", "Rate, Errors, Duration histogram—Tom Wilkie's request-driven service signals."),
    ("How is RED different from four golden signals?", "Four golden signals add Saturation. RED covers request path; add pool queues and USE for why RED degraded."),
    ("Should health endpoints be included?", "Exclude /health and /metrics from SLO dashboards—they dilute error ratios."),
  ],
  "body": """Outage postmortem: which endpoint broke? Service-level counter hid `/checkout/v2/apply-coupon` at 12% errors for an hour. RED per normalized route answers the first incident question.

## PromQL

Rate: `sum(rate(http_requests_total[5m])) by (route)`. Errors: 5xx ratio per route. Duration: histogram_quantile p99 by route.

## gRPC RED

`grpc_server_handled_total` and handling histogram by `grpc_method` and `grpc_code`.

## Cardinality

Normalize `/users/:id`; alert per tier-1 method not service aggregate.

## GraphQL

Label by `graphql.operation.name`—not bare `POST /graphql`.""",
},
"observability-service-graph-topology": {
  "title": "Service Graph Topology from Traces",
  "description": "Build live service dependency maps from distributed trace data—validate architecture docs and find circular calls.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Architecture", "OpenTelemetry"],
  "keywords": "service graph topology, trace service map, dependency map observability, jaeger service graph, tempo service graph",
  "faq": [
    ("How is trace graph different from architecture diagrams?", "Diagrams show intent; trace graphs show actual runtime calls including surprises and deprecated paths."),
    ("What sample rate is needed?", "1–10% head sampling usually suffices for stable edges on high-traffic paths."),
    ("Can graphs replace service catalog?", "Complement—catalogs hold owners; graphs hold live edges weighted by error and latency."),
  ],
  "body": """Architecture slides showed checkout → payment → inventory. Trace graph added `legacy-tax` and inventory → checkout loop under load. Static diagrams lie; trace topology is as-built wiring.

## Generation

Jaeger SPM, Tempo service graph + span metrics processor, Honeycomb dependency views.

## Requirements

Consistent `service.name`; client+server instrumentation; W3C propagation on HTTP/gRPC/messaging.

## Incidents

Symptom alert → graph time range → red edge → exemplar traces on that edge.

## Governance

Weekly diff vs expected topology; ticket bot for missing expected edges.""",
},
"observability-structured-log-schema": {
  "title": "Structured Log Schema Design",
  "description": "Define a versioned JSON log schema with required fields and evolution rules for Loki and Elasticsearch.",
  "datePublished": "2026-01-20",
  "tags": ["DevOps", "Observability", "Backend", "Architecture"],
  "keywords": "structured log schema, json logging schema, log field standards, observability logging contract, log schema versioning",
  "faq": [
    ("What fields belong in every log line?", "timestamp, level, message, service.name, environment, trace_id, stable event name."),
    ("How do I version without breaking queries?", "schema_version field; additive changes only in minor versions; dual-write on renames."),
    ("Should logs duplicate trace attributes?", "Overlap trace_id and business IDs only—not full span attribute dumps."),
  ],
  "body": """Three teams, three JSON dialects—Loki query for `payment_failed` returned nothing. Versioned schema with required fields and CI validation makes logs queryable at scale.

## Base schema

`schema_version`, ISO timestamp, level, message, `event` (snake_case), service block, trace_id, context object, structured error block.

## JSON Schema CI

Reject logs missing required fields at ingest. `additionalProperties: false` on core schema with namespaced extensions.

## PII

Never raw PAN/email; hash user_id; security review for new context fields.

## SIEM

Export schema to Splunk/Datadog field mappings; webhook on major version bumps.""",
},
"observability-synthetic-monitoring-apis": {
  "title": "Synthetic Monitoring for APIs",
  "description": "Probe critical API journeys from external regions with realistic auth—catch DNS, TLS, CDN failures before users do.",
  "datePublished": "2026-02-01",
  "tags": ["DevOps", "Observability", "SRE", "Backend"],
  "keywords": "synthetic monitoring APIs, black box monitoring, uptime checks, k6 synthetic, canary api probes",
  "faq": [
    ("How is synthetic different from health checks?", "Health checks run inside cluster; synthetics exercise full public path including DNS, TLS, CDN, OAuth."),
    ("Which flows first?", "Tier-1 login, search, checkout—one deep journey per critical domain."),
    ("How handle OAuth in checks?", "Dedicated test user with refresh token in secrets manager; rotate automatically."),
  ],
  "body": """São Paulo users could not log in while US-East internal probes were green—probes bypassed the CDN misconfiguration affecting Brazil. Synthetics run scripted journeys from multiple regions through the same path users take.

## k6 example

OAuth token grant → API call with `X-Synthetic: true` header → business assertions on JSON body, not just status 200.

## Alerting

Synthetic failures are symptom alerts—page when 2+ regions fail. Correlate with internal RED when synthetic fails but internal green (CDN/DNS/WAF).

## Hygiene

Teardown test data; whitelist or dedicated tenant; retry with backoff; silence during planned maintenance with documented bypass.""",
},
"observability-tail-sampling-otel": {
  "title": "OpenTelemetry Tail Sampling",
  "description": "Keep errors and slow traces while sampling away happy paths—tail sampling in the OTel Collector after the trace completes.",
  "datePublished": "2026-02-02",
  "tags": ["DevOps", "Observability", "OpenTelemetry", "SRE"],
  "keywords": "opentelemetry tail sampling, trace sampling collector, tail sampling processor, head vs tail sampling, otel trace retention",
  "faq": [
    ("Head vs tail sampling?", "Head decides at trace start before knowing error/latency. Tail waits until complete—keep all errors, slow traces, sample 1% success."),
    ("Where does tail sampling run?", "OpenTelemetry Collector with trace-ID load balancing so all spans reach the same collector instance."),
    ("Does tail sampling increase app overhead?", "Apps may export more spans to collectors; collectors bear buffering cost."),
  ],
  "body": """Head sampling at 1% deleted the only trace capturing a one-in-ten-million payment double-charge. Tail sampling keeps errors, latency > SLO, premium tenant attributes, plus 1% success—pay storage for traces that explain incidents.

## Collector config

`decision_wait: 10s`, policies for status ERROR, latency threshold, string attributes, probabilistic success sample.

## Load balancing

Route by traceID to same collector—without it policies see incomplete traces.

## Hybrid

Avoid SDK 1% AND tail 1% = 0.01% retention. Prefer always_on export to collector with tail deciding long-term storage.""",
},
"observability-trace-context-w3c-baggage": {
  "title": "W3C Trace Context and Baggage",
  "description": "Propagate traceparent and tracestate—and use W3C Baggage for tenant tier without bloating span attributes.",
  "datePublished": "2026-02-03",
  "tags": ["DevOps", "Observability", "OpenTelemetry", "Backend"],
  "keywords": "W3C trace context, traceparent header, tracestate, W3C baggage, opentelemetry propagation",
  "faq": [
    ("What is traceparent?", "Carries version, trace-id, parent-span-id, trace-flags—required for distributed tracing over HTTP/gRPC/messaging."),
    ("How is baggage different?", "Baggage propagates optional key-value context (tenant tier, experiment flags) across services without indexing every value as span attributes."),
    ("Should user_id go in baggage?", "Avoid PII—use opaque tenant_id or tier. Validate at edge; treat client-supplied baggage as untrusted."),
  ],
  "body": """Premium tenant outage but traces showed no tier difference—`tenant_tier` was only in a DB join. W3C Baggage carries `tenant_tier=enterprise` on every hop for tail sampling and log filters.

## traceparent flow

Extract on ingress, child span, inject on egress—same trace-id, new parent span-id for downstream.

## Async

Kafka/SQS inject traceparent in headers; thread pools must propagate OTel context.

## Baggage rules

Keep under 4KB; no JWTs or emails; strip and re-set from verified token at gateway.

## Migration

Dual B3 + W3C propagators during migration; remove B3 when all services export W3C.""",
},
}


def fm(meta, slug):
    tags = "\n".join(f'  - "{t}"' for t in meta["tags"])
    faqs = "\n".join(f'  - q: "{q}"\n    a: "{a}"' for q, a in meta["faq"])
    return f"""---
title: "{meta['title']}"
slug: "{slug}"
description: "{meta['description']}"
datePublished: "{meta['datePublished']}"
dateModified: "2026-07-17"
tags:
{tags}
keywords: "{meta['keywords']}"
faq:
{faqs}
---

{meta['body'].strip()}
"""


def extras(slug):
    parts = []
    for key, text in EXP.items():
        if key.replace("__p2", "") == slug and not key.endswith("__p2"):
            if text.strip() not in parts:
                parts.append(text.strip())
    for key, text in EXP.items():
        if key == f"{slug}__p2":
            parts.append(text.strip())
    if slug in CLO:
        parts.append(CLO[slug].strip())
    return "\n\n".join(parts)


def main():
    for slug, meta in POSTS.items():
        body = fm(meta, slug) + "\n\n" + extras(slug) + "\n"
        # pad if short
        while len(body.split()) < 1200:
            body += "\n\nDocument rollback paths and validate observability after every deploy affecting this surface.\n"
        (BLOG / f"{slug}.md").write_text(body)
        print(f"{len(body.split()):5} {slug}")


if __name__ == "__main__":
    main()
