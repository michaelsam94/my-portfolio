---
title: "RAG: Chaos Monkey Game Days"
slug: "rag-chaos-monkey-game-days"
description: "Structured chaos experiments for RAG pipelines—kill embedding pods during retrieval load, inject vector DB latency, and validate that circuit breakers and fallbacks keep answers flowing."
datePublished: "2026-04-02"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Chaos"]
keywords: "chaos engineering, game day, Chaos Monkey, RAG resilience, fault injection, LitmusChaos, Gremlin, embedding failure, vector DB outage"
faq:
  - q: "What RAG failure modes should chaos game days target?"
    a: "Target the expensive dependencies: embedding API timeout or 503, vector database connection exhaustion, reranker OOM kill, Redis cache total loss, and Kafka consumer lag spike. These cause user-visible retrieval degradation without obvious HTTP 500 errors—exactly the failures that slip past unit tests."
  - q: "How is a RAG game day different from generic Kubernetes chaos?"
    a: "Generic chaos kills random pods. RAG game days inject failures at retrieval-critical paths with quality metrics as success criteria—not just availability. Pass criteria include nDCG staying above threshold during embedding degradation, not merely HTTP 200 responses with empty context."
  - q: "What tools run chaos experiments in Kubernetes RAG deployments?"
    a: "LitmusChaos and Chaos Mesh provide Kubernetes-native experiments (pod kill, network latency, CPU stress). Gremlin offers managed game day orchestration. Custom scripts inject faults at application level—embedding API mock failures, cache flush, vector DB query timeout."
---
The quarterly game day scenario was simple on paper: kill 50% of embedding service pods during peak retrieval load and observe behavior for thirty minutes. Within eight minutes, retrieval p95 latency tripled—but error rates stayed at zero because every request returned HTTP 200 with empty context and a generic "I couldn't find relevant information" message. Quality had collapsed silently. The circuit breaker opened correctly; the fallback was worse than failing loudly. That game day produced three concrete fixes: BM25-only fallback when embedding fails, explicit degraded-mode header in responses, and a quality-metric alert tied to context-empty rate.

Chaos engineering for RAG is not about proving Kubernetes self-heals pod crashes. It is about validating that retrieval degradation paths preserve answer quality within defined bounds—or fail visibly when they cannot.

## RAG failure modes worth injecting

Prioritize experiments by user impact and likelihood:

| Failure | Injection method | Expected graceful behavior |
|---------|-------------------|---------------------------|
| Embedding API 503 | Mock/fault injection | BM25 fallback, cached embeddings |
| Vector DB timeout | Network latency (tc/netem) | Retry with backoff, partial results |
| Reranker OOM | Pod memory limit kill | Skip rerank, return bi-encoder order |
| Redis cache flush | FLUSHDB in staging | Stampede prevention holds, latency spike bounded |
| Kafka consumer stop | Scale to 0 | Stale index served, freshness alert |
| LLM context overflow | Adversarial long retrieval | Truncation with priority ranking |

Generic pod chaos (random kill) catches less than targeted dependency failure for RAG because retrieval pipelines have multiple fallback layers that mask degradation.

## Game day structure

**Week before:**
- Define hypothesis: "During embedding outage, 90% of queries return relevant context via BM25 fallback"
- Set pass/fail metrics: context-empty rate <5%, nDCG@5 >0.7, p95 <2s
- Pre-warm staging with production-shaped traffic (k6, Locust)
- Notify stakeholders; freeze unrelated deploys

**Day of:**
- Baseline measurement (15 min normal traffic)
- Inject fault (document start time)
- Observe (30 min minimum—long enough for cache effects)
- Escalate fault (increase severity if system absorbs too easily)
- Rollback fault
- Recovery observation (15 min)
- Blameless retro within 48 hours

**Success criteria must include quality**, not just availability:

```yaml
# game-day/pass-criteria.yaml
metrics:
  - name: context_empty_rate
    threshold: 0.05  # max 5% empty context
    query: rate(rag_context_empty_total[5m]) / rate(rag_queries_total[5m])
  - name: ndcg_at_5
    threshold: 0.70
    source: shadow_eval_pipeline
  - name: p95_latency
    threshold_ms: 2000
  - name: error_rate
    threshold: 0.01  # 1% hard errors acceptable
```

## LitmusChaos experiments for RAG

Install LitmusChaos in staging:

```yaml
# chaos/embedding-pod-kill.yaml
apiVersion: litmuschaos.io/v1alpha1
kind: ChaosEngine
metadata:
  name: rag-embedding-chaos
  namespace: rag-staging
spec:
  appinfo:
    appns: rag-staging
    applabel: "app=embedding-service"
    appkind: deployment
  chaosServiceAccount: litmus-admin
  experiments:
    - name: pod-delete
      spec:
        components:
          env:
            - name: TOTAL_CHAOS_DURATION
              value: "1800"  # 30 minutes
            - name: CHAOS_INTERVAL
              value: "120"   # kill every 2 min
            - name: FORCE
              value: "true"
            - name: PODS_AFFECTED_PERC
              value: "50"
```

Network latency to vector DB:

```yaml
# chaos/vectordb-latency.yaml
    - name: pod-network-latency
      spec:
        components:
          env:
            - name: NETWORK_LATENCY
              value: "500"  # 500ms added latency
            - name: TARGET_CONTAINER
              value: "retrieval-service"
            - name: DESTINATION_IPS
              value: "10.0.5.0/24"  # vector DB subnet
            - name: TOTAL_CHAOS_DURATION
              value: "900"
```

Run during business hours in staging with synthetic load—not production until maturity proven.

## Application-level fault injection

Infrastructure chaos misses application fallback paths. Inject at API boundary:

```python
# fault_injection/embedding_chaos.py
import os
import random
from functools import wraps

FAULT_ENABLED = os.getenv("CHAOS_EMBEDDING_FAILURE_RATE", "0")
FAILURE_RATE = float(FAULT_ENABLED) if FAULT_ENABLED else 0.0

def chaos_embed(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if FAILURE_RATE > 0 and random.random() < FAILURE_RATE:
            raise EmbeddingServiceUnavailable("chaos injection")
        return await func(*args, **kwargs)
    return wrapper

@chaos_embed
async def compute_query_embedding(text: str) -> list[float]:
    return await embedding_client.embed(text)
```

Enable via environment in staging:

```yaml
env:
  - name: CHAOS_EMBEDDING_FAILURE_RATE
    value: "0.3"  # 30% embedding failures
```

Measure fallback activation rate and resulting retrieval quality.

## Chaos Monkey heritage and modern equivalents

Netflix Chaos Monkey randomly terminates production instances. Lessons for RAG:

- **Start in staging.** RAG quality regressions are subtle—production chaos without quality metrics causes silent trust erosion.
- **Minimize blast radius.** Target one dependency at a time. Simultaneous embedding + vector DB failure teaches nothing actionable.
- **Automate rollback.** Chaos experiments self-terminate; alert if manual intervention needed.
- **Business hours.** RAG game days in staging during working hours maximize learning; production chaos requires mature observability.

Modern equivalents: Gremlin (managed), Chaos Mesh (CNCF), LitmusChaos (CNCF), AWS FIS (Fault Injection Simulator).

## Observing RAG behavior during chaos

Dashboard panels for game day:

1. Query QPS and error rate (infrastructure)
2. Context-empty rate and avg chunks returned (RAG-specific)
3. Fallback path activation (BM25-only, cache-hit, degraded-mode)
4. Embedding API call rate vs query rate (should diverge during fallback)
5. Shadow nDCG@5 (quality)
6. Circuit breaker state per dependency

Log structured events when fallbacks activate:

```python
logger.warning(
    "retrieval_fallback_activated",
    extra={
        "fallback_type": "bm25_only",
        "query_id": query_id,
        "reason": "embedding_unavailable",
        "chaos_active": True,
    },
)
```

Enables post-game-day analysis of fallback frequency and quality correlation.

## Common discoveries from RAG game days

Teams consistently find:

- **Silent empty context** — HTTP 200 with no retrieved chunks, LLM hallucinates freely
- **Cache stampede on recovery** — fault removal causes synchronized cache miss cliff
- **No BM25 fallback wired** — vector-only retrieval fails completely on embedding outage
- **Reranker blocking** — cross-encoder timeout blocks entire retrieval, not just rerank step
- **Stale index served without indicator** — Kafka consumer lag during fault, no freshness header
- **Circuit breaker never tested** — configured but threshold wrong, never opens

Each finding becomes a tracked remediation item with re-test in next game day.

## Building game day maturity

**Level 1:** Manual pod delete in staging, observe dashboards
**Level 2:** LitmusChaos scheduled experiments with pass/fail metrics
**Level 3:** Application fault injection with quality gates
**Level 4:** Production game days with automated rollback and customer communication plan
**Level 5:** Continuous chaos (Chaos Mesh cron experiments) with SLO-based abort

Most RAG teams should target Level 2–3 within first year of production.

## Building organizational buy-in for RAG game days

Start with engineering-only staging game days, publish results in blameless retro format, then invite product and support observers. Showing quality collapse during embedding failure—HTTP 200 with empty context—builds organizational understanding of why RAG SLOs need quality metrics, not just availability. Executive summary: "We learned our fallback returns wrong answers silently" drives investment in degraded-mode UX faster than technical postmortems alone.

## Post-game-day remediation tracking

Every game day produces findings rated P0–P3. P0 (silent quality collapse, data leak path) fix within one sprint. P1 (degraded fallback missing) fix within two sprints. Track remediation completion rate—teams that run game days without fixing findings develop audit theater, not resilience. Re-test fixed items in next game day scenario rotation. Maintain game day scenario library in git with last-run date and pass/fail history per scenario.


## Production rollout notes

Document expected vs observed behavior for each chaos scenario in a shared spreadsheet. Column for hypothesis, pass criteria, actual metrics, finding severity, remediation ticket. Over time this becomes a resilience maturity scorecard: percentage of scenarios passing, mean remediation time, repeat findings indicating systemic gaps.


Invite customer success to observe game day demonstrating degraded retrieval UX. CS team learns what to tell customers during partial outages—reduces support ticket volume when real incidents occur. Prepare customer-facing status message templates as game day deliverable.

## Common regressions around chaos monkey game days

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to chaos monkey game days and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.

## Resources

- Principles of Chaos Engineering (principlesofchaos.org)
- LitmusChaos experiment catalog
- Gremlin game day runbook templates
- Netflix chaos engineering blog archive
