---
title: "AI Agents: Anomaly Detection Metrics"
slug: "agent-anomaly-detection-metrics"
description: "Choosing and calibrating anomaly metrics for LLM agent fleets — token burn spikes, tool-loop detection, retrieval drift, and alert thresholds that on-call engineers trust."
datePublished: "2025-03-04"
dateModified: "2025-03-04"
tags: ["AI", "Agent", "Anomaly"]
keywords: "anomaly detection metrics, agent observability, token spike alerting, Prometheus anomaly, isolation forest ops, false positive rate, LLM SLO burn"
faq:
  - q: "Which metrics best detect anomalies in agent workloads?"
    a: "Combine rate metrics (tokens/sec, tool calls/min, retrieval queries/sec), distribution metrics (p99 latency per tool, embedding similarity scores), and ratio metrics (refusal rate, error-to-success ratio, cost per completed task). Single-threshold alerts on raw counters fail when traffic grows — use seasonality-aware baselines or quantile-based bands."
  - q: "How do you reduce false positives from anomaly alerts?"
    a: "Group alerts by tenant and agent version, require multi-signal confirmation before paging (e.g., token spike AND error rate rise), use minimum support windows (anomaly sustained 10+ minutes), and maintain suppression rules for known events like marketing launches or batch reindex jobs."
  - q: "What is the difference between point, contextual, and collective anomalies for agents?"
    a: "Point anomalies are single outlier observations (one request with 500k tokens). Contextual anomalies are outliers given context (high token count during a known short prompt). Collective anomalies are subtle shifts across sequences (slow tool-call loop that each step looks normal). Agent failures often manifest as collective anomalies — optimize detectors accordingly."
  - q: "Should anomaly detection use ML models or statistical thresholds?"
    a: "Start with robust statistics (median absolute deviation, EWMA bands, seasonal decomposition) on 5–10 core metrics — they're explainable in postmortems. Add lightweight ML (isolation forest, matrix profile) for multivariate patterns once baselines are stable. Black-box models without feature attribution erode on-call trust quickly."
---
Our pager fired at 3 a.m. because token consumption doubled. On-call rolled back a deploy that had nothing to do with it — marketing had emailed 40,000 users a link to the agent. The anomaly was real; the diagnosis was wrong because we alerted on a global counter without tenant segmentation, seasonality, or a companion signal distinguishing traffic growth from runaway tool loops. Anomaly detection for agent fleets lives or dies on **metric selection** and **threshold semantics**, not on which fancy algorithm you import.

Agents generate time series traditional web SRE playbooks weren't designed for: bursty LLM calls, fat-tailed latency, retrieval fan-out, and feedback loops where one bad tool response triggers ten retries. This piece is about the metrics worth instrumenting and how to calibrate detectors so alerts mean "investigate agent behavior" — not "someone popular clicked a link."

## Instrumentation map for agent pipelines

Before algorithms, enumerate what you measure. A minimal agent observability schema:

| Layer | Metrics | Anomaly question |
|-------|---------|------------------|
| Gateway | requests/sec, auth failures, queue depth | DDoS or credential stuffing? |
| Orchestrator | active sessions, steps/session, loop detections | Runaway multi-turn loops? |
| LLM | tokens in/out, time-to-first-token, model routing mix | Cost attack or wrong model route? |
| Retrieval | queries/sec, chunks/request, cache hit rate | Retrieval storm or index corruption? |
| Tools | calls/tool, error rate/tool, p99 latency/tool | Broken integration or abuse? |
| Outcomes | task completion rate, human handoff rate | Silent quality collapse? |

Emit labels consistently: `tenant_id`, `agent_version`, `model`, `tool_name`. Anomalies without labels are noise.

```python
# instrumentation/agent_metrics.py
from prometheus_client import Counter, Histogram, Gauge

TOKENS = Counter(
    "agent_llm_tokens_total",
    "Tokens consumed",
    ["tenant_id", "agent_version", "direction"],  # direction=in|out
)
TOOL_CALLS = Counter(
    "agent_tool_calls_total",
    "Tool invocations",
    ["tenant_id", "tool_name", "status"],
)
SESSION_STEPS = Histogram(
    "agent_session_steps",
    "Orchestration steps per completed session",
    ["tenant_id", "agent_version"],
    buckets=[1, 2, 5, 10, 20, 50, 100],
)
ACTIVE_LOOPS = Gauge(
    "agent_detected_loops",
    "Sessions flagged for repeated identical tool pattern",
    ["tenant_id"],
)
```

## Point anomalies: spikes you can explain

Point anomalies are single observations far from typical — a request with 200k input tokens, a tool call returning 50MB JSON. They're the easiest to detect and the easiest to misinterpret.

Use **per-request caps** as hard limits (fail closed) and **statistical detectors** for softer warnings. Robust z-scores via median absolute deviation (MAD) resist LLM latency outliers better than mean/std:

```python
import numpy as np

def mad_zscore(series: np.ndarray, value: float) -> float:
    med = np.median(series)
    mad = np.median(np.abs(series - med)) or 1e-9
    return 0.6745 * (value - med) / mad

# Alert if mad_zscore(last_7d_hourly_tokens, current_hour_tokens) > 6
```

