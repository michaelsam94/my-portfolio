---
title: "Dynamic Few-Shot Example Selection"
slug: "llm-few-shot-example-selection"
description: "Select few-shot examples dynamically for LLM prompts: embedding similarity, diversity sampling, metadata filters, and selection strategies that beat static examples."
datePublished: "2024-12-03"
dateModified: "2024-12-03"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "few-shot example selection, dynamic few-shot prompting, in-context learning, example retrieval LLM, prompt examples"
faq:
  - q: "How many few-shot examples should I include?"
    a: "Typically 3–8 examples depending on example length and task complexity. More examples help up to a point — then context bloat hurts and the model confuses patterns. Measure on your eval set: plot accuracy vs example count and stop where marginal gain drops below 1%."
  - q: "Static vs dynamic few-shot — when does dynamic win?"
    a: "Dynamic wins when your task has diverse subtypes (support intents, document formats, code patterns) and no single static set covers them well. Static is fine for homogeneous tasks with stable patterns. Dynamic adds latency (embedding lookup) and infrastructure."
  - q: "Should few-shot examples include chain-of-thought?"
    a: "Include reasoning in examples only when the task requires multi-step reasoning and you've confirmed CoT helps on evals. For classification and extraction, input→output pairs without reasoning are cleaner and use fewer tokens."
---

The same four few-shot examples in every prompt worked until users started asking about enterprise billing — a category none of the examples covered. The model defaulted to consumer pricing patterns and sounded confident doing it. Static few-shot is a shotgun; dynamic selection picks the right examples for each input, improving accuracy without stuffing 20 examples into every prompt.

## Example store design

```python
@dataclass
class FewShotExample:
    id: str
    input: str
    output: str
    embedding: list[float]
    metadata: dict  # intent, language, difficulty, tenant
    quality_score: float  # from human review or eval performance
```

Store in vector index + Postgres for metadata filtering. Curate examples from:

- Human-reviewed production interactions
- Golden eval cases with known-good outputs
- Synthetic examples for rare edge cases

Quality over quantity — 200 excellent examples beat 2,000 noisy ones.

## Similarity-based selection

Retrieve examples closest to the current input:

```python
async def select_examples(
    query: str,
    k: int = 5,
    filters: dict | None = None,
) -> list[FewShotExample]:
    embedding = await embed(query)
    candidates = await index.search(
        embedding,
        filter=filters,
        top_k=k * 3,  # over-fetch for diversity reranking
    )
    return diversify(candidates, k)
```

Use the same embedding model as your semantic router for consistency.

## Diversity sampling

Similarity alone picks near-duplicates. After retrieval, diversify:

```python
def diversify(candidates: list[FewShotExample], k: int) -> list[FewShotExample]:
    selected = [candidates[0]]  # best match always included
    while len(selected) < k:
        remaining = [c for c in candidates if c not in selected]
        # pick candidate maximally different from selected set
        next_ex = max(remaining, key=lambda c: min_distance(c, selected))
        selected.append(next_ex)
    return selected
```

Maximal marginal relevance (MMR) balances relevance and diversity:

```python
def mmr_score(candidate, query_embed, selected, lambda_param=0.7):
    relevance = cosine(candidate.embedding, query_embed)
    if not selected:
        return relevance
    max_sim = max(cosine(candidate.embedding, s.embedding) for s in selected)
    return lambda_param * relevance - (1 - lambda_param) * max_sim
```

## Metadata filtering

Constrain examples to relevant subset:

```python
filters = {
    "intent": classified_intent,
    "language": detect_language(query),
    "quality_score": {"$gte": 0.8},
}
```

Don't show billing examples for technical queries even if embedding similarity is high — intent filter first, similarity second.

## Prompt assembly

```python
def build_few_shot_prompt(examples: list[FewShotExample], query: str) -> str:
    shots = "\n\n".join(
        f"Input: {ex.input}\nOutput: {ex.output}"
        for ex in examples
    )
    return f"""Follow the pattern in these examples:

{shots}

Input: {query}
Output:"""
```

Place examples after system instructions, before the actual query. Consistent formatting across examples matters — the model learns the pattern from structure.

## Quality maintenance

Examples degrade as product changes:

