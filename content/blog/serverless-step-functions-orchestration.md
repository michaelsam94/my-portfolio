---
title: "Orchestrating Workflows with Step Functions"
slug: "serverless-step-functions-orchestration"
description: "Orchestrate serverless workflows with AWS Step Functions: Standard vs Express, error handling, parallel steps, and human approval tasks."
datePublished: "2025-07-26"
dateModified: "2026-07-17"
tags: ["Serverless", "AWS", "Workflow", "Orchestration"]
keywords: "AWS Step Functions, serverless workflow orchestration, Step Functions Standard Express, saga pattern Step Functions, callback pattern, human approval workflow"
faq:
  - q: "Standard or Express Step Functions workflow?"
    a: "Standard workflows support long-running executions up to one year, exactly-once state transitions, and full execution history—ideal for order fulfillment and human approvals. Express workflows handle high-volume short flows (under five minutes) at lower cost with at-least-once semantics. Choose Standard for sagas needing audit trail; Express for streaming ETL fan-out."
  - q: "How do I handle Lambda failures in state machines?"
    a: "Use Retry blocks with backoff for transient errors, Catch blocks routing to compensating states or DLQ. Set ResultPath to preserve original input when handling errors. Avoid infinite retries—maxAttempts and interval caps. For idempotent Lambdas, retries are safe; document which steps require manual intervention on permanent failure."
  - q: "Can Step Functions wait for human approval?"
    a: "Yes. Task states with `.waitForTaskToken` pause until callback with task token—SendTaskSuccess or SendTaskFailure from approval UI or webhook. Timeout transitions escalate or cancel. This pattern beats polling SQS for manager sign-off on large refunds."
---

Refund approval needed inventory release, Stripe reversal, email, and CRM update—with rollback if step three failed. Wiring that in Lambda chains via SNS quickly becomes spaghetti. AWS Step Functions models workflows as state machines with visual execution history, built-in retry, parallel branches, and wait-for-human tasks. You pay per state transition, but you buy clarity when onboarding asks "what happens when payment fails mid-flow?"

## Hello workflow ASL

```json
{
  "Comment": "Process refund",
  "StartAt": "ValidateRefund",
  "States": {
    "ValidateRefund": {
      "Type": "Task",
      "Resource": "arn:aws:lambda:...:function:validate",
      "Next": "ApproveIfLarge"
    },
    "ApproveIfLarge": {
      "Type": "Choice",
      "Choices": [{
        "Variable": "$.amount_cents",
        "NumericGreaterThan": 100000,
        "Next": "WaitForApproval"
      }],
      "Default": "ProcessRefund"
    },
    "ProcessRefund": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "End": true
    }
  }
}
```

Amazon States Language (ASL) defines transitions; CDK and Terraform generate it.

## Retry and Catch

```json
"ProcessRefund": {
  "Type": "Task",
  "Resource": "...",
  "Retry": [{
    "ErrorEquals": ["Lambda.ServiceException", "States.TaskFailed"],
    "IntervalSeconds": 2,
    "MaxAttempts": 3,
    "BackoffRate": 2
  }],
  "Catch": [{
    "ErrorEquals": ["RefundDeclined"],
    "Next": "NotifyFailure"
  }]
}
```

Separate business failures (Catch) from infrastructure blips (Retry).

## Parallel inventory and payment

```json
"ParallelRefund": {
  "Type": "Parallel",
  "Branches": [
    {"StartAt": "ReversePayment", "States": {...}},
    {"StartAt": "RestockInventory", "States": {...}}
  ],
  "Next": "SendConfirmation"
}
```

Parallel succeeds when all branches succeed; one failure fails the parallel unless isolated with separate error handling.

## Human approval with task token

```json
"WaitForApproval": {
  "Type": "Task",
  "Resource": "arn:aws:states:::lambda:invoke.waitForTaskToken",
  "Parameters": {
    "FunctionName": "sendApprovalEmail",
    "Payload": {
      "taskToken.$": "$$.Task.Token",
      "refund.$": "$"
    }
  },
  "TimeoutSeconds": 86400,
  "Next": "ProcessRefund"
}
```

Approval Lambda calls `SendTaskSuccess` with token when manager clicks approve.

## Map state for batch

Process array items with concurrency limit:

```json
"MapOrders": {
  "Type": "Map",
  "ItemsPath": "$.orders",
  "MaxConcurrency": 10,
  "Iterator": { "StartAt": "ProcessOne", "States": {...} }
}
```

## Observability

Execution graph in console shows failed state in red. Export history to CloudWatch Logs; link execution ARN to business ID in input. X-Ray traces Lambda steps when enabled.

