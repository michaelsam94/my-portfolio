---
title: "AI Agents: Experiment Sequential Testing"
slug: "agent-experiment-sequential-testing"
description: "Sequential testing for production A/B experiments — alpha spending, peeking without inflating false positives, group sequential boundaries, and when to stop agent feature rollouts early."
datePublished: "2025-03-31"
dateModified: "2025-03-31"
tags: ["AI", "Agent", "Experiment"]
keywords: "sequential testing, A/B testing, alpha spending, peeking, O'Brien-Fleming, group sequential, experiment stopping rules, false positive rate"
faq:
  - q: "Why does peeking at A/B test results inflate false positives?"
    a: "Each interim look is an independent opportunity to reject the null under noise. If you stop the first time p < 0.05, you accumulate Type I error across looks — a nominally 5% test can reach 20–30% false positive rates depending on peek frequency. Sequential methods allocate α across planned looks so the family-wise error rate stays controlled."
  - q: "When should teams use sequential testing instead of fixed-horizon tests?"
    a: "Use sequential testing when stakeholders will peek anyway (dashboards, weekly reviews), when early stopping saves meaningful cost (LLM inference, infra), or when harm from a bad variant must be detected quickly. Stick with fixed-horizon tests when sample size is small, looks are unplanned, or you need simplicity for regulatory pre-registration."
  - q: "What is alpha spending in group sequential designs?"
    a: "Alpha spending distributes your total Type I error budget (e.g., α=0.05) across interim analyses. O'Brien-Fleming spends little early and more at the final look — conservative early stopping. Pocock spends evenly — easier early stops but stricter overall. Pick a spending function before the first user enters the experiment."
  - q: "How does sequential testing apply to agent feature experiments?"
    a: "Agent experiments often track composite metrics: task success rate, latency, token cost, and human escalation rate. Sequential boundaries should be defined on a primary metric with pre-registered guardrails on secondary metrics. Never stop on a cherry-picked metric after peeking at five dashboards."
---
The product manager opened the experiment dashboard on day three. Conversion looked up 4%. Slack celebrated. Engineering started the rollout PR. On day fourteen, after the full sample arrived, the lift had evaporated — indistinguishable from zero within confidence intervals.

Nobody lied. The team peeked at a noisy interim estimate, treated a random fluctuation as signal, and paid for it in wasted deploys and eroded trust in experimentation. Sequential testing exists to make early looks **statistically honest**: you can monitor progress without turning every dashboard refresh into a false discovery machine.

## Fixed-horizon tests assume you look once

Classical hypothesis testing assumes a single analysis at a pre-specified sample size. Reject H₀ if p < α. That contract breaks the moment someone checks results before n is reached — which is every production team with a live metrics board.

Each interim peek adds another chance to observe a "significant" result under the null. If you peek daily for two weeks on a flat experiment, probability of at least one spurious p < 0.05 exceeds 0.25 even when there is no true effect. The fix is not "don't peek." The fix is **spending your α budget across planned looks**.

## Group sequential boundaries

Group sequential testing divides the experiment into K planned analyses at sample fractions n₁, n₂, …, n_K. At each look, compare the test statistic to a boundary that is stricter than the fixed-horizon critical value early on, relaxing toward the final α.

The O'Brien-Fleming boundary is the conservative default for product teams who want early stopping only on overwhelming evidence:

```
At look k of K, reject H₀ if |Z_k| > c_k

where c_k = Φ^{-1}(1 - α/2) / sqrt(n_k / n_K)   (approximate intuition)
```

Early looks require very large Z-scores. The final look approximates the standard z = 1.96 for α = 0.05 two-sided.

Pocock boundaries use a constant critical value across looks — easier to stop early, but you pay with lower power at the final analysis if the effect is real but moderate.

| Spending function | Early stopping | Final analysis power | Best for |
|-------------------|----------------|----------------------|----------|
| O'Brien-Fleming | Hard | High | Safety-critical, skeptical stakeholders |
| Pocock | Easier | Moderate | Cost-sensitive, fast iteration |
| Haybittle-Peto | Very hard early | High | "Stop only if p < 0.001 early" heuristics made rigorous |

Pre-register K, the look schedule, and the spending function **before** traffic enters. Changing the schedule mid-flight invalidates the guarantees.

## Implementing sequential analysis in code

Most teams do not need a custom prover — they need a reproducible boundary table and a job that evaluates it on schedule.

```python
from dataclasses import dataclass
from scipy import stats
import math

@dataclass
class SequentialLook:
    look_index: int
    cumulative_n: int
    z_critical: float
    alpha_spent: float

def obrien_fleming_boundaries(
    total_n: int,
    looks: list[int],
    alpha: float = 0.05,
) -> list[SequentialLook]:
    """Two-sided O'Brien-Fleming approximate boundaries."""
    z_final = stats.norm.ppf(1 - alpha / 2)
    boundaries = []
    cumulative_alpha = 0.0

    for i, n_k in enumerate(looks, start=1):
        fraction = n_k / total_n
        z_k = z_final / math.sqrt(fraction)
        # Incremental alpha spent at this look (numerical; use tables in production)
        alpha_k = 2 * (1 - stats.norm.cdf(z_k))
        cumulative_alpha = alpha_k
        boundaries.append(
            SequentialLook(i, n_k, z_k, cumulative_alpha)
        )
    return boundaries

def z_test_proportion(p_control: float, p_treatment: float, n: int) -> float:
    p_pool = (p_control + p_treatment) / 2
    se = math.sqrt(2 * p_pool * (1 - p_pool) / n)
    return (p_treatment - p_control) / se

# Planned: 50k users per variant, looks at 10k, 25k, 50k
looks = [10_000, 25_000, 50_000]
bounds = obrien_fleming_boundaries(50_000, looks)

# Interim read at 25k
z = z_test_proportion(0.042, 0.048, 25_000)
look = bounds[1]
decision = "STOP: reject H0" if abs(z) > look.z_critical else "CONTINUE"
print(f"z={z:.3f}, boundary={look.z_critical:.3f} → {decision}")
```

