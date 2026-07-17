---
title: "AI Agents: Fraud Scoring Realtime"
slug: "agent-fraud-scoring-realtime"
description: "Build sub-100ms fraud scoring paths with feature stores, rules-plus-model ensembles, idempotent decision logs, and shadow-mode rollout that balances false positives against agent abuse."
datePublished: "2025-08-05"
dateModified: "2025-08-05"
tags: ["AI", "Agent", "Fraud"]
keywords: "fraud scoring, realtime, feature store, risk engine, machine learning, false positive, payment fraud"
faq:
  - q: "Should realtime fraud scoring block transactions synchronously?"
    a: "Only when latency budget and model confidence support it—typically sub-100ms p99 with a rules fast-path. High-uncertainty scores should enqueue async review or step-up verification instead of hard declines that churn good customers."
  - q: "How do you prevent feature leakage in fraud models?"
    a: "Compute features from events strictly before decision time, use point-in-time joins in the feature store, and ban post-outcome labels from inference payloads. Leakage inflates offline AUC and collapses in production."
  - q: "What is a sensible shadow mode rollout?"
    a: "Run new models parallel to production decisions without enforcing outcomes for two to four weeks. Compare score distributions, alert rates, and counterfactual precision on labeled chargebacks before promoting to active block mode."
  - q: "How do agent platforms differ from payment fraud scoring?"
    a: "Agent abuse includes credential stuffing on tool APIs, prompt injection for exfiltration, wallet draining via chained tool calls, and synthetic account farming—not just card BIN patterns. Blend behavioral velocity features with LLM-specific signals like tool-call entropy and policy bypass attempts."
---
Payment fraud teams learned decades ago that batch nightly scores miss the cart. Agent platforms replay the same lesson on a faster clock: tool calls fire in milliseconds, promo credits disappear in minutes, and attackers script LLM workflows before a human analyst finishes coffee. Realtime fraud scoring sits on the hot path—checkout, payout, API key minting, high-value tool invocations—and must decide with incomplete information under strict latency budgets.

This guide covers engineering a production realtime fraud scorer: feature computation at decision time, rules-plus-model ensembles, idempotent decision logging, and rollout patterns that avoid training on leaked labels or drowning support in false positives.

## Decision architecture on the hot path

A typical synchronous flow:

```
Client request → AuthN → Feature assembly → Rules layer → Model score → Action policy → Response
                              ↓                              ↓
                        Feature store                   Decision log (async)
```

**Latency budget allocation** (example 80ms p99 total):

| Stage | Budget |
|-------|--------|
| Auth + request parse | 10ms |
| Feature fetch (Redis/gRPC) | 25ms |
| Rules evaluation | 10ms |
| Model inference | 20ms |
| Policy + response | 15ms |

Exceed budget → degrade to rules-only or allow-with-step-up, never hang the user while a GPU warms up.

Keep inference **stateless**; state lives in the feature store and decision log. Horizontal scale adds replicas behind a load balancer with sticky routing only if session features require it—prefer user-id keyed features instead.

## Feature store at decision time

Realtime features fall into buckets:

- **Velocity** — events per minute per device, IP, account, payment instrument
- **Aggregates** — trailing 1h/24h spend, failed auth count, distinct merchants
- **Graph** — shared device fingerprint across accounts (careful with privacy)
- **Agent-specific** — tool-call rate, unique endpoints hit, policy denial streaks
- **Static** — account age, KYC tier, country mismatch flags

Use **point-in-time correct joins**. Offline training must replay the same logic:

```python
from datetime import datetime, timedelta

def velocity_features(user_id: str, now: datetime, redis) -> dict:
    window_key = f"vel:{user_id}:{now.strftime('%Y%m%d%H%M')}"
    count_5m = redis.incr(window_key)
    redis.expire(window_key, 300)
    return {
        "events_5m": int(count_5m),
        "account_age_hours": account_age_hours(user_id, now),
    }
```

Materialize heavy aggregates asynchronously; the hot path reads precomputed Redis hashes keyed by `(entity, window)`.

Document **feature freshness SLAs**. A stale \"transactions_24h\" counter silently weakens models—monitor lag between event ingest and feature update.

## Rules layer before models

Rules catch known-bad patterns instantly and explain decisions to regulators:

```python
def rules_decision(ctx: FraudContext) -> RuleOutcome | None:
    if ctx.bin_country != ctx.ip_country and ctx.amount_usd > 500:
        return RuleOutcome(action="review", reason="geo_mismatch_high_amount")
    if ctx.device_seen_accounts_24h > 5:
        return RuleOutcome(action="block", reason="device_farming")
    if ctx.agent_tool_denials_5m > 20:
        return RuleOutcome(action="block", reason="agent_policy_abuse")
    return None
```

Rules should be **versioned**, unit-tested, and deployed independently of ML models. Return explicit `reason codes` for support dashboards—not opaque scores.

Order: cheap rules first, model second, expensive graph lookups last with circuit breakers.

## Model scoring and calibration

Gradient boosted trees (XGBoost, LightGBM) remain the workhorse for tabular fraud features—fast CPU inference, interpretable SHAP for disputes. Deep models rarely justify latency unless graph neural nets on precomputed embeddings.