```typescript
const chain = validateTask
  .next(new sfn.Choice(this, "Large?")
    .when(sfn.Condition.numberGreaterThan("$.amount", 1000), approvalTask)
    .otherwise(processTask));
new sfn.StateMachine(this, "RefundMachine", { definition: chain });
```

Execution graph in console links to business ID in input—support quotes execution ARN. Catch versus Retry: business failures Catch, infrastructure Retry with cap.

Map state MaxConcurrency prevents stampeding downstream. Human approval waitForTaskToken timeout escalates—86400 seconds without handler leaves workflows stuck visible.

CDK or Terraform generates ASL—review diffs like application code.

## Sustaining production quality

Standard workflows billing includes state transitions — optimize ASL to avoid superfluous Pass states. Test Task failure branches with injected errors; compensation paths need same idempotency discipline as saga services. Export execution history to observability backend for support lookup by order ID.

## Express vs Standard workflows

Express workflows suit high-volume short flows with at-least-once semantics. Standard workflows give exactly-once state transitions and long-running waits — use for order sagas and human approval steps.

## Resources

- [AWS Step Functions developer guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [Amazon States Language specification](https://states-language.net/spec.html)
- [Step Functions error handling](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html)
- [Callback with task token pattern](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html#connect-wait-token)
- [AWS CDK Step Functions module](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_stepfunctions-readme.html)

## Operational checklist (1)

Before promoting Serverless Step Functions Orchestration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Serverless Step Functions Orchestration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Serverless Step Functions Orchestration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Serverless Step Functions Orchestration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Serverless Step Functions Orchestration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Serverless Step Functions Orchestration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Serverless Step Functions Orchestration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Serverless Step Functions Orchestration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Serverless Step Functions Orchestration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Serverless Step Functions Orchestration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Capacity and cost notes for serverless step functions orchestration

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct serverless step functions orchestration changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for serverless step functions orchestration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for serverless step functions orchestration

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most serverless step functions orchestration regressions before production.

Concrete probe 2: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around serverless step functions orchestration

Most incidents involving serverless step functions orchestration start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for serverless step functions orchestration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for serverless step functions orchestration

Name three invariants that must hold after every deploy of serverless step functions orchestration. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

Concrete probe 4: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for serverless step functions orchestration

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to serverless step functions orchestration, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

| Check | Expected for serverless step functions orchestration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for serverless step functions orchestration

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for serverless step functions orchestration should include the revert command and the expected user-visible effect within five minutes.

Concrete probe 6: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for serverless step functions orchestration

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how serverless step functions orchestration breaks without a clear owner in the incident channel.

| Check | Expected for serverless step functions orchestration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for serverless step functions orchestration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

Order fulfillment spans payment, inventory, shipping, and email — one Lambda timeout cannot hold the saga. Step Functions express long-running workflows with visual state, retries, and human tasks without maintaining scheduler infrastructure yourself.

## Standard versus Express workflows

| Type | Duration | Semantics | Cost model |
| --- | --- | --- | --- |
| Standard | Up to one year | Exactly-once state transitions | Per transition |
| Express | Up to five minutes | At-least-once, high volume | Per execution + duration |

Use Standard for order sagas, approval flows, and anything needing durable wait states. Express for high-throughput event processing where duplicate side effects are idempotent.

## Retry and catch

```json
"Retry": [{
  "ErrorEquals": ["States.TaskFailed", "Lambda.ServiceException"],
  "IntervalSeconds": 2,
  "MaxAttempts": 3,
  "BackoffRate": 2.0
}],
"Catch": [{
  "ErrorEquals": ["States.ALL"],
  "Next": "CompensatePayment",
  "ResultPath": "$.error"
}]
```

Business failures (declined card) route to Catch without retry storm. Transient AWS errors retry with backoff.

## Compensation design

Each forward step has compensating action: release inventory, refund payment, cancel shipment label. Compensations must be idempotent — Step Functions may replay. Store saga state in DynamoDB with version for audit.

## Wait for human approval

`.waitForTaskToken` sends token to SNS/SQS; human approves via API calling `SendTaskSuccess`. SLA timer on wait — escalate or auto-reject.

## Observability

Execution history is your audit trail — export to CloudWatch Logs for retention beyond default UI window. Trace Map shows stuck states. Alert on executions `FAILED` or running longer than p99 order completion.

## Local testing

Step Functions Local and workflow simulator validate ASL before deploy. Unit test Lambda tasks; integration test full graph in dev account with mocked payment gateway.

## Cost control

Long waits in Standard are cheap per minute but millions of open executions add up. Close executions promptly after terminal state. Express for fan-out inside short windows.

## Resources

- [Step Functions developer guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [Saga pattern on AWS](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-data-persistence/saga-pattern.html)
