---
title: "Detecting and Mitigating Hallucinations"
slug: "llm-hallucination-detection-mitigation"
description: "Detect and reduce LLM hallucinations in production: grounding checks, citation verification, confidence scoring, retrieval requirements, and architectural patterns that limit fabrication."
datePublished: "2024-12-09"
dateModified: "2024-12-09"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "LLM hallucination detection, reduce hallucinations RAG, grounded generation, hallucination mitigation, LLM factuality"
faq:
  - q: "Can you eliminate LLM hallucinations entirely?"
    a: "No — current models confabulate by nature, especially without grounding context. You can reduce frequency from ~15–30% on open questions to under 5% on grounded RAG with citation requirements and verification layers. The goal is making hallucinations rare, detectable, and non-actionable — not impossible."
  - q: "What is the most effective anti-hallucination technique for RAG?"
    a: "Require citations tied to retrieved chunks and reject responses where claims aren't supported by cited text. Combine with retrieval quality monitoring — most 'hallucinations' in RAG apps are actually retrieval failures where the model fills gaps from parametric knowledge."
  - q: "How do I detect hallucinations without ground truth?"
    a: "Use NLI (natural language inference) models to check if each claim is entailed by retrieved context. LLM-as-judge with the context provided. Cross-reference structured data sources. Flag responses with low retrieval overlap or high parametric-knowledge patterns ('I believe', unsupported specifics)."
---

The chatbot told a customer your enterprise plan includes dedicated Slack support. It doesn't. The model wasn't lying — it generated a plausible answer when retrieval returned nothing about Slack. Hallucination is the default behavior when context is missing or ignored. Detection and mitigation aren't prompt hacks; they're architectural requirements for any LLM app where wrong answers have consequences.

## Taxonomy

Not all hallucinations are equal:

| Type | Example | Primary fix |
|------|---------|-------------|
| Intrinsic | Contradicts provided context | Stronger grounding prompts, NLI check |
| Extrinsic | Unsupported by any source | Retrieval improvement, "I don't know" training |
| Fabrication | Invented citations, fake data | Citation verification |
| Reasoning error | Wrong conclusion from correct facts | CoT verification, calculator tools |

Diagnose the type before picking a fix.

## Grounding architecture

```
Query → Retrieve → [Empty? → "I don't know" response, STOP]
                → Pack context → Generate with citation requirement
                → Verify claims against context → Post to user
```

The empty retrieval short-circuit prevents the most common hallucination path:

```python
chunks = await retrieve(query, tenant_id)
if not chunks or max(c.score for c in chunks) < RELEVANCE_THRESHOLD:
    return Response(
        "I couldn't find relevant information in our documentation. "
        "Let me connect you with support.",
        confidence="low",
    )
```

Don't let the model freestyle when retrieval fails.

## Citation requirements

Force structured citations in the prompt:

```python
SYSTEM = """
Answer ONLY using the provided context. For every factual claim,
include a citation [doc_id:chunk_id]. If context doesn't contain
the answer, say "I don't have information about that."
"""
```

Verify post-generation:

```python
def verify_citations(response: str, chunks: list[Chunk]) -> VerificationResult:
    claims = extract_cited_claims(response)
    failures = []
    for claim in claims:
        source = find_chunk(claim.citation, chunks)
        if not source:
            failures.append(f"Invalid citation: {claim.citation}")
        elif not nli_entails(source.text, claim.text):
            failures.append(f"Unsupported: {claim.text}")
    return VerificationResult(passed=len(failures) == 0, failures=failures)
```

NLI models (DeBERTa-based cross-encoders) check entailment cheaply without another LLM call.

## Hallucination detection signals

Score responses before delivery:

```python
@dataclass
class HallucinationSignals:
    retrieval_max_score: float       # low = likely gap-fill
    citation_coverage: float         # % claims with valid citations
    nli_support_rate: float          # % claims entailed by context
    hedging_language: bool           # "I think", "probably"
    numeric_claims_unverified: int   # numbers not in context

def risk_score(signals: HallucinationSignals) -> float:
    score = 0.0
    if signals.retrieval_max_score < 0.7: score += 0.3
    if signals.citation_coverage < 0.8: score += 0.3
    if signals.nli_support_rate < 0.7: score += 0.3
    if signals.numeric_claims_unverified > 0: score += 0.2
    return min(score, 1.0)
```

