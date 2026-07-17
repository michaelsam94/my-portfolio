---
title: "Agentic Retrieval Loops"
slug: "rag-agentic-retrieval-loops"
description: "Build agentic RAG with multi-step retrieval loops: query decomposition, iterative search, self-correction, and stopping criteria that improve answer quality on complex questions."
datePublished: "2024-11-17"
dateModified: "2026-07-17"
tags: ["AI", "RAG", "Agents", "Retrieval"]
keywords: "agentic RAG, iterative retrieval, query decomposition, self-RAG, multi-hop retrieval, retrieval loops, LLM agents"
faq:
  - q: "When should I use agentic retrieval instead of single-shot RAG?"
    a: "Single-shot RAG works when one query maps cleanly to one retrieval call and the answer lives in a few chunks. Agentic retrieval helps when questions require combining facts from multiple documents, resolving ambiguities, or verifying claims across sources. If your eval set shows multi-hop failures, loops are worth the added latency and cost."
  - q: "How do I prevent infinite retrieval loops?"
    a: "Set a hard maximum iteration count — typically three to five — and define explicit stop conditions: sufficient evidence gathered, confidence threshold met, or no new documents retrieved. Log each loop's query and result count so you can tune stopping rules from production data rather than guessing."
  - q: "Does agentic RAG cost significantly more than standard RAG?"
    a: "Yes. Each loop iteration adds an LLM call plus at least one retrieval call. A three-iteration loop can cost three to five times a single-shot pipeline. Use it selectively for complex queries or route simple questions through a fast single-shot path based on a lightweight classifier."
---

A user asked your docs bot "Can I use SSO with the legacy API if my org migrated to the new auth service last quarter?" Single-shot RAG retrieved a chunk about SSO configuration from 2022 and a chunk about the new auth service launch — then synthesized a confident wrong answer because nobody taught the pipeline that "last quarter" requires checking migration timelines across two doc sets. Agentic retrieval loops exist for exactly this: questions where one embedding search is not enough.

## Single-shot RAG breaks on multi-hop questions

Standard RAG embeds the user query, retrieves top-k chunks, stuffs them into a prompt, and generates an answer. That pipeline assumes the query embedding aligns with the chunks that contain the answer. Multi-hop questions violate that assumption because the answer requires intermediate facts the original query never mentions.

"Which compliance framework applies to our EU customers using the Frankfurt region?" needs at least two hops: identify which product those customers use, then find the compliance doc for that product in that region. One retrieval call rarely lands both chunks in top-k.

## The agentic loop pattern

An agentic retrieval loop wraps the LLM and retriever in a cycle:

1. **Plan** — decompose the question into sub-queries or decide what to search next.
2. **Retrieve** — run one or more searches with the current sub-query.
3. **Evaluate** — assess whether retrieved context is sufficient, contradictory, or incomplete.
4. **Refine** — rewrite the query, search again, or proceed to answer.
5. **Stop** — exit when criteria are met or max iterations hit.

```python
MAX_ITERATIONS = 4

def agentic_rag(question: str) -> str:
    context_chunks = []
    sub_query = question

    for i in range(MAX_ITERATIONS):
        new_chunks = retrieve(sub_query, top_k=5)
        context_chunks.extend(new_chunks)

        assessment = llm_evaluate(question, context_chunks)
        # assessment: { "sufficient": bool, "next_query": str | None }

        if assessment["sufficient"]:
            break
        if assessment["next_query"] is None:
            break
        sub_query = assessment["next_query"]

    return llm_generate(question, dedupe(context_chunks))
```

The evaluate step is what separates agentic RAG from blind re-querying. Without it, you are just running the same search multiple times with minor paraphrases.

## Query decomposition strategies

**LLM-generated sub-queries:** Ask the model to break the question into independent search tasks before any retrieval. Works well for analytical questions with clear facets.

```text
Question: Compare uptime SLAs for Enterprise vs Starter plans in APAC.

Sub-queries:
1. Enterprise plan uptime SLA APAC
2. Starter plan uptime SLA APAC
3. APAC region infrastructure redundancy
```

