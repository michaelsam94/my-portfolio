---
title: "Pod Security Standards"
slug: "kubernetes-pod-security-standards"
description: "Enforce Kubernetes Pod Security Standards: privileged, baseline, and restricted profiles, namespace labels, and migrating workloads without breaking production."
datePublished: "2026-03-05"
dateModified: "2026-03-05"
tags: ["Kubernetes", "DevOps"]
keywords: "Pod Security Standards, PSS, restricted profile, Pod Security Admission, PSA, namespace labels, securityContext"
faq:
  - q: "What replaced PodSecurityPolicy in Kubernetes?"
    a: "Pod Security Admission (PSA) built into Kubernetes 1.25+ enforces Pod Security Standards via namespace labels. PodSecurityPolicy was removed in 1.25. Migrate PSP rules to PSS profiles and namespace label configuration."
  - q: "What is the difference between baseline and restricted PSS?"
    a: "Baseline prevents known privilege escalations—hostPath, privileged containers, host namespaces. Restricted adds hardening: non-root users, dropped capabilities, read-only root filesystem, seccomp RuntimeDefault. Restricted breaks many legacy images without securityContext updates."
  - q: "How do I audit before enforcing restricted mode?"
    a: "Set pod-security.kubernetes.io/enforce=restricted to warn or audit mode first (enforce-version labels), or use warn/audit labels alongside enforce=privileged. Collect violation events from API audit logs and fix workloads before switching enforce label to restricted."
---

PodSecurityPolicy deletion left a gap teams filled with admission webhooks, OPA, and hope. **Pod Security Standards (PSS)** plus **Pod Security Admission** built into Kubernetes replace that with three clear profiles—**privileged**, **baseline**, **restricted**—applied per namespace via labels. No CRD installation required on modern clusters.

We flipped `restricted` on a namespace without audit mode; CI pods running as root failed instantly. The fix was not rolling back standards—it was adding `securityContext` to Deployments and running warn mode for two sprints first.

## The three profiles

| Profile | Intent |
|---------|--------|
| privileged | Unrestricted—system workloads only |
| baseline | Blocks known escalations, allows common patterns |
| restricted | Hardened pod spec, non-root, minimal caps |

Details in [Kubernetes PSS documentation](https://kubernetes.io/docs/concepts/security/pod-security-standards/).

## Namespace labels

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: checkout
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

- **enforce** — rejects violating pods
- **audit** — logs violations to audit log
- **warn** — kubectl warning to user

Start with `enforce: baseline` and `warn: restricted` during migration.

## Restricted-compliant Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: checkout-api
  namespace: checkout
spec:
  template:
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: ghcr.io/org/checkout-api:2.4.1
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsUser: 10001
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir: {}
```

Read-only root needs writable mounts for `/tmp`, cache dirs, or use emptyDir.

## Common violations and fixes

| Violation | Fix |
|-----------|-----|
| `runAsNonRoot` | Set `runAsUser` in Dockerfile and securityContext |
| Privileged container | Remove or isolate to privileged namespace |
| `hostPath` volumes | Use PVC or emptyDir |
| `capabilities.add NET_BIND_SERVICE` | Run on port >1024 or justify baseline namespace |
| Root filesystem writable | readOnlyRootFilesystem + tmp emptyDir |

## Namespace tiering

```
kube-system, monitoring     → privileged or baseline
production apps             → restricted
legacy batch                → baseline until remediated
```

Document exceptions with ticket references—do not leave baseline namespaces unowned.

## Checking compliance

```bash
kubectl label namespace checkout \
  pod-security.kubernetes.io/warn=restricted --overwrite

kubectl apply -f deployment.yaml
# Warning appears if non-compliant
```

Third-party tools: **Polaris**, **Kubescape** scan manifests against PSS before apply.

## Interaction with other admission

PSS runs as admission plugin order alongside ResourceQuota, NetworkPolicy does not affect PSA. Kyverno can mutate defaults (add securityContext) before PSA validates—useful for gradual rollout:

```yaml
apiVersion: kyverno.io/v1
kind: ClusterPolicy
metadata:
  name: add-default-securitycontext
spec:
  rules:
    - name: run-as-non-root
      match:
        any:
          - resources:
              kinds: [Pod]
      mutate:
        patchStrategicMerge:
          spec:
            securityContext:
              runAsNonRoot: true
```

## Migration runbook

1. Inventory namespaces and current pod specs
2. Enable warn/audit restricted cluster-wide
3. Fix workloads starting with stateless Deployments
4. Enforce baseline on all app namespaces
5. Enforce restricted on new namespaces immediately
6. Remediate legacy; isolate unblockable workloads to baseline namespace with review

## Windows nodes

PSS profiles differ on Windows—validate `securityContext.windowsOptions` separately. Linux restricted assumptions do not transfer.

## Init containers

Init containers must meet same profile as app containers— forgotten root init container blocks entire pod under restricted.


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

- [Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — profile requirements
- [Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) — label configuration
- [Migrate from PSP](https://kubernetes.io/docs/tasks/configure-pod-container/migrate-from-psp/) — official migration guide
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes) — broader hardening checklist
