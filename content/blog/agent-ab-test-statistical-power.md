---
title: "AI Agents: Ab Test Statistical Power"
slug: "agent-ab-test-statistical-power"
description: "Statistical power is the difference between experiments that detect real lifts and ones that waste weeks on noise — sample size math, pre-registration, and stopping rules for production A/B tests."
datePublished: "2025-03-29"
dateModified: "2025-03-29"
tags: ["AI", "Agent"]
keywords: "A/B testing, statistical power, sample size, minimum detectable effect, hypothesis testing, experiment design, Type II error, sequential testing"
faq:
  - q: "What is statistical power in an A/B test?"
    a: "Power (typically denoted 1−β) is the probability that your test detects a real effect of a given size when one exists. At 80% power, if the true lift is your minimum detectable effect, you will reject the null hypothesis 80% of the time. The remaining 20% is a Type II error — a false negative."
  - q: "How much traffic do I need for an A/B test?"
    a: "Sample size depends on baseline conversion rate, minimum detectable effect (MDE), significance level (α), and desired power. A site with 2% conversion detecting a 10% relative lift (2.0% → 2.2%) typically needs roughly 30,000 users per variant at α=0.05 and 80% power. Use a calculator; do not guess."
  - q: "Can I stop an A/B test early when results look significant?"
    a: "Peeking inflates false positive rates unless you use sequential testing methods (e.g., O'Brien-Fleming boundaries, mSPRT, or Bayesian approaches with proper priors). Stopping the first time p < 0.05 turns a nominally 5% α test into a 20–30% false positive rate depending on peek frequency."
  - q: "What minimum detectable effect should I choose?"
    a: "Pick the smallest lift that would justify the engineering cost of shipping the variant. If a 0.5% relative improvement is not worth a deploy, do not power the test to detect it — you will run for months. Align MDE with product and finance, not statistics alone."
---
Product teams love A/B tests because they promise objectivity. Data teams dread them because most experiments are designed to fail quietly — not with a dramatic wrong answer, but with a inconclusive shrug after three weeks of split traffic.

The culprit is usually statistical power. An underpowered experiment cannot distinguish a real improvement from sampling noise. Teams ship the control by default, conclude "the variant didn't work," and never learn that the test was never capable of detecting the lift in the first place.

## Power in one picture

Hypothesis testing balances four linked parameters:

| Parameter | Symbol | Typical value | What it means |
|-----------|--------|---------------|---------------|
| Significance level | α | 0.05 | False positive rate if null is true |
| Power | 1−β | 0.80 | True positive rate if effect exists |
| Effect size | δ or MDE | domain-specific | Smallest lift worth detecting |
| Sample size | n | computed | Users per variant |

Fix any three and the fourth is determined. In practice you choose α, power, and MDE, then calculate n before launching.

The null hypothesis H₀: treatment effect = 0. The alternative H₁: effect ≥ MDE. Power is P(reject H₀ | H₁ is true).

A test with 20% power is a coin flip with extra steps. Yet I routinely audit experiment configs where teams set 50/50 splits on a feature with 500 daily exposures and expect to detect a 3% relative lift on a 1.2% conversion metric within two weeks. The math says they need eight months.

## Sample size for proportion metrics

Most product experiments measure binary outcomes: clicked, subscribed, purchased. For two-proportion z-tests, sample size per variant approximates:

```
n ≈ 2 × (z_{α/2} + z_β)² × p(1−p) / δ²
```

Where p is baseline conversion rate and δ is absolute lift (not relative). A 10% *relative* lift on 2% baseline is only 0.2 absolute percentage points.

```python
import math
from scipy import stats

def sample_size_proportions(
    baseline: float,
    relative_lift: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Users per variant for two-sided proportion test."""
    p1 = baseline
    p2 = baseline * (1 + relative_lift)
    delta = abs(p2 - p1)
    p_bar = (p1 + p2) / 2

    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)

    n = (2 * (z_alpha + z_beta) ** 2 * p_bar * (1 - p_bar)) / (delta ** 2)
    return math.ceil(n)

# Example: 2% baseline, detect 10% relative lift (→ 2.2%)
n_per_variant = sample_size_proportions(0.02, 0.10)
print(f"Need {n_per_variant:,} users per variant")  # ~31,000
```

For continuous metrics (revenue per user, session duration), swap in Cohen's d and use t-test formulas. Revenue metrics with heavy tails need larger samples or winsorization — raw means are dominated by outliers and inflate variance.

## Pre-registration beats post-hoc storytelling

Before any traffic splits, document:

1. **Primary metric** — one metric decides ship/no-ship
2. **MDE** — smallest effect worth detecting
3. **Sample size and runtime** — derived from MDE, not vibes
4. **Secondary metrics** — exploratory, not decision criteria
5. **Segmentation plan** — pre-specified slices, not "let's check mobile"

Store this in your experiment platform or a locked doc. When the PM asks on day four "can we also look at returning users in Germany," you have a paper trail distinguishing confirmatory from exploratory analysis.

Exploratory slices are fine. Using them as ship criteria after the fact is p-hacking with a spreadsheet.

## The peeking problem and legitimate early stopping

Classical fixed-horizon tests assume you look at results exactly once, at predetermined n. Real teams peek daily. Each peek is an additional hypothesis test on the same data without α correction.

If you peek 10 times during an experiment, your effective false positive rate exceeds 15% even with nominal α=0.05.

