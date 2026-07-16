---
title: "GraphQL Federation and the Supergraph"
slug: "graphql-federation-supergraph"
description: "GraphQL federation and the supergraph explained: how subgraphs compose into one schema, entity resolution across services, and the operational tradeoffs teams underestimate."
datePublished: "2026-04-30"
dateModified: "2026-04-30"
tags: ["Backend", "GraphQL", "Architecture", "API Design"]
keywords: "GraphQL federation, supergraph, subgraphs, Apollo federation, schema composition, entity resolution"
faq:
  - q: "What is GraphQL federation?"
    a: "GraphQL federation is an architecture for splitting a single GraphQL API across multiple independently-owned services called subgraphs, which are composed into one unified schema — the supergraph — that clients query as if it were monolithic. A gateway (router) plans and executes each query across the relevant subgraphs and stitches the results together. It lets separate teams own separate parts of the graph without maintaining one giant shared server."
  - q: "What is an entity in GraphQL federation?"
    a: "An entity is a type whose fields can be defined and resolved across multiple subgraphs, identified by a key. For example, a User might have profile fields in an accounts subgraph and order fields contributed by an orders subgraph, joined on the user's id. The @key directive declares the identifying fields, and each subgraph provides a reference resolver so the router can fetch its slice of that entity."
  - q: "When should I use federation instead of a single GraphQL server?"
    a: "Use federation when multiple teams need to own distinct domains of a large graph and independent deployment matters more than simplicity — typically at organizational scale with many services. For a small team or a single product, one well-structured GraphQL server (a monograph) is simpler, cheaper to operate, and avoids the distributed-query complexity federation introduces. Adopt federation to solve an ownership problem, not a performance one."
---

Federation exists to answer an organizational question, not a technical one: how do you let ten teams each own part of a GraphQL API without forcing them all into one repository and one deploy? GraphQL federation composes multiple independently-built and independently-deployed services — subgraphs — into a single unified schema called the supergraph. Clients query the supergraph as though it were one monolithic API; behind the scenes a router figures out which subgraphs hold which fields, calls them, and assembles the response. The magic trick is that a `User` can have its profile from one service and its orders from another, joined seamlessly, with neither team knowing about the other's internals.

I've stood up federated graphs and I've also talked teams *out* of them. Both were the right call in context. This is a genuinely powerful architecture with an operational bill that people consistently underestimate, so let me cover both the mechanism and the honest tradeoffs.

## Subgraphs and the supergraph

A subgraph is an ordinary GraphQL service that also speaks the federation spec — it exposes a schema plus some federation metadata. Composition takes all the subgraph schemas and merges them into one supergraph schema. That composed schema is what the router serves to clients.

Say two teams own different domains. The accounts team's subgraph:

```graphql
type User @key(fields: "id") {
  id: ID!
  name: String!
  email: String!
}

type Query {
  user(id: ID!): User
}
```

The orders team's subgraph *extends* that same `User` with the fields they own:

```graphql
type User @key(fields: "id") {
  id: ID! @external
  orders: [Order!]!
}

type Order @key(fields: "id") {
  id: ID!
  total: Float!
  placedAt: String!
}
```

Composition merges these into one `User` type that has `name`, `email`, *and* `orders`. A client writes a single query spanning both, and never sees the seam:

```graphql
query {
  user(id: "u_42") {
    name          # from accounts subgraph
    orders {      # from orders subgraph
      total
    }
  }
}
```

## Entity resolution: the heart of it

The concept that makes this work is the **entity**. An entity is a type shared across subgraphs, identified by a `@key`. Here `User @key(fields: "id")` says "any subgraph that knows a user's `id` can contribute to or resolve a `User`."

When the router processes that query, it does something like:

1. Call the accounts subgraph's `user(id: "u_42")` to get `name` and the `id`.
2. Take that `id` and ask the orders subgraph to resolve the `User` entity for it, then fetch `orders`.

Step 2 relies on each subgraph implementing a **reference resolver** — a function that, given the key fields, returns that entity's slice. The router uses a special `_entities` query under the hood:

```graphql
# What the router effectively sends to the orders subgraph:
query {
  _entities(representations: [{ __typename: "User", id: "u_42" }]) {
    ... on User { orders { total } }
  }
}
```

