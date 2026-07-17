---
title: "AI Agents: Gateway Api Ingress Evolution"
slug: "agent-gateway-api-ingress-evolution"
description: "Migrating agent workloads from Ingress to Gateway API — HTTPRoute, GRPCRoute, TLS termination, canary traffic splits, and platform-level rate limits for LLM inference endpoints."
datePublished: "2026-02-14"
dateModified: "2026-02-14"
tags: ["AI", "Agent", "Gateway"]
keywords: "Gateway API, Kubernetes ingress, HTTPRoute, GRPCRoute, agent inference, canary rollout, TLS termination, Envoy Gateway, NGINX migration"
faq:
  - q: "Why migrate agent inference ingress from classic Ingress to Gateway API?"
    a: "Gateway API separates infrastructure (GatewayClass, load balancer) from application routing (HTTPRoute), supports gRPC and WebSocket first-class, exposes portable traffic splitting for canaries, and replaces annotation soup with typed CRDs. Agent platforms mixing REST tools, streaming SSE, and gRPC embedders outgrow single-resource Ingress limitations."
  - q: "Can HTTPRoute do canary rollouts for a new agent orchestrator version?"
    a: "Yes. BackendRef weights or RequestMirror filters split traffic between stable and candidate Services. Pair with metric analysis (error rate, p95 latency, token throughput) before shifting weight to 100%. Gateway API's role-based visibility lets app teams own HTTPRoute while platform teams own Gateway."
  - q: "How do you handle long-lived SSE streams from agent chat through Gateway API?"
    a: "Configure appropriate idle timeouts on Gateway and backend Service — defaults often kill streams at 60s. Use HTTPRoute rules matching /v1/chat/completions or /agent/stream paths with backend policies extending timeout. Verify your implementation (Envoy Gateway, Istio, Cilium) documents streaming behavior; not all controllers treat SSE identically."
  - q: "What is the recommended coexistence strategy during Ingress to Gateway API migration?"
    a: "Run dual entry temporarily: existing Ingress handles legacy paths; new Gateway owns net-new hostnames or /v2 prefixes. Migrate route-by-route with DNS or path cutover, validate TLS cert propagation on Gateway listeners, then decommission Ingress controllers once HTTPRoute coverage matches. Never big-bang flip production agent traffic without weighted fallback."
---
Agent platforms outgrow `kubernetes.io/ingress.class` annotations the same way they outgrow single-model routing: one hostname initially serves a simple REST API, then adds streaming chat, gRPC embedding services, WebSocket tool bridges, admin dashboards, and per-tenant rate limits — each fighting for another NGINX snippet nobody remembers writing. **Gateway API** is the Kubernetes evolution of ingress: role-oriented resources, implementation-agnostic routing, and first-class traffic splitting. For teams running agent inference behind Kubernetes, the migration question is when, not if — and how to do it without dropping active SSE sessions mid-token.

Classic **Ingress** bundles listener config, routing rules, and TLS into one resource owned ambiguously by "whoever applied the YAML." Annotations differ per controller (NGINX, ALB, GCE). gRPC requires expert mode. Canary deploys mean duplicating Ingress resources or bolting on service mesh. Gateway API splits concerns: **GatewayClass** (platform), **Gateway** (cluster ops), **HTTPRoute** / **GRPCRoute** (application teams), **BackendTLSPolicy** (mTLS to upstream). Agent service owners publish routes; platform engineers operate the data plane.

## Resource model mapped to agent workloads

| Gateway API resource | Owner | Agent platform example |
|---------------------|-------|------------------------|
| GatewayClass | Platform | `envoy`, `aws-alb`, `gke-l7-global-external` |
| Gateway | Platform | Public LB for `api.agents.example.com` |
| HTTPRoute | App team | `/v1/agents/*` → orchestrator Service |
| GRPCRoute | App team | `embedder.v1.Embedder` → GPU embedder pods |
| ReferenceGrant | Platform | Allow HTTPRoute in ns `agents` to reference Gateway in ns `infra` |

An agent stack typically exposes:

- **Orchestrator REST + SSE** — chat completions, tool streaming
- **Webhook ingress** — Slack, Teams, email triggers
- **Internal gRPC** — low-latency embedder and reranker calls (sometimes behind same Gateway with internal listener)
- **Admin API** — separate HTTPRoute with IP allowlist or auth policy attachment

