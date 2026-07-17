---
title: "Building a Content Moderation Pipeline"
slug: "llm-safety-content-moderation-pipeline"
description: "Build a content moderation pipeline for LLM apps: input filtering, provider moderation APIs, custom classifiers, output scanning, and layered defense that catches policy violations before users see them."
datePublished: "2025-01-08"
dateModified: "2026-07-17"
tags:
keywords: "LLM content moderation, AI safety pipeline, OpenAI moderation API, input output filtering, content policy LLM"
faq:
  - q: "Should I moderate LLM inputs, outputs, or both?"
    a: "Both. Input moderation blocks harmful requests before they reach the model (jailbreaks, CSAM queries, abuse). Output moderation catches policy violations the model produces despite instructions (harmful content, PII leaks, off-brand responses). Input-only moderation misses model-generated harm; output-only wastes compute on requests you should reject upfront."
  - q: "Provider moderation API vs custom classifier — which do I need?"
    a: "Start with provider APIs (OpenAI Moderation, Anthropic safety classifiers) — free or cheap, maintained, broad coverage. Add custom classifiers for domain-specific policies (competitor mentions, medical advice, financial recommendations) that generic models don't cover. Layer both — provider catches universal harm, custom catches business rules."
  - q: "What should happen when moderation flags content?"
    a: "Tier by severity. Block and log critical violations (CSAM, violence, hate). Refuse with generic message for high-severity. Rewrite or redact for medium (PII in output). Log-only for low-severity borderline cases with human review sampling. Never silently pass flagged critical content."
---
A user pasted content into your AI writing assistant that shouldn't have reached the model. The model complied. The output violated your terms of service and appeared on screen before any human saw it. Content moderation for LLM apps isn't one API call — it's a pipeline that checks input before inference, output before display, and logs everything for review and compliance.

## Pipeline architecture

```
User input
    ↓
[Input moderation] → BLOCK → generic refusal
    ↓ pass
[LLM generation]
    ↓
[Output moderation] → BLOCK/REDACT → safe response
    ↓ pass
User sees response
    ↓
[Async audit log + sampling for human review]
```

Each stage is independent — a failure in one doesn't skip the others.

## Input moderation

```python
async def moderate_input(text: str, tenant_id: str) -> ModerationResult:
    # Layer 1: Provider API (fast, broad)
    provider_result = await openai.moderations.create(input=text)
    if provider_result.results[0].flagged:
        return ModerationResult(action="block", reason="provider_flag", details=provider_result)

    # Layer 2: Custom business rules
    custom = await custom_classifier.check(text, tenant_id)
    if custom.violation:
        return ModerationResult(action="block", reason=custom.category)

    # Layer 3: Prompt injection heuristics
    if injection_score(text) > INJECTION_THRESHOLD:
        return ModerationResult(action="block", reason="injection_attempt")

    return ModerationResult(action="pass")
```

Run input moderation in parallel with auth/rate limiting — don't add sequential latency.

## Output moderation

Model outputs need the same scrutiny:

```python
async def moderate_output(text: str, context: RequestContext) -> ModerationResult:
    result = await openai.moderations.create(input=text)
    if result.results[0].flagged:
        categories = result.results[0].categories
        if categories.sexual_minors or categories.self_harm:
            return ModerationResult(action="block", log_level="critical")
        return ModerationResult(action="block", log_level="high")

    # Custom: no competitor mentions
    if context.tenant_policy.no_competitors:
        if mentions_competitor(text):
            return ModerationResult(action="redact", redact_patterns=COMPETITOR_NAMES)

    # PII scan
    pii = detect_pii(text)
    if pii:
        return ModerationResult(action="redact", redact_spans=pii)

    return ModerationResult(action="pass")
```

## Custom classifiers

Train or prompt classifiers for domain rules:

```python
DOMAIN_MODERATION_PROMPT = """
Classify if this text violates any policy:
- MEDICAL_ADVICE: specific medical recommendations
- FINANCIAL_ADVICE: investment recommendations without disclaimer
- COMPETITOR_MENTION: names competing products
- OFF_BRAND: tone inconsistent with professional support

Return JSON: {"violations": [...], "severity": "none|low|medium|high|critical"}
"""
```

Use a cheap, fast model (GPT-4o-mini). Cache results for identical inputs.

## Action matrix

| Severity | Input action | Output action | Logging |
|----------|-------------|---------------|---------|
| Critical | Block + alert | Block + alert | Full audit, legal review |
| High | Block | Block + generic response | Full audit |
| Medium | Warn + proceed | Redact + deliver | Standard log |
| Low | Log | Log | Sampled human review |

