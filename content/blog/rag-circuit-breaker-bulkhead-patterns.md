---
title: "RAG: Circuit Breaker Bulkhead Patterns"
slug: "rag-circuit-breaker-bulkhead-patterns"
description: "Circuit breakers and bulkheads isolate RAG retrieval failures—when embedding or vector search degrades, trip the breaker, shed load to BM25 fallback, and preserve thread pools for healthy dependencies."
datePublished: "2024-10-29"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Circuit"]
keywords: "circuit breaker, bulkhead pattern, resilience4j, RAG fault tolerance, embedding timeout, vector DB isolation, fallback retrieval, thread pool isolation"
faq:
  - q: "Where should circuit breakers sit in a RAG retrieval pipeline?"
    a: "Place breakers at each external dependency boundary: embedding API client, vector database query client, reranker service, and optional LLM context assembly call. When embedding breaker opens, route to BM25-only retrieval. When vector DB breaker opens, serve cached results or return explicit degraded response—not unbounded retries."
  - q: "What is a bulkhead and why does RAG need it?"
    a: "Bulkheads isolate resource pools so failure in one dependency cannot exhaust shared threads or connections. RAG retrieval that shares a thread pool between embedding calls and vector search allows embedding slowness to starve vector queries. Separate pools with per-pool limits contain blast radius."
  - q: "How do you tune circuit breaker thresholds for RAG?"
    a: "Start with failure rate 50% over 10-request sliding window and 30-second open state. RAG dependencies have different latency profiles—embedding may need 5-second call timeout vs 500ms for cache. Tune from game day data: threshold should open before connection pool exhaustion but not on single transient blips."
---
Embedding latency climbed gradually over twenty minutes—p95 from 200 ms to 4 seconds. Without circuit breakers, the retrieval service queued unlimited embedding requests, exhausted its thread pool, and vector search stopped responding too. Every query returned timeout after timeout. With breakers configured, at 50% failure rate the embedding breaker opened after ten seconds, routed new queries to BM25-only fallback, and preserved the vector search thread pool for cache hits and keyword retrieval. p95 stabilized at 800 ms with reduced but non-zero relevance.

Circuit breakers and bulkheads are resilience patterns from distributed systems literature—Michael Nygard's *Release It!* catalog—that RAG pipelines need explicitly because retrieval chains multiple fallible dependencies with vastly different latency and failure characteristics.

## RAG dependency graph and failure propagation

```
Query → [Embedding] → [Vector search] → [Reranker] → Context assembly
              ↓              ↓               ↓
         Breaker #1     Breaker #2      Breaker #3
              ↓              ↓               ↓
         BM25 fallback   Cache serve     Skip rerank
```

Without isolation, slow embedding blocks threads needed for vector search. Bulkheads prevent cross-contamination.

## Circuit breaker states

```
CLOSED (normal) → failures exceed threshold → OPEN (fail fast)
OPEN → timeout expires → HALF-OPEN (probe)
HALF-OPEN → probe succeeds → CLOSED
HALF-OPEN → probe fails → OPEN
```

In OPEN state, calls fail immediately without waiting for timeout—protecting downstream and caller resources.

## Implementation with resilience4j (Java) or equivalent

```java
// config/CircuitBreakerConfig.java
CircuitBreakerConfig embeddingConfig = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)
    .waitDurationInOpenState(Duration.ofSeconds(30))
    .slidingWindowType(SlidingWindowType.COUNT_BASED)
    .slidingWindowSize(10)
    .recordExceptions(EmbeddingException.class, TimeoutException.class)
    .ignoreExceptions(ValidationException.class)
    .build();

CircuitBreaker embeddingBreaker = CircuitBreaker.of("embedding", embeddingConfig);

// Register event listeners for metrics
embeddingBreaker.getEventPublisher()
    .onStateTransition(event -> metrics.recordBreakerTransition("embedding", event));
```

Python equivalent with `pybreaker`:

```python
# resilience/breakers.py
import pybreaker

embedding_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    exclude=[ValidationError],
    name="embedding",
)

@embedding_breaker
async def call_embedding(text: str) -> list[float]:
    return await embedding_client.embed(text, timeout=5.0)
```

## Fallback wiring per breaker

```python
# retrieval/hybrid_with_fallback.py
async def retrieve(query: str) -> RetrievalResult:
    try:
        embedding = await call_embedding(query)
        vector_results = await call_vector_search(embedding)
    except pybreaker.CircuitBreakerError:
        logger.warning("embedding_breaker_open", extra={"query_hash": hash_query(query)})
        vector_results = []

    bm25_results = await call_bm25_search(query)  # separate bulkhead pool

    if not vector_results and not bm25_results:
        raise RetrievalUnavailable("all paths failed")

    merged = merge_results(vector_results, bm25_results)
    
    try:
        return await call_reranker(query, merged)
    except pybreaker.CircuitBreakerError:
        return RetrievalResult(chunks=merged[:10], degraded=True, reason="reranker_unavailable")
```

Each breaker failure activates a specific fallback—not a generic error.

## Bulkhead pattern: isolated thread pools

```python
# resilience/bulkheads.py
import asyncio
from concurrent.futures import ThreadPoolExecutor

embedding_pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix="embed")
vector_pool = ThreadPoolExecutor(max_workers=30, thread_name_prefix="vector")
rerank_pool = ThreadPoolExecutor(max_workers=10, thread_name_prefix="rerank")

async def call_vector_search(embedding: list[float]) -> list[Chunk]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(vector_pool, _sync_vector_query, embedding)
```

Separate pools ensure embedding slowness cannot consume all vector search threads. Size pools from capacity planning:

- Embedding pool: match GPU endpoint concurrency limit
- Vector pool: match DB connection pool size
- Rerank pool: match reranker replica capacity

