---
title: "Message Ordering Guarantees for Multi-Agent Pipelines"
slug: "agent-message-ordering-guarantees"
description: "Design Kafka partitions, SQS FIFO, and in-process agent mailboxes so tool results, user edits, and streaming tokens arrive in causal order—without blocking parallelism or corrupting conversation state."
datePublished: "2024-11-15"
dateModified: "2024-11-15"
tags: ["AI Agents", "Messaging", "Distributed Systems", "Event Ordering"]
keywords: "message ordering guarantees, agent event pipeline, Kafka partition key, FIFO queue, causal ordering, conversation state machine"
faq:
  - q: "Do agent systems need global message ordering?"
    a: "Almost never. You need per-conversation (or per-run_id) ordering so user messages, tool calls, and tool results replay in causal sequence. Cross-tenant and cross-run ordering is irrelevant and forcing global order destroys throughput."
  - q: "How does Kafka provide ordering for agent events?"
    a: "Ordering is guaranteed only within a single partition. Publish all events for one run_id or conversation_id to the same partition using a stable key. More partitions increase parallelism; hot keys create skew—monitor partition lag per key hash."
  - q: "What breaks ordering in agent pipelines most often?"
    a: "Retry without sequence numbers, parallel tool workers returning results out of completion order, mixing at-least-once delivery with non-idempotent state updates, and UI websockets that race SSE chunks against REST history fetches. Fix with monotonic sequence ids and idempotent reducers."
  - q: "Should streaming LLM tokens participate in the same ordering scheme?"
    a: "Tokens on a single stream are ordered by the provider connection. Your pipeline should assign them sub-sequence ids (run_id, message_id, chunk_index) when persisting to event log so reconnecting clients merge chunks correctly. Do not interleave two assistant messages on one stream without message boundaries."
---

The agent showed the user "Refund approved" before it showed "Checking order status"—backwards causality in the transcript. Root cause was three **tool workers** writing results to Redis lists without sequence numbers; the UI sorted by `completed_at`, and a fast cache hit finished after a slow database lookup. The model had the right final answer; the **event log** lied about how we got there. Worse: replaying the conversation for eval trained the wrong policy on shuffled tool traces.

Multi-agent and tool-augmented systems are message systems disguised as chat. Ordering guarantees define whether state machines, billing meters, and audit trails remain trustworthy. The mistake is assuming your broker's "ordered" marketing applies globally. In practice you engineer **scope**: ordered per run, per session, or per partition—and accept disorder everywhere else.

## Ordering scopes

| Scope | Guarantee | Typical use |
|-------|-----------|-------------|
| Global | Total order all events | Avoid—single bottleneck |
| Per conversation | All user/assistant/tool events ordered | Chat UI, run replay |
| Per aggregate | Order within one tool invocation chain | Planner → executor subgraph |
| Per provider stream | Token order within one completion | SSE to browser |

Pick the **weakest scope that satisfies invariants**. Billing usually needs per-run order; cross-run order does not matter.

## Event envelope design

Every persisted message carries:

```typescript
type AgentEvent = {
  runId: string;
  conversationId: string;
  seq: number;           // monotonic per runId, assigned by single writer
  causationId?: string;  // parent event seq
  type: "user_message" | "assistant_chunk" | "tool_call" | "tool_result" | "system";
  payload: unknown;
  createdAt: string;     // informational only—not for ordering
};
```

**Assign `seq` at the orchestrator**—the single writer for a run—not at workers. Workers return results; orchestrator commits with next seq.

```typescript
class RunEventLog {
  private nextSeq = 1;

  append(type: AgentEvent["type"], payload: unknown, causationId?: string): AgentEvent {
    const event: AgentEvent = {
      runId: this.runId,
      conversationId: this.conversationId,
      seq: this.nextSeq++,
      causationId,
      type,
      payload,
      createdAt: new Date().toISOString(),
    };
    this.store.append(event); // transactional with state transition
    return event;
  }
}
```

Consumers **must not** sort by timestamp—clocks skew, retries duplicate, and tool latency varies.

## Broker patterns

### Kafka: partition by run_id

```python
producer.send(
    topic="agent.events.v1",
    key=run_id.encode(),  # stable partition mapping
    value=json.dumps(event).encode(),
    headers=[("seq", str(seq).encode())],
)
```

Consumer reads partition sequentially; idempotent reducer applies events in seq order. On duplicate delivery (at-least-once), skip if `seq <= last_applied_seq`.

```python
def apply_event(state: RunState, event: dict) -> RunState:
    if event["seq"] <= state.last_seq:
        return state  # duplicate or replay
    if event["seq"] != state.last_seq + 1:
        raise GapError(f"expected {state.last_seq + 1}, got {event['seq']}")
    return reduce(state, event)
```

**Gap detection** triggers buffer or fetch from authoritative store—never guess.

### SQS FIFO: MessageGroupId = run_id

FIFO queues provide order within a message group. Throughput limit: 300 TPS per group (AWS default)—sufficient for single-run orchestration, not for fan-in from thousands of parallel tools unless you batch.

```json
{
  "MessageGroupId": "run_7f3a",
  "MessageDeduplicationId": "run_7f3a-seq-42",
  "MessageBody": "{...}"
}
```

Use content-based dedup or explicit dedup id from `(run_id, seq)`.

### Redis Streams: XADD with consumer groups

Good for low-latency agent workers:

```
XADD run:7f3a:events * type tool_result seq 42 payload {...}
```

Consumer group reads preserve order per stream key. One stream key per run_id; cap stream length with MAXLEN ~ approximate for memory.

