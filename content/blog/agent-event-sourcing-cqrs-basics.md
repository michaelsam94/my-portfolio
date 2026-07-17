---
title: "AI Agents: Event Sourcing Cqrs Basics"
slug: "agent-event-sourcing-cqrs-basics"
description: "Event Sourcing Cqrs Basics: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2024-11-04"
dateModified: "2024-11-04"
tags: ["AI", "Agent", "Event"]
keywords: "agent, event, sourcing, cqrs, basics, ai, production, engineering, architecture"
faq:
  - q: "Why would an agent system use event sourcing instead of storing final state in Postgres?"
    a: "Agent runs are long, branching, and non-deterministic. Event sourcing records every decision—user message, model completion, tool call, approval gate—as an immutable fact. You get a perfect audit trail for compliance, the ability to replay sessions for debugging, and the option to rebuild read models when prompts or eval logic change. CRUD on a single 'session state' JSON blob collapses under concurrency and loses history."
  - q: "What is CQRS in the context of agent orchestration?"
    a: "Command Query Responsibility Segregation separates writes (append events to the log) from reads (projected views optimized for UI). The write side accepts 'RunTool' commands and emits ToolStarted/ToolCompleted events. The read side maintains a denormalized 'session timeline' view for the dashboard and a separate 'billing summary' view—each rebuilt from the same event stream without contending locks on one wide table."
  - q: "How do you handle LLM non-determinism when replaying events?"
    a: "Store model outputs as events at write time—never re-invoke the LLM on replay unless explicitly running a counterfactual simulation. The event payload captures tokens, model version, and raw completion. Replay reconstructs what happened, not what might happen today with a newer model. For 'what-if' replays, fork the stream at a point and label results as simulated."
  - q: "When is event sourcing overkill for agents?"
    a: "Skip it for stateless single-turn chatbots with no tools and no audit requirements. Adopt it when sessions span multiple tools, human approvals, billing per step, regulatory retention, or cross-session analytics. The operational cost of an event store is justified when 'what exactly did the agent do?' is a production question, not a dev curiosity."
---
Support needed the full story of a billing dispute: which tools ran, what the model saw, who approved the wire transfer. The session table had a JSON column `state` overwritten on every step—latest snapshot only, no ordering guarantee under concurrent tool callbacks, and a migration last month that truncated nested fields. Reconstructing the session meant guessing from scattered CloudWatch logs. The team had a CRUD model for a workflow that was inherently a narrative.

Event sourcing stores facts; CQRS serves queries from purpose-built projections. Together they give agent platforms something relational update-in-place cannot: an append-only history that survives schema changes, concurrent writers, and post-incident scrutiny. This post covers the basics without assuming you are building a bank—but with the rigor you need if auditors eventually call.

## Event sourcing in one paragraph

Instead of `UPDATE sessions SET status = 'done'`, you append:

```
SessionStarted     { sessionId, userId, tenantId, at }
UserMessageReceived { text, at }
ModelCompletionRecorded { model, tokens, content, at }
ToolCallRequested  { tool, args, at }
ToolCallCompleted  { tool, result, latencyMs, at }
SessionCompleted   { outcome, at }
```

Current state is derived by folding events—a **fold** or **aggregate** in domain-driven design terms. The event log is the system of record; projections are disposable caches you rebuild.

## CQRS: why one table is not enough

Agent UIs need a fast chronological timeline. Finance needs per-tenant token totals. Safety review needs a queue of sessions with policy flags. One normalized schema serving all three creates hot rows and expensive joins.

CQRS splits:

- **Command side:** validates business rules, appends events, enforces invariants (e.g., cannot complete session while tool pending).
- **Query side:** consumers read from projections updated synchronously (strong consistency for UI) or asynchronously (eventual consistency for analytics).

```
┌──────────┐    commands     ┌─────────────┐    events    ┌──────────────┐
│   API    │ ──────────────► │  Aggregate  │ ───────────► │  Event Store │
└──────────┘                 └─────────────┘              └──────┬───────┘
                                                                 │
                    ┌────────────────────────────────────────────┼────────────┐
                    ▼                                            ▼            ▼
            TimelineProjection                          BillingProjection  SafetyQueue
            (Postgres read model)                       (ClickHouse)       (Redis stream)
```