## Bulkhead with semaphores (async)

For async services, semaphores achieve similar isolation:

```python
embedding_sem = asyncio.Semaphore(20)
vector_sem = asyncio.Semaphore(30)

async def call_embedding(text: str) -> list[float]:
    async with embedding_sem:
        return await embedding_client.embed(text)

async def call_vector_search(embedding: list[float]) -> list[Chunk]:
    async with vector_sem:
        return await vector_db.query(embedding, top_k=50)
```

Semaphore limits concurrent calls; combined with circuit breaker, doubly protects downstream.

## Tuning for RAG-specific latency profiles

| Dependency | Typical p95 | Call timeout | Breaker window | Open duration |
|------------|------------|--------------|----------------|---------------|
| Embedding API | 200–800 ms | 5s | 10 requests | 30s |
| Vector DB | 50–200 ms | 2s | 20 requests | 20s |
| Reranker | 100–300 ms | 3s | 10 requests | 30s |
| Redis cache | 1–5 ms | 100ms | 50 requests | 10s |

Embedding has highest variance—tune breaker to open on sustained degradation, not single slow call. Use percentile-based health checks where library supports it.

## Observability

Export breaker state to Prometheus:

```
# HELP rag_circuit_breaker_state Breaker state (0=closed, 1=open, 2=half-open)
rag_circuit_breaker_state{dependency="embedding"} 0

# HELP rag_circuit_breaker_calls_total
rag_circuit_breaker_calls_total{dependency="embedding",result="success"} 15234
rag_circuit_breaker_calls_total{dependency="embedding",result="failure"} 89
rag_circuit_breaker_calls_total{dependency="embedding",result="short_circuit"} 234
```

Alert on:
- Breaker open >5 minutes (dependency genuinely down)
- Frequent open/close cycling (flapping— tune thresholds)
- High short_circuit rate with low user-visible degraded header (silent fallback)

Dashboard: breaker state timeline overlaid with retrieval p95 and fallback activation rate.

## Combining with retries

Retries and circuit breakers interact:

```python
@retry(max_attempts=2, wait_exponential_multiplier=0.1, retry_on=TransientError)
@embedding_breaker
async def call_embedding_with_retry(text: str) -> list[float]:
    return await embedding_client.embed(text)
```

Rule: retry only in CLOSED state. Never retry in OPEN state—fail fast to fallback. Most breaker libraries handle this automatically.

## Testing breaker behavior

Game day injections (see chaos engineering post):

1. Inject 100% embedding failure → verify breaker opens within window
2. Verify BM25 fallback activates with `degraded: true` header
3. Verify vector search still responds (bulkhead isolation)
4. Remove injection → verify HALF-OPEN probe → CLOSED recovery
5. Measure recovery time and cache stampede on breaker close

Unit tests mock dependency failures; integration tests validate end-to-end fallback paths.

## Anti-patterns

- **Single breaker for entire pipeline** — masks which dependency failed
- **No fallback when breaker open** — returns error instead of degraded retrieval
- **Shared thread pool** — bulkhead defeated
- **Breaker threshold too aggressive** — opens on normal embedding variance
- **No half-open probing** — manual intervention required to recover
- **Retry storm before open** — retries amplify load on failing dependency; limit retries

Circuit breakers stop the bleeding; bulkheads prevent contagion. Together they make RAG retrieval fail partially and visibly rather than completely and silently.

## Breaker configuration in service mesh environments

Istio and Linkerd provide outlier detection (passive circuit breaking) at the proxy layer—complement application-level breakers, do not replace them. Proxy outlier detection ejects unhealthy hosts; application breakers handle slow-but-200 responses that outlier detection misses. Configure both: proxy for pod-level failures, application breaker for dependency latency degradation without HTTP errors.

Export breaker state changes as structured logs for post-incident timeline reconstruction. "Embedding breaker opened at 03:14, closed at 03:22" explains retrieval quality dip in incident review better than latency graphs alone.

## Graceful degradation UX during breaker open states

When breakers open, API responses should include structured degraded flag—not just slower or empty results. Return JSON header X-RAG-Degraded: true with reason code (embedding_unavailable, reranker_timeout). Frontend displays subtle indicator: "Search quality may be reduced." Users tolerate degraded search when informed; silent quality drop erodes trust permanently. Product and engineering align on degraded-mode copy before implementing breaker fallbacks.


## Production rollout notes

Load test breaker thresholds quarterly with production-shaped traffic in staging. Thresholds tuned at launch become wrong after architecture changes—new caching layer reduces embedding call rate, making old failure-rate thresholds never trigger. Recalibrate from game day data after major pipeline changes.


Document breaker open state in OpenTelemetry traces as span attribute rag.degraded=true. Distributed traces across retrieval pipeline show exactly which dependency failed during multi-hop requests. Jaeger filter on degraded traces speeds post-incident root cause analysis.


Platform teams publish breaker status dashboard internally so product engineers understand current degradation state during incidents. Transparency reduces duplicate status Slack threads asking 'is retrieval degraded?' when breaker metrics already answer the question.

Review breaker configurations after every major RAG pipeline architecture change—new caching layers and fallback paths invalidate thresholds tuned for the previous design.

## Acceptance criteria for circuit breaker bulkhead patterns

Ship only when staging demonstrates the failure modes you claim to handle. Record the evidence — load test output, chaos result, or screenshot of the alert firing — in the PR. Revisit the settings after the first real incident; production will teach you which timeout or retention value was optimistic. Prefer boring, documented tradeoffs over clever defaults that only exist in one engineer's head.

## Resources

- Michael Nygard, *Release It!* — circuit breaker and bulkhead patterns
- resilience4j documentation
- pybreaker Python library
- Netflix Hystrix design principles (historical reference)
