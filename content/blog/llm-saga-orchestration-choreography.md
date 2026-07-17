---
title: "Saga Orchestration Choreography"
slug: "llm-saga-orchestration-choreography"
description: "Orchestration centralizes saga state; choreography distributes it through events. How to choose, compensate, and operate both when LLM agents span multiple services."
datePublished: "2024-11-01"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "saga pattern, orchestration vs choreography, compensating transactions, distributed workflows, event-driven architecture, LLM tool chains"
faq:
  - q: "When should I choose orchestration over choreography for a saga?"
    a: "Choose orchestration when you need a single place to inspect saga state, enforce ordering, and run compensations in a known sequence — typical for payment or provisioning flows with strict audit requirements. Choose choreography when services are independently owned, you want loose coupling, and each participant already publishes domain events. Hybrid setups are common: orchestrate the critical path, choreograph notifications and analytics."
  - q: "How do compensating transactions work when an LLM agent step fails midway?"
    a: "Each forward step that mutates external state needs a defined undo action — release inventory, void authorization, delete a draft record. The saga coordinator (or the service that executed the step) invokes compensations in reverse order. Non-idempotent compensations require idempotency keys so retries do not double-refund or double-charge. Never assume the LLM will infer compensations; encode them in tool schemas and workflow definitions."
  - q: "What is the biggest operational blind spot in choreographed sagas?"
    a: "No central state store. When step three fails, you reconstruct progress from scattered event logs across Kafka topics, SQS dead-letter queues, and service databases. Without correlation IDs propagated on every event and a searchable trace backend, debugging a stuck saga takes hours. Invest in distributed tracing and a saga correlation header before you scale choreography past a handful of services."
  - q: "Can orchestration and choreography coexist in one agent workflow?"
    a: "Yes, and most mature systems do. A Step Functions state machine or Temporal workflow might orchestrate reserve-inventory → charge-card → provision-tenant, while each downstream service choreographs side effects — sending email, updating search indexes, emitting analytics. The boundary rule: orchestrate anything that must succeed or roll back atomically from a business perspective; choreograph everything else."
---
A payment agent reserved warehouse stock, charged the card, then crashed while provisioning the tenant. Inventory stayed locked. The card stayed charged. Nobody knew which compensations to run because the workflow lived in three separate repos and a shared Slack thread.

That incident is the saga problem in miniature. Multi-step business processes that span services cannot rely on a single database transaction. The saga pattern replaces two-phase commit with a sequence of local transactions, each paired with a compensating action if a later step fails. The architectural fork — orchestration versus choreography — determines where saga state lives and who decides what happens next.

## Two ways to coordinate the same business story

Consider an agent-assisted onboarding flow: verify identity, create a billing account, provision a workspace, send a welcome email.

**Orchestration** puts a coordinator in the middle. One process — a workflow engine, a state machine, or a dedicated orchestrator service — calls each participant in order, records progress, and triggers compensations on failure. Think AWS Step Functions, Temporal, or Camunda driving the sequence.

**Choreography** removes the center. Each service listens for events, performs its local work, and publishes what happened next. The billing service hears `IdentityVerified`, creates an account, emits `BillingAccountCreated`. The workspace service hears that event and provisions. No single component owns the full script.

Neither approach is universally superior. Orchestration trades coupling for visibility. Choreography trades visibility for autonomy.

