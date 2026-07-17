---
title: "Event-Driven Serverless Architecture"
slug: "serverless-event-driven-architecture"
description: "Design event-driven serverless systems: EventBridge, SQS, idempotency, dead-letter queues, and choreography versus orchestration."
datePublished: "2025-07-22"
dateModified: "2026-07-17"
tags:
  - "Engineering"
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

## Dead-letter queues

```yaml
RedrivePolicy:
  deadLetterTargetArn: !GetAtt OrderDLQ.Arn
  maxReceiveCount: 5
```

Alert on DLQ depth. Replay tool reprocesses after fix with same idempotency guard.

## Ordering tradeoffs

Standard SQS preserves rough order but not strictly. FIFO queues serialize per `MessageGroupId` (e.g., order_id) with throughput limits. EventBridge does not guarantee order—design for out-of-order arrival.

## Observability

OpenTelemetry trace context injected in event metadata (`traceparent`). CloudWatch metrics on age of oldest message. Correlate business IDs across logs—not just request IDs from single Lambda.

Choreographed saga: `PaymentFailed` event triggers inventory release. Orchestrated: Step Functions `Catch` invokes refund Lambda. Document failure matrix in runbook.

Per-invocation billing favors batching SQS messages (batch size 10). EventBridge pricing per event—avoid chatty fine-grained events when one summary suffices.

Schema registry validates event compatibility on publish—breaking changes fail CI before production consumers break.

DLQ depth alerts with replay runbook after fix. Idempotency table TTL exceeds max redelivery window.

Choreography versus Step Functions: document failure matrix in runbook when payment fails mid-saga. Cost: batch SQS where per-message billing adds up.

Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.

Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Shipping serverless event driven architecture without regrets

Serverless designs for serverless event driven architecture succeed when you embrace the platform constraints: cold starts, execution time limits, at-least-once delivery, and per-invocation pricing. Design handlers to be idle-cheap and burst-tolerant.

### Patterns that keep costs predictable

- Batch SQS messages when per-invocation overhead dominates
- Prefer async event reactions over synchronous fan-out from the request path
- Cap concurrency to protect downstream databases
- Use provisioned concurrency only for latency-critical authenticated paths

### Idempotency

Every consumer for serverless event driven architecture should key on `event_id` (or natural business key) with a conditional write. Retries and duplicate deliveries are normal. Store processed IDs with a TTL longer than the maximum redelivery window.

### Observability

Propagate trace context in event envelopes. Alert on DLQ depth, iterator age, and p99 duration. Cold-start regressions show up as latency cliffs after idle periods — track init duration separately from business logic duration.

### Local and CI testing

Contract-test event schemas. Use local emulators sparingly; prefer unit tests with recorded events and integration tests against ephemeral cloud stacks for the critical path of serverless event driven architecture.

## Resources

- [Amazon EventBridge documentation](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html)
- [AWS SQS with Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [Serverless Land event-driven patterns](https://serverlessland.com/event-driven-architecture)
- [Enterprise Integration Patterns](https://www.enterpriseintegrationpatterns.com/)
- [AWS Step Functions documentation](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)

## EventBridge schema discovery

Enable schema discovery on domain buses — generated schemas accelerate consumer contract tests and catch producer drift when `detail` payload adds required fields without version bump.

## Dead letter redrive automation

Step Functions or Lambda on schedule drains DLQ to staging queue when depth > 0 for >15 minutes — page owner before auto-redrive if poison message pattern detected in first five samples.

## Cross-account event policies

EventBridge resource policies whitelist producer account IDs explicitly — overly broad `*` principals allowed data exfiltration via event bus in shared services account audit findings.

## Partial SQS batch failure

Return `batchItemFailures` from Lambda so one poison message does not retry entire batch of ten successfully processed records.
