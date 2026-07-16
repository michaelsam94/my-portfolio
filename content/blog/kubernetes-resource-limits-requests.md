---
title: "Getting Resource Limits Right"
slug: "kubernetes-resource-limits-requests"
description: "Set Kubernetes CPU and memory requests and limits correctly: QoS classes, LimitRange, VPA hints, OOM behavior, and avoiding throttling surprises."
datePublished: "2026-03-13"
dateModified: "2026-03-13"
tags: ["Kubernetes", "DevOps"]
keywords: "Kubernetes resource limits, requests, QoS, LimitRange, CPU throttling, OOMKilled, quality of service"
faq:
  - q: "What happens if I set limits without requests?"
    a: "Kubernetes sets requests equal to limits for CPU and memory when only limits are specified. Pods get Guaranteed QoS for those resources but scheduling uses the implicit requests—often over-provisioning cluster capacity. Explicit requests help the scheduler place pods correctly."
  - q: "Why is my pod OOMKilled despite low CPU usage?"
    a: "Memory limits are hard caps—exceeding working set triggers kernel OOM killer inside the cgroup. Java heap, buffer caches, and native leaks count. CPU throttling does not cause OOM; memory limits and application allocation patterns do."
  - q: "Should limits equal requests for production?"
    a: "Guaranteed QoS (limits = requests) protects latency-sensitive workloads from neighbor noise and reduces eviction priority. Burstable (requests < limits) allows burst CPU but risks throttling at limit. Pick Guaranteed for critical services; Burstable for batch with headroom."
---

Java service OOMKilled every Tuesday. Limits were 512Mi; heap was `-Xmx768m`. The container runtime did not care about JVM flags—it enforced cgroup memory. **Requests** tell the scheduler where to place pods; **limits** cap runtime usage. Getting both wrong wastes money or kills pods.

Kubernetes resource management separates **scheduling** (requests) from **enforcement** (limits). Understand QoS classes and what happens at the boundary.

## Requests vs limits

```yaml
resources:
  requests:
    cpu: 500m
    memory: 512Mi
  limits:
    cpu: "2"
    memory: 1Gi
```

- **CPU request** — guaranteed share; scheduler uses sum of requests per node
- **CPU limit** — CFS quota throttles usage beyond limit (Linux)
- **Memory request** — scheduling minimum
- **Memory limit** — hard cap; exceed → OOMKill

CPU is compressible (throttled). Memory is not (killed).

## QoS classes

| Class | Condition | Eviction priority |
|-------|-----------|-------------------|
| Guaranteed | limits = requests (all containers) | Last evicted |
| Burstable | requests set, limits differ or partial | Middle |
| BestEffort | no requests/limits | First evicted |

Production APIs should aim for **Guaranteed** on memory at minimum:

```yaml
resources:
  requests:
    memory: 1Gi
    cpu: 500m
  limits:
    memory: 1Gi
    cpu: 500m
```

## LimitRange defaults

Prevent BestEffort pods in namespace:

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: defaults
  namespace: checkout
spec:
  limits:
    - default:
        cpu: 500m
        memory: 512Mi
      defaultRequest:
        cpu: 200m
        memory: 256Mi
      max:
        cpu: "4"
        memory: 8Gi
      min:
        cpu: 50m
        memory: 64Mi
      type: Container
```

New containers without resources inherit defaults.

## ResourceQuota caps

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: checkout-quota
  namespace: checkout
spec:
  hard:
    requests.cpu: "20"
    requests.memory: 40Gi
    limits.cpu: "40"
    limits.memory: 80Gi
    pods: "50"
```

Stops one team from consuming cluster.

## Sizing workflow

1. Deploy with VPA **Off** or metrics-server historical usage
2. Set requests to p95 usage over 7 days
3. Set memory limit to request + headroom (20–30%) or equal for Guaranteed
4. Set CPU limit ≥ request if burst needed; equal for no burst
5. Load test and watch `container_cpu_cfs_throttled_seconds_total`

For JVM:

```
container memory limit ≥ heap + metaspace + threads + native + 25% buffer
```

Use `-XX:MaxRAMPercentage` with container-aware JVM.

## Debugging throttling and OOM

```bash
kubectl describe pod checkout-api-xyz | grep -A5 "Last State"
kubectl get events -n checkout --field-selector reason=OOMKilling
```

Prometheus:

```promql
rate(container_cpu_cfs_throttled_seconds_total{pod="checkout-api-xyz"}[5m])
```

High throttle → raise CPU limit or reduce work per thread.

## Vertical Pod Autoscaler hints

VPA recommendation object:

```bash
kubectl get vpa checkout-api-vpa -o yaml
```

Apply recommendations iteratively; do not copy blindly for Java without heap review.

## Common mistakes

| Mistake | Effect |
|---------|--------|
| No requests | BestEffort, random placement, first evicted |
| Memory limit too tight | OOMKill under load |
| CPU request = limit on IO-bound app | Unnecessary throttling if CPU unused |
| Identical limits for all envs | Staging wastes; prod starves |

Right-size per environment—staging requests can be half production.

## Node pressure and eviction behavior

When nodes fill, the kubelet evicts BestEffort pods first, then Burstable pods exceeding requests. Guaranteed pods survive until the node truly runs out of memory at the OS level—a misconfigured Guaranteed pod with a memory leak can take a node down. Monitor node-level `memory.available` and `node_pressure` conditions alongside per-pod metrics.

Cluster Autoscaler and Karpenter use **pod requests**, not limits, when deciding whether new nodes are needed. Under-requested Deployments cause scheduling hotspots; over-requested ones block bin-packing and waste capacity. Review quarterly: compare VPA recommendations, actual usage, and spend per namespace.

## CPU limits and latency-sensitive services

CPU throttling manifests as tail latency spikes without high CPU metrics—threads wait for CFS quota refresh. For latency-critical APIs, either set limit equal to request (no throttling ceiling) or omit CPU limit entirely while keeping requests for scheduling (controversial but common on GKE guidance for predictable latency). Document the choice in your platform runbook; mixed clusters need consistency per tier.

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


## Resources

- [Managing resources for containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) — official semantics
- [QoS classes documentation](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/) — eviction behavior
- [LimitRange API](https://kubernetes.io/docs/concepts/policy/limit-range/) — namespace defaults
- [VPA recommendations FAQ](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler/FAQ.md) — automated sizing input
