---
title: "AI Agents: Dead Letter Queue Handling"
slug: "agent-dead-letter-queue-handling"
description: "Dead Letter Queue Handling: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-11-11"
dateModified: "2024-11-11"
tags: ["AI", "Agent", "Dead"]
keywords: "agent, dead, letter, queue, handling, ai, production, engineering, architecture"
faq:
  - q: "When should an agent job go to the DLQ instead of retrying?"
    a: "Route to DLQ when failure is deterministic: schema validation errors, unknown tool names after deploy, token payloads that exceed model context even after compression, or tenant config that no longer exists. Transient failures—429 rate limits, network blips, sandbox cold starts—belong on the main queue with backoff until a retry budget exhausts."
  - q: "What metadata must every DLQ message carry?"
    a: "Original payload hash, receive count, last error class and message, correlation/trace ID, agent version, model ID, tenant ID, and timestamps for first failure and DLQ arrival. Without this envelope, replay becomes guesswork and root-cause analysis spans hours."
  - q: "How do you replay DLQ messages safely after a fix?"
    a: "Never bulk-redrive without triage. Replay through a staging consumer with the fixed code, validate success rate on a sample batch, then redrive in tenant-scoped batches with idempotency keys so duplicate side effects cannot occur. Cap replay rate to avoid thundering herds on LLM APIs."
  - q: "How is agent DLQ handling different from generic microservice DLQs?"
    a: "Agent jobs are expensive—each retry may invoke an LLM, burn embedding quota, or trigger paid external APIs. DLQ policies must account for cost per retry, partial completion (tool A succeeded, tool B failed), and content that may be toxic or oversized rather than treating all failures as equal HTTP errors."
---
A support agent queue held 14,000 messages. Four hundred sat in the dead letter queue for three weeks—nobody owned the dashboard. Each DLQ entry was a customer ticket summarization job that failed when a prompt template referenced a retired tool schema. Engineers fixed the template on day two. Without a replay workflow, those tickets never got AI-assisted responses; customers waited while the main queue processed new work fine.

Dead letter queues are where agent platforms store **work that will not succeed without intervention**. Treating DLQ as a graveyard guarantees silent data loss. Treating it as an operational queue—with classification, triage, and controlled replay—is what separates demo pipelines from production systems.

## DLQ architecture for agent pipelines

Agent workloads typically fan out: orchestrator → tool workers → LLM completion → post-process → webhook. Failures can occur at any stage with different retry semantics.

```
                    ┌──▶ tool-worker ──┐
Orchestrator ──▶ Q ─┤                  ├──▶ completion ──▶ Q ──▶ post-process
                    └──▶ retrieval ────┘         │
                                                   │ maxReceiveCount
                                                   ▼
                                              [ DLQ ]
                                                   │
                                    triage UI / automated classifier
                                                   │
                              replay (staging) ──▶ main Q
```

Design principles:

- **One DLQ per failure domain** — do not mix tool failures with webhook delivery failures; replay policies differ.
- **Poison pill isolation** — messages exceeding receive count route to DLQ automatically; never infinite nack loops.
- **Partial state capture** — if tool A succeeded, persist intermediate state on the message envelope so replay does not re-bill.

## Failure classification before DLQ routing

Not every failure deserves the same path. Classify at the worker boundary:

| Class | Examples | DLQ? | Notes |
|-------|----------|------|-------|
| Transient | 429, 503, timeout | After budget | Exponential backoff first |
| Permanent input | Bad JSON, unknown enum | Immediate | Fix upstream producer |
| Permanent config | Missing API key for tenant | Immediate | Page tenant owner |
| Version skew | Tool schema mismatch post-deploy | Immediate | Replay after deploy sync |
| Cost abort | Token estimate > budget | Immediate | Needs prompt compression |
| Security | Jailbreak payload flagged | Separate DLQ | Restricted access |

