---
title: "Output Filtering and Safe Completions"
slug: "llm-safety-output-filtering"
description: "Filter LLM outputs before they reach users: moderation classifiers, regex and schema validation, streaming interruption, policy engines, and safe completion patterns for production."
datePublished: "2025-03-09"
dateModified: "2026-07-17"
tags:
keywords: "LLM output filtering, safe completions AI, output moderation LLM, streaming content filter, LLM response validation"
faq:
  - q: "Should output filtering happen before or after streaming to the user?"
    a: "Ideally before — buffer initial tokens and run moderation on chunks, or use provider streaming moderation hooks. If you stream unfiltered for latency, implement mid-stream cutoff when a classifier flags content, replace remaining tokens with a safe message, and log the incident. Never stream medical, legal, or financial advice without domain-specific output checks."
  - q: "Provider moderation API vs custom output filters — do I need both?"
    a: "Layer them. Provider APIs catch broad harm categories (violence, hate, sexual content) with maintained models. Custom filters enforce business rules: no competitor names, required disclaimers, JSON schema conformance, PII patterns. Provider-only misses domain policy; custom-only misses evolving universal harm categories."
  - q: "How do I filter structured LLM outputs like JSON?"
    a: "Validate against a strict schema (JSON Schema, Pydantic) after generation — reject and retry on failure. Strip markdown fences before parsing. For tool arguments, validate types, ranges, and allowlists before execution. Structured output mode from providers reduces parse failures but still requires semantic validation."
---
The coding assistant streamed a complete AWS access key into the chat bubble before the moderation job running on the finished response could flag it. Output filtering that runs only on `completion.done` is too late for streaming UIs — users screenshot tokens in seconds. Safe completions require treating model output as untrusted data that passes through validation, moderation, and policy gates before display, tool execution, or storage — regardless of how confident the model sounded generating it.

## Output filtering pipeline

```
Model tokens → Chunk buffer → Moderation → Schema validate → Policy engine → User / Tool
                    ↓ fail              ↓ fail           ↓ fail
                 Block/retry        Block/retry      Block/replace
```

Each stage can **block** (discard), **retry** (regenerate with stricter prompt), or **replace** (safe canned response).

## Moderation classifiers

Run provider or self-hosted classifiers on output text:

```python
async def moderate_output(text: str) -> ModerationResult:
    resp = await openai_client.moderations.create(input=text)
    flagged = resp.results[0].flagged
    categories = {
        k: v for k, v in resp.results[0].categories.model_dump().items() if v
    }
    return ModerationResult(flagged=flagged, categories=categories)

async def safe_complete(prompt: str, max_retries: int = 2) -> str:
    for attempt in range(max_retries + 1):
        raw = await llm.generate(prompt)
        mod = await moderate_output(raw)
        if not mod.flagged:
            return raw
        prompt = append_restriction(prompt, mod.categories)
    return FALLBACK_MESSAGE
```

Category-specific retries work better than generic "try again" — "Remove violent content and answer factually" beats blank regeneration.

## Streaming interruption

For SSE streaming, accumulate windows and check incrementally:

```python
BUFFER_WINDOW = 200  # characters
blocked = False

async for chunk in llm.stream(prompt):
    if blocked:
        continue
    buffer += chunk
    if len(buffer) >= BUFFER_WINDOW:
        if await moderate_output(buffer).flagged:
            blocked = True
            yield "\n\n[Response removed: policy violation]"
            audit.log("stream_blocked", buffer_preview=buffer[:100])
            break
        yield buffer
        buffer = ""
if not blocked and buffer:
    if not (await moderate_output(buffer)).flagged:
        yield buffer
```

Trade latency for safety — larger windows catch more context but delay first token moderation.

## PII and secret detection

Regex and NER models catch emails, phone numbers, SSN patterns, credit cards, and API keys:

