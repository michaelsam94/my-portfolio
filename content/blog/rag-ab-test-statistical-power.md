---
title: "Statistical Power in A/B Tests: Sample Size and Early Stopping"
slug: "rag-ab-test-statistical-power"
description: "How to compute power, choose minimum detectable effect, and avoid peeking bias when running product experiments."
datePublished: "2025-09-14"
dateModified: "2026-07-17"
tags:
  - "Experimentation"
  - "Statistics"
  - "Product"
keywords: "ab test, statistical power, sample size, mde, experimentation"
faq:
  - q: "What power level should product teams target?"
    a: "80% is the usual default — meaning an real effect of your chosen MDE is detected 80% of the time; raise to 90% for high-stakes pricing or trust changes where false negatives are costly."
  - q: "How does baseline conversion affect required sample?"
    a: "Lower baseline rates need larger absolute sample sizes for the same relative lift because variance p(1-p) is smaller near extremes but relative MDEs translate to tiny absolute differences."
  - q: "Can I stop early when results look significant?"
    a: "Naive peeking inflates false positive rate — use sequential testing methods, fixed horizon, or pre-registered stopping rules with alpha spending if you must monitor continuously."
---
Product teams ship A/B tests hoping to detect a one-point lift in conversion, then wonder why the experiment runs for six weeks and still reads inconclusive. Statistical power is the probability that a test will reject the null when a real effect of a specified size exists — and most underpowered experiments were doomed at design time, not at analysis. This article walks through minimum detectable effect choice, sample size formulas, variance reduction, and the peeking traps that make dashboards lie.

## Power, alpha, and MDE defined without jargon

Fix significance level alpha (typically 0.05 two-sided). Choose minimum detectable effect (MDE) delta — the smallest lift that would change the ship decision. Power (1-beta) is then the chance you detect that delta if it is real.

Underpowered tests waste traffic: they look inconclusive when effects exist. Overpowered tests with microscopic MDEs detect trivial lifts that are statistically significant but economically meaningless — a 0.01% relative change on checkout button color with ten million users.

Before writing code, write the decision rule: We will ship if lift >= 2% relative with 95% confidence at 80% power. That sentence drives sample size more than any calculator defaults.

## Sample size for conversion rate metrics

For two-proportion z-test with equal allocation, approximate per-variant sample n:

```
n ≈ 2 * (z_{1-α/2} + z_{1-β})^2 * p̄(1-p̄) / δ^2
```

where p̄ is pooled baseline rate and delta is absolute difference in proportions.

Example: baseline 4%, MDE absolute +0.4 percentage points (10% relative), alpha 0.05, power 0.80 yields roughly 19,000 users per variant. Halving MDE to 0.2 points quadruples required n.

Use pre-experiment data to estimate baseline and daily eligible traffic; divide n by daily volume for runtime. If runtime exceeds product patience, widen MDE or accept lower power explicitly in the experiment charter.

## Ratio metrics and delta methods

Revenue per user, session length, and order value are ratio or heavy-tailed metrics — normal approximations fail. Options:

- **Bootstrap confidence intervals** on user-level aggregates with cluster assignment at user ID.
- **CUPED** variance reduction using pre-period covariates — often cuts required sample 20–40% when covariate correlates with outcome.
- **Linearization** for ratio metrics in large samples with careful delta-method standard errors.

Never analyze ratio metrics by averaging daily ratios across days without weighting — Simpson's paradox lurks in weekly experiment readouts.

## Multiple comparisons and metric families

Primary metric should be one per test. Guardrail metrics (latency, support tickets, refund rate) need correction or hierarchical testing: primary must win before interpreting secondary wins.

When testing multiple variants (A/B/C/n), use Dunnett or false discovery control if exploring; for confirmatory winner selection, pre-register pairwise contrasts or use hierarchical gatekeeping.

Dashboards showing twelve metrics with uncorrected p-values will always show one green cell by chance.

## Peeking, sequential tests, and optional stopping

Checking p-values daily and stopping at first p<0.05 inflates false positives dramatically — a 5% test behaves like 20%+ effective alpha under continuous monitoring.

Mitigations:

1. **Fixed horizon** — decide sample n upfront; analyze once.
2. **Group sequential boundaries** — O'Brien-Fleming spending functions allow interim looks with adjusted thresholds.
3. **Sequential probability ratio tests** — popular in tech via mSPRT implementations with clear stopping boundaries.

If leadership demands mid-flight reads, show confidence intervals and projected runtime, not raw p-values with ship buttons.

## Variance reduction with CUPED and stratification

CUPED adjusts outcome Y using pre-experiment covariate X:

Y_cuped = Y - theta * (X - E[X])

Choose theta to minimize variance; often session count pre-period for conversion tests. Stratified randomization by country or platform ensures balance and enables post-stratified estimation with lower variance.

Document covariates in the experiment spec — post-hoc CUPED on the metric that moved most is p-hacking with extra steps.

## Operational checklist before launch

- Pre-register hypothesis, primary metric, MDE, runtime, and stopping rule in experiment ticket.
- Verify assignment salt stable across deploys; broken bucketing invalidates n.
- Expose sample ratio mismatch (SRM) checks — chi-square on assignment counts flags broken flags early.
- Log exposure events with timestamp; analyze on exposed population, not intent-to-treat leakage from cache.
- Archive variant definitions — retroactive relabeling destroys reproducibility.

## Communicating results to stakeholders

Ship/no-ship memos should lead with confidence interval on primary metric, runtime achieved versus planned, and guardrail status — not p-value alone. When inconclusive, state what MDE was powered for and how many more days would reach 80% power at current traffic — that reframes we need more data as a planning miss, not experimental failure.

## Power calculators and tooling in practice

Use Evan Miller's sample size calculator or Statsig planning tools as starting points — then adjust for cluster assignment if users not independent. Document assumed baseline conversion and MDE in experiment ticket; retroactive changing MDE after peeking invalidates analysis. Export power curve showing probability of detecting 50%, 75%, and 100% of target MDE at planned runtime.

## Org process for experiment registry

Central registry lists active experiments, primary metric, powered MDE, owner, and stop date — prevents overlapping tests polluting same metric. Data science office hours review underpowered designs before launch. Archive losing variants with confidence interval, not just p-value, for institutional learning.

Power is not a statistics homework problem — it is a planning tool that prevents six-week inconclusive tests. Pick an MDE tied to business value, compute n before launch, guard against peeking, and use CUPED when you have pre-period signal. Experiments that end with we need more data usually needed more power on day zero.

Design review checklist item 1 for A/B test statistical power: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in A/B test statistical power often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for A/B test statistical power should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for A/B test statistical power documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for A/B test statistical power: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in A/B test statistical power often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for A/B test statistical power should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for A/B test statistical power documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for A/B test statistical power: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in A/B test statistical power often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for A/B test statistical power should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for A/B test statistical power documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for A/B test statistical power: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in A/B test statistical power often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for A/B test statistical power should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for A/B test statistical power documents escalation when primary and secondary on-call roles are unreachable.
