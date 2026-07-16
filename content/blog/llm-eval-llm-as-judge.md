---
title: "LLM-as-a-Judge Evaluation"
slug: "llm-eval-llm-as-judge"
description: "Use LLMs to evaluate LLM outputs: judge prompts, rubric design, position bias mitigation, correlation with humans, and when automated judges replace annotation."
datePublished: "2024-11-27"
dateModified: "2024-11-27"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "LLM as judge, automated LLM evaluation, G-Eval, LLM judge prompt, model evaluation automation"
faq:
  - q: "Can an LLM judge replace human evaluation?"
    a: "Partially. LLM judges correlate well with humans on clarity, relevance, and format compliance (0.7–0.85 correlation with good rubrics). They poorly judge factual accuracy without ground truth, subtle safety issues, and domain-specific correctness. Use judges for scale; humans for calibration and high-stakes decisions."
  - q: "Which model should be the judge?"
    a: "Use a model at least as capable as the one being evaluated, often one tier higher. GPT-4o judging GPT-4o-mini outputs works. GPT-4o-mini judging GPT-4o outputs misses nuance. Never use the same model instance that generated the output — cache contamination and self-preference bias."
  - q: "How do I reduce position bias in pairwise judging?"
    a: "Run each comparison twice with swapped order (A/B then B/A). Accept only when both runs agree. Alternatively, use single-response absolute scoring instead of pairwise comparison — no position bias, but less sensitive to small quality differences."
---

Human review doesn't scale to 10,000 daily responses. Offline metrics like BLEU score nonsense on conversational AI. LLM-as-a-judge — using a strong model to rate outputs against a rubric — fills the gap between cheap automated checks and expensive human labeling. It's imperfect, biased in known ways, and still better than flying blind.

## Judge patterns

**Absolute scoring** — rate one response:

```python
JUDGE_PROMPT = """Evaluate the assistant response on a 1-5 scale.

User question: {question}
Context provided: {context}
Assistant response: {response}

Criteria:
- Groundedness: Is every claim supported by context?
- Completeness: Does it fully answer the question?
- Clarity: Is it well-organized and concise?

Return JSON: {"groundedness": int, "completeness": int, "clarity": int, "overall": int, "reasoning": str}
"""
```

**Pairwise comparison** — pick the better of two responses:

```python
PAIRWISE_PROMPT = """Which response better answers the user's question?
Consider accuracy, completeness, and helpfulness.

Question: {question}
Response A: {response_a}
Response B: {response_b}

Return JSON: {"winner": "A" | "B" | "tie", "reason": str}
"""
```

Pairwise is more sensitive for comparing prompt variants. Absolute is simpler and avoids position bias with single responses.

## Position bias mitigation

LLM judges favor the first response in pairwise comparisons ~55–65% of the time. Fix:

```python
async def unbiased_pairwise(question: str, resp_a: str, resp_b: str) -> str:
    r1 = await judge_pairwise(question, resp_a, resp_b)  # A first
    r2 = await judge_pairwise(question, resp_b, resp_a)  # B first
    if r1.winner == "A" and r2.winner == "B":  # swapped order, B was first → B wins
        return "A"
    if r1.winner == "B" and r2.winner == "A":
        return "B"
    return "tie"  # disagree → human review or third pass
```

## Calibrating against humans

Before trusting the judge at scale:

1. Label 100–200 examples manually
2. Run judge on same set
3. Compute correlation (Pearson for scores, Cohen's kappa for categories)
4. Tune rubric until correlation exceeds your threshold (typically 0.75+)

```python
human_scores = load_human_labels("calibration_set.jsonl")
judge_scores = [await judge(item) for item in calibration_set]
correlation = pearsonr(human_scores, judge_scores)
assert correlation > 0.75, f"Judge miscalibrated: r={correlation}"
```

Recalibrate when changing judge model, rubric, or product domain.

## G-Eval style chain-of-thought judging

Ask the judge to reason before scoring — improves correlation with humans:

```python
GEVAL_PROMPT = """
Evaluate step-by-step:
1. Identify what the user asked
2. Check each claim in the response against context
3. Note missing information
4. Assign scores

Then output JSON scores.
"""
```

CoT judging costs more tokens but reduces arbitrary scores.

## What judges get wrong

| Failure | Mitigation |
|---------|------------|
| Confident hallucinations rated highly | Require citation checking step |
| Verbosity rewarded | Explicit conciseness criterion |
| Self-preference (same model family) | Use different model as judge |
| Missing domain knowledge | Provide reference answers in rubric |
| Length bias (longer = better) | Blind token count; penalize excess length |

Add reference answers for factual evals when ground truth exists — judge compares to reference, not its own knowledge.

## Production usage

**CI regression** — judge scores new prompt vs baseline on golden set:

```python
baseline_scores = run_judge(prompt_v2, golden_set)
if mean(baseline_scores) < mean(control_scores) - 0.3:
    fail_build("Judge score regression")
```

**Online sampling** — judge 5% of production responses, alert on score drops.

**Not for** — real-time user-facing decisions, safety blocking (use dedicated classifiers), billing disputes.

## Cost management

Judge calls double your eval cost. Reduce:

- Judge with mini model for screening, frontier for borderline cases
- Cache judge results by (input_hash, output_hash)
- Batch eval runs overnight
- Sample rather than judge 100%

## Judge prompt design

Effective judge prompts use structured rubrics, not open-ended scoring:

```python
JUDGE_PROMPT = """
Evaluate the assistant response on a scale of 1-5 for each criterion.

User question: {question}
Assistant response: {response}
Reference answer (if available): {reference}

Criteria:
1. Correctness: Is the response factually accurate? (1=wrong, 5=perfect)
2. Completeness: Does it fully address the question? (1=missing key info, 5=complete)
3. Conciseness: Is it appropriately brief? (1=verbose, 5=concise)

Respond in JSON: {"correctness": N, "completeness": N, "conciseness": N, "reasoning": "..."}
"""
```

Structured JSON output enables automated parsing and per-criterion tracking. Open-ended "rate 1-10" prompts produce inconsistent scores across judge runs.

## Position bias mitigation

LLM judges favor the first response in pairwise comparisons:

```python
def unbiased_pairwise_judge(response_a: str, response_b: str, question: str) -> str:
    # Run twice with swapped order
    result1 = judge(f"A: {response_a}\nB: {response_b}", question)
    result2 = judge(f"A: {response_b}\nB: {response_a}", question)
    # If both agree on winner regardless of order, confident result
    if result1.winner == result2.winner:
        return result1.winner
    return "tie"  # position bias detected; don't count
```

Swap A/B order and require agreement. Discard ties from win-rate calculations — they indicate genuine ambiguity, not quality difference.

## Calibrating judge against human labels

Validate judge accuracy before trusting it in CI:

```python
def calibrate_judge(judge_fn, human_labels: list[dict]) -> float:
    agreements = 0
    for item in human_labels:
        judge_score = judge_fn(item["question"], item["response"])
        human_score = item["human_score"]
        if abs(judge_score - human_score) <= 1:  # within 1 point
            agreements += 1
    correlation = agreements / len(human_labels)
    assert correlation > 0.7, f"Judge correlation {correlation:.2f} below threshold"
    return correlation
```

Collect 100+ human-labeled examples. Judge must correlate >0.7 with human scores before blocking CI on judge regression.

## Failure modes

- **Judge used for real-time safety blocking** — latency and cost prohibitive; use classifiers
- **Position bias not mitigated** — pairwise comparisons systematically favor first response
- **Judge not calibrated against humans** — CI blocks on judge noise, not real regression
- **Length bias unchecked** — judge rewards verbose responses
- **Same model as judge and generator** — self-preference bias inflates scores

## Production checklist

- Judge prompt uses structured JSON rubric with per-criterion scores
- Position bias mitigated by A/B order swapping in pairwise comparisons
- Judge calibrated against 100+ human labels (correlation >0.7)
- Different model used for judge vs generator (avoid self-preference)
- Judge used for CI regression and 5% production sampling only
- Length bias checked: correlate judge score with response token count

## Resources

- [G-Eval paper (Liu et al.)](https://arxiv.org/abs/2303.16634)
- [MT-Bench and LLM judge methodology](https://arxiv.org/abs/2306.05685)
- [AlpacaEval automatic evaluation](https://github.com/tatsu-lab/alpaca_eval)
- [LangChain evaluation with LLM judges](https://python.langchain.com/docs/concepts/evaluation/)
- [Anthropic model grading best practices](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering)
