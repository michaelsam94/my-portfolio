---
title: "Temporal Workflow Saga Pattern"
slug: "queue-temporal-workflow-saga"
description: "Durable timers and compensation activities — vs choreographed Kafka saga."
datePublished: "2026-03-20"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "Queues"
  - "Messaging"
keywords: "temporal saga, workflow compensation, durable execution, orchestrated saga"
faq:
  - q: "What is the difference between an orchestrated saga in Temporal and a choreographed saga on Kafka?"
    a: "Temporal centralizes saga logic in a workflow function that calls activities in order and runs compensations on failure. Kafka choreography publishes events — each service reacts independently. Temporal gives visible state, built-in timers, and automatic retry; Kafka scales event fan-out but debugging multi-hop failure requires distributed tracing across consumers."
  - q: "How do Temporal timers replace sleep in saga steps?"
    a: "workflow.sleep(duration) is durable — worker crash does not lose the timer. Temporal fires the next step when time elapses. Never use time.sleep in workflow code; use workflow timers for delays between saga steps like payment capture after 24-hour hold."
  - q: "When should compensation run in a Temporal saga?"
    a: "Run compensations in reverse order of successful forward steps when a later step fails and the business requires rollback — cancel shipment if payment fails, refund if shipment fails after charge. Skip compensation for steps that are safely retryable or already idempotent no-ops. Not every failure needs full rollback; define terminal failure states explicitly."
---

Booking a trip charged the customer, reserved inventory, then failed sending confirmation email — and the ops runbook said "manually refund in Stripe." The Kafka choreographed saga had no single place showing which steps succeeded before the timeout. Rewriting as a Temporal workflow with explicit compensate activities turned a three-hour finance reconciliation into an automatic `RefundPayment` activity triggered by workflow failure semantics.

## Saga problem space

Distributed transaction without 2PC:

```
Reserve inventory → Charge payment → Book carrier → Send confirmation
        │                  │               │
        └── on failure, undo prior steps (compensate)
```

**Choreography (Kafka/events):** each service listens and emits — no central coordinator.

**Orchestration (Temporal):** workflow code defines order and compensation.

Temporal fits when steps have strict ordering, human-visible workflow history, delays spanning hours/days, and complex compensation logic versioned with deploys.

## Temporal building blocks

| Concept | Role in saga |
|---------|--------------|
| Workflow | Deterministic orchestrator — no I/O directly |
| Activity | Side effect — call API, DB write |
| Timer | Durable sleep between steps |
| Signal | External event (user cancel) mid-saga |
| Query | Read workflow state without mutation |

Workflow code example (TypeScript SDK):

```typescript
import { proxyActivities, sleep, ApplicationFailure } from '@temporalio/workflow';

const { reserveInventory, chargePayment, bookCarrier, sendEmail,
        releaseInventory, refundPayment, cancelCarrier } =
  proxyActivities<typeof activities>({
    startToCloseTimeout: '2 minutes',
    retry: { maximumAttempts: 3 },
  });

export async function bookTripSaga(tripId: string, userId: string): Promise<void> {
  let inventoryReserved = false;
  let paymentCharged = false;
  let carrierBooked = false;

  try {
    await reserveInventory(tripId);
    inventoryReserved = true;

    await chargePayment(tripId, userId);
    paymentCharged = true;

    await sleep('24 hours');

    await bookCarrier(tripId);
    carrierBooked = true;

    await sendEmail(tripId, userId);
  } catch (err) {
    if (carrierBooked) await cancelCarrier(tripId);
    if (paymentCharged) await refundPayment(tripId, userId);
    if (inventoryReserved) await releaseInventory(tripId);
    throw ApplicationFailure.nonRetryable('bookTrip failed', String(err));
  }
}
```

Compensations run **reverse order** of successful forward steps.

## Determinism rules

Workflow code must replay identically.

**Allowed:** control flow, `sleep`, activity calls, signals, child workflows.

**Forbidden:** `Math.random()`, direct HTTP, `Date.now()` (use `workflow.now()`), threading.

## Activities: retries and idempotency

```typescript
export async function chargePayment(tripId: string, userId: string): Promise<void> {
  await stripe.paymentIntents.create(
    { amount: ..., metadata: { tripId } },
    { idempotencyKey: `charge-${tripId}` },
  );
}
```

Use heartbeats for long activities with `Context.current().heartbeat(step)`.

## Durable timers vs queue delayed jobs

Temporal timer survives worker pod restart, workflow code deploy (with compatible versioning), and activity worker scale to zero. Use `workflow.sleep` not external scheduler for saga delays tied to business state.

## Signals for cancellation

```typescript
export const cancelTripSignal = defineSignal('cancelTrip');

setHandler(cancelTripSignal, () => { cancelled = true; });
```

Register signal handlers before wait points that should be interruptible.

## Saga vs 2PC

Sagas accept **eventual consistency** — compensation may fail (refund API down). Design compensation retry policies separate from forward path and alert on stuck compensating workflows.

## Versioning sagas in production

