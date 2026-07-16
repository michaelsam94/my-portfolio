---
title: "RBAC and Service Accounts"
slug: "kubernetes-rbac-service-accounts"
description: "Kubernetes RBAC and service accounts: Role vs ClusterRole, binding patterns, least privilege for apps, and avoiding default token automount pitfalls."
datePublished: "2026-03-09"
dateModified: "2026-03-09"
tags: ["Kubernetes", "DevOps"]
keywords: "Kubernetes RBAC, ServiceAccount, RoleBinding, least privilege, automountServiceAccountToken, IRSA"
faq:
  - q: "What is the difference between Role and ClusterRole?"
    a: "Role grants permissions within a namespace. ClusterRole grants cluster-wide permissions or namespace permissions when bound with RoleBinding to a specific namespace. Use Role for app workloads scoped to one namespace; ClusterRole for operators, nodes, and cluster-scoped resources."
  - q: "Should application pods use the default ServiceAccount?"
    a: "No. Create a dedicated ServiceAccount per application with minimal RBAC. Disable automount unless the pod calls Kubernetes API. Default ServiceAccount in namespace often has unnecessary token exposure and unclear ownership."
  - q: "How do cloud IAM roles integrate with Kubernetes service accounts?"
    a: "Workload Identity (GKE), IRSA (EKS), and Azure Workload Identity federate Kubernetes ServiceAccounts to cloud IAM roles via OIDC. Pods assume cloud permissions without static credentials in Secrets—preferred for S3, KMS, and database access."
---

A pod using the `default` ServiceAccount in `production` had a ClusterRoleBinding left from debugging—it could list Secrets cluster-wide. **RBAC** mistakes are silent until something exfiltrates credentials. Service accounts are identities for pods; **RoleBindings** attach permissions. Treat them like production IAM, not boilerplate YAML.

**RBAC** controls who can perform which actions on which resources. **ServiceAccounts** provide pod identity for in-cluster API access and cloud federation.

## Minimal Role for app reading ConfigMaps

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: checkout-api
  namespace: checkout
automountServiceAccountToken: false
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: checkout-api-config-reader
  namespace: checkout
rules:
  - apiGroups: [""]
    resources: ["configmaps"]
    resourceNames: ["checkout-api-config"]
    verbs: ["get", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: checkout-api-config-reader
  namespace: checkout
subjects:
  - kind: ServiceAccount
    name: checkout-api
    namespace: checkout
roleRef:
  kind: Role
  name: checkout-api-config-reader
  apiGroup: rbac.authorization.k8s.io
```

Pod spec:

```yaml
spec:
  serviceAccountName: checkout-api
  automountServiceAccountToken: true  # only if pod needs API access
```

If the app never calls API, keep `automountServiceAccountToken: false` on both SA and pod.

## ClusterRole for operators

Controllers watching cluster-scoped resources need ClusterRole + ClusterRoleBinding:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: backup-operator
rules:
  - apiGroups: ["storage.example.com"]
    resources: ["databasebackups"]
    verbs: ["get", "list", "watch", "update", "patch"]
  - apiGroups: ["batch"]
    resources: ["jobs"]
    verbs: ["create", "delete", "get", "list", "watch"]
```

Scope operator ServiceAccount to operator namespace in binding.

## Avoid dangerous permissions

Never grant to app ServiceAccounts:

- `secrets` list/watch cluster-wide
- `*` verbs on `*`
- `escalate`, `bind`, `impersonate`
- `nodes/proxy` unless node debugging tool

Use [RBAC lookup](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#command-line-utilities):

```bash
kubectl auth can-i list secrets --as=system:serviceaccount:checkout:checkout-api -n checkout
```

## IRSA on EKS (example)

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: checkout-api
  namespace: checkout
  annotations:
    eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/checkout-api-s3-read
```

Trust policy maps OIDC subject `system:serviceaccount:checkout:checkout-api`. Pod uses AWS SDK default chain—no keys in env.

Similar patterns: GKE Workload Identity, Azure Workload Identity.

## User access vs pod RBAC

Human access via OIDC groups bound to ClusterRoles:

```yaml
subjects:
  - kind: Group
    name: platform-admins
    apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: admin
```

Separate break-glass cluster-admin from daily operator roles.

## Audit and hygiene

- Regularly review RoleBindings with [rbac-lookup tools](https://github.com/cyberark/kube-bench) or policy scanners
- Remove unused ServiceAccounts
- Namespace owners own their RBAC manifests in Git
- Enable audit logging for RBAC denial and secret access

## Token projection (bound tokens)

Legacy long-lived tokens in Secrets deprecated. Use **TokenRequest** projection:

```yaml
volumes:
  - name: k8s-api-token
    projected:
      sources:
        - serviceAccountToken:
            path: token
            expirationSeconds: 3600
            audience: api
```

Short-lived, audience-bound tokens reduce blast radius.

## Impersonation for break-glass

Cluster admins debugging as a ServiceAccount:

```bash
kubectl auth can-i list pods --as=system:serviceaccount:checkout:checkout-api -n checkout
```

Run before deploy when tightening RBAC—catches missing permissions in staging.

## Namespace-scoped operators

Operators in `operators` namespace watching CRs cluster-wide need ClusterRole—but bind to operator SA only, not default SA in app namespaces.


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

- [Kubernetes RBAC documentation](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) — authorization overview
- [ServiceAccount documentation](https://kubernetes.io/docs/concepts/security/service-accounts/) — pod identity
- [EKS IAM Roles for Service Accounts](https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html) — IRSA setup
- [GKE Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity) — GCP federation
