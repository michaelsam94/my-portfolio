---
title: "Structured Outputs and Function Calling Done Right"
slug: "structured-outputs-function-calling"
description: "How to get reliable JSON from LLMs: structured outputs vs JSON mode vs function calling, schema design, validation, and the failure modes that bite in production."
datePublished: "2026-02-05"
dateModified: "2026-07-17"
tags: ["LLM", "Function Calling", "JSON Schema", "Backend"]
keywords: "structured outputs, JSON mode, function calling, tool calling, LLM structured data, JSON schema, constrained decoding"
faq:
  - q: "What is the difference between JSON mode and structured outputs?"
    a: "JSON mode only guarantees the model returns syntactically valid JSON — it can still invent fields or wrong types. Structured outputs enforce your exact JSON Schema via constrained decoding, so the shape is guaranteed to match. Prefer structured outputs when the provider supports them."
  - q: "Is function calling the same as structured outputs?"
    a: "They share the same schema machinery but differ in intent. Function calling asks the model to choose a tool and produce arguments for it; structured outputs ask the model to return data in a fixed shape as its final answer. Many providers implement both with the same JSON Schema constraint."
  - q: "Why does my LLM still return invalid data with a schema?"
    a: "Usually the schema is valid but semantically wrong — the model fills required fields with plausible-but-fabricated values, or enums are too loose. Constrained decoding guarantees shape, not truth, so you still need business-rule validation after parsing."
faqAnswers:
  - question: "When is structured outputs function calling the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for structured outputs function calling?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back structured outputs function calling safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Getting a language model to emit prose is easy. Getting it to emit the same shape of JSON on every call, so a downstream service can parse it without defensive try/catch spaghetti, is where most integrations quietly fall apart. Structured outputs and function calling exist to solve exactly this — and used correctly, they turn an LLM from a text generator into a dependable component in a typed system.

The short version: use **structured outputs** (schema-constrained decoding) when you want guaranteed-shape data back, use **function calling** when you want the model to pick a tool and produce its arguments, and never trust either without a validation layer that checks meaning, not just syntax. Everything below is about doing that well.

## Three mechanisms, in order of guarantee

There's a hierarchy here, and mixing them up is the root of a lot of flaky behavior.

- **Prompt-and-pray.** You ask for JSON in the prompt and parse whatever comes back. It works ~90% of the time, which is exactly bad enough to page you at 2am. Avoid in production.
- **JSON mode.** The provider guarantees *syntactically* valid JSON. No trailing commas, no markdown fences. But the keys, types, and required fields are still up to the model's goodwill.
- **Structured outputs / constrained decoding.** You supply a JSON Schema and the decoder is masked at each token step so only tokens that keep the output valid against the schema are allowed. The returned object is guaranteed to match the shape you asked for.

Function calling sits on top of the same schema mechanism: the tool's parameters *are* a JSON Schema, and the model's job is to emit arguments that satisfy it.

## Structured outputs in practice

Here's the pattern I reach for with the OpenAI SDK and a Pydantic model, which keeps the schema and the parsed type in one place:

```python
from pydantic import BaseModel, Field
from openai import OpenAI

class Invoice(BaseModel):
    vendor: str
    invoice_number: str
    total_cents: int = Field(description="total in integer cents, never a float")
    currency: str = Field(pattern="^[A-Z]{3}$")
    line_items: list[str]

client = OpenAI()
resp = client.chat.completions.parse(
    model="gpt-4o-2024-08-06",
    messages=[
        {"role": "system", "content": "Extract invoice fields from the document."},
        {"role": "user", "content": document_text},
    ],
    response_format=Invoice,
)
invoice = resp.choices[0].message.parsed  # a real Invoice instance
```

Because decoding is constrained to the schema, `invoice` is always a well-formed `Invoice`. What it is *not* guaranteed to be is correct — `total_cents` will be an integer, but it might be the wrong integer. Constrained decoding solves shape, not truth.

## Design schemas the model can actually fill

The biggest quality gains come from schema design, not model choice. A few rules that have saved me repeatedly:

**Use enums instead of free text wherever the value space is closed.** `"status": {"enum": ["paid", "unpaid", "overdue"]}` forces one of three answers; a free string invites "Paid (partially)" and other surprises.

**Represent money as integer cents, never floats.** Floats invite `19.99` becoming `19.990000001`, and worse, the model sometimes reasons better about integers.

