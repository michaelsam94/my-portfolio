---
title: "Zero-Shot Classification with LLMs"
slug: "llm-classification-zero-shot"
description: "Classify text without training data using LLMs: prompt design, label schemas, confidence calibration, cost vs fine-tuned models, and production patterns that beat generic zero-shot."
datePublished: "2024-11-03"
dateModified: "2024-11-03"
tags: ["AI", "LLM", "Machine Learning"]
keywords: "zero-shot classification LLM, text classification prompt, LLM labels, zero-shot vs fine-tuned, production text classifier"
faq:
  - q: "When is zero-shot LLM classification good enough?"
    a: "When you have fewer than 20 labels, limited labeled data (< 200 examples), rapidly changing label sets, or need to ship this week. Once you have 500+ labeled examples per class and stable labels, a fine-tuned small model or embedding classifier is usually cheaper and more consistent at scale."
  - q: "How do I handle imbalanced classes in zero-shot?"
    a: "Describe rare classes with more detail in the prompt — definition, examples, counter-examples. Add explicit instruction to not default to the majority class. Measure per-class recall in evals; aggregate accuracy hides failures on rare but important labels like 'fraud' or 'safety'."
  - q: "Structured output or free-text labels?"
    a: "Always structured. Use JSON schema, function calling, or logit bias toward valid labels. Free-text classification invites format drift ('Billing' vs 'billing' vs 'Billing Issue') that breaks downstream routing."
---

You need to classify support tickets into twelve categories by Friday. Training a BERT model takes labeled data you don't have and a ML engineer who's booked until next sprint. Zero-shot classification — describing labels in a prompt and asking the LLM to pick one — gets you to 80% accuracy in an afternoon. The other 20% is prompt design, eval discipline, and knowing when to stop zero-shoting and fine-tune.

## Basic zero-shot prompt

```python
CLASSIFY_PROMPT = """Classify the following text into exactly one category.

Categories:
- billing: payment issues, invoices, refunds, subscription charges
- technical: bugs, errors, feature not working, performance
- account: login, password, profile changes, deletion
- shipping: delivery status, tracking, damaged packages
- other: anything that doesn't clearly fit above

Text: {text}

Return JSON: {{"label": "<category>", "confidence": 0.0-1.0}}"""
```

Label descriptions matter more than label names. "billing" alone is ambiguous; the description disambiguates "cancel subscription" (billing) from "cancel account" (account).

## Multi-label and hierarchical

Some texts belong to multiple categories:

```json
{"labels": ["technical", "billing"], "primary": "technical"}
```

Hierarchical classification reduces confusion:

```
Step 1: domain → {product, account, sales}
Step 2: within product → {bug, feature_request, how_to}
```

Two cheap calls beat one call with 40 flat labels.

## Confidence you can trust

LLM confidence scores are poorly calibrated out of the box. Improve with:

1. **Logprobs** on classification tokens (if provider supports)
2. **Multiple samples** — agreement rate as confidence
3. **Verbalized + logprob ensemble**

```python
async def classify_with_confidence(text: str, n: int = 3) -> ClassResult:
    results = [await classify(text) for _ in range(n)]
    labels = [r.label for r in results]
    majority = Counter(labels).most_common(1)[0]
    confidence = majority[1] / n
    return ClassResult(label=majority[0], confidence=confidence)
```

Route low-confidence to human review, not to automated actions.

## Cost at scale

| Volume | Zero-shot GPT-4o-mini | Fine-tuned small model |
|--------|----------------------|------------------------|
| 1K/day | ~$0.50/day | Overkill |
| 100K/day | ~$50/day | ~$2/day inference |
| 1M/day | ~$500/day | ~$15/day |

Zero-shot wins on flexibility and time-to-ship. Fine-tuning wins on unit economics above ~10K/day with stable labels.

Hybrid: zero-shot for new/rare labels, fine-tuned model for high-volume core categories.

## Eval methodology

Build a labeled eval set of 100–300 examples stratified by class:

```python
metrics = {
    "accuracy": accuracy_score(y_true, y_pred),
    "macro_f1": f1_score(y_true, y_pred, average="macro"),
    "per_class_recall": recall_per_class(y_true, y_pred),
}
```

