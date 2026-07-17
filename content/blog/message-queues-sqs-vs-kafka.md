---
title: "SQS vs Kafka: Choosing a Backbone"
slug: "message-queues-sqs-vs-kafka"
description: "Compare AWS SQS and Apache Kafka for message-driven architectures: throughput, ordering, replay, operational overhead, and decision criteria."
datePublished: "2025-05-24"
dateModified: "2026-07-17"
tags:
keywords: "SQS vs Kafka, message queue comparison, AWS SQS vs Apache Kafka, event streaming vs message queue, Kafka vs SQS when to use"
faq:
  - q: "When should I choose SQS over Kafka?"
    a: "Choose SQS when you need a managed, zero-ops message queue for task distribution, job processing, or decoupling services with moderate throughput (up to ~3,000 messages/sec per queue with batching). SQS is simpler, cheaper at low volume, and requires no cluster management."
  - q: "When is Kafka the better choice?"
    a: "Choose Kafka when you need event streaming with replay, high throughput (millions of messages/sec), strict ordering within partitions, event sourcing, or multiple consumer groups reading the same data independently. Kafka excels as a durable event log, not just a message queue."
  - q: "Can I use both SQS and Kafka in the same system?"
    a: "Yes. A common pattern uses Kafka as the central event bus for domain events and SQS for task queues between specific services. Kafka handles 'what happened' (event log); SQS handles 'do this work' (job dispatch). Connect them with bridge consumers that read from Kafka topics and enqueue SQS messages."
---
Your team needs asynchronous messaging. Someone says Kafka because Netflix uses it. Someone else says SQS because it is managed and they do not want to operate a cluster. Both are correct for different problems. Choosing wrong means either operating Kafka infrastructure for a simple job queue or hitting SQS throughput limits on an event streaming pipeline.

SQS is a message queue — point-to-point, consume-and-delete, managed. Kafka is an event log — append-only, replayable, self-managed (or MSK/confluent). The choice depends on your throughput needs, ordering requirements, replay semantics, and tolerance for operational complexity.

## Core architectural difference

**SQS:** producer sends a message, one consumer processes it, message is deleted.

```
Producer → [Queue] → Consumer → Done (message gone)
```

**Kafka:** producer appends to a topic log, multiple consumer groups read independently, messages persist.

```
Producer → [Topic/partition log] → Consumer Group A
                                 → Consumer Group B
                                 → (replay from any offset)
```

SQS is a mailbox. Kafka is a ledger.

## Feature comparison

| Feature | SQS (Standard) | SQS (FIFO) | Kafka |
|---------|---------------|------------|-------|
| Throughput | ~3K msg/sec | 300 msg/sec | Millions/sec |
| Ordering | Best-effort | Strict (per group) | Strict (per partition) |
| Message retention | 14 days max | 14 days max | Configurable (days to forever) |
| Replay | No | No | Yes (by offset) |
| Multiple consumers | Competing consumers | Competing consumers | Independent consumer groups |
| Delivery guarantee | At-least-once | Exactly-once (with dedup) | At-least-once / exactly-once |
| Ops overhead | Zero (managed) | Zero (managed) | High (cluster management) |
| Cost at low volume | Very cheap | Very cheap | Expensive (minimum 3 brokers) |

## SQS: when and how

SQS fits task distribution and service decoupling:

```python
import boto3, json

sqs = boto3.client("sqs")

# Producer: enqueue a job
sqs.send_message(
    QueueUrl="https://sqs.us-east-1.amazonaws.com/123456789/image-processing",
    MessageBody=json.dumps({
        "image_id": "img_12345",
        "operations": ["resize", "watermark"],
        "output_bucket": "processed-images",
    }),
)

# Consumer: process and delete
messages = sqs.receive_message(QueueUrl=QUEUE_URL, WaitTimeSeconds=20)
for msg in messages["Messages"]:
    job = json.loads(msg["Body"])
    process_image(job)
    sqs.delete_message(QueueUrl=QUEUE_URL, ReceiptHandle=msg["ReceiptHandle"])
```

**Good fit:**
- Background job processing (emails, image processing, report generation)
- Microservice decoupling with moderate message volume
- Serverless architectures (Lambda triggered by SQS)
- Teams without dedicated infrastructure engineers

**Bad fit:**
- Event sourcing (no replay)
- Analytics pipelines reading historical events
- Multiple independent consumers of the same data
- Throughput above ~3K messages/sec per queue

## Kafka: when and how

Kafka fits event streaming and high-throughput pipelines:

```python
from confluent_kafka import Producer, Consumer

# Producer: append event to topic
producer = Producer({"bootstrap.servers": "kafka:9092"})
producer.produce(
    "order-events",
    key=order["customer_id"],
    value=json.dumps({"event": "order_created", "order_id": order["id"], "total": order["total"]}),
)
producer.flush()

# Consumer: read from specific offset
consumer = Consumer({
    "bootstrap.servers": "kafka:9092",
    "group.id": "inventory-service",
    "auto.offset.reset": "earliest",
})
consumer.subscribe(["order-events"])

while True:
    msg = consumer.poll(1.0)
    if msg:
        event = json.loads(msg.value())
        update_inventory(event)
        consumer.commit(msg)
```

**Good fit:**
- Event-driven architecture with domain events
- Event sourcing and CQRS
- Real-time analytics and stream processing (Flink, Spark Streaming)
- Multiple services consuming the same event stream
- High throughput (100K+ messages/sec)
- Audit log requiring replay capability

**Bad fit:**
- Simple job queues with low volume
- Teams without Kafka operational experience
- Workloads where messages should disappear after processing

## The hybrid pattern

Many production systems use both:

```
Service A → Kafka (order-events) → Inventory Service
                                 → Analytics Service
                                 → Bridge Consumer → SQS (notification-jobs) → Email Service
```

Kafka is the system of record for domain events. SQS handles task dispatch to workers that do not need the full event history.

## Cost comparison at scale

**SQS:** $0.40 per million requests (standard). At 10M messages/day ≈ $120/month.

**Kafka (self-hosted on AWS):** 3× m5.large brokers ≈ $200/month minimum + operational time. MSK (managed Kafka) starts at ~$400/month for 3 brokers.

**Kafka (Confluent Cloud):** pay per CKU, typically $500+/month for production workloads.

SQS wins below ~50M messages/month. Kafka wins when you need its features regardless of cost.

## Migration considerations

**SQS to Kafka:** when you outgrow SQS throughput, need replay, or want multiple consumer groups. Run both in parallel during migration — produce to Kafka, bridge to SQS for consumers not yet migrated.

**Kafka to SQS:** rare, but happens when teams want to eliminate Kafka ops overhead and only need simple queuing. Consolidate consumer groups into SQS workers.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get message queues sqs vs kafka wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of message queues sqs vs kafka fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When message queues sqs vs kafka misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [AWS SQS developer guide](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/welcome.html)
- [Apache Kafka documentation](https://kafka.apache.org/documentation/)
- [Amazon MSK (managed Kafka)](https://docs.aws.amazon.com/msk/latest/developerguide/what-is-msk.html)
- [Martin Kleppmann: Turning the database inside out](https://www.youtube.com/watch?v=fU9hR3iSM08)
- [Confluent: Kafka vs SQS comparison](https://www.confluent.io/learn/kafka-vs-sqs/)
