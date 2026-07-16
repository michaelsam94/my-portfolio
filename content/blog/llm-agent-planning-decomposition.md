---
title: "Task Decomposition for Agents"
slug: "llm-agent-planning-decomposition"
description: "How to break complex goals into agent-executable subtasks: planning patterns, dependency graphs, replanning triggers, and when decomposition hurts more than it helps."
datePublished: "2024-10-04"
dateModified: "2024-10-04"
tags: ["AI", "LLM", "AI Agents", "Architecture"]
keywords: "LLM task decomposition, agent planning, subtask breakdown, agent orchestration, hierarchical agents"
faq:
  - q: "How granular should agent subtasks be?"
    a: "Each subtask should map to one verifiable outcome — a file edited, a query answered, a ticket created — completable in 3–8 tool calls. Smaller tasks waste tokens on coordination; larger tasks let the agent drift. If you can't write a one-sentence success criterion, the task is too big."
  - q: "Should the planner and executor be separate models?"
    a: "Often yes. A frontier model plans; a cheaper model executes tool calls and summarizes results. Re-planning after failures can stay on the frontier model. This cuts cost 50–70% on long runs without sacrificing plan quality on the hard decisions."
  - q: "When does decomposition fail?"
    a: "When the goal requires tight integration across steps — refactoring five files with cross-dependencies — or when intermediate state is hard to verify. Decomposition works best when subtasks are loosely coupled and each produces an inspectable artifact."
---

"Book me a flight to Berlin next Tuesday under $400" sounds like one request. To an agent, it's six subtasks with dependencies: parse dates, search flights, filter by price, check seat availability, collect payment info, confirm booking. Skip the decomposition step and the agent searches airlines before it knows your departure city. Do it badly and you get six redundant API calls and a confirmation for the wrong week.

Task decomposition is the difference between an agent that finishes and one that confuses motion for progress.

## Plan-then-execute vs interleaved planning

Two patterns dominate:

**Plan-then-execute**: generate the full task list upfront, then run each item sequentially.

```python
plan = planner.decompose(
    goal="Migrate users table to new schema",
    context=schema_docs,
)

for step in plan.steps:
    result = executor.run(step, prior_results=plan.completed)
    plan.mark_done(step.id, result)
    if result.failed:
        plan = planner.replan(plan, failure=result.error)
```

**Interleaved (ReAct-style)**: decide the next step after each tool result. Better when the environment is unpredictable — debugging, exploratory data analysis — but harder to budget because step count is unbounded.

Use plan-then-execute for workflows you understand (deployments, ETL, form filling). Use interleaved for open-ended investigation.

## Writing decomposable goals

A decomposable goal has:

- A clear **terminal condition** ("migration complete, all rows validated")
- **Independent checkpoints** ("schema created", "data copied", "indexes rebuilt")
- **Verifiable outputs** per step (a row count, a HTTP 200, a diff)

Bad decomposition prompt:

> Break this into steps.

Better:

> Decompose into subtasks. Each subtask must: (1) have a single verb, (2) list required inputs from prior steps, (3) define how to verify success, (4) estimate whether it needs write access. Output JSON.

```json
{
  "steps": [
    {
      "id": "s1",
      "task": "Export current users table to staging bucket",
      "depends_on": [],
      "verify": "row count matches production count ± 0",
      "tools": ["sql_query", "s3_upload"]
    }
  ]
}
```

Structured output makes orchestration code trivial and lets you parallelize steps with empty `depends_on` arrays.

## Dependency graphs and parallelism

Not all steps are sequential. A dependency DAG lets independent branches run concurrently:

```
     [Parse intent]
        /        \
 [Search flights] [Check calendar]
        \        /
      [Rank options]
           |
      [Book selected]
```

In Python, topological sort + `asyncio.gather` on each level:

```python
async def run_level(steps: list[Step], ctx: Context) -> None:
    await asyncio.gather(*[execute(s, ctx) for s in steps])

for level in plan.topological_levels():
    await run_level(level, ctx)
```

Parallel decomposition is where agents beat sequential chains on latency — three independent API calls in one wall-clock second instead of three.

## Replanning triggers

Static plans break. Replan when:

- A tool returns unexpected data (empty search results)
- A step fails twice with the same error
- New information invalidates assumptions ("flight cancelled")
- Budget threshold hit (step 8 of 12, 80% tokens consumed)

Don't replan on every hiccup — that burns tokens. Retry transient failures once, then escalate to the planner with the failure context:

```python
if step.attempts >= 2 and not step.transient_error:
    new_steps = planner.replan(
        original_goal=plan.goal,
        completed=plan.completed,
        failure={"step": step.id, "error": step.last_error},
    )
```

## Hierarchical decomposition

Deep tasks need nested plans. "Build a REST API" decomposes into modules; each module decomposes into endpoints; each endpoint into handler + tests.

Cap recursion depth at 2–3 levels. Deeper hierarchies produce plans that look organized but execute slowly because coordination overhead dominates.

A supervisor agent holds the top-level plan. Worker agents receive single subtasks with isolated context windows — they don't need the full project history, just their assignment and shared artifacts (schema, API spec).

## Measuring decomposition quality

Track these per run:

- **Steps planned vs steps executed** — large gaps mean bad initial plans
- **Replan count** — more than two replans usually means the goal was underspecified
- **Wasted steps** — tool calls whose results no subsequent step used
- **Time-to-first-useful-output** — users care about early progress

A/B test decomposition prompts against a golden set of 30 multi-step tasks. The winning prompt isn't the one that produces the prettiest plan — it's the one with the highest task completion rate under a fixed token budget.

## When to skip decomposition

Single-tool queries ("what's the weather in Oslo?") don't need a planner. Classification → direct tool call → response.

Similarly, tightly coupled code edits across a monolith often work better as one agent with full repo context than six sub-agents each holding a fragment.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get agent planning decomposition wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around agent planning decomposition break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When agent planning decomposition misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [ReAct: Synergizing Reasoning and Acting](https://arxiv.org/abs/2210.03629)
- [Plan-and-Solve Prompting](https://arxiv.org/abs/2305.04091)
- [LangGraph multi-agent workflows](https://langchain-ai.github.io/langgraph/)
- [AutoGPT task management patterns](https://docs.agpt.co/)
- [Anthropic tool use documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