**Make "unknown" a first-class value.** If a field might be absent from the source, give the model a way to say so — an optional field or an explicit `null` — otherwise it will hallucinate a plausible value to satisfy a `required` constraint. This single change killed most of the fabrication I saw in a document-extraction pipeline.

**Keep nesting shallow.** Deeply nested schemas increase the chance the model loses track and are harder to validate. Flatten where you can.

**Add `description` fields.** The schema descriptions are part of the prompt. Use them to state units, formats, and edge-case handling ("ISO 8601 dates", "empty array if none found").

## Function calling: let the model act, you stay in control

Function calling is how an agent decides *what to do*. You expose a set of tools; the model returns which tool to call and with what arguments; your code executes it and feeds the result back. Crucially, the model does not run anything — it only proposes.

```python
tools = [{
    "type": "function",
    "function": {
        "name": "get_charger_status",
        "description": "Return live status for one EV charger by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "charger_id": {"type": "string"},
                "include_meter": {"type": "boolean", "default": False},
            },
            "required": ["charger_id"],
            "additionalProperties": False,
        },
    },
}]
```

Two guardrails matter here. Set `additionalProperties: false` so the model can't smuggle in extra arguments your handler doesn't expect. And treat every tool call as untrusted input: validate `charger_id` against your real ID format and authorize it against the calling user before executing. The model choosing a tool is a *suggestion*, and a manipulated prompt can produce hostile suggestions — see [prompt injection and agent security](https://blog.michaelsam94.com/prompt-injection-agent-security/) for why that boundary is non-negotiable.

## The validation layer you still need

Constrained decoding gives you a well-typed object. Your business rules give you a *correct* one. Between parse and use, run a validation pass:

1. **Semantic checks.** Does `total_cents` equal the sum of line items? Is the date in a plausible range? Does the referenced ID exist?
2. **Repair loop, bounded.** On failure, send the error back to the model once or twice ("total didn't match line items, recompute") rather than retrying blindly. Cap the loop — infinite repair attempts are a cost and latency sink.
3. **Fallback.** If repair fails, route to a human or a deterministic extractor rather than shipping bad data downstream.

This mirrors how you'd treat any untrusted parser output. The LLM is a probabilistic component wrapped in a deterministic contract.

## Where this fits

Structured outputs are the backbone of reliable agents: they make tool arguments parseable, make responses composable, and let you plug an LLM into a typed pipeline without turning every call site into a string-parsing minefield. Pair them with good [LLM observability](https://blog.michaelsam94.com/llm-observability-opentelemetry-genai/) so you can see when schemas drift or validation failures spike, and with an eval suite so a prompt tweak doesn't silently break extraction on your long tail of documents.

Done right, "the model returns JSON" stops being a source of incidents and becomes the boring, reliable interface it should be.

## Schema validation loop

Validate tool JSON against JSON Schema before execution — models invent enum values. One retry with schema error appended to tool message; fail closed to user on second miss. Log `tool_parse_success` separately from chat latency SLO — parse failures clustered after model swap we missed in canary.

## Schema validation loop

Validate tool JSON against JSON Schema before execution — models invent enum values. One retry with schema error appended to tool message; fail closed to user on second miss. Log `tool_parse_success` separately from chat latency SLO — parse failures clustered after model swap we missed in canary.

## Field metrics and rollback

Capture baseline p75 error rate and latency on tier-1 routes before merge. Compare seven days post-deploy sliced by mobile and region. Document rollback in PR and runbook.

## Resources

- [OpenAI — Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI — Function calling](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic — Tool use](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [JSON Schema — Official specification](https://json-schema.org/)
- [Pydantic documentation](https://docs.pydantic.dev/latest/)
- [Google — Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)

## Failure modes specific to structured outputs function calling

Operating structured outputs function calling well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For structured outputs function calling:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified structured outputs function calling stops moving — sunsetting is a feature.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Metrics and alarms for structured outputs function calling

Reviewers should challenge assumptions encoded in structured outputs function calling: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for structured outputs function calling: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for structured outputs function calling: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for structured outputs function calling: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Anti-patterns unique to structured outputs function calling

Roll out structured outputs function calling behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for structured outputs function calling

Detail 1 (626): for structured outputs function calling, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for structured outputs function calling becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break structured outputs function calling, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about structured outputs function calling: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing structured outputs function calling

Detail 2 (495): for structured outputs function calling, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing structured outputs function calling becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break structured outputs function calling, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about structured outputs function calling: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.