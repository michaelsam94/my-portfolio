---
title: "Workflow Idempotency Keys"
slug: "llm-workflow-idempotency-keys"
description: "Design idempotency keys for agent workflows: tool side effects, Temporal run IDs, HTTP Idempotency-Key headers, and deduplication stores that survive retries and human double-clicks for teams running LLM features in production."
datePublished: "2026-04-23"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "agent workflow idempotency keys, dedupe agent tool calls, Temporal idempotent workflow, Idempotency-Key header"
faq:
  - q: "Where should idempotency keys originate in agent systems?"
    a: "Client or gateway generates keys at workflow start — format `{tenant_id}:{client_request_id}`. Tool calls inherit `{workflow_key}:{step_id}`. Never let the LLM invent keys; inject deterministically from orchestration layer."
  - q: "How long should idempotency records live?"
    a: "Minimum 24–72 hours for HTTP API semantics; 30 days for financial agent workflows aligned with billing dispute windows. TTL must exceed max retry horizon including DLQ replays."
  - q: "What if the same key is reused with different parameters?"
    a: "Return 409 Conflict with stored response hash mismatch — never silently return wrong result. Log potential attack or client bug. Agent orchestrator should treat as fatal for that run."
  - q: "Does Temporal replace application idempotency keys?"
    a: "Temporal gives run-level dedupe via WorkflowId reuse policy — not substitute for tool side-effect idempotency. Combine: Temporal WorkflowId for orchestration, idempotency keys on each external API call inside activities."
---
Users double-click Approve. Load balancers retry POSTs. Temporal activities replay after worker crash. LLM agents hallucinate progress but the **payment tool already ran**. Idempotency keys are how agent workflows guarantee "exactly-once semantics where it matters" without pretending networks are reliable.

## Layers of idempotency

```
Client Idempotency-Key
        │
        ▼
Gateway dedupe (HTTP 409/200 replay)
        │
        ▼
Workflow engine (Temporal WorkflowId)
        │
        ▼
Activity / tool call keys → external APIs
        │
        ▼
Downstream provider (Stripe Idempotency-Key)
```

Each layer covers different retry sources — don't skip inner layers because outer exists.

## Key format conventions

```text
# User-initiated agent run
idem:tenant_42:usr_click_20260717_abc123

# Tool step within run
idem:run_9f3:step_send_invoice:v1

# Scheduled cron agent
idem:tenant_42:daily_reconcile:2026-07-17
```

Properties:

- Stable across retries of **same logical operation**
- Unique across **different** operations
- Include tenant scope to prevent cross-tenant collision in shared stores

## HTTP gateway pattern

```python
from fastapi import Header, HTTPException

@app.post("/v1/agent/runs")
async def start_run(
    body: StartRunRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
):
    scope = f"{body.tenant_id}:{idempotency_key}"
    cached = idem_store.get(scope)
    if cached:
        if cached.request_hash != hash(body):
            raise HTTPException(409, "idempotency key reused with different body")
        return cached.response

    run = orchestrator.start(body)
    idem_store.put(scope, hash(body), run, ttl=86400 * 3)
    return run
```

Clients (mobile, web) generate UUIDv4 `Idempotency-Key` per button click.

## Temporal workflow IDs

```python
# temporal starter
async def start_agent_workflow(tenant_id: str, client_key: str, input: RunInput):
    workflow_id = f"agent-run/{tenant_id}/{client_key}"
    handle = await client.start_workflow(
        AgentRunWorkflow.run,
        input,
        id=workflow_id,
        id_reuse_policy=WorkflowIdReusePolicy.REJECT_DUPLICATE,
    )
    return handle
```

`REJECT_DUPLICATE` prevents two runs for same user action; use `ALLOW_DUPLICATE_FAILED_ONLY` if retries after failure should restart.

## Activity-level tool idempotency

```python
@activity.defn
async def charge_customer(params: ChargeParams) -> ChargeResult:
    key = f"charge:{params.workflow_id}:{params.step_id}"
    existing = await idem_store.get(key)
    if existing:
        return existing

    result = stripe.PaymentIntent.create(
        amount=params.amount,
        currency="usd",
        customer=params.customer_id,
        idempotency_key=key,
    )
    await idem_store.put(key, result, ttl=86400 * 30)
    return result
```

Stripe dedupes on their side; your store avoids duplicate API calls before network round trip.

## Dedupe store implementation

Redis with SET NX:

```python
def reserve(key: str, ttl_sec: int) -> bool:
    return redis.set(f"idem:{key}", "pending", nx=True, ex=ttl_sec)

def complete(key: str, response: dict):
    redis.set(f"idem:{key}", json.dumps(response), ex=ttl_sec)
```

Postgres for audit-grade durability:

```sql
CREATE TABLE idempotency_keys (
  scope text PRIMARY KEY,
  request_hash bytea NOT NULL,
  response jsonb NOT NULL,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX ON idempotency_keys (created_at);
```

## LLM non-determinism vs idempotent side effects

Model output varies; **side effects must not**. Pattern:

1. Plan phase — LLM proposes tool calls (no side effects).
2. Commit phase — orchestrator executes tools with idempotency keys (deterministic).
3. Re-plan on tool results — new LLM turn.

Never interleave unguarded tool execution inside streaming generation.

## Human-in-the-loop approval

Approval token doubles as idempotency scope:

```python
def on_approval(approval_id: str, decision: str):
    key = f"approval:{approval_id}"
    if not reserve(key, ttl=86400 * 7):
        return get_stored_outcome(key)
    outcome = execute_approved_tools(approval_id, decision)
    complete(key, outcome)
```

Second click on Approve returns same outcome — no double ship.

## Testing idempotency

```python
def test_duplicate_start_run_returns_same_run_id(client):
    headers = {"Idempotency-Key": "test-key-1"}
    r1 = client.post("/v1/agent/runs", json=payload, headers=headers)
    r2 = client.post("/v1/agent/runs", json=payload, headers=headers)
    assert r1.json()["run_id"] == r2.json()["run_id"]
    assert orchestrator.start.call_count == 1
```

Chaos: kill worker mid-activity, verify replay doesn't double-charge.

## Metrics

- `idempotency_cache_hit_total` — healthy on retries
- `idempotency_conflict_409_total` — investigate client bugs
- `tool_duplicate_prevented_total` by tool name

## Resources

- [Stripe — Idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [Temporal — Workflow Id reuse policies](https://docs.temporal.io/workflows#workflow-id-reuse-policy)
- [IETF draft — Idempotency-Key header](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header)
- [AWS — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.