Wire this into your experiment orchestration layer. The analysis job should emit structured events: `look_index`, `z_stat`, `boundary`, `decision`, `primary_metric`, `guardrail_status`. Dashboards display progress; only the batch job triggers stop/ship actions.

## mSPRT and always-valid inference

Group sequential methods require **planned** looks. Modern alternatives like mixture Sequential Probability Ratio Tests (mSPRT) and "always-valid" p-values support continuous monitoring with bounded false positive rates even when look times are irregular.

Experiment platforms (Optimizely Stats Engine, Statsig's sequential testing, GrowthBook with CUPED + sequential options) embed these methods so product teams get honest confidence intervals on dashboards without running R scripts. If you build in-house, read Johari et al. on peeking at A/B tests and the mSPRT construction — the implementation detail matters less than the contract: **the UI must use the sequential p-value, not the fixed-horizon one**.

```typescript
interface SequentialDecision {
  experimentId: string;
  lookIndex: number;
  cumulativeSampleSize: number;
  sequentialPValue: number;
  adjustedAlpha: number;
  canStopForEfficacy: boolean;
  canStopForFutility: boolean;
  guardrailsPassed: boolean;
}

export function evaluateSequentialLook(
  stats: VariantStats,
  config: SequentialConfig,
): SequentialDecision {
  const pSeq = computeMSPRT(stats, config);
  const look = config.boundaries[stats.lookIndex];
  return {
    experimentId: config.experimentId,
    lookIndex: stats.lookIndex,
    cumulativeSampleSize: stats.n,
    sequentialPValue: pSeq,
    adjustedAlpha: look.alphaSpent,
    canStopForEfficacy: pSeq < look.efficacyThreshold && stats.guardrailsOk,
    canStopForFutility: pSeq > look.futilityThreshold,
    guardrailsPassed: stats.guardrailsOk,
  };
}
```

## Futility stopping saves budget

Sequential testing is not only about stopping when you win. **Futility analysis** asks: if the true effect is at most δ_min, what is the probability we ever reach efficacy? If conditional power drops below 10% at the 50% information fraction, continuing wastes traffic that could serve other experiments.

For agent systems burning GPU dollars per request, futility stopping on "no lift in task completion after 40% of planned sample" is often worth more than early efficacy stopping.

## Guardrails and multiple metrics

Agent experiments rarely have a single binary conversion. Typical bundles:

- **Primary:** task success rate (did the agent resolve the ticket?)
- **Guardrails:** p95 latency, cost per session, escalation rate, toxicity score

Sequential boundaries apply to the **primary** metric only. Guardrails use fixed thresholds or Bayesian priors — if escalation rate crosses a safety line, halt regardless of primary metric joy. Document this in the experiment spec:

```
Primary: task_success_rate, O'Brien-Fleming, K=4, α=0.05
Guardrail halt: escalation_rate > control + 2pp OR p95_latency > 8s
Guardrail does NOT trigger early ship
```

Mixing "we stopped because revenue looked good but latency silently doubled" is how agent rollouts cause weekend incidents.

## Operational integration

Treat sequential testing as infrastructure, not a spreadsheet:

1. **Experiment registry** stores spending function, look schedule, primary metric SQL, guardrail definitions.
2. **Analysis cron** runs after each look window closes — not on every realtime dashboard tick unless using always-valid methods.
3. **Auto-pause** puts losing variants on hold when futility triggers; human review before auto-ship on efficacy.
4. **Audit log** records who changed boundaries (should be nobody after launch).

Alert on **SLO burn of experiment integrity**: unplanned looks, manual sample size changes, or dashboard p-values that disagree with sequential p-values (usually means someone wired the wrong column).

## Common mistakes

**Post-hoc look scheduling.** Adding a look because "results are interesting" destroys Type I control. Plan looks at 25%, 50%, 75%, 100% of traffic — or use always-valid monitoring.

**Stopping on secondary metrics.** "Signup was flat but engagement among a segment spiked" is p-hacking with extra steps.

**Ignoring multiple experiments.** Running twenty sequential tests on overlapping traffic without false discovery rate control still yields junk wins. Coordinate with Benjamini-Hochberg or holdout pools.

**Underpowered sequential tests.** Sequential methods do not create power from thin air. If fixed-horizon n is 100k per variant, planning four looks at 5k each is pointless — early boundaries will never cross.

## The takeaway

Sequential testing lets teams peek without lying to themselves. Pre-register looks and spending functions, implement boundaries in the analysis pipeline (not in Slack reactions), and separate primary efficacy from guardrail safety. Agent experiments are expensive enough that honest early stopping pays for the statistics many times over.

## Resources

- [Group Sequential Methods with Applications to Clinical Trials (Jennison & Turnbull)](https://www.crcpress.com/Group-Sequential-Methods-with-Applications-to-Clinical-Trials/Jennison-Turnbull/p/book/9780412985610)

- [Peeking at A/B Tests: Why it matters, and what to do about it (Johari et al.)](https://exp-platform.com/Documents/2017-08-PeekingAtABTests.pdf)

- [Optimizely Stats Engine whitepaper](https://www.optimizely.com/optimization-glossary/stats-engine/)

- [Statsig sequential testing documentation](https://docs.statsig.com/experiments-plus/sequential-testing)

- [Always Valid Inference: Continuous Monitoring of A/B Tests (Howard et al.)](https://arxiv.org/abs/1511.01950)
