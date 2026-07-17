---
title: "Prompt Engineering Anti-Patterns"
slug: "prompt-engineering-anti-patterns"
description: "Avoid common prompt engineering mistakes: vague instructions, conflicting constraints, context stuffing, and patterns that cause hallucination and format drift."
datePublished: "2026-04-23"
dateModified: "2026-07-17"
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


## Lint prompts in CI like code

Static checks catch recurring anti-patterns: contradictory pairs (`concise` + `comprehensive`), JSON output paired with `write prose`, timestamps in first 200 tokens, more than three `don't` without matching `do`. Fail PRs that bump prompt version without eval score attachment — same rigor as code coverage on critical paths.

## Slice evals by failure mode

Report kitchen-sink, format-drift, and hallucination rates separately on your golden set. Aggregate pass rate hides opposing movements — format improves while factual errors rise when someone adds persuasive persona text without retrieval grounding.

## Prompt component ownership

Assign owners per section: legal owns compliance block, eng owns schema block, design owns tone — PRs touching another team's block need their review. Orphan prompts accumulate contradictions when three teams edit one string without coordination.

## Regression golden files

Store expected JSON outputs for 30 frozen inputs per prompt version — CI diff on model upgrade flags drift before production deploy. Frozen inputs include edge cases from past incidents (empty PDF, unicode names, adversarial spacing).

## Production rollout notes

Schedule quarterly prompt audits on production templates — product marketing edits accumulate in shared system strings. Diff audit against eval golden set; any prompt change without eval attachment gets reverted in audit. Anti-patterns often return through copy-paste from old Confluence pages, not through intentional model changes.
## Anti-pattern catalog in wiki

Maintain internal wiki of named anti-patterns with before/after prompt pairs — kitchen sink Q3 2025, JSON prose conflict incident #4412. New engineers fix faster when examples link to real postmortems not abstract advice. Review catalog in onboarding week one.

## Model family specific anti-patterns

Reasoning models may over-elaborate despite concise instructions — anti-pattern is stacking verbose persona on top of model that already expands chain-of-thought. Eval verbosity separately from accuracy when upgrading model tier.

## Closing operational guidance

Include negative examples in few-shot sparingly — one bad example teaches more than three good if labeled DO NOT; unlabeled bad examples in prompt teach the model the wrong pattern. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away.

## Resources

- [OpenAI prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Anthropic prompt design documentation](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- [Simon Willison on prompt injection](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)
- [LMSYS prompt library patterns](https://lmsys.org/)
- [OpenAI structured outputs](https://platform.openai.com/docs/guides/structured-outputs)
