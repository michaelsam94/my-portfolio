---
title: "Centralized Logging with Loki"
slug: "kubernetes-logging-loki-fluentbit"
description: "Centralize Kubernetes logs with Grafana Loki and Fluent Bit: collection, labels, LogQL queries, retention, and avoiding cardinality explosions."
datePublished: "2026-02-09"
dateModified: "2026-02-09"
tags: ["Kubernetes", "DevOps"]
keywords: "Grafana Loki, Fluent Bit, LogQL, Kubernetes logging, log aggregation, Promtail, label cardinality"
faq:
  - q: "How is Loki different from Elasticsearch for logs?"
    a: "Loki indexes labels (metadata) not full log line content—like Prometheus for logs. Storage cost stays lower; ad-hoc full-text search is weaker than Elasticsearch. Loki fits teams already on Grafana who query logs alongside metrics with LogQL."
  - q: "Should I use Promtail or Fluent Bit with Loki?"
    a: "Fluent Bit is the common choice in Kubernetes—it collects container logs, systemd, and forwards to multiple backends. Promtail is Loki-native and simpler for Loki-only stacks. Many clusters run Fluent Bit as DaemonSet forwarding to Loki."
  - q: "What causes high cardinality problems in Loki?"
    a: "High-cardinality labels—user IDs, request IDs, pod UUIDs as labels—create excessive index streams and slow queries. Keep labels coarse: namespace, app, level, cluster. Parse detailed fields at query time with LogQL json parsers or log line filters."
---

`kubectl logs` does not scale past three replicas and two namespaces. We had twenty-seven production pods and still spent twenty minutes grepping during an incident. **Grafana Loki** plus **Fluent Bit** gave one query surface—`{namespace="checkout"} |= "timeout"`—with labels aligned to our Prometheus metrics.

**Loki** aggregates logs cheaply by indexing metadata. **Fluent Bit** ships logs from every node to Loki with Kubernetes metadata attached.

## Architecture

```
Pod stdout/stderr → container runtime → /var/log/containers/*.log
    → Fluent Bit DaemonSet → Loki ingester → object storage (S3/GCS)
    → Grafana LogQL queries
```

Optional: OpenTelemetry Collector instead of Fluent Bit for unified traces/metrics/logs.

## Deploy Loki (Helm)

```bash
helm install loki grafana/loki-stack \
  --namespace observability \
  --set grafana.enabled=true \
  --set loki.persistence.enabled=true \
  --set loki.config.storage_config.aws.s3.bucket=loki-chunks
```

Production uses **Loki microservices** or **Simple Scalable** mode with S3/GCS backend—not single-binary persistence on cluster disk.

## Fluent Bit DaemonSet config

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit
  namespace: observability
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush        1
        Log_Level    info

    [INPUT]
        Name              tail
        Path              /var/log/containers/*.log
        Parser            docker
        Tag               kube.*
        Mem_Buf_Limit     50MB
        Skip_Long_Lines   On

    [FILTER]
        Name                kubernetes
        Match               kube.*
        Kube_URL            https://kubernetes.default.svc:443
        Merge_Log           On
        Keep_Log            Off
        K8S-Logging.Parser  On
        Labels              On

    [OUTPUT]
        Name            loki
        Match           *
        Host            loki-gateway.observability.svc
        Port            80
        Labels          job=fluentbit, cluster=prod
        Label_Keys      $kubernetes['namespace_name'],$kubernetes['labels']['app']
        Remove_Keys     kubernetes,stream
```

Map only low-cardinality keys to Loki labels—`namespace`, `app`, `container`.

## LogQL queries

```logql
{namespace="checkout", app="api"} |= "error" != "healthcheck"
```

Rate of errors:

```logql
sum(rate({app="api"} |= "ERROR" [5m])) by (namespace)
```

JSON parsing at query time:

```logql
{app="api"} | json | status >= 500 | line_format "{{.method}} {{.path}}"
```

## Retention and limits

Configure `table_manager` / compactor retention per tenant—30 days hot, S3 lifecycle for cold.

Set ingestion limits (`ingestion_rate_mb`, `per_stream_rate_limit`) so one noisy pod cannot deny others.

## Structured logging from apps

Log JSON to stdout—Fluent Bit parses once:

```kotlin
logger.info("""{"event":"payment_failed","orderId":"$id","code":402}""")
```

Avoid putting `orderId` in Loki labels—query with `| json | orderId="123"`.

## Correlation with traces

Include `trace_id` in log lines, not labels. Grafana links logs to Tempo traces when trace ID is parseable.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing logs | Check Fluent Bit RBAC, path mounts |
| Query timeout | Reduce time range; fix cardinality |
| Duplicate lines | Merge_Log settings, container restart handling |
| Lag | Scale ingesters; check S3 write latency |

## Multi-line stack traces

Java/Kotlin stack traces break across lines—configure Fluent Bit multiline parser:

```ini
[FILTER]
    Name          multiline
    Match         kube.*
    multiline.parser java
```

Without multiline, Loki indexes each stack frame as separate log lines—queries miss context.

## Cost control

S3 storage for Loki chunks grows with label cardinality and retention. Run compactor with retention aligned to compliance minimum, not "forever because storage is cheap."


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Documentation your team should maintain

Maintain a one-page runbook link from your main service README: prerequisites, owner rotation, last drill date, and known sharp edges. Link to vendor docs in the Resources section below but capture org-specific decisions (CIDR ranges, cluster names, approval gates) in internal docs that stay current. New hires should deploy a safe canary within a week using only that runbook—if they cannot, the doc is incomplete.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Common questions from reviewers

Reviewers and auditors often ask whether this approach scales with team growth and whether it fails safely. Answer explicitly in your design doc: what happens when dependencies are down, when credentials expire, and when traffic doubles overnight. Prefer defaults that deny or degrade gracefully over defaults that fail open. Document known limits (throughput ceilings, supported versions, regions) in the same place operators look during incidents—avoid scattering critical constraints across Slack threads.


## Version and compatibility notes

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together.

## Resources

- [Grafana Loki documentation](https://grafana.com/docs/loki/latest/) — architecture and config
- [Fluent Bit Loki output](https://docs.fluentbit.io/manual/pipeline/outputs/loki) — plugin reference
- [LogQL query language](https://grafana.com/docs/loki/latest/query/) — functions and parsers
- [Loki label best practices](https://grafana.com/docs/loki/latest/get-started/labels/) — cardinality guidance
