---
title: "RabbitMQ Dead Letter Exchange"
slug: "queue-rabbitmq-dead-letter-exchange"
description: "DLX routing for poison messages — TTL queues and retry count headers."
datePublished: "2026-03-17"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "rabbitmq dead letter exchange, DLX, poison message, retry queue TTL"
faq:
  - q: "When does RabbitMQ send a message to a dead letter exchange?"
    a: "When a message is rejected (basic.reject/basic.nack) with requeue=false, expires per-message TTL, or is dropped because the queue exceeded max-length — and the queue declares x-dead-letter-exchange. Without DLX, rejected messages disappear or requeue infinitely."
  - q: "How do I implement delayed retry with DLX and TTL?"
    a: "Create a retry queue with x-message-ttl and x-dead-letter-exchange pointing back to the main exchange. Failed messages publish to retry queue, sit until TTL expires, then dead-letter back to main queue for reprocessing. Increment x-death count header to cap attempts."
  - q: "What is stored in the x-death header?"
    a: "An array of death records: reason (rejected, expired, maxlen), queue name, exchange, routing-keys, time, and count. Use it to implement max retry — when count exceeds threshold, route to manual DLQ instead of retry queue."
---

A payment webhook consumer threw on malformed JSON from one merchant integration — and requeued forever, blocking the entire queue because prefetch held the poison message at the head. Switching to `nack(requeue=False)` with a dead letter exchange routed bad payloads to a quarantine queue, preserved the original body for debugging, and let healthy merchants flow. DLX is RabbitMQ's escape hatch from infinite pain loops.

## Dead letter mechanics

Queue arguments:

```python
channel.queue_declare(
    queue='webhooks.main',
    arguments={
        'x-dead-letter-exchange': 'webhooks.dlx',
        'x-dead-letter-routing-key': 'failed',
    },
)
channel.exchange_declare('webhooks.dlx', exchange_type='direct', durable=True)
channel.queue_declare('webhooks.dlq', durable=True)
channel.queue_bind('webhooks.dlq', 'webhooks.dlx', routing_key='failed')
```

Three death reasons RabbitMQ records:

| Reason | Trigger |
|--------|---------|
| `rejected` | nack/reject with requeue=false |
| `expired` | per-message or queue TTL exceeded |
| `maxlen` | queue length limit dropped message |

## Poison message handling

```python
def on_message(ch, method, properties, body):
    try:
        event = json.loads(body)
        process(event)
        ch.basic_ack(method.delivery_tag)
    except json.JSONDecodeError:
        ch.basic_nack(method.delivery_tag, requeue=False)  # → DLX
    except TransientAPIError:
        ch.basic_nack(method.delivery_tag, requeue=True)
    except PermanentError:
        ch.basic_nack(method.delivery_tag, requeue=False)
```

**Never** nack poison with `requeue=True` — infinite hot loop.

## TTL retry queue pattern

```
main.queue ──fail──► retry.30s.queue (TTL=30000ms, DLX=main.exchange)
                           │
                      (wait 30s)
                           │
                           └──dead-letter──► main.queue
```

```python
channel.queue_declare(
    queue='webhooks.retry.30s',
    arguments={
        'x-message-ttl': 30000,
        'x-dead-letter-exchange': 'webhooks.main',
        'x-dead-letter-routing-key': 'process',
    },
)
```

## Counting retries with x-death

```python
def death_count(properties):
    if not properties.headers or 'x-death' not in properties.headers:
        return 0
    return sum(d.get('count', 0) for d in properties.headers['x-death'])

def on_message(ch, method, properties, body):
    if death_count(properties) >= 5:
        ch.basic_publish(exchange='webhooks.dlx', routing_key='poison', body=body)
        ch.basic_ack(method.delivery_tag)
        return
    try:
        process(body)
        ch.basic_ack(method.delivery_tag)
    except RetryableError:
        ch.basic_nack(method.delivery_tag, requeue=False)
```

## Exponential backoff tiers

Multiple retry queues with increasing TTL: `retry.10s` → `retry.60s` → `retry.300s` → `dlq.final`. Or use **rabbitmq_delayed_message_exchange** plugin for cleaner single-queue delay scheduling.

## DLQ monitoring and reprocessing

Dashboard metrics: `dlq.depth`, `x-death.reason` breakdown, age of oldest DLQ message.

Reprocessing: fix bug, sample DLQ messages, shovel in batches, monitor error rate.

## DLX vs alternate exchange

**Alternate exchange** catches unroutable publishes — publisher misconfiguration.

**DLX** handles consumer-side rejection and TTL — processing failures.

Use both.

## Quorum queues and DLX

Quorum queues support DLX arguments; test TTL and maxlen under quorum in staging before migrating payment queues.

## Shovel plugin for DLQ reprocessing

```json
{
  "src-queue": "webhooks.dlq",
  "dest-queue": "webhooks.main",
  "ack-mode": "on-confirm"
}
```

Throttle with `src-prefetch-count` to avoid overwhelming consumer pool.

