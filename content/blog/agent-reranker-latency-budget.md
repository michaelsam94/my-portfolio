---
title: "AI Agents: Reranker Latency Budget"
slug: "agent-reranker-latency-budget"
description: "Allocate milliseconds across retrieval, reranking, and generation in agent RAG pipelines—with adaptive top-k, deadline propagation, and graceful fallback when the cross-encoder misses its slot."
datePublished: "2025-04-14"
dateModified: "2025-04-14"
tags: ["AI", "Agent", "Reranker"]
keywords: "reranker latency budget, cross-encoder timeout, RAG pipeline SLA, adaptive top-k, Cohere rerank, retrieval quality tradeoff"
faq:
  - q: "What share of total RAG latency should reranking consume?"
    a: "Cap reranking at 15–25% of end-to-end p95 budget for interactive agents—typically 80–150 ms on a 600 ms target. Retrieval and generation dominate; reranking is high leverage per millisecond but hits steep diminishing returns past 100 candidate pairs."
  - q: "Should agents skip reranking under load?"
    a: "Degrade by reducing candidate count before skipping entirely. Drop from top-50 to top-20 first; if still over budget, fall back to bi-encoder scores with a logged degrade flag. Blind skip without telemetry hides quality regressions product teams never notice until eval scores drop."
  - q: "How do you budget batched vs per-query rerank calls?"
    a: "Batching improves throughput but adds queue wait. Set a max batch wait of 10–20 ms; if the batch is not full by then, send partial batch. Measure queue_time separately from model_inference_ms—on-call often optimizes the wrong knob."
  - q: "Does reranker latency matter for background agent tasks?"
    a: "Loosen budgets for async jobs—500 ms rerank on a 30 s report job is fine. Still enforce deadlines so runaway retrieval does not block worker pools; use context cancellation propagated from the job scheduler."
---
Product wanted "better answers" from the support agent. Engineering added a cross-encoder reranker on top-100 bi-encoder hits. p95 query latency jumped from 620 ms to 1.4 s; users complained before eval dashboards moved. The reranker was not slow in isolation—it had **no budget**, ran on 100 pairs every time, and blocked generation even when the first five bi-encoder results were already correct. Fixing agent quality required treating reranking as a scheduled passenger with a ticket, not a free rider on the critical path.

## Decompose the pipeline budget

Start from user-facing SLO—say 800 ms p95 for first token visible—and allocate backward:

| Stage | Target p95 | Notes |
|-------|------------|-------|
| Gateway auth + routing | 40 ms | fixed |
| Query embedding | 60 ms | cache frequent queries |
| Vector retrieval (top-100) | 120 ms | HNSW params trade recall |
| **Rerank (100→10)** | **120 ms** | **this post** |
| Context assembly | 30 ms | token trimming |
| LLM first token | 430 ms | dominates |

Sum with overlap awareness: parallelize embedding with auth where possible; rerank cannot start until retrieval returns.

Document the budget in repo `docs/latency-budget.md` and enforce in code—not slide decks.

## Deadline propagation

Pass `deadline` through the stack:

```typescript
interface RequestContext {
  traceId: string;
  deadlineMs: number; // absolute monotonic deadline
}

function remainingMs(ctx: RequestContext): number {
  return Math.max(0, ctx.deadlineMs - performance.now());
}

async function ragQuery(ctx: RequestContext, query: string): Promise<RagResult> {
  const embed = await withTimeout(embedQuery(query), remainingMs(ctx) * 0.15);
  const hits = await withTimeout(retrieve(embed, 100), remainingMs(ctx) * 0.25);

  const rerankBudget = Math.min(remainingMs(ctx) * 0.25, 150);
  const ranked = await rerankWithBudget(query, hits, rerankBudget, ctx);

  return assembleContext(ranked, remainingMs(ctx));
}
```

Child stages receive **fractions of remaining time**, not fixed slices—prevents earlier spikes from stealing rerank budget silently.

## Adaptive top-k: spend where marginal gain exists

Score dispersion from bi-encoder tells you whether reranking is worth full cost:

```python
import numpy as np

def adaptive_rerank_k(scores: list[float], max_k: int = 50, min_k: int = 10) -> int:
    if len(scores) <= min_k:
        return len(scores)
    top = np.array(scores[:max_k])
    # Normalized gap between rank-5 and rank-20
    spread = top[4] - top[19] if len(top) >= 20 else top[0] - top[-1]
    if spread > 0.12:  # tune from offline eval
        return min_k  # clear winners — cheap rerank
    if spread > 0.06:
        return 25
    return max_k  # ambiguous — spend budget
```

Log chosen `k` and `spread` per query. Product analytics correlates `k` distribution with thumbs-down rate.

## Rerank executor with cancellation

```python
import asyncio
from dataclasses import dataclass

@dataclass
class RerankResult:
    doc_ids: list[str]
    degraded: bool
    latency_ms: float

async def rerank_with_budget(
    query: str,
    docs: list[dict],
    budget_ms: float,
    client,
) -> RerankResult:
    t0 = asyncio.get_event_loop().time()
    k = adaptive_rerank_k([d["score"] for d in docs])
    subset = docs[:k]

    try:
        ranked = await asyncio.wait_for(
            client.rerank(query, [d["text"] for d in subset]),
            timeout=budget_ms / 1000,
        )
        ordered = [subset[i]["id"] for i in ranked.indices[:10]]
        return RerankResult(
            doc_ids=ordered,
            degraded=False,
            latency_ms=(asyncio.get_event_loop().time() - t0) * 1000,
        )
    except asyncio.TimeoutError:
        fallback = [d["id"] for d in sorted(subset, key=lambda x: -x["score"])[:10]]
        return RerankResult(
            doc_ids=fallback,
            degraded=True,
            latency_ms=budget_ms,
        )
```

