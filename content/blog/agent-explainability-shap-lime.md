---
title: "AI Agents: Explainability Shap Lime"
slug: "agent-explainability-shap-lime"
description: "SHAP and LIME in production ML — local vs global explanations, tabular vs text models, latency budgets, explanation stability, and compliance workflows for agent decision systems."
datePublished: "2025-05-22"
dateModified: "2025-05-22"
tags: ["AI", "Agent", "Explainability"]
keywords: "SHAP, LIME, explainability, feature attribution, model interpretability, XAI, production ML, agent decisions"
faq:
  - q: "When should I use SHAP instead of LIME?"
    a: "Use SHAP when you need consistent additive attributions with theoretical guarantees (Shapley values), especially for tree models (TreeSHAP is fast) or moderate-sized neural nets. Use LIME when you need a quick local linear approximation for any black-box model and can tolerate explanation instability across runs. In production, SHAP is the default for tabular scoring; LIME is common for text/image prototypes."
  - q: "How do you explain LLM or agent outputs with SHAP/LIME?"
    a: "Direct SHAP on billions of parameters is impractical. Practical paths: explain a smaller surrogate (distilled classifier), attribute at the token level via SHAP on embedding inputs, or explain structured tool-choice models separately from generative text. For RAG agents, explain retrieval scores and reranker features — not every generated token."
  - q: "What latency budget is realistic for real-time explanations?"
    a: "TreeSHAP on 50 features with XGBoost typically lands in 5–50ms per row. KernelSHAP with 1000 coalitions can take seconds — batch offline or cache. LIME with 5000 perturbed samples on text may exceed 500ms. Precompute explanations for high-stakes decisions; serve cached attributions with TTL for repeat queries."
  - q: "Are SHAP/LIME explanations legally sufficient for regulated decisions?"
    a: "They support but do not replace compliance. GDPR 'right to explanation' and fair-lending audits require human-readable reason codes tied to decision logic. SHAP gives feature contributions; you still need adverse action reason codes, monotonicity checks, and documentation that the explanation method matches the deployed model version."
---
The loan agent denied an application in eleven seconds. The applicant asked why. Support pasted a generic "our model considers many factors" template. Regulators asked for feature-level reason codes. Engineering ran SHAP offline on a stale model checkpoint that did not match production.

Explainability is not a research curiosity for agent systems that touch credit, healthcare, hiring, or fraud. SHAP (SHapley Additive exPlanations) and LIME (Local Interpretable Model-agnostic Explanations) are the two workhorses teams reach for first — and the two methods most often misapplied. This deep dive covers how they work, where they break, and how to ship them without lying to users about certainty.

## Two questions: local vs global

**Local explanations** answer: why did the model score *this* input 0.73? **Global explanations** answer: which features matter across the population?

LIME is inherently local — it fits a simple interpretable model in a neighborhood around one instance. SHAP provides local Shapley values that sum to the model output (for additive explainers) and can be aggregated globally by averaging absolute SHAP values per feature.

| Method | Scope | Model agnostic? | Consistency | Typical cost |
|--------|-------|-----------------|-------------|--------------|
| LIME | Local | Yes | Low (sampling noise) | Medium–High |
| TreeSHAP | Local + global | Tree models only | High | Low |
| KernelSHAP | Local | Yes | High (slow) | High |
| DeepSHAP | Local | Neural nets | Medium | High |

For agent routing (which tool? which policy tier?), local explanations map cleanly to user-facing "because X and Y." For monitoring drift, global SHAP rankings compared week-over-week catch silent feature pipeline bugs.

## LIME: local linear approximations

LIME perturbs the input, queries the black-box model, and weights samples by proximity to the original instance. It then trains a sparse linear model (Lasso) to approximate the decision boundary locally.

For tabular data:

```python
import lime
import lime.lime_tabular
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

# Train a stand-in production model
X_train = pd.read_parquet("features/train.parquet")
y_train = X_train.pop("approved")
model = GradientBoostingClassifier(n_estimators=200, max_depth=4)
model.fit(X_train, y_train)

explainer = lime.lime_tabular.LimeTabularExplainer(
    training_data=X_train.values,
    feature_names=list(X_train.columns),
    class_names=["denied", "approved"],
    mode="classification",
    discretize_continuous=True,  # bin numeric features for readable rules
)

def explain_row(row: pd.Series, num_samples: int = 5000) -> lime.Explanation:
    exp = explainer.explain_instance(
        row.values,
        model.predict_proba,
        num_features=8,
        num_samples=num_samples,
    )
    return exp

sample = X_train.iloc[42]
explanation = explain_row(sample)
for feat, weight in explanation.as_list():
    print(f"{feat}: {weight:+.4f}")
```

**Production caveats for LIME:**

- **Instability:** Re-running with different random seeds changes top features. Set `random_state`, increase `num_samples`, and show confidence bands or top-k overlap metrics internally.
- **Tabular discretization:** `discretize_continuous=True` produces human-readable rules ("credit_utilization > 0.72") but hides within-bin nuance.
- **High-dimensional text:** Perturbing tokens produces plausible but not faithful attributions when the model uses long-range context.

Use LIME for exploratory analysis and customer-support prototypes. Promote to SHAP when explanations become contractual.

## SHAP: Shapley values with additivity

SHAP assigns each feature a contribution φᵢ such that (for additive explainers):

```
base_value + Σ φᵢ = model_output(instance)
```

Shapley values come from cooperative game theory: fair allocation of payout across players (features). TreeSHAP computes exact values for tree ensembles in polynomial time — the reason XGBoost/LightGBM production stacks default to SHAP.

