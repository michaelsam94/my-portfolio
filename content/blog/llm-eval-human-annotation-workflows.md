---
title: "Human Annotation Workflows"
slug: "llm-eval-human-annotation-workflows"
description: "Design human annotation workflows for LLM eval: labeling interfaces, quality control, inter-annotator agreement, active learning, and pipelines that produce training data not arguments."
datePublished: "2024-11-24"
dateModified: "2024-11-24"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "LLM human annotation, data labeling workflow, inter-annotator agreement, RLHF labeling, LLM eval labeling"
faq:
  - q: "How many annotators do I need per item?"
    a: "Two for most classification and quality rating tasks — measure agreement, adjudicate disagreements. Three for nuanced quality scoring or safety labels where error cost is high. Single annotator only for low-stakes triage with spot-check auditing (10% double-labeled)."
  - q: "What inter-annotator agreement score is acceptable?"
    a: "Cohen's kappa above 0.6 is workable for subjective tasks; above 0.8 is strong. Below 0.4 means your rubric is ambiguous or annotators need retraining — fix the guidelines before labeling more data. Report agreement per category, not just aggregate."
  - q: "Build in-house labeling or use a vendor?"
    a: "In-house for domain-specific tasks (your product, your policies) where context matters. Vendors for scale on general tasks (toxicity, sentiment) with clear rubrics. Hybrid works: vendor for first pass, internal experts for adjudication and calibration."
---

Three annotators rated the same chatbot response: helpful, unhelpful, and harmful. Same response. The rubric said "evaluate helpfulness" and didn't define what helpful meant when the answer was confident but wrong. Human annotation workflows fail more often from ambiguous instructions than from lazy annotators. Good workflow design — clear rubrics, proper tooling, quality loops — turns labeling from a bottleneck into a compounding asset.

## Workflow stages

```
Sample selection → Annotator assignment → Labeling → QA review → Adjudication → Dataset export
        ↑                                                              ↓
        └──────────── active learning (high-disagreement items) ───────┘
```

Each stage has different tooling and ownership.

## Sampling strategy

Don't label randomly — prioritize information value:

| Priority | Source | Why |
|----------|--------|-----|
| P0 | Safety flags, P1 feedback | High impact failures |
| P1 | Low model confidence | Uncertain = informative |
| P2 | Random sample | Distribution coverage |
| P3 | High agreement auto-labels | Validate automated scoring |

```python
def sample_for_labeling(queue: Queue, budget: int) -> list[Item]:
    items = []
    items.extend(queue.safety_flags(limit=budget * 0.3))
    items.extend(queue.low_confidence(limit=budget * 0.3))
    items.extend(queue.random(limit=budget * 0.4))
    return dedupe(items)[:budget]
```

## Annotation interface

Annotators need context, not just the model output:

```
┌─────────────────────────────────────────┐
│ User message: "..."                     │
│ Retrieved docs: [expandable chunks]     │
│ Tool trace: search() → 3 results        │
│ Model response: "..."                   │
├─────────────────────────────────────────┤
│ Rate helpfulness: [1-5]                 │
│ Failure mode: [dropdown multi-select]   │
│ Correct response (optional): [text]    │
│ Notes: [text]                           │
└─────────────────────────────────────────┘
```

Show retrieval context — without it, annotators blame the model for retrieval failures.

## Rubric design

Bad rubric: "Rate quality 1–5."

Good rubric:

```
5 - Fully correct, grounded in context, appropriate tone
4 - Correct with minor issues (verbosity, missing citation)
3 - Partially correct, missing key info user needed
2 - Incorrect but not harmful
1 - Incorrect and potentially harmful (wrong policy, PII leak)
```

Include 10–20 worked examples per score level. Annotators reference these during training.

## Quality control

**Gold standard items** — 10% of each batch are pre-labeled items with known answers:

```python
def check_annotator_quality(labels: list, gold: list) -> float:
    accuracy = sum(l == g for l, g in zip(labels, gold)) / len(gold)
    if accuracy < 0.85:
        flag_annotator_for_retraining(annotator_id)
    return accuracy
```

**Inter-annotator agreement**:

```python
from sklearn.metrics import cohen_kappa_score
kappa = cohen_kappa_score(annotator_a_labels, annotator_b_labels)
```

Track kappa per annotator pair and per category. Declining kappa = rubric drift or annotator fatigue.

## Adjudication

When annotators disagree:

1. Auto-adjudicate if 2-of-3 agree (majority vote)
2. Escalate to senior reviewer if all disagree
3. Log adjudication decisions — they become rubric clarifications

