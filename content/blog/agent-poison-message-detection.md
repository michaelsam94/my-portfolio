---
title: "AI Agents: Poison Message Detection"
slug: "agent-poison-message-detection"
description: "Detect and isolate poison messages in agent job queues: retry budgets, DLQ routing, failure classification, and recovery workflows that stop one bad payload from stalling the fleet."
datePublished: "2024-11-13"
dateModified: "2024-11-13"
tags: ["AI", "Agent", "Poison"]
keywords: "poison message detection, dead letter queue, agent job queue, retry budget, message failure classification, SQS DLQ Kafka poison pill"
faq:
  - q: "What makes a message poison in an agent pipeline?"
    a: "Any message that fails processing every time it is consumed—malformed tool args, references to deleted tenant config, prompt templates that trigger unhandled exceptions, or payloads that exceed context limits after retries. Poison messages are deterministic failures masquerading as transient errors, causing infinite redelivery until the queue backs up."
  - q: "How many retries before quarantining a message?"
    a: "Use receive-count thresholds aligned with idempotency: 3–5 attempts for LLM tool invocation jobs with exponential backoff, fewer (2–3) for fast-fail validation errors detected on first parse. Combine absolute receive count with a retry budget per correlation ID so variant failures of the same root cause share fate."
  - q: "Should poison messages ever re-enter the main queue automatically?"
    a: "Only after explicit replay from a DLQ with a fixed payload or schema version bump—not via automatic redrive without human or automated triage passing classification rules. Auto-redrive without root-cause fix recreates the incident within minutes."
  - q: "How do agent-specific failures differ from generic microservice poison pills?"
    a: "Agent jobs fail on model 429s (transient), token limit exceeded (often permanent for that payload), tool sandbox timeouts (maybe transient), and embedding dimension mismatches after deploy (permanent until model version aligned). Classifiers must inspect error types, not only HTTP status codes."
---
One malformed tool-call payload—an `order_id` field containing a nested JSON blob instead of a string—sat in the agent work queue for eleven hours. Every consumer crashed in the deserialization hook, nacked the message, and moved on. With visibility timeout set to 30 seconds and four workers, the same message consumed roughly 5,000 CPU minutes before someone noticed queue age p99 spiking while error rate dashboards looked "fine" because each worker logged and moved on.

Poison message detection is how agent platforms distinguish **retry tomorrow** from **never going to work**. Without it, a single bad job cycles forever, starving legitimate agent tasks and burning LLM budget on doomed retries. This post covers classification, quarantine architecture, and recovery for agent-specific failure modes.

## Anatomy of a retry storm

```
Producer ──▶ [ Main queue ] ──▶ Worker pool ──▶ LLM / tools
                  ▲                    │
                  │         fail + nack (no DLQ)
                  └────────────────────┘
                         same message forever
```

Symptoms:

- Queue depth grows linearly while worker CPU stays high.
- Per-message age exceeds p99 SLA by orders of magnitude.
- Error logs show identical stack traces; trace IDs differ.
- LLM spend rises with zero successful task completions.

Generic alerting on error rate misses this—each attempt is a "handled" failure.

## Failure taxonomy for agent jobs

Classify before retry policy:

| Class | Examples | Retry? | Action |
|-------|----------|--------|--------|
| Transient | 429, 503, network blip | Yes, backoff | Leave in main queue |
| Permanent input | Schema validation, unknown tool | No | DLQ immediately |
| Permanent config | Missing tenant secret, deprecated model | No | DLQ + page tenant owner |
| Poison content | Prompt bomb, decompression zip slip | No | DLQ + security review |
| Ambiguous | Tool timeout | Limited retry | DLQ after budget exhausted |

Agent workers should attach `failure_class` to structured logs on every catch block—not only `error.message`.

```python
from enum import Enum
from dataclasses import dataclass
import traceback

class FailureClass(str, Enum):
    TRANSIENT = "transient"
    PERMANENT_INPUT = "permanent_input"
    PERMANENT_CONFIG = "permanent_config"
    POISON_CONTENT = "poison_content"
    UNKNOWN = "unknown"


@dataclass
class ProcessingOutcome:
    success: bool
    failure_class: FailureClass | None = None
    retryable: bool = False
    detail: str = ""


def classify_exception(exc: Exception) -> ProcessingOutcome:
    name = type(exc).__name__
    if name in ("RateLimitError", "ServiceUnavailable", "TimeoutError"):
        return ProcessingOutcome(False, FailureClass.TRANSIENT, retryable=True, detail=name)
    if name in ("ValidationError", "JsonDecodeError", "KeyError"):
        return ProcessingOutcome(False, FailureClass.PERMANENT_INPUT, retryable=False, detail=name)
    if name in ("TenantConfigError", "ModelNotFoundError"):
        return ProcessingOutcome(False, FailureClass.PERMANENT_CONFIG, retryable=False, detail=name)
    if name in ("ContextLengthExceededError", "PromptInjectionBlocked"):
        return ProcessingOutcome(False, FailureClass.POISON_CONTENT, retryable=False, detail=name)
    return ProcessingOutcome(False, FailureClass.UNKNOWN, retryable=True, detail=name)
```

Start with exception type mapping; evolve to a small rules engine inspecting payload hash + error combo for UNKNOWN reduction.

## Retry budget and receive count

Two limits work together:

1. **Per-message receive count** — SQS `ApproximateReceiveCount`, Kafka consumer retry headers, or Redis stream delivery counter.
2. **Per-correlation retry budget** — same `job_id` or `session_id` should not consume more than N total attempts across requeues.

