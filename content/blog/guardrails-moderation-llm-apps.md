---
title: "Guardrails and Moderation for LLM Applications"
slug: "guardrails-moderation-llm-apps"
description: "Practical LLM guardrails and content moderation for production apps: input filters, output validation, NeMo Guardrails patterns, and where rules beat models."
datePublished: "2026-02-14"
dateModified: "2026-02-14"
tags: ["LLM", "AI Safety", "Guardrails", "Moderation"]
keywords: "LLM guardrails, content moderation, AI safety, output validation"
faq:
  - q: "What is the difference between moderation and guardrails in LLM apps?"
    a: "Moderation typically classifies content as safe or unsafe — hate speech, sexual content, violence. Guardrails are broader: they enforce output format, block policy violations, prevent PII leakage, and constrain tool use. Moderation is one layer inside a guardrails stack."
  - q: "Should guardrails run before or after the LLM call?"
    a: "Both. Input guardrails filter or rewrite prompts before inference. Output guardrails validate responses before users or downstream systems see them. High-risk apps add a third check on tool arguments between planning and execution."
  - q: "Are LLM-based guardrails reliable enough for production?"
    a: "As a secondary check, yes. As the only control, no. Combine deterministic rules (regex, schema validation, allowlists) with classifier models. Rules catch known failures cheaply; models catch paraphrases and edge cases."
---

"Add guardrails" is the most vague ticket in AI engineering. Product wants brand-safe outputs. Security wants no PII in responses. Legal wants disclaimers on medical and financial answers. Engineering wants JSON that parses. Those are four different problems sharing one word.

A production guardrails stack is a **pipeline of checks with explicit failure modes** — block, rewrite, escalate to human, or fall back to a safe template. Not a single moderation API call you bolt on after the demo works.

## The three checkpoints

```
User input → [Input guardrails] → LLM → [Output guardrails] → User
                              ↘ Tool args → [Action guardrails] → Execute
```

| Checkpoint | Catches | Typical mechanisms |
| --- | --- | --- |
| Input | Jailbreaks, injection, abuse | Classifiers, rate limits, blocklists |
| Output | Policy violations, PII, bad JSON | Schema validation, DLP, moderation |
| Action | Dangerous tool calls | Allowlists, argument validators |

Skipping any leg leaves a hole. Input-only moderation does not stop the model from hallucinating a credit card number in the output. Output-only validation does not stop a user from injecting instructions that reach your tools.

## Input moderation: fast filters first

Run cheap checks before you spend tokens:

1. **Rate limiting and abuse signals** — per-user, per-IP, per-API key. Obvious, often forgotten.
2. **Blocklists and regex** — internal hostnames, competitor slurs your legal team maintains, known jailbreak prefixes.
3. **Classifier models** — OpenAI Moderation API, Azure AI Content Safety, Perspective API, or open models like Llama Guard 3.

```python
from openai import OpenAI
client = OpenAI()

def check_input(text: str) -> tuple[bool, str]:
    result = client.moderations.create(input=text)
    cats = result.results[0].categories
    if cats.hate or cats.sexual or cats.violence:
        return False, "content_policy_violation"
    return True, "ok"
```

Classifiers return probabilities, not truth. Set thresholds per category and **log borderline cases** for human review. A support bot can tolerate higher false-positive rates than a children's app.

For agent systems, also scan **retrieved context and tool outputs** before the next turn — indirect injection lives there. The input guardrail scope must include anything entering the context window, not just the user's latest message. See [prompt injection and agent security](https://blog.michaelsam94.com/prompt-injection-agent-security/) for harness patterns that complement moderation.

## Output validation: trust but verify

The model finished generating. Now enforce contracts:

### Structured output guardrails

If downstream code expects JSON, validate with JSON Schema before it touches business logic:

```python
import jsonschema

ORDER_SCHEMA = {
    "type": "object",
    "required": ["sku", "quantity"],
    "properties": {
        "sku": {"type": "string", "pattern": "^[A-Z0-9-]{4,20}$"},
        "quantity": {"type": "integer", "minimum": 1, "maximum": 99},
    },
    "additionalProperties": False,
}

def validate_order(raw: str) -> dict:
    data = json.loads(raw)  # catch parse errors
    jsonschema.validate(data, ORDER_SCHEMA)
    return data
```

OpenAI structured outputs with `strict: true`, Gemini `responseSchema`, and Anthropic tool use reduce parse failures at the source — but still validate server-side. Models drift across versions.

