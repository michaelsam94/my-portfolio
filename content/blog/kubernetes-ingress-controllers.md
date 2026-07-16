---
title: "Choosing a Kubernetes Ingress"
slug: "kubernetes-ingress-controllers"
description: "Compare Kubernetes ingress controllers: NGINX, Traefik, HAProxy, cloud LBs, and Gateway API migration—selection criteria for production clusters."
datePublished: "2026-02-01"
dateModified: "2026-02-01"
tags: ["Kubernetes", "DevOps"]
keywords: "Ingress controller, NGINX Ingress, Traefik, AWS Load Balancer Controller, ingress selection, TLS termination"
faq:
  - q: "What does an Ingress controller actually do?"
    a: "Ingress resources define routing rules—host, path, TLS—but are inert without a controller. The controller watches Ingress objects and programs a data plane (NGINX, Envoy, cloud LB) to route external traffic to Services. Without a controller, kubectl apply ingress does nothing."
  - q: "Should I terminate TLS at the ingress controller or the cloud load balancer?"
    a: "Cloud LB termination offloads CPU and integrates with managed certificates (ACM, Google-managed certs). Ingress termination gives finer-grained per-host certs and mTLS options inside the cluster. Hybrid: LB terminates public TLS, ingress handles internal routing over HTTP or re-encrypts to pods."
  - q: "When should I skip Ingress and use a cloud LoadBalancer Service?"
    a: "Single-service exposure, TCP/UDP non-HTTP protocols, or extreme simplicity on managed Kubernetes often favor Service type LoadBalancer directly. Ingress adds value with many HTTP routes sharing one IP, path-based routing, and centralized TLS."
---

We picked the default ingress chart because it was first in the tutorial. Six months later we needed gRPC, connection draining during deploys, and WAF integration—the controller could not do two of three without forking annotations. **Ingress controller selection** is a long-lived platform bet; swapping controllers means reprogramming every route and retesting TLS.

An **Ingress** is an API; the **controller** is the implementation. Dozens exist—NGINX, Traefik, HAProxy, Kong, Istio, cloud-specific controllers. Criteria: protocol support, observability, upgrade path to Gateway API, and operational fit.

## Evaluation criteria

| Criterion | Questions to ask |
|-----------|------------------|
| Protocols | HTTP/2, gRPC, WebSocket, TCP passthrough? |
| TLS | cert-manager integration, mTLS to pods? |
| Performance | Throughput, latency, config reload behavior |
| Observability | Prometheus metrics, access logs, tracing |
| High availability | Multi-replica, leader election, graceful reload |
| Ecosystem | Gateway API support, WAF, rate limiting plugins |
| Operations | Upgrade cadence, CVE response, config validation |

## NGINX Ingress Controller

Most common self-managed choice. Mature annotation set, large community.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "10m"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  number: 8080
```

Pros: documentation, examples everywhere. Cons: annotation sprawl, reload behavior on large configs, Gateway API lag vs newer projects.

## Traefik

Native Let's Encrypt, dynamic config, Kubernetes CRD (IngressRoute) alongside standard Ingress.

Good for clusters wanting automatic certs and middleware chains (rate limit, auth) as CRDs.

Watch CRD vs Ingress portability if multi-cluster standards matter.

## Cloud-native controllers

**AWS Load Balancer Controller** creates ALB/NLB from Ingress or Gateway API—integrates ACM, WAF, shield.

**GKE Ingress** binds to Google Cloud HTTP(S) load balancers with global anycast IPs.

On managed cloud, default controllers reduce ops burden. Trade-off: cloud lock-in and LB cost per rule.

## HAProxy / Kong / Istio ingress

**HAProxy Ingress** — performance-focused, familiar to HAProxy admins.

**Kong** — API gateway features: plugins, consumer auth, analytics.

**Istio** — service mesh ingress gateway when you already run Istio for mTLS and traffic policy.

Avoid Istio ingress solely for simple HTTP if mesh overhead is not justified.

## IngressClass and multi-tenant clusters

```yaml
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: external-nginx
spec:
  controller: k8s.io/ingress-nginx
```

Teams reference `ingressClassName`—platform can run internal vs external controllers.

## Migration path to Gateway API

Prefer controllers with active Gateway API support (Envoy Gateway, Cilium, GKE Gateway). New routes as HTTPRoute; legacy Ingress during transition.

## Production checklist

- Run controller as Deployment with PDB and HPA if CPU-bound
- Separate internal and external ingress classes
- Integrate cert-manager for Let's Encrypt or private CA
- Set resource requests; ingress is on critical path
- Test config reload under load—some controllers drop connections on reload
- Document supported annotations—app teams will use them

## Proxy protocol and real client IP

Behind L4 load balancers, enable PROXY protocol or `X-Forwarded-For` trust only from LB IP ranges—otherwise clients spoof source IP in rate limiting rules.


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

- [Kubernetes Ingress documentation](https://kubernetes.io/docs/concepts/services-networking/ingress/) — API reference
- [ingress-nginx project](https://kubernetes.github.io/ingress-nginx/) — deployment and annotations
- [Traefik Kubernetes docs](https://doc.traefik.io/traefik/providers/kubernetes-ingress/) — Ingress and CRD providers
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/) — ALB/NLB integration