```typescript
interface RetryState {
  receiveCount: number;
  firstSeenAt: string;
  lastErrorClass: string;
  payloadHash: string;
}

const MAX_RECEIVES = 5;
const MAX_AGE_MS = 60 * 60 * 1000; // 1 hour wall clock cap

function shouldQuarantine(state: RetryState, outcome: ProcessingOutcome): boolean {
  if (!outcome.retryable) return true;
  if (state.receiveCount >= MAX_RECEIVES) return true;
  if (Date.now() - Date.parse(state.firstSeenAt) > MAX_AGE_MS) return true;
  if (state.lastErrorClass === outcome.detail && state.receiveCount >= 3) return true;
  return false;
}
```

Wall-clock cap catches messages with long backoff that still never succeed.

## Dead letter queue design

DLQ messages need **more context** than main queue messages:

```json
{
  "original_payload_ref": "s3://agent-dlq/payloads/abc123.json",
  "failure_class": "permanent_input",
  "receive_count": 7,
  "last_error": "ValidationError: order_id must be string",
  "worker_version": "agent-worker-2.8.1",
  "model_version": "gpt-4o-2024-08-06",
  "correlation_id": "sess_9f2c",
  "quarantined_at": "2024-11-13T14:22:01Z",
  "payload_hash": "sha256:…"
}
```

Store fat payloads in object storage; DLQ carries pointer—SQS 256 KB limit bites agent jobs with embedded document chunks.

Encrypt DLQ at rest; payloads may contain user PII even when "poison."

Restrict DLQ consume IAM to break-glass roles. Replay tooling uses a separate `dlq-replayer` service account audited per message.

## Detection heuristics beyond receive count

**Stack trace fingerprinting** — hash top three frames; if one fingerprint exceeds 50% of failures in 10 minutes while queue depth rises, likely poison or bad deploy.

**Payload hash clustering** — same `payload_hash`, 100% failure rate, zero successes globally → auto-quarantine on next receive without waiting for MAX_RECEIVES.

**Canary consumer** — low-priority worker that processes suspected poison messages with extended logging; isolate to single-threaded pool so poison does not block main fleet.

**Schema version gate** — reject messages with `schema_version < minimum_supported` to DLQ at enqueue time, not dequeue—cheap poison prevention at producer.

## Agent-specific poison patterns

**Context length bombs** — user uploads 400 pages; chunker emits 2,000 fragments each enqueued separately. Detection: preflight token estimate in producer; reject over budget before queue insert.

**Tool schema drift** — deploy changes JSON schema; old messages fail validation. Detection: spike in `PERMANENT_INPUT` after deploy; pause consumer, flush DLQ to fixed schema or reprocess with migration.

**Circular plan messages** — orchestrator re-enqueues same plan step with identical args after tool "soft failure." Detection: DAG cycle detection on `plan_hash` in correlation store; quarantine with `POISON_CONTENT` class.

**Model 404** — wrong model string after rename. Permanent config; alert tenant-scoped, not global page.

## Recovery and replay workflow

1. **Triage dashboard** — DLQ depth by `failure_class`, top `payload_hash`, link to object storage viewer (redacted).
2. **Fix root cause** — deploy schema fix, restore tenant config, patch validation.
3. **Replay ticket** — engineer selects DLQ IDs, replay service transforms payload if needed, inserts to main queue with `replay_generation` incremented.
4. **Verify** — replay jobs go to canary workers first; promote on success rate.

Never bulk redrive entire DLQ without filter—one unpatched poison message recreates storm.

```bash
# Example: replay single message after fix (conceptual CLI)
agent-dlq replay \
  --id msg_01HF... \
  --transform fix-order-id-string \
  --target-queue agent-jobs \
  --canary-percent 10
```

## Metrics and alerts

| Metric | Alert when |
|--------|------------|
| `queue_oldest_message_age_seconds` | > SLA × 3 for 15 min |
| `dlq_inflow_rate` | > baseline × 5 |
| `receive_count_max` | any message > MAX_RECEIVES still in main queue |
| `failure_fingerprint_top1_ratio` | > 0.5 for 10 min |
| `retry_budget_exhausted_total` | any increase post-deploy |

Dashboard panel: messages grouped by `payload_hash` with success/fail ratio—poison shows 0% success bar.

## Testing poison paths

Chaos tests:

- Inject permanently failing message; assert reaches DLQ within MAX_RECEIVES.
- Inject transient failures (mock 503 twice, succeed third)—assert never DLQ.
- Flood queue with poison + legit mix; assert legit p95 latency within SLO (poison isolation works).

Contract test producer validation rejects oversize payloads before publish.

## Closing thought

Poison message detection is operational hygiene for any agent platform using async jobs. Classify failures honestly, cap retries with wall-clock budgets, enrich DLQ entries for triage, and treat automatic redrive as guilty until proven innocent. The queue that looks healthy while one message eats the fleet is a failure mode you only hit once—unless you build detection on purpose.

## Resources

- [AWS SQS Dead-Letter Queues](https://docs.aws.amazon.com/AWSSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html) — receive count redrive patterns.
- [Azure Service Bus dead-lettering](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues) — subqueue semantics and monitoring.
- [Apache Kafka: handling poison pills](https://kafka.apache.org/documentation/#design_concepts_compaction) — log compaction vs DLQ topic patterns.
- [Google Cloud Pub/Sub dead-letter topics](https://cloud.google.com/pubsub/docs/dead-letter-topics) — delivery attempt thresholds.
- [Enterprise Integration Patterns: Dead Letter Channel](https://www.enterpriseintegrationpatterns.com/DeadLetterChannel.html) — foundational messaging pattern reference.
