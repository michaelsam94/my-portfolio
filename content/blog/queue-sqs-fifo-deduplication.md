---
title: "AWS SQS FIFO Deduplication"
slug: "queue-sqs-fifo-deduplication"
description: "Message deduplication ID and group ID — throughput limits per group."
datePublished: "2026-03-19"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "sqs fifo deduplication, message group id, content based deduplication, fifo throughput"
faq:
  - q: "How does SQS FIFO deduplication work?"
    a: "Within a five-minute deduplication interval, FIFO queues treat messages with the same MessageDeduplicationId as duplicates and accept only one. With ContentBasedDeduplication=true, SQS hashes the body to derive the ID. Otherwise you must supply MessageDeduplicationId explicitly — typically a business idempotency key."
  - q: "What does MessageGroupId control?"
    a: "MessageGroupId defines ordering scope. Messages sharing a group are strictly ordered and processed one at a time per consumer. Different groups process in parallel. One group = one lane; hot customer ID as group key serializes all their messages and caps throughput at ~300 TPS per queue API limits."
  - q: "What are FIFO throughput limits and how do I scale them?"
    a: "Standard FIFO queues deliver up to 300 transactions per second per API action without batching, 3000 with batching, or higher with high throughput mode partitioning across message group IDs. Standard queues have nearly unlimited throughput but no ordering or deduplication guarantees."
---

A inventory service double-subtracted stock when API Gateway retried a checkout POST during a Lambda timeout — two SQS messages, two decrements, one angry warehouse manager. Moving order events to a FIFO queue with `MessageDeduplicationId` set to the checkout idempotency key collapsed duplicates within the five-minute window and preserved per-order sequencing via `MessageGroupId=order_id`. FIFO is not "SQS but nicer"; it is a contract with throughput ceilings you design around.

## FIFO vs standard queues

| Feature | Standard | FIFO |
|---------|----------|------|
| Ordering | Best effort | Strict within MessageGroupId |
| Deduplication | None | 5-minute window by dedup ID |
| Throughput | Nearly unlimited | 300/sec (3,000 batched) base |
| Name suffix |任意 | Must end in `.fifo` |
| Exactly-once processing | No (at-least-once) | Dedup at enqueue, not consumer |

FIFO solves **duplicate publishes** and **ordering within a group** — consumers must still be idempotent because visibility timeout redelivery remains at-least-once.

## MessageDeduplicationId

```python
def publish_order_event(order_id: str, event_type: str, payload: dict):
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(payload),
        MessageGroupId=order_id,
        MessageDeduplicationId=f"{order_id}:{event_type}",
    )
```

Same `MessageDeduplicationId` within 5 minutes → SQS accepts first, drops duplicates.

**ContentBasedDeduplication:**

```python
Attributes={
    'FifoQueue': 'true',
    'ContentBasedDeduplication': 'true',
}
```

Identical bodies dedupe automatically. Risk: legitimate retries with same body but different intent dedupe incorrectly. Prefer explicit IDs for business events.

## MessageGroupId and ordering

```python
MessageGroupId=order_id   # serialize lifecycle: created → paid → shipped
```

Parallelism = number of **distinct groups** in flight.

Anti-pattern: `MessageGroupId='default'` — entire system one lane.

Partition groups by entity: `order_id`, `user_id`, or `hash(tenant_id) % 128`.

High throughput FIFO:

```python
Attributes={
    'DeduplicationScope': 'messageGroup',
    'FifoThroughputLimit': 'perMessageGroupId',
}
```

## Throughput math

Base FIFO: ~300 messages/sec without batching. With batching max 10: ~3000/sec theoretical.

If you need 10k/sec ordered **per key**, FIFO may be wrong tool — consider Kafka partition or dedup table + standard queue.

## Consumer-side idempotency still required

```python
def handler(record, context):
    for item in record['Records']:
        body = json.loads(item['body'])
        dedup_key = body['deduplication_id']
        if not store.try_claim(dedup_key, ttl=86400):
            continue
        process(body)
```

Use DynamoDB conditional put or Postgres `ON CONFLICT DO NOTHING` for claim table.

## Partial batch failure with Lambda and FIFO

```python
def handler(event, context):
    failures = []
    for record in event['Records']:
        try:
            handle(record)
        except RetryableError:
            failures.append({'itemIdentifier': record['messageId']})
    return {'batchItemFailures': failures}
```

Without this, one poison message blocks entire group until maxReceiveCount → DLQ.

## Visibility timeout vs FIFO ordering

Long processing holds message invisible — other messages in same MessageGroupId wait. Set visibility timeout > p99 handler duration or use heartbeat pattern for long jobs.

## Cross-region FIFO considerations

FIFO queues are regional — global active-active requires separate FIFO per region and dedup store in global database if same checkout can hit two regions.

## Testing deduplication in staging

Send same `MessageDeduplicationId` twice; assert one receive. Run before production traffic.

## CloudWatch alarms

```yaml
ApproximateAgeOfOldestMessage:
  Threshold: 300
  Dimensions: QueueName: orders.fifo
```

Pair with DLQ alarm — old message age with zero DLQ inflow suggests consumer stall not poison message.

