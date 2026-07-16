---
title: "Detecting N+1 Queries"
slug: "performance-n-plus-one-detection"
description: "Find and fix N+1 query problems: ORM lazy loading traps, SQL logging, query counting in tests, and DataLoader batching patterns."
datePublished: "2026-02-13"
dateModified: "2026-02-13"
tags: ["Performance", "Database", "ORM", "Backend"]
keywords: "N+1 query problem, ORM lazy loading, query detection, DataLoader batching, SQL performance"
faq:
  - q: "What is an N+1 query problem?"
    a: "One query loads N parent records, then N additional queries load related data — one per parent. Loading 100 blog posts with authors becomes 1 + 100 = 101 queries instead of 1 join or 2 batched queries."
  - q: "How do you detect N+1 in development?"
    a: "Enable SQL query logging, use ORM debug modes (Django DEBUG, Hibernate statistics, Prisma query logs), or add middleware that counts queries per request and fails when count exceeds a threshold in tests."
  - q: "Is eager loading always the fix for N+1?"
    a: "Usually — JOIN or prefetch related objects in one or two queries. Sometimes batch loading (DataLoader) is better when you can't predict which relations you need, or when joins create cartesian product row explosion."
---

The orders page loaded 50 orders in 120ms. With 500 orders it took 8 seconds. Linear scaling in a list view is almost always N+1 — one query for the list, one query per row for the related customer, product, or status label. I've found this bug in Rails, Django, Hibernate, and Prisma codebases. The ORM makes it easy to traverse object graphs; the database pays for each traversal.

## What N+1 looks like

```python
# Python/SQLAlchemy — classic N+1
orders = session.query(Order).limit(100).all()  # 1 query
for order in orders:
    print(order.customer.name)  # +100 queries (lazy load Customer)
```

```javascript
// Prisma — same pattern
const orders = await prisma.order.findMany({ take: 100 });
for (const order of orders) {
  const customer = await prisma.customer.findUnique({ where: { id: order.customerId } });
}
```

One request, 101 round-trips. At 2ms DB latency that's 200ms minimum — before query execution time.

## Detection in development

**Query counting middleware (Rails pattern):**

```ruby
# spec/support/query_counter.rb
ActiveSupport::Notifications.subscribe("sql.active_record") do |*args|
  QueryCounter.count += 1
end

RSpec.it "loads orders index efficiently" do
  create_list(:order, 50, :with_customer)
  expect { get orders_path }.to perform_under(5).queries
end
```

**Django nplusone package:**
```python
# settings.py DEBUG tooling
INSTALLED_APPS += ['nplusone.ext.django']
MIDDLEWARE += ['nplusone.ext.django.NPlusOneMiddleware']
NPLUSONE_RAISE = True  # fail in tests
```

**Prisma query log:**
```typescript
const prisma = new PrismaClient({ log: ['query'] });
// Watch for repeated SELECT ... WHERE id = $1 patterns
```

**APM in staging.** Datadog DBM, New Relic, or Pyroscope show repeated identical query shapes differing only in bind parameters — the N+1 fingerprint.

## Fixes: eager load and batch

**JOIN / includes (when relation is always needed):**

```python
orders = (
    session.query(Order)
    .options(joinedload(Order.customer))
    .limit(100)
    .all()
)
```

```typescript
const orders = await prisma.order.findMany({
  take: 100,
  include: { customer: true },
});
```

**Separate IN query (select IN batch):**

```python
orders = session.query(Order).limit(100).all()
customer_ids = [o.customer_id for o in orders]
customers = session.query(Customer).filter(Customer.id.in_(customer_ids)).all()
customer_map = {c.id: c for c in customers}
```

Two queries regardless of N.

**GraphQL DataLoader:**

```typescript
const customerLoader = new DataLoader(async (ids: readonly string[]) => {
  const customers = await prisma.customer.findMany({ where: { id: { in: [...ids] } } });
  const map = new Map(customers.map(c => [c.id, c]));
  return ids.map(id => map.get(id));
});

// Resolvers batch within same tick
customer: (order) => customerLoader.load(order.customerId),
```

DataLoader coalesces per-request loads into one query automatically.

## When JOIN isn't the answer

Cartesian explosion: loading orders with 50 line items each via JOIN returns 5000 rows for 100 orders. Use separate queries:

```python
.options(selectinload(Order.line_items))  # 2 queries: orders, then line_items WHERE order_id IN (...)
```

Not `joinedload` for large collections.

Partial needs: if customer name appears only 10% of the time, eager loading everyone wastes work — DataLoader or conditional prefetch wins.

## Prevention in code review

Red flags in PRs:
- Loop over query results with `await`/`async` DB calls inside
- Accessing `.relation` property in templates without prefetch in view
- GraphQL resolvers without DataLoader for nested types
- Missing `include`/`preload` when adding new list endpoint fields

CI gate: integration test with fixed fixture count asserts query count ceiling. Bump ceiling only with explicit review.

## Production monitoring

Alert on queries-per-request p99 for hot endpoints. Sudden jump from 5 to 150 after deploy — N+1 regression shipped.

Database slow query log grouped by normalized query pattern (`WHERE id = ?`) — high execution count relative to distinct id values signals batch opportunity.

## ORM-specific gotchas

Hibernate `@OneToMany` lazy collections inside `@Transactional` methods cause N+1 when serializing to JSON — session open during view rendering is an anti-pattern; use DTO projection or fetch join in service layer.

GraphQL without DataLoader on list fields is N+1 by design — audit schema with GraphQL query complexity limits and field-level tracing in Apollo Studio.

## Operational notes

Add query count assertions to contract tests for public API endpoints — consumer-driven pact tests catch N+1 regressions when backend teams add fields to GraphQL types without updating DataLoader batch functions.

Ship pg_stat_statements or APM database monitoring in prod — N+1 in production often differs from staging due to data volume; catch regressions where they hurt users.

Add database query count to your APM service maps — sudden edges between API and database with query count proportional to response list length visualize N+1 without reading code during incidents.

## Common production mistakes

Teams get n plus one detection wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Performance work on n plus one detection regresses when optimizations target p50 only, benchmarks run on laptops not production hardware, and flamegraphs are captured once then never compared after refactors.

## Debugging and triage workflow

When n plus one detection misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Rails strict loading guide](https://guides.rubyonrails.org/active_record_querying.html#strict-loading)
- [GraphQL DataLoader (Lee Byron)](https://github.com/graphql/dataloader)
- [Prisma relation queries optimization](https://www.prisma.io/docs/guides/performance-and-optimization/query-optimization-performance)
- [SQLAlchemy loading strategies](https://docs.sqlalchemy.org/en/20/orm/queryguide/relationships.html)
- [django-debug-toolbar SQL panel](https://django-debug-toolbar.readthedocs.io/)
