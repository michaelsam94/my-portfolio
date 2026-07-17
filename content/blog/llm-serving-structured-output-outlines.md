---
title: "Structured Output at Serving Time"
slug: "llm-serving-structured-output-outlines"
description: "Enforce JSON schemas and structured formats during LLM inference with constrained decoding, Outlines, and server-side grammar validation."
datePublished: "2025-03-09"
dateModified: "2026-07-17"
tags:
keywords: "structured output LLM, constrained decoding, Outlines library, JSON schema LLM, vLLM guided decoding, llama.cpp grammar"
faq:
  - q: "What is the difference between prompt-based JSON and constrained decoding?"
    a: "Prompt-based approaches ask the model to output JSON and hope it complies — it fails 5–15% of the time even with good models. Constrained decoding masks invalid tokens at each step so only schema-valid continuations are possible. The output is guaranteed valid; you pay a small latency overhead for the constraint engine."
  - q: "Does constrained decoding hurt output quality?"
    a: "Slightly, in edge cases. By preventing the model from exploring invalid token paths, you constrain its distribution. In practice, for well-defined schemas with reasonable field descriptions, quality impact is minimal because the model rarely 'wanted' to produce malformed JSON anyway."
  - q: "Can I use structured output with any model?"
    a: "Constrained decoding requires access to logits at each generation step, so it works with open-weight models served through vLLM, llama.cpp, or Outlines directly. Most closed APIs (OpenAI, Anthropic) offer their own structured output modes that work similarly under the hood."
---
Your pipeline expects the LLM to return `{"intent": "refund", "order_id": "12345", "amount": 29.99}`. Instead it returns a markdown code block wrapping JSON with a trailing comma and a comment explaining its reasoning. You add regex cleanup, a JSON repair library, and a retry loop — and you still fail 3% of production requests.

Structured output at serving time eliminates this class of failure by constraining token generation to valid schema paths. The model can only emit tokens that keep the partial output parseable against your JSON Schema, regex, or context-free grammar.

## Why prompt engineering is not enough

Even strong instruction-tuned models violate JSON format under pressure:

- Long outputs increase format drift.
- Low temperature reduces creativity but does not guarantee syntax.
- Tool-calling fine-tunes help but break on novel schemas.

```python
# This fails more than you'd expect in production
response = llm.generate(
    f"Return JSON matching this schema: {schema}\n\nExtract entities from: {text}"
)
data = json.loads(response)  # json.JSONDecodeError at 2am
```

Constrained decoding moves the guarantee from probabilistic to deterministic.

## How constrained decoding works

At each generation step, the inference engine:

1. Takes the current partial output.
2. Determines which tokens are valid continuations per the grammar/schema.
3. Sets logits of invalid tokens to −∞ (masking).
4. Samples or greedy-selects from the remaining valid tokens.

For JSON Schema, the engine maintains a parser state. If the partial output is `{"name": "`, the next tokens must start a valid JSON string — no `{`, no `[`, no bare words.

```python
import outlines

model = outlines.models.transformers("meta-llama/Llama-3.1-8B-Instruct")

schema = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["refund", "support", "cancel"]},
        "order_id": {"type": "string"},
        "amount": {"type": "number"},
    },
    "required": ["intent", "order_id"],
}

generator = outlines.generate.json(model, schema)
result = generator("Extract intent from: I want a refund for order 12345")
# result is a Python dict, guaranteed valid
```

## Outlines: schema-first generation

Outlines is the most mature open-source library for constrained generation. It supports:

- **JSON Schema** — nested objects, arrays, enums, numeric ranges.
- **Regex** — for flat string patterns like dates or IDs.
- **Context-free grammars** — for SQL, code, or custom DSLs.

Integration with vLLM via `--guided-decoding-backend outlines`:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --guided-decoding-backend outlines
```

Then pass schema in the API request:

```python
response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Extract entities from: ..."}],
    extra_body={
        "guided_json": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        }
    },
)
```

## Grammar-based constraints in llama.cpp

llama.cpp supports GBNF (GGML BNF) grammars for constrained generation:

```bash
llama-cli -m model.gguf \
  --grammar-file json.gbnf \
  -p "Extract: John is 30 years old"
```

GBNF grammars are more verbose than JSON Schema but offer fine-grained control — useful for SQL dialects, configuration formats, or domain-specific languages where JSON Schema is awkward.

## API-level structured output

Managed providers implement their own constrained decoding:

- **OpenAI** `response_format: { type: "json_schema", json_schema: {...} }` on GPT-4o and later.
- **Anthropic** tool use with `input_schema` effectively constrains output to the tool's parameter schema.
- **Google Gemini** `responseSchema` in generation config.

These are preferable when you do not self-host, but you have less visibility into the constraint engine and less control over fallback behavior.

## Performance considerations

Constrained decoding adds overhead per token:

- **Schema compilation:** one-time cost to convert JSON Schema to a finite state machine. Cache compiled schemas across requests.
- **Mask computation:** checking valid tokens at each step. Complex schemas with many optional fields increase branching.
- **Batch impact:** per-request grammars reduce batching efficiency in some engines.

Rule of thumb: expect 10–30% latency increase versus unconstrained generation for simple schemas. For complex nested schemas, profile before deploying — the alternative (retry loops on invalid JSON) often costs more in aggregate.

## Designing schemas for reliable extraction

Schema design affects both validity and quality:

```python
# Good: constrained enum prevents hallucinated categories
"intent": {"type": "string", "enum": ["refund", "support", "cancel"]}

# Good: description guides the model's semantic choice
"order_id": {"type": "string", "description": "Numeric order ID from the text"}

# Avoid: overly permissive schemas that don't constrain meaning
"data": {"type": "object"}  # model can put anything here
```

Keep schemas flat when possible. Deeply nested structures increase parser state complexity and give the model more room to produce technically valid but semantically empty output.

## Common production mistakes

Teams get serving structured output outlines wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving structured output outlines break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When serving structured output outlines misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Outlines library documentation](https://outlines-dev.github.io/outlines/)
- [vLLM guided decoding](https://docs.vllm.ai/en/latest/serving/openai_compatible_server.html#extra-parameters-for-guided-decoding)
- [llama.cpp grammar support](https://github.com/ggerganov/llama.cpp/blob/master/grammars/README.md)
- [OpenAI structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [JSON Schema specification](https://json-schema.org/draft/2020-12/json-schema-core)
