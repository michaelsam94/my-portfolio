---
title: "Counterfactual Explanations for ML Models"
slug: "rag-counterfactual-explanations"
description: "Generate actionable counterfactual explanations for agent decisions — minimal input changes, feasibility constraints, diversity sampling, and audit-ready UX for regulated workflows."
datePublished: "2025-05-24"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Counterfactual"]
keywords: "counterfactual explanations, XAI agents, actionable recourse, DiCE algorithm, model interpretability, agent decision audit"
faq:
  - q: "What makes a counterfactual explanation useful for agent users?"
    a: "A useful counterfactual names the smallest change to inputs that would flip the agent's decision to an acceptable outcome — 'if annual_income were $52k instead of $48k, approval would succeed' — and respects feasibility (no 'change your age to 25'). Users need actionable recourse, not abstract feature attributions."
  - q: "Can LLM agents generate counterfactuals without a trained classifier?"
    a: "LLMs can narrate plausible counterfactuals from prompt context, but they hallucinate constraints unless grounded in a deterministic policy engine or surrogate model. Production stacks pair LLM phrasing with validated counterfactual search over structured features — never trust free-form counterfactuals for credit, hiring, or medical triage without verification."
  - q: "How do you prevent discriminatory counterfactual suggestions?"
    a: "Mark legally protected attributes as immutable in the search space (race, gender, age in many jurisdictions). Audit generated counterfactuals for proxy leakage — zip code substituting for race. Run fairness tests: counterfactual cost distributions should not differ systematically across demographic groups."
---
A loan agent denied the application in four seconds. The user asked why. The agent returned SHAP values: `debt_to_income` contributed −0.31, `credit_utilization` −0.22. Correct, opaque, and useless — the applicant cannot "adjust SHAP." What they needed was a **counterfactual**: "If you pay down card balance by $1,400 (utilization 78% → 62%), approval probability crosses threshold." Counterfactual explanations answer the closest-world question: *what minimal change would have produced a different outcome?*

For agent systems making consequential decisions — underwriting, insurance quotes, access control, medical triage routing — counterfactuals bridge model output and human action. Feature attributions describe the past; counterfactuals prescribe feasible futures. This post covers search algorithms, constraint modeling, LLM grounding, and operational patterns that keep explanations auditable.

## Counterfactuals vs attributions vs contrastive examples

| Method | Question answered | User actionability |
|--------|-------------------|-------------------|
| Feature attribution (SHAP, LIME) | Which inputs pushed the score? | Low — no magnitude path |
| Contrastive example | What similar case got approved? | Medium — may not be reachable |
| Counterfactual | What change flips the decision? | High — if feasible |

Counterfactuals require a **decision boundary** — binary or score threshold — and a **search space** over mutable features. Agent wrappers often expose natural language decisions; underneath, a structured scorer or rules engine must exist for valid counterfactual search.

```
Original x ──► model f(x) ──► deny (score 0.42, threshold 0.50)
                    │
                    ▼
         search min ||x' - x|| s.t. f(x') ≥ 0.50
                    │
                    ▼
         x' = x with {utilization: 0.62, inquiries: 1}
         "Reduce utilization by $1,400; wait 30 days on new inquiry"
```

## DiCE-style search over structured features