## Baseline Gateway and HTTPRoute for agent REST

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: agent-public
  namespace: infra
spec:
  gatewayClassName: envoy-gateway
  listeners:
    - name: https
      protocol: HTTPS
      port: 443
      hostname: api.agents.example.com
      tls:
        mode: Terminate
        certificateRefs:
          - name: agents-api-tls
            namespace: infra
---
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: agent-orchestrator
  namespace: agents
spec:
  parentRefs:
    - name: agent-public
      namespace: infra
  hostnames:
    - api.agents.example.com
  rules:
    - matches:
        - path:
            type: PathPrefix
            value: /v1/agents
      timeouts:
        request: 300s      # long agent turns; controller-specific field placement may vary
      backendRefs:
        - name: orchestrator-stable
          port: 8080
          weight: 90
        - name: orchestrator-canary
          port: 8080
          weight: 10
    - matches:
        - path:
            type: PathPrefix
            value: /v1/webhooks
      backendRefs:
        - name: webhook-handler
          port: 8080
```

Weights on `backendRefs` enable **canary agent releases** without a service mesh — though verify your Gateway controller implements weighted routing (Envoy Gateway yes; some cloud L7 load balancers map differently).

## GRPCRoute for embedder and reranker services

Agent retrieval stacks often gRPC-call embedders from the orchestrator inside the cluster, but edge gRPC matters when clients or sidecars call directly. GRPCRoute matches on service/method:

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GRPCRoute
metadata:
  name: embedder-route
  namespace: agents
spec:
  parentRefs:
    - name: agent-internal
      namespace: infra
  hostnames:
    - embedder.internal.agents.example.com
  rules:
    - matches:
        - method:
            service: embedder.v1.Embedder
            method: EmbedBatch
      backendRefs:
        - name: embedder-gpu
          port: 9090
```

HTTP/2 cleartext (h2c) versus TLS differs by implementation — prefer TLS for cross-namespace boundaries even "internal."

## TLS termination and mTLS to agent pods

Gateway terminates public TLS; **BackendTLSPolicy** (or equivalent policy attachment) configures upstream validation when agent pods expect mTLS or present their own certs:

```yaml
apiVersion: gateway.networking.k8s.io/v1alpha3
kind: BackendTLSPolicy
metadata:
  name: orchestrator-upstream-tls
  namespace: agents
spec:
  targetRefs:
    - group: ""
      kind: Service
      name: orchestrator-stable
  validation:
    caCertificateRefs:
      - name: internal-ca
        group: ""
        kind: ConfigMap
    hostname: orchestrator.agents.svc.cluster.local
```

Agent workloads processing PII benefit from encryption even inside the cluster — Gateway API policy attachments centralize that config instead of per-deployment sidecar annotations.

## Streaming, SSE, and WebSocket considerations

Agent chat UIs consume **Server-Sent Events** or WebSocket streams lasting minutes. Ingress controllers default **proxy-read-timeout** to 60 seconds — users see frozen tokens mid-sentence. Gateway implementations expose timeout configuration on HTTPRoute, Gateway, or policy CRDs depending on version.

Checklist for streaming routes:

- Extend idle/read timeout above max expected turn duration (often 120–300s; tool-heavy agents longer)
- Disable response buffering if controller supports it — buffering breaks SSE chunk delivery
- Confirm HTTP/1.1 keep-alive behavior for SSE; HTTP/2 multiplexing may differ
- Load-test concurrent long streams; connection limits hit before CPU on small Gateways

For **WebSocket tool bridges**, match `Upgrade` headers in HTTPRoute rules (implementation-specific) or use dedicated Gateway listener on port 443 with appropriate backend protocol.

## Rate limiting and WAF at the Gateway layer

Agent APIs are abuse magnets — prompt injection is app-layer, but credential stuffing and runaway automation hit ingress first. Attach rate-limit **Policy** (Gateway API inference extension ecosystem) or vendor-specific extensions at Gateway or HTTPRoute:

```yaml
# Conceptual — exact CRD varies by implementation (Envoy GlobalRateLimit, etc.)
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: BackendTrafficPolicy
metadata:
  name: agent-rate-limits
  namespace: agents
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      name: agent-orchestrator
  rateLimit:
    local:
      rules:
        - clientSelectors:
            - headers:
                - name: x-tenant-id
                  type: Distinct
          limit:
            requests: 120
            unit: Minute
```

