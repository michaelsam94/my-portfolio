---
title: "LLM Observability: Tracing Agents with OpenTelemetry GenAI"
slug: "llm-observability-opentelemetry-genai"
description: "LLM observability with OpenTelemetry GenAI: trace agent loops, tool calls, token usage, and retrieval spans for production debugging and cost control."
datePublished: "2026-02-19"
dateModified: "2026-02-19"
tags: ["Observability", "OpenTelemetry", "LLM", "Agents"]
keywords: "LLM observability, GenAI tracing, OpenTelemetry GenAI, agent tracing, LLM monitoring, spans, semantic conventions"
faq:
  - q: "What is OpenTelemetry GenAI?"
    a: "It's a set of OpenTelemetry semantic conventions that standardize how you trace generative AI operations — naming spans, attributes for model, token counts, cost, and tool calls. Using them means your LLM traces work in any OTel-compatible backend instead of a proprietary format."
  - q: "Why do LLM agents need distributed tracing?"
    a: "A single user request can trigger a dozen model calls, retrievals, and tool executions. Without a trace tying them together, debugging a bad answer means guessing. A trace shows the exact sequence, inputs, outputs, latency, and cost of every step, so failures become visible instead of mysterious."
  - q: "What should I record on an LLM span?"
    a: "The model name, request parameters, prompt and completion token counts, latency, and cost, plus tool-call details and errors. Be deliberate about logging prompt and response content — it's invaluable for debugging but carries privacy and cost implications, so sample or redact."
---

An LLM agent that misbehaves in production is a special kind of debugging pain. The answer was wrong, but why? Was it bad retrieval, a tool that returned garbage, a prompt that got truncated, or the model just fumbling? Without tracing, you're reading logs and guessing. With proper observability, you open one trace and see the entire decision path — every model call, every tool result, every token, and where the time and money went.

OpenTelemetry's GenAI semantic conventions make this vendor-neutral. Instead of locking into one LLM-monitoring SaaS, you instrument with standard OTel spans and attributes and send them anywhere — Jaeger, Grafana Tempo, Datadog, Langfuse, Phoenix. The same discipline that made microservices debuggable now applies to agents, and it's the difference between "the AI is flaky" and "retrieval returned stale chunks for queries matching this pattern."

## Traces, spans, and why agents map onto them cleanly

A trace represents one end-to-end request; spans are the nested operations inside it. Agents map onto this model naturally because an agent run *is* a tree of operations:

```text
Trace: handle_support_query                        [1,840ms, $0.021]
├─ span: agent.run                                 [1,835ms]
│  ├─ span: retrieval.search        (vector db)    [ 120ms]
│  ├─ span: gen_ai.chat  gpt-4o     (plan)         [ 410ms, 1.2k tok]
│  ├─ span: tool.get_order_status                  [  90ms]
│  ├─ span: gen_ai.chat  gpt-4o     (answer)       [ 980ms, 2.4k tok]
│  └─ span: guardrail.output_moderation            [  35ms]
```

Read top to bottom and the agent's reasoning is laid bare: it retrieved, planned, called a tool, composed an answer, and checked it. When something's wrong, the offending span is right there with its inputs and outputs.

## The GenAI semantic conventions

The value of the OTel GenAI conventions is agreement on *names*, so tooling can compute cost, token usage, and error rates without custom parsing. The core span for a model call uses operation names like `gen_ai.chat` and attributes such as:

| Attribute | Example | Purpose |
|---|---|---|
| `gen_ai.system` | `openai` | provider |
| `gen_ai.request.model` | `gpt-4o` | requested model |
| `gen_ai.response.model` | `gpt-4o-2024-08-06` | model that answered |
| `gen_ai.usage.input_tokens` | `1180` | prompt tokens |
| `gen_ai.usage.output_tokens` | `240` | completion tokens |
| `gen_ai.request.temperature` | `0.2` | sampling params |

Token counts on every span are what let you build a cost view for free — sum them, multiply by per-model rates, and you've got per-request and per-feature cost attribution, which feeds directly into [cutting LLM costs](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/).

## Instrumenting in practice

The fastest path is auto-instrumentation. OpenLLMetry (from Traceloop) and OpenInference (from Arize Phoenix) both patch popular SDKs to emit GenAI-convention spans with almost no code:

```python
from traceloop.sdk import Traceloop

Traceloop.init(app_name="support-agent")  # auto-instruments OpenAI, Anthropic, etc.
# your existing LLM calls now emit spans automatically
```

For the parts auto-instrumentation doesn't cover — your own agent loop, retrieval, tools — add manual spans so the tree is complete:

```python
from opentelemetry import trace
tracer = trace.get_tracer("support-agent")

with tracer.start_as_current_span("tool.get_order_status") as span:
    span.set_attribute("tool.name", "get_order_status")
    span.set_attribute("order.id", order_id)
    result = get_order_status(order_id)
    span.set_attribute("tool.result_size", len(result))
```

Wrap tools and retrieval like this and every step lands in the same trace, correlated by trace ID with the rest of your backend. That last point is underrated: because it's plain OpenTelemetry, an LLM span sits in the *same* trace as the HTTP request, database query, and cache lookup around it. You see the whole request, not just the AI slice — the same [observability and SLO](https://blog.michaelsam94.com/designing-for-observability-slos/) discipline you'd apply to any service.

## What to actually watch

Instrumentation is the means; here's what the data is for:

- **Latency, broken down by span.** Time-to-first-token, per-model latency, tool latency. When p95 spikes, the trace says whether it's the model, a slow tool, or retrieval.
- **Cost per request and per feature.** Aggregated token attributes. This is how you find the one endpoint quietly burning the budget.
- **Quality signals.** Attach eval scores, guardrail verdicts, and user feedback (thumbs up/down) to traces so you can pull up every low-scored run and see what they share. This closes the loop with your [eval suite](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/).
- **Error and retry rates.** Failed tool calls, schema-validation failures, moderation blocks, model timeouts.

## The privacy and cost decision on content

The one genuinely hard call is whether to log prompt and completion *content*. It's the single most useful thing for debugging — you can't diagnose a bad answer you can't see — but it carries real weight:

- **Privacy.** Prompts contain user data. Logging it raw may violate your own policy or regulations. Redact PII before it hits the span, and restrict who can read trace content.
- **Cost and volume.** Full prompt/response text on high-traffic endpoints balloons storage. Sample it — capture content on a percentage of traffic and on all errors and low-scored runs, where it matters most.

A workable default: record metadata (model, tokens, latency, cost) on 100% of requests, and content on a sampled subset plus every failure. You keep debuggability where you need it without logging every user's data forever.

Set this up early — retrofitting tracing onto an agent already misbehaving in production is miserable, while having it from day one turns "the AI is flaky" into a trace you can actually read. Standard conventions mean you're never locked into one vendor's dashboard, and the traces live right alongside the rest of your system's telemetry.

## Resources

- [OpenTelemetry — GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [OpenTelemetry — Official documentation](https://opentelemetry.io/docs/)
- [OpenLLMetry / Traceloop (GitHub)](https://github.com/traceloop/openllmetry)
- [Arize Phoenix — OpenInference](https://github.com/Arize-ai/openinference)
- [Langfuse documentation](https://langfuse.com/docs)
- [Grafana Tempo documentation](https://grafana.com/docs/tempo/latest/)
