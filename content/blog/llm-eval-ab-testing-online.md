---
title: "Online A/B Testing for LLM Features"
slug: "llm-eval-ab-testing-online"
description: "Run online A/B tests on LLM features: experiment design, guardrail metrics, prompt and model variants, statistical pitfalls, and when offline evals lie."
datePublished: "2024-11-18"
dateModified: "2024-11-18"
tags: ["AI", "LLM", "Machine Learning", "Architecture"]
keywords: "LLM A/B testing, online experiment LLM, prompt A/B test, model comparison production, LLM feature flags"
faq:
  - q: "What should I A/B test in an LLM product?"
    a: "Model tier (GPT-4 vs mini), prompt versions, retrieval parameters (chunk count, reranker on/off), response format (with/without citations), and UX changes (streaming vs batch). Don't A/B test safety filters without strong guardrails — the losing variant might violate policy before you detect it."
  - q: "How long should an LLM A/B test run?"
    a: "Long enough for your primary metric to reach statistical significance — usually 1–2 weeks minimum for B2B with moderate traffic. LLM metrics have high variance; avoid stopping early on a good day. Pre-register sample size and run duration before launching."
  - q: "What guardrail metrics prevent shipping harmful variants?"
    a: "Track alongside primary metrics: error rate, latency p99, cost per session, thumbs-down rate, safety violation rate, and human escalation rate. Auto-kill a variant if guardrails breach thresholds even if the primary metric looks good."
---

Offline eval said the new prompt was 8% better. Online, users clicked thumbs-down 12% more often and average session cost went up 40%. LLM quality doesn't fully compress into a benchmark score — online A/B testing catches the gap between eval wins and user experience. It's slower and noisier than offline eval, but it's the only test that counts when real users with real money interact with your product.

## Experiment architecture

```python
async def handle_request(request: Request) -> Response:
    variant = experiment.assign(
        experiment="prompt_v3_test",
        unit_id=request.tenant_id,  # or user_id
    )
    prompt = PROMPTS[variant]  # "control" | "treatment"
    response = await orchestrator.run(request, prompt_version=variant)
    await analytics.track("llm_response", {
        "experiment": "prompt_v3_test",
        "variant": variant,
        "tenant_id": request.tenant_id,
        "latency_ms": response.latency,
        "cost_usd": response.cost,
        "thumbs": None,  # filled async on feedback
    })
    return response
```

Use consistent hashing on `tenant_id` or `user_id` — not `request_id` — so the same user always sees the same variant.

## Choosing the unit of randomization

| Unit | Use when |
|------|----------|
| User | Consumer apps, personal experience |
| Tenant | B2B SaaS, team-level behavior |
| Session | Short experiments, high traffic |
| Request | Only for stateless, low-stakes (risky — inconsistent UX) |

Tenant-level randomization prevents one team seeing two different bot personalities in the same workflow.

## Primary vs guardrail metrics

