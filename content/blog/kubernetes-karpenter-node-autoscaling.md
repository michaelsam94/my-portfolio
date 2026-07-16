---
title: "Node Autoscaling with Karpenter"
slug: "kubernetes-karpenter-node-autoscaling"
description: "Autoscale Kubernetes nodes with Karpenter: NodePools, NodeClaims, consolidation, spot instances, and tuning for cost and scheduling latency."
datePublished: "2026-02-05"
dateModified: "2026-02-05"
tags: ["Kubernetes", "DevOps"]
keywords: "Karpenter, node autoscaling, NodePool, consolidation, spot instances, EKS, cluster autoscaler"
faq:
  - q: "How is Karpenter different from Cluster Autoscaler?"
    a: "Cluster Autoscaler scales fixed node groups—new nodes match predefined instance types and take ASG launch time. Karpenter provisions nodes directly from cloud APIs per pending pod requirements, picking instance type, zone, and capacity type (spot/on-demand) dynamically. Faster bin-packing and broader instance diversity."
  - q: "What triggers Karpenter to provision a node?"
    a: "Unschedulable pods—typically pending because of insufficient CPU, memory, GPU, or topology constraints—trigger Karpenter to evaluate NodePool limits and launch a matching NodeClaim. It does not wait for node group capacity; it creates nodes tailored to pod spec."
  - q: "Does Karpenter support spot instances safely?"
    a: "Yes, with disruption budgets, consolidation policies, and pod disruption tolerations. Mix on-demand for critical workloads via separate NodePools or requirements. Use topology spread and PDBs so spot interruption does not violate availability."
---

Cluster Autoscaler added a `m5.2xlarge` while our pod needed four CPUs and 8Gi—we paid for sixteen cores idle for twenty minutes. **Karpenter** launched a `c6i.xlarge` in under a minute, bin-packed pending pods, and consolidated away the half-empty node an hour later. That per-pod provisioning model is why many EKS teams switched.

**Karpenter** is a node lifecycle controller—not a pod autoscaler. It watches unschedulable pods and provisions right-sized nodes, then removes empty or underutilized nodes through **consolidation**.

## Install on EKS (overview)

```bash
helm install karpenter oci://public.ecr.aws/karpenter/karpenter \
  --namespace karpenter --create-namespace \
  --set settings.clusterName=my-cluster \
  --set serviceAccount.annotations."eks\.amazonaws\.com/role-arn"=$KARPENTER_IAM_ROLE_ARN
```

Karpenter needs IAM permissions to create EC2 instances, pass node role, and describe subnets/security groups.

## NodePool and EC2NodeClass

Modern Karpenter v1 API:

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: general
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: default
      requirements:
        - key: kubernetes.io/arch
          operator: In
          values: [amd64]
        - key: karpenter.sh/capacity-type
          operator: In
          values: [spot, on-demand]
        - key: node.kubernetes.io/instance-type
          operator: In
          values: [m6i.large, m6i.xlarge, c6i.large, c6i.xlarge]
      expireAfter: 720h
  limits:
    cpu: 1000
  disruption:
    consolidationPolicy: WhenEmptyOrUnderutilized
    consolidateAfter: 1m
```

```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: default
spec:
  amiSelectorTerms:
    - alias: al2023@latest
  role: KarpenterNodeRole
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: my-cluster
```

## Scheduling interaction

Pods with resource requests trigger provisioning. Missing requests cause Karpenter to guess poorly—always set requests.

Taints and tolerations isolate workloads:

```yaml
# NodePool template spec
taints:
  - key: workload
    value: batch
    effect: NoSchedule
```

Pods need matching tolerations and node affinity.

## Consolidation and cost

`consolidationPolicy: WhenEmptyOrUnderutilized` moves pods to fewer nodes and terminates extras. `consolidateAfter` prevents thrashing during rolling deploys.

Set NodePool `limits` to cap runaway spend—Karpenter stops provisioning at CPU/memory ceilings.

## Spot best practices

- Separate NodePools: `capacity-type=spot` for fault-tolerant jobs, on-demand for stateful
- Use `karpenter.sh/do-not-disrupt` annotation during critical migrations
- PDBs on every production Deployment
- Interruption handling via AWS Node Termination Handler or Karpenter native drift

## Observability

Metrics: `karpenter_nodes_created`, `karpenter_scheduling_duration`, pod scheduling latency. Alert on pending pods older than threshold with Karpenter logs showing provisioning errors (subnet exhaustion, IAM deny).

## vs Cluster Autoscaler

Keep Cluster Autoscaler if you have simple fixed node groups and no appetite for new tooling. Choose Karpenter when instance diversity, spot optimization, and faster scale-out matter.

## Over-provisioning with pause pods

Low-priority pause pods hold capacity for burst—Karpenter sees pending pause, keeps warm nodes. Delete pause on scale event; real pods schedule immediately.

## AMI drift

`amiSelectorTerms` with `@latest` alias picks new AMIs on reconcile—pin version in production, canary alias in staging.


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

Pin library and control-plane versions in production manifests; track upstream release notes quarterly. Run upgrade drills in non-production before bumping minor versions that touch serialization, auth, or CRD schemas. Keep a compatibility matrix in your internal wiki listing supported Kubernetes, broker, and SDK versions validated together. Re-run node provisioning load tests after every Karpenter minor upgrade.

## Resources

- [Karpenter documentation](https://karpenter.sh/docs/) — concepts and AWS provider
- [Karpenter NodePool API](https://karpenter.sh/docs/concepts/nodepools/) — requirements and limits
- [AWS EKS Karpenter guide](https://docs.aws.amazon.com/eks/latest/userguide/karpenter.html) — IAM and installation
- [Cluster Autoscaler comparison (AWS blog)](https://aws.amazon.com/blogs/containers/using-karpenter-with-amazon-eks/) — migration notes
