---
title: "Agent Planning: ReAct vs Plan-and-Execute"
slug: "agent-planning-react-vs-plan-execute"
description: "ReAct vs plan-and-execute for agent planning: how each reasons, their cost and reliability tradeoffs, and how to pick the right pattern for your workload."
datePublished: "2026-04-29"
dateModified: "2026-04-29"
tags: ["AI Agents", "LLM", "Architecture"]
keywords: "ReAct, plan and execute, agent planning, reasoning acting, agent architecture, task decomposition"
faq:
  - q: "What is the difference between ReAct and plan-and-execute agents?"
    a: "ReAct interleaves reasoning and acting in a tight loop — the agent thinks, takes one action, observes the result, then decides the next step, adapting continuously. Plan-and-execute separates the two phases: a planner generates a full multi-step plan up front, then an executor carries out each step, often without re-planning until the plan finishes or fails. ReAct is more adaptive per step, while plan-and-execute is more predictable and usually cheaper for long tasks."
  - q: "When should I use plan-and-execute over ReAct?"
    a: "Use plan-and-execute when the task decomposes into a fairly stable sequence of steps, when you want to review or constrain the plan before execution, or when you need to cut token cost on long horizons. ReAct suits open-ended, exploratory tasks where each next step genuinely depends on what the previous one returned. Many production agents blend both, planning at a high level and using ReAct within steps."
  - q: "Which agent planning pattern is more reliable?"
    a: "Neither is universally more reliable; they fail differently. ReAct can wander, loop, or lose the thread over many steps because it never commits to a plan, while plan-and-execute can stubbornly follow a plan that reality has already invalidated. Reliability comes less from the pattern and more from step verification, bounded retries, and clear termination conditions layered on top of whichever you choose."
---

Give an agent a non-trivial task and the first architectural question is *how it decides what to do next*. The two dominant answers are ReAct, which interleaves thinking and acting one step at a time, and plan-and-execute, which drafts a full plan up front and then carries it out. Agent planning is this control loop — the strategy that turns a goal into a sequence of tool calls — and choosing between these patterns shapes your agent's cost, adaptability, and failure modes more than almost any other decision.

I've built both, and the honest summary is that neither is "better." They're tuned for different problems, and the mistake is picking one dogmatically. Let me lay out how each actually behaves.

## ReAct: think, act, observe, repeat

ReAct (Reasoning + Acting) runs a loop. The model produces a thought, chooses one action (a tool call), observes the result, and feeds that observation back in to decide the next thought and action. It keeps going until it decides the task is done.

```text
Thought: I need the user's latest order status.
Action: search_orders(email="a@b.com")
Observation: [{id: 4821, status: "shipped", ...}]
Thought: It shipped. The user asked about delivery, so I need tracking.
Action: get_tracking(order_id=4821)
Observation: {eta: "2026-05-02", carrier: "DHL"}
Thought: I have enough to answer.
```

The strength is adaptivity: every decision is made with the freshest information, so ReAct handles tasks where you genuinely can't know step 3 until you've seen the output of step 2. Exploratory research, debugging, anything branchy — ReAct shines.

The weaknesses are equally real. Because it never commits to a plan, it can wander, revisit dead ends, or loop when an observation is ambiguous. And it's token-hungry: the full growing transcript of thoughts and observations is re-sent on every step, so a 15-step task pays a rising context cost each iteration. On long horizons that adds up fast — which is one of the pressures behind [cutting LLM costs with caching, routing, and batching](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/).

## Plan-and-execute: commit first, then do

Plan-and-execute splits the work. A **planner** call reads the goal and emits a structured, multi-step plan. An **executor** then runs each step — often with cheaper models or plain code — and only returns to the planner if a step fails or the plan is exhausted.

```text
PLAN (generated once):
  1. Find the user's most recent order        -> search_orders
  2. If shipped, fetch tracking               -> get_tracking
  3. Summarize delivery status for the user

EXECUTE: run step 1, step 2, step 3 in sequence.
```