## Publisher confirms and DLX together

Publisher confirms ensure message reached broker before API returns 200. DLX handles consumer-side failure — both layers needed for checkout webhooks.

## Security: DLQ payload inspection

DLQ messages contain full failure context — restrict queue read permissions. PII in DLQ requires retention policy aligned with GDPR.

Dead letter exchanges turn "stuck forever" into a structured lifecycle: fail fast to DLX, delay through TTL retry queues, count attempts via `x-death`, and land in human triage DLQ when automation gives up. Wire monitoring on DLQ depth, cap retries, and rehearse reprocessing before Black Friday — not during it.

## Per-message TTL vs queue TTL

Per-message TTL in properties overrides queue default — useful when retry backoff varies by error type without creating dozen TTL queues. Header `expiration` in milliseconds on publish; dead-letter to same retry exchange with different routing keys per delay tier.

## Federated DLQ across regions

Multi-region active-active may federate DLQ to central triage region — messages dead-lettered in EU route to global DLQ via shovel for support team in one timezone. Mind data residency — GDPR may forbid moving DLQ body across border without scrubbing.

## Monitoring with rabbitmq_prometheus

Export `rabbitmq_queue_messages{queue="webhooks.dlq"}` and alert rate of change. Sudden drop without deploy indicates accidental purge — audit management API access.

## Consumer prefetch and DLX interaction

Prefetch 100 with poison message at head blocks 99 unprocessed deliveries until nack — lower prefetch on queues without DLX configured turns poison into fast fail. With DLX, prefetch 10-50 balances throughput and poison isolation.

## Testing DLX chain in CI

Testcontainers RabbitMQ with declared DLX — publish malformed message, assert lands in DLQ within timeout. Regression test prevents deploy that removes `x-dead-letter-exchange` argument from queue declaration.

## DLX with priority queues

Priority queue with DLX preserves priority on dead-letter if target queue supports priority — otherwise DLQ receives default priority zero. Normalize priority on retry publish from DLQ consumer when reprocessing.

## Management API purge accidents

Purge DLQ via management UI without backup destroys forensic evidence — require two-person rule or disable purge in prod RBAC. Export DLQ to S3 before bulk reprocess for audit trail.

## HTTP webhook consumer ack timing

Ack only after downstream HTTP 2xx — premature ack before response body processed loses message on process crash after ack. With DLX, nack on timeout routes to retry; align consumer timeout with partner SLA.

## DLX routing key conventions

Use routing keys `retry.30s`, `poison`, `exhausted` consistently across services — on-call runbook maps key to action without reading queue declaration source each incident.

## Ha-mode deprecated migration

Teams on classic mirrored queues migrate to quorum — DLX arguments recreate identically but queue type change requires declare new queue and shovel messages during maintenance. Test DLX chain on quorum in staging before cutover weekend.

## Message TTL and clock skew

Per-message TTL uses broker clock — NTP skew between publishers and broker rarely matters at second granularity but sub-second TTL tests fail mysteriously across zones. Use queue TTL for retry delays measured in seconds or longer.

## Grafana dashboard panels

Panel 1: main queue depth. Panel 2: DLQ depth. Panel 3: retry queue depth. Panel 4: rate of x-death reason rejected. Correlated spike in panel 1 and 3 indicates retry storm; panel 2 spike without panel 1 drop indicates consumer not processing DLQ reprocessor.

## Legal hold on DLQ messages

Subpoena may require preserving DLQ poison messages — export to WORM storage before purge after fix. DLQ is forensic evidence for fraud investigation not only engineering debug artifact.

## Closing principle

Every production queue with external payload variability needs a DLX path — JSON from partners, webhooks, and mobile clients will eventually poison. Design DLX before first poison incident; rehearse reprocess quarterly; cap retries with x-death; never requeue poison indefinitely.

## Read next when debugging DLX

If messages disappear without reaching DLQ, verify DLX exchange binding and that nack uses requeue=false. If retry loop never ends, inspect x-death count and max retry routing to final DLQ — not every failure should return to main queue forever.

Document tier ownership, DLX bindings, cron schedules, and FIFO group-key schema in the same repository as application code — operational knowledge drift causes repeat incidents when runbooks live only in wiki software nobody updates after reorganizations.

Export sample x-death headers into runbook appendix so on-call recognizes retry-exhausted versus first-failure patterns without opening RabbitMQ management UI during VPN outage.

Add DLQ depth alert before first production webhook integration — teams that add DLX only after first outage rebuild customer trust slowly. Review DLX bindings on every queue declaration change in pull request checklist.
Surface x-death headers in your DLQ inspector so operators see expired-in-retry versus rejected-by-consumer without decoding raw AMQP properties by hand.

Document the SLO this setting protects for queue-rabbitmq-dead-letter-exchange.

Operational ownership matters as much as broker config for queue rabbitmq dead letter exchange: name an on-call team, alert on depth or age, and rehearse replay or redrive in staging before you need it in production.
