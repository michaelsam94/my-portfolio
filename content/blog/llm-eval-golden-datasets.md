---
title: "Building Golden Eval Datasets"
slug: "llm-eval-golden-datasets"
description: "Build golden eval datasets for LLM apps: case selection, labeling standards, versioning, regression CI, and the properties that make eval sets trustworthy."
datePublished: "2024-11-21"
dateModified: "2024-11-21"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "golden eval dataset LLM, LLM evaluation dataset, regression testing LLM, eval set construction, LLM quality benchmark"
faq:
  - q: "How many examples should a golden eval set contain?"
    a: "Start with 50–100 covering your critical paths, then grow to 200–500 as you find failures in production. Below 30, metrics swing wildly between runs. Above 1000, maintenance cost dominates unless you automate labeling. Stratify by intent, difficulty, and language — not just total count."
  - q: "Who should label golden eval examples?"
    a: "Domain experts or senior support/engineering staff who know correct behavior. Not the person who wrote the prompt — they're biased toward their own wording. Two independent labelers on 20% of cases to measure inter-annotator agreement."
  - q: "How often should I update the golden set?"
    a: "Add cases weekly from production failures (feedback loop). Review full set monthly for stale expectations — product changes make old 'correct' answers wrong. Version the dataset in git; never silently edit cases without a changelog."
---

Your LLM prompt change shipped with confidence because "evals looked fine." The eval set had 12 examples, all written by the engineer who wrote the prompt, none covering the refund edge case that generated 40 support tickets. A golden eval dataset is the regression suite for non-deterministic software — and like any test suite, it's only as good as the cases you bothered to include.

## Properties of a good golden set

| Property | Why it matters |
|----------|----------------|
| Representative | Covers real production query distribution |
| Adversarial | Includes known failure modes and edge cases |
| Stable expectations | Expected outputs don't change weekly |
| Independently labeled | Not labeled by prompt author alone |
| Versioned | Git-tracked with changelog |

Missing any one property produces false confidence.

## Case structure

```yaml
# eval/golden/refund_014.yaml
id: refund_014
added: "2024-11-21"
source: "production_feedback_fb_8821"
tags: [billing, refund, edge_case]
input:
  messages:
    - role: user
      content: "I bought the annual plan yesterday but want a refund — I meant to pick monthly."
context:
  retrieval_docs: ["pricing-policy-v3", "refund-faq"]
expected:
  must_include: ["30-day", "annual", "prorated"]
  must_not_include: ["no refunds", "contact lawyer"]
  must_cite: true
  max_tokens: 300
  tool_calls: []  # should NOT call refund API without confirmation
metadata:
  difficulty: hard
  labeler: "sarah@company.com"
```

Separate `must_include`, `must_not_include`, and behavioral expectations (`must_cite`, `tool_calls`). Free-text exact match is too brittle.

## Building the initial set

1. **Mine production logs** — sample 500 recent queries, cluster by embedding
2. **Pick 5–10 clusters** representing top intents
3. **Add 5 examples per cluster** — include one edge case each
4. **Add every P0 incident** from the last quarter
5. **Label with expected behavior**, not expected exact wording

```python
def sample_stratified(queries: list, n_per_cluster: int = 5) -> list:
    clusters = embed_and_cluster(queries, k=10)
    return [sample(c, n_per_cluster) for c in clusters]
```

## Scoring functions

Match eval type to expectation type:

```python
def score_case(output: str, expected: Expected) -> CaseResult:
    checks = []
    checks.append(all(kw in output.lower() for kw in expected.must_include))
    checks.append(not any(kw in output.lower() for kw in expected.must_not_include))
    checks.append(citation_present(output) if expected.must_cite else True)
    checks.append(len(output.split()) <= expected.max_tokens * 1.3)
    return CaseResult(passed=all(checks), details=checks)
```

For RAG evals, add retrieval metrics:

- Expected doc in top-K retrieved
- Answer grounded in retrieved context (RAGAS faithfulness)

For agents, add trajectory checks:

- Called correct tools in correct order
- Didn't call blocked tools

## CI integration

```yaml
# .github/workflows/llm-eval.yml
- name: Run golden eval
  run: python -m evals.run --dataset eval/golden/ --threshold 0.92
```

Block deploy if aggregate score drops below threshold or any P0 case fails:

```python
P0_CASES = {"refund_014", "safety_003", "pii_007"}

results = run_eval(dataset)
if any(not r.passed for r in results if r.id in P0_CASES):
    sys.exit(1)
if results.pass_rate < 0.92:
    sys.exit(1)
```

Run on prompt changes, model changes, and retrieval config changes — not every code deploy unless LLM path touched.

## Growing from failures

Every production failure becomes a case:

```python
async def on_feedback(event: FeedbackEvent):
    if event.thumbs == "down" and event.reviewed_label:
        await eval_repo.propose_case(
            input=event.input,
            expected=event.reviewer_expected,
            source=event.id,
        )
```

Weekly review of proposed cases — accept, edit, or reject. Rejected cases still inform prompt fixes without polluting the golden set.

## Avoiding eval overfitting

If you iterate on prompts until 100% pass rate, you've overfit to 50 examples. Mitigate:

- Hold out 20% as a private test set nobody optimizes against
- Rotate in new production samples monthly
- Track pass rate on held-out set separately
- Accept 90–95% on golden set — perfection means stale or too easy

## Versioning

```
eval/
  golden/
    v1/   # archived
    v2/   # current
  CHANGELOG.md
```

When product behavior intentionally changes (new refund policy), bump dataset version and update expectations in one PR with the prompt change.

## CI integration

Golden datasets run on every prompt/model change:

```yaml
# GitHub Actions
- name: Run LLM evals
  run: |
    python eval/run.py --dataset golden/v2 --model ${{ env.MODEL_VERSION }}
    python eval/compare.py --baseline main --threshold 0.02
```

Fail CI if pass rate drops more than 2% vs main branch. Block deploy on regression — cheaper than production incident.

## Case authoring guidelines

Good golden cases are:

- **Specific** — "Refund order 4521" not "Handle refund"
- **Edge cases** — empty cart, expired subscription, multi-currency
- **Adversarial** — prompt injection attempts, out-of-scope requests
- **Stable** — expected output doesn't change with today's date

Bad cases: assertions on exact wording when paraphrase is acceptable. Use semantic similarity or structured output validation instead of string match.

## Metric selection

| Task type | Metrics |
|-----------|---------|
| Classification | Accuracy, F1 per class |
| Generation | LLM-judge + human spot-check |
| RAG | Faithfulness, context recall |
| Tool use | Trajectory match, arg correctness |

One metric never suffices — pair automated scores with weekly human review of 20 random cases.

Pair with [LLM eval human annotation workflows](https://blog.michaelsam94.com/llm-eval-human-annotation-workflows/) when building review pipelines for golden dataset maintenance.

## Common production mistakes

Teams get eval golden datasets wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around eval golden datasets break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Resources

- [OpenAI evals framework](https://github.com/openai/evals)
- [Ragas evaluation for RAG](https://docs.ragas.io/)
- [LangSmith dataset management](https://docs.smith.langchain.com/evaluation/how_to_guides/datasets)
- [Braintrust eval platform](https://www.braintrust.dev/docs/guides/evals)
- [HELM benchmark methodology](https://crfm.stanford.edu/helm/latest/)
