---
title: "Predictive and Scheduled Autoscaling"
slug: "ops-autoscaling-predictive-scheduled"
description: "Go beyond CPU-based HPA: scheduled scaling for known traffic patterns, predictive autoscaling with metrics pipelines, and Karpenter capacity planning."
datePublished: "2025-12-26"
dateModified: "2026-07-17"
tags: ["DevOps", "Kubernetes", "Autoscaling", "SRE"]
keywords: "predictive autoscaling, scheduled scaling Kubernetes, HPA custom metrics, Karpenter scaling, capacity planning"
faq:
  - q: "When should you use scheduled scaling instead of reactive HPA?"
    a: "Use scheduled scaling when traffic follows predictable calendars — daily morning peaks, weekday business hours, or known marketing events. Scale up 15–30 minutes before the spike so cold pods pass readiness probes before users arrive. HPA alone reacts too late when pod startup takes 60+ seconds."
  - q: "How does predictive autoscaling differ from scheduled scaling?"
    a: "Scheduled scaling uses fixed cron rules you define. Predictive autoscaling uses historical metrics (often ML-based) to forecast demand and pre-scale. Predictive handles gradual drift and seasonal patterns; scheduled handles sharp, known events. Most teams use both."
  - q: "What metrics work best for custom HPA beyond CPU?"
    a: "Request rate (from ingress or service mesh), queue depth (SQS, Kafka lag), p95 latency, and concurrent connections predict load better than CPU on I/O-bound services. CPU HPA on Node.js APIs that spend 80% time waiting on Postgres is essentially random."
---

Every Black Friday we scaled the same way: watch Grafana, panic, manually bump HPA `maxReplicas`, watch node provisioning lag, lose money. Reactive autoscaling works when your pods start in five seconds and your traffic ramps gradually. Real workloads violate both assumptions.

Scheduled and predictive scaling aren't replacements for HPA — they're the layer that makes HPA usable under spiky, calendar-driven traffic.

## Reactive HPA's blind spots

Standard Horizontal Pod Autoscaler watches CPU or memory and adds pods when utilization crosses a threshold. Problems:

- **Cold start lag.** New pods need image pull, JVM warmup, DB connection pool init. Users hit errors during the 2–5 minute ramp.
- **CPU lies.** Event-loop services show low CPU at high RPS. Batch workers show high CPU while idle between jobs.
- **Scale-down too aggressive.** `behavior.scaleDown.stabilizationWindowSeconds` defaults can shrink capacity while queue depth is still elevated.

```yaml
# HPA with custom metric: requests per second
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 3
  maxReplicas: 50
  metrics:
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "100"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
```

Expose `http_requests_per_second` via Prometheus adapter or Datadog external metrics. It's more correlated with user pain than `container_cpu_usage_seconds_total`.

## Scheduled scaling with KEDA or CronHPA

For known patterns, cron-based scaling pre-warms capacity:

```yaml
# KEDA ScaledObject with cron trigger
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: api-cron-scaler
spec:
  scaleTargetRef:
    name: api
  minReplicaCount: 2
  maxReplicaCount: 50
  triggers:
    - type: cron
      metadata:
        timezone: America/New_York
        start: "0 8 * * 1-5"    # 8 AM weekdays
        end: "0 18 * * 1-5"     # 6 PM weekdays
        desiredReplicas: "20"
    - type: prometheus
      metadata:
        serverAddress: http://prometheus:9090
        query: sum(rate(http_requests_total[2m]))
        threshold: "5000"
```

During the cron window, minimum replicas sit at 20. Outside it, Prometheus-driven scaling takes over down to 2. The handoff matters — set cron `desiredReplicas` to your expected *floor* during peak hours, not the ceiling.

Legacy option: `kubernetes-cronhpa-controller` or patched deployments via GitOps cron jobs. KEDA consolidates cron + queue + prometheus triggers in one CRD; we standardized on it to reduce controller sprawl.

## Predictive scaling on AWS and GCP

**AWS Predictive Scaling (EC2 Auto Scaling Groups)** analyzes up to 14 days of CloudWatch metrics and forecasts capacity for the next 48 hours. Enable it on ASGs backing your EKS node groups or standalone EC2 fleets. It works best with consistent daily patterns; one-off launches need scheduled overrides.