Emit `rerank_degraded_total` counter—alert when degrade rate exceeds 5% for 15 minutes.

## Batching without blowing p95

Self-hosted cross-encoders (sentence-transformers, ONNX runtime) benefit from micro-batching:

```python
class RerankBatcher:
    def __init__(self, max_batch=16, max_wait_ms=15):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.max_batch = max_batch
        self.max_wait_ms = max_wait_ms

    async def rerank(self, query: str, pairs: list[str]) -> list[float]:
        fut = asyncio.get_event_loop().create_future()
        await self.queue.put((query, pairs, fut))
        return await fut

    async def run_worker(self, model):
        while True:
            batch = []
            deadline = asyncio.get_event_loop().time() + self.max_wait_ms / 1000
            while len(batch) < self.max_batch:
                timeout = max(0, deadline - asyncio.get_event_loop().time())
                try:
                    item = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    batch.append(item)
                except asyncio.TimeoutError:
                    break
            if not batch:
                continue
            # model forward on concatenated batch — implementation specific
            ...
```

Separate metrics: `rerank_batch_size`, `rerank_queue_wait_ms`, `rerank_inference_ms`. High queue wait under low inference means increase `max_wait_ms` cautiously or add GPU replicas.

## Hosted rerank APIs (Cohere, Jina, etc.)

Vendor latency includes network RTT—budget 40–60 ms overhead on top of advertised model time. Co-locate agent workers in the same region as rerank endpoint. Cache rerank results for identical `(query_hash, doc_set_hash)` within TTL for FAQ-heavy agents; invalidate on corpus update.

Compare cost: hosted rerank per 1k queries vs GPU amortized—finance cares when agent traffic 10×.

## Quality guardrails when degrading

Degraded path must not silently ship garbage:

1. Log feature flag `rerank_degraded` on response metadata for offline eval joins
2. Weekly sample degraded queries for human review
3. Auto-raise budget temporarily if degrade correlates with support ticket volume

Run offline nDCG@10 with full rerank vs bi-encoder-only on golden sets—know your quality floor before enabling adaptive k.

## Load testing rerank saturation

Scenario matrix:

- Steady 500 QPS with p95 budget 800 ms
- Spike 3× with retrieval cache cold
- Single query with max_k=100 and adversarial long documents

Watch GPU SM utilization and batch queue depth—not just HTTP 500 rate. Rerank timeouts manifest as **good-enough wrong answers**, not errors.

## Instrumentation checklist

Traces should include spans:

- `retrieve` with `hit_count`, `index_name`
- `rerank` with `k`, `degraded`, `inference_ms`, `queue_ms`
- `generate` with `prompt_tokens`

SLO burn on parent `agent.query` span when rerank child exceeds 150 ms for 5% of traffic.

## Token budget interaction

Reranking longer documents increases cross-encoder input tokens—latency and cost rise together. Truncate candidate text to 512 tokens per side with sentence-aware cutoffs before rerank scoring. Log `truncated_pair_count` when truncation fires; eval teams compare truncated vs full-text nDCG quarterly.

If your agent passes reranked chunks directly to the LLM, rerank latency savings mean nothing when generation blows the context window. Tie rerank `top_n` output to remaining **generation token budget**—return fewer, higher-confidence chunks when the user query already consumed retrieval budget.

## Cold start and model warm-up

Self-hosted reranker pods cold-start in 3–8 seconds on scale-from-zero platforms. Agent traffic spikes after marketing launches hit cold GPUs first—p95 explodes while average looks fine. Keep minimum replicas ≥2 during business hours; run synthetic rerank warmup queries every 60 seconds on each pod (`/health/warm` endpoint that runs a dummy forward pass).

For serverless GPU, accept higher baseline cost or route interactive traffic to always-warm pools and batch analytics to spot instances.

## Eval loop closing the budget

Define two offline metrics tracked weekly:

- **Latency compliance**: % of golden queries where simulated pipeline meets 800 ms with production budgets
- **Quality delta**: nDCG@10 full rerank minus degraded path

Raise rerank budget only when quality delta exceeds 4 points and latency compliance stays above 98%. Lower budget when compliance drops below 95% regardless of quality—users abandon before reading perfect answers.

Ship feature flags per tenant tier: enterprise gets full rerank budget; free tier gets adaptive k capped at 15. Meter `rerank_ms * qps` per tier for COGS reporting.

## Multi-query agent turns

Sub-agents and decomposition patterns issue three retrieval calls per user message. Budget per **turn**, not per sub-query—or split the 120 ms rerank slice across calls (40 ms each) with hard fallback on the third. Parent orchestrator passes shared `deadlineMs`; child calls must not reset deadlines locally.

## Resources

- [Cohere Rerank API documentation](https://docs.cohere.com/reference/rerank) — latency characteristics and batch limits for hosted rerankers
- [Sentence Transformers — Cross-Encoders](https://www.sbert.net/examples/applications/cross-encoder/README.html) — self-hosted rerank modeling options
- [ONNX Runtime — Performance tuning](https://onnxruntime.ai/docs/performance/tune-performance.html) — optimizing cross-encoder inference on CPU/GPU
- [Google SRE — Implementing SLOs](https://sre.google/workbook/implementing-slos/) — budgeting error budgets across pipeline stages
- [Pinecone — Hybrid search and reranking patterns](https://docs.pinecone.io/guides/search/hybrid-search) — retrieval+r rerank integration in vector stacks
