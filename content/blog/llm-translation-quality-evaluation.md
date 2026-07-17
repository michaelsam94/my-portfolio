---
title: "Evaluating LLM Translation Quality"
slug: "llm-translation-quality-evaluation"
description: "Measure LLM translation quality with COMET, chrF++, human evaluation frameworks, and domain-specific benchmarks — not just BLEU scores."
datePublished: "2025-04-10"
dateModified: "2026-07-17"
tags:
keywords: "LLM translation evaluation, COMET metric, BLEU score limitations, machine translation quality, human evaluation translation, chrF score"
faq:
  - q: "Is BLEU score still useful for evaluating LLM translations?"
    a: "BLEU measures n-gram overlap with reference translations and correlates poorly with human judgment for LLM outputs, which often produce valid paraphrases that BLEU penalizes. Use BLEU as a rough regression signal only. Prefer COMET or chrF++ for automatic evaluation, and human evaluation for production decisions."
  - q: "How many human evaluators do I need for reliable translation quality scores?"
    a: "For directional quality assessment (adequacy and fluency on a 1–5 scale), 3 independent evaluators per segment with MQM (Multidimensional Quality Metrics) is standard. Report inter-annotator agreement (Krippendorff's alpha above 0.6). For go/no-go decisions on a new model, evaluate at least 200 segments per language pair."
  - q: "Can I use an LLM to evaluate another LLM's translations?"
    a: "LLM-as-judge works for translation evaluation when prompted with source text, candidate translation, and reference translation together. GPT-4 as evaluator correlates reasonably with human scores on common language pairs. It fails on low-resource languages and domain-specific terminology where the judge model lacks expertise."
---
Your team swapped Google Translate API for an LLM-based translation pipeline. BLEU scores look fine. Then your German customer support lead reads the output and says half the translations are grammatically correct but mean something different from the source. Formal English "Please provide your account details" becomes informal German that reads like a text message to a friend.

Automatic metrics missed the problem because they measure surface overlap, not meaning preservation. Evaluating LLM translation quality requires layered metrics — automatic for regression detection, human evaluation for production decisions, and domain-specific test sets for your actual content.

## Why BLEU fails for LLM translations

BLEU (Bilingual Evaluation Understudy) counts n-gram matches between the candidate translation and one or more reference translations:

```
BLEU = BP × exp(Σ w_n × log(p_n))

where p_n = n-gram precision for n=1,2,3,4
```

Problems with LLM outputs:

- **Valid paraphrases score low.** Reference: "The meeting was cancelled." Candidate: "The meeting has been called off." BLEU penalizes this despite identical meaning.
- **Fluency is ignored.** A grammatically perfect translation that misses the source meaning can score higher than a slightly awkward but accurate translation.
- **No source awareness.** BLEU compares candidate to reference without looking at the source text. A hallucinated but fluent sentence can score well.

Use BLEU only as a coarse regression check — did scores drop 10 points after a model swap? Investigate. Do not use BLEU alone to claim translation quality.

## COMET: neural metric with source awareness

COMET (Crosslingual Optimized Metric for Evaluation of Translation) uses a pretrained multilingual model to score translation quality considering source, candidate, and reference together:

```python
from comet import download_model, load_from_checkpoint

model_path = download_model("Unbabel/wmt22-comet-da")
model = load_from_checkpoint(model_path)

data = [
    {
        "src": "Please provide your account details.",
        "mt": "Bitte geben Sie Ihre Kontodaten an.",
        "ref": "Please submit your account information.",
    }
]

scores = model.predict(data, batch_size=8, gpus=1)
print(scores)  # [0.87] — high score for accurate translation
```

COMET scores correlate with human judgment at 0.85+ Pearson correlation on WMT benchmarks — significantly better than BLEU. Use COMET-22 (the latest WMT-trained variant) for production evaluation.

## chrF++: character-level F-score

chrF++ operates at the character level, making it more robust to morphological variation and word order differences:

```python
from sacrebleu.metrics import CHRF

chrf = CHRF(word_order=2)  # chrF++ with word order
score = chrf.corpus_score(
    hypotheses=["Bitte geben Sie Ihre Kontodaten an."],
    references=[["Please submit your account information."]],
)
print(f"chrF++: {score.score:.1f}")
```

chrF++ works well for morphologically rich languages (German, Finnish, Turkish) where word-level metrics miss partial matches.

## Building a domain-specific test set

Generic WMT test sets do not reflect your content. Build an eval set from your actual translation workload:

```python
test_set = [
    {
        "source": "Your order #12345 has been shipped.",
        "reference": "Ihre Bestellung #12345 wurde versandt.",
        "domain": "shipping_notification",
        "critical_terms": ["#12345", "versandt"],
    },
    {
        "source": "This medication may cause drowsiness.",
        "reference": "Dieses Medikament kann Schläfrigkeit verursachen.",
        "domain": "medical_warning",
        "critical_terms": ["Schläfrigkeit"],
    },
]
```

Include:

- 200+ segments per language pair
- Coverage of your domain terminology
- Edge cases (numbers, dates, proper nouns, idioms)
- Segments tagged with critical terms that must be preserved

## Human evaluation with MQM

Multidimensional Quality Metrics (MQM) provides a structured framework for human evaluation:

| Error type | Severity | Example |
|-----------|----------|---------|
| Accuracy — Mistranslation | Critical | "Refund" → "Erstattung" translated as "Rückgabe" (return, not refund) |
| Fluency — Grammar | Major | Wrong verb conjugation |
| Terminology — Inconsistent | Minor | "Account" translated two different ways in the same document |
| Style — Awkward | Minor | Correct but unnatural phrasing |

Scoring: Critical = −25, Major = −5, Minor = −1. Start from 100, subtract errors.

```python
def mqm_score(errors: list[dict]) -> float:
    penalties = {"critical": 25, "major": 5, "minor": 1}
    total_penalty = sum(penalties[e["severity"]] for e in errors)
    return max(0, 100 - total_penalty)
```

Run MQM evaluation on 200 segments with 3 annotators before switching translation models in production.

## LLM-as-judge for translation

When human evaluation is too slow for CI/CD:

```python
JUDGE_PROMPT = """
Evaluate this translation on a scale of 1-5 for:
1. Accuracy: Does the translation preserve the source meaning?
2. Fluency: Is the translation grammatically correct and natural?

Source ({source_lang}): {source}
Translation ({target_lang}): {translation}
Reference ({target_lang}): {reference}

Return JSON: {"accuracy": N, "fluency": N, "errors": ["description of any errors"]}
"""
```

LLM judges work best for high-resource language pairs where the judge model has strong target-language proficiency. Always validate the judge against human scores on a calibration set before trusting it for automated regression testing.

## Regression testing in CI

Automate translation quality checks:

```python
def translation_regression_test(model, test_set, baseline_scores):
    results = []
    for item in test_set:
        translation = model.translate(item["source"], target_lang="de")
        comet_score = compute_comet(item["source"], translation, item["reference"])
        results.append(comet_score)

    avg_score = sum(results) / len(results)
    assert avg_score >= baseline_scores["comet"] - 0.02, (
        f"COMET dropped from {baseline_scores['comet']:.3f} to {avg_score:.3f}"
    )
```

Run on every model update, prompt change, or fine-tune. A 0.02 COMET drop is worth investigating; a 0.05 drop is a blocker.

## Resources

- [COMET metric GitHub repository](https://github.com/Unbabel/COMET)
- [sacreBLEU and chrF++ implementation](https://github.com/mjpost/sacrebleu)
- [MQM error typology (Google)](https://themqm.org/error-types-2/error-types/)
- [WMT conference shared tasks and benchmarks](https://www2.statmt.org/wmt24/)
- [Unbabel COMET-22 model on Hugging Face](https://huggingface.co/Unbabel/wmt22-comet-da)

## Production notes for LLM stacks

When `llm-translation-quality-evaluation` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `evaluating llm translation quality` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
