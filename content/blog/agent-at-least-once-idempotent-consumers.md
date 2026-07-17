---
title: "AI Agents: At Least Once Idempotent Consumers"
slug: "agent-at-least-once-idempotent-consumers"
description: "Build agent event consumers that survive at-least-once delivery—dedup keys, idempotent side effects, offset commit ordering, and poison-message handling without double-charging LLM runs."
datePublished: "2024-11-20"
dateModified: "2024-11-20"
tags: ["AI", "Agent"]
keywords: "at-least-once delivery, idempotent consumers, message deduplication, Kafka consumer, agent event processing, exactly-once semantics"
faq:
  - q: "Is at-least-once delivery good enough for agent pipelines?"
    a: "Yes, if every consumer is idempotent. Brokers and cloud queues guarantee at-least-once in practice—crashes between processing and ack always redeliver. Agent side effects (LLM calls, tool invocations, billing) cannot tolerate duplicates unless you deduplicate or make writes safe to replay."
  - q: "Where should idempotency keys live for agent events?"
    a: "Prefer the event envelope: stable idempotency_key derived from upstream run_id + step_name + attempt. Store processed keys in a dedup table or cache with TTL exceeding max redelivery window. Do not rely solely on Kafka offset—rebalances and replays skip offsets differently."
  - q: "When should consumers commit offsets relative to side effects?"
    a: "Commit only after side effects are durable and dedup record is written—process-store-commit order. Committing before a successful LLM tool call causes lost work on crash; committing after without dedup causes double execution on redelivery."
  - q: "How do you handle poison messages that fail idempotency checks?"
    a: "After N failures with the same idempotency_key, route to a dead-letter queue with full payload and consumer version. Do not skip offset on main partition without DLQ—silent loss is worse than duplicate. Alert on DLQ rate; replay only after fixing the handler bug."
---
Our agent billing dashboard showed 847 runs for a batch that should have produced 812. The diff traced to a Kafka consumer that crashed after calling OpenAI but before committing its offset. On restart, every in-flight message ran again—same prompt, same tool chain, **new invoice line items**. The broker did exactly what at-least-once promises. We did not.

Agent platforms are event-heavy: run queued, step completed, tool result ingested, embedding job finished. Every handler must assume **the same message arrives twice** and still leave the system correct. This is not pessimism—it is the contract your queue already gives you.

## Delivery semantics in one diagram

```
Producer ──► Broker (persists) ──► Consumer
                  │                    │
                  │                    ├─ Process (maybe slow)
                  │                    ├─ Crash here → redelivery
                  │                    └─ Commit offset
```

| Guarantee | What you get | Agent risk |
|-----------|--------------|------------|
| At-most-once | No duplicates | Lost runs, stuck workflows |
| At-least-once | No loss, duplicates possible | Double LLM spend, duplicate emails |
| Exactly-once | Broker marketing | End-to-end still needs idempotent sinks |

Practical agent stacks choose at-least-once plus idempotent consumers. Chasing Kafka exactly-once semantics across Postgres, Stripe, and external APIs rarely pays off.

## Idempotency key design

An idempotency key must be **stable across redeliveries** and **unique across distinct work**.

Good sources:

- `run_id` + `step_index` for orchestration events
- Upstream `event_id` UUID if producer assigns one at creation
- Hash of `(tenant_id, workflow_id, logical_operation, input_version)`

Bad sources:

- Kafka `(topic, partition, offset)` — changes on repartitioning
- `Date.now()` inside the consumer
- LLM response content — nondeterministic at non-zero temperature

```typescript
import { createHash } from "crypto";

export function idempotencyKey(event: AgentEvent): string {
  const material = [
    event.tenant_id,
    event.run_id,
    event.step_name,
    String(event.input_version ?? 0),
  ].join("|");
  return createHash("sha256").update(material).digest("hex");
}
```

Include `input_version` when step inputs can be patched and re-emitted under the same step name.

## The dedup store

Track processed keys before performing irreversible side effects:

```sql
CREATE TABLE consumer_dedup (
  idempotency_key   TEXT PRIMARY KEY,
  consumer_group    TEXT NOT NULL,
  processed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  result_ref        TEXT,  -- optional pointer to output artifact
  expires_at        TIMESTAMPTZ NOT NULL
);

CREATE INDEX ON consumer_dedup (expires_at);
```

TTL should exceed broker redelivery window (often 7 days for SQS visibility timeout stacks; Kafka depends on retention). Expired keys allow intentional replay after bug fixes—version your handler and use a new `input_version` when semantics change.

For high-throughput paths, Redis SET with TTL works as a fast filter backed by Postgres for audit:

```python
async def try_claim(key: str, group: str, ttl_seconds: int = 604800) -> bool:
    # SET NX — only first consumer wins
    claimed = await redis.set(f"dedup:{group}:{key}", "1", nx=True, ex=ttl_seconds)
    if not claimed:
        return False
    await db.execute(
        "INSERT INTO consumer_dedup (idempotency_key, consumer_group, expires_at) "
        "VALUES ($1, $2, now() + interval '7 days') ON CONFLICT DO NOTHING",
        key, group,
    )
    return True
```

## Consumer loop: correct ordering

