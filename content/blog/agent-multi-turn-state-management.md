---
title: "Multi-Turn State Management"
slug: "agent-multi-turn-state-management"
description: "Manage state across multi-turn agent conversations: typed state objects, conversation threading, tool result lifecycle, and avoiding context rot."
datePublished: "2026-06-30"
dateModified: "2026-06-30"
tags: ["AI Agents", "LLM", "Architecture", "Backend"]
keywords: "agent state management, multi-turn agents, conversation state, agent session state, LLM state machine"
faq:
  - q: "What state does a multi-turn agent need to track?"
    a: "At minimum: conversation history, current goal and subtask, tool results pending action, user identity and permissions, extracted entities (IDs, names, dates), and execution metadata (step count, cost, errors). Separate ephemeral turn state from durable session state and from long-term semantic memory."
  - q: "How is agent state different from chat history?"
    a: "Chat history is the raw message log — necessary but insufficient. Agent state includes structured data the orchestrator needs: which phase the workflow is in, what tools have been called, parsed entities, approval status, and retry counts. The LLM sees a rendered view of state; the orchestrator owns the canonical typed object."
  - q: "Where should agent state be stored?"
    a: "Active session state lives in memory or Redis for low-latency access during a conversation. Checkpoint state for resumable workflows goes to durable storage (Postgres, DynamoDB). Long-term facts promote to a semantic memory store at session end. Never rely on the LLM's context window as your state store."
---

Chat history is not state. I've debugged agents that "forgot" the order ID at turn 8 not because the model has amnesia, but because nobody built a state object — the orchestrator hoped the LLM would remember a number mentioned twelve messages ago. Multi-turn agent state is a typed, orchestrator-owned data structure that survives summarization, survives model swaps, and gives you something to assert on in tests. The message log is an audit trail; state is what the agent actually knows.

## State layers

```
┌─────────────────────────────────────┐
│  Turn state (ephemeral)             │  current LLM response, pending tool calls
├─────────────────────────────────────┤
│  Session state (in-memory/Redis)    │  goal, entities, phase, step count
├─────────────────────────────────────┤
│  Checkpoint state (durable)         │  graph position, approval status
├─────────────────────────────────────┤
│  Semantic memory (long-term)        │  user prefs, project facts
└─────────────────────────────────────┘
```

Each layer has different lifetime, storage, and access patterns. Conflating them creates bugs.

## The session state object

Define it explicitly — don't infer state from chat history:

```python
@dataclass
class SessionState:
    session_id: str
    user_id: str
    goal: str | None = None
    phase: Literal["intake", "research", "execute", "review"] = "intake"
    entities: dict[str, Any] = field(default_factory=dict)
    tool_results: dict[str, Any] = field(default_factory=dict)
    pending_tool_calls: list[ToolCall] = field(default_factory=list)
    step_count: int = 0
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
```

Update state in your orchestrator after every turn — never let the model directly mutate it. The model *proposes* actions; code *commits* state changes.

```python
async def process_turn(state: SessionState, user_message: str) -> AgentResponse:
    state.step_count += 1
    context = render_context(state, user_message)
    llm_response = await llm.complete(context, tools=available_tools(state))

    if llm_response.tool_calls:
        state.pending_tool_calls = llm_response.tool_calls
        results = await execute_tools(llm_response.tool_calls, state)
        state.tool_results.update(results)
        # Second LLM call with tool results — or loop
        llm_response = await llm.complete(render_context(state, user_message))

    update_entities_from_response(state, llm_response)
    return AgentResponse(text=llm_response.content, state=state)
```

## Rendering state for the LLM

The model doesn't read your Python objects. Render a consistent context block:

```python
def render_context(state: SessionState, user_message: str) -> list[Message]:
    system = f"""You are a support agent.
Current goal: {state.goal or 'Not yet determined'}
Phase: {state.phase}
Known entities: {json.dumps(state.entities, indent=2)}
Steps taken: {state.step_count}
"""
    messages = [SystemMessage(system)]
    messages.extend(state.recent_history(limit=5))
    messages.append(UserMessage(user_message))
    return messages
```

Keep rendering deterministic. If the same state produces different context strings between turns, the model behaves inconsistently.

## Tool result lifecycle

Tool results have a lifecycle most agents ignore:

1. **Pending** — tool call proposed, not yet executed
2. **Active** — result in current context, agent hasn't acted on it
3. **Consumed** — agent used the result, safe to drop from active context
4. **Archived** — stored in state.tool_results, retrievable but not in prompt

Mark results as consumed explicitly:

```python
def mark_consumed(state: SessionState, tool_call_id: str):
    state.tool_results[tool_call_id]["status"] = "consumed"
```

When assembling context, include only Active results. This alone can cut context size 40% in tool-heavy agents.

## Threading and concurrency

Users send messages while the agent is still processing. Handle it:

- **Reject with status**: "Still working on your previous request" (simple, safe)
- **Queue**: process messages sequentially (most common)
- **Interrupt**: cancel in-flight work, restart with new message (complex, use sparingly)

Never process two turns concurrently against the same session state. Race conditions on entity extraction are subtle and nasty.

Store `processing: bool` on session state with a TTL lock in Redis.

## State transitions for workflow phases

If your agent has phases, enforce transitions in code:

```python
VALID_TRANSITIONS = {
    "intake": ["research"],
    "research": ["execute", "intake"],  # intake = user changed goal
    "execute": ["review", "research"],
    "review": ["execute", "done"],
}

def transition(state: SessionState, new_phase: str):
    if new_phase not in VALID_TRANSITIONS.get(state.phase, []):
        raise InvalidTransition(f"{state.phase} → {new_phase}")
    state.phase = new_phase
```

The model can *suggest* a phase change via a tool call; your orchestrator validates and commits it. This prevents the agent from skipping research and jumping to execute.

## Testing state management

State objects make agents testable:

```python
def test_entity_extraction_updates_state():
    state = SessionState(session_id="s1", user_id="u1")
    update_entities_from_response(state, mock_response(order_id="4521"))
    assert state.entities["order_id"] == "4521"

def test_invalid_phase_transition_raises():
    state = SessionState(phase="intake")
    with pytest.raises(InvalidTransition):
        transition(state, "execute")
```

Pair with [deterministic replay tests](https://blog.michaelsam94.com/agent-deterministic-replay-testing/) for full-turn integration coverage.

## Context budget and summarization without losing state

When `step_count` or estimated tokens exceed a threshold, agents summarize older turns — but summarization must not replace structured state. The anti-pattern: compress the last twenty messages into a paragraph and drop the order ID. The fix: summarize *narrative* history while keeping `state.entities`, `state.tool_results` (archived), and `state.phase` intact:

```python
def trim_context(state: SessionState) -> SessionState:
    if estimate_tokens(state) > TOKEN_BUDGET:
        state.conversation_summary = llm.summarize(state.recent_history(limit=20))
        state.trimmed_message_ids = [m.id for m in state.messages[:-5]]
    return state
```

Render context as: summary block + last five messages + structured entity block. The model gets continuity; the orchestrator keeps canonical IDs for tool calls and tests. Log when summarization fires — frequent firing means the workflow is too chatty or the budget is too tight.

## Entity resolution across turns

Users say "that order" at turn 6 referring to order 4521 from turn 2. Chat history may still mention 4521, but models lose coreference under pressure. Maintain an **entity registry** in session state with types, IDs, and last-mentioned turn:

```python
state.entities["order"] = {"id": "4521", "turn": 2, "confidence": 1.0}
```

Update from tool results (authoritative) and from NLU extraction (provisional). When the user says "cancel it," resolve against the most recent entity of matching type above a confidence threshold; if ambiguous, ask — do not guess. Export resolved entities in traces for debugging "wrong order cancelled" incidents.

## Schema evolution for long-lived sessions

Sessions span hours or days in async approval flows. When you add `approval_status` to `SessionState`, old Redis blobs deserialize without it. Use explicit schema versions and migration on read:

```python
def load_session(raw: dict) -> SessionState:
    version = raw.get("schema_version", 1)
    if version < CURRENT_SCHEMA:
        raw = migrate_session(raw, version, CURRENT_SCHEMA)
    return SessionState(**raw)
```

Bump version when fields are renamed or semantics change. [Graph checkpoints](https://blog.michaelsam94.com/agent-graph-workflows-langgraph/) need the same discipline — stale checkpoint shape plus new node code equals production exceptions mid-workflow.

## Common production mistakes

Teams get multi turn state management wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using multi turn state management loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When multi turn state management misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [LangGraph state management](https://langchain-ai.github.io/langgraph/concepts/low_level/#state)
- [Redis session storage patterns](https://redis.io/docs/latest/develop/use/patterns/session-storage/)
- [Temporal workflow state](https://docs.temporal.io/workflows)
- [OpenAI assistants API — threads and runs](https://platform.openai.com/docs/assistants/how-it-works)
- [Agent graph workflows](https://blog.michaelsam94.com/agent-graph-workflows-langgraph/)
