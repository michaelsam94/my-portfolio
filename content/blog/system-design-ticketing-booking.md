---
title: "System Design: Ticketing System"
slug: "system-design-ticketing-booking"
description: "Designing a ticketing and booking system: inventory holds, overselling prevention, seat maps, payment integration, and handling flash-sale traffic spikes."
datePublished: "2025-11-21"
dateModified: "2025-11-21"
tags: ["System Design", "Backend", "Architecture", "Distributed Systems"]
keywords: "ticketing system design, seat reservation, inventory hold, concert ticket booking, overselling prevention, flash sale"
faq:
  - q: "How do ticketing systems prevent double booking?"
    a: "Use atomic inventory decrements with database constraints or distributed locks. The hold pattern reserves seats temporarily (5–15 minutes) while the user pays; confirmed booking converts the hold to a sale. Compare-and-swap on remaining count, or row-level locks on seat records, prevent two transactions from claiming the same seat."
  - q: "What is the difference between a hold and a confirmed booking?"
    a: "A hold is a temporary reservation that expires if payment is not completed — inventory is soft-locked. A confirmed booking is permanent after successful payment, with a ticket issued. Holds must TTL-expire and release inventory automatically via scheduled jobs or Redis key expiry callbacks."
  - q: "How do you handle flash sale traffic for popular events?"
    a: "Queue users before they hit inventory (virtual waiting room), serve holds from a pre-sharded inventory pool, cache event metadata aggressively, and decouple payment from seat selection when possible. Rate limit per user, use CDN for static seat maps, and load test the hold-confirm path at expected peak QPS."
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

## Common production mistakes

Teams get ticketing booking wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for ticketing booking breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When ticketing booking misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Metrics worth dashboarding

For ticketing booking, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Resources

- [Ticketmaster architecture talks (InfoQ)](https://www.infoq.com/news/2014/06/ticketmaster/)
- [Stripe idempotent requests](https://stripe.com/docs/api/idempotent_requests)
- [Saga pattern for distributed transactions](https://microservices.io/patterns/data/saga.html)
- [AWS virtual waiting room pattern](https://aws.amazon.com/blogs/architecture/exploring-the-cloudfront-event-driven architecture/)
- [SELECT FOR UPDATE (PostgreSQL)](https://www.postgresql.org/docs/current/explicit-locking.html)