**Primary** (what you're trying to improve):

- Task completion rate
- Thumbs-up rate
- Time to resolution
- Conversion on AI-assisted flows

**Guardrails** (don't regress):

- Cost per session
- Latency p95/p99
- Error/timeout rate
- Escalation to human rate
- Safety flag rate

```python
GUARDRAILS = {
    "cost_per_session": {"max_lift": 0.15},      # no >15% cost increase
    "latency_p99": {"max_lift": 0.20},
    "safety_violations": {"max_absolute": 0.001}, # hard ceiling
}
```

Auto-stop treatment if guardrails breach for 24 hours.

## What to test

High-value experiments:

1. **Model downgrade** — can mini handle this feature? (usually biggest cost win)
2. **Retrieval config** — top-5 vs top-10 chunks, reranker on/off
3. **Prompt structure** — citation format, tone, verbosity
4. **Caching** — semantic cache on/off for FAQ feature

Low-value: testing punctuation in system prompt on low traffic — you'll never reach significance.

## Statistical pitfalls

- **Peeking** — checking results daily and stopping when significant inflates false positives. Pre-register duration.
- **Multiple comparisons** — testing 5 metrics without correction finds "significance" by chance. Designate one primary metric.
- **Simpson's paradox** — treatment wins overall but loses per segment. Break down by tenant tier, language, query type.
- **Novelty effects** — users react to change temporarily. Run at least 7 days.

Use sequential testing or Bayesian methods if your experimentation platform supports them — they handle peeking better than fixed-horizon tests.

## Connecting online to offline

Before launching online:

1. Run offline eval on both variants (golden dataset)
2. Ensure offline direction matches hypothesis
3. Launch online with 5–10% traffic to treatment
4. Ramp if guardrails hold

After online:

- Sample 100 treatment responses for human review
- Add failure cases to offline golden set
- Offline eval prevents regression on next variant

## Feature flag integration

Use your existing flag system (LaunchDarkly, Unleash, custom):

```yaml
experiment:
  name: model_routing_v2
  variants:
    control: { model: "gpt-4o", weight: 50 }
    treatment: { model: "gpt-4o-mini", weight: 50 }
  targeting:
    include_tenants: ["internal", "beta-cohort"]
```

Start with internal/beta tenants. Expand after guardrails pass.

## Document everything

Experiment log per test:

- Hypothesis, variants, metrics, duration
- Result: ship, revert, iterate
- Link to prompt/model versions deployed

Future you won't remember why `prompt_v2` was reverted.

## Statistical significance for LLM experiments

Don't ship on gut feel — compute significance:

```python
from scipy.stats import chi2_contingency

def ab_test_significance(control_successes, control_total,
                          treatment_successes, treatment_total,
                          alpha=0.05):
    table = [
        [control_successes, control_total - control_successes],
        [treatment_successes, treatment_total - treatment_successes],
    ]
    chi2, p_value, _, _ = chi2_contingency(table)
    return {
        "p_value": p_value,
        "significant": p_value < alpha,
        "control_rate": control_successes / control_total,
        "treatment_rate": treatment_successes / treatment_total,
    }

# Example: thumbs-up rate
result = ab_test_significance(450, 1000, 520, 1000)
# p=0.003 → significant improvement in treatment
```

Minimum sample size: 500 users per variant for 5% effect detection at 80% power. Run experiments for at least 1 week to capture day-of-week effects.

## Guardrail metrics

Primary metric alone can hide regressions — monitor guardrails:

```python
GUARDRAILS = {
    "latency_p99_ms": {"max": 3000, "action": "pause_experiment"},
    "error_rate": {"max": 0.02, "action": "pause_experiment"},
    "safety_violation_rate": {"max": 0.001, "action": "kill_experiment"},
    "cost_per_request_usd": {"max": 0.05, "action": "alert"},
}

def check_guardrails(experiment_metrics):
    for metric, threshold in GUARDRAILS.items():
        if experiment_metrics[metric] > threshold["max"]:
            trigger_action(threshold["action"], metric)
```

Auto-pause experiment if safety violation rate exceeds threshold — don't wait for manual review.

## Sequential testing and early stopping

Fixed-horizon tests waste time when effect is obvious early. Sequential testing allows early stop:

```
Day 1: 200 users/variant → guardrails pass, no significance
Day 3: 600 users/variant → p=0.04, significant → ship treatment
Day 7: (skipped — already decided)
```

Use sequential testing frameworks (Statsig, Optimizely) that adjust significance thresholds for multiple looks. Naive early stopping inflates false positive rate.

## Failure modes

- **Ship on insufficient sample size** — false positive; treatment worse at scale
- **No guardrail metrics** — latency regression hidden by primary metric improvement
- **Experiment on all users immediately** — blast radius too large; start with beta cohort
- **No experiment log** — same failed experiment repeated months later
- **Multiple simultaneous experiments** — interaction effects confound results

## Production checklist

- Minimum 500 users per variant before decision
- Guardrail metrics auto-pause experiment on threshold breach
- Beta/internal cohort first; expand after guardrails pass
- Experiment log with hypothesis, result, and prompt/model version
- Statistical significance computed before shipping (p < 0.05)
- Failed experiments add cases to offline golden eval set

Run online A/B with guardrail metrics (latency, error rate) not just quality score — better model that doubles latency loses users.

## Resources

- [Evan Miller's A/B testing sample size calculator](https://www.evanmiller.org/ab-testing/sample-size.html)
- [Statsig experimentation platform docs](https://docs.statsig.com/experiments-plus/)
- [Google's Trustworthy Online Controlled Experiments](https://experimentguide.com/)
- [Netflix experimentation culture (architecture)](https://netflixtechblog.com/its-all-a-bout-testing-the-netflix-experimentation-platform-4e1ca458c15)
- [OpenAI evals best practices](https://platform.openai.com/docs/guides/evals)