```python
if disagreement(item):
    if item.category == "safety":
        escalate_to_senior(item)  # never majority-vote safety
    else:
        item.label = majority_vote(item.labels)
```

## Active learning loop

High-disagreement items are the most valuable training data:

```python
disagreement_score = 1 - (agreement_count / total_annotators)
if disagreement_score > 0.5:
    add_to_few_shot_candidates(item)
    add_to_golden_eval(item, after_adjudication=True)
```

These items clarify model boundaries and improve prompts.

## Throughput and cost

Estimate: 2–5 minutes per item for quality rating with context review. 100 items = 3–8 hours of annotator time.

Optimize:

- Keyboard shortcuts in labeling UI
- Pre-fill suggested labels from model (annotator confirms/corrects)
- Batch similar items (same intent cluster)
- Limit free-text fields — dropdowns scale better

## Data export for downstream use

Export formats:

```json
{
  "id": "ann_4421",
  "input": {"messages": [...], "context": [...]},
  "labels": {
    "helpfulness": 4,
    "failure_modes": ["retrieval_miss"],
    "correct_response": "Our return window is 30 days..."
  },
  "annotators": ["a1", "a2"],
  "agreement": 1.0,
  "adjudicated": false
}
```

Feed into: golden eval sets, few-shot examples, fine-tuning datasets, prompt improvement tickets.

## Inter-annotator agreement metrics

Measure annotation quality before trusting labels:

| Metric | Use for | Threshold |
|---|---|---|
| Cohen's kappa | 2 annotators, categorical labels | >0.6 acceptable, >0.8 good |
| Fleiss' kappa | 3+ annotators | >0.5 acceptable |
| Krippendorff's alpha | Missing data, varied scales | >0.67 acceptable |
| Percent agreement | Quick sanity check | Misleading with imbalanced labels |

```python
from sklearn.metrics import cohen_kappa_score

kappa = cohen_kappa_score(annotator_a_labels, annotator_b_labels)
if kappa < 0.6:
    # Trigger adjudication session — don't use disputed labels in training
    schedule_adjudication(disputed_items)
```

Low kappa on a label category means the rubric is ambiguous — fix the guidelines before annotating more.

## Adjudication workflow

When annotators disagree, a senior reviewer resolves:

```
1. Flag items with kappa < 0.6 or exact disagreement on safety labels
2. Senior annotator reviews both labels + source rubric
3. Decision recorded with rationale
4. Rubric updated if pattern of disagreement found
5. Original annotators notified of decision (calibration feedback)
```

Adjudication sessions are expensive — budget 10–15% of total annotation time. Disputed safety labels always require adjudication; disputed helpfulness scores can use majority vote.

## Active learning for annotation efficiency

Don't annotate randomly — prioritize high-uncertainty examples:

```python
def select_for_annotation(unlabeled_pool, model, n=100):
    predictions = model.predict_proba(unlabeled_pool)
    uncertainty = 1 - predictions.max(axis=1)  # least confident
    return unlabeled_pool.nlargest(n, uncertainty)
```

Model-assisted pre-labeling + human correction is 3–5× faster than annotation from scratch. Annotator confirms or corrects model suggestion rather than writing from blank.

## Failure modes

- **No agreement measurement** — noisy labels in training data; model learns noise
- **Single annotator for safety labels** — no quality check on critical outputs
- **Rubrics too vague** — low kappa; wasted annotation budget
- **Random sampling for annotation** — misses edge cases model fails on
- **Annotations not linked to model version** — can't trace which labels trained which model

## Production checklist

- Cohen's kappa computed per label category after each annotation batch
- Adjudication workflow for disagreements below threshold
- Active learning prioritizes high-uncertainty examples
- Model pre-labeling with human confirm/correct workflow
- Rubric updated when systematic disagreement patterns found
- Annotation exports linked to model and prompt versions

Measure inter-annotator agreement (Cohen's kappa) weekly — kappa below 0.6 means your rubric is ambiguous, not that annotators are wrong.

## Resources

- [Label Studio open-source labeling](https://labelstud.io/guide/)
- [Argilla LLM feedback collection](https://docs.argilla.io/latest/)
- [Cohen's kappa interpretation (Landis & Koch)](https://www.jstor.org/stable/2529310)
- [Snorkel programmatic labeling concepts](https://snorkel.ai/snorkel-flow/)
- [Scale AI data labeling best practices](https://scale.com/guides/data-labeling)
