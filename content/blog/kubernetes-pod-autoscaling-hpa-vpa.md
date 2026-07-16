---
title: "Autoscaling with HPA and VPA"
slug: "kubernetes-pod-autoscaling-hpa-vpa"
description: "Scale Kubernetes workloads with HPA and VPA: metrics sources, behavior tuning, vertical vs horizontal trade-offs, and running both safely."
datePublished: "2026-03-01"
dateModified: "2026-03-01"
tags: ["Kubernetes", "DevOps"]
keywords: "HPA, VPA, Horizontal Pod Autoscaler, Vertical Pod Autoscaler, Kubernetes autoscaling, custom metrics"
faq:
  - q: "Can I use HPA and VPA on the same Deployment?"
    a: "Historically they conflicted when both adjusted the same containers. Modern guidance: use VPA in recommendation-only mode with HPA, or HPA on custom/external metrics while VPA adjusts requests on Deployments without HPA. Never let both mutate pod spec simultaneously without careful configuration."
  - q: "What metrics can HPA use besides CPU?"
    a: "Memory, custom metrics from Prometheus adapter, external metrics (queue depth, cloud monitoring), and object metrics (Ingress requests per second). CPU remains default but application-specific metrics often scale better for IO-bound services."
  - q: "Does VPA restart pods when changing resources?"
    a: "Yes, in Auto mode VPA evicts pods to apply new requests/limits. Use updateMode Off for recommendations only, or Initial to set resources only at pod creation. Plan disruption budgets before enabling Auto on production."
---

Traffic spiked every weekday at nine; CPU stayed at forty percent while request latency doubled—threads blocked on JDBC pool size, not CPU. **HPA** on CPU added pods that contended for the same database. **VPA** recommendations showed requests set to 100m CPU but actual use at 800m; **HPA** on a custom `http_requests_in_flight` metric with right-sized requests from VPA fixed both problems.

Kubernetes offers **Horizontal Pod Autoscaler (HPA)** for replica count and **Vertical Pod Autoscaler (VPA)** for per-container CPU/memory requests. Node scaling (Cluster Autoscaler, Karpenter) sits below; these sit at the workload layer.

## HPA on CPU

Requires metrics-server:

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
```

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: checkout-api
  namespace: checkout
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: checkout-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Percent
          value: 10
          periodSeconds: 60
```

`behavior` prevents flapping—slow scale-down, cautious scale-up.

Ensure requests are set—HPA utilization is `usage/requests`, not limits.

## HPA on custom metrics

Prometheus adapter exposes metrics:

```yaml
metrics:
  - type: Pods
    pods:
      metric:
        name: http_requests_per_second
      target:
        type: AverageValue
        averageValue: "1000"
```

Install [prometheus-adapter](https://github.com/kubernetes-sigs/prometheus-adapter) with rules mapping PromQL to custom.metrics.k8s.io.

Queue depth via external metrics:

```yaml
  - type: External
    external:
      metric:
        name: sqs_queue_length
        selector:
          matchLabels:
            queue: orders
      target:
        type: AverageValue
        averageValue: "30"
```

## VPA installation and modes

```bash
kubectl apply -f https://github.com/kubernetes/autoscaler/releases/latest/download/vertical-pod-autoscaler-release.yaml
```

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: checkout-api-vpa
  namespace: checkout
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: checkout-api
  updatePolicy:
    updateMode: "Auto"  # Off | Initial | Recreate | Auto
  resourcePolicy:
    containerPolicies:
      - containerName: api
        minAllowed:
          cpu: 100m
          memory: 256Mi
        maxAllowed:
          cpu: 2
          memory: 2Gi
```

**Off** — recommendations only in VPA object status.

**Initial** — apply at pod creation.

**Auto** — evict and recreate pods with new resources (disruptive).

## Combined strategy

Recommended production pattern:

1. VPA in **Off** mode for two weeks—collect recommendations
2. Apply recommendations to Deployment requests manually or switch to **Initial**
3. HPA on CPU or custom metric for replica scaling
4. PDB ensures minimum availability during VPA evictions

Avoid HPA CPU + VPA Auto on identical Deployment without `resourcePolicy` exclusions—race conditions on pod spec.

## KEDA for event-driven scale

**KEDA** scales from zero based on Kafka lag, cron, Prometheus queries:

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: order-processor
spec:
  scaleTargetRef:
    name: order-processor
  minReplicaCount: 0
  maxReplicaCount: 50
  triggers:
    - type: kafka
      metadata:
        bootstrapServers: kafka:9092
        consumerGroup: order-processor
        topic: orders
        lagThreshold: "100"
```

Complements HPA for batch and queue workers.

## Observability

Alert on HPA hitting `maxReplicas`, VPA recommendations far above requests (cost risk), and scaling loop oscillation. Dashboard: desired vs current replicas, metric values, VPA recommendation vs actual.

## Cooldown during deploys

HPA may scale up during rolling update when old and new pods coexist briefly—raise `minReplicas` during deploy or use Flagger/Argo Rollouts for controlled traffic shift.

## Memory-based HPA caution

Memory utilization HPA lags JVM heap growth—custom metrics (GC pause, pool wait time) often scale better than raw memory percent.


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


## Resources

- [Horizontal Pod Autoscaler documentation](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/) — metrics and behavior API
- [Vertical Pod Autoscaler FAQ](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler/FAQ.md) — modes and HPA interaction
- [KEDA documentation](https://keda.sh/docs/) — event-driven autoscaling
- [Prometheus adapter setup](https://github.com/kubernetes-sigs/prometheus-adapter) — custom metrics for HPA