### Content policy on output

Run the same moderation classifiers on the **assistant response** before display. Add domain rules:

- **PII detection** — Microsoft Presidio, Google DLP API, or regex for emails, phone numbers, national IDs.
- **Financial/medical disclaimers** — if response matches regulated topics, append required text or refuse.
- **Citation requirements** — for RAG apps, reject answers where no retrieved chunk supports claims (LLM-as-judge or entailment model).

### Repair vs refuse

When validation fails, pick a policy:

| Failure | User-facing behavior |
| --- | --- |
| JSON syntax | One retry with repair prompt |
| Schema violation | Retry once, then safe error |
| Moderation hit | Refuse with generic message |
| PII detected | Redact and show, or refuse |

Infinite retry loops burn money and leak context. Cap at one repair attempt.

## Frameworks: NeMo Guardrails and Guardrails AI

[NVIDIA NeMo Guardrails](https://github.com/NVIDIA/NeMo-Guardrails) models guardrails as a dialog flow — Colang scripts define allowed paths, fact-checking rails, and topical boundaries. Good when you need **conversational policy** expressed declaratively and want to iterate without redeploying Python.

[Guardrails AI](https://github.com/guardrails-ai/guardrails) wraps validators (`.validate()`) around LLM calls with a hub of pre-built checks — `ValidJSON`, `ProfanityFree`, `ToxicLanguage`. Good for **output validation** in Python services with minimal boilerplate:

```python
from guardrails import Guard
from guardrails.hub import ToxicLanguage, ValidJSON

guard = Guard().use_many(ToxicLanguage(), ValidJSON())
result = guard(llm_api, prompt=user_prompt)
```

Neither replaces deterministic checks. Use them to orchestrate validators, not as magic safety dust.

## Where rules beat models

Models paraphrase; rules do not get tired:

- **Tool allowlists** — hardcoded per agent profile, not model discretion.
- **SQL allowlists** — parse AST, permit only SELECT on approved views.
- **Output length caps** — truncate before moderation if response exceeds N tokens.
- **Locale and age gates** — deterministic routing to stricter policies for minors.

On a robotics fleet dashboard, I blocked any tool argument containing `rm -`, `DROP`, or URLs outside our domain with a 0.2ms regex pass. No classifier required.

## Moderation for multilingual and regional apps

Serving Cairo, Gulf, and European users from one stack means **one global moderation model is insufficient**. Arabic dialect, code-switching, and cultural context produce false positives on English-centric classifiers.

Mitigations:

- Run eval sets in every supported language before launch.
- Tune thresholds per locale; log false positives by `Accept-Language`.
- Escalate borderline cases to human moderators with context, not binary blocks.

## Metrics that prove guardrails work

Track in production, not just in staging:

| Metric | Why |
| --- | --- |
| Block rate by category | Detect drift or attacks |
| False positive reports | User appeals, support tickets |
| Repair retry rate | Model format health |
| PII catch rate | DLP effectiveness |
| Time-to-detect new jailbreak | Red team cadence |

Run a monthly red-team pass against your stack. New jailbreaks spread on social media within days; your guardrails need a human update loop.

## Minimum viable guardrails stack

For a B2B SaaS assistant shipping in weeks, not months:

1. Input moderation API + rate limits
2. Output moderation + PII regex
3. JSON Schema validation on structured responses
4. Tool allowlist with argument validation
5. Logging and alerting on block spikes

Add Colang flows or custom classifiers when evals show systematic gaps — not before you have evals.

Guardrails are not a substitute for least-privilege architecture. They are the last line of defense when the model does something you did not intend. Build them as a pipeline, measure them like any other service, and prefer rules where rules suffice.

## Resources

- [OpenAI Moderation API Guide](https://platform.openai.com/docs/guides/moderation)
- [Azure AI Content Safety Documentation](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/)
- [NVIDIA NeMo Guardrails Documentation](https://docs.nvidia.com/nemo/guardrails/latest/)
- [Guardrails AI Documentation](https://www.guardrailsai.com/docs)
- [Google Cloud Sensitive Data Protection (DLP)](https://cloud.google.com/sensitive-data-protection/docs)
- [Microsoft Presidio — PII Detection](https://microsoft.github.io/presidio/)
- [Meta Llama Guard Model Card](https://github.com/meta-llama/PurpleLlama)
