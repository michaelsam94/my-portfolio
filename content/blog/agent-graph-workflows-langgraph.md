---
title: "Graph Workflows for Agents"
slug: "agent-graph-workflows-langgraph"
description: "Model agent logic as explicit graphs: nodes, edges, state, checkpoints, and conditional routing. When LangGraph-style workflows beat free-form agent loops."
datePublished: "2026-06-26"
dateModified: "2026-06-26"
tags: ["AI Agents", "LLM", "Architecture", "Backend"]
keywords: "LangGraph, agent graph workflow, state machine agents, agent orchestration graph, conditional agent routing"
faq:
  - q: "What is a graph workflow for agents?"
    a: "A graph workflow models agent logic as nodes (functions or LLM calls) connected by edges (transitions). Shared state flows through the graph, and conditional edges route to different nodes based on runtime results. Unlike a free-form while-loop, the graph makes control flow explicit, testable, and resumable from any node."
  - q: "When should I use a graph instead of a simple agent loop?"
    a: "Use a graph when your agent has distinct phases (research → plan → execute → review), needs human approval gates, requires checkpoint/resume after failures, or has branching logic that varies by intent. Simple Q&A agents with 2–3 tool calls don't need a graph — a loop is fine."
  - q: "How do checkpoints work in agent graphs?"
    a: "After each node completes, the framework serializes the full graph state to durable storage. If the process crashes or pauses for human input, execution resumes from the last checkpoint rather than restarting. This is essential for long-running agents and approval workflows."
---

Free-form agent loops — while not done, call LLM, execute tools, repeat — work until they don't. The moment you need "research, then pause for human approval, then execute, then verify," you're hand-rolling a state machine inside a while loop, complete with bugs about which step you're on after a timeout. Graph workflows make that state machine explicit: nodes are steps, edges are transitions, state is a typed object that flows through the graph, and checkpoints let you resume mid-flight. I've migrated three production agents from loops to graphs; the code got longer but the failure modes got enumerable.

## Graph vs loop

| Aspect | Agent loop | Graph workflow |
|--------|-----------|----------------|
| Control flow | Implicit in prompt | Explicit nodes and edges |
| Branching | Model decides everything | Code + model hybrid |
| Debugging | Read full transcript | Inspect state at each node |
| Resume | Restart from scratch | Checkpoint and continue |
| Testing | Mock LLM sequence | Test nodes independently |

Use a loop for exploratory agents. Use a graph for production workflows with compliance, billing, or multi-phase pipelines.

## A concrete graph

```python
from typing import TypedDict, Literal

class AgentState(TypedDict):
    user_query: str
    research: str | None
    plan: str | None
    approval: Literal["pending", "approved", "rejected"] | None
    result: str | None

async def research_node(state: AgentState) -> AgentState:
    research = await llm.complete(f"Research: {state['user_query']}")
    return {**state, "research": research}

async def plan_node(state: AgentState) -> AgentState:
    plan = await llm.complete(f"Plan given research:\n{state['research']}")
    return {**state, "plan": plan}

async def execute_node(state: AgentState) -> AgentState:
    result = await execute_plan(state["plan"])
    return {**state, "result": result}

def route_after_research(state: AgentState) -> str:
    if needs_approval(state["research"]):
        return "human_review"
    return "plan"
```

```
START → research → [needs approval?] → human_review → plan → execute → END
                         ↓ (no)
                        plan → execute → END
```

Each node is a pure function `(state) → state`. Conditional edges are routing functions that read state and return the next node name. The LLM lives *inside* nodes, not as the orchestrator of everything.

## Where the model decides vs where code decides

This is the design choice that matters most:

- **Code decides**: routing between phases, retry limits, approval gates, tool allowlists per node
- **Model decides**: content generation within a node, tool selection from an allowed set, summarization

I've seen teams give the model a "route to next step" tool and regret it — the model routes incorrectly under pressure and skips approval. Hard-code phase transitions; let the model fill in content.

## Checkpoints and human-in-the-loop

Graph frameworks persist state after each node:

```python
# Conceptual checkpoint flow
graph = StateGraph(AgentState)
graph.add_node("research", research_node)
graph.add_node("human_review", human_review_node)  # pauses until external signal
graph.add_node("execute", execute_node)
graph.add_conditional_edges("research", route_after_research)
graph.compile(checkpointer=PostgresCheckpointer(db_url))
```

When `human_review` runs, the graph saves state and stops. An API endpoint receives the approval, injects `{"approval": "approved"}`, and resumes from the checkpoint. This is how [human-in-the-loop approval](https://blog.michaelsam94.com/agent-human-in-the-loop-approval/) works without polling loops.

## Testing graph nodes

Each node is independently testable:

```python
async def test_plan_node_formats_correctly():
    state = {"user_query": "refund order", "research": "Order 4521 is eligible."}
    result = await plan_node(state)
    assert result["plan"] is not None
    assert "4521" in result["plan"]
```

Test routing functions with fixed state — no LLM needed. Integration tests run the full graph with [recorded LLM fixtures](https://blog.michaelsam94.com/agent-deterministic-replay-testing/).

## When graphs become overkill

If your agent is "receive question → search docs → answer," a graph adds ceremony without benefit. If it's "classify intent → branch to one of five pipelines → each with different tools and approval rules," the graph pays for itself in the first debugging session.

The [workflow vs autonomous agent](https://blog.michaelsam94.com/agent-workflow-vs-agent-patterns/) decision is really about how much control flow you need to own versus delegate to the model.

## State schema design

LangGraph state should be typed and versioned — treat it like a database schema:

```python
from typing import TypedDict, Annotated
import operator

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]  # append-only reducer
    plan: str | None
    approval_status: Literal["pending", "approved", "rejected"]
    retry_count: int
```

Use reducers for list fields that multiple nodes append to. Without reducers, parallel node execution overwrites instead of merging — a bug that only appears under concurrent tool calls.

## Checkpointing and human-in-the-loop

Persist checkpoints to Postgres or Redis for production recovery:

```python
from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
graph = workflow.compile(checkpointer=checkpointer)

# Resume after HITL approval
config = {"configurable": {"thread_id": session_id}}
graph.invoke({"approval_status": "approved"}, config=config)
```

Interrupt before write nodes with `interrupt_before=["execute_action"]`. The graph pauses, surfaces state to UI, resumes on approval. Without checkpointing, process restarts lose in-flight agent work.

## Observability for graphs

Log every node transition with `{thread_id, node, duration_ms, state_diff}`. When agents loop between `plan` and `research` twelve times, the trace shows it immediately — token cost alone doesn't surface routing loops.

Pair with [agent observability tracing](https://blog.michaelsam94.com/agent-observability-tracing-spans/) and [human-in-the-loop approval](https://blog.michaelsam94.com/agent-human-in-the-loop-approval/) for production graph deployments.

## Common production mistakes

Teams get graph workflows langgraph wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using graph workflows langgraph loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Resources

- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
- [LangGraph checkpointing guide](https://langchain-ai.github.io/langgraph/concepts/persistence/)
- [Temporal — durable workflow execution](https://docs.temporal.io/)
- [Amazon States Language spec](https://states-language.net/spec.html)
- [Building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/)