## Terraform queue attributes

```hcl
resource "aws_sqs_queue" "orders_fifo" {
  name                        = "orders.fifo"
  fifo_queue                  = true
  content_based_deduplication = false
  deduplication_scope         = "messageGroup"
  fifo_throughput_limit       = "perMessageGroupId"
}
```

Infrastructure-as-code prevents console drift where staging enables content-based dedup but prod expects explicit IDs.

## Cost considerations

FIFO pricing higher per request than standard. Batching reduces cost with `SendMessageBatch` max 10 entries.

## When not to use FIFO

- Fire-and-forget telemetry (use standard + idempotent agg)
- Global strict total order (single group bottleneck)
- Duplicate detection window > 5 minutes (use dedup store in DB)

SQS FIFO pairs `MessageDeduplicationId` (five-minute duplicate collapse) with `MessageGroupId` (ordered lane per entity). Design group keys for parallelism, set explicit dedup IDs from business events, batch for throughput, and keep consumer idempotency because visibility timeout is still at-least-once. FIFO fixes duplicate **enqueue**; your database fixes duplicate **process**.

## MessageDeduplicationId collision across event types

Using only `order_id` as dedup ID collapses distinct events (created vs paid) within five minutes — include event type in dedup key as shown earlier. Document dedup key schema in API contract alongside idempotency-key header semantics.

## SNS → SQS FIFO subscription

SNS publishes to FIFO with `MessageGroupId` mapped from message attributes — configure subscription raw delivery for JSON control. Filter policies reduce FIFO ingress cost when only subset of events need ordering.

## Dead letter queue FIFO pairing

FIFO DLQ must end in `.fifo` and receive redriven messages preserving group ID — configure redrive allow policy. MaxReceiveCount exhaustion moves poison message to DLQ without breaking ordering metadata for forensic replay.

## Exactly-once processing myth

Marketing "exactly-once" for FIFO refers to deduplication at enqueue within five minutes — not consumer exactly-once. Architecture reviews should reject FIFO selection based solely on exactly-once checkbox without consumer idempotency design.

## Load test group ID distribution

Uniform random MessageGroupId across 10k keys achieves parallel throughput; single group load test proves ordering not throughput — both tests required before launch sign-off.

## Cross-account FIFO access

SQS queue policy allowing cross-account send must include fifo dedup attributes in IAM condition keys where applicable — partner account publish failures show access denied on SendMessage not dedup confusion.

## Extended dedup window workaround

Five-minute dedup window insufficient for daily batch resubmit — use business dedup table with 24h TTL at consumer; FIFO dedup handles rapid retry only. Document two-layer dedup in architecture diagram for auditor clarity.

## API Gateway idempotency integration

API Gateway native idempotency cache pairs with FIFO MessageDeduplicationId from same key — client sends Idempotency-Key header, Lambda publishes to FIFO with matching dedup ID. End-to-end duplicate collapse from browser retry through queue to worker claim table.

## Monitoring dedup effectiveness

CloudWatch does not expose deduplicated message count directly — compare SendMessage API count to processed count in application metrics; large gap indicates client retry storm successfully deduped at queue.

## Lambda reserved concurrency per FIFO trigger

Reserve concurrency on Lambda processing FIFO trigger prevents standard queue Lambdas from consuming account concurrency during spike — FIFO payment path keeps minimum 10 concurrent executions while bulk standard queue scales independently.

## Message attributes size limit

FIFO message attributes count toward 256KB total — large attribute payloads reduce body budget. Keep dedup metadata in body JSON not attributes; MessageDeduplicationId parameter sufficient for dedup without bloating attributes.

## Disaster recovery FIFO queue URL

Document primary and DR region FIFO queue URLs in runbook — failover requires DNS or config switch; MessageGroupId state does not replicate across regions automatically. Failover drill includes verifying dedup table in global database still authoritative across regions.

## Cost anomaly detection

Sudden SendMessage bill spike may indicate client retry loop deduped at queue but still charging API calls — fix client backoff; dedup prevents duplicate processing not duplicate API billing for sends that SQS accepts as deduplicated success responses.

## Closing principle

FIFO solves ordering within a group and duplicate collapse at enqueue for five minutes — not end-to-end exactly-once. Design MessageGroupId for parallelism, MessageDeduplicationId from business keys, consumer idempotency for visibility timeout, and load test hot groups before launch.

## Read next when FIFO throughput stalls

Check CloudWatch for single MessageGroupId dominance — one hot group caps at FIFO throughput limit while other groups idle. Split hot entity across synthetic sub-groups only if business ordering allows (e.g. order line items not whole order).

Document tier ownership, DLX bindings, cron schedules, and FIFO group-key schema in the same repository as application code — operational knowledge drift causes repeat incidents when runbooks live only in wiki software nobody updates after reorganizations.
Derive MessageDeduplicationId from a stable business event id — a fresh UUID on every HTTP retry disables FIFO deduplication and invites double processing.

Document the SLO this setting protects for queue-sqs-fifo-deduplication.

Operational ownership matters as much as broker config for queue sqs fifo deduplication: name an on-call team, alert on depth or age, and rehearse replay or redrive in staging before you need it in production.
