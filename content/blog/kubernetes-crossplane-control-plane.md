---
title: "Infrastructure with Crossplane"
slug: "kubernetes-crossplane-control-plane"
description: "Manage cloud infrastructure with Crossplane on Kubernetes: Composite Resources, Compositions, providers, and GitOps patterns for platform teams."
datePublished: "2026-01-20"
dateModified: "2026-01-20"
tags: ["Kubernetes", "DevOps"]
keywords: "Crossplane, Composite Resource, Composition, XRD, cloud infrastructure, control plane, Upbound"
faq:
  - q: "How is Crossplane different from Terraform in a Kubernetes cluster?"
    a: "Crossplane represents infrastructure as Kubernetes CRDs reconciled by controllers—same reconciliation loop model as Deployments. Terraform runs plan/apply as jobs or CLI with separate state. Crossplane fits teams standardizing on kubectl, GitOps, and RBAC for infra; Terraform fits broad multi-cloud modules and mature provider ecosystems."
  - q: "What is a Composite Resource in Crossplane?"
    a: "An XRD defines your platform API—e.g., DatabaseInstance—with fields app teams need. A Composition templates how that CR maps to managed resources (RDS, VPC rules). Developers claim an XR; Crossplane materializes cloud objects from the Composition."
  - q: "Do I still need Terraform if I adopt Crossplane?"
    a: "Many organizations use both—Crossplane for app-adjacent dynamic infra inside clusters, Terraform for foundational networking and org-level landing zones. Evaluate overlap to avoid two sources of truth for the same bucket or database."
---

Platform engineers kept a spreadsheet of "who requested which RDS instance." Terraform lived in a repo app developers could not touch; tickets took days. **Crossplane** moved the contract onto the cluster: developers apply a `PostgreSQLInstance` CR with size and environment; a Composition creates AWS RDS, security groups, and secrets. The spreadsheet died.

Crossplane extends Kubernetes to manage external infrastructure. **Providers** talk to AWS, GCP, Azure; **Composite Resource Definitions (XRDs)** define your abstractions; **Compositions** wire abstractions to managed resources.

## Install Crossplane and provider

```bash
helm repo add crossplane-stable https://charts.crossplane.io/stable
helm install crossplane crossplane-stable/crossplane --namespace crossplane-system --create-namespace

kubectl apply -f provider-aws.yaml
```

```yaml
apiVersion: pkg.crossplane.io/v1
kind: Provider
metadata:
  name: provider-aws
spec:
  package: xpkg.upbound.io/upbound/provider-aws-s3:v1.14.0
```

Configure provider credentials via IRSA, workload identity, or `ProviderConfig` secret ref—never commit keys.

## Define a Composite Resource Definition

Platform team exposes simplified API:

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: CompositeResourceDefinition
metadata:
  name: xpostgresinstances.platform.example.com
spec:
  group: platform.example.com
  names:
    kind: XPostgreSQLInstance
    plural: xpostgresinstances
  claimNames:
    kind: PostgreSQLInstance
    plural: postgresinstances
  versions:
    - name: v1alpha1
      served: true
      referenceable: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                storageGB:
                  type: integer
                environment:
                  type: string
              required: [storageGB, environment]
```

## Composition maps to cloud resources

```yaml
apiVersion: apiextensions.crossplane.io/v1
kind: Composition
metadata:
  name: aws-postgres-standard
spec:
  compositeTypeRef:
    apiVersion: platform.example.com/v1alpha1
    kind: XPostgreSQLInstance
  resources:
    - name: rds
      base:
        apiVersion: rds.aws.upbound.io/v1beta1
        kind: Instance
        spec:
          forProvider:
            engine: postgres
            instanceClass: db.t3.micro
            allocatedStorage: 20
      patches:
        - fromFieldPath: spec.storageGB
          toFieldPath: spec.forProvider.allocatedStorage
```

## App team claim

```yaml
apiVersion: platform.example.com/v1alpha1
kind: PostgreSQLInstance
metadata:
  name: orders-db
  namespace: checkout
spec:
  storageGB: 50
  environment: production
  compositionSelector:
    matchLabels:
      provider: aws
```

Crossplane reconciles until RDS exists; status fields surface endpoint and readiness.

## GitOps integration

Store XRDs and Compositions in a platform repo; app teams commit Claims in app repos. Argo CD or Flux reconciles both. RBAC limits who can create Claims vs who can edit Compositions.

## Operations

- Watch `kubectl get managed` for stuck resources
- Enable drift detection policies—manual console edits fight controllers
- Version Compositions; migrate Claims with compatibility testing
- Monitor Crossplane pod memory—large compositions stress reconciliation

## When Crossplane fits

Good: internal platform APIs, self-service databases and buckets, Kubernetes-native teams.

Poor: one-off infra, teams without K8s ops maturity, need for Terraform module marketplace day one.

## Composition functions and patch-and-transform

Crossplane 1.14+ supports **Composition Functions** (pipeline mode) for logic that YAML patches express poorly—conditional resources, loops over parameters, validation. When a Composition grows past a few patches, refactor to a function written in Go or KCL rather than copy-pasting patch blocks. Functions run as separate pods; pin versions and test in staging like any controller upgrade.

Treat Compositions like Terraform modules: semver, changelog, and consumer Claims pinned to `compositionRevisionRef` when you need controlled rollouts.

## Day-2 operations and drift

Managed resources expose `Ready` conditions—watch `kubectl get managed -A` in your platform dashboard. Manual edits in the AWS console create drift; enable `managementPolicies` and deletion policies consciously. A Claim deleted with `deletionPolicy: Orphan` leaves cloud resources running—good for accidental protection, bad for cost leaks.

Run regular orphaned resource audits linking cloud tags `crossplane.io/claim-name` to actual Claims in etcd backups.

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

- [Crossplane documentation](https://docs.crossplane.io/latest/) — concepts and getting started
- [Upbound provider AWS](https://marketplace.upbound.io/providers/upbound/provider-aws/) — managed resource catalog
- [Crossplane Composition guide](https://docs.crossplane.io/latest/concepts/compositions/) — patches and functions
- [CNCF Crossplane project](https://www.crossplane.io/) — architecture and community
