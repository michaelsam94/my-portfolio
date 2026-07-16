---
title: "Event-Driven Serverless Architecture"
slug: "serverless-event-driven-architecture"
description: "Design event-driven serverless systems: EventBridge, SQS, idempotency, dead-letter queues, and choreography versus orchestration."
datePublished: "2025-07-22"
dateModified: "2025-07-22"
tags: ["Serverless", "Event-Driven", "Architecture", "AWS"]
keywords: "event driven serverless, EventBridge architecture, SQS Lambda pattern, serverless choreography, event sourcing serverless, DLQ best practices"
faq:
  - q: "EventBridge or SNS for domain events?"
    a: "EventBridge suits multi-subscriber routing with content-based filtering, schema registry, and cross-account buses. SNS fan-out to SQS is simpler for notify-all patterns with fewer routing rules. Many architectures use EventBridge as domain bus and SNS only for mobile push or email fan-out from one rule."
  - q: "How do I prevent duplicate event processing?"
    a: "At-least-once delivery is guaranteed—design consumers idempotent with deduplication keys stored in DynamoDB or conditional writes. SQS FIFO with deduplication IDs helps for ordered streams. Track processed event_id with TTL exceeding max redelivery window."
  - q: "Choreography or Step Functions orchestration?"
    a: "Choreography scales team autonomy—each service reacts to events independently. Orchestration centralizes workflow visibility and error handling in Step Functions when sagas span many steps with compensations. Use choreography for simple reactions; orchestration when you need timeout, retry policy, and human approval in one place."
---

The order service POSTed synchronously to inventory, email, and analytics—800ms p99 and cascading failures when analytics timed out. Event-driven serverless decouples producers from consumers: publish `OrderPlaced`, let Lambdas react independently, scale per handler, and retry without blocking checkout. The complexity moves to idempotency, ordering guarantees, and observability across invisible call chains.



## Event envelope

```json
{
  "event_id": "evt_01JXYZ",
  "type": "order.placed",
  "version": "1",
  "timestamp": "2025-07-22T10:00:00Z",
  "source": "orders-service",
  "data": {
    "order_id": "ord_991",
    "customer_id": "cust_42",
    "total_cents": 15000
  }
}
```

Schema registry (EventBridge Schema Registry, AsyncAPI) validates compatibility on publish.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## EventBridge rule example

```yaml
EventPattern:
  source: ["orders-service"]
  detail-type: ["order.placed"]
Targets:
  - Arn: !GetAtt InventoryQueue.Arn
  - Arn: !GetAtt EmailQueue.Arn
```

Each target gets SQS buffer absorbing Lambda scale bursts.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Lambda consumer with idempotency

```python
def handler(event, context):
    for record in event["Records"]:
        body = json.loads(record["body"])
        event_id = body["event_id"]
        if already_processed(event_id):
            continue
        process_order(body["data"])
        mark_processed(event_id)
```

Use conditional PutItem on DynamoDB partition key `event_id`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Dead-letter queues

```yaml
RedrivePolicy:
  deadLetterTargetArn: !GetAtt OrderDLQ.Arn
  maxReceiveCount: 5
```

Alert on DLQ depth. Replay tool reprocesses after fix with same idempotency guard.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Ordering tradeoffs

Standard SQS preserves rough order but not strictly. FIFO queues serialize per `MessageGroupId` (e.g., order_id) with throughput limits. EventBridge does not guarantee order—design for out-of-order arrival.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


## Observability

OpenTelemetry trace context injected in event metadata (`traceparent`). CloudWatch metrics on age of oldest message. Correlate business IDs across logs—not just request IDs from single Lambda.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.



Choreographed saga: `PaymentFailed` event triggers inventory release. Orchestrated: Step Functions `Catch` invokes refund Lambda. Document failure matrix in runbook.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Per-invocation billing favors batching SQS messages (batch size 10). EventBridge pricing per event—avoid chatty fine-grained events when one summary suffices.

Schema registry validates event compatibility on publish—breaking changes fail CI before production consumers break.

DLQ depth alerts with replay runbook after fix. Idempotency table TTL exceeds max redelivery window.

Choreography versus Step Functions: document failure matrix in runbook when payment fails mid-saga. Cost: batch SQS where per-message billing adds up.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.




Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [Amazon EventBridge documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html)
- [AWS SQS with Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Serverless Land event-driven patterns](https://serverlessland.com/event-driven-architecture)
- [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/)
- [AWS Step Functions documentation](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
