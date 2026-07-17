---
title: "Feature Engineering for Contextual Bandits"
slug: "rag-contextual-bandits-features"
description: "Build context vectors that make agent routing bandits work — intent signals, latency features, cost proxies, delayed rewards, and cold-start priors for prompt and model selection."
datePublished: "2025-07-26"
dateModified: "2026-07-17"
tags: ["AI Agents", "Bandits", "ML", "Routing"]
keywords: "contextual bandits features, agent model routing, LinUCB features, Thompson sampling context, exploration exploitation agent"
faq:
  - q: "What belongs in the context vector vs the reward signal?"
    a: "Context is everything known before the arm is pulled: intent, tenant tier, input length, time of day. Reward is observed after: task success, latency, cost, thumbs-down. Never put post-hoc outcomes in context — that leaks the label and inflates offline metrics."
  - q: "How many features before LinUCB or logistic Thompson sampling breaks down?"
    a: "Stay under 50–100 well-chosen features for linear models; use regularization and feature hashing beyond that. High-cardinality raw text belongs in embeddings reduced to 8–16 dimensions, not one-hot token IDs."
  - q: "How do you handle delayed rewards in agent bandits?"
    a: "Log pull events immediately; attach rewards when the session ends or after a timeout (e.g., 30 minutes). Use propensity-weighted updates for late-arriving labels and cap staleness — ignore rewards arriving more than 24h after pull unless task completion inherently delayed."
---

You deployed LinUCB to pick between four system prompts and three model tiers. Offline replay looked great. Online, the bandit keeps routing billing questions to the creative-writing prompt because both share the word "account" in the context vector. **Contextual bandits are only as good as their features** — the arm selection math is solved; the engineering work is building a context representation that reflects what actually drives reward for RAG workloads.

This post covers feature design for RAG routing bandits: which signals to include, how to encode them, how delayed rewards interact with context timestamps, and how to validate that your feature vector is not leaking future information.

## What agent bandits optimize

Production agent bandits typically choose among **arms** like:

- System prompt variants
- Model tier (fast/cheap vs capable/expensive)
- Retrieval depth (top-k, reranker on/off)
- Tool routing policy (aggressive vs conservative)
- Fallback chain ordering

The **context** is observed at decision time — before the arm is pulled. The **reward** arrives after the agent completes work: task success, user thumbs, latency SLA, token cost, escalation to human.

```
Session start
    │
    ▼
Extract context x ──► Bandit.select_arm(x) ──► arm k
    │
    ▼
Agent runs with arm k configuration
    │
    ▼
Observe reward r (possibly delayed)
    │
    ▼
Bandit.update(x, k, r)
```

If `x` omits intent or tenant constraints, the bandit learns spurious correlations. If `x` includes the model's own confidence score from a prior turn, you leak outcome information.

## Feature categories that matter for RAG systems

### Intent and task type

The strongest predictor of which prompt or model works is **what the user is trying to do**. Sources:

- Classifier output (support / billing / code / research) with calibrated probabilities
- Embedding of first user message reduced via PCA to 8–16 dims
- Detected language and locale
- Presence of attachments (PDF, image, CSV)

```python
# features/intent.py
from dataclasses import dataclass
import numpy as np

@dataclass
class IntentFeatures:
    p_support: float
    p_billing: float
    p_code: float
    p_research: float
    embedding_pca: np.ndarray  # shape (16,)
    has_attachment: float
    language_en: float

    def to_vector(self) -> np.ndarray:
        return np.concatenate([
            [self.p_support, self.p_billing, self.p_code, self.p_research,
             self.has_attachment, self.language_en],
            self.embedding_pca,
        ])
```

Use classifier **probabilities**, not argmax labels. Hard labels discard uncertainty that the bandit can exploit.

### Input scale and complexity

Token count, tool count available, and estimated retrieval difficulty predict latency-sensitive arm choices:

- `log1p(input_tokens)` — user message + attached doc size estimate
- `log1p(rag_candidates)` — chunks retrieved before rerank
- `tool_count_available` — capped at 20
- `requires_code_execution` — binary from intent classifier

Large inputs often reward capable models; simple FAQs reward fast models. Without scale features, bandits over-index on intent alone.

### Tenant and policy constraints

B2B agents need **hard constraints** encoded as features or as arm filters:

- `tenant_tier` — one-hot: free, pro, enterprise
- `data_residency_eu` — binary; filters non-EU model arms entirely
- `pii_present` — binary from DLP scan; boosts conservative tool arms
- `sla_latency_ms` — contractual p95 target

Some constraints should **filter ineligible arms** before bandit selection rather than enter the context vector. A bandit cannot learn "never send HIPAA tenants to external model X" from reward alone without expensive violations.

### Temporal and load features

- `hour_of_day_sin/cos` — cyclic encoding
- `queue_depth_normalized` — current inference queue
- `recent_error_rate_arm_family` — rolling 5-min error rate for model provider

Under load, cheap arms may maximize reward even for complex intent because latency penalties dominate user satisfaction.

### Session continuity

- `turn_index` — multi-turn sessions differ from first message
- `prior_task_success` — binary, prior turn outcome
- `tools_invoked_count` — depth of retrieval loop so far

Do not include **current arm identity** from prior turns as a feature unless you are running a separate "switching cost" experiment — it creates path dependence that confounds arm comparison.

## Building the context vector

Concatenate normalized feature groups with documented schema versioning:

```python
# features/context_builder.py
import numpy as np
from datetime import datetime

FEATURE_SCHEMA_VERSION = 3

def build_context(session: dict) -> np.ndarray:
    intent = extract_intent_features(session["first_message"])
    scale = extract_scale_features(session)
    tenant = extract_tenant_features(session["tenant_id"])
    temporal = extract_temporal_features(datetime.utcnow())
    continuity = extract_continuity_features(session)

    vector = np.concatenate([
        intent.to_vector(),       # 22 dims
        scale.to_vector(),        # 6 dims
        tenant.to_vector(),       # 8 dims
        temporal.to_vector(),     # 4 dims
        continuity.to_vector(),   # 3 dims
    ])  # total 43 dims

    assert vector.shape[0] == 43, f"schema v{FEATURE_SCHEMA_VERSION} mismatch"
    return vector
```

**Normalize continuous features** to zero mean and unit variance using stats from training traffic — refreshed weekly. Store normalization params alongside the bandit checkpoint.

**Version the schema.** When you add features, bump `FEATURE_SCHEMA_VERSION` and either retrain from scratch or pad old vectors with zeros — never silently change dimension order.

## Reward design for RAG bandits

Multi-objective rewards need explicit weighting:

```python
def compute_reward(outcome: dict) -> float:
    success = 1.0 if outcome["task_completed"] else 0.0
    latency_penalty = min(outcome["latency_ms"] / 30_000, 1.0) * 0.2
    cost_penalty = min(outcome["token_cost_usd"] / 0.50, 1.0) * 0.15
    human_escalation = 1.0 if outcome["escalated"] else 0.0

    thumbs = outcome.get("user_rating")  # -1, 0, 1 or None
    thumbs_bonus = (thumbs or 0) * 0.25

    return success + thumbs_bonus - latency_penalty - cost_penalty - 0.5 * human_escalation
```

Log **component rewards** separately for debugging. A bandit optimizing composite reward may shift arms for reasons product cannot explain unless you decompose.

Clip rewards to [-1, 2] or similar bounded range. Unbounded cost penalties destabilize LinUCB confidence intervals.

## Delayed rewards and propensity logging

Agent task success may arrive minutes later. Pattern:

```python
# bandit/event_log.py
@dataclass
class PullEvent:
    event_id: str
    context: np.ndarray
    arm: str
    context_schema_version: int
    timestamp: float
    propensity: float  # P(arm | context) under current policy

def update_on_reward(event_id: str, reward: float, bandit: LinUCB):
    event = pull_log.get(event_id)
    if event is None:
        return
    age_hours = (time.time() - event.timestamp) / 3600
    if age_hours > 24:
        metrics.increment("bandit.stale_reward_dropped")
        return
    bandit.update(event.context, event.arm, reward)
```

Log **propensity** — the probability the pulled arm was selected — for offline IPS (inverse propensity scoring) evaluation when you change the policy. Without propensity, offline replays lie.

## Cold start for new arms

Adding a prompt arm with zero history starves exploration. Mitigations:

1. **Optimistic prior** — initialize arm reward estimate at 75th percentile of existing arms per intent slice
2. **Minimum traffic floor** — 5% of pulls matching arm's target intent until N≥200
3. **Similarity transfer** — if new prompt embedding is close to arm A, seed prior from A's stats for overlapping intent buckets

```python
def seed_arm_prior(new_arm: str, prompt_embedding: np.ndarray, arms: dict) -> float:
    similarities = {
        name: cosine_sim(prompt_embedding, meta.embedding)
        for name, meta in arms.items()
    }
    best_match = max(similarities, key=similarities.get)
    if similarities[best_match] > 0.85:
        return arms[best_match].mean_reward * 0.9
    return global_mean_reward + 0.1  # slight optimism
```

## Feature leakage checklist

Before shipping, audit for these leaks:

| Leak | Symptom |
|------|---------|
| Post-hoc model confidence in context | Offline AUC too good; online flat |
| Outcome-derived "complexity" score | Bandit ignores intent features |
| Same-session reward in context of next pull | Within-session overfitting |
| Arm ID unless modeling switching | Incumbent arm always wins |
| Unnormalized token counts | Dominates linear model weights |

Run **permutation importance** offline: shuffle each feature column, measure reward prediction drop. Features with zero importance are candidates for removal — they add noise and dimensionality.

## Evaluation without lying to yourself

1. **IPS offline evaluation** using logged propensities from production
2. **Holdout intent buckets** — entire intent classes reserved for final validation
3. **Switchback tests** — alternate bandit on/off by hour to measure global lift
4. **Slice dashboards** — reward by intent, tenant tier, input length quartile

Require **minimum sample size per arm-intent cell** before declaring an arm winner. "Billing + enterprise + long doc" may have 40 sessions/week — too thin for confident elimination.

## Operational ownership

Feature pipelines for bandits need the same SLOs as payment code:

- **Freshness** — context features computed in <50ms at session start
- **Schema contracts** — protobuf or JSON schema with CI validation
- **Backfill jobs** — when adding features, recompute context for last 7 days of pull logs for offline replay
- **Kill switch** — feature flag to revert to static champion arm without redeploy

Alert when feature distributions drift (PSI > 0.2 on input_tokens or intent probabilities). Drift often precedes bandit reward collapse after product or taxonomy changes.

## The takeaway

Contextual bandits for RAG routing fail in production when teams treat feature engineering as an afterthought. Build context from intent probabilities, input scale, tenant constraints, and session continuity — never from outcomes. Normalize, version, and log propensities. Design composite rewards with interpretable components. Cold-start new arms deliberately. The bandit algorithm is the easy part; the context vector is where uplift lives or dies.

## Resources

- [Li et al. — A Contextual-Bandit Approach to Personalized News (LinUCB)](https://arxiv.org/abs/1003.0146)
- [Chapelle & Li — An Empirical Evaluation of Thompson Sampling](https://arxiv.org/abs/1209.3352)
- [Google — Counterfactual Learning for Bandits (IPS)](https://developers.google.com/machine-learning/recommendation/dnn/recommendation-systems)
- [Vowpal Wabbit — Contextual Bandit documentation](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/examples/contextual_bandits.html)
- [Netflix — Artwork Personalization bandit features (engineering blog)](https://netflixtechblog.com/artwork-personalization-c589f174ad76)
