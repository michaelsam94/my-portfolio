---
title: "Prompt Decomposition Techniques"
slug: "prompt-engineering-decomposition"
description: "Break complex LLM tasks into prompt chains: decomposition patterns, intermediate validation, map-reduce summarization, and when single-shot prompts fail."
datePublished: "2026-04-27"
dateModified: "2026-07-17"
tags: ["AI", "LLM", "Prompt Engineering", "Architecture"]
keywords: "prompt decomposition, LLM chain of prompts, map reduce LLM, task decomposition AI, multi-step prompting"
faq:
  - q: "When should you decompose a task into multiple LLM calls?"
    a: "When single-shot accuracy drops on complex multi-step reasoning, when output exceeds context limits, when different steps need different models or tools, or when intermediate results must be validated before proceeding. Legal doc analysis, code migration, and long report generation commonly benefit."
  - q: "What is map-reduce for LLM prompts?"
    a: "Map: process chunks independently with the same sub-prompt. Reduce: combine chunk outputs in a final synthesis call. Handles documents longer than context window and parallelizes work — at the cost of multiple API calls and potential coherence loss at chunk boundaries."
  - q: "How do you prevent error propagation in prompt chains?"
    a: "Validate intermediate outputs with schemas, sanity checks, or smaller specialist prompts before passing forward. Fail fast on malformed steps; don't let hallucinated step-1 output poison step-3. Log intermediates for debugging."
---

A single prompt asked the model to read a 40-page contract, list obligations, rate risk, and draft a summary email. It hallucinated a termination clause and sounded confident doing it. Split into four prompts — extract clauses, classify risk per clause, aggregate scores, draft email from structured JSON — error rate dropped sharply. Same model. Better decomposition.

## Single-shot limits

Models struggle when tasks combine:
- Long input consumption
- Multi-step reasoning
- Strict structured output
- Domain tool use

Decomposition trades latency and cost for accuracy and debuggability.

## Pattern: sequential chain

```
Input ──► Prompt A (extract) ──► JSON ──► Prompt B (analyze) ──► Prompt C (format)
```

Example — invoice processing:

```python
# Step 1: Extract
extracted = llm.call(
    system="Extract fields as JSON. Use null for missing.",
    user=f"Invoice text:\n{ocr_text}",
    response_format=InvoiceSchema,
)

# Step 2: Validate business rules (code, not LLM)
if extracted.total_cents and extracted.line_items:
    assert sum(item.amount for item in extracted.line_items) == extracted.total_cents

# Step 3: Summarize for human
summary = llm.call(
    system="Write 2-sentence AP summary from structured data only.",
    user=json.dumps(extracted.model_dump()),
)
```

Step 2 catches LLM math errors before they reach finance.

## Pattern: map-reduce for long documents

```python
chunks = split_text(contract, max_tokens=3000, overlap=200)

# Map
partial_summaries = [
    llm.call(f"List obligations in this section only:\n{chunk}")
    for chunk in chunks
]

# Reduce
final = llm.call(
    f"Deduplicate and merge these obligation lists:\n{partial_summaries}"
)
```

Overlap reduces boundary misses — clause split across chunks appears in both.

For extraction, map step returns structured JSON; reduce merges with dedup key on clause_id.

## Pattern: router + specialists

```python
intent = llm.call(
    "Classify: billing | technical | legal. One word only.",
    user=ticket_text,
)

handlers = {
    "billing": billing_prompt,
    "technical": technical_prompt,
    "legal": legal_prompt,
}
response = handlers[intent.strip().lower()].call(user=ticket_text)
```

Cheap fast model for routing; capable model for specialist step.

## Pattern: generator + critic

```python
draft = llm.call("Draft answer to customer question", user=question)
critique = llm.call(
    "List factual errors or unsupported claims in the draft. JSON array.",
    user=draft,
)
if json.loads(critique):
    draft = llm.call("Revise draft fixing these issues", user=f"{draft}\n\nIssues:{critique}")
```

Critic catches hallucinations before user sees output — not foolproof, measurably helpful.

## Intermediate representation matters

Pass JSON between steps, not prose. Prose accumulates ambiguity:

```
Bad chain:  summary paragraph → another summary → email
Good chain:  structured facts → validated schema → email template fill
```

Pydantic / Zod validation between steps:

```python
try:
    data = InvoiceSchema.model_validate_json(raw)
except ValidationError:
    data = llm.call("Fix JSON to match schema", ...)  # one retry max
```

## Cost and latency tradeoffs

| Approach | Calls | Best when |
|----------|-------|-----------|
| Single-shot | 1 | Simple, short tasks |
| Chain | 2–5 | Structured pipelines |
| Map-reduce | N+1 | Long input |
| Parallel map | N parallel + 1 | Latency-sensitive long docs |

Parallelize map steps with asyncio/gather — wall clock equals slowest chunk plus reduce.

## When not to decompose

- Task is genuinely atomic ("translate this sentence")
- Added steps amplify inconsistency (creative writing tone drift)
- Latency budget sub-second — chain won't fit
- Intermediate data is sensitive — more exposure surfaces in logs

Start monolithic; decompose when eval shows systematic failure modes on compound steps.

## Observability across chains

Log each chain step's input hash, output summary, latency, and token count. When step 3 fails, replay steps 1-2 from logs without re-running expensive retrieval. Trace IDs tie multi-step calls together in OpenTelemetry.

## Operational notes

Cap retry count per chain step — infinite "fix your JSON" loops burn budget. After two validation failures, escalate to human or return structured error to caller with partial progress attached.

Document chain DAG in architecture diagram for complex pipelines — onboarding engineers fix step 4 faster when steps 1-3 inputs are visible without reading entire codebase.

Set per-chain token budget ceiling in orchestrator — decomposition without budget caps allows runaway map steps on large documents that exhaust daily API quota in one user request.

Prefer idempotent chain steps where possible — retrying failed step 3 should not duplicate side effects from step 2 when orchestrator replays partial chains.

## Decomposition pattern

Break complex tasks into ordered subtasks in the prompt:

```
Step 1: Extract entities from user message
Step 2: Classify intent
Step 3: Select tool
Step 4: Execute and synthesize
```

Or use explicit JSON schema output for step 1, feed to step 2 in separate LLM call — more reliable than single-shot for compound requests.


## DAG documentation for onboarding

Draw the chain as a DAG in your repo: nodes are steps, edges carry schema names (`InvoiceJSON → SummaryText`). New engineers fix step 4 faster when they see which upstream schema changed. Include expected p95 latency and token budget per node — decomposition without budgets allows runaway map fan-out on large PDFs.

## Partial chain replay after failures

Persist intermediate JSON after each validated step. When step 4 fails, replay from step 3 output without re-running expensive step 1 OCR+extract. Idempotent step keys (`doc_hash + step_id`) prevent duplicate side effects when orchestrators retry.

## Fan-out limits on map steps

Cap map parallelism at 10 concurrent chunk calls — 200-chunk document with unbounded asyncio.gather tripped provider rate limits and cost alarms. Queue map work with semaphore; surface progress for long docs.

## Chain versioning

Tag each step output with `chain_version` and `step_schema_version` — replay debugging needs to know if step 2 failed because step 1 used deprecated schema from last week's deploy.

## Production rollout notes

Document expected token budget per chain in runbook — finance approval for new document types requires cost estimate from pilot chain trace. A single unbounded map over 500-page PDF can exceed daily API quota; decomposition without budgets is an ops incident waiting for first enterprise upload.
## Step timeout budgets

Each chain step gets max wall clock — step 2 killed after 15s triggers fallback response, not infinite hang. Orchestrator records which step timed out for ops dashboard. Long-running map steps need per-chunk timeout distinct from reduce step timeout.

## Deterministic steps outside LLM

Move regex validation, checksum verification, and date parsing to code between LLM steps — reduces tokens and eliminates hallucinated date formats in intermediate JSON passed to step 3.

## Closing operational guidance

Reduce step temperature 0; creative steps moderate — mixed chain with single global temperature suboptimizes each step. Pass per-step generation config in orchestrator metadata. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away.

## Resources

- [LangChain LCEL documentation](https://python.langchain.com/docs/concepts/lcel/)
- [LlamaIndex query pipeline](https://docs.llamaindex.ai/en/stable/module_guides/querying/pipeline/)
- [OpenAI cookbook — chunking strategies](https://cookbook.openai.com/)
- [Map-reduce paper (Dean & Ghemawat)](https://research.google/pubs/mapreduce-simplified-data-processing-on-large-clusters/)
- [Instructor library for structured outputs](https://python.useinstructor.com/)
