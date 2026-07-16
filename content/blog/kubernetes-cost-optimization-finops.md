---
title: "Kubernetes Cost Optimization and FinOps"
slug: "kubernetes-cost-optimization-finops"
description: "A practical guide to Kubernetes cost optimization: rightsizing requests, autoscaling, spot capacity, and the FinOps habits that keep cloud bills down."
datePublished: "2026-06-27"
dateModified: "2026-06-27"
tags: ["Kubernetes", "FinOps", "Cloud Cost", "Platform Engineering"]
keywords: "Kubernetes cost, FinOps, cloud cost optimization, k8s rightsizing, cluster autoscaling, resource requests, spot instances"
faq:
  - q: "What is the biggest driver of wasted Kubernetes spend?"
    a: "Over-provisioned resource requests. Teams set CPU and memory requests far above what pods actually use, so the scheduler reserves capacity that sits idle. Rightsizing requests against real usage typically recovers 30-50% of node cost before you touch anything else."
  - q: "Should I use the Horizontal Pod Autoscaler or the Vertical Pod Autoscaler?"
    a: "Use both, for different things. HPA scales replica count for stateless workloads that get busier under load; VPA (or its recommendations) tunes per-pod requests toward real usage. Run VPA in recommendation mode first so it advises rather than evicts."
  - q: "Are spot instances safe for production on Kubernetes?"
    a: "Yes for interruptible, replicated workloads. Run stateless services and batch jobs on spot with a fallback node pool of on-demand capacity, spread across instance types and zones, and handle the two-minute termination notice with graceful draining."
---

The first time I looked closely at a Kubernetes bill, the cluster was running at about 18% CPU utilization and we were paying for the other 82%. Nothing was broken. Every pod was healthy, every dashboard was green. The money was leaking through resource requests that nobody had revisited since the services were first deployed. Kubernetes cost optimization almost always starts there — not with fancy autoscaling, but with the gap between what pods *request* and what they actually use.

FinOps is the discipline of closing that gap on purpose, continuously, with the people who spend the money in the loop. It isn't a one-off cleanup. It's a habit, and the habit is cheaper than the tooling.

## Requests and limits are the whole game

The scheduler places pods based on their **requests**, not their real usage. If a pod requests 1 CPU and 2Gi but uses 100m and 300Mi at peak, you've reserved ten times the CPU and six times the memory it needs. Multiply that across a few hundred pods and you're buying nodes to hold air.

Pull actual usage before you change anything. If you have Prometheus and the metrics adapter running:

```promql
# p95 CPU usage per pod over the last 7 days
quantile_over_time(0.95,
  sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="prod"}[5m]))[7d:5m]
)
```

Set requests near the p95 of real usage, not the peak-of-peaks. A useful rule of thumb I've settled on: **request the p95, don't set a CPU limit at all, and set a memory limit at roughly 1.5x the request.** CPU is compressible — a pod that wants more than its request just gets throttled, no crash. Memory is not — exceed the limit and the kernel OOM-kills you. So the failure modes are asymmetric, and your config should reflect that.

```yaml
resources:
  requests:
    cpu: 150m       # ~p95 observed
    memory: 384Mi
  limits:
    memory: 512Mi   # headroom before OOMKill; no cpu limit on purpose
```

The Vertical Pod Autoscaler's recommender is the fastest way to get these numbers at scale. Run it in `recommendationOnly` mode so it advises rather than evicts pods under you, then feed its recommendations into your manifests. Automatic VPA eviction in production is a good way to page yourself at 3am.

## Autoscale the pods, then autoscale the nodes

Once requests are honest, autoscaling actually works, because the signals mean something.

- **Horizontal Pod Autoscaler** scales replicas for stateless services. Scale on a real load signal — requests-per-second or queue depth via custom metrics — not just CPU, which lags and misrepresents I/O-bound work.
- **Cluster autoscaling** adds and removes nodes to fit the pods. Karpenter (on AWS) has largely replaced the older cluster-autoscaler for me because it provisions right-sized nodes directly from pending pods instead of scaling fixed node groups, and it consolidates underused nodes aggressively.

The consolidation part is where the money comes back. A cluster that scales up eagerly but never scales *down* is just a slower way to overspend. Set `consolidationPolicy: WhenEmptyOrUnderutilized` and let it bin-pack.

## Spot capacity, without the pager

Spot/preemptible instances are 60-90% cheaper and perfectly fine for anything replicated and interruptible. The trick is not betting the cluster on a single instance type in a single zone. Diversify across several instance families and all your AZs so a spot reclamation in one pool doesn't take out your whole capacity. Keep a small on-demand pool for the things that genuinely can't tolerate interruption — your ingress controllers, stateful leaders, anything holding a lease.

Handle the termination notice properly: honor `terminationGracePeriodSeconds`, drain connections, and make sure your `PodDisruptionBudget` prevents the autoscaler from evicting every replica at once. I've written before about why [designing for observability and SLOs](https://blog.michaelsam94.com/designing-for-observability-slos/) matters here — you need to *see* that spot churn isn't eating your error budget before you trust it with more traffic.

## FinOps is a feedback loop, not a dashboard

Tools like OpenCost or Kubecost break spend down by namespace, deployment, and label so cost stops being one opaque number. But allocation reporting only helps if the numbers land in front of the teams who create the cost.

What's actually worked on teams I've run:

| Practice | Cadence | Owner |
|---|---|---|
| Rightsizing review from VPA recs | Monthly | Service team |
| Idle/zombie resource sweep | Weekly | Platform |
| Namespace cost report in Slack | Weekly | Automated |
| Anomaly alert on daily spend delta | Real-time | Platform |
| Commitment/savings-plan review | Quarterly | Finance + Platform |

The anomaly alert earns its keep. A misconfigured `replicas: 200` or a runaway batch job shows up as a spend spike hours before it shows up on the monthly invoice, and catching it same-day is the difference between a shrug and an incident review.

Tag and label everything with an owner and a cost center from day one. Untagged spend is unassignable spend, and unassignable spend never gets cleaned up because it's nobody's problem.

## The unglamorous wins

Before you reach for anything clever, the boring stuff pays best: delete the `LoadBalancer` services fronting things that no longer get traffic, drop over-provisioned PersistentVolumes, expire old container images out of your registry, and check what your logging and metrics pipeline costs — I've seen observability bills quietly overtake compute. Bin-packing with the right node sizes and shutting down non-prod clusters overnight are each worth more than most micro-optimizations.

If you're standardizing this across teams, it belongs in your [platform engineering](https://blog.michaelsam94.com/platform-engineering-internal-developer-platform/) layer so good defaults ship with every new service instead of being rediscovered each quarter, and it pairs naturally with [GitOps](https://blog.michaelsam94.com/gitops-argocd-flux/) so cost-related config changes are reviewed and audited like any other.

## Where to start Monday

Pull a week of usage, set requests to p95, and turn on VPA recommendations. That alone typically recovers a third of the bill and costs you an afternoon. Then make cost visible per team and wire up a spend anomaly alert. Autoscaling, spot, and commitment planning come after — they're multipliers on an efficient cluster, and multipliers on a wasteful one just waste faster.

## Resources

- [Kubernetes documentation — Resource management for pods](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Karpenter — Kubernetes node autoscaling](https://karpenter.sh/docs/)
- [OpenCost — open source Kubernetes cost monitoring](https://www.opencost.io/docs/)
- [Kubernetes Vertical Pod Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler)
- [FinOps Foundation — Framework](https://www.finops.org/framework/)
- [AWS — Amazon EC2 Spot best practices](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/spot-best-practices.html)
