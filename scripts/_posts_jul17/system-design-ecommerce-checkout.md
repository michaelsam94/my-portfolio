---
title: "System Design: E-Commerce Checkout"
slug: "system-design-ecommerce-checkout"
description: "Design a scalable checkout: cart consistency, inventory reservation, payment orchestration, idempotency, and failure recovery across distributed services."
datePublished: "2026-02-14"
dateModified: "2026-07-17"
tags: ["System Design", "E-Commerce", "Architecture", "Backend"]
keywords: "ecommerce checkout design, cart service, inventory reservation, payment orchestration, idempotent checkout"
faq:
  - q: "Why separate cart, inventory, and payment into distinct services?"
    a: "Each domain has different consistency requirements and failure modes. Carts tolerate eventual consistency; inventory needs short-lived reservations with TTL; payments require strong idempotency and PCI scope isolation. Coupling them in one monolith simplifies early development but creates cascading failures when payment webhooks retry or inventory oversells during flash sales."
  - q: "How long should inventory reservations last during checkout?"
    a: "Typical TTL is 10–15 minutes, aligned with session timeout. Reservations decrement available stock without finalizing the sale until payment succeeds. Expired reservations return stock via a background sweeper. Too short frustrates users on slow 3DS flows; too long locks inventory during abandoned carts."
  - q: "What idempotency strategy prevents double charges?"
    a: "Clients send Idempotency-Key on POST /checkout. The API stores key → response mapping in Redis or Postgres for 24 hours. Retries with the same key return the original order ID without re-calling the payment provider. Payment provider calls use their idempotency keys as a second layer."
---

Black Friday checkout p99 hit 45 seconds because we treated checkout as a single database transaction spanning cart, inventory, tax, shipping quotes, and Stripe. One slow shipping carrier API blocked every payment. We decomposed into orchestrated sagas with compensating actions: reserve inventory, authorize payment, capture on fulfillment trigger. Failed payments released reservations automatically. Conversion recovered 12% because users stopped seeing spinner-of-death at the card step.

## Checkout as an explicit state machine

Checkout progresses through discrete states with allowed transitions:

```
CART_VALIDATED → ADDRESS → SHIPPING → PAYMENT → AUTHORIZED → CONFIRMED
                      ↓                      ↓
                  ABANDONED              FAILED (release stock)
```

Persist state in a `checkout_sessions` table so refreshes and back-button navigation resume correctly. Never rely on client-only cart state for payment amounts — server recomputes totals before every charge.

```python
class CheckoutState(Enum):
    CART_VALIDATED = 10
    INVENTORY_RESERVED = 40
    PAYMENT_AUTHORIZED = 50
    CONFIRMED = 60
    FAILED = 99
```

Illegal transitions return `409 Conflict` with current state — clients poll or resume rather than retry blindly.

## Cart service and price consistency

Cart items store SKU, quantity, and **price snapshot** at add-to-cart time. Revalidate on checkout start: if catalog price changed, show diff and require acknowledgment. Promotions apply via a pricing engine that returns line-level adjustments with rule IDs for audit.

```json
{
  "cart_id": "crt_8f2a",
  "lines": [
    { "sku": "SKU-441", "qty": 2, "unit_price_cents": 2999, "price_version": "pv_102" }
  ],
  "currency": "USD"
}
```

Separate read-heavy cart browsing (Redis or DynamoDB) from write-heavy checkout (Postgres for completed orders).

## Inventory reservation without overselling

Soft reservation on "Proceed to payment":

```sql
BEGIN;
SELECT quantity, reserved FROM inventory WHERE sku = $1 FOR UPDATE;
UPDATE inventory SET reserved = reserved + $qty WHERE sku = $1;
INSERT INTO reservations (id, sku, qty, checkout_id, expires_at)
VALUES ($id, $1, $qty, $checkout_id, now() + interval '15 minutes');
COMMIT;
```

Background sweeper releases expired reservations. Payment success converts reservation to committed decrement; failure releases.

| Approach | Pros | Cons |
| --- | --- | --- |
| Pessimistic lock | Strong consistency | Contention on hot SKUs |
| Optimistic + retry | High throughput | User-visible retry |
| Partition by warehouse | Parallel hot SKUs | Split shipments |

## Payment orchestration and PCI scope

Never store raw PANs. Tokenize client-side with Stripe Elements; server receives payment method tokens only.

```python
async def authorize_payment(checkout: Checkout):
    result = await stripe.payment_intents.create(
        amount=checkout.total_cents,
        currency=checkout.currency,
        idempotency_key=f"checkout-{checkout.id}-auth",
        capture_method="manual",
    )
    checkout.payment_intent_id = result.id
    checkout.state = CheckoutState.PAYMENT_AUTHORIZED
```

Physical goods: authorize at checkout, capture at shipment. Digital goods: authorize and capture immediately.

## Webhook idempotency

```sql
INSERT INTO processed_events (event_id) VALUES ($1)
ON CONFLICT (event_id) DO NOTHING RETURNING event_id;
```

Process side effects only after insert succeeds. Do not confirm order on client-side success alone — webhooks can arrive late or duplicate.

## Saga compensations

| Failure at | Compensation |
| --- | --- |
| Payment auth fails | Release inventory reservation |
| Order creation fails | Void payment, release inventory |
| Capture fails | Retry capture; alert if auth expiring |

