---
title: "The Strangler Fig Migration"
slug: "microservices-strangler-fig-migration"
description: "Migrate monoliths to microservices incrementally with the strangler fig pattern: routing layers, feature flags, and risk-controlled extraction."
datePublished: "2025-06-21"
dateModified: "2025-06-21"
tags: ["BE", "Microservices", "Migration", "Architecture"]
keywords: "strangler fig pattern, monolith to microservices migration, incremental migration, legacy system modernization, anti-corruption layer, monolith decomposition"
faq:
  - q: "How long does a strangler fig migration typically take?"
    a: "Most organizations take 18–36 months to migrate a medium-sized monolith, extracting 1–3 bounded contexts per quarter. The monolith keeps running throughout — there is no big-bang cutover. Timeline depends on team size, test coverage in the monolith, and how tightly coupled the domains are."
  - q: "Which part of the monolith should I extract first?"
    a: "Start with a bounded context that is relatively isolated, has clear boundaries, and delivers visible business value when independent. Payment processing, notification delivery, and search are common first candidates. Avoid starting with the core domain — it has the most coupling."
  - q: "How do I prevent the monolith and new services from diverging?"
    a: "Use an anti-corruption layer at each extraction boundary to translate between the monolith's data model and the new service's model. Share nothing — no shared database tables, no shared libraries with domain logic. Sync data via events, not direct queries."
---

The board approved microservices. Engineering estimated 18 months for a full rewrite. Twelve months in, the rewrite is 40% done, the monolith still runs production, and now you maintain two systems with duplicated logic and diverging data models.

The strangler fig pattern avoids this. Named after the tropical fig that grows around a host tree and eventually replaces it, the pattern wraps the monolith with a routing layer and incrementally redirects traffic to new services — one bounded context at a time. The monolith shrinks until nothing remains.

## How the pattern works

```
Phase 1: All traffic → Monolith
Phase 2: /payments/* → Payment Service, everything else → Monolith
Phase 3: /payments/* → Payment Service, /notifications/* → Notification Service, rest → Monolith
Phase N: All traffic → Microservices, monolith decommissioned
```

The routing layer (API gateway, reverse proxy, or service mesh) decides where each request goes. New features are built as microservices from day one. Existing features are extracted one at a time.

## Step 1: Identify bounded contexts

Map the monolith's domains before writing any code:

```
Monolith
├── User Management (registration, profiles, auth)
├── Catalog (products, categories, search)
├── Orders (cart, checkout, order history)
├── Payments (charging, refunds, billing)
├── Notifications (email, SMS, push)
└── Reporting (analytics, exports)
```

Assess coupling between contexts:

| Context | Coupling to others | Extract priority |
|---------|-------------------|-----------------|
| Notifications | Low (async, event-driven) | High — first candidate |
| Payments | Medium (called by Orders) | High — clear boundary |
| Catalog | Medium (read by many) | Medium |
| Orders | High (calls Payments, Catalog) | Later |
| User Management | High (used everywhere) | Last |

## Step 2: Build the routing layer

An API gateway or reverse proxy routes requests:

```nginx
# nginx routing during migration
location /api/v2/notifications/ {
    proxy_pass http://notification-service:8080/;
}

location /api/v2/payments/ {
    proxy_pass http://payment-service:8080/;
}

location /api/ {
    proxy_pass http://monolith:8080/;  # everything else
}
```

Feature flags provide finer control:

```python
def route_request(path: str, user_id: str):
    if path.startswith("/notifications") and feature_flags.is_enabled("notifications-v2", user_id):
        return notification_service.handle(path)
    if path.startswith("/payments") and feature_flags.is_enabled("payments-v2", user_id):
        return payment_service.handle(path)
    return monolith.handle(path)
```

Roll out to internal users first, then 5%, 25%, 100% of traffic.

## Step 3: Extract with an anti-corruption layer

When extracting notifications from the monolith:

```python
# Anti-corruption layer: translates monolith events to notification service format
class NotificationACL:
    def handle_monolith_order_event(self, event: dict):
        notification = NotificationRequest(
            user_id=event["customer_id"],  # monolith calls it customer_id
            template="order_confirmation",
            data={
                "order_number": event["order_num"],  # monolith format
                "total": Decimal(event["total_cents"]) / 100,
            },
            channel=self._map_channel(event["notify_via"]),  # "email" → Channel.EMAIL
        )
        self.notification_service.send(notification)
```

The ACL absorbs the monolith's quirks so the new service can have a clean domain model.

## Step 4: Data migration strategies

Extracted services need their own data store:

**Dual-write period:** write to both monolith DB and new service DB during transition.

```python
def create_notification(data):
    # Write to new service
    notification_service.create(data)
    # Also write to monolith (temporary)
    if migration_config.dual_write_enabled:
        monolith_db.insert("notifications", to_monolith_format(data))
```

**Event-driven sync:** monolith publishes events; new service consumes and builds its own data.

```python
# Monolith publishes (add to existing code)
event_bus.publish("notification.created", notification_data)

# New service consumes
@event_handler("notification.created")
def sync_notification(event):
    notification_repo.upsert(from_monolith_event(event))
```

**Read migration:** new service reads from monolith DB initially, migrates to its own DB over time. Highest risk — avoid if possible.

## Step 5: Decommission the monolith module

Once a bounded context is fully extracted and verified:

1. Confirm 100% traffic routes to the new service (check gateway metrics).
2. Remove the monolith code for that context.
3. Drop the monolith database tables (after backup and verification period).
4. Remove the ACL — direct communication replaces translation.

Repeat for each bounded context. The monolith shrinks with each extraction.

## Measuring migration progress

Track:
- **Traffic percentage** routed to new services vs. monolith.
- **Monolith codebase size** (lines of code, number of modules remaining).
- **Dual-write lag** (data consistency between monolith and new service).
- **Incident rate** in extracted services vs. monolith baseline.

A healthy migration shows monolith traffic decreasing steadily while new service traffic increases, with no spike in error rates during cutover.

## Strangler routing layer

```
API Gateway → legacy monolith (default)
            → new service (if route in migration list)
```

Migrate route-by-route. Shared database initially — extract schema last. Feature flags control traffic split per route.

## Common production mistakes

Teams get strangler fig migration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of strangler fig migration fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When strangler fig migration misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Martin Fowler: Strangler Fig Application](https://martinfowler.com/bliki/StranglerFigApplication.html)
- [Sam Newman: Monolith to Microservices](https://samnewman.io/books/monolith-to-microservices/)
- [Anti-Corruption Layer pattern (Microsoft)](https://learn.microsoft.com/en-us/azure/architecture/patterns/anti-corruption-layer)
- [Feature flags for migration (LaunchDarkly)](https://docs.launchdarkly.com/
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