Understanding this is the difference between federation feeling like magic and feeling like a black box. Every cross-subgraph join is a representation being passed to a reference resolver. Which brings us straight to the biggest operational hazard.

## The N+1 problem, distributed

The classic GraphQL N+1 problem gets worse under federation because the "1+N" now crosses network boundaries. If you fetch a list of 100 users and each needs `orders` from another subgraph, a naive router makes one call for the list and then risks fanning out for the order data. In practice the router batches entity fetches into a single `_entities` call per subgraph per query step — but *within* that subgraph, your reference resolvers can still trigger N database queries if you didn't batch.

The fix is the same discipline as any GraphQL server, applied per subgraph: use DataLoader-style batching in every reference resolver so a batch of 100 representations becomes one database query, not 100. I've seen federated graphs with beautiful schemas quietly melting a database because someone wrote a reference resolver that did a single-row lookup per entity. Batching is not optional at scale.

## Federation versus the alternatives

Federation is one point on a spectrum of ways to assemble an API across services:

| Approach | Ownership model | Best for |
| --- | --- | --- |
| Monograph (one GraphQL server) | One team/repo | Small teams, single product |
| Federation / supergraph | Many teams, many subgraphs | Large orgs, independent deploys |
| Schema stitching (legacy) | Central gateway config | Mostly superseded by federation |
| BFF per client | Client team owns the layer | Divergent client needs |

The comparison worth internalizing: federation is about *distributing schema ownership*. If your problem is instead "each client wants a differently-shaped API," a [backend-for-frontend](https://blog.michaelsam94.com/backend-for-frontend-bff/) may serve you better than federating everything. And if you're still deciding whether GraphQL is even the right protocol here, the tradeoffs in [REST vs gRPC vs GraphQL in 2026](https://blog.michaelsam94.com/rest-vs-grpc-vs-graphql-2026/) matter more than any federation detail — federation only makes sense once you've committed to GraphQL and hit an ownership ceiling.

## The operational bill

Here's what the glossy diagrams omit. Federation buys team autonomy and pays for it in distributed-systems complexity:

- **Composition can fail.** Two subgraphs defining conflicting types or invalid references will fail to compose. You need composition checks in CI, gated against the published supergraph, so a bad subgraph change is caught before it breaks everyone. Schema registries (Apollo GraphOS, Hive) exist precisely for this.
- **A query can now fail partially.** One subgraph being slow or down affects any query touching it. You must design for partial results, timeouts, and per-subgraph error handling — a monograph never had this failure mode.
- **Tracing gets harder.** A single client query becomes a fan-out of subgraph calls. Without distributed tracing that stitches the whole plan together, debugging "why is this query slow" becomes archaeology.
- **The router is now critical infrastructure.** It's a shared component every request flows through. It needs its own scaling, monitoring, and careful version management.
- **Governance overhead.** Naming conventions, ownership of shared entities, and who's allowed to extend what all become cross-team agreements. That coordination cost is real and permanent.

## My honest recommendation

Reach for federation when you have a genuine ownership problem: several teams, a large graph, and real pain from being coupled into one server and one deploy cadence. In that situation it's a clean, well-supported way to let teams move independently while presenting one API to clients, and the tooling around composition checks and registries has matured a lot.

Do *not* reach for it to solve performance or because microservices sound modern. If you're a small team or a single product, a well-structured monograph with good module boundaries will outrun a federated graph on both velocity and operability, and you can always federate later when the ownership pressure is real. The best federated graphs I've seen started as monographs and split when a specific team's autonomy demanded it — not on day one, on a diagram. Adopt the architecture to fix the problem you actually have, and the supergraph becomes an asset rather than a distributed-systems tax you pay forever.

## Resources

- [GraphQL — official specification](https://spec.graphql.org/)
- [Apollo — Federation documentation](https://www.apollographql.com/docs/federation/)
- [Apollo Federation subgraph specification](https://www.apollographql.com/docs/federation/subgraph-spec)
- [The Guild — GraphQL Hive](https://the-guild.dev/graphql/hive)
- [graphql.org — DataLoader and batching](https://graphql.org/learn/best-practices/)
- [Apollo Router (GitHub)](https://github.com/apollographql/router)