```python
PATTERNS = [
    (r"sk-[a-zA-Z0-9]{20,}", "openai_key"),
    (r"AKIA[0-9A-Z]{16}", "aws_access_key"),
    (r"\b\d{3}-\d{2}-\d{4}\b", "ssn"),
]

def redact_secrets(text: str) -> tuple[str, list[str]]:
    findings = []
    for pattern, kind in PATTERNS:
        if re.search(pattern, text):
            findings.append(kind)
            text = re.sub(pattern, f"[REDACTED_{kind}]", text)
    return text, findings
```

Block and alert on secret detection — redaction in user-facing chat may still expose that a secret existed. For internal logs, redact before write.

## Schema validation for structured output

```python
from pydantic import BaseModel, Field

class ProductSummary(BaseModel):
    title: str = Field(max_length=100)
    price_usd: float = Field(ge=0, le=1_000_000)
    category: Literal["electronics", "books", "home"]

def parse_and_validate(raw: str) -> ProductSummary:
    data = json.loads(strip_markdown_fence(raw))
    return ProductSummary.model_validate(data)
```

On validation failure, retry with "Return valid JSON matching schema" — cap retries to avoid cost loops.

## Policy engine for business rules

Beyond harm moderation, enforce product policy:

```python
def policy_check(text: str, context: RequestContext) -> PolicyResult:
    if context.brand == "acme" and "competitor_x" in text.lower():
        return PolicyResult(block=True, reason="competitor_mention")
    if context.domain == "medical" and not text.startswith(MEDICAL_DISCLAIMER):
        return PolicyResult(block=True, reason="missing_disclaimer")
    return PolicyResult(block=False)
```

Centralize rules in config — legal should update disclaimers without redeploying model weights.

## Safe completion patterns

**Constrained decoding** — use grammar or JSON mode so output space is limited.

**Refusal templates** — consistent, non-jailbreakable messages for blocked categories.

**Human escalation** — route edge cases to review queue instead of guessing.

**Caching safe responses** — FAQ answers pre-approved, model only for novel queries.

## Tool-call output filtering

When models invoke tools, filter **arguments** before execution, not just user-visible text:

```python
def validate_tool_call(name: str, args: dict, context: RequestContext) -> None:
    if name == "send_email":
        if args.get("to") not in context.allowed_recipients:
            raise ToolCallBlocked("recipient_not_allowed")
        if contains_html_script(args.get("body", "")):
            raise ToolCallBlocked("unsafe_html")
    if name == "run_sql" and not is_read_only(args.get("query", "")):
        raise ToolCallBlocked("write_sql_forbidden")
```

A jailbroken model that streams safe-looking text can still emit malicious tool payloads. Treat tool JSON like user input — schema validate, allowlist destinations, and cap string lengths.

For multi-step agent loops, re-run output filters after **each** tool result before feeding it back into context. Tool returns may contain injected instructions from third-party APIs.

## Coordinating filters with human review

Not every block should be a dead end. Route medium-severity flags to a review queue with the redacted draft attached:

```python
if mod.flagged and mod.max_severity == "medium":
    review_id = queue.enqueue(response=redacted, categories=mod.categories)
    return f"Your response is pending review (ref {review_id})."
```

Humans approve, edit, or reject within SLA. Sampling low-severity passes catches false negatives without reviewing every completion.

## Metrics and regression testing

Track:

- `output_filter.block_rate` by category
- `output_filter.retry_count` before success
- `stream.mid_block_rate`
- User override / report rate post-filter

Maintain golden-set evaluations — known harmful prompts must produce blocked or safe outputs after model updates.

## Resources

- [OpenAI Moderation API](https://platform.openai.com/docs/guides/moderation)
- [NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails)
- [Microsoft Azure Content Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/)
- [JSON Schema specification](https://json-schema.org/)
- [OWASP LLM Top 10 — Improper Output Handling](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

## Production notes for LLM stacks

When `llm-safety-output-filtering` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `output filtering and safe completions` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
