---
title: "Managing Secrets with External Secrets"
slug: "kubernetes-secrets-external-secrets"
description: "Sync Kubernetes secrets from vaults with External Secrets Operator: SecretStore, ExternalSecret, rotation, and avoiding plaintext secrets in Git."
datePublished: "2026-03-17"
dateModified: "2026-03-17"
tags: ["Kubernetes", "DevOps"]
keywords: "External Secrets Operator, ESO, SecretStore, AWS Secrets Manager, HashiCorp Vault, secret rotation"
faq:
  - q: "Why use External Secrets Operator instead of Sealed Secrets?"
    a: "Sealed Secrets encrypts Secret manifests for Git storage—secrets live in etcd after decryption. External Secrets Operator pulls from external vaults at runtime and refreshes on interval. Use Sealed Secrets for GitOps-native encrypted commits; ESO when source of truth is AWS/GCP/Vault already."
  - q: "How often does ESO refresh secrets from the provider?"
    a: "ExternalSecret spec refreshInterval defaults to 1h—configurable per resource. Shorter intervals increase API calls to the vault; longer intervals delay rotation propagation. Match interval to rotation SLA and provider rate limits."
  - q: "Are synced Kubernetes Secrets encrypted at rest?"
    a: "Depends on cluster configuration—enable etcd encryption at rest with KMS provider for defense in depth. ESO reduces plaintext secrets in Git but target Secrets still exist in etcd unless you use secretless patterns (CSI driver mounting vault directly)."
---

Database passwords in Git—base64 is not encryption—rotated quarterly with a runbook forty steps long. **External Secrets Operator (ESO)** pulls credentials from AWS Secrets Manager (or Vault, GCP Secret Manager) into Kubernetes Secrets on a schedule. Rotation happens in the vault; pods pick up new values on next sync or restart.

**ESO** bridges external secret stores and Kubernetes. **SecretStore** configures provider access; **ExternalSecret** defines what to fetch and where to write.

## Install ESO

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  --namespace external-secrets --create-namespace
```

## SecretStore with AWS (IRSA)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: aws-secrets
  namespace: checkout
spec:
  provider:
    aws:
      service: SecretsManager
      region: eu-west-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa
```

ServiceAccount annotated with IAM role allowing `secretsmanager:GetSecretValue` on specific ARNs.

## ExternalSecret

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: checkout-db-credentials
  namespace: checkout
spec:
  refreshInterval: 15m
  secretStoreRef:
    name: aws-secrets
    kind: SecretStore
  target:
    name: checkout-db-credentials
    creationPolicy: Owner
  data:
    - secretKey: username
      remoteRef:
        key: prod/checkout/database
        property: username
    - secretKey: password
      remoteRef:
        key: prod/checkout/database
        property: password
```

ESO creates/updates Secret `checkout-db-credentials` with keys `username` and `password`.

Deployment reference:

```yaml
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: checkout-db-credentials
        key: password
```

## Rotation

Rotate in AWS Secrets Manager with versioning. ESO syncs new values on `refreshInterval`. Apps must reload secrets—restart pods via Reloader or watch file mounts:

```yaml
metadata:
  annotations:
    secret.reloader.stakater.com/reload: checkout-db-credentials
```

Or use **CSI Secret Store driver** for mount-based rotation without full env restart where supported.

## ClusterSecretStore

Shared store across namespaces:

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-global
spec:
  provider:
    aws:
      service: SecretsManager
      region: eu-west-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets
            namespace: external-secrets
```

Reference from ExternalSecrets in any namespace with appropriate RBAC.

## Vault provider (brief)

```yaml
spec:
  provider:
    vault:
      server: https://vault.internal:8200
      path: secret
      version: v2
      auth:
        kubernetes:
          mountPath: kubernetes
          role: checkout
          serviceAccountRef:
            name: checkout-api
```

Vault Kubernetes auth binds SA to policy.

## Security practices

- Least-privilege IAM per namespace SecretStore
- Never commit ExternalSecret with embedded credentials—only remote refs
- Enable etcd encryption at rest
- Audit vault access logs correlated with ESO ServiceAccount
- Prefer workload identity over long-lived access keys in ClusterSecretStore

## ESO vs alternatives

| Tool | Pattern |
|------|---------|
| Sealed Secrets | Encrypted secrets in Git |
| SOPS | Mozilla SOPS encrypted YAML |
| Vault Agent Injector | Sidecar renders files |
| ESO | Pull sync to K8s Secret |

Many teams combine SOPS for config and ESO for dynamic credentials.

## Templating merged secrets

ExternalSecret `target.template` merges multiple remote keys into one Secret with custom structure—useful for connection strings:

```yaml
target:
  template:
    data:
      DATABASE_URL: "postgres://{{ .username }}:{{ .password }}@host/db"
```

Validate templates in CI—bad template syntax fails sync silently until pod crash loops.


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

- [External Secrets Operator documentation](https://external-secrets.io/latest/) — providers and CRDs
- [AWS Secrets Manager integration guide](https://external-secrets.io/latest/provider/aws-secrets-manager/) — IAM and examples
- [HashiCorp Vault provider](https://external-secrets.io/latest/provider/hashicorp-vault/) — auth methods
- [Kubernetes secrets encryption at rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/) — etcd KMS configuration