Mitigations:

**Fixed horizon (simplest).** Do not look until n reaches pre-calculated sample size. Hard discipline, zero methodology overhead.

**Sequential probability ratio test (SPRT / mSPRT).** Valid early stopping with controlled error rates. Statsig, Optimizely, and Eppo implement variants. Requires platform support.

**Group sequential designs.** Pre-plan interim analyses at 50% and 100% sample with Bonferroni or O'Brien-Fleming adjusted boundaries.

**Bayesian experiments.** Report P(variant > control | data). Still requires a pre-specified decision rule — "stop if prob best > 95%" — not moving goalposts.

```typescript
// Anti-pattern: daily peek with naive p-value
async function shouldShipUnsafe(experimentId: string): Promise<boolean> {
  const result = await statsEngine.analyze(experimentId);
  // Each call is a separate peek — inflates false positives
  return result.pValue < 0.05;
}

// Better: enforce fixed horizon in the platform
async function shouldShip(experimentId: string): Promise<"ship" | "hold" | "not_ready"> {
  const exp = await experimentStore.get(experimentId);
  const result = await statsEngine.analyze(experimentId);

  if (exp.currentSampleSize < exp.requiredSampleSize) {
    return "not_ready"; // do not evaluate p-value yet
  }
  return result.pValue < exp.alpha ? "ship" : "hold";
}
```

## Multiple comparisons and metric gardens

Every additional metric you treat as confirmatory multiplies false positive risk. Ten independent metrics at α=0.05 expect half a false significant result even under the null.

Hierarchy of evidence:

1. One primary metric, one decision
2. Secondary metrics labeled exploratory in the report
3. Guardrail metrics (latency, error rate, support tickets) with "do no harm" thresholds, not lift targets

For guardrails, use non-inferiority framing: "variant error rate must not exceed control by more than 0.1%."

## Variance reduction: the free lunch

If sample size is the bottleneck, reduce variance before asking for more traffic:

**CUPED (Controlled-experiment Using Pre-Experiment Data).** Adjust post-treatment outcomes by pre-treatment covariates. Often cuts required sample size 30–50% when users have stable pre-period behavior.

**Stratified randomization.** Balance on known high-variance dimensions (country, plan tier) at assignment time.

**User-level clustering.** For B2B, randomize at account level, not user level, to avoid interference.

```python
def cuped_adjust(
    post_metric: np.ndarray,
    pre_metric: np.ndarray,
) -> np.ndarray:
    """Return CUPED-adjusted metric for variance reduction."""
    theta = np.cov(post_metric, pre_metric)[0, 1] / np.var(pre_metric)
    pre_mean = pre_metric.mean()
    return post_metric - theta * (pre_metric - pre_mean)
```

Check with your stats team whether CUPED assumptions hold for your metric — it fails when pre-period data is missing or non-stationary.

## Power analysis for LLM and agent features

AI product experiments add wrinkles:

**Latency as a guardrail.** A prompt change may lift conversion while p99 latency crosses 3 seconds. Power the guardrail separately or use composite success criteria.

**Non-stationarity.** Model updates upstream of your feature change mid-experiment. Freeze model versions during tests or include version as a covariate.

**Heavy-tailed cost metrics.** Token spend per session has infinite-looking variance. Median-based tests or log-transform before computing sample size.

**Network effects.** If treatment users affect control users (shared marketplace inventory), independent-sample formulas underestimate required n. Cluster randomization or switchback designs apply.

## Reporting results honestly

When the test concludes, report:

- Point estimate and confidence interval, not just p-value
- Achieved power at observed effect (post-hoc power is misleading for interpretation, but "we were powered to detect 5% lift and observed 1%" is informative)
- Runtime and sample size relative to plan
- Any protocol deviations (early stop, filter changes, incident exclusions)

"We didn't reach significance" is ambiguous. "We observed +1.2% relative lift (95% CI: −0.8% to +3.2%) with 85% of planned sample; we are underpowered to confirm lifts below 3%" is actionable.

## Organizational habits that compound

Teams with high experiment velocity share a few practices:

- **Experiment review before launch** — a 15-minute stats check on MDE and n
- **Shared calculator** — same formulas in the platform and the wiki
- **Kill switch on underpowered tests** — platform warns when projected runtime exceeds 4 weeks
- **Archive of inconclusive tests** — meta-analysis across similar features reveals if MDEs were systematically too ambitious

Statistical power is not academic pedantry. It is the contract between product and data teams about what "we tested it" actually means. Design for power before you split traffic, stop peeking without correction, and treat every inconclusive result as a sample size problem until proven otherwise.

## Resources

- [Evan Miller: Sample Size Calculator (proportions)](https://www.evanmiller.org/ab-testing/sample-size.html)
- [Google: Overlapping Experiment Infrastructure (2010 paper)](https://research.google/pubs/pub36500/)
- [Microsoft ExP platform documentation on A/B testing](https://www.microsoft.com/en-us/research/group/experimentation-platform-exp/)
- [Imbens & Rubin: Causal Inference for Statistics, Social, and Biomedical Sciences](https://www.cambridge.org/core/books/causal-inference-for-statistics-social-and-biomedical-sciences/71126BE7574D334F988712FDE354DAE5)
- [Statsig docs: Sequential testing and CUPED](https://docs.statsig.com/experiments-plus/stats-engine)
