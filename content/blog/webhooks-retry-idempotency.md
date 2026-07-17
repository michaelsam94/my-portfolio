---
title: "Webhook Retries and Idempotency"
slug: "webhooks-retry-idempotency"
description: "Build reliable webhook delivery with retry strategies, exponential backoff, idempotency keys, dead letter queues, and receiver-side deduplication."
datePublished: "2026-05-24"
dateModified: "2026-07-17"
tags: ["Backend", "Webhooks", "Reliability", "API"]
keywords: "webhook retry, idempotency, exponential backoff, dead letter queue, webhook delivery, at-least-once"
faq:
  - q: "Why do webhooks need retry logic?"
    a: "Webhook receivers go down, return 503, hit rate limits, or take too long to respond. Without retries, events are lost permanently. At-least-once delivery requires retrying failed deliveries until the receiver acknowledges success with a 2xx response. Most webhook providers retry over hours or days with increasing intervals."
  - q: "How does idempotency prevent duplicate webhook processing?"
    a: "Retries mean the same event may arrive multiple times. Idempotency keys — usually the event ID — let receivers detect and skip duplicates. The sender includes a unique event ID in every payload. The receiver stores processed IDs and rejects or ignores events it has already handled. Without this, a retried payment webhook could charge a customer twice."
  - q: "What HTTP status codes should webhook receivers return?"
    a: "Return 2xx (200, 201, 204) to acknowledge successful processing and stop retries. Return 4xx (except 429) for permanent failures the sender should not retry — invalid payload, unknown event type. Return 429 or 5xx for temporary failures that should trigger retry. Never return 2xx before processing completes — the sender will not retry after a success response."
---
A payment webhook fired three times because our endpoint returned 200 before the database transaction committed. The first attempt timed out at the gateway, Stripe retried, and we processed the same `payment_intent.succeeded` event twice — double-shipping an order. Fixing the response timing and adding idempotency checks on event ID took one day and prevented every duplicate since.

## Delivery architecture

```
Event occurs → Queue → Delivery worker → HTTP POST → Receiver
                ↑                              |
                └── Retry scheduler ←── 4xx/5xx/timeout
                         |
                    Dead letter queue (max retries exceeded)
```

Never deliver webhooks synchronously from the event handler. Queue events and deliver asynchronously.

## Retry schedule

Exponential backoff with jitter:

```python
RETRY_SCHEDULE = [
    60,       # 1 minute
    300,      # 5 minutes
    1800,     # 30 minutes
    7200,     # 2 hours
    36000,    # 10 hours
    86400,    # 24 hours
]

def schedule_retry(delivery, attempt):
    if attempt >= len(RETRY_SCHEDULE):
        move_to_dead_letter(delivery)
        return

    base_delay = RETRY_SCHEDULE[attempt]
    jitter = random.uniform(0, base_delay * 0.1)
    delay = base_delay + jitter

    delivery.retry_at = now() + timedelta(seconds=delay)
    delivery.attempt = attempt + 1
    queue.enqueue(delivery, delay=delay)
```

| Attempt | Delay | Cumulative |
|---|---|---|
| 1 | 1 min | 1 min |
| 2 | 5 min | 6 min |
| 3 | 30 min | 36 min |
| 4 | 2 hours | ~2.5 hours |
| 5 | 10 hours | ~12.5 hours |
| 6 | 24 hours | ~36.5 hours |

## Sender-side idempotency

Each event gets a unique, immutable ID:

```json
{
  "id": "evt_20260524_001",
  "type": "payment.completed",
  "created_at": "2026-05-24T10:30:00Z",
  "data": {
    "payment_id": "pay_123",
    "amount": 4999,
    "currency": "usd"
  }
}
```

Store delivery attempts per event ID:

```sql
CREATE TABLE webhook_deliveries (
  id          UUID PRIMARY KEY,
  event_id    TEXT NOT NULL,
  endpoint_id UUID NOT NULL,
  attempt     INT DEFAULT 1,
  status      TEXT DEFAULT 'pending',
  response_code INT,
  retry_at    TIMESTAMPTZ,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE(event_id, endpoint_id, attempt)
);
```