```python
import lightgbm as lgb
import numpy as np

booster = lgb.Booster(model_file="fraud_v42.txt")

def score_transaction(features: dict) -> float:
    x = np.array([[features[k] for k in FEATURE_ORDER]], dtype=np.float32)
    raw = booster.predict(x)[0]
    return float(raw)  # calibrated probability if trained with logloss + calibration

def action_from_score(score: float, ctx: FraudContext) -> str:
    if score >= 0.95:
        return "block"
    if score >= 0.75:
        return "step_up"  # OTP, passkey, manual review queue
    return "allow"
```

Calibrate probabilities on holdout chargebacks—raw scores from imbalanced training lie. Use isotonic or Platt scaling and re-check weekly.

For **agent abuse**, add features like tool sequence n-grams hashed to buckets, ratio of read vs write tools, and retrieval queries targeting sensitive collections. Retrain when new tools ship; attackers probe fresh surfaces first.

## Idempotent decision logging

Every decision must log once per idempotency key—even when clients retry:

```python
def decide(request_id: str, ctx: FraudContext) -> Decision:
    existing = db.decisions.find_one({"request_id": request_id})
    if existing:
        return Decision(**existing)

    rule = rules_decision(ctx)
    if rule:
        decision = Decision(action=rule.action, reason=rule.reason, score=None)
    else:
        score = score_transaction(ctx.features)
        decision = Decision(
            action=action_from_score(score, ctx),
            reason="model_v42",
            score=score,
        )

    db.decisions.insert_one({
        "request_id": request_id,
        **decision.dict(),
        "features_hash": hash_features(ctx.features),
        "ts": utcnow(),
    })
    publish_async("fraud.decisions", decision)
    return decision
```

Async consumers update labels when chargebacks arrive—never block the hot path on warehouse writes.

Store **feature snapshots** or hashes for dispute investigation. Full feature JSON aids debugging but may contain PII—apply retention and access controls.

## Action policy and customer experience

Hard blocks without appeal paths churn good users. Policy tiers:

| Action | When | UX |
|--------|------|-----|
| Allow | Low risk | Silent |
| Step-up | Medium | OTP, passkey, email confirm |
| Review | Uncertain | Queue + provisional allow/deny by vertical |
| Block | High confidence | Clear message + support path |

Tune thresholds against **precision at operational alert volume**, not ROC alone. A model with 0.99 AUC that generates 5% step-ups may still overwhelm support.

Implement **cooldown lists** for false positive recovery—auto-allow after verified step-up within session.

## Shadow mode and champion/challenger

Promote models safely:

1. **Shadow** — challenger scores logged, production action from champion only
2. **Challenger sample** — enforce challenger on 1–5% traffic with tight monitoring
3. **Promote** — challenger becomes champion when chargeback rate and false positive tickets beat baseline

Compare **counterfactual metrics**: \"Would challenger have blocked this confirmed fraud?\" and \"Would challenger have blocked this later-labeled good customer?\"

Automate rollback when block rate spikes >3σ above seven-day baseline.

## Observability and feedback loops

Dashboards:

- Score distribution by segment (new vs returning, country, agent tier)
- Action rates: allow / step-up / block
- Latency p50/p95/p99 per stage
- Feature null rates and staleness
- Chargeback lag-adjusted precision/recall

Alert on **feature pipeline lag**, **model version mismatch** (serving v41 while training exports v42), and **sudden drop in event volume**—often ingestion failure, not fraud disappearance.

Close the loop: chargebacks and manual review labels flow to label store with **delay adjusted windows** so retrains respect chargeback latency (30–120 days for cards).

## Security and adversarial considerations

Fraud systems become targets:

- Rate-limit feature API internally
- Sign requests between services; mTLS inside mesh
- Detect **score probing**—same account sweeping amounts to map thresholds
- Rotate model artifacts from trusted CI; verify checksums at load

Attackers adapt to rules quickly—keep **hidden honeypot features** and rotate public reason codes.

For **multi-tenant agent platforms**, isolate score thresholds per tenant vertical. A block threshold tuned for consumer chat may annihilate conversion on a B2B automation API with legitimately bursty tool usage. Export tenant-specific policy configs versioned alongside model artifacts.

## Testing

- Unit tests for every rule and threshold boundary
- Contract tests between feature store and scorer
- Load tests at 2× peak QPS with production-shaped feature cardinality
- Replay yesterday's traffic in staging after each model promotion

Include **regression fixtures** for known fraud rings and known good power users—both directions.

## The takeaway

Realtime fraud scoring is an ensemble of fresh features, tested rules, calibrated models, and policies tuned for human impact—not a single AUC number. Build sub-100ms paths with graceful degradation, log decisions idempotently, roll models through shadow mode, and close the label loop with chargeback-aware retraining. Agent platforms extend the threat model; extend features and rules accordingly.

## Resources

- [Stripe — Radar fraud detection overview](https://stripe.com/radar)
- [Feast — Feature store for realtime ML](https://docs.feast.dev/)
- [LightGBM documentation](https://lightgbm.readthedocs.io/)
- [PCI DSS — Requirement 6 and logging guidance](https://www.pcisecuritystandards.org/)
- [FATF — Digital identity and fraud risk guidance](https://www.fatf-gafi.org/)
