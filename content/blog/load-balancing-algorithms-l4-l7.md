---
title: "L4 vs L7 Load Balancing"
slug: "load-balancing-algorithms-l4-l7"
description: "Choose between L4 transport and L7 application load balancing: how each layer routes traffic, algorithm trade-offs, and when to combine both."
datePublished: "2025-04-18"
dateModified: "2025-04-18"
tags: ["OPS", "Networking", "Load Balancing", "Infrastructure"]
keywords: "L4 vs L7 load balancing, layer 4 load balancer, layer 7 application load balancer, nginx load balancing, HAProxy algorithms, round robin vs least connections"
faq:
  - q: "Should I use L4 or L7 load balancing for my API?"
    a: "Use L7 if you need path-based routing, header inspection, TLS termination with SNI, or HTTP-specific health checks. Use L4 when you need maximum throughput with minimal latency overhead — gaming servers, database proxies, or internal service mesh data planes. Many production setups use both: L4 for distribution, L7 for routing."
  - q: "What load balancing algorithm should I use?"
    a: "Round robin works for homogeneous backends with similar request costs. Least connections is better when request duration varies — long-polling, WebSocket, or LLM inference endpoints. Weighted round robin distributes traffic proportionally when backends have different capacity. Consistent hashing preserves session affinity without sticky sessions."
  - q: "Does load balancing add significant latency?"
    a: "L4 adds roughly 0.1–0.5ms per hop — it forwards packets without parsing content. L7 adds 1–5ms because it terminates TCP, parses HTTP, and makes routing decisions. For most web APIs this is negligible compared to application processing time. Profile your p99 before optimizing the load balancer."
---

Your API runs on four backend instances behind a load balancer. Users report intermittent 502 errors. One instance handles 80% of traffic while the others idle. WebSocket connections drop when you deploy because the load balancer routes the upgrade request to a different server than the one holding the TCP session.

The problem is usually not "load balancing is broken" — it is that you picked the wrong layer or the wrong algorithm for your traffic pattern. L4 and L7 load balancers make fundamentally different routing decisions, and the algorithm you choose determines whether traffic distributes evenly under real workloads.

## OSI layers: where routing happens

**Layer 4 (Transport):** routes based on IP address and port. The load balancer sees TCP/UDP packets but does not inspect HTTP content.

**Layer 7 (Application):** routes based on HTTP properties — URL path, headers, cookies, query parameters, method.

```
Client request: GET /api/v2/users HTTP/1.1
                Host: api.example.com

L4 sees:  TCP to 10.0.1.5:443          → forward to backend:8080
L7 sees:  GET /api/v2/users             → route to users-service-v2 pool
          Host: api.example.com          → match virtual host
          Authorization: Bearer ...      → optional auth routing
```

## L4 load balancing

L4 balancers operate on packets. They do not terminate HTTP — they forward TCP connections to backend servers.

**How it works:**

```
Client → L4 LB (VIP:443) → Backend A (10.0.1.10:8080)
                         → Backend B (10.0.1.11:8080)
                         → Backend C (10.0.1.12:8080)
```

**Modes:**

- **Direct routing (DR):** LB modifies the MAC address, backend responds directly to client. Fastest, but backends must accept traffic for the VIP.
- **NAT mode:** LB rewrites source/destination IP. Simpler setup, LB becomes a bottleneck.
- **Tunnel mode:** LB encapsulates packets. Used in cross-subnet deployments.

**Pros:**
- Extremely high throughput (millions of connections per second)
- Low latency (no HTTP parsing)
- Protocol-agnostic (TCP, UDP, MQTT, gRPC over TCP)

**Cons:**
- No path-based routing
- No TLS termination (unless using TLS passthrough with SNI)
- No HTTP health checks (TCP connect checks only)
- Sticky sessions require connection-level affinity

**Examples:** AWS Network Load Balancer (NLB), HAProxy in TCP mode, Linux IPVS, Cloudflare Spectrum.