## Receiver-side deduplication

```python
@app.post("/webhooks/payments")
async def handle_payment_webhook(request: Request):
    payload = await request.json()
    event_id = payload["id"]

    # Check if already processed
    if await redis.exists(f"webhook:processed:{event_id}"):
        return Response(status_code=200)

    # Verify signature first (before any processing)
    verify_signature(request.headers, await request.body())

    # Process the event
    await process_payment_event(payload)

    # Mark as processed (TTL covers retry window)
    await redis.set(f"webhook:processed:{event_id}", "1", ex=86400 * 3)

    return Response(status_code=200)
```

Return 200 for duplicates — tell the sender to stop retrying.

## Idempotent processing

Make handlers safe to replay:

```python
async def process_payment_event(payload):
    payment_id = payload["data"]["payment_id"]

    async with db.transaction():
        existing = await db.orders.find_by_payment_id(payment_id)
        if existing:
            return existing  # already processed

        order = await db.orders.create(
            payment_id=payment_id,
            amount=payload["data"]["amount"],
            status="paid",
        )
        await fulfillment.queue(order.id)
        return order
```

Use database unique constraints as a safety net:

```sql
ALTER TABLE orders ADD CONSTRAINT unique_payment_id UNIQUE (payment_id);
```

## Dead letter queue

After max retries, move to DLQ for manual investigation:

```python
def move_to_dead_letter(delivery):
    db.dead_letter_queue.insert({
        "event_id": delivery.event_id,
        "endpoint": delivery.endpoint_url,
        "payload": delivery.payload,
        "attempts": delivery.attempt,
        "last_error": delivery.last_error,
        "failed_at": now(),
    })
    alert_ops(f"Webhook delivery failed after {delivery.attempt} attempts")
```

Provide a dashboard for replaying DLQ events after fixing receiver issues.

## Monitoring

Track these metrics:

- Delivery success rate (target: > 99%)
- P50/P95 delivery latency
- Retry rate per endpoint
- DLQ depth
- Duplicate detection rate

Alert when any endpoint's success rate drops below 95% over a one-hour window.

## Endpoint health scoring

Track success rate per endpoint over rolling windows. Automatically disable endpoints below 50% success for one hour — stop wasting retries on permanently broken URLs. Notify the endpoint owner with the failure reason and last successful delivery timestamp.

## Payload size limits

Cap webhook payload size at 256KB. Larger events should include a URL to fetch full data. Receivers timeout on large payloads; retries compound the problem.

## Resources

- [Stripe webhook best practices](https://docs.stripe.com/webhooks/best-practices)
- [GitHub webhook delivery docs](https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks)
- [Webhook delivery patterns (Hookdeck)](https://hookdeck.com/webhooks/guides)
- [Idempotency keys (Stripe)](https://docs.stripe.com/api/idempotent_requests)
- [AWS EventBridge retry policy](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-rule-dlq.html)

## Operational checklist (1)

Before promoting Webhooks Retry Idempotency changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Webhooks Retry Idempotency after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Webhooks Retry Idempotency touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Webhooks Retry Idempotency changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Webhooks Retry Idempotency after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Webhooks Retry Idempotency touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Webhooks Retry Idempotency changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Capacity and cost notes for webhooks retry idempotency

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct webhooks retry idempotency changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for webhooks retry idempotency |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for webhooks retry idempotency

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most webhooks retry idempotency regressions before production.

Concrete probe 2: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around webhooks retry idempotency

Most incidents involving webhooks retry idempotency start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for webhooks retry idempotency |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for webhooks retry idempotency

Name three invariants that must hold after every deploy of webhooks retry idempotency. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 4: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for webhooks retry idempotency

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to webhooks retry idempotency, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for webhooks retry idempotency |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for webhooks retry idempotency

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for webhooks retry idempotency should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 6: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for webhooks retry idempotency

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how webhooks retry idempotency breaks without a clear owner in the incident channel.

| Check | Expected for webhooks retry idempotency |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for webhooks retry idempotency in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
