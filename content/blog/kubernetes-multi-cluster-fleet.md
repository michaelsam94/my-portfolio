---
title: "Managing Multi-Cluster Fleets"
slug: "kubernetes-multi-cluster-fleet"
description: "Operate Kubernetes multi-cluster fleets: hierarchy, GitOps, cluster API, policy propagation, and observability patterns for platform teams."
datePublished: "2026-02-13"
dateModified: "2026-02-13"
tags: ["Kubernetes", "DevOps"]
keywords: "multi-cluster Kubernetes, fleet management, Cluster API, GitOps, Anthos, Rancher Fleet, policy propagation"
faq:
  - q: "When do I need multiple Kubernetes clusters instead of one large cluster?"
    a: "Separate clusters for blast radius, regulatory boundaries, region latency, environment isolation (prod vs nonprod), and team autonomy. One mega-cluster simplifies ops until a control plane outage or misconfigured ClusterRole affects everyone."
  - q: "How do platform teams deploy the same app to many clusters?"
    a: "GitOps with ApplicationSets (Argo CD) or Flux templates that generate one Application per cluster from cluster generator. Central repo defines desired state; each cluster agent reconciles locally. Avoid kubectl scripts looping over kubeconfigs."
  - q: "What is Cluster API in fleet context?"
    a: "Cluster API (CAPI) declaratively manages cluster lifecycle—create, upgrade, scale node pools—across providers. Fleet platforms use CAPI to provision homogeneous clusters; GitOps layers deploy workloads onto those clusters."
---

One cluster, three regions, twelve teams worked until a cert-manager misconfiguration took every Ingress offline simultaneously. Splitting to a **fleet**—regional production clusters plus staging—contained the next incident to a single region. Multi-cluster adds operational overhead; it trades that for blast radius, compliance boundaries, and upgrade canaries.

**Multi-cluster fleet management** covers how you provision clusters, deploy consistently, enforce policy, and observe aggregate health without treating each kubeconfig as a snowflake.

## Fleet topology patterns

| Pattern | Use case |
|---------|----------|
| Hub-spoke | Central management cluster controls spokes |
| Environment-per-cluster | dev, staging, prod isolated |
| Region-per-cluster | Latency and data residency |
| Team-per-cluster | Hard multi-tenant isolation |

Document which pattern you use—hybrids confuse on-call.

## GitOps with ApplicationSet

Argo CD ApplicationSet generates per-cluster Applications:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: platform-addons
  namespace: argocd
spec:
  generators:
    - clusters:
        selector:
          matchLabels:
            env: production
  template:
    metadata:
      name: '{{name}}-cert-manager'
    spec:
      project: platform
      source:
        repoURL: https://github.com/org/platform-gitops
        path: addons/cert-manager
        helm:
          valueFiles:
            - values-{{metadata.labels.region}}.yaml
      destination:
        server: '{{server}}'
        namespace: cert-manager
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

Register clusters in Argo CD with labels (`region`, `env`). One commit rolls cert-manager everywhere matching selector.

## Policy propagation

**OPA Gatekeeper** or **Kyverno** policies live in a central repo, synced to each cluster via GitOps or tools like **Rancher Fleet**:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: require-requests-limits
spec:
  validationFailureAction: Enforce
  rules:
    - name: validate-resources
      match:
        any:
          - resources:
              kinds: [Pod]
      validate:
        message: "CPU and memory requests/limits required"
        pattern:
          spec:
            containers:
              - resources:
                  requests:
                    memory: "?*"
                    cpu: "?*"
                  limits:
                    memory: "?*"
                    cpu: "?*"
```

Test policies in staging fleet before enforce mode in production fleet.

## Cluster provisioning with Cluster API

```yaml
apiVersion: cluster.x-k8s.io/v1beta1
kind: Cluster
metadata:
  name: prod-eu-west
  namespace: fleet-system
spec:
  clusterNetwork:
    pods:
      cidrBlocks: [10.244.0.0/16]
  infrastructureRef:
    apiVersion: infrastructure.cluster.x-k8s.io/v1beta1
    kind: AWSCluster
    name: prod-eu-west
  controlPlaneRef:
    apiVersion: controlplane.cluster.x-k8s.io/v1beta1
    kind: KubeadmControlPlane
    name: prod-eu-west-control-plane
```

Upgrade Kubernetes version on fleet by bumping template on canary cluster first, validate, then roll.

## Observability across clusters

- **Thanos or Cortex** — federated Prometheus metrics with `cluster` external label
- **Grafana** — multi-cluster dashboards, datasource per cluster or unified
- **Loki** — `cluster` label on all log streams

Alert routing includes cluster identity in PagerDuty payload.

## Identity and access

Avoid long-lived kubeconfigs on laptops. Use:

- OIDC with short-lived tokens per cluster
- **Teleport**, **Boundary**, or cloud SSO integration
- RBAC templates applied via GitOps per cluster role

Central identity; local RBAC binding.

## Networking between clusters

**Submariner**, **Cilium Cluster Mesh**, or cloud VPN connect private services. Prefer public APIs with mTLS over flat pod networks unless low latency private mesh is required.

## Anti-patterns

- Snowflake clusters manually kubectl-patched
- Different ingress annotations per cluster without documentation
- Fleet-wide changes without canary cluster
- Ignoring control plane upgrade skew across fleet

## Fleet upgrade order

Upgrade control plane on staging fleet cluster first, validate add-ons (CNI, CSI, metrics), then canary production region, then remainder. Skipping staging fleet guarantees production surprise.

## Cost allocation

Tag clusters with `cost-center` labels; chargeback reports per fleet slice—multi-cluster without cost visibility breeds orphaned clusters.


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

- [Cluster API book](https://cluster-api.sigs.k8s.io/) — lifecycle management
- [Argo CD ApplicationSet](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/) — multi-cluster generators
- [Rancher Fleet documentation](https://fleet.rancher.io/) — bundle deployment to clusters
- [Google Anthos fleet concepts](https://cloud.google.com/anthos/multicluster-management/fleets) — enterprise fleet model reference
