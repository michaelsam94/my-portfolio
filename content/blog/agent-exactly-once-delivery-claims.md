---
title: "AI Agents: Exactly Once Delivery Claims"
slug: "agent-exactly-once-delivery-claims"
description: "Exactly Once Delivery Claims: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-11-17"
dateModified: "2024-11-17"
tags: ["AI", "Agent", "Exactly"]
keywords: "agent, exactly, once, delivery, claims, ai, production, engineering, architecture"
faq:
  - q: "Is exactly-once delivery actually possible in distributed systems?"
    a: "Pure exactly-once end-to-end is impossible under the laws of distributed systems—networks drop acknowledgments, processes crash mid-handler, and brokers redeliver. What vendors mean is 'exactly-once semantics': the effect on your application state happens once, achieved by idempotent consumers plus transactional outbox or broker deduplication. The claim is about observable outcomes, not magic transport."
  - q: "Why do agent pipelines care more than typical microservices?"
    a: "A duplicate Kafka message that double-charges a penny is annoying. A duplicate agent job that sends two wire transfers, indexes the same document twice into a vector store, or runs a destructive shell tool twice is catastrophic. Agent side effects are expensive, irreversible, and externally visible. At-least-once delivery is the default; without idempotency you get at-most-never-trust."
  - q: "What is the difference between idempotency keys and broker exactly-once?"
    a: "Idempotency keys are application-layer: the consumer records 'job-abc already processed' and skips. Broker exactly-once (e.g., Kafka transactions) guarantees no duplicate records within a stream under specific producer configs—but your tool calls still need idempotency because the broker cannot see past your consumer. Use both: broker features shrink the duplicate window; app idempotency closes the gap."
  - q: "How do I test that duplicates are harmless?"
    a: "Chaos-test by replaying messages deliberately. In staging, wrap consumers with a fault injector that delivers each message 2–3 times. Assert downstream state: one row in billing, one vector embedding, one Slack notification. Property: effect_count(message_id) == 1 for all idempotent handlers."
---
The Kafka consumer group looked healthy. Lag was zero. Yet finance found duplicate invoice line items—same `job_id`, same amount, timestamps two seconds apart. The agent worker had processed `RunBillingSync` twice after a rebalance left the first attempt's offset uncommitted. The broker delivered at-least-once, as designed. The handler was not idempotent, as assumed. Marketing called it "exactly-once Kafka." Engineering learned what the claim actually covered—which was not the credit card charge.

"Exactly-once delivery" is the most misunderstood phrase in event-driven agent architecture. This post unpacks what brokers and stream processors really guarantee, how to achieve exactly-once **effects** for tool calls and side effects, and how to stop believing checkbox semantics that stop at the consumer boundary.

## The impossibility result, practically stated

The classic two-generals problem applies: a producer cannot know if a message was processed after a network partition. Brokers choose among:

| Guarantee | Meaning | Duplicate risk |
|-----------|---------|----------------|
| At-most-once | Fire and forget; may lose messages | None |
| At-least-once | Retry until ack; may duplicate | High without idempotency |
| Exactly-once semantics | Effect applied once | Requires app + infra cooperation |

Kafka's EOS (idempotent producer + transactions), Pulsar deduplication, and SQS FIFO with deduplication IDs shrink duplicate **publication**. They do not make your `delete_file` tool safe when the consumer crashes after the delete but before commit.

For agents, the useful framing is **effectively-once processing**:

```
duplicate_messages × idempotent_handler = single_external_effect
```

## Where duplicates enter agent pipelines

**Consumer rebalance.** Partition reassigned while handler runs; offset not committed → redelivery.

**Visibility timeout expiry.** SQS message not deleted in time; another worker picks it up.

**HTTP webhook retries.** Tool gateway returns 500 after succeeding; caller retries.

**Orchestrator at-least-once.** Temporal, Step Functions, and custom schedulers retry activities on timeout—even if the activity completed but the ack was lost.

