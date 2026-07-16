---
title: "API Gateway Patterns"
slug: "api-gateway-patterns"
description: "API gateway patterns for production: routing, authentication, rate limiting, BFF, and when a gateway helps vs when it becomes a bottleneck."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "Architecture", "API", "DevOps"]
keywords: "API gateway patterns, API gateway architecture, backend for frontend BFF, Kong API gateway, rate limiting gateway"
faq:
  - q: "What is an API gateway?"
    a: "An API gateway is a server that sits between clients and backend services, handling cross-cutting concerns: authentication, rate limiting, routing, request/response transformation, SSL termination, and logging. Clients talk to one endpoint; the gateway routes to the appropriate microservice."
  - q: "When do I need an API gateway?"
    a: "You need a gateway when you have multiple backend services that clients must access through a single entry point, when you want centralized auth/rate limiting without duplicating it in every service, or when you need request transformation between client and service formats. Skip it for monoliths or single-service APIs."
  - q: "What is the Backend-for-Frontend (BFF) pattern?"
    a: "BFF is a variant where you create separate gateway APIs tailored to each client type — mobile BFF, web BFF, partner BFF. Each BFF aggregates and shapes data for its client's needs. Mobile gets compact responses; web gets rich responses. BFFs prevent one generic API from serving all clients poorly."
---

An API gateway is the front door to your backend — and like a front door, it can either make everything smoother (centralized auth, clean routing, consistent logging) or become a bottleneck everyone queues behind. I've deployed gateways with Kong, AWS API Gateway, and custom Envoy configurations. The pattern works when it handles cross-cutting concerns that shouldn't be duplicated in every service. It fails when teams put business logic in the gateway, creating a distributed monolith that's harder to test than the services it fronts.

## Core responsibilities

```
Client → [SSL] → [Auth] → [Rate Limit] → [Route] → [Transform] → Service
                     ↓           ↓            ↓           ↓
                   Logs     Metrics      Tracing     Cache
```

| Concern | Gateway handles | Service handles |
|---------|----------------|-----------------|
| Authentication | Token validation | Business authorization |
| Rate limiting | Per-client quotas | Resource-specific limits |
| Routing | Path → service mapping | N/A |
| SSL/TLS | Termination | Internal mTLS |
| Logging/tracing | Access logs, request IDs | Business event logs |
| Response shaping | BFF aggregation | Domain logic |
| Caching | Public response cache | Data-level cache |

## Routing

Path-based routing to services:

```yaml
# Kong declarative config
services:
  - name: users-service
    url: http://users:8080
    routes:
      - name: users-route
        paths: ["/api/v1/users"]

  - name: orders-service
    url: http://orders:8080
    routes:
      - name: orders-route
        paths: ["/api/v1/orders"]
```

Clients see `api.example.com/api/v1/users` and `api.example.com/api/v1/orders`. Behind the gateway, these route to different services on different ports.

## Centralized authentication

Validate tokens once at the gateway, pass user context to services:

```
Client: Authorization: Bearer <jwt>
Gateway: validates JWT → extracts user_id, roles
Gateway → Service: X-User-Id: 123, X-User-Roles: admin,user
Service: trusts gateway headers (internal network only)
```

