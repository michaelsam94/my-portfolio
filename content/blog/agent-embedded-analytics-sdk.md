---
title: "AI Agents: Embedded Analytics Sdk"
slug: "agent-embedded-analytics-sdk"
description: "Instrument agent products with an embedded analytics SDK—event schemas for tool calls and token usage, batching, privacy redaction, and dashboards your customers actually open."
datePublished: "2025-03-20"
dateModified: "2025-03-20"
tags: ["AI", "Agent", "Embedded"]
keywords: "embedded analytics, agent telemetry SDK, product analytics, token usage tracking, tenant dashboards, event batching, PII redaction, Segment, PostHog"
faq:
  - q: "What events should an agent analytics SDK capture?"
    a: "Minimum viable schema: session_started, turn_completed (latency, model, token_in/out), tool_invoked (name, success, duration), retrieval_hit/miss, guardrail_triggered, and session_ended (outcome). Avoid raw prompts by default—capture prompt_hash, template_version, and token counts. Let enterprise tenants opt in to content logging with explicit consent."
  - q: "How do I ship analytics without slowing agent responses?"
    a: "Never block the LLM path on analytics I/O. Emit events to an in-memory queue, flush on a timer (1–5 s) or batch size threshold, use sendBeacon on page unload for browser SDKs, and retry with exponential backoff on a background worker. Critical billing events may dual-write synchronously to your ledger—keep product analytics async."
  - q: "How does embedded analytics differ from internal observability?"
    a: "Internal observability (OpenTelemetry) serves engineers: stack traces, pod metrics, trace IDs. Embedded analytics serves customers and PMs: per-tenant usage, tool adoption, cost allocation, and success rates—aggregated, redacted, and exposed in your product UI. Use separate pipelines so customer-facing rollups cannot leak other tenants' data."
  - q: "What privacy controls do enterprise customers expect?"
    a: "Tenant-configurable retention (30/90/365 days), PII scrubbers before enqueue, region-specific ingestion endpoints, export/delete APIs for GDPR, and role-based dashboard access. Document which fields may contain user content and default to hashing or omission."
---
Customers kept asking the same question in QBRs: "Which agents actually get used, and what are we paying per successful resolution?" Internal Grafana showed pod CPU. It did not show that Tenant A's support bot invoked `refund_tool` 400 times with a 12% success rate while Tenant B never left RAG retrieval. The gap was embedded analytics—telemetry designed to ship **inside** the product, scoped to each tenant's admins, with schemas that speak product language (turns, tools, outcomes) instead of infrastructure dialect (spans, containers).

An embedded analytics SDK is the contract between your agent runtime and customer-facing dashboards. Get the event model wrong and PMs distrust the numbers; get privacy wrong and legal kills the feature. This post covers schemas, transport, redaction, and the aggregation layer that turns firehoses into widgets customers pay for.

## Event schema for agent workloads

Generic pageview analytics fail agent products. Design events around the **conversation turn** as the atomic unit.

Core events:

| Event | Purpose | Key properties |
|-------|---------|----------------|
| `session_started` | Funnel top | `tenant_id`, `agent_id`, `channel`, `user_hash` |
| `turn_completed` | Latency and cost | `tokens_in`, `tokens_out`, `model`, `duration_ms`, `outcome` |
| `tool_invoked` | Tool adoption | `tool_name`, `success`, `duration_ms`, `error_code` |
| `retrieval` | RAG quality proxy | `hit`, `chunk_count`, `index_version`, `latency_ms` |
| `guardrail_triggered` | Safety | `rule_id`, `action` (block, rewrite) |
| `session_ended` | Resolution | `resolution` (resolved, escalated, abandoned), `turn_count` |