## Modeling agent sessions as aggregates

An aggregate is a consistency boundary—everything inside commits together. For agents, `Session` is the natural aggregate root.

```typescript
// domain/session.aggregate.ts
type SessionEvent =
  | { type: "SessionStarted"; sessionId: string; userId: string; at: string }
  | { type: "UserMessageReceived"; text: string; at: string }
  | { type: "ModelCompletionRecorded"; model: string; content: string; tokens: number; at: string }
  | { type: "ToolCallCompleted"; tool: string; result: unknown; at: string }
  | { type: "SessionCompleted"; outcome: "success" | "failed" | "cancelled"; at: string };

interface SessionState {
  sessionId: string;
  userId: string;
  status: "active" | "completed" | "failed";
  pendingTools: number;
  totalTokens: number;
  lastMessageAt: string | null;
}

export function fold(state: SessionState | null, event: SessionEvent): SessionState {
  switch (event.type) {
    case "SessionStarted":
      return {
        sessionId: event.sessionId,
        userId: event.userId,
        status: "active",
        pendingTools: 0,
        totalTokens: 0,
        lastMessageAt: null,
      };
    case "ModelCompletionRecorded":
      return {
        ...state!,
        totalTokens: state!.totalTokens + event.tokens,
        lastMessageAt: event.at,
      };
    case "ToolCallCompleted":
      return { ...state!, pendingTools: Math.max(0, state!.pendingTools - 1) };
    case "SessionCompleted":
      return { ...state!, status: event.outcome === "success" ? "completed" : "failed" };
    default:
      return state!;
  }
}

export function decide(
  state: SessionState | null,
  command: { type: "CompleteSession"; outcome: string },
): SessionEvent[] {
  if (!state || state.status !== "active") {
    throw new Error("Cannot complete inactive session");
  }
  if (state.pendingTools > 0) {
    throw new Error("Cannot complete while tools are pending");
  }
  return [{ type: "SessionCompleted", outcome: command.outcome as "success", at: new Date().toISOString() }];
}
```

Commands that violate invariants never become events—the aggregate rejects them before append.

## Event store implementation patterns

Production options span managed services (EventStoreDB, Amazon EventBridge with archival) and DIY Postgres tables:

```sql
-- Minimal Postgres event store
CREATE TABLE agent_events (
  id            BIGSERIAL PRIMARY KEY,
  stream_id     TEXT NOT NULL,           -- e.g. session/{uuid}
  stream_version INT NOT NULL,           -- optimistic concurrency
  event_type    TEXT NOT NULL,
  payload       JSONB NOT NULL,
  metadata      JSONB NOT NULL DEFAULT '{}',
  occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (stream_id, stream_version)
);

CREATE INDEX idx_agent_events_stream ON agent_events (stream_id, stream_version);
```

Append with expected version check:

```typescript
async function appendEvents(
  db: Db,
  streamId: string,
  expectedVersion: number,
  events: SessionEvent[],
): Promise<void> {
  await db.transaction(async (tx) => {
    const { rows } = await tx.query(
      `SELECT COALESCE(MAX(stream_version), 0) AS v FROM agent_events WHERE stream_id = $1`,
      [streamId],
    );
    const current = Number(rows[0].v);
    if (current !== expectedVersion) {
      throw new ConcurrencyError(streamId, expectedVersion, current);
    }
    for (let i = 0; i < events.length; i++) {
      await tx.query(
        `INSERT INTO agent_events (stream_id, stream_version, event_type, payload, metadata)
         VALUES ($1, $2, $3, $4, $5)`,
        [streamId, current + i + 1, events[i].type, events[i], { correlationId: crypto.randomUUID() }],
      );
    }
  });
}
```

Optimistic concurrency prevents two workers from interleaving conflicting events on the same session—a realistic failure when tool callbacks arrive out of order.

## Projections: building read models

Projectors subscribe to new events and update read tables. Keep projectors **idempotent**: processing the same event twice should not double-count tokens.