[Diverse Counterfactual Explanations (DiCE)](https://arxiv.org/abs/1905.07857) generates multiple valid counterfactuals by optimizing proximity, sparsity, and diversity jointly. Production implementations rarely use the library verbatim but follow its pattern:

```python
# explanations/counterfactual_search.py
from dataclasses import dataclass
import numpy as np

@dataclass
class FeatureSpec:
    name: str
    value: float
    mutable: bool
    min_val: float
    max_val: float
    dtype: str  # "continuous" | "categorical"

IMMUTABLE = {"age", "race", "gender", "zip_code"}  # jurisdiction-specific

def generate_counterfactuals(
    features: list[FeatureSpec],
    predict_fn,
    target_class: int = 1,
    n: int = 5,
    max_iter: int = 2000,
) -> list[dict]:
    x0 = np.array([f.value for f in features])
    mutable_idx = [i for i, f in enumerate(features) if f.mutable and f.name not in IMMUTABLE]
    rng = np.random.default_rng(42)
    candidates = []

    for _ in range(max_iter):
        x_prime = x0.copy()
        # Sparse perturbation: change 1–3 features
        k = rng.integers(1, min(4, len(mutable_idx) + 1))
        chosen = rng.choice(mutable_idx, size=k, replace=False)
        for j in chosen:
            spec = features[j]
            if spec.dtype == "continuous":
                delta = rng.normal(0, 0.1 * (spec.max_val - spec.min_val))
                x_prime[j] = np.clip(x0[j] + delta, spec.min_val, spec.max_val)
            else:
                x_prime[j] = rng.integers(spec.min_val, spec.max_val + 1)

        if predict_fn(x_prime) >= target_class:
            dist = np.sum(np.abs(x_prime - x0) / (np.array([f.max_val - f.min_val + 1e-9 for f in features])))
            candidates.append((dist, x_prime))

    candidates.sort(key=lambda t: t[0])
    # Diversity filter: drop counterfactuals too similar in feature space
    diverse = []
    for dist, xp in candidates:
        if all(np.mean(np.abs(xp - d) > 0.05) for d in diverse):
            diverse.append(xp)
        if len(diverse) >= n:
            break
    return [dict(zip([f.name for f in features], xp)) for xp in diverse]
```

Wrap `predict_fn` with the same preprocessing pipeline as production — counterfactuals on raw user input that bypass scaling produce fantasy edits.

## Feasibility and actionability constraints

Mathematically valid counterfactuals often violate reality:

- "Increase income by $200k" — not actionable this week
- "Change employment_status to 'tenured professor'" — categorical leap
- "Set age to 21" — illegal suggestion in credit contexts

Layer **feasibility scores** after search:

```python
def feasibility_score(original: dict, counterfactual: dict, rules: list) -> float:
    score = 1.0
    for rule in rules:
        score *= rule(original, counterfactual)
    return score

def income_delta_cap(original, cf, max_pct=0.15):
    delta = cf["annual_income"] - original["annual_income"]
    if delta > max_pct * original["annual_income"]:
        return 0.0
    return 1.0
```

Rank displayed counterfactuals by `proximity × feasibility`, not proximity alone. Log rejected infeasible candidates for compliance review — regulators ask what you *did not* show.

## Grounding LLM agents in verified counterfactuals

Agent UX often demands natural language. Never let the LLM invent numeric counterfactuals.

Pipeline:

1. Structured decision service returns `{decision, score, features}`.
2. Counterfactual engine searches over mutable features.
3. LLM receives **frozen** counterfactual JSON and rephrases for the user.
4. Validator checks LLM output against JSON — reject regeneration if numbers drift.

```typescript
const systemPrompt = `You explain loan decisions using ONLY the counterfactuals in COUNTERFACTUALS_JSON.
Do not invent new numbers, features, or policy rules. If asked about immutable attributes, state they cannot be changed per policy.`;

async function explainDecision(sessionId: string, decision: Decision) {
  const cfs = await counterfactualService.generate(decision.featureVector, {
    desiredOutcome: "approve",
    count: 3,
  });

  const llmResponse = await agent.complete({
    system: systemPrompt,
    user: `Decision: ${decision.outcome}. COUNTERFACTUALS_JSON: ${JSON.stringify(cfs)}`,
  });

  assertNumbersMatch(llmResponse, cfs); // strip and compare
  await auditLog.write({ sessionId, decision, cfs, llmResponse });
  return llmResponse;
}
```

This pattern survives model upgrades — the search layer is deterministic; the LLM is presentation.

## Diversity and user trust

Single counterfactuals feel coercive ("the only way is pay $1,400"). Multiple paths build trust:

- **Path A** — pay down utilization (fast, requires liquidity)
- **Path B** — add co-signer (relational cost)
- **Path C** — wait 60 days for inquiry to age off (time cost)

DiCE's diversity objective penalizes counterfactuals that change the same features. In UI, label tradeoffs explicitly; hide internal feature names users do not recognize (`revolving_balance` → "total credit card balance").

## Evaluation metrics

Offline:

- **Validity rate** — % counterfactuals that actually flip `predict_fn`
- **Sparsity** — mean number of changed features
- **Proximity** — normalized L1 distance
- **Actionability** — % passing feasibility rules

Online:

- User follow-through rate on suggested actions (with consent)
- Support ticket volume on "why denied" themes
- Disparate impact of suggested actions across groups

Run counterfactual eval in CI when the scorer model version changes — explanation quality regresses silently otherwise.

## Audit, retention, and regulation

Store `{input_hash, model_version, counterfactuals[], timestamp, immutable_set}` for each explanation request. GDPR and FCRA contexts may treat explanations as part of adverse action notices — retention policies apply.

For tool chains, propagate `explanation_id` so downstream tools do not re-generate conflicting counterfactuals mid-session.

Red-team: prompt injection asking the agent to suggest changing protected attributes. Immutable feature enforcement must live in search code, not prompt instructions alone.

## Latency budgets and caching in production

Counterfactual search is CPU-bound for tree ensembles; GPU for neural scorers. Budget 100–500ms per explanation request; cache by `(model_version, feature_vector_hash, desired_outcome)` for repeat queries in the same session.

Feature flag `counterfactual_explanations_v2` when changing search parameters — A/B test comprehension, not just validity rate.

Alert when validity rate drops below 95% — usually a training-serving skew bug.

Session-level consistency matters: if an agent generates counterfactuals mid-conversation and the user acts on one path, subsequent turns must not contradict earlier suggested edits. Pin `counterfactual_set_id` on the session and invalidate when the underlying scorer model version changes.

## The takeaway

Counterfactual explanations turn agent denials into paths forward — when search is constrained, verified, and separated from LLM narration. Build on structured scorers, enforce immutable attributes in code, rank by feasibility, surface diverse options, and audit everything. Attribution charts impress data scientists; counterfactuals reduce support tickets and satisfy regulators asking "what could they have done differently?"

## Resources

- [DiCE: Diverse Counterfactual Explanations (arxiv)](https://arxiv.org/abs/1905.07857)
- [Interpretable Machine Learning — Counterfactual Explanations chapter](https://christophm.github.io/interpretable-ml-book/counterfactual.html)
- [IBM AI Explainability 360 — DiCE implementation](https://aix360.mybluemix.net/)
- [EU AI Act — transparency obligations summary](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [FCRA adverse action notice requirements (CFPB)](https://www.consumerfinance.gov/compliance/compliance-resources/fair-credit-reporting-act/)
