#!/usr/bin/env python3
"""Topic-specific closing sections to reach 1200+ words without generic template."""
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"

CLOSINGS = {
    "oauth2-token-introspection-revocation": """
## Closing the loop with resource servers

Resource servers should treat introspection latency as part of the request critical path budget. If introspection adds 40ms p99 and your checkout SLO is 500ms p99, that is 8% of user-visible latency spent on auth verification—worth tracking alongside database time. Emit client-side metrics on introspection cache hits, misses, and errors; alert when miss rate spikes after AS deploys.

Document for API consumers whether tokens are JWT (local validation) or opaque (introspection required). Partner integrations fail mysteriously when docs omit this distinction and partners attempt local JWKS validation on opaque tokens. Your public API reference should state validation method, expected `aud` claim, and introspection endpoint URL for opaque flows only.
""",
    "observability-api-latency-histograms": """
## Histograms in autoscaling decisions

Horizontal Pod Autoscaler custom metrics often use average latency derived from histograms. Misconfigured buckets skew HPA: if all latency sits in one bucket, HPA sees flat p95 and fails to scale during gradual degradation. When wiring HPA to Prometheus, use recording rules for p95 per service with buckets validated against load test bimodal distributions (cache hit vs miss).

SRE review of new endpoints should include signing off histogram bucket set before the route serves production traffic—same gate as OpenAPI review. Adding buckets later creates new time series; choosing correctly once avoids dashboard discontinuities during peak season.
""",
    "observability-continuous-profiling-parca": """
## Ownership and access model

Assign Parca UI access to service teams for their namespaces only—platform operates agents and storage, product teams investigate their flame graphs. Prevents accidental cross-team visibility into unreleased feature code paths visible in symbols while still enabling self-service perf debugging.

Include Parca link in performance-related incident templates next to Grafana and Tempo. Three-way correlation (metrics spike, trace slow span, profile hot function) should be exercisable in under ten minutes by any mid-level backend engineer after onboarding lab.
""",
    "observability-continuous-profiling": """
## When profiles contradict intuition

Teams often optimize JSON serialization while profiles show mutex contention in a metrics library lock. Trust profiles over assumptions during incidents—human guesses about hot paths are wrong often enough that profile-first triage saves hours. Capture profile screenshot in postmortem timeline next to deploy marker for regression tracking.

Budget continuous profiling storage like trace storage: 30-day default retention, 90-day for tier-1 payment services if required by internal policy. Object lifecycle rules prevent finance surprise on S3 bills.
""",
    "observability-db-query-tracing-orm": """
## ORM tracing in microservice decomposition

During monolith extraction, identical repository methods may run in two services—trace comparison proves which deployment still emits N+1 patterns. Use span counts as migration gate: extracted service must not exceed span budget of monolith equivalent endpoint before cutover traffic shifts.

DBA collaboration improves when traces include `db.system`, `db.name`, and normalized statement—DBAs filter Tempo by slow span without application log access. Shared language reduces ping-pong during index recommendation tickets.
""",
    "observability-ebpf-network-observability": """
## Runbook integration

Network timeout runbooks should start with Hubble/Pixie query templates parameterized by namespace and service labels from the alert. Copy-paste commands beat prose instructions at 3 AM. Include screenshot of healthy baseline flow map in runbook appendix so on-call recognizes abnormal edge colors quickly.

For hybrid cloud, eBPF sees pod-to-NAT-to-internet paths—document which hops are visible vs blind when debugging SaaS API failures from Kubernetes workloads. Reduces false accusations of external vendor outage when corporate proxy MITM is the actual fault.
""",
    "observability-error-budget-burn-alerts": """
## Executive communication

Translate burn rate alerts into non-technical summaries for leadership: "At current error rate we consume a week of monthly budget daily" lands better than raw PromQL. Automate weekly email from recording rules showing budget remaining per tier-1 SLO—aligns release train decisions without emergency meetings.

When multiple services share one error budget (user journey composite), document attribution rules when burn occurs—avoid circular blame between frontend and backend during joint incidents.
""",
    "observability-exemplars-traces-metrics": """
## Exemplar retention and Tempo alignment

Tempo retention shorter than metric retention yields exemplars pointing to expired traces—align retention policies or accept 404 on older exemplar clicks. For incidents older than trace retention, logs with trace_id remain fallback; document this limitation in on-call training.

Enable exemplars on tier-1 latency panels first; expand to tier-2 after validating storage impact in Mimir/Grafana Cloud billing dashboard over two-week soak period.
""",
    "observability-grpc-status-code-metrics": """
## gRPC retries and metric interpretation

Client retry middleware inflates `grpc_client_attempts` relative to server handled count—track attempt ratio as separate metric. High retry ratio with elevated `UNAVAILABLE` during deploys signals need for better graceful shutdown, not automatic client retry increase which amplifies load.

Document gRPC SLO error code sets in service README—new engineers otherwise assume all non-OK codes are page-worthy, causing alert definition drift between teams.
""",
    "observability-kafka-consumer-lag-slo": """
## Business stakeholder alignment

Product managers understand "search results 15 minutes stale" better than "lag 900000"—dashboards should show lag converted to freshness SLA with color thresholds agreed in quarterly planning. Engineering owns measurement; product owns acceptable staleness numbers.

During Kafka cluster upgrades, temporarily widen lag alert thresholds with change ticket reference—controlled lag spike during partition reassignment should not page if processing latency SLO still green.
""",
    "observability-log-trace-correlation": """
## Parser compatibility across log agents

Fluent Bit, Vector, and Promtail parse JSON differently—validate trace_id field extraction in staging with each agent version before fleet rollout. Double-escaped JSON from nested loggers breaks derived fields regex; standardize on single JSON object per log line without stringified JSON wrappers.

Include trace_id in audit logs for security-sensitive operations even when trace sampling is off—audit trail completeness outweighs trace backend storage cost for those events.
""",
    "observability-metrics-cardinality": """
## Developer education over enforcement alone

Cardinality lint in CI catches new bad labels at PR time; lunch-and-learn on why `user_id` labels hurt prevents repeat offenses from teams who missed the lint rule. Show Prometheus memory graph from real incident where one label exploded series—story beats policy document.

For acquisitions integrating new services, run cardinality audit in first week— inherited metrics often include anti-patterns from acquired team's earlier stack choices.
""",
    "observability-oncall-runbook-automation": """
## Measuring automation ROI

Track mean time from page to first automated diagnose output completion—target under 60 seconds. If diagnose scripts exist but nobody triggers them, problem is discoverability not automation—embed script output in default PagerDuty incident note via webhook rather than requiring manual script invocation.

Version runbook scripts with git tags matching service releases so postmortems reference exact diagnose logic used during incident, not moving main branch head.
""",
    "observability-red-metrics-method": """
## RED in serverless and function platforms

Lambda and Cloud Functions need RED on invocation handler, not just API Gateway HTTP metrics—cold start latency appears in function duration histogram, not edge 5xx. Instrument handler entry/exit in runtime wrapper shared library so all functions get consistent labels without copy-paste.

Batch jobs exposing HTTP admin port for health only should still emit RED on job processing endpoints if operators hit manual trigger APIs—do not leave admin routes as only instrumented surface while business logic runs silently.
""",
    "observability-service-graph-topology": """
## Graph as onboarding artifact

New engineers study service graph in first week to learn real dependencies—faster than reading stale wiki. Assign mentor walkthrough: pick one user journey, trace it in graph, open exemplar trace, read correlated logs. Practical observability onboarding beats slide deck architecture review.

When decommissioning services, graph should show edge traffic trending to zero before DNS cut—graph-driven deprecation confirms no shadow callers remain.
""",
    "observability-structured-log-schema": """
## SIEM field mapping

Export JSON schema to Splunk/Datadog field mapping configuration when enterprise SIEM ingests application logs—field name mismatches break correlation rules for security detections. Security team signs off schema changes affecting `security.*` events; application team signs off `event` catalog for product analytics.

Schema registry webhook notifies downstream parser owners on major version bump—prevent silent parse failures Friday evening after merge.
""",
    "observability-structured-logging": """
## Cost control without losing errors

Log volume budget per service with automatic throttle on INFO when daily quota exceeded—ERROR and WARN bypass throttle. Prevents one verbose deploy from indexing terabytes while preserving incident signal. Finance and engineering agree quota numbers quarterly based on per-GB ingest pricing.

Temporary debug logging for one tenant requires signed token and auto-expires—audit log records who enabled debug and when it disabled, satisfying support escalation policy without permanent verbose mode.
""",
    "observability-synthetic-monitoring-apis": """
## Coordinating with deployment windows

Silence synthetics during planned maintenance that intentionally returns 503 from edge—OR configure synthetics to hit maintenance bypass header on origin directly to validate origin health while edge shows maintenance page to users. Document which mode your status page commit uses to avoid false external green during deliberate user-facing maintenance.

Compare synthetic latency from multiple regions in one dashboard—single-region probe misses regional BGP issues affecting subset of users; multi-region disagreement triggers investigation before global page.
""",
    "observability-tail-sampling-otel": """
## Collector resource planning worksheet

Estimate required collector memory: `decision_wait × peak_traces_per_second × average_spans_per_trace × bytes_per_span_in_buffer`. Undersizing causes silent trace drop more common than explicit sampling—monitor dropped trace counter and size buffers for peak complete checkout flow during load test, not average Tuesday traffic.

Document tail sampling policies in service catalog entry for each service—on-call knows errors always retained for payments even when global success sample is 1%.
""",
    "observability-trace-context-w3c-baggage": """
## Debugging propagation failures in production

When orphan spans appear, enable OpenTelemetry Collector `probabilistic_sampler` debug logging temporarily OR use telemetry introspection API—avoid enabling debug globally. Common fix: reorder middleware so trace extraction runs before auth middleware that short-circuits unauthenticated requests without span.

Baggage propagation failures often manifest as missing tenant tier in downstream logs while present upstream—add integration test asserting baggage keys at each hop in CI pipeline for tier-1 services.
""",
}


def main():
    for slug, closing in CLOSINGS.items():
        path = BLOG / f"{slug}.md"
        text = path.read_text()
        closing = closing.strip()
        if closing in text:
            wc = len(text.split())
        else:
            if "## Resources" in text:
                text = text.replace("\n## Resources", f"\n{closing}\n\n## Resources", 1)
            else:
                text = text + "\n" + closing + "\n"
            path.write_text(text)
            wc = len(text.split())
        flag = "OK" if wc >= 1200 else "SHORT"
        print(f"{flag} {wc:5} {slug}")


if __name__ == "__main__":
    main()
