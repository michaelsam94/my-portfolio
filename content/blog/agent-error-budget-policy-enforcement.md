---
title: "AI Agents: Error Budget Policy Enforcement"
slug: "agent-error-budget-policy-enforcement"
description: "Error Budget Policy Enforcement: production patterns for ai teams — design, implementation, testing, security, and operations."
datePublished: "2026-03-18"
dateModified: "2026-03-18"
tags: ["AI", "Agent", "Error"]
keywords: "agent, error, budget, policy, enforcement, ai, production, engineering, architecture"
faq:
  - q: "What is an error budget for an agent service?"
    a: "An error budget is the allowable unreliability over a window, derived from your SLO. If the agent completion SLO is 99.5% monthly, the budget is ~3.6 hours of bad responses per month. Burn comes from timeouts, tool failures, hallucination-triggering errors, and retrieval misses—not just HTTP 500s. When budget exhausts, policy should slow or block risky changes until reliability recovers."
  - q: "How is error budget enforcement different from a generic error rate alert?"
    a: "Alerts fire on symptoms; budgets govern process. A 2% error spike alert pages on-call. Budget enforcement blocks the next deploy, freezes prompt experiments, or requires executive exception. It connects reliability metrics to release velocity—the core SRE bargain—so teams cannot ship features while silently eroding user trust."
  - q: "Which SLIs matter most for LLM agent pipelines?"
    a: "Track end-to-end task success (user got a correct, complete answer), p95 time-to-first-token, tool invocation success rate, and retrieval hit rate. Model-provider 429s and context-length overflows are budget burners. Separate 'hard failures' (5xx, timeout) from 'soft failures' (wrong answer flagged by eval harness)—both consume budget if your SLO includes quality."
  - q: "Can error budget policy coexist with rapid prompt iteration?"
    a: "Yes, with tiered budgets. Production traffic uses the strict monthly SLO. Prompt A/B tests run in a sandbox cohort with its own micro-budget or excluded from production burn if traffic is <1%. When production budget is below 25% remaining, freeze all non-critical experiments automatically via CI gate."
---
Engineering had shipped twelve prompt changes in two weeks. Dashboards showed green—availability was 99.97%. Then support opened a ticket cluster: the agent had started confirming destructive actions without waiting for user approval. Root cause was a prompt regression introduced nine deploys ago. No alert fired because every request returned HTTP 200. The model answered confidently; it was just wrong in a way that violated the product's safety SLO.

Availability metrics lie about agent systems. Error budget policy enforcement exists to connect what users experience to what engineering is allowed to ship. Without automated enforcement, budgets become slide-deck decoration; with it, they become the throttle that keeps experimentation from outrunning reliability.

## From SLO to enforceable budget

An SLO is a target (e.g., 99.5% of agent sessions complete successfully within 60 seconds). The error budget is everything left on the table:

```
monthly_budget_fraction = 1 - SLO_target
monthly_budget_minutes  = monthly_budget_fraction × 43,200 min (30-day month)
```

For 99.5%: budget = 0.5% × 43,200 ≈ **216 minutes** (~3.6 hours) of allowed bad sessions per month.

**Burn rate** measures how fast you consume that budget:

```
burn_rate = (errors_in_window / total_in_window) / (1 - SLO_target)
```

A burn rate of 14.4 over one hour means you will exhaust a 30-day budget in one hour if it continues. Multi-window burn alerts (Google SRE workbook) catch both sudden spikes and slow leaks.

For agents, define **session success** precisely in the SLO doc:

- User received a response (not hung or cancelled)
- No unrecoverable tool error aborted the workflow
- Safety classifier did not block for policy violation attributable to service fault
- Optional: automated eval score above threshold on sampled traffic

Ambiguity here undermines every downstream policy gate.

## Policy tiers: what happens when budget burns

Enforcement is a graduated response, not a single kill switch.

| Budget remaining | Policy action |
|------------------|---------------|
| 50–100% | Normal velocity; experiments allowed |
| 25–50% | Require extra reviewer for deploys touching agent core |
| 10–25% | Block non-critical deploys; freeze prompt A/B tests |
| 0–10% | Incident posture; only reliability fixes ship |
| Exhausted | Executive exception required; postmortem before feature resume |

Automate these gates in CI/CD. A human can override with audit trail, but the default should be mechanical—willpower fails at 11 PM before a launch deadline.

```yaml
# .github/workflows/deploy-gate.yml (conceptual)
jobs:
  error-budget-check:
    runs-on: ubuntu-latest
    steps:
      - name: Query burn from monitoring API
        id: budget
        run: |
          REMAINING=$(curl -s "$BUDGET_API/agent-completion/remaining_pct")
          echo "remaining=$REMAINING" >> $GITHUB_OUTPUT

      - name: Block deploy if budget critical
        if: steps.budget.outputs.remaining < 10
        run: |
          echo "Error budget below 10%. Deploy blocked by policy."
          echo "Override: set label 'budget-exception-approved' on PR"
          exit 1
```

Pair deploy gates with **release windows**: risky changes (new tool integrations, prompt overhauls) only ship when budget is above 50%.

## Implementing burn-rate math in code

Whether you use Datadog, Prometheus, or a custom store, the computation is the same:

```typescript
// slo/burn-rate.ts
type BurnRateWindow = { windowMinutes: number; burnRate: number };

export function computeBurnRate(
  successes: number,
  failures: number,
  sloTarget: number, // e.g. 0.995
): number {
  const total = successes + failures;
  if (total === 0) return 0;
  const errorRate = failures / total;
  const errorBudgetFraction = 1 - sloTarget;
  return errorRate / errorBudgetFraction;
}

export function budgetRemainingPct(
  successes: number,
  failures: number,
  sloTarget: number,
): number {
  const total = successes + failures;
  const allowedErrors = total * (1 - sloTarget);
  const consumed = failures;
  if (allowedErrors === 0) return failures === 0 ? 100 : 0;
  const remaining = Math.max(0, allowedErrors - consumed);
  return (remaining / allowedErrors) * 100;
}

// Multi-window alert: 1h AND 6h burn both elevated → page
export function shouldPage(windows: BurnRateWindow[]): boolean {
  const SHORT = windows.find((w) => w.windowMinutes === 60);
  const LONG = windows.find((w) => w.windowMinutes === 360);
  return (SHORT?.burnRate ?? 0) > 14.4 && (LONG?.burnRate ?? 0) > 6;
}
```

Instrument **failures** with labels: `failure_reason=tool_timeout`, `model_429`, `retrieval_empty`, `safety_block`. Budget dashboards slice burn by cause so postmortems start with data, not guesses.

## Agent-specific SLI instrumentation

HTTP middleware is insufficient. Agent sessions span multiple internal steps:

```python
# observability/agent_session.py
from dataclasses import dataclass, field
from enum import Enum
import time


class StepOutcome(Enum):
    OK = "ok"
    RETRYABLE = "retryable"
    FATAL = "fatal"


@dataclass
class AgentSessionRecorder:
    session_id: str
    started_at: float = field(default_factory=time.time)
    steps: list[dict] = field(default_factory=list)
    terminal_outcome: str | None = None

    def record_step(self, name: str, outcome: StepOutcome, latency_ms: float):
        self.steps.append({
            "name": name,
            "outcome": outcome.value,
            "latency_ms": latency_ms,
        })

    def finish(self, success: bool, failure_reason: str | None = None):
        self.terminal_outcome = "success" if success else failure_reason
        # Emit single event for SLO counting
        metrics.increment(
            "agent_session_total",
            tags={"outcome": self.terminal_outcome},
        )
        metrics.histogram(
            "agent_session_duration_ms",
            (time.time() - self.started_at) * 1000,
        )
```

Count **one session outcome per user task**, not per LLM call. A session with three retried tool calls that eventually succeeds is a success—unless your SLO includes latency, in which case late success still burns latency budget.

## Quality-aware budgets

Hard errors are easy to count. Wrong answers are not. Options:

**Automated eval sampling.** Route 5% of production traffic through a lightweight judge model or rule harness. Failed evals increment a `quality_failure` counter that consumes a separate quality budget—or a weighted fraction of the main budget.

**User feedback signals.** Thumbs-down and regeneration requests are lagging but real. Weight them lower than hard failures to avoid noise from subjective dislike.

**Safety SLO as hard gate.** Policy violations attributable to service misconfiguration (wrong tool enabled, approval step skipped) burn budget at 2× rate—these are existential risk, not UX nitpicks.

Document weighting in the SLO spec so teams do not argue about math during incidents.

## Organizational enforcement

Tools enforce policy; culture makes it stick.

**Error budget review in sprint planning.** If budget is at 30%, the team allocates capacity to reliability work before new features. Product accepts this because the alternative is silent degradation.

**Blameless postmortems on budget exhaustion.** When budget hits zero, the question is systemic—missing eval, bad deploy gate, provider without fallback—not which engineer merged the PR.

**Shared ownership.** Agent reliability spans platform (orchestration), ML (prompts), and infra (GPU quotas). Budget dashboards are visible to all three; enforcement applies to all deploy pipelines.

## Testing policy before you need it

Game-day exercises validate enforcement:

1. Inject 5% synthetic failures into staging agent sessions for one hour.
2. Verify burn-rate alerts fire at expected thresholds.
3. Confirm deploy pipeline blocks when simulated remaining budget drops below 10%.
4. Practice exception workflow: who approves, what gets logged.

Run tabletop scenarios with product: "Budget is at 15%, marketing wants a prompt change for a campaign—what happens?" The answer should be in policy docs, not invented under pressure.

## Anti-patterns that hollow out budgets

**Vanity SLOs at 99.99% with no enforcement.** Teams ignore impossible targets; real regressions hide in the gap between aspirational and enforced SLO.

**Counting only 5xx.** Agent returns 200 with an empty answer—users churn; budget looks fine.

**Per-team budgets without a global cap.** Retrieval team has budget; orchestration team has budget; combined user experience fails while both dashboards are green.

**Manual freeze decisions.** Without CI gates, someone always ships "just this once."

## The takeaway

Error budget policy enforcement turns SRE theory into release discipline for agent systems. Define session-level success, compute burn with multi-window alerts, automate deploy and experiment gates at budget thresholds, and include quality—not just availability—in what counts as failure. The goal is not zero errors; it is predictable tradeoffs between velocity and trust, enforced by machinery rather than memory.

## Resources

- [Google SRE Workbook — Alerting on SLOs (multi-burn-rate)](https://sre.google/workbook/alerting-on-slos/)
- [Google SRE Book — Embracing Risk (error budgets)](https://sre.google/sre-book/embracing-risk/)
- [OpenSLO specification](https://openslo.com/)
- [Datadog Service Level Objectives](https://docs.datadoghq.com/service_management/service_level_objectives/)
- [Prometheus SLI/SLO recording rules patterns](https://prometheus.io/docs/practices/rules/)
