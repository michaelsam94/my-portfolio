---
title: "System Design: Ticketing System"
slug: "system-design-ticketing-booking"
description: "Designing a ticketing and booking system: inventory holds, overselling prevention, seat maps, payment integration, and handling flash-sale traffic spikes."
datePublished: "2025-11-21"
dateModified: "2026-07-17"
tags: ["System Design", "Backend", "Architecture", "Distributed Systems"]
keywords: "ticketing system design, seat reservation, inventory hold, concert ticket booking, overselling prevention, flash sale"
faq:
  - q: "How do ticketing systems prevent double booking?"
    a: "Use atomic inventory decrements with database constraints or distributed locks. The hold pattern reserves seats temporarily (5–15 minutes) while the user pays; confirmed booking converts the hold to a sale. Compare-and-swap on remaining count, or row-level locks on seat records, prevent two transactions from claiming the same seat."
  - q: "What is the difference between a hold and a confirmed booking?"
    a: "A hold is a temporary reservation that expires if payment is not completed — inventory is soft-locked. A confirmed booking is permanent after successful payment, with a ticket issued. Holds must TTL-expire and release inventory automatically via scheduled jobs or Redis key expiry callbacks."
  - q: "How do you handle flash sale traffic for popular events?"
    a: "Queue users before they hit inventory (virtual waiting room), serve holds from a pre-sharded inventory pool, cache event metadata aggressively, and decouple payment from seat selection when possible. Rate limit per user, use CDN for static seat maps, and load test the hold-confirm path at expected peak QPS."
faqAnswers:
  - question: "When is system design ticketing booking the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design ticketing booking?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design ticketing booking safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Ticketmaster opens sales for a stadium show. Two hundred thousand people hit refresh at 10:00:00 AM for eight thousand seats. The system must never sell seat 14-A twice, must expire abandoned carts before hoarders lock inventory, and must stay up when payment webhooks lag thirty seconds. Ticketing is inventory management under adversarial load with a clock.

## Core entities

```
Event ──< Section ──< Row ──< Seat
  │
  └── PricingTier (GA, VIP, early bird)

Hold (seat_id, user_id, expires_at, status)
Order (hold_ids[], payment_id, status)
Ticket (order_id, seat_id, barcode, status)
```

General admission simplifies to **pool counters** instead of per-seat maps: `GA_pool_remaining = 500`.

## The hold lifecycle

```
Available → Held (TTL) → Sold
                ↓
            Expired → Available
```

```sql
-- Pessimistic: lock seat row
BEGIN;
SELECT * FROM seats WHERE id = $1 AND status = 'available' FOR UPDATE;
UPDATE seats SET status = 'held', hold_expires_at = now() + interval '10 minutes'
  WHERE id = $1;
COMMIT;
```

Optimistic alternative for GA pools:

```sql
UPDATE ga_inventory
SET remaining = remaining - 1
WHERE event_id = $1 AND remaining > 0
RETURNING remaining;
```

Zero rows updated = sold out. Atomic decrement is the entire trick for counter-based inventory.

## Redis-backed holds for speed

Hot events push holds to Redis first, async sync to Postgres:

```redis
SET hold:evt-99:seat-14A user-42 EX 600 NX
```

`NX` fails if already held — instant conflict signal. Background worker persists holds to DB and reconciles. On payment success, promote to sold; on expiry, key vanishes and worker releases seat.

Trade-off: Redis/DB drift requires reconciliation jobs. Most high-scale ticket vendors accept eventual consistency with tight reconciliation.

## Seat map vs best-available

**Interactive seat map** — user picks exact seat. Requires per-seat state, vector map tiles CDN-cached, WebSocket or poll for seat status updates as others hold.

**Best available** — algorithm picks contiguous block. Faster checkout, fewer round trips, easier to shard inventory by section.

Many systems offer both; flash sales often default to best-available to reduce contention on individual seat rows.

## Payment integration

Never confirm ticket before payment clears:

```
1. Create hold
2. Redirect to payment / tokenize card
3. Payment webhook → confirm order → mark seats sold → emit tickets
4. Webhook failure / timeout → release hold
```

Idempotent webhook handling — Stripe may deliver twice. `order_id` uniqueness constraint and status state machine:

```
pending_payment → paid → fulfilled
               → failed → hold_released
```

## Virtual waiting room

When demand exceeds capacity by 10x, uncontrolled access creates thundering herd on inventory service. Queue layer (Queue-it, Cloudflare Waiting Room, custom):

1. User lands on event page → enters queue token
2. Queue admits N users/minute to purchase flow
3. Purchase flow receives signed token validating queue admission

Protects backend; does not guarantee tickets — sets expectations.

## Anti-abuse

- Per-account purchase limits
- CAPTCHA at queue entry
- Device fingerprinting for bot detection
- Resale market integration (optional) with transfer locks

## Failure modes

| Failure | Mitigation |
| --- | --- |
| Double sell | Atomic decrement, DB unique constraint on (event, seat) |
| Ghost holds | TTL + sweeper job |
| Payment success, DB fail | Outbox + reconciliation; manual support playbook |
| Hot row contention | Shard GA pools; section-level locks |

## Scale sketch

- 50k concurrent users in queue
- 5k holds/second peak
- Hold TTL 10 minutes → ~3M active hold records worst case (most expire fast)
- Postgres for source of truth; Redis for hot path

## Reporting and reconciliation

Nightly jobs compare sold seat count to venue capacity and flag discrepancies. Finance teams need immutable audit logs of price paid per seat — append-only order events, not mutable row overwrites. Support tooling to transfer tickets between accounts must re-validate availability and emit new barcode while invalidating old.

## Seat hold pattern

```sql
BEGIN;
SELECT * FROM seats WHERE id = $1 FOR UPDATE;
-- check available, insert hold with expiry
INSERT INTO holds (seat_id, user_id, expires_at) VALUES ($1, $2, NOW() + interval '10 minutes');
COMMIT;
```

Hold expires via cron — release seat if payment not completed. Never hold without TTL — ghost availability kills conversion.

## Metrics worth dashboarding

For ticketing booking, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Seat locking and double-booking prevention

Concert and airline booking share the same core problem: hold inventory during checkout with TTL. Optimistic locking on seat rows (`UPDATE seats SET status='held' WHERE id=? AND status='available'`) fails closed when zero rows updated. Display held seats as unavailable to other users immediately via WebSocket or short-poll on seat map. When hold expires, broadcast seat release so waiting users can grab released inventory — this creates burst traffic; rate-limit seat map refreshes per client.

## Payment timeout versus inventory hold

Hold TTL must exceed p99 payment completion time plus retry buffer — if Stripe checkout takes ninety seconds on mobile, a sixty-second hold guarantees double-booking complaints. Extend hold on payment-in-progress webhook, release on explicit cancel or timeout. Show countdown timer in UI synced to server hold expiry, not client clock.

## Resources

- [Ticketmaster architecture talks (InfoQ)](https://www.infoq.com/news/2014/06/ticketmaster/)
- [Stripe idempotent requests](https://stripe.com/docs/api/idempotent_requests)
- [Saga pattern for distributed transactions](https://microservices.io/patterns/data/saga.html)
- [AWS virtual waiting room pattern](https://aws.amazon.com/blogs/architecture/exploring-the-cloudfront-event-driven architecture/)
- [SELECT FOR UPDATE (PostgreSQL)](https://www.postgresql.org/docs/current/explicit-locking.html)

## system design ticketing booking rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ticketing booking rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ticketing booking rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ticketing booking rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design ticketing booking rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Trade-offs I keep revisiting for system design ticketing booking

System design interviews and production systems diverge: system design ticketing booking in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design ticketing booking:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |

## Ownership and on-call for system design ticketing booking

Reviewers should challenge assumptions encoded in system design ticketing booking: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for system design ticketing booking: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for system design ticketing booking: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for system design ticketing booking: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Rollout sequence that worked for system design ticketing booking

Roll out system design ticketing booking behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in system design ticketing booking

Detail 1 (769): for system design ticketing booking, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in system design ticketing booking becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design ticketing booking, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design ticketing booking: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for system design ticketing booking

Detail 2 (426): for system design ticketing booking, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for system design ticketing booking becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design ticketing booking, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design ticketing booking: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.