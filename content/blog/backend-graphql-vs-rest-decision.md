---
title: "Choosing Between GraphQL and REST"
slug: "backend-graphql-vs-rest-decision"
description: "A practical decision framework for GraphQL vs REST: overfetching, caching, authz complexity, mobile clients, and when a hybrid wins."
datePublished: "2024-11-12"
dateModified: "2024-11-12"
tags: ["Backend", "API", "Architecture"]
keywords: "GraphQL vs REST, API design decision, overfetching, BFF pattern, GraphQL caching, REST HATEOAS"
faq:
  - q: "When is GraphQL clearly the better choice?"
    a: "When multiple clients need very different shapes of the same domain data — especially mobile with bandwidth constraints — and you're willing to invest in a schema, DataLoader-style batching, and query cost limits. Product-driven UIs that constantly need new field combinations benefit most."
  - q: "When should I stick with REST?"
    a: "When resources are naturally document-shaped, HTTP caching and CDNs matter, your consumers are mostly external partners who expect OpenAPI, or your team is small and won't staff schema governance. REST plus a BFF still solves many 'overfetch' complaints without GraphQL's operational surface."
  - q: "Can I use both?"
    a: "Yes — and many mature orgs do. Public/partner APIs and simple CRUD stay on REST; a GraphQL layer (or BFF) serves first-party web/mobile. Don't expose two conflicting domain models — share the same service/domain layer underneath."
---

The GraphQL-vs-REST debate wastes time when it stays religious. The useful question is which constraints you have: client diversity, caching needs, authz complexity, and how much schema ops you'll actually staff. I've shipped both in the same company — REST for partners, GraphQL for the app — and the hybrid was calmer than forcing one dogma everywhere.

## What problem are you solving?

| Pain | REST-shaped fix | GraphQL-shaped fix |
|---|---|---|
| Overfetching on mobile | Sparse fieldsets / BFF | Client-specified selection sets |
| Underfetching / chattiness | Aggregate endpoints / BFF | Single query, nested fields |
| Evolving many clients | Versioned resources | Additive schema evolution |
| CDN cache friendliness | Excellent (GET by URL) | Harder (POST + varied queries) |
| External partner DX | OpenAPI ecosystem | Steeper; fewer corporate standards |

If your only client is your own Next.js app talking to your own BFF, GraphQL's win shrinks — you already control the aggregate. If you have iOS, Android, web, and a watch app all arguing about payload size, GraphQL starts paying rent.

## Authz and the N+1 trap

GraphQL makes it easy to write a query that walks ten relations. Each relation needs authorization. Miss one field resolver check and you've leaked data through a nested path REST never exposed.

```graphql
query {
  me {
    company {
      employees {
        salaryBand  # who can see this?
      }
    }
  }
}
```

Budget for: per-field or per-type authz, query depth/complexity limits, and DataLoader (or equivalent) so you're not doing N+1 SQL. REST has the same authz needs, but the attack surface is usually fewer endpoints with clearer boundaries.

## Caching reality

REST `GET /users/123` caches cleanly at the CDN with ETags. GraphQL typically POSTs to `/graphql` with unique bodies — CDN caching needs persisted queries or Automatic Persisted Queries (APQ) and careful cache keys. Client libraries (Apollo/Urql/Relay) normalize caches well *in the app*; edge caching takes more design.

If your API is mostly public, read-heavy, and CDN-bound (media metadata, catalogs), REST still wins on boring grounds.

## Operational cost

GraphQL needs:

- Schema reviews / ownership
- Breaking-change policy (usually additive only)
- Cost analysis in CI for expensive queries
- Observability that understands operation names, not just paths

REST needs versioning discipline and a zoo of endpoints if you don't invest in BFFs. Pick the tax you're willing to pay.

## A simple decision rule

1. **Partner/public API, CRUD resources, CDN** → REST (OpenAPI)
2. **Many first-party clients, nested domain, strong schema culture** → GraphQL
3. **Mostly one web app** → REST or tRPC/BFF; GraphQL optional
4. **Unsure** → REST now, extract a GraphQL BFF later over the same domain services

Don't migrate to GraphQL to look modern. Migrate when clients are negotiating payload shapes weekly and your REST aggregates are becoming ad-hoc RPCs with different names.

## The BFF pattern as a third option

Before choosing GraphQL, consider a Backend-for-Frontend (BFF) — a thin API layer per client that aggregates domain services into exactly the shape that client needs:

```
Mobile BFF → aggregates UserService + OrderService → /mobile/home-screen
Web BFF    → aggregates UserService + OrderService → /web/dashboard
Domain services (shared, client-agnostic)
```

BFFs solve overfetching without GraphQL's schema infrastructure. The tradeoff: N clients means N BFFs to maintain, and each BFF endpoint is a bespoke contract. GraphQL replaces N bespoke endpoints with one schema and N client queries.

Choose BFF when you have 1–2 clients and a small team. Choose GraphQL when you have 4+ clients with diverging data needs and can staff schema governance.

## Real-world hybrid architecture

Mature orgs rarely pick one:

| Surface | Protocol | Why |
|---|---|---|
| Partner/public API | REST + OpenAPI | Standard tooling, CDN cacheable, contractual stability |
| Mobile app | GraphQL or BFF | Payload control, nested data |
| Internal admin | REST or tRPC | Simple CRUD, type-safe if tRPC |
| Real-time updates | WebSocket/SSE + REST | GraphQL subscriptions add complexity |
| Webhooks/events | Async messaging | Neither REST nor GraphQL |

The domain service layer is shared — only the transport differs. Don't duplicate business logic in GraphQL resolvers; call the same service functions REST handlers call.

## GraphQL-specific production concerns

**Query cost analysis** — run expensive queries in CI:

```graphql
# Reject in production — depth 5, fetches 10^5 rows
query {
  users {
    orders {
      items {
        product {
          reviews { author { company { employees { name } } } } }
        }
      }
    }
  }
}
```

Set depth limits (max 7), complexity limits (max cost 1000), and pagination requirements on list fields.

**N+1 prevention** — DataLoader batches database calls per request tick:

```typescript
const userLoader = new DataLoader(async (ids: string[]) => {
  const users = await userService.findByIds(ids);
  return ids.map(id => users.find(u => u.id === id));
});

// In resolver: return userLoader.load(order.userId) — batched automatically
```

Without DataLoader, a query returning 100 orders fires 100 user lookups.

**Schema evolution policy** — additive changes only in production (new fields, new types). Deprecate with `@deprecated(reason: "...")` and remove after client migration. Breaking changes require a new schema version or `/v2/graphql` endpoint.

## REST-specific production concerns

**Versioning** — URL path (`/v2/users`) or header (`Accept: application/vnd.api+json;version=2`). Pick one, document sunset policy. See [API versioning guide](https://blog.michaelsam94.com/backend-api-versioning-deprecation/).

**Pagination** — cursor-based for large datasets, offset for admin tools. Consistent envelope: `{ data, meta: { next_cursor, total } }`.

**Error format** — RFC 7807 Problem Details across all endpoints. GraphQL errors in `{ errors: [{ message, path, extensions }] }` — different shape, same need for consistency within each protocol.

## Migration path: REST to GraphQL

If you decide to migrate, don't big-bang:

1. Stand up GraphQL alongside REST — same domain services underneath
2. Migrate one client (usually mobile) to GraphQL
3. Measure: payload size reduction, client development velocity, operational incidents
4. Migrate additional clients or keep hybrid indefinitely
5. Deprecate REST aggregates that GraphQL replaced — keep REST for partners

Most teams that "migrate to GraphQL" end up hybrid permanently. That's fine.

## Failure modes

- **GraphQL as generic SQL** — clients write queries that expose data they shouldn't access; field-level authz is non-optional
- **REST endpoint explosion** — `/users/with-orders`, `/users/with-orders-and-reviews` — sign you need BFF or GraphQL
- **Caching GraphQL at CDN** — requires persisted queries; don't expect it to work like REST out of the box
- **Two conflicting domain models** — REST returns `user_id`, GraphQL returns `userId`; breaks shared client code

## Production checklist

- Decision documented with client count, caching needs, and team capacity
- Domain services shared between REST and GraphQL layers
- GraphQL: depth/complexity limits, DataLoader, field authz
- REST: consistent error format, versioning policy, pagination standard
- Hybrid architecture diagram showing which clients use which protocol
- Schema review process if GraphQL is in use

## Resources

- [GraphQL Foundation — Best Practices](https://graphql.org/learn/best-practices/)
- [Microsoft API guidelines — REST](https://github.com/microsoft/api-guidelines)
- [Apollo — Persisted queries](https://www.apollographql.com/docs/apollo-server/performance/apq/)
- [Shopify — GraphQL Admin API design](https://shopify.dev/docs/apps/build/graphql)
---
