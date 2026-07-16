---
title: "Tracing Agent Runs with Spans"
slug: "agent-observability-tracing-spans"
description: "Instrument LLM agents with OpenTelemetry spans: trace LLM calls, tool executions, and decision points to debug failures and optimize cost in production."
datePublished: "2026-07-01"
dateModified: "2026-07-01"
tags: ["AI Agents", "LLM", "DevOps", "Architecture"]
keywords: "agent observability, OpenTelemetry LLM tracing, agent spans, LLM tracing, agent debugging production"
faq:
  - q: "What should you trace in an LLM agent?"
    a: "Trace every LLM call, tool execution, guardrail check, retrieval query, and state transition as spans within a parent trace per agent run. Capture latency, token counts, model ID, tool name, success/failure, and cost. Avoid logging full prompts in spans — log hashes and token counts instead."
  - q: "How is agent tracing different from application tracing?"
    a: "Agent traces are deeper and more sequential — a single user request may produce 5–30 spans across multiple LLM calls and tool invocations. Spans need to capture model-specific attributes (input/output tokens, finish reason) and semantic attributes (tool args, retrieval scores) that standard HTTP tracing doesn't cover."
  - q: "What tools support LLM agent tracing?"
    a: "OpenTelemetry with GenAI semantic conventions works with any backend (Jaeger, Datadog, Honeycomb). LangSmith and Langfuse provide agent-specific UIs on top. Choose based on whether your team already has an OTel pipeline or needs an agent-focused dashboard out of the box."
---

When an agent fails in production, "the model gave a wrong answer" is not a useful bug report. You need to know: which turn failed, what tools were called, what they returned, how many tokens were burned, and whether a guardrail blocked something silently. Agent observability through distributed tracing — one trace per run, spans per LLM call and tool execution — turns agent debugging from archaeology into engineering. I won't ship an agent without tracing anymore; the first production incident without it always costs more than the instrumentation effort.

## Trace structure

One user request = one trace. Everything else is a span:

```
Trace: agent_run_abc123 (user: "refund order 4521")
├── span: guardrail_input (2ms, pass)
├── span: llm_call_1 (planning) (1.2s, 840 in / 120 out tokens)
├── span: tool:lookup_order (340ms, success)
├── span: llm_call_2 (reasoning) (980ms, 1200 in / 85 out tokens)
├── span: guardrail_action (5ms, requires_approval)
├── span: approval_wait (12min, approved)
├── span: tool:create_refund (520ms, success)
├── span: llm_call_3 (response) (750ms, 900 in / 95 out tokens)
└── span: guardrail_output (3ms, pass)
```

Parent span is the agent run. Child spans are the work units. This maps directly to how you think about agent execution.

## Instrumentation with OpenTelemetry

```python
from opentelemetry import trace

tracer = trace.get_tracer("agent.orchestrator")

async def run_agent(user_message: str, session_id: str):
    with tracer.start_as_current_span("agent_run") as span:
        span.set_attribute("agent.session_id", session_id)
        span.set_attribute("agent.user_message_length", len(user_message))

        with tracer.start_as_current_span("llm_call") as llm_span:
            llm_span.set_attribute("gen_ai.system", "openai")
            llm_span.set_attribute("gen_ai.request.model", "gpt-4o")
            response = await llm.complete(messages)
            llm_span.set_attribute("gen_ai.usage.input_tokens", response.usage.input)
            llm_span.set_attribute("gen_ai.usage.output_tokens", response.usage.output)
            llm_span.set_attribute("gen_ai.response.finish_reasons", [response.finish_reason])

        with tracer.start_as_current_span("tool.execute") as tool_span:
            tool_span.set_attribute("agent.tool.name", "lookup_order")
            tool_span.set_attribute("agent.tool.args", json.dumps(args))
            result = await execute_tool("lookup_order", args)
            tool_span.set_attribute("agent.tool.success", result.success)
```

Use the [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/) — `gen_ai.request.model`, `gen_ai.usage.input_tokens`, etc. — so traces are portable across backends.

## What to capture vs what to avoid

**Capture in spans:**
- Latency per LLM call and tool
- Token counts and model ID
- Tool name and argument schema (not full PII payloads)
- Success/failure and error type
- Cost estimate per span
- Retrieval scores and chunk IDs (not chunk text)

**Do NOT capture in spans:**
- Full prompt text with user PII
- Complete tool responses with sensitive data
- API keys or auth tokens

For debugging prompts, use a separate secure debug mode with explicit opt-in, not production tracing.

## Dashboards that matter

Build these views from day one:

**Run explorer** — search traces by session ID, user ID, outcome (success/fail/timeout). Click into span waterfall.

**Cost attribution** — sum `gen_ai.usage.*` tokens by agent type, tenant, time period. Pair with [budget tracking](https://blog.michaelsam94.com/agent-cost-control-budgets/).

**Tool reliability** — error rate and p95 latency per tool. A degrading tool shows up here before users complain.

**Step distribution** — histogram of span count per trace. A bimodal distribution (5 steps vs 40 steps) usually means two distinct failure modes.

**Guardrail blocks** — count and reason codes. Spikes indicate attack or prompt drift.

## Connecting traces to eval

Export failed traces to your eval dataset:

```python
async def on_run_complete(trace_id: str, outcome: str):
    if outcome == "failure" or trace.step_count > STEP_THRESHOLD:
        scenario = await trace_to_scenario(trace_id)
        await eval_dataset.add(scenario, source="production", trace_id=trace_id)
```

Production failures become [eval scenarios](https://blog.michaelsam94.com/agent-evaluation-trajectory-analysis/) automatically. This closed loop is the highest-ROI observability investment for agents.

## Sampling strategy

Tracing every span of every run gets expensive in storage. Sample intelligently:

- **100% capture**: failures, runs exceeding cost threshold, first N runs per day per agent type
- **10% sample**: successful happy-path runs
- **0%**: health check / warmup runs

Always capture full traces for failures. The cost of storing a failed trace is negligible compared to the cost of not being able to debug it.

## Span naming conventions

Consistent names enable aggregation:

```
agent.run                    # root span per user request
agent.llm.chat              # LLM API call
agent.tool.{tool_name}      # tool execution
agent.retrieval             # RAG lookup
agent.guardrail.input       # input validation
agent.guardrail.output      # output validation
```

Attributes on every span:

```python
span.set_attribute("agent.session_id", session_id)
span.set_attribute("agent.tenant_id", tenant_id)
span.set_attribute("gen_ai.request.model", model)
span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
```

## Cost attribution from traces

Sum token attributes per trace → per-tenant daily cost:

```sql
SELECT tenant_id, SUM(input_tokens + output_tokens) AS tokens
FROM trace_spans
WHERE span_name = 'agent.llm.chat'
  AND timestamp > NOW() - INTERVAL '1 day'
GROUP BY tenant_id
ORDER BY tokens DESC;
```

Traces without token attributes are useless for FinOps — instrument at LLM client wrapper, not ad hoc.

Pair with [agent evaluation trajectory analysis](https://blog.michaelsam94.com/agent-evaluation-trajectory-analysis/) when exporting failed traces to eval datasets.

## Common production mistakes

Teams get observability tracing spans wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using observability tracing spans loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Resources

- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [LangSmith tracing documentation](https://docs.smith.langchain.com/tracing)
- [Langfuse observability platform](https://langfuse.com/docs)
- [OpenLLMetry — OTel instrumentation for LLMs](https://github.com/traceloop/openllmetry)
- [LLM observability with OpenTelemetry](https://blog.michaelsam94.com/llm-observability-opentelemetry-genai/)