```typescript
type FailureClass =
  | "transient"
  | "permanent_input"
  | "permanent_config"
  | "version_skew"
  | "cost_abort"
  | "security";

interface AgentJobEnvelope {
  jobId: string;
  tenantId: string;
  agentVersion: string;
  modelId: string;
  payloadHash: string;
  receiveCount: number;
  partialState?: Record<string, unknown>;
  traceId: string;
}

interface DLQDecision {
  route: "retry" | "dlq" | "security_dlq";
  failureClass: FailureClass;
  reason: string;
}

const MAX_RECEIVES = 5;
const TRANSIENT_BUDGET = 3;

function decideDLQ(
  envelope: AgentJobEnvelope,
  error: Error,
): DLQDecision {
  const cls = classifyError(error);

  if (cls === "security") {
    return { route: "security_dlq", failureClass: cls, reason: error.message };
  }

  if (cls === "transient") {
    if (envelope.receiveCount >= TRANSIENT_BUDGET) {
      return {
        route: "dlq",
        failureClass: cls,
        reason: `transient budget exhausted after ${envelope.receiveCount} attempts`,
      };
    }
    return { route: "retry", failureClass: cls, reason: "transient, backoff" };
  }

  // permanent classes
  return { route: "dlq", failureClass: cls, reason: error.message };
}

function classifyError(error: Error): FailureClass {
  if (error.name === "RateLimitError" || error.name === "ServiceUnavailable") {
    return "transient";
  }
  if (error.name === "ValidationError" || error.name === "SchemaMismatch") {
    return "permanent_input";
  }
  if (error.name === "TenantConfigMissing") {
    return "permanent_config";
  }
  if (error.name === "ToolNotFound") {
    return "version_skew";
  }
  if (error.name === "TokenBudgetExceeded") {
    return "cost_abort";
  }
  if (error.name === "SafetyViolation") {
    return "security";
  }
  return "transient"; // default conservative: retry until budget
}
```

## Enriching DLQ messages

Raw broker DLQ entries are insufficient. Wrap on send:

```python
import json
import hashlib
from datetime import datetime, timezone


def build_dlq_payload(original: dict, exc: Exception, envelope: dict) -> dict:
    return {
        "original_message": original,
        "dlq_metadata": {
            "arrived_at": datetime.now(timezone.utc).isoformat(),
            "first_failure_at": envelope.get("first_failure_at"),
            "receive_count": envelope["receive_count"],
            "failure_class": envelope.get("failure_class"),
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:2000],
            "agent_version": envelope["agent_version"],
            "model_id": envelope["model_id"],
            "tenant_id": envelope["tenant_id"],
            "trace_id": envelope["trace_id"],
            "payload_hash": hashlib.sha256(
                json.dumps(original, sort_keys=True).encode()
            ).hexdigest(),
            "partial_state": envelope.get("partial_state"),
        },
    }
```

Store DLQ payloads in durable object storage with broker reference if messages exceed size limits—agent jobs often carry large retrieved context blobs.

## Triage and replay workflows

**Triage dashboard** should group by `failure_class`, `agent_version`, and `tenant_id`. On-call engineers need one-click sample payload inspection with PII redaction, not raw JSON in CloudWatch.

**Replay pipeline:**

1. Filter DLQ by fixed root cause (e.g., `failure_class=version_skew` AND `agent_version < 2.4.0`).
2. Transform payload if needed (schema migration function versioned alongside agent).
3. Submit to staging queue; require >95% success on first 100 messages.
4. Redrive to production in batches of 50 with 30-second pause—protects LLM rate limits.
5. Mark DLQ entries `replayed_at` with operator ID; never delete until retention window expires.

```python
async def replay_batch(
    dlq_messages: list[dict],
    transform_fn,
    target_queue,
    *,
    batch_size: int = 50,
    pause_seconds: float = 30,
):
    for i in range(0, len(dlq_messages), batch_size):
        batch = dlq_messages[i : i + batch_size]
        for msg in batch:
            transformed = transform_fn(msg["original_message"])
            await target_queue.send(
                transformed,
                idempotency_key=msg["dlq_metadata"]["payload_hash"],
            )
        await asyncio.sleep(pause_seconds)
```

## Observability and alerting

Metrics that matter:

- `dlq_depth` by queue and failure_class
- `dlq_age_seconds` p99 — how long work has been stranded
- `dlq_inflow_rate` — spikes indicate deploy regressions
- `replay_success_rate` — replay without fix recreates incidents
- `cost_of_retries_usd` — agent-specific; sum LLM tokens on failed attempts

Alert when `dlq_depth > 0` for more than 15 minutes on customer-facing queues—not when depth is zero forever (that means DLQ routing is broken).

Trace DLQ sends as span events `dlq.routed` with failure_class so distributed traces show the full retry history.

## Security considerations

DLQ messages contain production payloads—prompts, user PII, retrieved documents. Apply encryption at rest, restrict IAM to triage roles, and audit every replay action. Security-classified messages go to a separate DLQ with tighter ACLs and automatic ticket creation.

Do not expose DLQ contents to third-party observability vendors without scrubbing. A DLQ dump during an incident has caused more than one accidental PII leak.

## Testing DLQ paths

- **Unit tests** for classification logic—every error type maps correctly.
- **Integration tests** that force max receive count and assert DLQ arrival with metadata.
- **Game days** inject version skew deploy and verify triage dashboard grouping.
- **Replay drills** quarterly: team replays staging DLQ batch under time pressure.

## Multi-stage agent DLQ patterns

Long-running agent workflows span multiple queues. A failure in step four should not re-run steps one through three if those side effects already committed.

**Saga-style checkpoints.** Persist `partial_state` after each successful stage: retrieval complete, tools invoked, draft response generated. DLQ messages carry the checkpoint so replay resumes at the failed stage.

**Compensating actions.** If step three charged a metered API and step four failed permanently, DLQ triage may trigger a refund or usage credit—not only a blind replay. Encode `billable_events` on the envelope.

**Child job DLQs.** Orchestrator fans out to tool workers with separate DLQs. Parent job should transition to `awaiting_child` state, not fail entirely when one tool DLQs—unless the tool was on the critical path. Document which tools are optional vs blocking in agent config; DLQ routing reads that config.

```typescript
interface ToolPolicy {
  name: string;
  critical: boolean;
  dlqQueue: string;
}

async function onToolDLQ(
  parentJobId: string,
  tool: ToolPolicy,
  dlqPayload: DLQPayload,
): Promise<void> {
  if (tool.critical) {
    await parentQueue.send({
      action: "fail_parent",
      parentJobId,
      reason: `critical tool ${tool.name} DLQ`,
      dlqRef: dlqPayload.id,
    });
  } else {
    await parentQueue.send({
      action: "continue_without_tool",
      parentJobId,
      skippedTool: tool.name,
    });
    await auditLog.record("non_critical_tool_dlq", dlqPayload);
  }
}
```

## Cost-aware DLQ retention

Agent DLQ messages can be large—retrieved context, base64 attachments. Set TTL policies: hot DLQ in broker for 7 days, archive to S3/GCS for 90 days with lifecycle deletion. Index metadata in a triage database so engineers search by `tenant_id` and `failure_class` without listing every S3 object.

Chargeback reports should include DLQ volume by tenant. A tenant sending systematically bad payloads drives DLQ inflow and LLM retry cost—that is a product conversation, not only an ops cleanup.

## The takeaway

Dead letter queue handling for agents is operational insurance. The DLQ is not failure—it is visibility. Classify failures, enrich messages, triage with ownership, and replay with idempotency and rate limits. The customer tickets sitting in that 14,000-message queue deserved the same engineering rigor as the happy path.

## Resources

- [AWS SQS Dead-Letter Queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/sqs-dead-letter-queues.html)
- [Azure Service Bus dead-lettering](https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-dead-letter-queues)
- [Google Cloud Pub/Sub dead-letter topics](https://cloud.google.com/pubsub/docs/dead-letter-topics)
- [Apache Kafka — handling poison pills](https://kafka.apache.org/documentation/#design_philosophy)
- [Companion: Poison Message Detection](/agent-poison-message-detection/)
- [OpenTelemetry semantic conventions — messaging](https://opentelemetry.io/docs/specs/semconv/messaging/)