Services don't validate tokens — they trust the gateway's headers on the internal network. This eliminates duplicate auth code across services. For [JWT vs sessions](https://blog.michaelsam94.com/api-authentication-jwt-vs-sessions/) trade-offs, gateways work well with short-lived JWTs.

Critical: services must reject requests without gateway-injected headers from external sources. Use mTLS between gateway and services.

## Rate limiting

Per-client or per-API-key limits at the gateway:

```yaml
plugins:
  - name: rate-limiting
    config:
      minute: 100
      hour: 5000
      policy: local
      fault_tolerant: true
```

Gateway rate limiting is coarse (per client/API key). Service-level rate limiting handles resource-specific quotas (e.g., 10 exports per day per user). Use both layers — see [rate limiting algorithms](https://blog.michaelsam94.com/api-rate-limiting-algorithms/).

## BFF pattern

Separate gateways per client type:

```
Mobile App → Mobile BFF → [Users, Orders, Search]
Web App    → Web BFF    → [Users, Orders, Search, Analytics, Admin]
Partner    → Partner API → [Orders (limited)]
```

Mobile BFF returns compact responses:

```json
// Mobile BFF response
{"orders": [{"id": "4521", "status": "shipped", "eta": "Jan 18"}]}

// Web BFF response (same data, more fields)
{"orders": [{"id": "4521", "status": "shipped", "eta": "Jan 18", "items": [...], "tracking_url": "...", "invoice_pdf": "..."}]}
```

Each BFF aggregates calls to backend services and shapes the response for its client. Mobile gets one round-trip instead of three.

## When NOT to use a gateway

- **Monolith**: put auth/rate limiting in middleware, not a separate hop
- **Internal service-to-service**: use service mesh (Istio/Linkerd) for mTLS and observability
- **Business logic routing**: if routing depends on business rules, it belongs in a service
- **Early-stage startup**: a gateway adds operational complexity you don't need with one service

## Gateway as bottleneck

Mitigations:
- **Horizontal scaling**: gateways are stateless — run multiple instances behind a load balancer
- **Caching**: cache public GET responses at the gateway (CDN or gateway cache)
- **Async processing**: gateway returns 202, client polls — for long operations
- **Circuit breakers**: stop routing to unhealthy services — see [bulkhead pattern](https://blog.michaelsam94.com/backend-bulkhead-isolation-pattern/)

Monitor gateway latency separately from service latency. If p99 gateway overhead exceeds 10ms, investigate plugin chain length.

## AI/LLM gateway variant

The [AI gateway pattern](https://blog.michaelsam94.com/ai-gateway-llm-proxy/) applies the same principles to LLM APIs: centralized auth, rate limiting, cost tracking, and model routing behind one endpoint.

Configure gateway timeouts shorter than upstream service timeouts — clients receive 504 from gateway, not hung connections waiting for origin.

## Plugin chain ordering

Gateway middleware order matters:

```
1. Request ID / tracing
2. Authentication
3. Rate limiting
4. Request validation
5. Routing
6. Response transformation
7. Logging / metrics
```

Auth before rate limiting — otherwise unauthenticated traffic consumes rate limit budget. Rate limiting before routing — reject overload before backend selection.

## mTLS and zero-trust

Service mesh vs API gateway division:

| Concern | API Gateway | Service Mesh |
|---------|-------------|--------------|
| North-south traffic | Yes | Optional |
| East-west mTLS | No | Yes |
| External auth | Yes | Internal identity |
| Rate limiting | Per-client | Per-service |

Use gateway for external clients, mesh for internal service-to-service — avoid duplicating auth in both layers.

## Health checks and circuit breaking

```yaml
# Kong upstream health check
healthchecks:
  active:
    http_path: /health
    healthy:
      interval: 5
      successes: 2
    unhealthy:
      interval: 5
      http_failures: 3
```

Remove unhealthy upstreams from rotation automatically — manual failover during incidents wastes minutes.

Pair with [API rate limiting algorithms](https://blog.michaelsam94.com/api-rate-limiting-algorithms/) when implementing gateway-level throttling.

## Common production mistakes

Teams get gateway patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

API design for gateway patterns frustrates clients when pagination cursors expire silently, error bodies lack stable machine-readable codes, and rate limits return 429 without `Retry-After` headers.

## Resources

- [Kong Gateway documentation](https://docs.konghq.com/gateway/latest/)
- [AWS API Gateway developer guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [Envoy proxy documentation](https://www.envoyproxy.io/docs/envoy/latest/)
- [Microsoft Azure API Management patterns](https://learn.microsoft.com/en-us/azure/architecture/microservices/design/gateway)
- [Rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/)