**Human-in-the-loop resume.** User clicks "retry"; system resubmits same `session_id` job.

Each path is normal. Treating duplicates as exceptional guarantees incidents.

## Idempotency keys: the application layer contract

Every externally visible command carries an idempotency key—`job_id`, `session_id + step_index`, or client-supplied UUID.

```typescript
// workers/idempotent-handler.ts
import { createHash } from "crypto";

interface JobEnvelope {
  idempotencyKey: string;
  type: string;
  payload: unknown;
}

export async function handleJob(
  db: Db,
  envelope: JobEnvelope,
  execute: (payload: unknown) => Promise<void>,
): Promise<"processed" | "duplicate" | "in_flight"> {
  const keyHash = createHash("sha256").update(envelope.idempotencyKey).digest("hex");

  return db.transaction(async (tx) => {
    const { rows } = await tx.query(
      `INSERT INTO idempotency_records (key_hash, status, created_at)
       VALUES ($1, 'in_flight', now())
       ON CONFLICT (key_hash) DO NOTHING
       RETURNING key_hash`,
      [keyHash],
    );

    if (rows.length === 0) {
      const existing = await tx.query(
        `SELECT status FROM idempotency_records WHERE key_hash = $1`,
        [keyHash],
      );
      return existing.rows[0].status === "completed" ? "duplicate" : "in_flight";
    }

    try {
      await execute(envelope.payload);
      await tx.query(
        `UPDATE idempotency_records SET status = 'completed', completed_at = now()
         WHERE key_hash = $1`,
        [keyHash],
      );
      return "processed";
    } catch (err) {
      await tx.query(`DELETE FROM idempotency_records WHERE key_hash = $1`, [keyHash]);
      throw err; // allow broker retry
    }
  });
}
```

Critical details:

- **Claim in-flight atomically** before side effects.
- **Delete in-flight record on failure** so legitimate retries can proceed.
- **Store completion persistently** so duplicates short-circuit.
- **TTL stale in-flight records** (e.g., 24h) for crash recovery with manual review.

## Transactional outbox: aligning DB and broker

Dual-write problem: you update Postgres and publish to Kafka—one can succeed, one fail.

Outbox pattern: write business row + outbox row in one transaction; separate relay publishes to broker.

```sql
CREATE TABLE outbox (
  id         BIGSERIAL PRIMARY KEY,
  topic      TEXT NOT NULL,
  payload    JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  published  BOOLEAN DEFAULT false
);
```

```python
# In same transaction as domain write
def complete_agent_step(conn, session_id, step_result):
    conn.execute(
        "UPDATE agent_steps SET status = 'done', result = %s WHERE id = %s",
        (step_result, session_id),
    )
    conn.execute(
        "INSERT INTO outbox (topic, payload) VALUES (%s, %s)",
        (
            "agent.step.completed",
            json.dumps({"session_id": session_id, "idempotency_key": session_id}),
        ),
    )
```

Relay uses `FOR UPDATE SKIP LOCKED` or Debezium CDC. Consumers still need idempotency—outbox guarantees **at-least-once publication**, not effect-once.

## Broker-level exactly-once: what Kafka EOS actually covers

Kafka transactions let a producer send to multiple partitions atomically and commit consumer offsets in the same transaction—isolation within the streaming layer.

```java
// Simplified Kafka EOS producer concept
props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
props.put(ProducerConfig.TRANSACTIONAL_ID_CONFIG, "agent-worker-1");

producer.initTransactions();
producer.beginTransaction();
producer.send(new ProducerRecord<>("agent-events", key, value));
producer.sendOffsetsToTransaction(offsets, consumerGroupMetadata);
producer.commitTransaction();
```

This prevents duplicate **records in the log** under broker failure modes the transaction covers. It does not prevent:

- Your consumer calling OpenAI twice
- Two different consumers processing logically duplicate jobs on different topics
- A bug that emits two events with different keys for one user action

Use EOS to keep event logs clean; still implement idempotent handlers for tools.

