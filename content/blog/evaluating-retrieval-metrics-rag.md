---
title: "Evaluating Retrieval: Recall, Precision, and NDCG for RAG"
slug: "evaluating-retrieval-metrics-rag"
description: "A practical guide to retrieval evaluation for RAG: recall@k, precision@k, MRR, and NDCG explained with examples, plus how to build a labeled eval set that works."
datePublished: "2026-02-21"
dateModified: "2026-02-21"
tags: ["RAG", "Retrieval", "Evaluation", "Search"]
keywords: "retrieval evaluation, recall and precision, NDCG, RAG metrics, search evaluation, MRR"
faq:
  - q: "Which retrieval metric matters most for RAG?"
    a: "Recall@k is usually the metric to optimize first, because if the relevant document isn't in the k chunks you retrieve, the generator cannot possibly use it. Once recall is high, use NDCG or MRR to check that the best chunks are ranked near the top where the model attends most."
  - q: "What is the difference between recall@k and NDCG?"
    a: "Recall@k asks whether the relevant documents are anywhere in the top k, ignoring their order. NDCG rewards putting the most relevant documents higher and supports graded relevance (some docs more relevant than others). Recall measures presence; NDCG measures ranking quality."
  - q: "How do I build a retrieval eval set without huge labeling effort?"
    a: "Start with 50-100 real queries and mark which chunks are relevant for each. You can bootstrap labels with an LLM judge and then human-verify a sample. A small, honest, domain-specific set beats a large noisy one for catching regressions."
---

When a RAG system gives a bad answer, the reflex is to blame the model or tweak the prompt. Usually the real culprit is upstream: the retriever never surfaced the right chunk, so the generator was working blind. You cannot fix what you don't measure, and "the answers seem better now" is not measurement. Retrieval evaluation gives you the numbers to know whether a change to your embeddings, chunking, or reranker actually helped.

The good news is that retrieval is a search problem, and search has decades of well-defined metrics. Recall@k, precision@k, MRR, and NDCG each answer a different question about retrieval quality, and knowing which one to optimize for saves you from chasing the wrong improvement. Here's what each measures, when to use it, and how to build the labeled set that makes any of it meaningful.

## First, separate retrieval from generation

RAG has two stages that fail differently. Evaluate them separately or you'll misdiagnose everything.

- **Retrieval:** given a query, did we fetch the right chunks? Measured by the metrics below against relevance labels.
- **Generation:** given the right chunks, did the model produce a correct, grounded answer? Measured by faithfulness and answer-correctness [evals](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/).

If retrieval recall is 60%, no amount of prompt engineering fixes the 40% of queries where the answer simply wasn't in the context. Fix retrieval first. This post is about that stage.

## Recall@k: is the answer even in there?

Recall@k asks: of all the documents that are relevant to this query, what fraction appear in the top k retrieved? For RAG it's usually the most important metric, because retrieval sets a hard ceiling — if the relevant chunk isn't in the k you pass to the model, the answer is unreachable no matter how good the model is.

If a query has 2 relevant chunks and you retrieve k=5 with 1 of them present, recall@5 = 0.5. Average across your query set for the system-level number. When I'm tuning a RAG pipeline, recall@k at my actual k (the number of chunks I feed the model) is the first dial I turn.

## Precision@k: how much of what you fetched is useful

Precision@k is the flip side: of the k documents retrieved, what fraction are relevant? Retrieve k=5 with 2 relevant and precision@5 = 0.4. Low precision means you're padding the context with junk, which costs tokens and — per [context engineering](https://blog.michaelsam94.com/context-engineering-beyond-prompts/) — actively distracts the model.

There's a real tension: raising k tends to raise recall and lower precision. The right k balances "don't miss the answer" against "don't drown the model in noise." A reranker is how you get both — cast a wide net for recall, then rerank and keep only the top few for precision.

## MRR: how high is the first good hit

Mean Reciprocal Rank cares only about the position of the *first* relevant result. If it's ranked 1st you score 1.0, 2nd scores 0.5, 3rd 0.33, and so on; average the reciprocals across queries. MRR is the right lens when there's essentially one correct answer per query — a factoid lookup, a "find the doc that defines X." It rewards getting the single right thing to the top and is blunt about everything below it.

## NDCG: ranking quality with graded relevance

NDCG (Normalized Discounted Cumulative Gain) is the most complete ranking metric and the one to reach for when order matters and relevance isn't binary. Two ideas:

- **Graded relevance.** A chunk can be perfect (3), useful (2), tangential (1), or irrelevant (0), not just yes/no.
- **Position discount.** Gains from lower-ranked results are discounted logarithmically, because users — and models, which attend most to the top of context — get less value from things further down.

DCG sums those discounted gains; NDCG normalizes it against the ideal ordering so the score lands in 0-1 and is comparable across queries. NDCG@10 is the standard for judging whether your reranker is putting the *best* chunks highest, not just somewhere in the set.

A quick reference for which to use:

| Metric | Answers | Best when |
|---|---|---|
| Recall@k | Is the relevant doc in the top k? | The first thing to optimize for RAG |
| Precision@k | How much of the top k is relevant? | Controlling context noise/cost |
| MRR | How high is the first relevant doc? | One correct answer per query |
| NDCG@k | Are the best docs ranked highest? | Graded relevance, tuning rerankers |

## Computing them without reinventing the wheel

You don't hand-roll these. `pytrec_eval` (bindings to the standard TREC evaluation tool) or the `ranx` library take your run and your relevance judgments (qrels) and return everything at once:

```python
from ranx import Qrels, Run, evaluate

qrels = Qrels({"q1": {"doc_42": 3, "doc_7": 1}})      # graded relevance
run   = Run({"q1": {"doc_42": 0.9, "doc_9": 0.8, "doc_7": 0.6}})  # your scores

print(evaluate(qrels, run, ["recall@5", "precision@5", "mrr", "ndcg@10"]))
```

## The eval set is the hard part

Metrics are trivial to compute; the labels feeding them are where the real work — and the value — lives. A useful retrieval eval set:

1. **Uses real queries.** Pull them from production logs, not your imagination. Real users ask messier questions than you'd invent.
2. **Is small and honest.** 50-100 queries with carefully checked relevance labels beat thousands of noisy ones. You want a set you trust enough to block a deploy on.
3. **Can be bootstrapped with an LLM judge.** Have a strong model label chunk relevance, then human-verify a sample to estimate the judge's error rate. This slashes labeling effort while keeping you honest.
4. **Covers your long tail.** Include the rare, hard queries where retrieval usually breaks, not just the easy head.

Wire it into CI so every change to embeddings, chunking strategy, or reranker runs the suite and reports recall@k and NDCG deltas. That turns "I think the new embedding model is better" into "recall@5 went from 0.71 to 0.83, NDCG@10 from 0.64 to 0.72" — which is the entire point. Retrieval you can measure is retrieval you can improve; everything else is guessing dressed up as engineering.

## Resources

- [TREC evaluation tool — pytrec_eval (GitHub)](https://github.com/cvangysel/pytrec_eval)
- [ranx — ranking evaluation library (GitHub)](https://github.com/AmenRa/ranx)
- [Ragas — RAG evaluation framework](https://docs.ragas.io/)
- [Pinecone — Retrieval evaluation guide](https://www.pinecone.io/learn/offline-evaluation/)
- [BEIR — Retrieval benchmark (GitHub)](https://github.com/beir-cellar/beir)
- [Stanford — Introduction to Information Retrieval](https://nlp.stanford.edu/IR-book/)