```typescript
// sdk/agent-analytics.ts
type AgentEvent =
  | { type: "session_started"; agentId: string; channel: string }
  | {
      type: "turn_completed";
      turnIndex: number;
      model: string;
      tokensIn: number;
      tokensOut: number;
      durationMs: number;
      outcome: "success" | "error" | "partial";
    }
  | {
      type: "tool_invoked";
      toolName: string;
      success: boolean;
      durationMs: number;
      errorCode?: string;
    };

interface AnalyticsConfig {
  tenantId: string;
  ingestUrl: string;
  apiKey: string;
  flushIntervalMs?: number;
  maxBatchSize?: number;
  onError?: (err: Error) => void;
}

export class AgentAnalytics {
  private queue: Array<Record<string, unknown>> = [];
  private timer: ReturnType<typeof setInterval> | null = null;

  constructor(private cfg: AnalyticsConfig) {
    const interval = cfg.flushIntervalMs ?? 3000;
    this.timer = setInterval(() => void this.flush(), interval);
  }

  track(event: AgentEvent, context?: { sessionId?: string; userHash?: string }) {
    this.queue.push({
      ...event,
      tenant_id: this.cfg.tenantId,
      session_id: context?.sessionId,
      user_hash: context?.userHash,
      ts: new Date().toISOString(),
      sdk_version: "2.1.0",
    });
    if (this.queue.length >= (this.cfg.maxBatchSize ?? 50)) {
      void this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.queue.length === 0) return;
    const batch = this.queue.splice(0, this.queue.length);
    try {
      await fetch(this.cfg.ingestUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.cfg.apiKey}`,
        },
        body: JSON.stringify({ events: batch }),
        keepalive: true,
      });
    } catch (err) {
      this.queue.unshift(...batch);
      this.cfg.onError?.(err as Error);
    }
  }
}
```

Attach the SDK at orchestration boundaries—after a turn completes, after tool return—never inside model streaming loops per token.

## Server-side vs client-side embedding

Agent products split across browser chat widgets, mobile SDKs, and pure API integrators.

**Browser embedded SDK.** Use sendBeacon for unload, avoid third-party cookies, respect CSP by hosting a first-party `/collect` proxy. Sample high-volume typing indicators; do not emit per keystroke.

**Server-side SDK.** Authoritative for billing-grade token counts. Browser events are hints; server reconciles from model API response headers.

**Hybrid.** Client emits UX events (widget opened, suggested reply clicked); server emits truth events (turn_completed). Join on `session_id` in the warehouse.

Never expose server ingest API keys to browsers. Proxy through session-authenticated endpoints.

## Privacy, redaction, and tenant isolation

Default scrub list before enqueue:

```python
# ingest/redaction.py
import re
import hashlib

EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE = re.compile(r"\+?\d[\d\s\-()]{8,}\d")

def redact(text: str) -> str:
    text = EMAIL.sub("[EMAIL]", text)
    text = PHONE.sub("[PHONE]", text)
    return text

def hash_user(tenant_id: str, user_id: str) -> str:
    return hashlib.sha256(f"{tenant_id}:{user_id}".encode()).hexdigest()[:16]
```

Ingest pipeline validates JWT or HMAC API keys map to exactly one `tenant_id`. Reject batches where event tenant mismatches key scope—prevents cross-tenant pollution attacks.

Retention jobs delete raw events past tenant policy; rollups (daily token totals) persist longer if contracts allow.

## Aggregation for customer dashboards

Raw events are not dashboard-ready. Stream to Kafka → Flink/dbt rollups:

```sql
-- daily_agent_usage.sql
SELECT
  tenant_id,
  agent_id,
  DATE(ts) AS day,
  COUNT(DISTINCT session_id) AS sessions,
  SUM(CASE WHEN event_type = 'turn_completed' THEN tokens_in + tokens_out ELSE 0 END) AS tokens,
  AVG(CASE WHEN event_type = 'turn_completed' THEN duration_ms END) AS avg_turn_ms,
  SUM(CASE WHEN event_type = 'tool_invoked' AND success THEN 1 ELSE 0 END) AS tool_successes
