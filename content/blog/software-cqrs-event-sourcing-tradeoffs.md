---
title: "When CQRS and Event Sourcing Pay Off"
slug: "software-cqrs-event-sourcing-tradeoffs"
description: "Evaluate CQRS and event sourcing honestly: read/write separation, event stores, projections, and problems they solve versus complexity they add."
datePublished: "2025-08-11"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "CQRS event sourcing tradeoffs, command query responsibility segregation, event store, read model projection, when to use event sourcing"
faq:
  - q: "Do I need event sourcing if I use CQRS?"
    a: "No. CQRS separates write models from read models; event sourcing persists state as a sequence of events instead of current row values. You can use CQRS with traditional CRUD writes projecting to read databases. Event sourcing adds auditability and temporal queries but increases storage, versioning, and operational complexity."
  - q: "What problems does event sourcing actually solve?"
    a: "Complete audit history, reconstructing state at any point in time, multiple read projections from one write stream, and debugging production by replaying events. It fits domains where history is legally significant—finance, healthcare—or where integrators need rich domain events. CRUD with updated_at solves most inventory dashboards fine."
  - q: "What is the biggest operational downside?"
    a: "Schema evolution on stored events—upcasting old event versions during replay—and rebuilding projections after bugs or new query requirements. Event store becomes critical infrastructure; backup and replay testing are mandatory. Team must think in events, not tables, across product and engineering."
---

The conference talk showed event sourcing like default architecture — every button click an immutable fact, read models materializing like magic. Six months later the team debugged why inventory projection lagged checkout by four minutes during peak. CQRS (Command Query Responsibility Segregation) and event sourcing solve specific pains: asymmetric read/write load, audit trails, and temporal reconstruction. They also introduce dual models, eventual consistency, and replay machinery. Use them when the business value exceeds the tax — not because DDD blogs said so.

## CQRS without event sourcing

```
Command → Write model (normalized DB)
              ↓ publish domain event
         Read model (denormalized Elasticsearch)
Query ← Read model only
```

Writes optimize for invariants; reads optimize for UI screens. Accept eventual consistency between models — display "processing" states honestly. You do **not** need an event store to separate read and write schemas — many teams publish domain events from CRUD writes without storing events as source of truth.

## Event sourcing core loop

```python
def handle(cmd: PlaceOrder):
    order = Order.create(cmd)
    events = order.pull_uncommitted_events()
    event_store.append(stream_id=order.id, events=events)
    publish(events)
```

State equals fold(events). Snapshots optional for long streams — rebuild aggregate from snapshot plus events after snapshot version.

## When the tradeoff favors ES/CQRS

| Signal | Fit |
|--------|-----|
| Regulatory audit of every change | Strong |
| Multiple read views same writes | Strong |
| Complex domain with rich behavior | Moderate |
| Simple CRUD admin | Weak |
| Strong immediate read-your-writes everywhere | Weak |

## Projection rebuild operations

Bug in projector? Fix code, reset checkpoint, replay from offset — or rebuild read DB from scratch. Automate replay in staging on every release. Document RPO for projection lag; alert when lag exceeds business tolerance (inventory display stale while warehouse knows truth).

Full replay duration estimate belongs in runbook — "8 hours for 400M events" changes on-call response when projector corrupts.

## Command handling idempotency

Commands carry `command_id`; dedupe at aggregate level. Retries are normal with at-least-once messaging. Without idempotency, duplicate `PlaceOrder` commands double-charge or double-ship.

## Schema evolution and upcasting

Event schema version 3 must upcast versions 1 and 2 during replay. Store event type name and version in envelope; upcasters are code you maintain forever. Breaking changes without upcasters brick replay — treat event schemas like public API.

## When CQRS is overkill

CRUD with one read model and moderate traffic rarely needs event sourcing complexity. CQRS pays off when read and write shapes diverge sharply, audit history is mandatory, or temporal queries ("balance as of date") are core requirements.

## Avoid distributed monolith

CQRS across fourteen microservices without bounded context discipline creates chatty command buses. Start modular monolith with in-process handlers; extract when scaling proves need. Every network hop adds failure modes — do not pay the tax before load requires it.

## Hybrid path

Event source **Order** aggregate only; **Customer** stays CRUD. Not every table earns a stream. Choose per aggregate based on audit and projection needs, not globally.

## Read model eventual consistency UX

Users who submit form expect immediate feedback — write model confirms; read model may lag milliseconds to seconds. Show "confirmed" from write response; do not read-your-writes from Elasticsearch if lag exists unless synchronously updated cache layer handles it.

## Event store backup and replay testing

Event store is critical infrastructure — backup like primary database. Quarterly restore drill replays into empty projection environment and compares checksums to production read models.

## Operational metrics

Monitor: projection lag histogram, replay queue depth, command handler error rate, event store append latency. Page on lag SLO breach before users see stale dashboards.

CQRS and event sourcing are powerful where history, audit, and read/write asymmetry dominate — expensive everywhere else. Start with one aggregate, prove replay and projection ops, then expand.

## Saga versus event sourcing

Distributed sagas orchestrate commands across services with compensations — different from event sourcing within one aggregate. Teams confuse them — saga state machines can use event sourcing internally, but not every saga step needs global event store.

## Testing projections

Golden file tests: given event sequence fixture, assert read model output JSON. Run in CI on every projector change. Property-based tests generate random valid event sequences and assert invariants (balance never negative).

## Debugging production with event replay

Replay production events into staging projector sandbox to reproduce bug without touching production read DB. Mask PII in event export — GDPR limits full replay to sanitized subsets.

## Cost of event storage

Event store storage grows unbounded — snapshot aggregates and archive cold streams to object storage with retention policy. Billing team needs storage growth projection before signing multi-year event sourcing commitment.

## Team skill requirements

Event sourcing requires developers comfortable with async messaging, idempotency, and versioned schemas — plan training budget. CRUD teams forced into ES without coaching produce anemic events (`OrderUpdated` with full DTO dump).

## Comparison to change data capture

CDC from database binlog projects read models without event sourcing write path — valid CQRS shortcut when write model stays relational. Tradeoff: events reflect row changes, not domain intent — audit narrative weaker.

Choose CQRS and event sourcing when the business pays for auditability and projection flexibility — not because your conference badge says DDD.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (4)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (5)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Projection versioning

Tag projection code with version — store `projectionVersion` in read model metadata. Mixed versions during deploy detected by integration test comparing event replay output to golden CSV.

## Operational metrics

Track projection lag seconds behind event stream head — alert when lag exceeds SLO during peak checkout; consumers may read stale inventory counts.

## Snapshot cadence

Snapshot aggregates every N events or T minutes — balance replay time against snapshot storage growth.