- **Version tag** examples with product version
- **Retire** examples that fail when used in eval spot-checks
- **A/B test** example sets — track downstream success by example cohort
- **Prevent leakage** — eval cases shouldn't appear as few-shot examples for the same eval run

```python
async def validate_example_set(examples: list, eval_set: list) -> list:
    eval_inputs = {e.input for e in eval_set}
    return [ex for ex in examples if ex.input not in eval_inputs]
```

## Active learning for example curation

When the model fails on a query type:

1. Human labels correct output
2. Add to example store with embedding
3. Similar future queries automatically get this example

This closes the loop between failures and improved few-shot coverage.

## Cost and latency

Dynamic selection adds one embedding call (~50ms) and one vector search (~10ms). Cache selected examples for identical queries. Pre-compute embeddings for the example store at ingest time.

For latency-sensitive paths, pre-classify intent and maintain per-intent static subsets (5 examples × 10 intents = hybrid approach).

## Semantic similarity selection

Select examples most similar to the current query:

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")

def select_examples(query: str, example_store: list[dict], k: int = 5) -> list[dict]:
    query_emb = model.encode(query)
    example_embs = np.array([model.encode(ex["input"]) for ex in example_store])
    similarities = example_embs @ query_emb / (
        np.linalg.norm(example_embs, axis=1) * np.linalg.norm(query_emb)
    )
    top_k_indices = similarities.argsort()[-k:][::-1]
    return [example_store[i] for i in top_k_indices]
```

Semantic selection outperforms random selection by 10–20% on domain tasks. Pre-compute example embeddings at ingest — selection adds ~50ms at query time.

## Maximal Marginal Relevance (MMR)

Avoid selecting redundant similar examples:

```python
def mmr_select(query_emb, example_embs, examples, k=5, lambda_=0.7):
    selected, selected_embs = [], []
    candidates = list(range(len(examples)))

    while len(selected) < k and candidates:
        scores = []
        for i in candidates:
            relevance = cosine(query_emb, example_embs[i])
            redundancy = max(
                (cosine(example_embs[i], s) for s in selected_embs),
                default=0
            )
            mmr_score = lambda_ * relevance - (1 - lambda_) * redundancy
            scores.append((mmr_score, i))
        best_idx = max(scores)[1]
        selected.append(examples[best_idx])
        selected_embs.append(example_embs[best_idx])
        candidates.remove(best_idx)
    return selected
```

MMR balances relevance to query with diversity among selected examples. Five similar examples teach one pattern; five diverse examples teach five patterns.

## Example quality scoring

Not all examples are equally valuable — weight by demonstrated effectiveness:

```python
@dataclass
class ScoredExample:
    input: str
    output: str
    intent: str
    success_rate: float  # downstream task success when this example used
    usage_count: int
    last_validated: datetime

def select_weighted(query: str, examples: list[ScoredExample], k: int = 5) -> list:
    candidates = semantic_filter(query, examples, k=k * 3)
    # Boost high success rate, penalize stale
    scored = sorted(
        candidates,
        key=lambda e: e.success_rate * freshness_weight(e.last_validated),
        reverse=True,
    )
    return scored[:k]
```

Retire examples with success_rate <0.6 after 50+ usages. Add production failures as new examples after human labeling.

## Failure modes

- **Random example selection** — inconsistent quality; misses relevant patterns
- **Eval cases used as few-shot examples** — data leakage inflates eval scores
- **All examples same intent** — model doesn't learn intent boundaries
- **Stale examples after product change** — wrong behavior demonstrated
- **Too many examples (>8)** — context window consumed; diminishing returns above 5

## Production checklist

- Semantic similarity selection with pre-computed example embeddings
- MMR for diversity among selected examples (k=5 maximum)
- Examples tagged with intent and product version
- Eval cases excluded from example store (no leakage)
- Low success-rate examples retired after sufficient usage
- Hybrid: static per-intent subset for latency-critical paths

## Resources

- [LangChain example selectors](https://python.langchain.com/docs/how_to/example_selectors/)
- [LlamaIndex prompt helper modules](https://docs.llamaindex.ai/en/stable/module_guides/querying/prompts/)
- [In-Context Learning survey](https://arxiv.org/abs/2301.00234)
- [kNN-LM: retrieval augmented language modeling](https://arxiv.org/abs/2005.10639)
- [DSPy automatic prompt optimization](https://dspy-docs.vercel.app/)