FROM agent_events
WHERE ts >= CURRENT_DATE - INTERVAL '90' DAY
GROUP BY 1, 2, 3;
```

Expose via embedded BI (Metabase iframe, custom React charts) with row-level security on `tenant_id`. Precompute expensive queries; dashboard SLA is 2 s, not warehouse scan time.

Widget ideas customers value:

- Token usage vs plan limit (burn-down)
- Top tools by success rate
- Median time-to-resolution by channel
- Guardrail triggers per 1k turns
- Model mix and cost attribution

## Reliability, backpressure, and cost

Analytics outages must not break agents. SDK drops events after bounded queue size (e.g., 500) with a counter metric `analytics_dropped_total`—alert internally, not customer-facing.

Ingest tier autoscales on queue depth. Rate-limit per tenant (10k events/min) to prevent runaway loops from buggy agents.

Compress batches with gzip above 10 KB. Deduplicate with `(session_id, turn_index, event_type)` idempotency keys for at-least-once pipelines.

## Testing and validation

Contract tests assert every orchestrator path emits required events:

```typescript
test("turn emits turn_completed", async () => {
  const mock = jest.spyOn(analytics, "track");
  await orchestrator.runTurn(session, "hello");
  expect(mock).toHaveBeenCalledWith(
    expect.objectContaining({ type: "turn_completed", tokensOut: expect.any(Number) }),
    expect.any(Object),
  );
});
```

Staging shadow mode: duplicate production traffic events to a validation sink and compare rollup totals against internal OTel metrics—drift >2% blocks release.

## Embedding analytics in customer-facing UI

The SDK is half the story; delivery is the other half. Customer admins expect analytics where they manage agents—not a separate BI login.

**Iframe embedding.** Host Metabase or Superset with signed URLs scoped to `tenant_id`. Rotate embed secrets per tenant; expire tokens in 10 minutes.

**First-party charts.** Query pre-aggregated tables via your API—never expose warehouse credentials to browsers. Cache rollup responses 60 seconds; stale usage numbers beat leaking live token streams.

**Export APIs.** Enterprise contracts request CSV exports of monthly token usage. Rate-limit exports; audit who downloaded what.

```typescript
// api/tenant-usage.ts
export async function getUsageSummary(tenantId: string, range: DateRange) {
  return db.query(
    `SELECT day, agent_id, sessions, tokens, tool_successes
     FROM daily_agent_usage
     WHERE tenant_id = $1 AND day BETWEEN $2 AND $3
     ORDER BY day DESC`,
    [tenantId, range.start, range.end],
  );
}
```

Surface SDK initialization in your agent builder UI: when a customer publishes an agent, auto-provision API keys and show a "Usage" tab wired to the same `tenant_id`—no manual wiring.

## Billing alignment and dual-write

Product analytics token counts must reconcile with vendor invoices (OpenAI, Anthropic) within agreed tolerance—usually ±2%. Nightly jobs compare:

- SDK `turn_completed` sums vs model provider usage API
- Internal OTel `llm_tokens_total` vs SDK rollups

Discrepancies trigger alerts to platform team, not customers, until explained (failed flushes, sampled sessions, admin test traffic).

For usage-based billing, treat the **server-side** SDK path as authoritative; customer invoices come from ledger tables fed by server events, not browser beacons.

## Anti-patterns

- Logging full prompts to analytics because "we might need them later"
- Using the same database as chat history for analytics queries (noisy neighbors)
- Synchronous HTTP to Segment on every tool call
- Dashboards that show other tenants' benchmarks without anonymization
- Changing event schema without version field—breaks historical charts

## Closing

Embedded analytics turns agent platforms from black boxes into products customers can justify renewing. Define turn-centric events, scrub by default, flush asynchronously, aggregate with tenant isolation, and expose rollups—not raw logs—in the UI. Internal observability keeps you awake at night; embedded analytics keeps customers awake planning expansions—which is the point.

## Resources

- [PostHog SDK and group analytics](https://posthog.com/docs/libraries)
- [Segment batch spec](https://segment.com/docs/connections/sources/catalog/libraries/website/javascript/#batching)
- [OpenTelemetry vs product analytics (CNCF blog)](https://opentelemetry.io/blog/)
- [GDPR-friendly analytics patterns — ICO guidance](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/)
- [dbt incremental models documentation](https://docs.getdbt.com/docs/build/incremental-models)