## Parallel tools without order corruption

When the planner invokes three tools in parallel, results may **complete** out of order but should **commit** in planner-assigned order:

```
Planner emits: tool_call seq=5 (A), seq=6 (B), seq=7 (C)
Workers complete: C, A, B
Orchestrator buffers until A arrives → append seq=8 result A
                  then B → seq=9
                  then C → seq=10
```

Buffer with timeout—if B never returns, append failure at seq=9 and do not block forever:

```typescript
async function collectToolResults(
  calls: ToolCall[],
  timeoutMs: number,
): Promise<ToolResult[]> {
  const pending = new Map(calls.map((c) => [c.id, c]));
  const ordered: ToolResult[] = [];
  const deadline = Date.now() + timeoutMs;

  while (pending.size > 0 && Date.now() < deadline) {
    const result = await resultQueue.pop(calls[0].runId);
    pending.delete(result.callId);
    ordered.push(result);
  }
  for (const call of pending.values()) {
    ordered.push({ callId: call.id, error: "timeout" });
  }
  return ordered.sort((a, b) => a.plannerOrder - b.plannerOrder);
}
```

The LLM sees tool results in **planner order**, matching the causal narrative.

## Streaming tokens and persistence

SSE delivers ordered chunks on one HTTP connection. Reconnects race with history API:

1. Client connects SSE with `Last-Event-ID: run/7f3a/chunk/881`
2. Server replays chunks with index > 881 from store, then live stream
3. Persist chunks with `(message_id, chunk_index)` unique constraint

```sql
CREATE TABLE assistant_chunks (
  run_id TEXT NOT NULL,
  message_id TEXT NOT NULL,
  chunk_index INT NOT NULL,
  content TEXT NOT NULL,
  PRIMARY KEY (run_id, message_id, chunk_index)
);
```

UI merges by `(message_id, chunk_index)`, not arrival time.

## Causal ordering vs total ordering

**Causal**: if event B references tool output from A, B must appear after A in the log. **Total**: every pair comparable.

Agent runs need causal order for tool chains; independent user edits on different branches (edit-and-resubmit) need **branch ids**:

```typescript
type AgentEvent = {
  // ...
  branchId: string;  // fork on user edit
  seq: number;         // monotonic per (runId, branchId)
};
```

Main branch seq=12 → user edits → new branch `edit-1` seq=1. UI shows branch picker; eval replays explicit branch.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Duplicate tool charges | Retry without idempotency key | Idempotent tool layer keyed by (run_id, seq) |
| Missing tool result in transcript | Out-of-order append | Orchestrator buffer + gap detection |
| Stale UI after reconnect | Client sorts by time | Server-side seq cursor |
| Partition hot spot | All runs same tenant key | Salt key: hash(tenant_id + run_id) |

## Testing ordering

Property-based tests: random parallel tool completions always produce monotonic seq in store.

Integration: kill consumer mid-batch; restart; verify no duplicates applied and no gaps without alert.

Chaos: inject 500ms jitter on tool workers; transcript order unchanged when sorted by seq.

Load: one run_id at 50 tool/sec—verify FIFO/Kafka partition limit not choking orchestrator single-writer.

## Observability

Metrics:

- `event_seq_gap_total` — should be zero
- `event_duplicate_skipped_total` — rises with retries, OK if idempotent
- `tool_result_buffer_wait_ms` p95 — capacity signal
- `partition_lag_max` per topic

Traces: link `causationId` across spans for debugging "why did seq 9 precede 8 in raw broker?"

## Human-in-the-loop and approval events

Human approvals—"confirm refund," "run destructive migration"—must slot into the same seq stream as model events, not a parallel audit table that UI merges ad hoc. Pattern:

```typescript
// User clicks approve on pending tool call at seq=14
orchestrator.append("human_approval", {
  approvedSeq: 14,
  approverUserId: ctx.userId,
  decision: "approved",
}, /* causationId */ "14");
orchestrator.append("tool_result", resultPayload, "14");
```

Rejections append `human_rejection` before any compensating `system` event. Eval replays see the full causal chain; billing attributes tool execution to post-approval seq only.

## Multi-region and ordering

Active-active regions break naive single-writer seq unless you elect one **ordering region** per run_id or use a CRDT/log merge. Practical approach for most agent SaaS:

- Route all events for `run_id` to a home region via sticky gateway
- Cross-region reads serve cached transcript with `last_seq` watermark
- Failover promotes standby region only after pausing writers in primary—accept brief unavailability over split-brain duplicates

If you must dual-write, use **conflict-free replicated seq** (allocating odd/even ranges per region) or a central consensus service (etcd, Spanner) for seq allocation—never `max(seq)+1` in two regions concurrently.

## The takeaway

Message ordering for agents is per-run causal consistency, not global FIFO. Centralize sequence assignment, partition brokers by run_id, buffer parallel tool results into planner order, persist streaming chunks with indexes, and make reducers idempotent for at-least-once delivery. Timestamps are for humans; sequence numbers are for correctness.

## Resources

- [Kafka — Ordering Guarantees documentation](https://kafka.apache.org/documentation/#semantics)
- [AWS SQS FIFO queues](https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/FIFO-queues.html)
- [Redis Streams introduction](https://redis.io/docs/latest/develop/data-types/streams/)
- [Leslie Lamport — Time, Clocks, and the Ordering of Events](https://lamport.azurewebsites.net/pubs/time-clocks.pdf)
- [CloudEvents spec — event correlation attributes](https://cloudevents.io/)
