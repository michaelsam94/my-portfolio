---
title: "Evaluating Agent Trajectories"
slug: "agent-evaluation-trajectory-analysis"
description: "How to evaluate LLM agent trajectories: step-level metrics, goal completion, tool accuracy, efficiency scores, and building eval datasets that catch real regressions."
datePublished: "2026-06-25"
dateModified: "2026-06-25"
tags: ["AI Agents", "LLM", "Testing", "Architecture"]
keywords: "agent evaluation, trajectory analysis, agent metrics, LLM agent benchmarks, tool use evaluation"
faq:
  - q: "What is an agent trajectory?"
    a: "An agent trajectory is the full sequence of steps an agent takes to complete a task: each LLM call, tool invocation, observation, and intermediate decision from the initial user message to the final response. Evaluating trajectories means scoring not just the final answer but the path taken to get there."
  - q: "What metrics matter most for agent evaluation?"
    a: "Goal completion rate is the north star. Supporting metrics include tool selection accuracy (did it pick the right tool?), argument correctness, step efficiency (fewest steps to goal), recovery rate on injected failures, and cost per successful run. A correct answer reached in 40 steps is a regression even if the final text looks fine."
  - q: "How many eval scenarios do you need?"
    a: "Start with 30–50 scenarios covering your top user intents, plus 10–15 adversarial cases (ambiguous input, missing data, tool failures). Expand when you see production failures not covered by existing scenarios. Quality and coverage of edge cases matter more than raw count."
---

Final-answer evals lie about agent quality. An agent that answers correctly after calling the wrong tool three times, burning $2 in tokens, and nearly triggering a refund on the wrong order is not production-ready — but a naive "does the response contain the right keyword?" eval passes it green. Trajectory evaluation scores the *path*, not just the destination: which tools fired, whether arguments were valid, how many steps it took, and whether it recovered when things broke. This is how you catch regressions that answer-level checks miss entirely.

## Trajectory anatomy

Every agent run produces a trace:

```json
{
  "scenario_id": "refund_order_001",
  "steps": [
    {"type": "llm", "tool_calls": [{"name": "lookup_order", "args": {"id": "4521"}}]},
    {"type": "tool_result", "name": "lookup_order", "output": {"status": "shipped"}},
    {"type": "llm", "tool_calls": [{"name": "create_refund", "args": {"order_id": "4521"}}]},
    {"type": "tool_result", "name": "create_refund", "output": {"refund_id": "R-99"}},
    {"type": "llm", "tool_calls": [], "content": "Refund R-99 initiated for order 4521."}
  ],
  "outcome": "success",
  "total_steps": 5,
  "cost_usd": 0.04
}
```

Score each dimension independently. An agent can succeed on outcome while failing on efficiency.

## Core metrics

**Goal completion** — binary or graded. Did the user's task get done? Use structured checks where possible:

```python
def eval_refund_scenario(trace, expected):
    refund_calls = [s for s in trace.steps if s.get("name") == "create_refund"]
    assert len(refund_calls) == 1, "should call create_refund exactly once"
    assert refund_calls[0]["args"]["order_id"] == expected["order_id"]
    assert "refund" in trace.final_response.lower()
```

**Tool selection accuracy** — for each step, was the chosen tool in the allowed set for this intent? Log confusion pairs ("called `search` when it should have called `lookup_order`") to guide prompt fixes.

**Argument validity** — parse tool args against JSON schema. Invalid args that the tool layer rejected count as failures even if the agent recovered.

**Step efficiency** — track median steps per scenario type. Alert when p50 steps increases by >30% after a prompt change.

**Recovery rate** — inject tool failures in eval scenarios. Score whether the agent retries correctly, escalates, or loops.

## Building the eval dataset

Structure scenarios as:

```yaml
- id: refund_eligible_order
  input: "I want a refund for order 4521"
  context: { user_id: "u-123", order_status: "delivered" }
  expected_tools: [lookup_order, create_refund]
  expected_outcome: success
  rubric: "Must confirm refund ID in response"

- id: refund_ineligible_order
  input: "Refund order 9999 please"
  context: { order_status: "processing" }
  expected_tools: [lookup_order]
  expected_outcome: polite_refusal
  rubric: "Must explain order is not yet eligible, not attempt refund"
```

