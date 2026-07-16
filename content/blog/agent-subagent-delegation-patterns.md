---
title: "Sub-Agent Delegation Patterns"
slug: "agent-subagent-delegation-patterns"
description: "Design sub-agent delegation for complex tasks: orchestrator-workers, specialist agents, context passing, and avoiding the infinite delegation loop."
datePublished: "2026-07-04"
dateModified: "2026-07-04"
tags: ["AI Agents", "LLM", "Architecture", "Backend"]
keywords: "sub-agent delegation, multi-agent orchestration, agent workers, specialist agents, agent hierarchy patterns"
faq:
  - q: "What is sub-agent delegation?"
    a: "Sub-agent delegation is when a primary orchestrator agent assigns subtasks to specialized sub-agents, each with its own system prompt, tools, and context window. The orchestrator defines what each sub-agent should accomplish, receives their results, and synthesizes a final answer. It's a divide-and-conquer pattern for complex multi-step tasks."
  - q: "When should you use sub-agents instead of one agent with many tools?"
    a: "Use sub-agents when subtasks require different expertise, tool sets, or security boundaries — a research agent with read-only tools, an executor with write tools, a code agent with a REPL. One agent with 40 tools suffers tool selection degradation; focused sub-agents with 5–8 tools each perform better."
  - q: "How do you prevent infinite delegation loops?"
    a: "Set a maximum delegation depth (typically 2: orchestrator → sub-agent, no sub-sub-agents), cap the number of sub-agent invocations per run, and require the orchestrator to synthesize after receiving sub-agent results rather than delegating further. Track delegation count in session state and halt when the limit is reached."
---

One agent with thirty tools is a jack of all trades that picks the wrong tool half the time. Sub-agent delegation splits the work: an orchestrator routes tasks to specialists — a research agent that only reads, a writer that only drafts, an executor that only calls write APIs — each with a focused prompt and a small tool set. I've seen tool selection accuracy jump from 70% to 95% just by narrowing each agent's scope. The trade-off is orchestration complexity, context passing overhead, and the very real risk of delegation loops that burn budget until someone notices.

## The orchestrator-workers pattern

```
User query
    ↓
Orchestrator (plans, delegates, synthesizes)
    ↓ ↓ ↓
Research    Writer    Executor
(read tools) (no tools) (write tools)
    ↓ ↓ ↓
Orchestrator synthesizes final response
```

The orchestrator's job is narrow:
1. Understand the user's goal
2. Decide which sub-agents to invoke (possibly in parallel)
3. Pass each sub-agent a focused task description
4. Synthesize sub-agent results into the final answer

The orchestrator does NOT do research or execution itself — it delegates.

## Sub-agent interface

Keep the contract simple:

```python
@dataclass
class SubAgentTask:
    agent_type: Literal["research", "writer", "executor", "coder"]
    instruction: str          # what to accomplish
    context: dict             # relevant facts, not full history
    max_steps: int = 10

@dataclass
class SubAgentResult:
    agent_type: str
    success: bool
    output: str
    structured_data: dict | None
    steps_used: int
    cost_usd: float

async def delegate(task: SubAgentTask) -> SubAgentResult:
    agent = get_specialist(task.agent_type)
    return await agent.run(
        instruction=task.instruction,
        context=task.context,
        budget=RunBudget(max_steps=task.max_steps, max_cost_usd=0.50),
    )
```

Each sub-agent gets a fresh context window with only what it needs — not the full conversation history. This is cheaper and reduces confusion.

## Context passing: less is more

The biggest mistake is passing the entire orchestrator transcript to every sub-agent. Pass structured context:

```python
# Bad: 8000 tokens of full history
sub_result = await delegate(SubAgentTask(
    agent_type="research",
    instruction="Find pricing for Vendor B",
    context={"full_transcript": orchestrator.history},  # NO
))

# Good: just what's needed
sub_result = await delegate(SubAgentTask(
    agent_type="research",
    instruction="Find pricing for Vendor B's enterprise plan",
    context={
        "vendor_name": "Vendor B",
        "requirements": ["enterprise tier", "annual billing"],
        "budget_limit": 50000,
    },
))
```

The orchestrator extracts relevant facts before delegating. Sub-agents return structured results the orchestrator can merge.

## Specialist agent design

Each specialist gets:

| Property | Research agent | Executor agent | Code agent |
|----------|---------------|----------------|------------|
| Tools | search, fetch, RAG | create, update, send | REPL, file read |
| System prompt | "Find and summarize facts" | "Execute approved actions" | "Write and run code" |
| Max steps | 15 | 5 | 20 |
| Guardrails | Read-only | Approval required | Sandboxed |

The executor agent should have the fewest tools and the strictest [action guardrails](https://blog.michaelsam94.com/agent-guardrails-input-output/). The research agent can be more exploratory.

## Parallel vs sequential delegation

**Parallel** when sub-tasks are independent:

```python
research_tasks = [
    SubAgentTask("research", "Research Vendor A pricing", ctx_a),
    SubAgentTask("research", "Research Vendor B pricing", ctx_b),
    SubAgentTask("research", "Research Vendor C pricing", ctx_c),
]
results = await asyncio.gather(*[delegate(t) for t in research_tasks])
synthesis = await orchestrator.synthesize(results)
```

**Sequential** when later tasks depend on earlier results:
research → plan → execute. Each phase completes before the next delegates.

## Preventing delegation loops

Hard limits in the orchestrator:

```python
MAX_DELEGATIONS = 5
MAX_DEPTH = 2  # orchestrator → sub-agent only, no nesting

class OrchestratorState:
    delegation_count: int = 0
    depth: int = 0

async def safe_delegate(state: OrchestratorState, task: SubAgentTask):
    if state.delegation_count >= MAX_DELEGATIONS:
        raise DelegationLimit("max delegations reached")
    if state.depth >= MAX_DEPTH:
        raise DelegationLimit("max depth reached")
    state.delegation_count += 1
    return await delegate(task)
```

If the orchestrator tries to delegate a sub-agent that tries to delegate another sub-agent, stop it. Depth-2 is almost always enough; depth-3 is where loops live.

Also: sub-agents return results, they don't delegate further. Only the orchestrator has delegation privileges.

## When sub-agents are overkill

For a 3-tool customer support agent that answers FAQs, sub-agents add latency and complexity without benefit. The threshold is roughly 12–15 tools or distinct security boundaries between read and write operations. Below that, one well-prompted agent with good [tool routing](https://blog.michaelsam94.com/agent-tool-selection-routing/) is simpler and faster.

## Subagent boundary design

| Subagent | Tools | Context |
|----------|-------|---------|
| Researcher | Read-only search, fetch | Full query |
| Executor | Write tools | Minimal task spec |
| Critic | None | Output to review |

Orchestrator passes structured handoff JSON, not full chat history — reduces token cost and context bleed.

## Common production mistakes

Teams get subagent delegation patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using subagent delegation patterns loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When subagent delegation patterns misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Multi-agent orchestration patterns](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/)
- [LangGraph multi-agent systems](https://langchain-ai.github.io/langgraph/concepts/multi_agent/)
- [OpenAI Swarm framework](https://github.com/openai/swarm)
- [CrewAI multi-agent framework](https://docs.crewai.com/)
- [Agent cost control and budgets](https://blog.michaelsam94.com/agent-cost-control-budgets/)