```typescript
import { patched } from '@temporalio/workflow';

if (patched('add-fraud-check-v2')) {
  await fraudCheck(tripId);
}
```

Use patch markers for compatible evolution — never break replay history for running workflows.

## Comparison: Temporal saga vs Kafka choreography

| Aspect | Temporal orchestrated | Kafka choreographed |
|--------|----------------------|---------------------|
| State visibility | Workflow history UI | Trace + consumer offsets |
| Ordering | Workflow sequence | Partition key per aggregate |
| Timeout handling | Native workflow timers | Consumer SLA + DLQ |
| Compensation | Explicit in workflow | Each service listens for cancel events |
| Coupling | Workflow knows all steps | Services know event schema |

## Failure recovery story

Worker dies mid-activity: Temporal retries on another worker. Workflow worker dies mid-sleep: new worker replays history; timer fires on time; completed activities not re-run.

## Child workflows for parallel saga steps

Independent steps after payment can run as child workflows with independent retry policies.

## Search attributes for support tooling

```typescript
await client.workflow.start(bookTripSaga, {
  workflowId: `trip-${tripId}`,
  searchAttributes: { TripId: [tripId], UserId: [userId] },
});
```

Support searches Temporal UI by business key instead of correlating Kafka offsets.

## Testing sagas

Temporal test environment supports time skip for timer testing and failure injection on activities.

## Security and PII in workflow input

Workflow inputs persist in Temporal history — pass tokenized references; activities fetch sensitive data at execution time.

Temporal sagas make distributed transactions explicit: forward activities, reverse compensations, durable timers, and replay-safe workflow code. Prefer orchestration when support needs one place to read trip state; keep Kafka for event fan-out and analytics. Implement idempotent activities, test compensation failures, and version workflows — the saga story survives longer than any single deploy.

## Saga timeout per step

Each activity `startToCloseTimeout` bounds step duration — separate from workflow execution timeout covering entire saga. Long-running saga needs generous workflow timeout (days) with per-step timeouts minutes — misconfigured workflow timeout cancels entire trip booking while payment activity still retrying.

## Human-in-the-loop signals

Approval steps use signal after query:

```typescript
await condition(() => approved, '72 hours');
```

Timer plus signal pattern replaces polling database for manager approval — workflow waits durably without holding worker thread.

## Kafka emit after saga step

Hybrid: activity completes DB write, publishes Kafka event for read models — workflow remains orchestration source of truth; Kafka consumers stay idempotent. Do not duplicate saga compensation logic in Kafka consumers — compensate only in workflow.

## Temporal Cloud namespaces

Separate namespace per environment — prod workflow history never shares dev cluster. Search attributes indexed per namespace for support tooling.

## Compensation ordering bugs

Compensating payment before canceling shipment leaves customer charged without goods — enforce reverse forward order in code review checklist. Unit test compensation sequence with mocked activities verifying call order on mid-saga failure injection.

## Workflow reset vs compensation

Temporal workflow reset truncates history to point before bad activity — dangerous in financial sagas vs explicit compensation. Prefer compensate over reset in prod; reset reserved for dev debugging with namespace isolation.

## Activity heartbeats for payment polling

Poll payment provider status with activity heartbeat each iteration — long poll loop without heartbeat hits startToCloseTimeout while payment still processing. Heartbeat extends activity lease; workflow receives completion when provider confirms settled.

## Saga observability with OpenTelemetry

Trace propagation from HTTP request into workflow start and each activity span — support sees single trace for failed booking instead of correlating Kafka offsets. Temporal SDK OTel integration varies by language; verify head sampling does not drop compensation spans.

## Long-running saga continue-as-new

Booking saga spanning multi-day trip uses continue-as-new to reset history size while carrying state struct — prevents history limit on workflows with hundreds of signal events from user itinerary changes.

## Temporal Nexus and cross-namespace saga

Multi-team sagas spanning namespaces use Nexus operations — booking team workflow calls payment namespace service with typed contract. Failure handling documents which namespace owns compensation for each step to avoid double-refund across team boundaries.

## Workflow query for support dashboard

Expose query handler returning human-readable saga step status — support UI calls Temporal query API instead of reading raw event history JSON. Reduces mean time to answer "was payment charged?" from minutes to seconds during customer call.

## Choosing saga orchestrator checklist

Choose Temporal when: steps > 3, delays > minutes, human signals needed, compensation logic changes weekly. Choose Kafka choreography when: many independent reactors, event log is product, strict service decoupling mandatory. Hybrid common at scale.

## Load test workflow start rate

Temporal frontend limits workflow start QPS per namespace — booking flash sale starts 50k workflows/sec may require sharded workflow IDs across namespaces or rate limit at API gateway before Temporal overloads while Kafka might absorb publish spike differently.

## Closing principle

Temporal sagas reward teams that invest in deterministic workflow code, idempotent activities, and explicit compensation ordering. The workflow history is your distributed transaction log — treat it as production data with retention, access control, and tested failure drills.
Ban wall-clock time and direct I/O in workflow code; add replay tests in CI so determinism bugs fail before they corrupt open histories in production.
