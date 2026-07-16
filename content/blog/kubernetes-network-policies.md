---
title: "Locking Down Traffic with Network Policies"
slug: "kubernetes-network-policies"
description: "Secure Kubernetes with NetworkPolicy: default deny, namespace isolation, DNS egress, and CNI requirements for zero-trust pod networking."
datePublished: "2026-02-17"
dateModified: "2026-02-17"
tags: ["Kubernetes", "DevOps"]
keywords: "NetworkPolicy, Kubernetes security, default deny, CNI, Calico, Cilium, pod network isolation"
faq:
  - q: "Do NetworkPolicies work on every Kubernetes cluster?"
    a: "Only if your CNI supports NetworkPolicy—Calico, Cilium, Weave Net do; basic kubenet and some managed defaults do not. Verify before relying on policies for compliance. Without enforcement, NetworkPolicy objects are documentation only."
  - q: "What happens when I apply a default deny policy?"
    a: "Pods matching the policy selector lose all traffic not explicitly allowed by other NetworkPolicies. Always allow DNS egress (kube-dns/CoreDNS on UDP/TCP 53) and health check paths before enforcing deny-all, or workloads fail mysteriously."
  - q: "Can NetworkPolicies replace a service mesh for security?"
    a: "NetworkPolicies enforce L3/L4—IP, port, namespace labels. They cannot inspect HTTP headers or JWTs. Use policies for baseline segmentation; add mesh or ingress auth for L7 controls. Together they complement each other."
---

A compromised pod in staging scanned the entire cluster—Redis in production, metadata API, neighbor namespaces—because every pod could talk to every pod. **NetworkPolicies** won't stop determined lateral movement alone, but default-deny plus explicit allow rules cut reachable targets from "everything" to "my Service and DNS."

**NetworkPolicy** is Kubernetes' declarative firewall for pods. It selects pods and defines allowed ingress and egress by label, namespace, IP block, and port.

## Default deny baseline

Deny all ingress in namespace `checkout`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: checkout
spec:
  podSelector: {}
  policyTypes:
    - Ingress
```

`podSelector: {}` matches all pods in namespace. Without allow policies, nothing receives inbound connections.

Egress deny (optional, stricter):

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-egress
  namespace: checkout
spec:
  podSelector: {}
  policyTypes:
    - Egress
```

## Allow ingress from ingress controller

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-ingress-to-api
  namespace: checkout
spec:
  podSelector:
    matchLabels:
      app: checkout-api
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
          podSelector:
            matchLabels:
              app.kubernetes.io/name: ingress-nginx
      ports:
        - protocol: TCP
          port: 8080
```

Label the ingress namespace consistently—policies reference labels, not names alone.

## Allow egress to database namespace

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-to-postgres
  namespace: checkout
spec:
  podSelector:
    matchLabels:
      app: checkout-api
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: data
          podSelector:
            matchLabels:
              app: postgres
      ports:
        - protocol: TCP
          port: 5432
```

## DNS egress (required)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns
  namespace: checkout
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
```

Without this, pods cannot resolve external hostnames.

## Cross-namespace patterns

Use namespace labels:

```yaml
metadata:
  labels:
    tier: frontend
    env: production
```

Reference with `namespaceSelector` and `podSelector` together for precise rules.

For external SaaS APIs, allow egress to `ipBlock` CIDRs or `0.0.0.0/0` on 443 from specific pods—narrower than namespace-wide open egress.

## Testing policies

```bash
kubectl run tmp -n checkout --rm -it --image=nicolaka/netshoot -- bash
curl http://checkout-api:8080/health
nc -zv postgres.data.svc 5432
```

Cilium provides `cilium connectivity test` and policy verdict logs. Calico logs denied flows in Felix.

## Rollout strategy

1. Audit current traffic with CNI flow logs (monitor mode)
2. Apply allow policies mirroring observed flows
3. Apply default deny
4. Fix breakages from denied flows
5. Alert on anomalous deny rates

Do not big-bang production without staging rehearsal.

## Limits

- No HTTP path or method filtering
- No authentication
- Performance impact usually minimal; verify on high-throughput CNI

Combine with RBAC, Pod Security Standards, and secrets management for defense in depth.

## Host network pods

Pods with `hostNetwork: true` bypass normal pod network namespace—NetworkPolicy may not apply. Isolate hostNetwork workloads to dedicated nodes with taints.

## Service mesh interaction

Istio/Linkerd add sidecar identities—policies may need to allow proxy ports. Test with mesh enabled before enforcing egress deny.


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

- [Kubernetes NetworkPolicy documentation](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — API reference
- [Calico network policy tutorial](https://docs.tigera.io/calico/latest/network-policy/get-started/kubernetes-policy/kubernetes-network-policy) — examples and enforcement
- [Cilium network policy guide](https://docs.cilium.io/en/stable/security/policy/) — L3/L4/L7 policies
- [Kubernetes hardening guide — network segmentation](https://kubernetes.io/docs/concepts/security/security-checklist/) — official checklist
