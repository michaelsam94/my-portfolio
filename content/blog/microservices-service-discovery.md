---
title: "Service Discovery Patterns"
slug: "microservices-service-discovery"
description: "How microservices find each other: client-side discovery, server-side discovery, DNS-based registration, and service mesh approaches."
datePublished: "2025-06-17"
dateModified: "2026-07-17"
tags:
keywords: "service discovery microservices, client side discovery, server side discovery, Consul service discovery, Kubernetes service discovery, Eureka service registry"
faq:
  - q: "Do I need a service registry if I use Kubernetes?"
    a: "Kubernetes provides DNS-based service discovery via ClusterIP Services — pods find each other at my-service.namespace.svc.cluster.local. You do not need Consul or Eureka inside Kubernetes for basic discovery. Add a service mesh (Istio, Linkerd) when you need traffic management, mTLS, or observability beyond what K8s Services provide."
  - q: "What is the difference between client-side and server-side discovery?"
    a: "Client-side discovery puts a registry client in each service — the client queries the registry and picks an instance to call directly. Server-side discovery routes through a load balancer that queries the registry — clients call a fixed address. Client-side is more efficient (no extra hop); server-side is simpler for clients."
  - q: "How do services register themselves?"
    a: "Self-registration: the service starts, registers with the registry, and sends heartbeats. Platform registration: Kubernetes, ECS, or Nomad automatically register services when pods/tasks start. Self-registration gives services more control; platform registration requires less application code."
---
Hardcoded service URLs break the moment you scale beyond one instance. `http://payment-service:8080` works in docker-compose with one container. It fails when payment-service has four replicas behind a load balancer, when it moves to a different host after a deploy, or when you split across availability zones.

Service discovery is how services find each other dynamically. A registry tracks which instances are healthy and where they live. Callers query the registry instead of configuration files.

## Client-side discovery

The calling service queries the registry and selects an instance:

```
Order Service → Registry: "where is Payment Service?"
              ← [10.0.1.10:8080, 10.0.1.11:8080, 10.0.1.12:8080]
              → 10.0.1.11:8080 (selected via load balancing)
```

```python
import consul

class ServiceDiscovery:
    def __init__(self, consul_host="consul:8500"):
        self.consul = consul.Consul(host=consul_host)

    def get_service_url(self, service_name: str) -> str:
        _, services = self.consul.health.service(service_name, passing=True)
        if not services:
            raise ServiceUnavailableError(f"No healthy instances of {service_name}")

        instance = self._select_instance(services)
        address = instance["Service"]["Address"]
        port = instance["Service"]["Port"]
        return f"http://{address}:{port}"

    def _select_instance(self, services):
        return random.choice(services)  # or round-robin, least-connections
```

**Pros:** no extra network hop, client controls load balancing algorithm.
**Cons:** registry client library in every service, clients must handle stale registry data.

## Server-side discovery

Clients call a fixed load balancer address; the LB queries the registry:

```
Order Service → Load Balancer (payment-service.internal)
              → Registry lookup
              → 10.0.1.11:8080
```

```python
# Client code is simple — just call the LB address
payment_url = "http://payment-service.internal/charge"
response = httpx.post(payment_url, json=order_data)
```

AWS ALB with ECS service discovery, nginx with Consul template, or Kubernetes Ingress all implement server-side discovery.

**Pros:** clients are simple, no registry library needed.
**Cons:** extra hop through LB, LB becomes a single point of failure (mitigated by HA).

## DNS-based discovery

The simplest approach — services register as DNS records:

```
payment-service.production.internal → 10.0.1.10
                                    → 10.0.1.11
                                    → 10.0.1.12
```

Kubernetes ClusterIP Services work this way:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: production
spec:
  selector:
    app: payment
  ports:
    - port: 8080
      targetPort: 8080
```

Any pod in the cluster reaches payment-service at `payment-service.production.svc.cluster.local:8080`. kube-proxy or iptables rules load-balance across matching pods.

## Self-registration with health checks

Services register on startup and deregister on shutdown:

```python
import consul, signal, sys

c = consul.Consul()
SERVICE_ID = f"payment-{hostname}-{port}"

def register():
    c.agent.service.register(
        name="payment-service",
        service_id=SERVICE_ID,
        address=hostname,
        port=port,
        check=consul.Check.http(f"http://{hostname}:{port}/health", interval="10s"),
    )

def deregister():
    c.agent.service.deregister(SERVICE_ID)

signal.signal(signal.SIGTERM, lambda *_: (deregister(), sys.exit(0)))
register()
```

Health checks ensure only healthy instances receive traffic. Failed checks remove the instance from the registry automatically.

## Service mesh discovery

Service meshes (Istio, Linkerd, Consul Connect) add a sidecar proxy to each pod that handles discovery, mTLS, retries, and traffic splitting:

```
Order Pod → Envoy Sidecar → Envoy Sidecar → Payment Pod
            (discovers via     (routes to
             control plane)     payment pod)
```

With Istio, no application code changes — the sidecar intercepts all traffic:

```yaml
apiVersion: networking.istio.io/v1
kind: VirtualService
metadata:
  name: payment-service
spec:
  hosts:
    - payment-service
  http:
    - route:
        - destination:
            host: payment-service
            subset: v2
          weight: 20
        - destination:
            host: payment-service
            subset: v1
          weight: 80
```

This enables canary deployments at the infrastructure level — 20% of traffic to v2, 80% to v1.

## Choosing a discovery pattern

| Environment | Recommended approach |
|------------|---------------------|
| Kubernetes | ClusterIP Services (DNS) |
| Kubernetes + advanced traffic | Service mesh (Istio/Linkerd) |
| AWS ECS | ALB + Cloud Map service discovery |
| Multi-cloud / on-prem | Consul or Eureka |
| Docker Compose (dev) | Docker DNS (service names) |
| Serverless | API Gateway + direct invocation |

For most teams on Kubernetes, built-in DNS discovery is sufficient until you need canary deployments, mTLS, or cross-cluster routing — then add a service mesh.

## Client-side vs server-side discovery

| Pattern | Pros | Cons |
|---------|------|------|
| DNS + K8s Service | Simple | TTL caching delays |
| Consul/etcd | Health-aware | Extra infrastructure |
| Service mesh | mTLS + LB built-in | Complexity |

Prefer Kubernetes headless services + client load balancing for gRPC long-lived connections.

## Resources

- [HashiCorp Consul service discovery](https://developer.hashicorp.com/consul/docs/discovery)
- [Kubernetes Services documentation](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Istio traffic management](https://istio.io/latest/docs/concepts/traffic-management/)
- [Netflix Eureka (Spring Cloud)](https://github.com/Netflix/eureka)
- [AWS Cloud Map service discovery](https://docs.aws.amazon.com/cloud-map/latest/dg/what-is-cloud-map.html)

## Production notes for LLM stacks

When `microservices-service-discovery` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `service discovery patterns` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.

## Production notes for LLM stacks

When `microservices-service-discovery` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `service discovery patterns` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.


For `microservices-service-discovery`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.

For `microservices-service-discovery`, treat observability and security controls as part of the user experience: silent failures erode trust faster than explicit error messages. Instrument deny paths, measure tail latency, and review dashboards with on-call weekly.
