---
title: "Orchestrating Workflows with Step Functions"
slug: "serverless-step-functions-orchestration"
description: "Orchestrate serverless workflows with AWS Step Functions: Standard vs Express, error handling, parallel steps, and human approval tasks."
datePublished: "2025-07-26"
dateModified: "2025-07-26"
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Observability

Execution graph in console shows failed state in red. Export history to CloudWatch Logs; link execution ARN to business ID in input. X-Ray traces Lambda steps when enabled.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [AWS Step Functions developer guide](https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html)
- [Amazon States Language specification](https://states-language.net/spec.html)
- [Step Functions error handling](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html)
- [Callback with task token pattern](https://docs.aws.amazon.com/step-functions/latest/dg/connect-to-resource.html#connect-wait-token)
- [AWS CDK Step Functions module](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-cdk-lib.aws_stepfunctions-readme.html)
