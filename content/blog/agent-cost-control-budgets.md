---
title: "Budgets and Cost Control for Agents"
slug: "agent-cost-control-budgets"
description: "Practical cost control for LLM agents: per-run budgets, model routing, caching, token accounting, and kill switches that prevent runaway spend."
datePublished: "2026-06-22"
dateModified: "2026-06-22"
tags: ["AI Agents", "LLM", "Architecture", "DevOps"]
keywords: "LLM agent cost control, agent budget limits, token cost optimization, model routing agents, LLM spend monitoring"
faq:
  - q: "How do you set a budget for an LLM agent?"
    a: "Define hard limits at three levels: per-request (max tokens and max tool calls), per-session (cumulative spend cap), and per-tenant daily/monthly quota. Enforce them in middleware before each LLM call, not after. When a limit is hit, return a graceful degradation response rather than silently failing mid-task."
  - q: "What is the cheapest way to run agents at scale?"
    a: "Route easy steps to smaller models and reserve frontier models for planning or failure recovery. Cache tool results and [semantic-cache](https://blog.michaelsam94.com/semantic-caching-llm-apis/) identical queries. Compress conversation history aggressively. Batch independent tool calls. These four levers typically cut spend 60–80% without changing agent capability."
  - q: "How do you detect runaway agent loops?"
    a: "Track step count, cumulative tokens, and repeated identical actions. If the agent calls the same tool with the same arguments three times, or exceeds 20 steps without progress, halt and escalate. Set wall-clock timeouts independent of token limits — a stuck agent burning tokens slowly is worse than one that fails fast."
---

The first time an agent loop ran unchecked in staging, it cost $847 in an afternoon. Not because the model was expensive — because nobody put a ceiling on steps, nobody routed simple lookups to a cheap model, and the agent kept re-querying a vector store with slightly rephrased questions that returned the same chunks. Agent cost isn't a finance problem you solve after launch; it's a reliability constraint you design in from day one, the same way you'd cap database connection pools.

## The cost stack

Agent spend breaks down predictably:

| Component | Typical share | Control lever |
|-----------|--------------|---------------|
| LLM inference (planning + synthesis) | 50–70% | Model routing, prompt compression |
| Tool calls (embeddings, search, APIs) | 15–30% | Caching, batching |
| Vision / long context | 5–20% | DOM over screenshots, summarization |
| Retries and loops | 0–50% (spiky) | Step limits, duplicate detection |

That last row is where budgets save you. A healthy agent runs 5–12 steps. A broken one runs 200.

## Hard budgets in middleware

Don't trust the agent to self-limit. Enforce in your orchestration layer:

```python
@dataclass
class RunBudget:
    max_steps: int = 25
    max_input_tokens: int = 500_000
    max_output_tokens: int = 50_000
    max_cost_usd: float = 2.00
    max_wall_seconds: float = 120.0

class BudgetTracker:
    def __init__(self, budget: RunBudget):
        self.budget = budget
        self.steps = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0
        self.started = time.monotonic()

    def check(self) -> None:
        if self.steps >= self.budget.max_steps:
            raise BudgetExceeded("step limit")
        if self.cost_usd >= self.budget.max_cost_usd:
            raise BudgetExceeded("cost limit")
        if time.monotonic() - self.started > self.budget.max_wall_seconds:
            raise BudgetExceeded("timeout")
```

Call `check()` before every LLM invocation and every tool call. On `BudgetExceeded`, summarize what was accomplished so far and return partial results — users prefer "here's what I found before hitting the limit" over a generic error.

## Model routing that actually saves money

Not every turn needs your best model:

- **Router/classifier** (cheap, fast): intent detection, tool selection, "is this done?"
- **Worker** (mid-tier): tool argument generation, summarization, formatting
- **Planner** (frontier): multi-step reasoning, failure recovery, ambiguous goals

I've seen teams cut inference cost 70% by running Haiku/GPT-4o-mini for tool calls and Opus/GPT-4 only when the worker fails twice. The routing decision itself should cost fractions of a cent — a 50-token classification call, not a full re-read of conversation history.

## Conversation history compression

An agent at step 20 sends the entire transcript — including ten full tool outputs — back to the model. That's linear cost growth per step. Compress aggressively:

1. **Summarize completed subtasks** into 2–3 sentences, drop raw tool output
2. **Keep last N turns verbatim**, summarize everything before
3. **Structured state** instead of chat history where possible (current plan, completed steps, pending tools)

The [memory summarization strategies](https://blog.michaelsam94.com/agent-memory-summarization-strategies/) you use for long sessions are the same techniques that control per-run cost.

## Caching layers

- **Exact cache**: same prompt hash → return cached response (great for FAQ-style agents)
- **Tool result cache**: TTL-based cache on `search(query)` and `fetch_url(url)`
- **Embedding cache**: never re-embed the same document chunk twice
- **Semantic cache**: similar queries hit cached answers (watch for stale answers on time-sensitive data)

Instrument cache hit rates per tool. A 40% hit rate on search alone pays for the Redis cluster.

## Kill switches and alerting

Set org-level daily spend caps in your provider dashboard *and* in application code. Alert at 50% and 80% of daily budget. When staging exceeds $50/day, page someone — that's almost always a loop, not legitimate traffic.

Log cost per agent run with tenant ID, user ID, and task type. The teams that control spend are the ones that can answer "which workflow costs us $3 per invocation?" within five minutes.

Alert at 80% of daily budget, hard-stop at 100% — soft limits without enforcement become finance surprises at month close.

## Per-tenant billing and chargeback

Expose cost in your product dashboard:

```python
@dataclass
class RunCost:
    tenant_id: str
    input_tokens: int
    output_tokens: int
    model: str
    cost_usd: float

async def record_run_cost(run: AgentRun) -> None:
    cost = calculate_cost(run.model, run.input_tokens, run.output_tokens)
    await billing.increment(tenant_id=run.tenant_id, amount=cost)
    await metrics.histogram("agent.cost_usd", cost, tags={"tenant": run.tenant_id})
```

Enterprise customers expect usage reports — build export before sales promises it.

## Budget-aware routing

When tenant approaches budget limit, degrade gracefully:

```python
if tenant.remaining_budget_usd < 0.10:
    model = "gpt-4o-mini"  # cheaper fallback
elif tenant.remaining_budget_usd <= 0:
    raise BudgetExceeded(tenant_id)
```

Notify tenant admin at 80% — surprise hard stops damage customer relationships more than model downgrade.

Pair with [LLM retry fallback strategies](https://blog.michaelsam94.com/llm-retry-fallback-strategies/) when budget limits trigger model downgrades.

## Common production mistakes

Teams get cost control budgets wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using cost control budgets loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When cost control budgets misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenAI pricing and usage API](https://platform.openai.com/docs/guides/usage)
- [Anthropic cost and usage documentation](https://docs.anthropic.com/en/api/rate-limits)
- [LangSmith cost tracking](https://docs.smith.langchain.com/)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Martin Fowler — LLM cost optimization patterns](https://martinfowler.com/articles/engineering-practices-for-LLM-applications.html)