| Dimension | Orchestration | Choreography |
|---|---|---|
| Saga state | Central (workflow engine DB) | Distributed (each service's store + event log) |
| Ordering guarantees | Explicit in workflow definition | Implicit via event contracts |
| Failure visibility | One dashboard, one execution ID | Reconstruct from correlated events |
| Service coupling | Participants depend on orchestrator API | Participants depend on event schema |
| Change velocity | Workflow change may touch one repo | Event schema change may touch many consumers |
| Best fit | Regulated flows, strict rollback order | High-autonomy microservices, event-native orgs |

## Orchestration in practice: owning the script

Orchestration shines when compensations must run in a precise reverse order and auditors want a single execution record. A Temporal workflow keeps saga state durable across process restarts — critical when agent tool calls take seconds to minutes and hosts crash mid-flight.

```typescript
// Temporal-style orchestrated saga — forward steps with compensations
import { proxyActivities, defineSignal, setHandler } from "@temporalio/workflow";

const { reserveInventory, releaseInventory, chargeCard, refundCard, provisionTenant, deprovisionTenant } =
  proxyActivities<typeof activities>({ startToCloseTimeout: "2m", retry: { maximumAttempts: 3 } });

export async function onboardCustomerSaga(input: OnboardInput): Promise<void> {
  let reservationId: string | undefined;
  let chargeId: string | undefined;

  try {
    reservationId = await reserveInventory(input.sku, input.qty);
    chargeId = await chargeCard(input.paymentMethodId, input.amountCents);
    await provisionTenant(input.tenantId, reservationId);
  } catch (err) {
    if (chargeId) await refundCard(chargeId);
    if (reservationId) await releaseInventory(reservationId);
    throw err;
  }
}
```

The orchestrator holds `reservationId` and `chargeId` in workflow memory (persisted by Temporal's event history). Compensation order is explicit: refund before release, or the reverse depending on your business rules — but the code makes the order legible.

For LLM agents, orchestration maps naturally to tool registries where each tool declares forward and compensate handlers. The agent runtime — not the model — decides which tools run and in what order. The model proposes intent; the orchestrator enforces invariants.

```python
# Tool registry with explicit compensation pairs
TOOL_REGISTRY = {
    "reserve_inventory": {
        "forward": reserve_inventory,
        "compensate": release_inventory,
    },
    "charge_payment": {
        "forward": charge_payment,
        "compensate": refund_payment,
    },
}

async def run_saga(steps: list[str], ctx: SagaContext) -> SagaResult:
    executed: list[tuple[str, Any]] = []
    for step in steps:
        try:
            result = await TOOL_REGISTRY[step]["forward"](ctx)
            executed.append((step, result))
        except Exception:
            for completed_step, result in reversed(executed):
                await TOOL_REGISTRY[completed_step]["compensate"](ctx, result)
            raise
    return SagaResult(ok=True, steps=executed)
```

Operational wins: query workflow history by `workflowId`, replay failed executions, pause between steps for human approval. Operational costs: the orchestrator becomes a scaling bottleneck and a deployment dependency — every new step may require a workflow definition change.

## Choreography in practice: events as the contract

Choreography fits teams that already treat domain events as the source of truth. The saga emerges from listeners; no central process holds the full state.

```typescript
// Event handlers — each service owns its slice
export async function onIdentityVerified(event: IdentityVerifiedEvent): Promise<void> {
  const account = await billing.createAccount(event.userId);
  await eventBus.publish({
    type: "BillingAccountCreated",
    correlationId: event.correlationId,
    payload: { accountId: account.id, userId: event.userId },
  });
}

export async function onBillingAccountCreated(event: BillingAccountCreatedEvent): Promise<void> {
  try {
    await workspace.provision(event.payload.userId);
    await eventBus.publish({
      type: "WorkspaceProvisioned",
      correlationId: event.correlationId,
      payload: { userId: event.payload.userId },
    });
  } catch (err) {
    await eventBus.publish({
      type: "WorkspaceProvisioningFailed",
      correlationId: event.correlationId,
      payload: { accountId: event.payload.accountId, reason: String(err) },
    });
  }
}

// Compensation listener — billing reacts to downstream failure
export async function onWorkspaceProvisioningFailed(
  event: WorkspaceProvisioningFailedEvent
): Promise<void> {
  await billing.closeAccount(event.payload.accountId, { reason: "downstream_failure" });
}
```

The `correlationId` field is non-negotiable. Without it, a `WorkspaceProvisioningFailed` event cannot be tied back to the originating `IdentityVerified` event across six Kafka partitions and two regions.

Choreography scales organizationally: the workspace team ships a new listener without opening a PR against the billing repo. The tradeoff is saga visibility. Answering "where is customer X in onboarding?" requires joining events across services or building a read-side projection.

```sql
-- Saga read model fed by event consumers (CQRS projection)
CREATE TABLE saga_projections (
  correlation_id   UUID PRIMARY KEY,
  current_stage    TEXT NOT NULL,
  started_at       TIMESTAMPTZ NOT NULL,
  last_event_at    TIMESTAMPTZ NOT NULL,
  failed           BOOLEAN DEFAULT FALSE,
  failure_reason   TEXT
);

-- Rebuilt from event stream; queryable by support and ops
```

## Where LLM agents shift the decision

Agent workflows add non-determinism and variable step counts. A research agent might call three tools or twelve depending on the query. Pure choreography struggles when the sequence is not known upfront. Pure orchestration struggles when the model dynamically selects tools from a large registry.

Practical pattern: **orchestrate the transaction boundary, choreograph the side effects.**

The agent runtime runs an orchestrated saga for anything that moves money, mutates authoritative records, or triggers compliance checks. Each successful forward step may emit domain events that choreograph email, search indexing, and metrics — fire-and-forget paths that do not require compensation if they fail.

Guardrails belong in the orchestrator, not the prompt:

- Allowlisted tool sequences for high-risk flows (payments, data deletion).
- Human-in-the-loop gates before irreversible steps.
- Timeouts per step with automatic compensation triggers.
- Idempotency keys derived from `(tenantId, workflowId, stepIndex)`.

## Compensation design rules that survive audits

Compensations are not rollbacks in the database sense. They are **semantic undo** — business operations that approximate reversing a forward step.

**Make compensations idempotent.** Network retries will invoke them twice. `releaseInventory(reservationId)` must succeed whether or not the reservation was already released.

**Make compensations best-effort where perfect undo is impossible.** You cannot un-send an email; you send a correction. Document which steps are compensatable and which require manual intervention.

**Never compensate out of order without analysis.** Refunding before releasing inventory might leave you with stock allocated to a ghost order. Write the compensation order down and test it in staging with injected failures.

**Log compensation attempts with the same correlation ID as forward steps.** Regulators and incident reviewers ask: "What did you do when step four failed?" The answer should be one query, not a archaeology expedition.

## Failure drills worth running quarterly

Inject failures at each saga step in staging: timeout, 500 response, partial success, duplicate delivery. Verify:

1. Forward step retries do not double-charge or double-reserve.
2. Compensation runs exactly once per failed saga (or documents why twice is safe).
3. Stuck sagas surface in a dashboard within minutes, not days.
4. Support can look up saga status by customer ID or correlation ID.

For choreographed flows, replay events into a fresh consumer group and confirm the read model rebuilds correctly. Event schema drift — a new required field on `BillingAccountCreated` — silently breaks downstream compensations if consumers reject malformed payloads.

## Choosing for your next agent workflow

Ask four questions before committing:

1. **Does a regulator or SLA require a single execution record?** → Lean orchestration.
2. **Do five teams own the participating services with independent release trains?** → Lean choreography.
3. **Is the step sequence fixed and small (< 8 steps)?** → Orchestration is simpler to operate.
4. **Will the LLM dynamically choose tools?** → Orchestrator with allowlists; do not let the model freestyle compensations.

Most production agent platforms land on a hybrid: Temporal or Step Functions for the money path, Kafka or SNS for everything that can catch up asynchronously. The saga pattern is not about picking a camp — it is about knowing which parts of your workflow need a conductor and which parts can improvise together.

## Resources

- [Microservices.io — Saga pattern](https://microservices.io/patterns/data/saga.html) — Chris Richardson's reference on orchestration vs choreography tradeoffs
- [Temporal documentation — Saga workflows](https://docs.temporal.io/develop/typescript/safe-deployments) — Durable execution and compensation patterns
- [AWS Step Functions — Handling error conditions](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html) — Catch/retry/compensate in ASL
- [Enterprise Integration Patterns — Event-driven architecture](https://www.enterpriseintegrationpatterns.com/patterns/messaging/) — Messaging patterns underlying choreographed sagas
- [Google Cloud — Transaction patterns for microservices](https://cloud.google.com/architecture/microservices-architecture-distributed-transactions) — Decision guide for sagas vs two-phase commit