## L7 load balancing

L7 balancers terminate the client connection, parse the HTTP request, and open a new connection to the selected backend.

```nginx
upstream api_v2 {
    least_conn;
    server 10.0.1.10:8080 weight=3;
    server 10.0.1.11:8080 weight=2;
    server 10.0.1.12:8080 weight=1;
}

server {
    listen 443 ssl;
    server_name api.example.com;

    location /api/v2/ {
        proxy_pass http://api_v2;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api/v1/ {
        proxy_pass http://api_v1_legacy;
    }
}
```

**Pros:**
- Path, header, and cookie-based routing
- TLS termination and certificate management
- HTTP health checks (GET /health → expect 200)
- Request/response modification (headers, redirects)
- Rate limiting and WAF integration

**Cons:**
- Higher latency (1–5ms per request)
- Lower max throughput than L4
- HTTP-specific (gRPC works, raw TCP does not)

**Examples:** AWS Application Load Balancer (ALB), nginx, HAProxy in HTTP mode, Envoy, Traefik.

## Load balancing algorithms

| Algorithm | How it works | Best for |
|-----------|-------------|----------|
| Round robin | Cycles through backends sequentially | Homogeneous backends, similar request costs |
| Weighted round robin | Round robin with capacity weights | Mixed backend sizes (m5.xlarge + m5.2xlarge) |
| Least connections | Routes to backend with fewest active connections | Variable request duration, WebSockets, LLM inference |
| IP hash | Hash client IP to backend | Session affinity without cookies |
| Consistent hash | Hash on a key (URL, header), minimal remapping on backend changes | Cache-heavy workloads, CDN origin |
| Random | Random backend selection | Simple, surprisingly effective at scale |
| Least response time | Routes to fastest-responding backend | Heterogeneous backend performance |

For LLM inference endpoints where requests take 2–30 seconds, **least connections** prevents the pile-up that round robin causes — a single slow request blocks a round-robin slot, but least connections routes around it.

## Health checks: the piece everyone gets wrong

A backend that fails silently — returns 200 on /health but 500 on actual requests — passes TCP health checks but fails users.

**L4 health check:** TCP connect to port. Fast, but only detects crashed processes.

**L7 health check:** HTTP GET to a health endpoint with expected status code and optional body validation.

```yaml
# HAProxy backend health check
backend api_servers
    option httpchk GET /health
    http-check expect status 200
    server api1 10.0.1.10:8080 check inter 5s fall 3 rise 2
    server api2 10.0.1.11:8080 check inter 5s fall 3 rise 2
```

Configure `fall` (consecutive failures before marking down) and `rise` (consecutive successes before marking up) to avoid flapping. A backend that fails 3 checks over 15 seconds goes out of rotation; it needs 2 successes to return.

## Combining L4 and L7

Production setups often stack both:

```
Internet → L4 LB (NLB) → L7 LB (nginx/ALB) → Backend pods
           distributes    routes by path
           across AZs     terminates TLS
```

- L4 handles cross-AZ distribution and DDoS absorption.
- L7 handles routing, TLS, and HTTP-specific logic.
- Backend pods see clean HTTP from the L7 layer.

For Kubernetes, the Ingress controller (L7) sits behind a cloud LB (L4):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
spec:
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /api/v2
            pathType: Prefix
            backend:
              service:
                name: api-v2
                port:
                  number: 8080
```

## Resources

- [HAProxy configuration manual](https://docs.haproxy.org/)
- [nginx load balancing documentation](https://nginx.org/en/docs/http/load_balancing.html)
- [AWS ELB comparison (NLB vs ALB vs CLB)](https://docs.aws.amazon.com/elasticloadbalancing/latest/userguide/how-elastic-load-balancing-works.html)
- [Envoy proxy load balancing policies](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/upstream/load_balancing/load_balancing)
- [Google Cloud load balancing overview](https://cloud.google.com/load-balancing/docs/load-balancing-overview)
