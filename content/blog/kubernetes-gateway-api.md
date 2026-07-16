---
title: "The Kubernetes Gateway API"
slug: "kubernetes-gateway-api"
description: "Route traffic with the Kubernetes Gateway API: GatewayClass, HTTPRoute, TLS, and how it improves on Ingress for multi-team clusters."
datePublished: "2026-01-24"
dateModified: "2026-01-24"
tags: ["Kubernetes", "DevOps"]
keywords: "Gateway API, HTTPRoute, GatewayClass, Kubernetes ingress, GKE Gateway, Envoy Gateway"
faq:
  - q: "Should new clusters use Gateway API instead of Ingress?"
    a: "For greenfield projects on supported clusters, yes—Gateway API is the successor model with role-oriented resources and richer routing. Ingress remains viable where your controller and tooling already standardize on it. Many teams run both during migration."
  - q: "Who owns Gateway vs HTTPRoute resources?"
    a: "Platform teams typically manage Gateway and GatewayClass (infra, IPs, TLS certs). Application teams create HTTPRoute in their namespaces referencing a Gateway. RBAC separates concerns cleanly—unlike monolithic Ingress annotations owned by one team."
  - q: "Which controllers implement Gateway API?"
    a: "Envoy Gateway, Istio, Cilium, Kong, Traefik, and cloud implementations (GKE Gateway, AWS Gateway Controller) support varying feature sets. Check GA status for HTTPRoute, GRPCRoute, and TLSRoute on your chosen controller."
---

Ingress worked until the thirteenth annotation convention for canary weights. Platform and app teams shared one Ingress object; a typo in `nginx.ingress.kubernetes.io/canary-weight` sent 50% of production traffic to staging. **Gateway API** splits ownership: platform defines `Gateway`, apps attach `HTTPRoute`—typed fields instead of annotation archaeology.

The **Gateway API** is a Kubernetes SIG-Network project replacing Ingress with extensible, role-oriented resources. Expressive routing (header matches, weight splits, filters) lives in CRDs, not vendor-specific strings.

## Core resources

| Resource | Owner | Purpose |
|----------|-------|---------|
| GatewayClass | Platform | Select controller implementation |
| Gateway | Platform | Listen on ports, terminate TLS |
| HTTPRoute | App team | Route HTTP traffic to Services |
| ReferenceGrant | Platform | Allow cross-namespace backend refs |

Install CRDs and a controller (example: Envoy Gateway):

```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.0/standard-install.yaml
```

## Platform Gateway

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: external
  namespace: infra
spec:
  gatewayClassName: eg
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      hostname: "*.example.com"
      tls:
        mode: Terminate
        certificateRefs:
          - name: wildcard-example-com
            kind: Secret
```

Controller assigns external IP and programs data plane.

## Application HTTPRoute

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: checkout
  namespace: checkout
spec:
  parentRefs:
    - name: external
      namespace: infra
  hostnames:
    - "checkout.example.com"
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /api
      backendRefs:
        - name: checkout-api
          port: 8080
          weight: 100
    - matches:
        - headers:
            - name: x-canary
              value: "true"
      backendRefs:
        - name: checkout-api-canary
          port: 8080
          weight: 100
```

Header-based canary without custom annotations.

## Traffic splitting

```yaml
backendRefs:
  - name: checkout-api-v1
    port: 8080
    weight: 90
  - name: checkout-api-v2
    port: 8080
    weight: 10
```

Weights are relative within a rule—clearer than percentage annotations.

## Cross-namespace access

HTTPRoute in `checkout` referencing Gateway in `infra` requires Gateway to allow routes from that namespace (controller-specific policy). **ReferenceGrant** permits Service in another namespace as backend:

```yaml
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-checkout-to-shared-db
  namespace: shared
spec:
  from:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      namespace: checkout
  to:
    - group: ""
      kind: Service
```

## Migration from Ingress

1. Install Gateway API CRDs and controller
2. Create Gateway mirroring existing Ingress entrypoint
3. Convert Ingress rules to HTTPRoute (tools: ingress2gateway)
4. Dual-run with different hostnames, then cut DNS
5. Remove Ingress when parity verified

## Observability

Controllers expose metrics on programmed routes, listener status, and backend health. `kubectl describe httproute checkout` shows parent acceptance conditions—debug "route not attached" there first.

## GRPCRoute and TLSRoute

Gateway API v1 adds GRPCRoute for gRPC services—match on service/method instead of hacking HTTPRoute with protocol annotations. TLSRoute handles TCP/TLS passthrough for databases and legacy protocols Ingress cannot express cleanly.

Check your controller's supported route kinds before designing APIs around experimental resources.


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

- [Gateway API specification](https://gateway-api.sigs.k8s.io/) — official docs and concepts
- [Gateway API guides — getting started](https://gateway-api.sigs.k8s.io/guides/) — controller-specific tutorials
- [Envoy Gateway project](https://gateway.envoyproxy.io/) — reference implementation
- [ingress2gateway tool](https://github.com/kubernetes-sigs/ingress2gateway) — Ingress migration helper