## Agent tool calls: designing for safe retry

Tools are the danger zone. Classify each tool:

| Tool class | Idempotency strategy |
|------------|---------------------|
| Read-only (search, GET) | Naturally safe; still dedupe to save cost |
| Create with server ID | Pass idempotency key to external API (Stripe, Slack) |
| Update / delete | Use version numbers or If-Match headers |
| Irreversible (shell, email) | Guard with pre-check + idempotency store; prefer dry-run event first |

```typescript
async function invokeTool(
  tool: Tool,
  args: unknown,
  idempotencyKey: string,
): Promise<ToolResult> {
  if (tool.supportsIdempotencyKey) {
    return tool.execute(args, { idempotencyKey });
  }
  if (tool.sideEffectClass === "irreversible") {
    const prior = await idempotencyStore.get(idempotencyKey);
    if (prior) return prior.result;
  }
  // Read-only: execute but cache result by key
  return tool.execute(args);
}
```

Document tool idempotency in the agent's tool manifest—planners and eval harnesses need to know which tools can be safely retried.

## Dedup windows and vector store pitfalls

Embedding pipelines often claim exactly-once because "we use a unique document ID." Reprocessing the same `doc_id` with unchanged content should upsert, not duplicate. Use deterministic IDs:

```
vector_id = hash(tenant_id + source_uri + content_version)
```

Reindex jobs that change embedding models bump `content_version` intentionally. Blind re-ingest without version logic creates near-duplicate vectors that poison retrieval.

## Observability: proving effect-once

Metrics that matter:

- `idempotency_duplicate_skipped_total` — healthy non-zero in production
- `idempotency_in_flight_stuck` — alert if > 0 for > 5 minutes
- `side_effect_count_by_key` — should never exceed 1; assert in tests

Structured logs on every handler:

```json
{
  "event": "job_handled",
  "idempotency_key": "sess_abc_step_3",
  "outcome": "duplicate",
  "handler": "RunBillingSync"
}
```

During incidents, grep `outcome=processed` grouped by key—duplicates show immediately.

## Testing duplicate delivery

**Replay harness.** Export production messages (sanitized) and feed each twice to staging consumers.

**Fault injection middleware.**

```python
async def maybe_duplicate(next_handler, message):
    await next_handler(message)
    if os.getenv("CHAOS_DUPLICATE_RATE", "0") == "1":
        await next_handler(message)  # intentional double delivery
```

**Contract tests with external APIs.** Mock Stripe/Slack idempotency endpoints; verify your client sends the same key on retry.

Game-day scenario: kill consumer pod after tool success, before offset commit. Verify one external effect when pod restarts.

## What to say in architecture reviews

When someone claims "exactly-once delivery," ask:

1. Exactly-once **what**—broker records, consumer processing, or external side effects?
2. What happens on rebalance mid-handler?
3. Where is the idempotency key generated and stored?
4. Is the outbox pattern used for DB + event alignment?
5. Show the test that delivers the same message three times.

Honest answers sound like: "At-least-once transport with idempotent consumers and transactional outbox; external APIs use provider idempotency keys." That is production-grade. "Exactly-once Kafka" without the rest is marketing.

## The takeaway

Exactly-once delivery claims describe semantics, not miracles. Agent systems need effectively-once **effects**: idempotency records at the handler, transactional outbox for publish consistency, broker EOS where appropriate, and tool manifests that classify retry safety. Test by duplicating messages on purpose. The goal is not zero duplicates in the log—it is zero duplicate wire transfers, emails, and database destroys.

## Resources

- [Kafka documentation — Exactly-once semantics](https://kafka.apache.org/documentation/#semantics)
- [Jepsen analyses of distributed systems](https://jepsen.io/analyses)
- [Stripe idempotent requests](https://stripe.com/docs/api/idempotent_requests)
- [Microservices.io — Transactional outbox pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [AWS SQS FIFO deduplication](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html)
