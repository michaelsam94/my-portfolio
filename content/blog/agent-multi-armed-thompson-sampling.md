---
title: "AI Agents: Multi Armed Thompson Sampling"
slug: "agent-multi-armed-thompson-sampling"
description: "Thompson sampling balances exploration and exploitation for agent prompt and model selection—if you store sufficient statistics, delay rewards correctly, and monitor regret."
datePublished: "2025-07-25"
dateModified: "2025-07-25"
tags: ["AI", "Agent", "Multi"]
keywords: "Thompson sampling, multi-armed bandit, agent prompt optimization, Bayesian A/B testing, exploration exploitation, contextual bandits, online experiments"
faq:
  - q: "When should agent teams use Thompson sampling instead of fixed A/B splits?"
    a: "Use Thompson sampling when you have many arms (prompt variants, models, retrieval settings), traffic is uneven across cohorts, and you want automatic exploration decay without hand-tuned epsilon schedules. Fixed splits are simpler when you run one rare experiment with strict statistical power requirements."
  - q: "What reward signal works best for agent bandits?"
    a: "Prefer delayed, task-level rewards: ticket resolved without handoff, user thumbs-up, or revenue attributed within a session window. Per-token proxies optimize the wrong objective and react too quickly to noise."
  - q: "How do you avoid cold-start pain with new arms?"
    a: "Seed priors from offline eval, use optimistic initial Beta parameters, or allocate a minimum traffic floor until each arm has enough samples to estimate variance. Never deploy a brand-new arm with a zero prior unless you accept early losses."
  - q: "Can Thompson sampling run entirely in the request path?"
    a: "Selection must be fast—read arm weights from Redis or an in-memory cache updated asynchronously. Posterior updates belong in a stream processor or batch job that consumes outcome events, not in the critical latency path of every agent turn."
---
Product wanted twelve prompt variants for the billing agent by Friday. Engineering wanted statistical rigor. Marketing wanted "always show the winner." A fixed 50/50 test could compare two arms; it chokes on twelve. Epsilon-greedy exploration works but tuning epsilon becomes a part-time job. **Thompson sampling**—pick the arm with the highest draw from each arm's posterior reward distribution—gives you adaptive exploration with one clean rule: sample, act, observe, update.

For agent systems, bandits show up everywhere: choosing among LLM backends, prompt templates, retrieval `top_k`, or tool routing heuristics. This post focuses on the production mechanics that textbook derivations skip: delayed rewards, non-stationarity when users change behavior, and storage layouts that do not collapse under Redis hot keys.

## Intuition without the integrals

Each arm (variant) has an unknown success rate. You maintain a belief—commonly Beta–Bernoulli for binary rewards like "task succeeded."

After observing `s` successes and `f` failures for arm `i`, the posterior is `Beta(α₀ + s, β₀ + f)`. To choose an arm, draw `θᵢ ~ Beta(αᵢ, βᵢ)` for every arm and pick the arm with largest `θᵢ`. Arms with high uncertainty get occasional lucky draws and extra trials; arms with proven poor performance fade naturally.

Compared to UCB1, Thompson sampling tends to incur lower regret in practice and handles many arms without per-arm confidence bookkeeping in application code.

## Agent-specific wrinkles

Web landing page bandits see immediate clicks. Agents see:

- **Delayed rewards** — human approval arrives minutes later
- **Session correlation** — multiple turns belong to one decision unit
- **Non-stationarity** — ticket mix shifts Monday mornings
- **Safety constraints** — some arms must never exceed caps (new model with higher hallucination rate)

Treat the **session** (or ticket) as the experimental unit when rewards reflect task completion, not individual HTTP requests.

## Reference implementation (Beta–Bernoulli)

Core logic in Python, suitable for offline simulation before production:

```python
# bandit/thompson.py
from dataclasses import dataclass, field
import random
import math

@dataclass
class ArmStats:
    successes: int = 0
    failures: int = 0
    alpha0: float = 1.0
    beta0: float = 1.0

    def sample(self) -> float:
        a = self.alpha0 + self.successes
        b = self.beta0 + self.failures
        return random.betavariate(a, b)

    def mean(self) -> float:
        a = self.alpha0 + self.successes
        b = self.beta0 + self.failures
        return a / (a + b)

@dataclass
class ThompsonBandit:
    arms: dict[str, ArmStats] = field(default_factory=dict)

    def select_arm(self, eligible: list[str] | None = None) -> str:
        candidates = eligible or list(self.arms.keys())
        best_arm, best_draw = None, -1.0
        for arm in candidates:
            draw = self.arms[arm].sample()
            if draw > best_draw:
                best_arm, best_draw = arm, draw
        assert best_arm is not None
        return best_arm

    def update(self, arm: str, reward: bool) -> None:
        stats = self.arms.setdefault(arm, ArmStats())
        if reward:
            stats.successes += 1
        else:
            stats.failures += 1
```

Simulate regret against a fixed best arm to validate your instrumentation before touching production traffic.

## Production architecture

Split **decision** from **learning**:

```
┌─────────────┐    assign arm     ┌──────────────┐
│ Agent API   │ ────────────────► │ Assignment   │
│ (read only) │ ◄──────────────── │ cache (Redis)│
└─────────────┘    posteriors     └──────▲───────┘
                                         │
                               batch/stream updates
                                         │
                                  ┌──────┴───────┐
                                  │ Outcome      │
                                  │ consumer     │
                                  └──────▲───────┘
                                         │
                           delayed rewards (Kafka/SQS)
```

Request path (TypeScript sketch):