```python
REFUSAL_MESSAGES = {
    "default": "I can't help with that request.",
    "injection": "I can't process that message. Please rephrase your question.",
    # Never explain WHY in detail — aids adversarial iteration
}
```

## Latency budget

Moderation adds latency. Budget:

| Stage | Target latency |
|-------|---------------|
| Provider moderation API | 100–300ms |
| Custom classifier | 200–500ms |
| PII regex scan | <10ms |
| Total pipeline overhead | <500ms |

Run provider and custom checks in parallel:

```python
provider, custom = await asyncio.gather(
    provider_moderate(text),
    custom_moderate(text),
)
```

## Human review queue

Sample flagged and borderline content:

```python
async def post_moderation_audit(result: ModerationResult, context: RequestContext):
    await audit_log.write(result, context)
    if result.severity in ("medium", "low") and random.random() < 0.05:
        await review_queue.add(result, context, priority=result.severity)
    if result.severity == "critical":
        await alert_oncall(result, context)
```

Reviewers need input, output, moderation scores, and tenant context.

## Compliance and retention

- Retain moderation logs per regulatory requirements (often 1–7 years for financial/health)
- Support legal hold on flagged content
- Document moderation policies for transparency reports
- Regional differences — EU AI Act, UK Online Safety Act may require specific measures

## Multi-layer moderation architecture

Production moderation stacks multiple layers — no single point of failure:

```
Layer 1: Input keyword blocklist (< 1ms, free)
Layer 2: Provider moderation API (~100ms, OpenAI/Anthropic)
Layer 3: Custom classifier (~50ms, domain-specific)
Layer 4: LLM output guardrail (~500ms, high-risk paths only)
Layer 5: Human review queue (async, sampled)
```

```python
async def moderate_request(input_text: str, context: RequestContext) -> ModerationResult:
    # Layer 1: instant blocklist
    if blocklist.match(input_text):
        return ModerationResult(action="block", reason="blocklist", layer=1)

    # Layer 2: provider API
    provider_result = await openai_moderation(input_text)
    if provider_result.flagged:
        return ModerationResult(action="block", reason=provider_result.categories, layer=2)

    # Layer 3: custom classifier for domain-specific harm
    custom_score = await domain_classifier(input_text, context.tenant_id)
    if custom_score > 0.9:
        return ModerationResult(action="block", reason="domain_classifier", layer=3)

    return ModerationResult(action="allow")
```

Early layers are cheap and fast — only escalate to expensive layers on borderline cases.

## Output moderation for generated content

Input moderation isn't enough — filter LLM outputs too:

```python
async def moderate_output(response: str, context: RequestContext) -> str:
    result = await openai_moderation(response)
    if result.flagged:
        await audit_log.write("output_blocked", context, result.categories)
        return "I can't provide that response. Please rephrase your request."
    return response
```

Prompt injection can cause model to generate harmful content even from benign input. Always moderate output for user-facing features.

## Moderation metrics and transparency

Track and report moderation activity:

```python
MODERATION_METRICS = [
    "moderation.input_blocked_rate",
    "moderation.output_blocked_rate",
    "moderation.layer_1_blocklist_hits",
    "moderation.human_review_queue_depth",
    "moderation.false_positive_rate",  # from human review feedback
]
```

Publish transparency reports: total requests, blocked rate, top block categories, human review overturn rate. Required for EU AI Act high-risk system compliance.

## Failure modes

- **Input moderation only** — prompt injection bypasses input filter via output
- **Single layer reliance** — provider API outage blocks all requests
- **No false positive tracking** — over-blocking erodes user trust silently
- **Moderation logs without retention policy** — compliance audit failure
- **Same threshold for all content types** — customer support vs creative writing need different policies

## Production checklist

- Multi-layer moderation: blocklist → provider API → custom classifier
- Output moderation on all user-facing LLM responses
- False positive rate tracked via human review feedback
- Moderation logs retained per regulatory requirement (1–7 years)
- Transparency report published quarterly
- Per-tenant/content-type threshold configuration

## Resources

- [OpenAI Moderation API](https://platform.openai.com/docs/guides/moderation)
- [Anthropic responsible scaling policy](https://www.anthropic.com/rsp-updates)
- [Perspective API (Jigsaw/Google)](https://perspectiveapi.com/)
- [OWASP LLM Top 10](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Meta Llama Guard safety model](https://huggingface.co/meta-llama/LlamaGuard-7b)

## Production notes for LLM stacks

When `llm-safety-content-moderation-pipeline` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `building a content moderation pipeline` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
