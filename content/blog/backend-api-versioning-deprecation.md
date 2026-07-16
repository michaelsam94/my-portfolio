---
title: "API Versioning and Deprecation"
slug: "backend-api-versioning-deprecation"
description: "Version and deprecate APIs without breaking clients: URL vs header versioning, sunset headers, migration windows, and communication patterns that work."
datePublished: "2026-07-16"
dateModified: "2026-07-16"
tags: ["Backend", "API", "Architecture", "DevOps"]
keywords: "API versioning, API deprecation strategy, URL versioning vs header, sunset header API, breaking API changes"
faq:
  - q: "What is the best way to version an API?"
    a: "URL path versioning (/api/v1/, /api/v2/) is the most visible and easiest for clients to implement. Header versioning (Accept: application/vnd.api+json;version=2) is cleaner URLs but harder to test in browsers. Both work — pick one and be consistent. Avoid versioning individual endpoints within the same version."
  - q: "How long should I support deprecated API versions?"
    a: "Minimum 6 months for internal APIs, 12 months for public/partner APIs. Provide sunset headers, changelog documentation, and migration guides. Never remove a version without verified migration of all active clients — check access logs to confirm zero traffic before decommissioning."
  - q: "How do I communicate API deprecation to clients?"
    a: "Use Deprecation and Sunset HTTP headers on every response from deprecated endpoints. Include deprecation notices in API documentation and changelog. Send direct notification to API key holders. Log warnings server-side when deprecated endpoints are called to track remaining usage."
---

Breaking an API is breaking a contract — and your clients can't deploy fixes as fast as you can deploy backend changes. API versioning is how you evolve without orphaning existing integrations. The mechanics are straightforward (URL prefix or header); the hard part is deprecation discipline — giving clients enough time and clear enough signals to migrate before you pull the plug. I've managed v1→v2 transitions where every client migrated smoothly (sunset headers, 12-month window, migration guide) and ones where we yanked v1 after 30 days and spent a quarter fixing broken integrations.

## Versioning strategies

**URL path (recommended for most APIs):**
```
GET /api/v1/orders
GET /api/v2/orders
```

**Header:**
```
GET /api/orders
Accept: application/vnd.myapp.v2+json
```

**Query parameter (avoid):**
```
GET /api/orders?version=2
```

URL versioning is explicit, cacheable, testable in any HTTP client, and visible in access logs. Header versioning keeps URLs clean but makes debugging harder. Pick URL versioning unless you have a strong reason not to.

## Non-breaking vs breaking changes

Within a version, only make backward-compatible changes:

| Change | Breaking? | Action |
|--------|-----------|--------|
| Add optional field to response | No | Same version |
| Add new endpoint | No | Same version |
| Add optional query parameter | No | Same version |
| Remove response field | Yes | New version |
| Rename field | Yes | New version |
| Change field type | Yes | New version |
| Change URL path | Yes | New version |
| Change error codes | Maybe | Document carefully |

When in doubt, new version. Clients ignore unknown fields; they crash on missing fields.

## Deprecation headers

RFC 8594 Sunset header + custom Deprecation header:

```python
@app.get("/api/v1/orders")
def list_orders_v1(response: Response):
    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = "Sat, 01 Jan 2027 00:00:00 GMT"
    response.headers["Link"] = '</api/v2/orders>; rel="successor-version"'
    return get_orders_v1()
```

Every response from deprecated endpoints includes these headers. Smart client SDKs log warnings; monitoring tracks deprecated endpoint usage.

## Migration timeline

```
Month 0:  v2 released, v1 marked deprecated
Month 1:  Deprecation headers live, migration guide published
Month 3:  Email to all API key holders with migration deadline
Month 6:  v1 returns warning body: {"warning": "v1 deprecated, migrate to v2 by Month 12"}
Month 9:  Direct outreach to clients still on v1 (from access logs)
Month 11: Final warning — v1 shuts down in 30 days
Month 12: v1 decommissioned (returns 410 Gone with migration link)
```

Adjust timeline based on client count and contract obligations. Public APIs need longer windows.

## Tracking remaining v1 usage

```python
@app.middleware("http")
async def track_version_usage(request, call_next):
    if "/api/v1/" in request.url.path:
        metrics.increment("api.v1.usage", tags={
            "endpoint": request.url.path,
            "client_id": request.headers.get("X-Api-Key", "unknown"),
        })
    return await call_next(request)
```