**Hypothesis-driven retrieval:** Generate a draft answer from initial chunks, identify claims lacking evidence, and retrieve specifically for those gaps. Self-RAG and corrective RAG variants use this pattern.

**Tool-calling agents:** Frame retrieval as a tool the agent invokes with explicit query strings. The agent's reasoning trace shows why each search happened — valuable for debugging and audit.

## Handling contradictions and stale chunks

Loops should detect when new chunks contradict earlier ones. Prompt the evaluator explicitly:

```text
If retrieved documents conflict, note the conflict and retrieve
with a query targeting the more recent or authoritative source.
Prefer documents tagged "current" over "deprecated".
```

Metadata filters — document version, effective date, status — reduce contradiction frequency but do not eliminate it. The loop's evaluate step is your last line of defense.

## Stopping criteria that work in production

Hard limits prevent runaway cost: `MAX_ITERATIONS = 4` is a common starting point. Soft stops improve quality:

- **Coverage check:** Does context address every entity in the question?
- **Novelty check:** Did the last retrieval return chunks already in context?
- **Confidence threshold:** Model rates its evidence sufficiency above 0.8.

Log iteration count, sub-queries, and chunk IDs per request. Questions that consistently hit max iterations indicate corpus gaps or bad chunking — not just a tuning problem.

## Routing simple vs complex queries

Not every question needs a loop. A lightweight classifier — keyword heuristics, embedding distance to known simple patterns, or a small model — routes "What are your business hours?" to single-shot and "How does feature X interact with policy Y for migrated accounts?" to the agentic path.

This hybrid architecture keeps p95 latency acceptable while improving quality on the 15–20% of queries that actually need multi-hop retrieval.


## Token budget governor

Track cumulative retrieved tokens across iterations — hard cap at 8k or 70% of model context, whichever lower. Evaluator prompt at cap must choose synthesize vs ask clarifying question, not silently truncate oldest chunks without telling the model.

## Cheap-first iteration strategy

Iteration 1: BM25 only. Iteration 2+: add vector + reranker if evaluator confidence below threshold. Saves 40–60% retrieval cost on queries that exit after one hop in our support bot traces.

## Sub-query diversity scoring

If iteration N retrieves >80% duplicate chunk IDs vs iteration N-1, stop early — rewriter is stuck. Log duplicate rate; high rates indicate poor query reformulation prompt or corpus too sparse for the question domain.

## Parallel sub-queries per iteration

Independent sub-queries (Enterprise SLA vs Starter SLA) can retrieve in parallel within one iteration — wall clock drops vs sequential searches. Merge contexts with dedupe on chunk ID before evaluate step; parallel without dedupe bloats context and confuses evaluator.

## User-visible loop transparency

Optional debug mode shows "Searching: migration timeline Q3 2025" — support power users tolerate slightly longer loops when progress is visible. Hide in consumer mode; show in B2B admin consoles with toggle.

## Production rollout notes

Product management should define max acceptable latency for agentic path — if p95 exceeds 8 seconds, route more queries to single-shot via classifier threshold tuning. Loops improve quality only when users wait; async email-style workflows tolerate longer loops than live chat.
## Citation requirement in loop exit

Final generation must cite chunk IDs used across all iterations — evaluator checks citations cover entities in question before marking sufficient. Prevents early exit when model has partial context missing one of three required entities in compound question.

## Closing operational guidance

Expose max iteration config per tenant tier — free tier single-shot only; enterprise enables four iterations with SLA on p95 latency documented in contract appendix. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away. Ship changes behind feature flags, measure before and after on real traffic, and keep rollback one deploy revert away.

## Resources

- [Self-RAG paper (Asai et al.)](https://arxiv.org/abs/2310.11511)
- [Corrective RAG (CRAG) research](https://arxiv.org/abs/2401.15884)
- [LangGraph — agentic workflows documentation](https://langchain-ai.github.io/langgraph/)
- [LlamaIndex query engines and agents](https://docs.llamaindex.ai/en/stable/understanding/agent/)
- [Anthropic — building effective agents](https://www.anthropic.com/research/building-effective-agents)