Per-tenant limits using `x-tenant-id` header distinct counting align with agent plan tiers. Global IP limits catch unauthenticated webhook abuse on `/v1/webhooks`.

## Migration playbook from Ingress

A phased migration reduces risk for live agent sessions:

**Phase 1 — Install Gateway controller** alongside existing Ingress (Envoy Gateway, Istio, or cloud-managed). Create GatewayClass and Gateway; issue certs via cert-manager `Certificate` referenced by Gateway listener.

**Phase 2 — Dual publish** new hostname `api-v2.agents.example.com` on Gateway; keep legacy Ingress on `api.agents.example.com`. Internal dogfood on v2 hostname.

**Phase 3 — Path or weight cutover** — HTTPRoute mirrors Ingress paths. Shift DNS CNAME or use weighted DNS 90/10 between Ingress LB and Gateway LB. Monitor SSE disconnect rate and 5xx during shift.

**Phase 4 — Decommission Ingress** per route. Delete orphan annotations. Document GatewayClass as the only supported ingress pattern for new agent services.

Translate common NGINX Ingress annotations:

| Ingress annotation | Gateway API equivalent |
|--------------------|------------------------|
| `nginx.ingress.kubernetes.io/proxy-read-timeout` | HTTPRoute/Gateway timeout policy |
| `nginx.ingress.kubernetes.io/canary-weight` | backendRefs weights |
| `nginx.ingress.kubernetes.io/ssl-redirect` | HTTPRoute redirect filter or listener HTTP→HTTPS |
| `cert-manager.io/cluster-issuer` | Same Certificate ref on Gateway listener |

## Multi-cluster and multi-tenant Gateway patterns

Agent platforms spanning regions may deploy **Gateway per cluster** with Global Load Balancer anycast fronting — HTTPRoute definitions replicated via GitOps (Argo CD ApplicationSet). Tenant-specific subdomains (`tenant-a.api.agents.example.com`) route via additional HTTPRoute hostnames without separate Gateways.

**ReferenceGrant** enforces cross-namespace trust: orchestrator namespace references Gateway in infra namespace only when platform team grants it — prevents arbitrary teams attaching routes to public Gateways.

## Observability across Gateway and agent SLOs

Export Gateway metrics: request count, 4xx/5xx, upstream latency, active connections, stream duration. Correlate with agent orchestrator metrics (tokens/sec, tool errors) during canaries.

Distributed traces should propagate `traceparent` from Gateway through to LLM calls — some controllers support OpenTelemetry export natively. Without it, "latency at ingress" vs "latency in model" becomes guesswork during incidents.

Log access with `tenant_id`, `route_name`, `backend_ref`, `protocol` (SSE vs REST). Agent incidents often split blame between Gateway timeout misconfig and orchestrator deadlock — logs must distinguish.

## Testing before production cutover

Contract test HTTPRoute acceptance: apply to test cluster, curl all path prefixes, verify TLS chain, run k6 with SSE scenario measuring stream completeness. GRPCRoute: `grpcurl` EmbedBatch against canary weight.

Chaos: kill canary backend pods during weighted split — error budget should trip automated weight rollback if wired to Flagger or Argo Rollouts integration.

## Closing

Gateway API ingress evolution is how Kubernetes-native agent platforms graduate from annotation-driven Ingress to typed, portable routing with canaries, gRPC, and policy attachments. Migrate route-by-route, validate streaming timeouts against real agent turn durations, and keep Ingress alive until SSE disconnect metrics prove parity. The Gateway is the front door users hit; agent reliability starts at the listener timeout defaults nobody changed from 60 seconds.

## Resources

- [Kubernetes Gateway API Documentation](https://gateway-api.sigs.k8s.io/)
- [Envoy Gateway User Guide](https://gateway.envoyproxy.io/docs/)
- [Gateway API: HTTPRoute Specification](https://gateway-api.sigs.k8s.io/api-types/httproute/)
- [Flagger: Canary CRD with Gateway API](https://docs.flagger.app/tutorials/gateway-api-progressive-delivery)
- [cert-manager: Securing Gateway Resources](https://cert-manager.io/docs/usage/gateway/)