The advantages: the expensive reasoning happens once, not every step, so long tasks get cheaper. The plan is inspectable — you can log it, validate it, or even require human approval before execution, which matters for anything with side effects. And execution is more predictable because the agent isn't re-deciding its whole strategy at each turn.

The cost is rigidity. If reality diverges from the plan — step 2 returns something unexpected — a naive executor plows ahead on a plan that no longer makes sense. So real plan-and-execute systems add a re-planning trigger: when a step fails or an observation violates the plan's assumptions, kick back to the planner with the new state. That gives you the predictability of planning with an escape hatch when the world doesn't cooperate.

## The tradeoffs side by side

| Dimension | ReAct | Plan-and-execute |
| --- | --- | --- |
| Adaptivity | High — decides each step live | Lower — commits to a plan |
| Token cost (long tasks) | Grows every step | Front-loaded, cheaper overall |
| Predictability | Lower — can wander | Higher — plan is fixed |
| Inspectable before acting | No | Yes — review the plan |
| Best at | Open-ended, branchy tasks | Structured, decomposable tasks |
| Classic failure | Loops, drift, dead ends | Following a stale plan |

The pattern I've settled on for most production work is a hybrid: plan at the high level to get a reviewable, cost-efficient backbone, and let the executor use a small ReAct loop *within* a step when that step is itself uncertain. You get the structure of a plan and the adaptivity of ReAct exactly where you need it.

## Reliability comes from the scaffolding, not the pattern

Here's the part teams underestimate: whichever loop you pick, its reliability is dominated by what you wrap around it. A bare ReAct or plan-and-execute agent is a demo. The scaffolding that makes it production-grade:

- **Step verification.** After each action, check the result is sane before continuing. A tool that returned an error or empty set should change behavior, not be blindly accepted.
- **Bounded loops.** Hard-cap total steps and detect repetition (same action, same args, twice) to kill runaway loops before they burn your budget.
- **Clear termination.** Define what "done" means explicitly. Agents that don't know when to stop either quit early or never stop.
- **State you can resume.** Persist the plan and progress so a crash or timeout doesn't restart from scratch.

All of this is the substance of [building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/) — the planning pattern is the skeleton, but the verification, bounds, and termination are the muscle that keeps it from collapsing.

## Where multi-agent designs fit

Once tasks get large, a single planning loop stops scaling and you decompose across *agents*, not just steps. An orchestrator agent plans and delegates subtasks to specialized worker agents, each of which may internally use ReAct or plan-and-execute for its slice. That's a different axis of design — coordination between agents rather than within one — and it's the subject of [multi-agent orchestration with orchestrator-workers](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/). The ReAct-vs-plan question doesn't disappear at that scale; it recurs inside each agent.

## How to actually choose

Don't start from the pattern; start from the task. Ask: can I write down the likely steps in advance? If the sequence is fairly stable — a data pipeline, a form-filling workflow, a report generation — plan-and-execute gives you cost and control. If each step's very existence depends on the last one's output — investigation, troubleshooting, open research — ReAct's adaptivity earns its cost.

Then ask about side effects. If steps mutate real systems (send money, delete records), the ability to inspect and approve a plan before execution is worth a lot, which tilts toward plan-and-execute. And ask about horizon length: the longer the task, the more ReAct's per-step token growth hurts, and the more front-loaded planning pays off.

The teams that struggle are the ones that pick a pattern because a framework defaulted to it, then fight its failure mode forever. Match the loop to the shape of the work, wrap it in real verification and bounds, and be willing to blend the two. The planning pattern is a means to reliable task completion — not an identity to defend.

## Resources

- [ReAct: Synergizing Reasoning and Acting in Language Models (arXiv)](https://arxiv.org/abs/2210.03629)
- [Plan-and-Solve Prompting (arXiv)](https://arxiv.org/abs/2305.04091)
- [LangGraph — agent architectures documentation](https://langchain-ai.github.io/langgraph/)
- [Anthropic — building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Reflexion: language agents with verbal reinforcement learning (arXiv)](https://arxiv.org/abs/2303.11366)