**GCP Autoscaler predictive mode** (Preview as of 2025) uses similar historical analysis for MIGs. Pair with GKE cluster autoscaler for node-level prediction.

For Kubernetes workloads directly, commercial tools (Cast AI, Stormforge, Spot by NetApp) and open-source experiments (Prophet + custom controller) forecast replica counts from Prometheus history. The pattern:

1. Export 30–90 days of request-rate metrics
2. Train a time-series model per service (Prophet, ARIMA, or cloud ML)
3. Write predicted replica count to a ConfigMap or push to KEDA external scaler
4. Reconcile every 15 minutes; HPA handles fine-grained adjustments

We run a lightweight internal job: query Prometheus for same-day-last-week RPS, apply 1.2× safety factor, set `spec.replicas` floor via GitOps PR auto-merge. Crude predictive scaling that beat our ML pilot because it was explainable.

## Node-level scaling with Karpenter

Pod HPA is useless if nodes don't exist. Karpenter provisions nodes on pending pod schedule time:

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: default
spec:
  template:
    spec:
      requirements:
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["spot", "on-demand"]
      expireAfter: 720h
  limits:
    cpu: 1000
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
```

Schedule a `NodePool` minimum via `--min-values` workaround or run a low-priority pause pod during peak windows to hold warm capacity. Some teams maintain a "warm pool" Deployment at zero desired replicas with `priorityClassName: overprovision` — Karpenter keeps nodes ready.

## Operating the combined stack

Our production setup for a B2B SaaS API:

| Layer | Mechanism | Lead time |
|-------|-----------|-----------|
| Baseline | KEDA cron (weekday 8–18) | 30 min before |
| Forecast | Same-DOW Prometheus job | 15 min before |
| Reactive | HPA on RPS + latency | Real-time |
| Nodes | Karpenter + spot/on-demand mix | 60–90 sec |

Alert when scheduled floor + HPA max is insufficient — `sum(rate(http_requests_total))` exceeding capacity model by 20% triggers a page, not a user-visible outage.

Track cost separately. Scheduled scaling increases idle cost. Compare pre-warm spend against revenue lost during last year's incident. Our break-even was 12 minutes of downtime per month.

## Common production mistakes

Teams get autoscaling predictive scheduled wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of autoscaling predictive scheduled fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When autoscaling predictive scheduled misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Predictive scaling signals beyond CPU

CPU lags traffic for JVM/.NET cold pools. Feed autoscaler custom metrics:

- Request rate from ingress (requests/sec)
- Kafka consumer lag
- Scheduled events (Black Friday cron scales at T-60 min)

```yaml
# KEDA ScaledObject example pattern
triggers:
  - type: prometheus
    metadata:
      query: sum(rate(http_requests_total[2m]))
      threshold: "500"
  - type: cron
    metadata:
      timezone: America/New_York
      start: 0 8 * * *
      end: 0 22 * * *
      desiredReplicas: "20"
```

Combine predictive (schedule) + reactive (Prometheus) — schedule sets floor, reactive handles spikes above forecast.

## Over-provisioning cost guardrails

Predictive scaling saves latency but can leave idle nodes. Set `scaleDown` stabilization windows (5–15 min) and max node caps per pool. FinOps reviews monthly: compare predicted schedule vs actual traffic — adjust cron windows when marketing campaign dates shift.

## Cluster autoscaler interaction

HPA scales pods; CA scales nodes — lag between them causes pending pods. Set HPA scale-up behavior `stabilizationWindowSeconds: 0` but CA priority expander ensures node pool pre-warmed before cron spike.

## Idle scale-down guards

Minimum replicas per AZ for zone spread — don't scale to one pod globally if topologySpreadConstraints require per-zone presence.

## Load test validates cron schedule

Before Black Friday, replay last year traffic shape against scaled environment — cron pre-warm at T-60 min useless if HPA max lower than peak need.

## Resources

- [Kubernetes HPA v2 documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [KEDA scalers reference (cron, prometheus)](https://keda.sh/docs/latest/scalers/)
- [Karpenter node provisioning](https://karpenter.sh/docs/concepts/nodepools/)
- [AWS Predictive Scaling for EC2](https://docs.aws.amazon.com/autoscaling/ec2/userguide/ec2-auto-scaling-predictive-scaling.html)
- [Prometheus adapter for custom metrics API](https://github.com/kubernetes-sigs/prometheus-adapter)