Macro-F1 for imbalanced data. Per-class recall for safety-critical labels. Track confusion pairs ("technical" vs "account") and fix with prompt clarifications.

## Production patterns

**Batch classification** for offline pipelines — process overnight at half cost.

**Cache** by content hash for duplicate submissions.

**Pre-filter** with keyword rules for obvious cases (regex → "password reset" = account) before LLM call.

**Ensemble with embedding classifier** — embedding model for high-confidence, LLM for the rest.

```python
async def classify(text: str) -> Label:
    emb_label, emb_score = embedding_classifier(text)
    if emb_score > 0.92:
        return emb_label
    return await llm_classify(text)
```

## Common failures

- **Label leakage in descriptions** — describing "billing" with example text that appears verbatim in test inputs
- **Language mismatch** — English labels, multilingual input
- **Stale labels** — prompt says "Windows app" but product is mobile-only now
- **Overclassification** — model picks a label because instruction says "exactly one" when "other" is correct

Update labels in version-controlled prompt registry, not scattered in code.

## Hierarchical classification

Multi-level taxonomies need staged classification — don't ask for 47 labels in one prompt:

```python
async def classify_hierarchical(text: str) -> Label:
    category = await llm_classify(text, labels=["technical", "billing", "general"])
    if category == "technical":
        sub = await llm_classify(text, labels=["api", "integration", "performance", "other"])
        return f"technical.{sub}"
    return category
```

Stage 1: coarse category (3–5 labels). Stage 2: fine-grained subcategory. Reduces confusion between similar labels and improves accuracy on imbalanced taxonomies.

## Confidence calibration

LLM classification lacks native confidence scores — derive them:

```python
def classify_with_confidence(text: str, labels: list[str]) -> tuple[str, float]:
    # Logprobs from completion API
    response = client.chat.completions.create(
        model="gpt-4o",
        logprobs=True,
        top_logprobs=5,
        messages=[{"role": "user", "content": f"Classify: {text}\nLabels: {labels}"}],
    )
    top_logprob = response.choices[0].logprobs.content[0].top_logprobs[0].logprob
    confidence = math.exp(top_logprob)  # convert log prob to probability
    return response.choices[0].message.content, confidence
```

Route low-confidence (<0.7) classifications to human review queue. High-confidence cases skip review — reduces annotation cost by 60–80%.

## Evaluating classifier changes

Before deploying prompt or label changes:

```python
def eval_classifier(test_set, classifier_fn):
    y_true, y_pred = [], []
    for item in test_set:
        pred = classifier_fn(item["text"])
        y_true.append(item["label"])
        y_pred.append(pred)
    return {
        "macro_f1": f1_score(y_true, y_pred, average="macro"),
        "per_class": classification_report(y_true, y_pred, output_dict=True),
        "confusion_pairs": top_confusion_pairs(y_true, y_pred, n=5),
    }
```

Fix top confusion pairs in prompt before adding more labels. "technical" vs "account" confusion → add distinguishing examples to label descriptions.

## Failure modes

- **Too many labels in one prompt** — accuracy drops above ~10 labels; use hierarchical
- **No confidence threshold** — low-quality classifications reach production silently
- **Label descriptions with test examples** — leakage inflates eval scores
- **No per-class recall tracking** — minority class failures hidden by high accuracy
- **Stale label definitions** — product changed; classifier still uses old categories

## Production checklist

- Labels in version-controlled prompt registry
- Hierarchical classification for taxonomies >10 labels
- Confidence threshold routes low-confidence to human review
- Macro-F1 and per-class recall tracked in eval suite
- Top confusion pairs reviewed after each prompt change
- Pre-filter with keyword rules for obvious cases before LLM call

Calibrate confidence thresholds on production traffic sample — zero-shot labels that look fine in dev skew on real user phrasing.

## Resources

- [OpenAI structured outputs guide](https://platform.openai.com/docs/guides/structured-outputs)
- [Hugging Face zero-shot classification (traditional)](https://huggingface.co/tasks/zero-shot-classification)
- [Anthropic classification prompt patterns](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering)
- [scikit-learn classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#classification-metrics)
- [SetFit few-shot alternative](https://huggingface.co/docs/setfit/en/index)