For token spikes, always pair with **request count**. Tokens/sec up 3× because requests/sec up 3× is capacity planning, not an incident. Tokens/sec up 3× at flat request count suggests prompt injection, retrieval bloat, or a model routing bug.

## Contextual anomalies: same number, different meaning

Contextual anomalies violate expectations **given circumstances**. Completion tokens spike during "summarize this 80-page PDF" sessions — normal. The same spike on "what's the weather?" is not.

Encode context as detector dimensions:

- **Intent class or route** (support vs coding vs retrieval-heavy)
- **Input size bucket** (chars or pages ingested)
- **User tier** (free vs enterprise quotas)

Train separate baselines per `(tenant_id, route)` tuple. Cold-start tenants use global priors with wide bands until support ≥ 1000 sessions.

Seasonality matters. B2B agents peak weekday mornings; consumer agents peak evenings. Use STL decomposition or Prophet-style seasonal bands on hourly aggregates before declaring anomaly.

## Collective anomalies: where agents actually fail

The painful incidents are collective: each tool call looks fine, but the session executes `search → read → search → read` twenty times, burning tokens and never completing. Matrix profile algorithms and sequence-based rules catch these:

```python
def detect_tool_stutter(calls: list[str], window: int = 6) -> bool:
    """True if same tool pattern repeats without progress."""
    if len(calls) < window:
        return False
    recent = calls[-window:]
    unique_tools = set(recent)
    if len(unique_tools) <= 2 and recent.count(recent[0]) >= window // 2:
        return True  # e.g., search,read,search,read,search,read
    return False
```

Track **steps-to-completion** distributions per agent version. A deploy that raises p50 steps from 4 to 9 is a quality regression — collective drift — even if no single step errors.

Similarly, watch **refusal rate** and **human escalation rate** in tandem. Refusals drop while escalations rise might indicate guardrail bypass, not improvement.

## Multivariate detection without black boxes

Univariate alerts multiply; multivariate detectors find correlated shifts. Isolation forests on standardized feature vectors work when you limit features to those on-call can interpret:

```python
from sklearn.ensemble import IsolationForest

features = ["tokens_out_p95", "tool_error_rate", "retrieval_chunks_p95", "ttft_p95"]
X = hourly_rollups[features].values
clf = IsolationForest(contamination=0.02, random_state=42)
scores = clf.fit_predict(X[-168:])  # last week hourly
# -1 = anomaly hour; log feature values alongside score for explainability
```

Never page on `-1` alone. Require at least one business-critical feature beyond bounds documented in the runbook.

## Threshold design on-call engineers accept

Alert fatigue kills agent platforms slowly. Rules that survived review with three teams:

1. **Page on symptom, ticket on cause.** Page when task completion rate drops AND error rate rises; ticket when isolation forest score is weird but users unaffected.

2. **Sustained breach.** Anomaly must persist 10–15 minutes to ignore flaky bursts from cold starts.

3. **Minimum volume.** Don't z-score hours with &lt; 50 sessions — variance is meaningless.

4. **Known-event suppressions.** Maintenance windows, index rebuilds, and launch calendars suppress predictable spikes.

5. **Burn-rate alerts for SLOs.** Anomaly on error budget consumption (multi-window) beats static thresholds for latency.

Document every alert with: **what it detects**, **what it doesn't**, **first actions**, **known false positives**. If you can't write that, delete the alert.

## Feedback loops from incidents

After every anomaly-driven incident or false page, record:

- Which metric fired first
- Root cause category (traffic, bug, attack, misconfiguration)
- Whether companion metrics would have clarified faster

Retune thresholds monthly from this log. Agents change behavior with every prompt and tool update — static thresholds rot faster than microservice CPU alerts.

Synthetic probes help: scheduled canonical tasks ("health check agent" runs a fixed prompt/tool chain every 5 minutes). Anomaly on probe latency or token count signals platform regression independent of user traffic skew.

Cost anomalies deserve equal billing with reliability anomalies. Track **cost per successful task** and **tokens per completed outcome** alongside latency. A deploy that doubles retrieval chunk count may leave error rates untouched while silently doubling inference spend — finance notices before SRE if you instrument spend as a first-class anomaly signal.

Version your agent releases in metric labels. When `agent_version` shifts, expect baseline drift for 24–48 hours; temporarily widen bands or suppress version-comparison alerts until the new version accumulates enough samples. Otherwise every prompt change pages on-call for benign behavioral shifts.

Anomaly detection for agents is not one algorithm — it's a layered strategy. Instrument rate, distribution, and ratio metrics with rich labels; treat point, contextual, and collective patterns differently; pair statistical bands with business SLO burn; and optimize for postmortem explainability over model sophistication. The goal is fewer 3 a.m. rollbacks for marketing emails, and faster detection of the tool loop that actually burns your budget.

## Resources

- [Google SRE Workbook — Monitoring distributed systems](https://sre.google/workbook/monitoring/)
- [Prometheus documentation — histograms and alerting](https://prometheus.io/docs/practices/histograms/)
- [Robust statistics for anomaly detection (NIST Engineering Stats Handbook)](https://www.itl.nist.gov/div898/handbook/)
- [Matrix Profile for time series motifs and discords](https://matrixprofile.org/)
- [OpenTelemetry semantic conventions for generative AI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
