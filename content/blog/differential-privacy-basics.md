---
title: "Differential Privacy Basics"
slug: "differential-privacy-basics"
description: "Differential privacy adds calibrated noise so aggregate statistics leak minimal information about individuals. Epsilon, sensitivity, and when DP beats anonymization."
datePublished: "2025-09-24"
dateModified: "2025-09-24"
tags: ["Security"]
keywords: "differential privacy, epsilon delta privacy, Laplace mechanism, privacy budget, DP aggregates, Google differential privacy"
faq:
  - q: "What is differential privacy?"
    a: "Differential privacy (DP) guarantees that the output of an analysis changes minimally whether any single individual's data is included or excluded. Achieved by adding random noise calibrated to query sensitivity. Stronger epsilon means less noise and weaker privacy; weaker epsilon means more noise and stronger privacy."
  - q: "What does the epsilon parameter mean?"
    a: "Epsilon (ε) controls the privacy loss budget — how much information about individuals leaks per query. Lower ε is more private. Organizations set cumulative privacy budgets across queries; exhausting the budget stops further releases. Delta (δ) allows tiny failure probability in approximate DP."
  - q: "When should I use differential privacy instead of anonymization?"
    a: "Use DP when publishing aggregate statistics on sensitive datasets where re-identification from anonymized microdata remains risky — census tabulations, location analytics, ML on user data. Anonymization removes fields; DP mathematically bounds inference from any aggregate you release."
---

Removing names from a dataset doesn't stop someone from combining age, zip, and diagnosis to re-identify patients. Differential privacy attacks the problem differently: **every number you publish carries calibrated noise** so no individual's presence or absence moves the needle much.

## The intuition

Consider counting users with a medical condition in a database. True count: 847. DP releases:

```
published_count = true_count + Laplace(0, sensitivity/ε)
                = 847 + 3.2 = 850.2
```

An attacker can't tell if you were in the database based on this noisy aggregate — your inclusion shifts the distribution by at most e^ε.

## Formal guarantee (simplified)

Mechanism M satisfies **(ε, δ)-differential privacy** if for adjacent datasets D and D' differing by one row, and any output set S:

```
Pr[M(D) ∈ S] ≤ e^ε · Pr[M(D') ∈ S] + δ
```

Adjacent = one person added or removed. ε = 0.1 is very private (noisy); ε = 10 is weak.

## Sensitivity drives noise scale

**Global sensitivity** — maximum change in query result from one row change.

Count query sensitivity = 1 (one person changes count by at most 1).

Sum of ages 0–120 → sensitivity = 120.

**Laplace mechanism:**

```python
import numpy as np

def laplace_mechanism(true_value, sensitivity, epsilon):
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale)
    return true_value + noise

count = 847
noisy_count = laplace_mechanism(count, sensitivity=1, epsilon=0.5)
```

Gaussian mechanism used for (ε, δ)-DP with different noise shape.

## Privacy budget accounting

Each query consumes ε from a **global budget** for the dataset release. Ten queries at ε=0.1 each → total privacy loss composes (basic composition: sum of epsilons; advanced composition tightens bounds).

When budget exhausted — stop releasing or accept higher risk. Product and legal teams set ε thresholds, not engineers alone.

## Local vs central DP

**Central DP** — trusted curator adds noise to aggregates before publication. Census Bureau model.

**Local DP** — each user randomizes their data before sending (Apple keyboard emoji usage). Higher noise per user, no trusted central holder of raw data.

Pick based on trust model and accuracy needs.

## Practical deployments

- **US Census 2020** — DP for redistricting data
- **Google / Apple** — local DP in telemetry
- **OpenDP, Google DP libraries** — production-grade implementations

```python
# Conceptual OpenDP-style pipeline
# 1. Define measurement (count)
# 2. Apply stability bounds (clip contributions)
# 3. Add calibrated noise
# 4. Track budget
```

Clip extreme outliers before sum queries — one billionaire shouldn't dominate sensitivity.

## DP vs k-anonymity vs pseudonymization

| Approach | Guarantee |
|---|---|
| k-anonymity | Each record indistinguishable in group — vulnerable to homogeneity attacks |
| Pseudonymization | Reversible with key — still personal data |
| Differential privacy | Mathematical bound on any inference from output |