```typescript
type ArmPosterior = { armId: string; alpha: number; beta: number };

export async function pickPromptArm(experimentId: string): Promise<string> {
  const posteriors: ArmPosterior[] = await redis.getJson(
    `bandit:${experimentId}:posteriors`
  );
  let best: { armId: string; draw: number } | null = null;
  for (const p of posteriors) {
    const draw = sampleBeta(p.alpha, p.beta);
    if (!best || draw > best.draw) best = { armId: p.armId, draw };
  }
  return best!.armId;
}

// Called once per session, not per token
export async function logAssignment(
  sessionId: string,
  experimentId: string,
  armId: string
): Promise<void> {
  await events.publish("bandit.assignment", {
    sessionId,
    experimentId,
    armId,
    ts: Date.now(),
  });
}
```

Outcome worker joins assignments with delayed labels:

```python
# workers/bandit_update.py
def process_outcome(event):
    assign = db.get_assignment(event.session_id, event.experiment_id)
    if not assign:
        return  # orphan outcome — metrics should alarm
    reward = event.task_resolved and not event.policy_violation
    bandit.update(assign.arm_id, reward)
    redis.set_posteriors(event.experiment_id, bandit.snapshot())
```

Use idempotent outcome processing—Kafka at-least-once delivery duplicates updates otherwise.

## Priors from offline eval

Cold-start every arm at `Beta(1,1)` wastes user pain. Seed from offline eval:

```python
def seed_from_eval(base_rate: float, n_pseudo: int = 50) -> ArmStats:
    successes = round(base_rate * n_pseudo)
    failures = n_pseudo - successes
    return ArmStats(successes=successes, failures=failures, alpha0=1, beta0=1)
```

Document pseudo-count magnitude—too high freezes exploration; too low ignores useful offline signal.

## Safety rails

Bandits optimize average reward, not worst-case risk. Add guardrails:

- **Kill switch** per arm when policy violation rate exceeds threshold in sliding window
- **Traffic caps** on experimental models (max 5% until 500 sessions observed)
- **Holdout** fraction always routed to production baseline for drift detection

```python
def eligible_arms(bandit, experiment_cfg, metrics) -> list[str]:
    arms = list(bandit.arms.keys())
    safe = []
    for arm in arms:
        if metrics.violation_rate(arm, window="1h") > experiment_cfg.max_violation:
            continue
        if metrics.sessions(arm) < experiment_cfg.min_samples:
            if metrics.total_sessions(experiment_cfg.id) > 1000:
                continue  # stop exploring clearly bad arms after global warmup
        safe.append(arm)
    return safe or [experiment_cfg.baseline_arm]
```

## Monitoring what matters

Dashboards should show:

| Metric | Why |
|--------|-----|
| **Cumulative regret** vs oracle arm | Bandit health |
| **Arm traffic share** | Exploration not stuck |
| **Time-to-first-reward** | Delay pipeline broken? |
| **Assignment/outcome join rate** | Logging gaps |
| **Baseline holdout delta** | Non-stationarity or bug |

Alert when one arm exceeds 95% traffic for 24h unexpectedly—often a stale cache, not a miracle winner.

## When not to use Thompson sampling

Skip bandits when:

- Sample size is too small for any adaptive method (low-traffic B2B tenants)
- Regulatory requirements demand fixed proportions and pre-registered analysis
- Reward signal arrives too late relative to experiment duration (weeks-long sales cycles without proxies)
- Arms are not interchangeable (different user segments need contextual bandits or separate experiments)

For contextual features (plan tier, locale), move to **contextual Thompson sampling** or linear UCB with logged propensities—do not pretend a global bandit is personalized.

## Worked example: three prompt arms

Suppose three billing prompts (`p_short`, `p_detailed`, `p_policy_first`) run under Thompson sampling with Beta priors seeded from offline approval rates: 0.88, 0.91, and 0.86 with 40 pseudo-samples each. Early traffic explores all three; after 2,000 sessions, `p_detailed` concentrates near 70% assignment because its posterior tightens around 0.90 while `p_policy_first` stops receiving traffic once violations spike.

If Monday ticket volume doubles, non-stationarity may lift `p_short` temporarily—users want faster answers. A holdout baseline arm still receiving 10% traffic reveals the shift before the bandit fully adapts. Without that holdout, you might attribute seasonality to prompt superiority and over-commit.

Document arm diffs in experiment README files so PMs know *why* traffic moved, not just *that* it moved.

## Closing

Multi-armed Thompson sampling is a workhorse, not magic. It shines when agent teams iterate many prompts and models under noisy, delayed feedback—provided you treat assignment logging, posterior refresh, and safety caps as first-class infrastructure. Get those boring pieces right, and the math takes care of exploration without another three-hour meeting about epsilon values.

## Resources

- [A Tutorial on Thompson Sampling (Russo et al., 2018)](https://web.stanford.edu/~bvr/pubs/TS_Tutorial.pdf) — comprehensive introduction and regret discussion
- [Multi-Armed Bandits (Lattimore & Szepesvári, 2020)](https://tor-lattimore.com/downloads/book/book.pdf) — free textbook covering Thompson sampling and alternatives
- [Google Optimize alternatives / Experimentation (Google Analytics)](https://developers.google.com/analytics/devguides/collection/ga4/experimentation) — patterns for online experiment assignment (conceptual parallels)
- [Netflix tech blog: interleaving and bandits](https://netflixtechblog.com/) — industry write-ups on adaptive experimentation at scale (search for bandit-related posts)
- [Vowpal Wabbit contextual bandit docs](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/examples/contextual_bandits.html) — when agent arms need user-context features beyond vanilla Thompson sampling