```python
# projections/billing_projector.py
def handle_model_completion(event: dict, conn) -> None:
    session_id = event["metadata"]["stream_id"]
    tokens = event["payload"]["tokens"]
    tenant_id = event["metadata"].get("tenant_id")

    conn.execute(
        """
        INSERT INTO billing_daily (tenant_id, day, total_tokens, event_id)
        VALUES (%s, CURRENT_DATE, %s, %s)
        ON CONFLICT (tenant_id, day) DO UPDATE
          SET total_tokens = billing_daily.total_tokens + EXCLUDED.total_tokens
        WHERE NOT EXISTS (
          SELECT 1 FROM processed_events WHERE event_id = EXCLUDED.event_id
        )
        """,
        (tenant_id, tokens, event["id"]),
    )
    conn.execute(
        "INSERT INTO processed_events (event_id) VALUES (%s) ON CONFLICT DO NOTHING",
        (event["id"],),
    )
```

Run projectors as dedicated consumers with at-least-once delivery; dedupe via `processed_events` or deterministic upserts.

## Snapshots for long agent runs

A session with eighty events slows replay. Every N events (or when fold latency exceeds a threshold), persist a snapshot:

```
SessionSnapshot { state: SessionState, atVersion: 42 }
```

Load latest snapshot, then fold only events after version 42. Snapshots are optimization, not source of truth—you can delete and rebuild them from the log.

## CQRS read paths for agent UX

**Timeline projection** powers the operator console—chronological list with icons per event type. Sub-100 ms load time; paginate backward by version.

**Session summary** holds current status, last message preview, token count—what the inbox list needs without scanning full history.

**Search projection** denormalizes tool names and outcomes into Elasticsearch for "show me sessions where `delete_database` was called."

Each projection evolves independently. Adding a safety flag to the search index does not migrate the billing table.

## Operational concerns

**Retention and GDPR.** Events may contain PII in user messages. Define retention policies per stream type; tombstone events (`UserDataErased`) instruct projectors to redact without deleting audit metadata.

**Replay storms.** Rebuilding a projection replays all history—do it off-peak with rate limits. Version projectors (`billing_v3`) so you can run old and new in parallel before cutover.

**Monitoring.** Track `append_latency_ms`, `projection_lag_seconds`, `concurrency_conflict_total`. Lagging billing projection is finance risk; lagging timeline is UX risk.

## Testing event-sourced agents

**Given-When-Then on aggregates.** Given a sequence of events, when command X, then expect events Y or rejection Z. No database required.

**Property tests on fold.** Random event sequences never produce negative `pendingTools` or `totalTokens`.

**Integration tests.** Append real events to Testcontainers Postgres; assert projector output matches golden files.

```typescript
// session.aggregate.test.ts
describe("Session aggregate", () => {
  it("rejects complete while tools pending", () => {
    const events: SessionEvent[] = [
      { type: "SessionStarted", sessionId: "s1", userId: "u1", at: "t0" },
      // Tool started but not completed — fold would show pendingTools > 0
    ];
    const state = events.reduce(fold, null);
    expect(() => decide(state, { type: "CompleteSession", outcome: "success" })).toThrow();
  });
});
```

## When not to reach for the event store

Event sourcing adds moving parts. If your agent is a thin wrapper around one LLM call with no tools, Postgres `sessions` row plus `updated_at` is fine. Adopt events when debugging requires narrative, compliance requires immutability, or multiple read shapes contend on one write model.

Start small: event-source the tool-call boundary only—append `ToolCallCompleted` while keeping user messages in conventional tables—then expand once projectors prove stable.

## The takeaway

Event sourcing and CQRS give agent platforms an append-only history and flexible read models suited to long, branching, auditable workflows. Model sessions as aggregates with explicit invariants, append to a versioned store with optimistic concurrency, project into purpose-built views, and snapshot for replay performance. Store LLM outputs at write time so replay shows what happened—not a stochastic re-roll. The complexity is real, but so is the alternative cost of explaining agent behavior from a overwritten JSON column.

## Resources

- [Martin Fowler — Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Martin Fowler — CQRS](https://martinfowler.com/bliki/CQRS.html)
- [Greg Young — CQRS Documents](https://cqrs.files.wordpress.com/2010/11/cqrs_documents.pdf)
- [EventStoreDB documentation](https://www.eventstore.com/eventstoredb)
- [Marten — .NET document DB with event sourcing](https://martendb.io/events/)
