---
title: "REST API Design and Richardson Maturity"
slug: "rest-api-design-richardson-maturity"
description: "Use Richardson's maturity model to design REST APIs that earn their verbs: resources, HTTP semantics, hypermedia, and where each level actually pays off."
datePublished: "2025-04-05"
dateModified: "2025-04-05"
tags: ["REST", "API Design", "HTTP", "Backend"]
keywords: "Richardson maturity model, REST API design, HTTP verbs, HATEOAS, resource modeling, API architecture, level 2 REST"
faq:
  - q: "Do I need HATEOAS to call my API RESTful?"
    a: "Richardson level 3 (hypermedia controls) is valuable when clients are diverse and long-lived, but most internal product APIs stop at level 2 and that is fine. Level 2 means correct use of URIs as resources, HTTP verbs, and status codes. Chasing HATEOAS for a mobile app you control often adds payload noise without client benefit."
  - q: "What is the minimum bar for a production REST API?"
    a: "Level 2: nouns in paths, verbs in methods, meaningful status codes, and consistent error bodies. GET must not mutate state. POST creates, PUT replaces, PATCH partial-updates, DELETE removes. If your API uses POST for everything with action names in the URL, you are still at level 0 regardless of what the README claims."
  - q: "How should I model nested resources?"
    a: "Nest when the child cannot exist without the parent and scoping is always required, e.g. `/orders/{id}/line-items`. Shallow collections with query filters are easier to evolve than deep hierarchies. If clients need cross-parent queries, expose a top-level collection with filter parameters rather than forcing traversal through three URL segments."
---

A partner integration team asked why their "REST" API required POST bodies named `createUser` and `deleteUser` on the same `/api/actions` endpoint. That is level 0 on Richardson's model—single-URI RPC dressed in JSON. The maturity model is not a trophy ladder; it is a diagnostic for whether your HTTP surface actually uses the protocol or merely tunnels procedures through it. Most teams should aim for level 2, understand level 3, and stop feeling guilty about skipping hypermedia when they own both client and server.

## Level 0: the swamp of one endpoint

Level 0 APIs expose one URL and encode the operation in the payload. They work behind corporate firewalls and die at public scale because every client hard-codes operation names, versioning becomes ambiguous, and caches cannot help you. If you are greenfield on HTTP, do not start here unless you are wrapping a legacy mainframe with no alternative.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Level 1: resources without verbs

Level 1 introduces distinct URIs per resource type—`/users`, `/orders`—but still tends to tunnel actions via POST because teams fear PUT and DELETE. You get cleaner routing and logging, yet clients still guess URLs from documentation alone. It is a stepping stone, not a destination.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Level 2: where most APIs should live

Level 2 aligns HTTP methods with semantics and uses status codes that mean something to intermediaries:

| Method | Intent | Success | Typical failure |
|--------|--------|---------|-----------------|
| GET | Read | 200 | 404 |
| POST | Create | 201 + Location | 409 |
| PUT | Replace | 200/204 | 412 |
| PATCH | Partial update | 200 | 422 |
| DELETE | Remove | 204 | 404 |

```http
POST /v1/orders HTTP/1.1
Content-Type: application/json

{"customerId": "cust_42", "items": [{"sku": "WIDGET", "qty": 2}]}

HTTP/1.1 201 Created
Location: /v1/orders/ord_9f3a
ETag: "v1"
```

Use `ETag` and `If-Match` for optimistic concurrency on updates. Return `422 Unprocessable Content` when JSON parses but business rules fail—distinct from `400` for malformed syntax. Caching, CDN behavior, and observability all improve when methods tell the truth.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Modeling collections and pagination

Collections are resources too. Prefer:

```
GET /v1/invoices?status=open&cursor=eyJpZCI6MTIzfQ
```

over RPC-style `POST /v1/invoices/search`. Cursor-based pagination keeps ordering stable under concurrent inserts; offset pagination is acceptable only for small, admin-only tables. Document default sort and maximum page size in OpenAPI so generated clients inherit sane limits.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Level 3: hypermedia when clients are strangers

Level 3 embeds links (`self`, `next`, `cancel`) so a generic client discovers transitions without out-of-band docs. Payment processors and public government APIs benefit because integrators you have never met ship clients years later. For your first-party SPA backed by the same repo, links often duplicate what TypeScript types already express.

If you adopt level 3, pick one hypermedia format (JSON:API, HAL, or Siren) and enforce it in CI. Half-implemented `_links` objects confuse more than they help.

Publish an OpenAPI diff in CI for every pull request touching public routes. Consumers generated from the spec catch renames before deploy. Mobile apps ship weeks after the API and will hit removed fields if you skip deprecation windows.

Level-2 semantics unlock HTTP caching. GET with ETag lets clients send If-None-Match and receive 304 when nothing changed. Cache-Control on authenticated resources prevents shared caches from leaking data while still allowing browser revalidation. POST responses are not cacheable by default—do not fight the spec with custom headers unless you understand CDN behavior.

Internal clients are not exempt from maturity discipline. Admin tools that tunnel POST RPC become external integrations eventually. Naming resources consistently today avoids awkward aliases tomorrow when partners mirror your paths.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.

## Resources

- [Richardson Maturity Model (Martin Fowler)](https://martinfowler.com/articles/richardsonMaturityModel.html)
- [HTTP semantics (RFC 9110)](https://www.rfc-editor.org/rfc/rfc9110.html)
- [JSON:API specification](https://jsonapi.org/format/)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
- [MDN HTTP request methods](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods)