DP is strongest for **published aggregates**; doesn't replace access control on raw data.

## Accuracy tradeoffs

Small populations get noisy counts — suppress cells below threshold (**privacy-utility tradeoff**). Hierarchical queries (county → state) need careful budget splitting.

Communicate uncertainty to analysts — DP outputs are stochastic, not bugs.

## Getting started

1. Identify aggregate releases (dashboards, public APIs, research)
2. Define threat model — what must stay private
3. Choose ε with legal/stakeholders (often 0.1–1.0 range debated)
4. Use vetted libraries — don't hand-roll noise
5. Document budget consumption per release

## Local vs global differential privacy

Two deployment models with different tradeoffs:

| | Local DP | Central DP |
|---|---|---|
| Noise added | On device before upload | At aggregation server |
| Trust model | Server never sees raw data | Server sees raw, adds noise on output |
| Accuracy | High per-user noise | Lower noise on aggregates |
| Use case | Apple keyboard, telemetry | Census, published statistics |

Local DP: each user adds noise to their data before sending. Server aggregates noisy values. Central DP: server collects raw data, adds calibrated noise to published aggregates only.

Most enterprise analytics use central DP — local DP sacrifices too much accuracy for small populations.

## Privacy budget accounting

Every DP query consumes privacy budget (ε). Track cumulative consumption:

```python
class PrivacyBudgetTracker:
    def __init__(self, total_epsilon: float):
        self.total = total_epsilon
        self.consumed = 0.0

    def spend(self, epsilon: float, query_name: str):
        if self.consumed + epsilon > self.total:
            raise PrivacyBudgetExhausted(
                f"Query '{query_name}' would exceed budget "
                f"({self.consumed + epsilon:.2f} > {self.total})"
            )
        self.consumed += epsilon
        log_audit(query_name, epsilon, self.consumed)

# Usage
budget = PrivacyBudgetTracker(total_epsilon=1.0)
budget.spend(0.1, "monthly_active_users")
budget.spend(0.05, "revenue_by_region")
# budget.spend(0.9, "deep_dive") → raises PrivacyBudgetExhausted
```

Once budget exhausted, no more DP queries until next release cycle. Document budget allocation in privacy policy.

## OpenDP implementation example

Use vetted libraries — never hand-roll noise:

```python
import opendp.prelude as dp

# Laplace mechanism for count query
def dp_count(true_count: int, epsilon: float, sensitivity: int = 1) -> float:
    scale = sensitivity / epsilon
    noise = dp.laplace_scale(scale).sample()
    return max(0, true_count + noise)

# Example: publish noisy user count
true_users = 10_247
noisy_users = dp_count(true_users, epsilon=0.1)
# Result: ~10,247 ± ~10 ( Laplace noise)
```

OpenDP provides composable privacy mechanisms with proven bounds. Google's DP library offers similar primitives for Go and Java.

## Failure modes

- **Hand-rolled noise** — incorrect calibration; privacy guarantee void
- **Unlimited queries on same dataset** — privacy budget exhausted; re-identification possible
- **Small population suppression ignored** — noisy count of 3 users is meaningless
- **DP on raw data access** — DP protects published aggregates, not database access
- **No budget documentation** — compliance audit fails; can't prove privacy guarantee

## Production checklist

- Vetted DP library used (OpenDP, Google DP) — no hand-rolled noise
- Privacy budget (ε) defined with legal/stakeholders before first release
- Budget tracker prevents queries after exhaustion
- Small population cells suppressed (threshold typically k≥10)
- DP applied to published aggregates only; access control on raw data
- Budget consumption documented per release cycle

## Resources

- [OpenDP project](https://opendp.org/)
- [Google differential privacy library](https://github.com/google/differential-privacy)
- [US Census — Disclosure avoidance handbook](https://www.census.gov/programs-surveys/decennial-census/decade/2020/planning-management/process/disclosure-avoidance.html)
- [The Algorithmic Foundations of Differential Privacy (Dwork & Roth)](https://www.cis.upenn.edu/~aaroth/Papers/privacybook.pdf)
- [Apple — Local differential privacy overview](https://www.apple.com/privacy/docs/Differential_Privacy_Overview.pdf)
