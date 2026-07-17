---
title: "Evaluating RAG with RAGAS"
slug: "rag-evaluation-ragas-framework"
description: "Evaluate RAG pipelines with the RAGAS framework: faithfulness, answer relevancy, context precision, and context recall metrics with practical CI integration."
datePublished: "2024-12-07"
dateModified: "2026-07-17"
tags: ["AI", "RAG", "Evaluation", "RAGAS"]
keywords: "RAGAS evaluation, RAG metrics, faithfulness score, context recall, answer relevancy, LLM evaluation framework"
faq:
  - q: "What metrics does RAGAS provide for RAG evaluation?"
    a: "Core metrics include faithfulness (are claims supported by retrieved context?), answer relevancy (does the answer address the question?), context precision (are retrieved chunks relevant?), and context recall (was all necessary information retrieved?). RAGAS also offers aspect-specific critiques and newer agent-focused metrics. Together they decompose pipeline failures into retrieval vs generation problems."
  - q: "Do I need ground truth answers to use RAGAS?"
    a: "Some metrics like context recall and answer correctness require ground truth references. Faithfulness and answer relevancy can run without golden answers by using LLM-as-judge evaluation against retrieved context. Start with faithfulness on production logs even before you build a full golden eval set."
  - q: "How do I integrate RAGAS into CI/CD?"
    a: "Maintain a frozen eval dataset of 50–200 question-context-answer triples. Run RAGAS scoring on every pipeline change — embedding model, chunk size, prompt template — and fail CI if key metrics drop below thresholds. Keep eval LLM calls separate from production inference to control cost and version lock the judge model."
---

The team swapped embedding models and celebrated a 12% latency improvement. Nobody ran evals until support tickets spiked two weeks later — context recall on billing questions had dropped 23 points, and the new model consistently missed refund policy chunks. Latency metrics looked great; quality metrics were never measured. RAGAS exists so you catch that regression before users do.

## Why RAG needs component-level metrics

End-to-end accuracy alone cannot tell you whether to fix retrieval or generation. A wrong answer might mean:

- Retrieval failed to find the right chunks (fix chunking, embeddings, or hybrid search).
- Retrieval succeeded but generation ignored context (fix prompts, model, or temperature).
- Generation hallucinated despite good context (add faithfulness checks).

RAGAS decomposes the pipeline into measurable components so you know which knob to turn.

## Core RAGAS metrics explained

**Faithfulness** — measures whether statements in the generated answer are supported by retrieved context. Low faithfulness means hallucination or over-extrapolation even when retrieval was correct.

**Answer relevancy** — measures whether the answer actually addresses the question. High faithfulness with low relevancy means the model cited real docs but answered a different question.

**Context precision** — measures what fraction of retrieved chunks are relevant to the question. Low precision means noisy retrieval crowding the context window.

**Context recall** — measures whether retrieved context contains the information needed to produce the ground truth answer. Requires reference answers. Low recall means chunking or search problems.

| Symptom | Likely low metric | Fix direction |
|---------|-------------------|---------------|
| Wrong facts with good sources available | Faithfulness | Prompt, model, post-checks |
| Right facts, wrong question answered | Answer relevancy | Prompt, query routing |
| Right answer buried in irrelevant chunks | Context precision | Reranking, smaller top-k |
| Correct answer not in retrieved set | Context recall | Chunking, embeddings, hybrid |

## Running RAGAS in Python

```python
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
)

eval_data = {
    "question": ["What is the refund window for Enterprise plans?"],
    "answer": ["Enterprise plans allow refunds within 60 days of purchase."],
    "contexts": [[
        "Enterprise plan terms: Refunds requested within 60 days...",
        "Starter plan terms: All sales are final..."
    ]],
    "ground_truth": ["Enterprise refunds are available within 60 days."],
}

dataset = Dataset.from_dict(eval_data)
results = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    llm=eval_llm,       # judge model — lock the version
    embeddings=eval_emb,
)

print(results)
```

RAGAS uses an LLM as judge for several metrics. Lock the judge model version — switching judges changes absolute scores and breaks comparability across runs.

## Building a useful eval dataset

Quality beats quantity. 50 well-crafted examples covering:

- Simple single-hop factual questions.
- Multi-hop questions requiring multiple chunks.
- Questions where the answer is "not documented."
- Adversarial questions similar to but different from training examples.
- Domain jargon and acronym-heavy queries.

Source questions from production logs (anonymized), support ticket themes, and onboarding FAQs. Label ground truth answers and the chunk IDs that should retrieve.

## CI integration pattern

```yaml
# Simplified CI step
- name: RAG eval gate
  run: |
    python scripts/run_ragas_eval.py \
      --dataset evals/rag_golden_v3.jsonl \
      --min-faithfulness 0.85 \
      --min-context-recall 0.75
```

Fail the build when metrics drop below thresholds compared to the baseline stored from the last approved run. Store full result JSON as CI artifacts for trend analysis.

Run evals on pipeline changes, not every application deploy. Embedding model swaps, chunk strategy changes, prompt rewrites, and reranker updates all warrant a RAGAS run.

## Limitations to plan around

- **LLM judge variance** — scores fluctuate 2–5 points between judge model versions. Lock versions and re-baseline when upgrading.
- **Cost** — faithfulness and relevancy call the judge per example. A 200-example eval is cheap; running it on every production query is not.
- **English bias** — RAGAS metrics were developed primarily on English text. Validate on your languages before trusting thresholds.
- **Not a user satisfaction proxy** — high RAGAS scores correlate with quality but do not capture tone, formatting preferences, or UX.

Use RAGAS for regression detection and component debugging. Pair it with human review on a sample of production answers monthly.

## Ragas metrics interpretation

| Metric | Measures | Target |
|--------|----------|--------|
| faithfulness | Answer grounded in context | > 0.85 |
| answer_relevancy | Answer addresses question | > 0.80 |
| context_precision | Retrieved chunks relevant | > 0.75 |
| context_recall | Needed info retrieved | > 0.80 |

Run Ragas on 100-question golden set weekly — track drift when changing chunking or embedding model.

## Common production mistakes

Teams get evaluation ragas framework wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

RAG pipelines for evaluation ragas framework degrade when chunk boundaries split tables, embeddings go stale after doc updates, and retrieval metrics are measured offline only. Re-index incrementally and monitor answer faithfulness on live traffic samples.

## Debugging and triage workflow

When evaluation ragas framework misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Custom RAGAS metrics for agentic pipelines

When RAG feeds tool-using agents, extend RAGAS with custom metrics: tool selection accuracy, parameter extraction fidelity, and multi-hop context completeness. Wrap agent trajectories into RAGAS dataset rows with `contexts` as all retrieved plus tool outputs.

Compare faithfulness before and after adding agent loops — agents sometimes synthesize across tools in ways standard faithfulness judges flag incorrectly. Tune judge prompts on 20 hand-scored examples first.

## Production sampling with RAGAS-lite

Full RAGAS on every query is prohibitive. Sample 1% of production traffic into async eval queues running faithfulness-only checks. Alert when rolling 7-day faithfulness drops more than 5 points vs. baseline — faster than waiting for CSAT declines.

## Stratified eval datasets

Balance golden sets across product lines and languages. Over-represented FAQ categories inflate aggregate RAGAS scores while enterprise billing questions fail silently. Report per-stratum metrics in CI artifacts.

## Measuring success for evaluation ragas framework

Define two or three metrics tied to user outcomes before tuning implementation details. Review them weekly in a short run review: median and p95 latency, error or block rates where applicable, and a quality sample from production logs or golden eval sets. Store dashboard links and threshold values in the runbook so on-call engineers know what "healthy" means without reading source code. When metrics drift after a deploy, roll back first and compare traces with correlation IDs second — speed matters more than root cause during customer-visible regressions.

## Resources

- [RAGAS documentation](https://docs.ragas.io/)
- [RAGAS GitHub repository](https://github.com/explodinggradients/ragas)
- [RAGAS paper — evaluating RAG pipelines](https://arxiv.org/abs/2309.15217)
- [Hugging Face — datasets library](https://huggingface.co/docs/datasets/)
- [LangSmith evaluation and tracing](https://docs.smith.langchain.com/evaluation)