```python
async def consume(message: AgentEvent, handler_version: str) -> None:
    key = idempotency_key(message)

    if not await try_claim(key, CONSUMER_GROUP):
        metrics.increment("consumer.duplicate_skipped")
        return  # safe no-op; still ack message

    try:
        result = await execute_side_effects(message)  # LLM, DB writes, webhooks
        await store_result_ref(key, result.id)
        await commit_offset(message)
    except TransientError as e:
        await release_claim(key)  # allow redelivery
        raise
    except PermanentError as e:
        await dead_letter(message, reason=str(e), handler_version=handler_version)
        await commit_offset(message)  # do not block partition forever
```

Critical details:

1. **Claim before side effects** — two concurrent deliveries must not both pass.
2. **Release claim on transient failure** — otherwise you drop work permanently.
3. **DLQ on permanent failure** — with handler version for replay tooling.
4. **Ack/commit after success path completes** — including dedup persist.

## Making side effects idempotent

Dedup is the outer gate; inner operations should still be safe if dedup TTL expires.

**Database writes:** use upserts keyed on business id:

```sql
INSERT INTO agent_run_steps (run_id, step_index, status, output_json)
VALUES ($1, $2, 'completed', $3)
ON CONFLICT (run_id, step_index)
DO UPDATE SET
  status = EXCLUDED.status,
  output_json = EXCLUDED.output_json,
  updated_at = now()
WHERE agent_run_steps.status != 'completed';
```

The `WHERE` clause prevents overwriting a completed step with stale retry data.

**External APIs:** pass provider idempotency headers. OpenAI and Stripe both support idempotency keys—reuse your envelope key:

```typescript
await openai.chat.completions.create(
  { model: "gpt-4o", messages },
  { headers: { "Idempotency-Key": idempotencyKey } }
);
```

**Tool invocations:** store `(run_id, tool_name, args_hash)` → `external_ref` and return cached ref on duplicate.

## Agent-specific patterns

**Run orchestrator consumer:** emits step jobs. Idempotency on `(run_id, step_index)` prevents duplicate parallel steps that race on shared state.

**Embedding worker:** content hash as key. Re-embedding identical document after redelivery should overwrite same vector row, not duplicate index entries.

**Webhook notifier:** HMAC-signed payload with `event_id`. Receivers deduplicate; your consumer still dedups before POST to avoid partner rate limits.

**Billing aggregator:** sum token usage with `(run_id, step_index)` granularity. Never `+=` on redelivery—use insert-only usage rows with unique constraint.

## Offset commit vs transactional outbox

Some teams wrap DB write + offset commit in one transaction (Kafka transactions). That helps when the **only** sink is your database. Agent pipelines call external LLM APIs—those cannot join your Kafka transaction.

Pattern that works:

1. Dedup claim in DB transaction with workflow state update.
2. Side effect outside transaction.
3. On side effect success, mark step complete; on failure, release claim.

If side effect succeeds but mark-complete fails, redelivery hits dedup—return cached result from `result_ref` instead of re-calling the LLM.

```python
async def execute_with_cache(message: AgentEvent, key: str):
    existing = await get_result_ref(key)
    if existing:
        return existing
    result = await call_llm_and_tools(message)
    await save_result_ref(key, result.id)
    return result
```

## Poison messages and DLQ replay

Define `MAX_ATTEMPTS = 5` with exponential backoff. Same `idempotency_key` incrementing attempt counter in logs—not in the key itself.

DLQ payload should include:

- Original event JSON
- Stack trace and handler version
- Partition, offset, timestamp
- Tenant id for scoped replay tools

Replay tooling must **require** explicit operator action and bump handler version or event `input_version`. Blind DLQ re-inject without code fix replays the poison.

## Observability

Metrics that catch duplicate damage early:

- `consumer.duplicate_skipped` — should correlate with rebalance events, not baseline traffic
- `consumer.dedup_claim_contention` — concurrent delivery attempt rate
- `llm.calls_per_run_id` — should be ~1; alert if p99 > 1.2
- `billing.tokens_per_run_id` — same
- DLQ depth by `error_class`

Trace id propagation: attach `run_id` and `idempotency_key` to every span so incident queries do not require grep across three systems.

## Testing redelivery

Unit tests are insufficient. Integration tests must:

1. Process message successfully.
2. Simulate crash before commit (do not commit offset).
3. Redeliver same message.
4. Assert exactly one LLM mock call and one billing row.

Use testcontainers for Kafka or SQS; inject a hook that throws `TransientError` on first attempt.

Property test: random crash points in handler should never increase `count(*)` on immutable ledger tables.

## When not to deduplicate

Some analytics events **want** counts of attempts including failures. Route those to a separate fire-and-forget topic without idempotent sinks—never mix with billing or tool execution on the same consumer without branching logic.

At-least-once is not a bug in your broker—it is physics. Idempotent consumers turn redelivery from a financial incident into a metric blip. Design keys from day one, claim before spend, cache results after success, and drill redelivery in game days before Black Friday traffic does it for you.

Document the redelivery contract in your internal agent SDK README: every handler author must declare idempotency keys and side-effect class ( reversible vs irreversible ) before merge. Code review without that checklist is how duplicate LLM invoices return.

## Resources

- [Kafka Documentation — Consumer Semantics](https://kafka.apache.org/documentation/#semantics)
- [AWS SQS — Exactly-Once Processing (FIFO deduplication)](https://docs.aws.amazon.com/AWSSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues-exactly-once-processing.html)
- [Stripe Idempotent Requests](https://stripe.com/docs/api/idempotent_requests)
- [OpenAI API — Idempotency](https://platform.openai.com/docs/api-reference/requesting-idempotency)
- [Designing Data-Intensive Applications — Ch. 11 (Stream Processing)](https://dataintensive.net/)