High risk → add disclaimer, refuse to answer, or escalate to human.

## Mitigation techniques

**Tool use for facts** — dates, math, lookups go through tools, not parametric knowledge:

```python
# Bad: "What's 847 * 293?" → model calculates
# Good: model calls calculator(847, 293)
```

**Structured output** — constrain to fields extractable from context.

**Self-consistency** — generate 3 answers, keep claims appearing in 2+ (expensive, high-stakes only).

**Fine-tuning on "I don't know"** — train/refine on examples where correct behavior is abstention.

## Measuring hallucination rate

Use RAGAS or custom evals:

```python
metrics = {
    "faithfulness": faithfulness_score(answer, context),  # RAGAS
    "hallucination_rate": sum(not faithful) / total,
}
```

Track in production by sampling and human review. Target < 5% for customer-facing factual Q&A.

## User-facing patterns

When uncertainty is detected:

- "Based on our documentation [link], ..." — grounded, citable
- "I'm not certain, but..." — honest hedging (better than confident wrong)
- "I couldn't find this in our docs" — abstention

Never present high-risk responses with the same UI confidence as verified ones.

## Citation grounding verification

Verify every factual claim against retrieved context:

```python
async def verify_citations(answer: str, context_chunks: list[str]) -> VerificationResult:
    claims = extract_claims(answer)  # sentence-level factual statements
    unsupported = []
    for claim in claims:
        supported = any(
            nli_entailment(claim, chunk) > 0.7
            for chunk in context_chunks
        )
        if not supported:
            unsupported.append(claim)
    return VerificationResult(
        faithfulness=1 - len(unsupported) / max(len(claims), 1),
        unsupported_claims=unsupported,
    )
```

NLI (Natural Language Inference) models check if context entails each claim. Claims without support get flagged or removed before presenting to user.

## Hallucination rate by domain

Different domains have different acceptable hallucination rates:

| Domain | Target rate | Detection method |
|---|---|---|
| Legal/medical | <1% | Human review + NLI |
| Customer support FAQ | <5% | RAGAS faithfulness |
| Creative writing | N/A | Not applicable |
| Code generation | <2% | Test execution |
| Financial data | <0.1% | Structured output + validation |

Set domain-specific thresholds — don't apply one global rate across all features.

## Production monitoring pipeline

Sample production responses for hallucination scoring:

```python
async def production_hallucination_monitor():
    sample = await sample_production_requests(rate=0.05)  # 5% sample
    for request in sample:
        if not request.has_retrieval_context:
            continue
        score = await faithfulness_score(request.answer, request.context)
        await metrics.record("hallucination.faithfulness", score)
        if score < 0.7:
            await review_queue.add(request, priority="high")
            await alert_if_rate_exceeds(threshold=0.05, window_minutes=60)
```

Alert when hallucination rate exceeds threshold over rolling window — indicates retrieval degradation or prompt drift.

## Failure modes

- **No faithfulness check on RAG answers** — hallucinated citations reach users
- **Same UI for verified and unverified** — users trust hallucinated content equally
- **Self-consistency without cost cap** — 3× inference cost on every request
- **Hallucination rate not tracked in production** — degradation discovered via support tickets
- **Abstention not trained** — model confabulates instead of saying "I don't know"

## Production checklist

- RAGAS faithfulness or NLI verification on all RAG responses
- Unsupported claims flagged or removed before user presentation
- Domain-specific hallucination rate targets defined
- 5% production sample scored and monitored with alerting
- Abstention examples in fine-tuning data for high-stakes domains
- UI distinguishes verified (with citation) vs unverified responses

Ground every factual claim with retrieval citation — hallucination rate drops more from RAG than from prompt pleading alone.

## Resources

- [RAGAS faithfulness metric](https://docs.ragas.io/en/stable/concepts/metrics/faithfulness.html)
- [SelfCheckGPT hallucination detection](https://arxiv.org/abs/2305.14661)
- [FActScore fine-grained factual evaluation](https://arxiv.org/abs/2305.14251)
- [Vectara hallucination leaderboard](https://github.com/vectara/hallucination-leaderboard)
- [Anthropic reducing hallucinations guide](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)
