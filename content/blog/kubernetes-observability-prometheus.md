---
title: "Monitoring Kubernetes with Prometheus"
slug: "kubernetes-observability-prometheus"
description: "Monitor Kubernetes with Prometheus: kube-prometheus-stack, ServiceMonitors, recording rules, alerting, and golden signals for clusters and apps."
datePublished: "2026-02-21"
dateModified: "2026-02-21"
tags: ["Kubernetes", "DevOps"]
keywords: "Prometheus, kube-prometheus-stack, ServiceMonitor, Kubernetes monitoring, PromQL, Grafana, alerting"
faq:
  - q: "What is the difference between Prometheus Operator and kube-prometheus-stack?"
    a: "Prometheus Operator is a controller managing Prometheus, Alertmanager, and ServiceMonitor CRDs. kube-prometheus-stack is a Helm chart bundling Operator plus default dashboards, rules, and exporters for Kubernetes infrastructure. Most clusters start with the stack, then customize."
  - q: "How do I scrape metrics from my application pods?"
    a: "Expose a /metrics endpoint in Prometheus format, add Service with port named or annotated for scrape, create ServiceMonitor CRD selecting that Service. Operator configures Prometheus scrape configs automatically—no manual prometheus.yml editing."
  - q: "What Kubernetes metrics should I alert on first?"
    a: "Node NotReady, persistent pod CrashLoopBackOff, deployment unavailable replicas, PVC nearly full, API server error rate, and workload SLO burn rates (latency, error ratio). Infrastructure alerts before custom app alerts."
---

The cluster "looked fine" on the cloud dashboard—nodes green, API responding. Meanwhile etcd latency crept up for six hours until deployments timed out. **Prometheus** on the cluster with kube-state-metrics and node-exporter would have fired `APIServerLatencyHigh` days earlier. Managed console UIs summarize billing; they do not replace workload-aware monitoring.

**Prometheus** pulls metrics from targets, stores time series, and evaluates alerting rules. On Kubernetes, **kube-prometheus-stack** deploys Prometheus Operator, Grafana, default scrape configs, and community dashboards.

## Install kube-prometheus-stack

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace observability --create-namespace \
  -f values.yaml
```

```yaml
# values.yaml excerpt
prometheus:
  prometheusSpec:
    retention: 15d
    storageSpec:
      volumeClaimTemplate:
        spec:
          accessModes: [ReadWriteOnce]
          resources:
            requests:
              storage: 100Gi
    externalLabels:
      cluster: prod-us-east
alertmanager:
  alertmanagerSpec:
    storage:
      volumeClaimTemplate:
        spec:
          resources:
            requests:
              storage: 10Gi
```

## ServiceMonitor for app metrics

App exposes metrics:

```kotlin
// Ktor with micrometer
install(MicrometerMetrics) {
    registry = PrometheusMeterRegistry(PrometheusConfig.DEFAULT)
}
routing {
    get("/metrics") {
        call.respondText(registry.scrape())
    }
}
```

Service and ServiceMonitor:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: checkout-api
  labels:
    app: checkout-api
spec:
  selector:
    app: checkout-api
  ports:
    - name: metrics
      port: 8080
      targetPort: 8080
---
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: checkout-api
  namespace: checkout
  labels:
    release: monitoring
spec:
  selector:
    matchLabels:
      app: checkout-api
  namespaceSelector:
    matchNames: [checkout]
  endpoints:
    - port: metrics
      path: /metrics
      interval: 30s
```

Helm release label `release: monitoring` must match Prometheus `serviceMonitorSelector`.

## Golden signals PromQL

**CPU saturation** (container):

```promql
sum(rate(container_cpu_usage_seconds_total{namespace="checkout"}[5m])) by (pod)
/
sum(kube_pod_container_resource_limits{resource="cpu", namespace="checkout"}) by (pod)
```

**Memory pressure**:

```promql
container_memory_working_set_bytes{namespace="checkout"}
/
kube_pod_container_resource_limits{resource="memory", namespace="checkout"}
```

**HTTP error rate** (with `http_requests_total` metric):

```promql
sum(rate(http_requests_total{status=~"5.."}[5m]))
/
sum(rate(http_requests_total[5m]))
```

## Recording rules

Precompute expensive queries:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: checkout-recording
  namespace: checkout
spec:
  groups:
    - name: checkout.rules
      rules:
        - record: checkout:http_requests:rate5m
          expr: sum(rate(http_requests_total{namespace="checkout"}[5m])) by (status)
```

Reference `checkout:http_requests:rate5m` in dashboards and alerts.

## Alerting

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: checkout-alerts
spec:
  groups:
    - name: checkout
      rules:
        - alert: CheckoutHighErrorRate
          expr: |
            sum(rate(http_requests_total{namespace="checkout",status=~"5.."}[5m]))
            /
            sum(rate(http_requests_total{namespace="checkout"}[5m])) > 0.05
          for: 10m
          labels:
            severity: page
          annotations:
            summary: "Checkout error rate above 5%"
```

Route via Alertmanager to PagerDuty/Slack with inhibition rules (suppress pod alert if node down).

## Grafana dashboards

Import community dashboards:

- **315** — Kubernetes cluster monitoring
- **6417** — Kubernetes pods
- **3662** — Prometheus 2.0 overview

Customize for your SLOs; link dashboards from alert annotations.

## Long-term storage

Prometheus local retention suits ops windows (15–30 days). Attach **Thanos** sidecar or **Cortex/Mimir** for multi-cluster historical query and compliance retention.

## kube-state-metrics vs node-exporter

**node-exporter** exposes hardware and OS metrics per node. **kube-state-metrics** watches API objects—Deployment replicas, Pod phase, PVC status. Alerting on `kube_deployment_status_replicas_unavailable` catches rollout failures node-exporter never sees.

## Cardinality budget

Avoid high-cardinality labels in app metrics (`user_id`, `request_id`). Prometheus scrapes explode; use logs or tracing for per-request detail.


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

- [kube-prometheus-stack chart](https://github.com/prometheus-community/helm-charts/tree/main/charts/kube-prometheus-stack) — Helm values reference
- [Prometheus Operator docs](https://prometheus-operator.dev/) — ServiceMonitor, PodMonitor CRDs
- [PromQL documentation](https://prometheus.io/docs/prometheus/latest/querying/basics/) — query language
- [Google SRE — four golden signals](https://sre.google/sre-book/monitoring-distributed-systems/) — latency, traffic, errors, saturation