Include adversarial cases: ambiguous order references, prompt injection in user input, tools returning empty results. The scenarios that come from [production failure logs](https://blog.michaelsam94.com/agent-observability-tracing-spans/) are worth more than fifty synthetic happy paths.

## LLM-as-judge: use carefully

For subjective quality ("was the tone appropriate?"), an LLM judge works in nightly evals. Rules:

- **Never in CI gates** — too non-deterministic
- **Provide the rubric explicitly** in the judge prompt
- **Judge trajectories, not just answers** — include tool call summary in judge context
- **Calibrate against human labels** monthly — if judge-human agreement drops below 80%, fix the rubric

## Trending, not snapshotting

Run evals on every prompt/model change and plot trends:

| Metric | Baseline | After change | Verdict |
|--------|----------|--------------|---------|
| Goal completion | 92% | 89% | Investigate |
| Median steps | 6.2 | 8.1 | Regression |
| Tool accuracy | 96% | 97% | OK |
| Cost per success | $0.03 | $0.05 | Watch |

A 3% completion drop might be noise in a 30-scenario set. Across 200 scenarios over two weeks of changes, it's a signal.

Pair offline evals with [deterministic replay tests](https://blog.michaelsam94.com/agent-deterministic-replay-testing/) in CI — replay catches orchestration breaks, eval catches reasoning quality drift.

## Trajectory scoring rubric

Score complete agent trajectories, not just final answers:

```python
def score_trajectory(trajectory: AgentTrajectory, expected: ExpectedOutcome) -> TrajectoryScore:
    return TrajectoryScore(
        goal_completion=trajectory.completed_goal == expected.outcome,
        tool_accuracy=correct_tools(trajectory.tools_called, expected.tools) / len(expected.tools),
        step_efficiency=len(trajectory.steps) / expected.max_steps,
        cost_efficiency=trajectory.total_tokens / expected.token_budget,
        safety=not any(t.name in FORBIDDEN_TOOLS for t in trajectory.tools_called),
    )
```

A trajectory can have correct final answer but wrong tool path — trajectory scoring catches shortcutting and unsafe tool use that answer-only eval misses.

## Building eval datasets from production

Production failures are the highest-value eval cases:

```python
async def sample_production_failures(days: int = 7) -> list[EvalScenario]:
    failures = await trace_store.query(
        filter={"outcome": "failed", "user_feedback": "negative"},
        since=days_ago(days),
        limit=50,
    )
    return [
        EvalScenario(
            input=f.user_message,
            context=f.agent_context,
            expected_outcome=human_label(f),  # human labels correct behavior
            source="production_failure",
            trace_id=f.trace_id,
        )
        for f in failures
    ]
```

Add 5–10 production failure cases to eval set weekly. Synthetic happy-path scenarios don't cover the long tail of real user behavior.

## Multi-dimensional regression detection

Track multiple metrics simultaneously — single metric regression hides compensating failures:

```python
REGRESSION_THRESHOLDS = {
    "goal_completion": -0.03,    # max 3% drop
    "tool_accuracy": -0.02,
    "median_steps": +0.20,        # max 20% increase
    "cost_per_success": +0.15,    # max 15% cost increase
    "safety_violations": +0,      # zero tolerance
}

def detect_regression(baseline: Metrics, current: Metrics) -> list[str]:
    regressions = []
    for metric, threshold in REGRESSION_THRESHOLDS.items():
        delta = (current[metric] - baseline[metric]) / baseline[metric]
        if delta < threshold or (metric == "safety_violations" and current[metric] > 0):
            regressions.append(f"{metric}: {delta:+.1%}")
    return regressions
```

Safety violations block deploy regardless of other metrics. Cost regression warns but doesn't block unless severe.

## Failure modes

- **Eval only final answer** — agent shortcuts tools; answer correct, process wrong
- **Small eval set (<30 scenarios)** — 3% completion drop is noise, not signal
- **LLM judge in CI gates** — non-deterministic; blocks merge on judge variance
- **No production failure cases** — eval set diverges from real user behavior
- **Single metric tracking** — cost improves while quality degrades unnoticed

## Production checklist

- Trajectory scored on goal completion, tool accuracy, step efficiency, cost, safety
- Eval set includes production failure cases (added weekly)
- Minimum 100 scenarios for statistical confidence
- LLM judge in nightly eval only — not CI gates
- Multi-dimensional regression thresholds defined per metric
- Trend dashboard plots all metrics over prompt/model versions

## Resources

- [LangSmith evaluation and datasets](https://docs.smith.langchain.com/evaluation)
- [AgentBench benchmark paper](https://arxiv.org/abs/2308.03688)
- [SWE-bench — coding agent evaluation](https://www.swebench.com/)
- [OpenAI evals best practices](https://platform.openai.com/docs/guides/evals)
- [RAGAS evaluation framework](https://docs.ragas.io/)