```python
async def compensate(checkout: Checkout, failed_step: str):
    if checkout.state >= CheckoutState.INVENTORY_RESERVED:
        await release_inventory(checkout)
    if checkout.state >= CheckoutState.PAYMENT_AUTHORIZED:
        await stripe.payment_intents.cancel(checkout.payment_intent_id)
    checkout.state = CheckoutState.FAILED
```

Use transactional outbox for `checkout.confirmed` events — write outbox row in same DB transaction as order insert.

## Idempotency throughout

Every external call carries idempotency key derived from `checkout_id + step`. Clients generate UUID Idempotency-Key per checkout attempt. Payment provider keys form a second layer.

## Tax, shipping, and fraud

Store tax and shipping quote IDs with TTL on checkout session; revalidate before capture. Pre-auth fraud check runs before payment authorize — high-risk orders route to manual review without capturing payment.

## Guest checkout and account linking

Guest checkout avoids registration friction. Email serves as correlation ID; post-purchase magic link offers account creation with order history import.

## Handling partial failures at scale

**Inventory service down:** Fail checkout with retry guidance — do not accept payment without reservation.

**Payment gateway timeout:** Leave checkout in `PAYMENT_PENDING`; reconciliation job polls gateway status.

**Split shipment:** Partial reservation success reserves available qty; offer backorder or split checkout.

## Observability and business metrics

Track funnel conversion at each state transition. Alert on compensation rate spike, reservation expiry rate, and webhook processing lag. Load test full saga at 3× expected peak including 3DS latency simulation.

## Order confirmation and downstream fulfillment

Emit `order.confirmed` through transactional outbox. Fulfillment, warehouse management, and email services consume the event asynchronously — checkout API returns confirmation without waiting for shipping label generation.

## Pricing engine and promotion stacking

The pricing engine evaluates rules server-side on every checkout start. Line-level adjustments carry `promotion_id` and `rule_version` for finance audit. When multiple promotions apply, precedence is explicit:

```
1. Employee discount (non-stackable)
2. Cart-level coupon
3. Line-item automatic promotions
```

Never trust client-calculated discount totals. Store computed totals on the checkout session record and revalidate before payment capture.

## 3DS and payment latency

Strong Customer Authentication adds 5–30 seconds to checkout. Inventory reservation TTL must exceed worst-case 3DS flow plus user distraction. Monitor `AUTHORIZED → CONFIRMED` latency separately from `PAYMENT → AUTHORIZED` — webhook delays masquerade as payment failures if you only watch client-side callbacks.

## Reconciliation jobs

Nightly reconciliation compares payment provider ledger against internal orders table. Orphaned payments (captured, no order) trigger automatic order creation or refund based on policy. Orphaned reservations (expired, payment succeeded) alert ops — indicates webhook handler failure or idempotency bug.

## PCI scope reduction

Tokenize client-side; server never sees PAN. Checkout service runs in PCI-scoped network segment with minimal egress. Logging must redact payment method identifiers. Quarterly ASV scans cover the cardholder data environment boundary — keep it as small as possible.

## Flash sale capacity planning

Hot SKU inventory contention requires partition by warehouse and queue-based reservation retry with exponential backoff. Rate-limit checkout initiation per user to prevent bot hoarding. Pre-warm payment provider connection pools before known sale events.

## Multi-currency and tax jurisdictions

Store currency on checkout session at initiation — do not convert mid-flow without user acknowledgment. Tax calculation uses address snapshot; shipping address change invalidates tax quote and requires recomputation before capture.

## Load testing checkout sagas

Simulate 3× peak with realistic 3DS latency injection. Measure p99 per saga step — inventory reservation, payment auth, order creation. Bottleneck at shipping quote API should not block payment step after decomposition.

## Abandoned cart recovery

Expired reservations return inventory automatically. Marketing systems consume `checkout.abandoned` events with cart snapshot for email recovery — separate from order confirmation flow. Do not hold reservations for marketing follow-up.

## Split payments and gift cards

Gift card balance application is a separate saga step before payment provider charge. Partial gift card + card payment requires two-phase commit semantics — void gift card hold if card payment fails.

## Audit trail for finance

Every price change, promotion application, and tax quote stores rule ID and timestamp on checkout record. Finance reconciliation exports checkout sessions — not just completed orders — for promotion liability reporting.

## International shipping and duties

Cross-border checkout adds duties estimation as separate quote step with its own TTL. Duties quote invalidation on address change follows same pattern as tax quote — revalidate before capture. Customs documentation generated at order confirmation, not at cart add.

## Subscription and recurring checkout

Recurring billing uses stored payment method with separate idempotency namespace — `subscription-{id}-cycle-{n}`. Failed renewal retries with exponential backoff; do not reuse checkout session idempotency keys across billing cycles.

## Checkout session TTL and cleanup

Checkout sessions expire after 30 minutes of inactivity — background job marks ABANDONED and releases any held reservations. TTL aligned with inventory reservation TTL prevents orphaned holds from abandoned payment flows.

## Resources

- [Stripe idempotent requests](https://stripe.com/docs/api/idempotent_requests)
- [Saga pattern — microservices.io](https://microservices.io/patterns/data/saga.html)
- [Transactional outbox pattern](https://microservices.io/patterns/data/transactional-outbox.html)
