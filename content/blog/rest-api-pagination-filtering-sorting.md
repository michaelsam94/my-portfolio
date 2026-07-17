---
title: "Pagination, Filtering, and Sorting"
slug: "rest-api-pagination-filtering-sorting"
description: "Design list endpoints with cursor pagination, safe filtering syntax, sort allowlists, and OpenAPI patterns that scale past ten thousand rows."
datePublished: "2025-04-21"
dateModified: "2026-07-17"
tags: ["REST", "API Design", "Backend", "Performance"]
keywords: "API pagination, cursor pagination, offset pagination, filtering query parameters, sort allowlist, keyset pagination, list endpoints"
faq:
  - q: "When is offset pagination acceptable?"
    a: "Offset works for admin tables under a few thousand rows where users jump to arbitrary pages and concurrent writes are rare. Public APIs with high insert rates should use cursor pagination because OFFSET scans degrade linearly and pages skip or duplicate rows when data shifts between requests."
  - q: "How do I prevent filter parameters from becoming SQL injection?"
    a: "Never interpolate user input into SQL or ORM fragments. Map allowed filter fields to typed column references via an allowlist. Parse operators from a fixed enum (=, gt, lt, in) and bind values as parameters. Reject unknown fields with 400 rather than silently ignoring them, which confuses clients."
  - q: "Should sort field names be exposed directly?"
    a: "Expose logical sort keys (createdAt, -amount) mapped internally to indexed columns. Reject sorts on unindexed columns in production APIs to avoid full table scans. Document default sort and maximum page size; cap limit at 100 unless the consumer has a contracted bulk export path."
faqAnswers:
  - question: "When is rest api pagination filtering sorting the wrong tool?"
    answer: "Skip rest api pagination filtering sorting when a simpler control or library already covers the failure mode, or when the operational cost exceeds the risk reduction for your threat model."
  - question: "What should I measure after adopting rest api pagination filtering sorting?"
    answer: "Track a leading signal (coverage, error class rate, or latency) and a lagging outcome (incidents, CVEs exploited, or user-visible failures) tied specifically to rest api pagination filtering sorting."
  - question: "How do I roll back a bad rest api pagination filtering sorting change?"
    answer: "Keep the previous config/version behind a flag or previous artifact; verify the rollback path in staging once, then document the one-command revert for on-call."
---
Support exported "all open tickets" and the request timed out at `GET /tickets?status=open&page=847&limit=100`. Offset pagination on a million-row table is an accidental denial of service. List endpoints are where APIs meet database physics: indexes, stable ordering, and bounded result sets. Getting pagination, filtering, and sorting right upfront saves you from bolting cursor tokens onto a breaking v2 later.

## Cursor pagination mechanics

Encode the last seen sort key in an opaque cursor:

```
GET /v1/events?limit=50&cursor=eyJ0IjoiMjAyNS0wNC0xVDEyOjAwOjAwWiIsImlkIjoiZXZfOTkifQ
```

Server decodes, applies `WHERE (created_at, id) > (:t, :id) ORDER BY created_at, id LIMIT 50`. Tie-break with primary key for stable ordering when timestamps collide. Response includes:

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "eyJ...",
    "has_more": true
  }
}
```

Sign cursors with HMAC if clients must not tamper with internal sort state.

## Filtering with an allowlist

Document filters explicitly in OpenAPI:

```
GET /v1/products?category=electronics&price_gte=100&price_lte=500&in_stock=true
```

Implementation pattern:

```python
ALLOWED_FILTERS = {
    "category": (Product.category, "eq"),
    "price_gte": (Product.price, "gte"),
    "price_lte": (Product.price, "lte"),
    "in_stock": (Product.stock, "gt", 0),
}

def apply_filters(query, params):
    for key, value in params.items():
        if key not in ALLOWED_FILTERS:
            raise ValidationError(f"Unknown filter: {key}")
        column, op, *args = ALLOWED_FILTERS[key]
        query = operators[op](query, column, value, *args)
    return query
```

Composite indexes must match common filter plus sort combinations—`(status, created_at DESC)` if every query filters by status.

## Sort syntax

Support comma-separated keys with `-` prefix for descending:

```
GET /v1/orders?sort=-created_at,id
```

Validate each token against `SORTABLE_FIELDS`. Return 400 for `-discount` if discount is computed and unindexed. Default sort should match the cursor key columns.

## Offset escape hatch

If you must support `page` and `offset` for legacy clients, cap maximum offset (e.g., 10,000) and log callers exceeding it. Provide CSV export or async search for deep scans.

## Total counts are expensive

`total` and `totalPages` require `COUNT(*)` which doubles query cost. Offer `has_more` instead, or make totals opt-in via `?include=total_count` on admin routes only.

## Rate limiting list endpoints

Broad filters on unindexed JSON columns are abuse vectors. Combine authentication, per-key rate limits, and query timeouts (statement_timeout in Postgres) so one integrator cannot scan your table.

Load tests should include worst-case filter combinations your docs allow. A missing composite index on tenant_id, status, created_at stays invisible until a large customer enables multi-tenant filtering at scale. Explain default sort explicitly; undefined order frustrates integrators building reconciliation jobs.

Publish worked examples: curl for first page, sample error when filter enum is wrong. Support closes tickets faster when docs show exact problem JSON for invalid queries. Cap include or expand depth for embedded resources—clients otherwise simulate GraphQL over REST one GET at a time.

Offset escape hatches need hard caps and logging. Provide async export for deep scans instead of unbounded OFFSET that doubles query cost on million-row tables.

Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Google AIP-158: Pagination](https://google.aip.dev/158)
- [GraphQL Cursor Connections Specification](https://relay.dev/graphql/connections.htm)
- [Use The Index, Luke: pagination](https://use-the-index-luke.com/no-offset)
- [OpenAPI Parameter Objects](https://spec.openapis.org/oas/latest.html#parameter-object)
- [Stripe pagination documentation](https://docs.stripe.com/api/pagination)

## Trade-offs I keep revisiting for rest api pagination filtering sorting


Operating rest api pagination filtering sorting well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For rest api pagination filtering sorting:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified rest api pagination filtering sorting stops moving — sunsetting is a feature.



| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |


## Load and chaos experiments for rest api pagination filtering sorting

Reviewers should challenge assumptions encoded in rest api pagination filtering sorting: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for rest api pagination filtering sorting: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for rest api pagination filtering sorting: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for rest api pagination filtering sorting: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Capacity planning with rest api pagination filtering sorting in mind

Roll out rest api pagination filtering sorting behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in rest api pagination filtering sorting

Detail 1 (80): for rest api pagination filtering sorting, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in rest api pagination filtering sorting becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break rest api pagination filtering sorting, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about rest api pagination filtering sorting: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for rest api pagination filtering sorting

Detail 2 (404): for rest api pagination filtering sorting, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for rest api pagination filtering sorting becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break rest api pagination filtering sorting, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about rest api pagination filtering sorting: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing rest api pagination filtering sorting

Detail 3 (791): for rest api pagination filtering sorting, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing rest api pagination filtering sorting becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break rest api pagination filtering sorting, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about rest api pagination filtering sorting: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.