Dashboard: v1 requests per day, broken down by client. Don't decommission until zero for 2 consecutive weeks.

## Running multiple versions

Share business logic, separate presentation:

```python
# Shared
class OrderService:
    def get_orders(self, user_id, cursor, limit):
        return db.query_orders(user_id, cursor, limit)

# v1 presentation
def to_v1(order) -> dict:
    return {"id": order.id, "status": order.status, "total": order.total}

# v2 presentation
def to_v2(order) -> dict:
    return {
        "id": order.id,
        "status": order.status,
        "total": {"amount": order.total, "currency": order.currency},
        "items": [to_v2_item(i) for i in order.items],
        "createdAt": order.created_at.isoformat(),
    }
```

Don't duplicate business logic across versions — duplicate only the response mapping.

## Document in OpenAPI

Maintain separate specs per version with deprecation markers — see [API docs with OpenAPI](https://blog.michaelsam94.com/api-documentation-openapi/):

```yaml
# v1 spec
info:
  version: "1.0.0"
  description: "DEPRECATED — sunset 2027-01-01. Migrate to v2."

# v2 spec
info:
  version: "2.0.0"
  description: "Current version."
```

## Contract testing across versions

When running v1 and v2 simultaneously, contract tests prevent accidental breakage:

```typescript
// Consumer-driven contract test
describe('Orders API v2 contract', () => {
  it('returns total as money object', async () => {
    const response = await api.v2.get('/orders/123');
    expect(response.data.total).toEqual({
      amount: expect.any(Number),
      currency: expect.stringMatching(/^[A-Z]{3}$/),
    });
  });

  it('v1 still returns flat total for backward compat', async () => {
    const response = await api.v1.get('/orders/123');
    expect(typeof response.data.total).toBe('number');
  });
});
```

Run contract tests in CI on every PR that touches response mappers. Breaking a v1 response while v1 is still active is a production incident waiting to happen.

## Handling additive evolution without new versions

Many changes don't require a new version if clients follow robust parsing rules:

- **Adding optional response fields** — safe; clients ignore unknown fields
- **Adding optional request fields** — safe; old clients don't send them
- **Adding new enum values** — risky if clients switch on exhaustive enums; document that enums may grow
- **Adding new endpoints** — always safe

Publish client SDK guidelines: "Never switch on exhaustive enums. Always ignore unknown response fields. Always send only documented request fields."

## Version routing in application code

Avoid duplicating entire handler stacks. Route at the presentation layer:

```typescript
app.get('/api/:version/orders', (req, res) => {
  const orders = orderService.list(req.user.id);
  switch (req.params.version) {
    case 'v1': return res.json(orders.map(toV1));
    case 'v2': return res.json(orders.map(toV2));
    default: return res.status(404).json({ error: 'Unknown API version' });
  }
});
```

Or use separate routers mounted at `/api/v1` and `/api/v2` that share service layer imports. Never fork business logic — only response serialization.

## Failure modes

- **Removing v1 with active clients** — check access logs, not assumptions; zero traffic for 2 weeks minimum
- **Breaking v1 while adding v2** — contract tests catch this; don't skip them
- **No sunset headers** — clients discover deprecation from broken integrations, not proactive warnings
- **Version in query parameter** — CDN caches wrong version; URL path or Accept header only
- **Inconsistent error format across versions** — clients can't build generic error handling
- **Deprecating without migration guide** — field mapping table (v1 `total` → v2 `total.amount`) is minimum

## Production checklist

- URL path versioning with consistent prefix (`/api/v1/`, `/api/v2/`)
- Deprecation and Sunset headers on all deprecated endpoints
- Access log metrics per version per client API key
- Migration guide published with field mapping table
- Contract tests for both versions in CI
- Business logic shared; only presentation layer duplicated
- Minimum 6-month (internal) or 12-month (public) deprecation window
- v1 returns 410 Gone with migration link after sunset, not 404

## Resources

- [RFC 8594 — Sunset Header Field](https://datatracker.ietf.org/doc/html/rfc8594)
- [Stripe API versioning approach](https://docs.stripe.com/api/versioning)
- [GitHub REST API versioning](https://docs.github.com/en/rest/about-the-rest-api/api-versions)
- [OpenAPI documentation](https://blog.michaelsam94.com/api-documentation-openapi/)
- [OWASP API Security Top 10 — improper inventory](https://blog.michaelsam94.com/api-security-owasp-api-top-10/)