```python
import shap
import xgboost as xgb

model = xgb.XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.05,
    tree_method="hist",
)
model.fit(X_train, y_train)

explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X_train.iloc[:500])

# Single prediction waterfall data
row_idx = 42
shap_explanation = explainer(X_train.iloc[[row_idx]])
print(f"Base: {shap_explanation.base_values[0]:.3f}")
for name, val in zip(X_train.columns, shap_explanation.values[0]):
    print(f"  {name}: {val:+.4f}")

# Global importance
shap.summary_plot(shap_values, X_train.iloc[:500], plot_type="bar")
```

For **agent tool-routing classifiers** (choose search vs calculator vs handoff), TreeSHAP on the routing model is fast enough for synchronous API responses when feature count stays under ~100.

## Text and LLM agents: where attribution gets hard

Generating free text is not a single scalar score. Practical decomposition:

1. **Retrieval stage:** Explain BM25/vector/reranker features with SHAP on the reranker (often a cross-encoder or small MLP).
2. **Tool selection:** Explain the classifier that picks tools — SHAP on structured context features (intent embedding distance, user tier, session length).
3. **Response quality:** Use separate eval models; do not SHAP the entire transformer at request time.

Token-level LIME/SHAP on BERT-sized models uses masking or integrated gradients on embeddings. Budget accordingly:

```python
import shap
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

tokenizer = AutoTokenizer.from_pretrained("distilbert-base-uncased-finetuned-sst-2-english")
model = AutoModelForSequenceClassification.from_pretrained(
    "distilbert-base-uncased-finetuned-sst-2-english"
)

def f(texts: list[str]) -> np.ndarray:
    inputs = tokenizer(texts, return_tensors="pt", padding=True, truncation=True)
    with torch.no_grad():
        logits = model(**inputs).logits
    return shap.approximate(shap softmax)(logits).numpy()

# Use shap.Explainer with a masker for text — run offline, cache results
```

Never block the user-facing agent on KernelSHAP over 512 tokens unless you have a dedicated GPU pool for explainability.

## Serving explanations in production

Architecture pattern:

```
Request → Model inference → Prediction stored
                       ↘ Async explain job (SHAP) → Explanation cache keyed by (model_version, input_hash)
Support UI / API ← read cache
```

```typescript
interface ExplanationRecord {
  predictionId: string;
  modelVersion: string;
  baseValue: number;
  outputValue: number;
  features: Array<{ name: string; value: unknown; shap: number }>;
  generatedAt: string;
  method: "TreeSHAP" | "KernelSHAP" | "LIME";
}

export async function getExplanation(
  predictionId: string,
): Promise<ExplanationRecord | null> {
  const cached = await redis.get(`xai:${predictionId}`);
  if (cached) return JSON.parse(cached);

  // Trigger async generation; return 202 + poll URL for sync-challenged cases
  await queue.publish("explain", { predictionId });
  return null;
}
```

**Version lock:** Explanations must reference the exact model artifact used for inference. Store `model_version` and `feature_schema_hash` alongside every explanation. Auditors compare denial reason codes against the deployed artifact — not last week's notebook.

## Stability, fairness, and monitoring

Track explanation stability metrics:

- **Top-k overlap:** Jaccard similarity of top-5 features across 10 LIME reruns — alert if mean < 0.6.
- **SHAP sign consistency:** Percentage of rows where income SHAP sign matches monotonic business expectation.
- **Population shift:** Mean |SHAP| per feature week-over-week — spikes in `device_fingerprint` may indicate proxy discrimination.

Fair lending and EU AI Act workflows map SHAP magnitudes to **adverse action reason codes** (top negative contributors above materiality threshold). Automate the mapping table; do not let support invent reasons.

## Security and privacy

Explanation APIs leak information. Returning SHAP for internal fraud features may reveal proprietary signals to attackers probing the model. Gate explanation detail by role:

- **Customer:** Top 3–4 reason codes, no raw internal feature names.
- **Internal analyst:** Full SHAP vector.
- **Regulator:** Signed PDF with model card + explanation methodology.

Perturbation-based methods (LIME, KernelSHAP) issue many model queries — rate-limit and detect probing loops.

## Testing explainability pipelines

1. **Unit tests:** Mock model; assert SHAP values sum to output ± ε.
2. **Golden rows:** Frozen inputs with expected top features — catch library upgrades that change TreeSHAP behavior.
3. **Contract tests:** Explanation schema matches support portal expectations.
4. **Latency tests:** p95 explain job under SLA at peak batch volume.

## The takeaway

SHAP and LIME translate model scores into stories humans can act on — when scoped correctly. Use TreeSHAP for production tabular and routing models; treat LIME as a flexible local probe with stability checks. Keep LLM attribution at retrieval and tool-choice boundaries, cache expensive explanations, and version everything. Explainability earns trust only when the explanation matches the model that actually decided.

## Resources

- [A Unified Approach to Interpreting Model Predictions (SHAP paper)](https://arxiv.org/abs/1705.07874)

- ["Why Should I Trust You?": Explaining the Predictions of Any Classifier (LIME paper)](https://arxiv.org/abs/1602.04938)

- [SHAP Python documentation](https://shap.readthedocs.io/en/latest/)

- [LIME GitHub repository](https://github.com/marcotcr/lime)

- [Interpretable Machine Learning book (Molnar) — SHAP chapter](https://christophm.github.io/interpretable-ml-book/shap.html)
