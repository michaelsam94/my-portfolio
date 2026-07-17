---
title: "Toxicity Classifier Thresholds for Agent Outputs"
slug: "agent-toxicity-classifier-threshold"
description: "Calibrate moderation models on agent-generated text: threshold tradeoffs, dual human review queues, multilingual bias, and blocking vs rewriting vs escalation policies."
datePublished: "2025-04-15"
dateModified: "2026-07-17"
tags: ["AI Agents", "Safety", "Moderation", "ML"]
keywords: "toxicity classifier threshold agent, content moderation LLM output, agent safety filter calibration, moderation false positive"
faq:
  - q: "Should moderation run on user input, agent output, or both?"
    a: "Both, with different thresholds. User input: block jailbreaks and illegal requests early. Agent output: catch hallucinated harmful content, leaked PII, and policy violations before render. Tool results may need a third profile if they contain user-generated text."
  - q: "One global threshold or per-category?"
    a: "Per-category. Harassment and self-harm warrant lower tolerance (higher recall) than mild profanity in a creative writing agent. A single score threshold optimizes for one category and fails others."
  - q: "How do you reduce false positives on medical or legal agents?"
    a: "Allowlist domain terms, use category-specific models, and route edge cases to human review instead of hard block. Calibrate on in-domain corpora — generic toxicity models flag anatomy and legal terms incorrectly."
  - q: "Block, rewrite, or escalate — how to choose?"
    a: "Block for high-confidence policy violations and safety risks. Rewrite (with second-pass model) for tone issues when user intent is benign. Escalate to human when confidence is mid-band (0.4–0.7) or when user tier is enterprise with SLA."
---

Generic toxicity APIs return a float. Production agent safety needs a **policy engine** that maps scores, categories, and context to block, rewrite, or escalate — calibrated on your agent's actual output distribution, not Twitter circa 2018. A customer support bot and a creative writing assistant should not share the same threshold table.

## Score semantics vary by vendor

Before calibrating thresholds, normalize what the score means:

| Provider | Output | Notes |
|----------|--------|-------|
| OpenAI Moderation API | Category booleans + scores | Multi-label, good for agents |
| Perspective API | Attribute scores 0–1 | Tunable, attrition on long text |
| Self-hosted (Detoxify, Llama Guard) | Custom heads | Requires your labeled data |
| Azure Content Safety | Severity levels 0–6 | Maps cleanly to tiered actions |

Log raw scores and model version on every decision — retrain or recalibrate when vendors update weights silently.

## Tiered action matrix

Design actions as a function of `(category, score, confidence, user_tier)`:

```python
from enum import Enum
from dataclasses import dataclass

class Action(Enum):
    ALLOW = "allow"
    REWRITE = "rewrite"
    BLOCK = "block"
    ESCALATE = "escalate"

@dataclass
class ModerationDecision:
    action: Action
    categories: list[str]
    max_score: float

THRESHOLDS = {
    "harassment": {"block": 0.85, "escalate": 0.55},
    "self_harm": {"block": 0.70, "escalate": 0.40},
    "profanity": {"rewrite": 0.80, "block": 0.95},
    "sexual": {"block": 0.88, "escalate": 0.60},
}

def decide(scores: dict[str, float], tier: str) -> ModerationDecision:
    worst = max(scores, key=scores.get)
    t = THRESHOLDS.get(worst, {"block": 0.90, "escalate": 0.65})
    s = scores[worst]
    if s >= t["block"]:
        return ModerationDecision(Action.BLOCK, [worst], s)
    if s >= t.get("escalate", 1.0):
        return ModerationDecision(Action.ESCALATE, [worst], s)
    if s >= t.get("rewrite", 1.0):
        return ModerationDecision(Action.REWRITE, [worst], s)
    return ModerationDecision(Action.ALLOW, [], s)
```

Enterprise tiers may lower escalate bands to favor human review over false blocks.

## Calibration workflow

1. **Sample production outputs** — stratified by agent type, language, conversation length (10k+ labels minimum for stable PR curves).
2. **Human label** — policy team marks violation type and severity; not just binary toxic/clean.
3. **Plot PR curves per category** — pick thresholds at target recall (e.g., 95% for self-harm) and measure precision cost.
4. **Shadow mode** — log decisions without enforcing for one week; compare to human adjudication.
5. **Enforce with kill switch** — feature flag per agent SKU.

```sql
-- Weekly calibration query: false positive candidates
SELECT output_id, category, score, human_label, decision
FROM moderation_audit
WHERE decision = 'block' AND human_label = 'allow'
  AND created_at > now() - interval '7 days'
ORDER BY score DESC
LIMIT 200;
```

Review the top 200 weekly — if medical terms dominate, adjust allowlists not thresholds blindly.

## Multilingual and dialect bias

Monolingual toxicity models over-flag low-resource languages and AAVE. Mitigations:

- Run language detection first; route to language-specific heads where available.
- Down-weight or skip categories with known bias until labeled data exists.
- Track `block_rate_by_locale` — alert on 3× deviation from en-US baseline.

Never ship global agents with English-only calibration sheets.

## Rewrite pass architecture

When action is `REWRITE`, use a constrained second model:

```python
REWRITE_PROMPT = """Rewrite the assistant message to comply with policy.
Preserve factual content and user-helpful intent. Remove harassment/profanity only.
Do not add new claims. Output the rewritten message only.

Original:
{message}
"""

async def moderate_and_maybe_rewrite(message: str) -> str:
    decision = await classify(message)
    if decision.action == Action.BLOCK:
        return get_safe_fallback(decision.categories)
    if decision.action == Action.REWRITE:
        rewritten = await llm.complete(REWRITE_PROMPT.format(message=message))
        # Re-check rewritten output — prevent bypass
        if (await classify(rewritten)).action == Action.BLOCK:
            return get_safe_fallback(decision.categories)
        return rewritten
    return message
```

Always re-moderate rewrites — attackers and models alike can launder content through rewrite steps.

## Human review queue design

Escalated items need SLAs:

| Queue | SLA | Staffing |
|-------|-----|----------|
| Self-harm signals | 15 min | 24/7 trained moderators |
| Harassment | 4 hr | Business hours + on-call |
| Ambiguous enterprise | 1 hr | Dedicated CSM + trust team |

Store agent run ID, full context (redacted PII), classifier scores, and one-click allowlist pattern for repeated false positives ("term X in oncology agent").

## Agent-specific failure modes

- **Tool injection:** RAG retrieves toxic forum posts → output moderation catches, but log retrieval source for corpus cleanup.
- **Roleplay drift:** Character agents exceed profanity rewrite threshold — use separate SKU thresholds.
- **Structured output:** JSON agents bypass string moderators — moderate rendered user-visible fields only, or schema-aware checks.

## Metrics dashboard

- `moderation_blocks_total` by category, agent_id
- `false_positive_rate` from human audit sample
- `rewrite_success_rate` (rewrite passes re-moderation)
- `escalation_queue_age_p95`
- User complaints correlated with block events

## Resources

- [OpenAI Moderation API guide](https://platform.openai.com/docs/guides/moderation)
- [Perspective API — threshold tuning](https://developers.perspectiveapi.com/s/about-the-api)
- [Llama Guard — Meta safety classifier](https://github.com/meta-llama/PurpleLlama)
- [NIST AI RMF — Map/Measure/Manage](https://www.nist.gov/itl/ai-risk-management-framework)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

