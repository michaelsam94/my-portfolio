---
title: "Prompt Engineering Anti-Patterns"
slug: "prompt-engineering-anti-patterns"
description: "Avoid common prompt engineering mistakes: vague instructions, conflicting constraints, context stuffing, and patterns that cause hallucination and format drift."
datePublished: "2026-04-23"
dateModified: "2026-04-23"
tags: ["AI", "LLM", "Prompt Engineering", "Best Practices"]
keywords: "prompt engineering anti-patterns, LLM prompt mistakes, prompt hallucination, prompt design failures, LLM instruction tuning"
faq:
  - q: "What is the most common prompt engineering mistake?"
    a: "Vague success criteria — 'write good code' or 'summarize briefly' without defining format, length, audience, or constraints. Models fill gaps with assumptions that rarely match your intent. Specificity beats cleverness."
  - q: "Why does adding more context sometimes make LLM output worse?"
    a: "Context stuffing buries the actual instruction under irrelevant documents, duplicates, or contradictory examples. Models attend unevenly to long prompts — critical constraints in the middle get lost. Put instructions first and last; trim context to what's necessary."
  - q: "How do conflicting instructions show up in prompts?"
    a: " 'Be concise' and 'include every detail,' or 'never guess' and 'always answer.' Models resolve conflicts unpredictably — often by ignoring one constraint. Audit prompts for contradictions and prioritize explicitly: 'If X conflicts with Y, prefer X.'"
---

I've debugged more bad prompts than bad models. The ticket said "GPT-4 got worse." The prompt had grown to 4,000 tokens of pasted wiki pages, three conflicting tone guidelines, and "respond in JSON" followed by "use natural prose." Strip the anti-patterns, same model, same task — accuracy jumped from unusable to shippable.

## Anti-pattern: the kitchen sink prompt

Everything in one message: role, examples, data, format, edge cases, company history.

```
You are an expert... [500 words persona]
Here are 40 pages of docs... [3000 tokens]
Be brief but thorough...
Return markdown except when JSON...
```

**Fix:** structure with clear sections; trim context to task-relevant chunks (RAG with top-k, not dump entire KB); use system message for stable rules, user message for task-specific input.

```
## Task
Extract vendor name and total from the invoice below.

## Output format
JSON: {"vendor": string, "total_cents": integer}

## Rules
- If field missing, use null — do not invent values.

## Invoice
{truncated_text}
```

## Anti-pattern: negative-only constraints

"Don't mention competitors. Don't use jargon. Don't be verbose. Don't hallucinate."

Models weakly comply with negation. Endless don'ts without positive direction.

**Fix:** say what to do:
- "Compare only to generic alternatives, not named vendors"
- "Use plain language suitable for non-technical readers"
- "Answer in 3–5 bullet points"
- "If uncertain, state what information is missing"

## Anti-pattern: format schizophrenia

"Return valid JSON" in system prompt, then "explain your reasoning in paragraphs" in user message.

**Fix:** pick one primary output contract. Reasoning in chain-of-thought can be internal (hidden) or in a separate field:

```json
{"reasoning": "...", "answer": {"vendor": "Acme", "total_cents": 4200}}
```

Validate with JSON schema / structured outputs API where available.

## Anti-pattern: few-shot examples that contradict rules

Examples show invented data when rule says "never invent." Or examples use different JSON keys than spec.

**Fix:** examples are training signal — align exactly with production rules. Three consistent examples beat ten messy ones. Remove outdated examples when schema changes.

## Anti-pattern: persona theater without task clarity

"You are a world-class Nobel physicist poet who..." — 200 words of character, one line of actual task.

Persona helps tone and domain vocabulary; it doesn't replace task specification.

**Fix:** one sentence persona max unless voice is the product. Spend tokens on input/output spec.

## Anti-pattern: asking the model to verify without tools

"Double-check all facts before answering" — models confabulate verification.

**Fix:** retrieval, calculator, code execution, or human review for factual claims. Prompt: "Use only provided sources; cite paragraph IDs."

## Anti-pattern: temperature misuse

Temperature 0.9 for structured extraction. Temperature 0 for creative marketing copy that sounds robotic.

**Fix:** low temperature (0–0.3) for deterministic formats; moderate (0.5–0.7) for creative tasks; adjust after fixing prompt structure, not before.

## Anti-pattern: no failure mode

Prompt assumes happy path — malformed input, empty context, non-English, adversarial injection.

**Fix:** explicit else branches:

```
If the document is not an invoice, respond: {"error": "not_an_invoice"}
If text is unreadable, respond: {"error": "ocr_failed"}
```

## Eval before iterate

Build 20–50 test cases with expected outputs. Change one prompt element at a time. Track pass rate — vibe-based iteration wastes time.

Anti-patterns show up as high variance across eval set — same prompt, wildly different formats on case 7 and case 12.

## Version control for prompts

Store prompts in Git with semantic versioning. Link production prompt version to eval scores — rollback prompt like rollback code when metrics regress. Diff prompts in PR review like application logic.

## Operational notes

Run red-team prompts against production system prompts monthly — injection attempts, instruction override, data exfiltration phrasing. Anti-patterns in user input mirror anti-patterns in your own prompt design.

Include prompt regression tests in release checklist when model version upgrades — new models break old prompts silently; eval suite catches format drift before deploy.

Maintain a shared internal gallery of failed prompts with postmortem notes — new team members learn faster from documented anti-patterns than from generic best-practice slides.

Pair prompt changes with eval PR comments showing score delta — reviewers approve prompt tweaks with same rigor as code when metrics move visibly.

Review prompts when upgrading model versions — behavior shifts without code changes.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get anti patterns wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of anti patterns fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When anti patterns misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenAI prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic prompt design documentation](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Simon Willison on prompt injection](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)
- [LMSYS prompt library patterns](https://lmsys.org/)
- [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
