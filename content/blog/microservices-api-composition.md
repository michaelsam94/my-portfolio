---
title: "API Composition Patterns"
slug: "microservices-api-composition"
description: "Aggregate data from multiple microservices with API composition: gateway aggregation, client-side composition, BFF patterns, and GraphQL federation."
datePublished: "2025-06-01"
dateModified: "2025-06-01"
tags: ["BE", "Microservices", "API", "Architecture"]
keywords: "API composition pattern, microservices aggregation, BFF backend for frontend, GraphQL federation, API gateway composition, service aggregation"
faq:
  - q: "What is the difference between API composition and API gateway?"
    a: "An API gateway routes requests to a single backend service and handles cross-cutting concerns (auth, rate limiting, TLS). API composition goes further — a single client request triggers calls to multiple backend services whose responses are merged into one. The gateway may host the composition logic, or a separate composer service does."
  - q: "When should I use a BFF instead of a generic API composer?"
    a: "Use a Backend-for-Frontend (BFF) when different client types (web, mobile, IoT) need different data shapes from the same backend services. A web BFF returns full product details with reviews; a mobile BFF returns a lightweight summary. One generic composer forces all clients to over-fetch or under-fetch."
  - q: "How do I handle partial failures in API composition?"
    a: "Define per-field fallback behavior: return partial data with null for failed services, cache stale data as fallback, or fail the entire request if a critical service is down. Never let one slow service block the entire response — set individual timeouts and use circuit breakers on each downstream call."
---

Your mobile app needs a product detail screen: product info from the catalog service, inventory from the warehouse service, reviews from the ratings service, and personalized pricing from the pricing service. Four microservices, four network calls, four potential failure points — all to render one screen.

API composition aggregates data from multiple services into a single response. The client makes one request; the composer orchestrates backend calls and assembles the result. Done well, clients stay simple. Done poorly, you build a distributed monolith that is slower and less reliable than the monolith you replaced.

## Composition patterns

**Gateway composition:** the API gateway calls multiple services and merges responses.

```
Client → API Gateway → Catalog Service
                     → Inventory Service    → Merged response
                     → Reviews Service
```

**Dedicated composer service:** a separate service handles aggregation logic.

```
Client → Composer Service → Catalog Service
                          → Inventory Service    → Merged response
                          → Reviews Service
```

**Client-side composition:** the client calls services directly and assembles the UI.

```
Client → Catalog Service
       → Inventory Service    → Client assembles
       → Reviews Service
```

**GraphQL federation:** each service exposes a GraphQL subgraph; a gateway merges schemas.

```
Client → GraphQL Gateway → Catalog subgraph
                         → Inventory subgraph  → Unified schema
                         → Reviews subgraph
```

## Gateway composition example

```python
import asyncio
import httpx

async def get_product_detail(product_id: str) -> dict:
    async with httpx.AsyncClient(timeout=2.0) as client:
        catalog_task = client.get(f"http://catalog/products/{product_id}")
        inventory_task = client.get(f"http://inventory/stock/{product_id}")
        reviews_task = client.get(f"http://reviews/product/{product_id}")

        results = await asyncio.gather(
            catalog_task, inventory_task, reviews_task,
            return_exceptions=True,
        )

    product = parse_or_default(results[0], default=None)
    if product is None:
        raise HTTPException(404, "Product not found")

    inventory = parse_or_default(results[1], default={"in_stock": None})
    reviews = parse_or_default(results[2], default={"items": [], "average": None})

    return {
        "product": product,
        "inventory": inventory,
        "reviews": reviews,
    }
```

Key details:
- **Parallel calls** with `asyncio.gather` — sequential calls multiply latency.
- **Individual timeouts** — one slow service does not block others.
- **Graceful degradation** — non-critical services return defaults on failure.

## Backend-for-Frontend (BFF)

Different clients need different data shapes:

```python
# Web BFF: full detail
@app.get("/web/products/{id}")
async def web_product_detail(id: str):
    return {
        "product": await catalog.get(id),
        "inventory": await inventory.get(id),
        "reviews": await reviews.get(id, limit=20),
        "recommendations": await recommendations.get(id, limit=8),
        "pricing": await pricing.get(id, include_history=True),
    }

# Mobile BFF: lightweight
@app.get("/mobile/products/{id}")
async def mobile_product_detail(id: str):
    return {
        "product": await catalog.get_summary(id),
        "in_stock": await inventory.get_stock_status(id),
        "rating": await reviews.get_average(id),
        "price": await pricing.get_current(id),
    }
```

Each BFF is owned by the frontend team it serves. Backend teams expose granular service APIs; BFFs compose them for specific client needs.

## Handling partial failures

Define failure policies per data source:

| Data source | Critical? | Failure behavior |
|------------|-----------|-----------------|
| Product catalog | Yes | Fail entire request (404/500) |
| Inventory | No | Return `"in_stock": null` |
| Reviews | No | Return empty array |
| Recommendations | No | Omit field entirely |
| Pricing | Yes | Fail or use cached price |

```python
async def fetch_with_fallback(coro, fallback, service_name: str):
    try:
        return await asyncio.wait_for(coro, timeout=2.0)
    except (asyncio.TimeoutError, httpx.HTTPError) as e:
        logger.warning(f"{service_name} unavailable: {e}")
        circuit_breaker.record_failure(service_name)
        return fallback
```

Wrap each downstream call with timeout, circuit breaker, and fallback.

## GraphQL as a composition layer

GraphQL federation lets each service own its schema fragment:

```python
# Catalog service subgraph
@strawberry.type
class Product:
    id: str
    name: str
    price: float

@strawberry.type
class Query:
    @strawberry.field
    async def product(self, id: str) -> Product:
        return await catalog_repo.get(id)

# Reviews service extends Product
@strawberry.type
class Product:
    reviews: list[Review] = strawberry.field(resolver=get_reviews)
```

The gateway resolves cross-service fields automatically. The client queries exactly what it needs in one request.

Trade-off: GraphQL adds operational complexity (schema registry, federation gateway, N+1 query risks with DataLoader).

## Anti-patterns to avoid

**Chatty composition:** 20 sequential service calls to render one page. Fix with parallel calls, batch APIs, or materialized views.

**Shared database composition:** composer queries multiple service databases directly. Breaks service boundaries — use APIs.

**God composer:** one service that knows about every other service. Split into domain-specific composers or BFFs.

**Synchronous chains:** A calls B calls C calls D. Total latency is the sum. Prefer parallel fan-out.

## Common production mistakes

Teams get api composition wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of api composition fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When api composition misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Sam Newman: Backends for Frontends pattern](https://samnewman.io/patterns/architectural/bff/)
- [GraphQL Federation specification](https://www.apollographql.com/docs/federation/)
- [Microsoft: Gateway Aggregation pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/gateway-aggregation)
- [Netflix API composition (BFF at scale)](https://netflixtechblog.com/optimizing-the-netflix-api-5c9ac716cf09)
- [Strawberry GraphQL Python library](https://strawberry.rocks/)
