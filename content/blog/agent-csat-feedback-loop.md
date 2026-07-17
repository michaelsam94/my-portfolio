---
title: "AI Agents: Csat Feedback Loop"
slug: "agent-csat-feedback-loop"
description: "Close the CSAT feedback loop for AI agents — thumbs signals, conversation mining, eval dataset curation, prompt drift detection, and routing low scores to human review."
datePublished: "2025-04-27"
dateModified: "2025-04-27"
tags: ["AI", "Agent", "Csat"]
keywords: "CSAT feedback loop, agent satisfaction, thumbs up down, LLM eval dataset, conversation analytics, agent quality monitoring"
faq:
  - q: "What CSAT signal should agent products collect first?"
    a: "Start with post-session thumbs up/down plus optional one-click reason tags (wrong answer, too slow, rude tone). Delay free-text surveys until you process structured signals — unstructured feedback without labels does not close the loop. Always bind feedback to session_id, model_version, and tool_trace."
  - q: "How many CSAT responses before acting on trends?"
    a: "Per-intent baselines need ~200 sessions for ±5% margin at 95% confidence. Global CSAT moves faster — alert on weekly rolling averages with minimum volume gates (e.g. n≥50/week per agent persona). Single thumbs-down is a data point; pattern of downs on refund intent after deploy is actionable."
  - q: "Should negative CSAT automatically retrain the agent?"
    a: "No — route negatives to human review queues first. Auto-add to fine-tuning sets without PII scrubbing and quality review poisons datasets. Automate: export reviewed negatives to eval sets, trigger regression tests, flag prompt versions that correlate with CSAT drops."
  - q: "How do you prevent CSAT bias from happy-path users only?"
    a: "Sample feedback prompts — show to 30–50% of sessions, always show after failed tool calls or escalations. Weight metrics by session outcome. Track non-response rate; silent users often churn instead of clicking thumbs-down."
---
CSAT for the support agent read 4.2 stars in the dashboard. Incidents were flat. Then someone pulled thumbs-down sessions and found forty percent involved refund policy after a prompt deploy three weeks earlier — a change nobody linked to satisfaction because **CSAT was collected but never closed**. Scores aggregated; traces rotted in cold storage; eval sets stayed frozen on launch-week conversations.

Customer Satisfaction (CSAT) feedback loops turn agent telemetry into product velocity: capture structured signals, join them to execution traces, mine patterns, update eval harnesses, and gate releases when satisfaction regresses. Without the loop, CSAT is a vanity chart.

## Signal design at session end

Minimal viable feedback UI:

```
┌─────────────────────────────────────────┐
│  Did this answer help?                  │
│     [👍 Yes]    [👎 No]                 │
│                                         │
│  (if No) What went wrong?               │
│  [ ] Incorrect  [ ] Incomplete          │
│  [ ] Too slow   [ ] Couldn't do task    │
└─────────────────────────────────────────┘
```

Capture server-side:

```typescript
interface CsatEvent {
  sessionId: string;
  tenantId: string;
  rating: "positive" | "negative" | "dismissed";
  reasonTags?: string[];
  freeText?: string;  // optional, moderated
  timestamp: string;
  agentVersion: string;
  modelId: string;
  promptHash: string;
  toolTraceIds: string[];
  latencyMsP95: number;
  escalated: boolean;
  locale: string;
}
```

Never orphan feedback from `sessionId` — without trace join, you cannot answer "which tool call failed?"

## Ingestion pipeline

```
Agent session ends ──► CSAT widget ──► Kafka csat.events
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              Warehouse (dbt)           Real-time alerts            Eval export job
              daily aggregates          CSAT drop > 2σ            reviewed negatives
```

```python
# pipelines/csat_ingest.py
from pydantic import BaseModel

class CsatRecord(BaseModel):
    session_id: str
    rating: str
    reason_tags: list[str]
    agent_version: str
    prompt_hash: str

def enrich_csat(raw: CsatRecord, trace_store) -> dict:
    trace = trace_store.get_session(raw.session_id)
    return {
        **raw.model_dump(),
        "intents": trace.detected_intents,
        "tools_called": [t.name for t in trace.tools],
        "final_outcome": trace.outcome,
        "input_tokens": trace.token_usage.input,
        "output_tokens": trace.token_usage.output,
        "had_hallucination_flag": trace.safety_flags.hallucination,
    }
```

Enrichment runs async — do not block the user's browser on warehouse joins.

## Analytics that drive action

Dashboard slices that matter:

| Dimension | Question |
|-----------|----------|
| `prompt_hash` | Did deploy X hurt CSAT? |
| `intent` | Which workflows fail? |
| `model_id` | Is GPT-4o-mini worse on billing? |
| `tool_name` | Which integration breaks trust? |
| `locale` | Translation regression? |

Rolling CSAT with volume gate:

```sql
-- dbt model: csat_weekly_by_intent
SELECT
  date_trunc('week', submitted_at) AS week,
  intent,
  agent_version,
  COUNT(*) FILTER (WHERE rating = 'positive') AS positives,
  COUNT(*) FILTER (WHERE rating = 'negative') AS negatives,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE rating = 'positive') / NULLIF(COUNT(*), 0), 1) AS csat_pct
FROM csat_enriched
WHERE rating IN ('positive', 'negative')
GROUP BY 1, 2, 3
HAVING COUNT(*) >= 50
```

Alert when `csat_pct` drops more than 8 points week-over-week for any intent with `total >= 50`.

## Human review queue for negatives

Auto-route high-value negatives:

```typescript
function shouldQueueReview(event: CsatEvent, session: Session): boolean {
  if (event.rating !== "negative") return false;
  if (session.estimatedRevenueAtRisk > 1000) return true;
  if (event.reasonTags?.includes("incorrect")) return true;
  if (session.escalated) return false; // already handled
  return Math.random() < 0.1; // sample for quality audit
}
```

Reviewers label root cause: `retrieval_miss`, `tool_error`, `policy_gap`, `tone`, `user_error`. Labels feed eval sets — not raw thumbs alone.

## Eval dataset curation loop

Closed loop steps:

1. Export reviewed negatives with `{input, expected_behavior, actual_output, root_cause}`
2. Dedupe near-identical queries via embedding clustering
3. Add to CI eval harness — regression must pass before prompt promote
4. Track **eval pass rate** alongside CSAT — diverging trends mean eval drift

```python
# eval/export_from_csat.py
def build_eval_case(reviewed_session) -> dict:
    return {
        "id": reviewed_session.session_id,
        "input": reviewed_session.user_messages[-1],
        "context": reviewed_session.retrieved_chunks,
        "expected": reviewed_session.reviewer_gold_answer,
        "tags": reviewed_session.root_cause_labels,
        "source": "csat_negative",
    }
```

Cap CSAT-sourced eval cases at 30% of total — balance with synthetic and SME-authored cases.

## Correlating CSAT with automated metrics

LLM-judge scores on traces should correlate with thumbs — if not, fix judge or CSAT placement:

```python
from scipy.stats import spearmanr

def audit_csat_judge_alignment(rows: list[dict]) -> float:
    csat_binary = [1 if r["rating"] == "positive" else 0 for r in rows]
    judge_scores = [r["llm_judge_helpfulness"] for r in rows]
    rho, _ = spearmanr(csat_binary, judge_scores)
    return rho  # target > 0.35
```

Low correlation — users angry about latency while judge only scores correctness. Expand reason tags and judge rubric together.

## Prompt and model rollback triggers

Feature flag `agent_prompt_v47` ships Monday. CSAT on `billing` intent drops from 82% to 71% by Thursday with n=120.

Automated response:

```yaml
# alerts/csat_regression.yaml
- name: csat_intent_regression
  condition: csat_pct_drop >= 7 AND sample_size >= 50
  window: 72h
  action:
    - notify: "#agent-quality"
    - create_incident: P2
    - suggest_rollback: agent_prompt_hash
```

Human confirms rollback — auto-rollback CSAT triggers need false-positive tuning per tenant seasonality (holiday spikes confuse naive thresholds).

## Privacy and retention

CSAT free-text may contain PII — run moderation API or regex scrub before analyst view. Retention: 90 days raw free-text, 2 years structured aggregates. GDPR erasure must cascade `session_id` from CSAT tables.

Do not use CSAT transcripts for model training without explicit opt-in — enterprise contracts often prohibit it.

## Closing the loop with users

Optional follow-up on negative CSAT: "We updated our answer based on feedback like yours" builds trust when you actually ship fixes. Track **return CSAT** for users who gave thumbs-down previously — recovery metric proves loop closure.

## Anti-patterns

- **CSAT on every message** — survey fatigue; once per resolved session
- **Aggregating without trace join** — pretty charts, no fixes
- **Ignoring dismiss rate** — 70% dismiss means selection bias
- **Using CSAT as sole SLO** — pair with task completion, latency, escalation rate

## Segmenting CSAT by agent persona

Multi-tool agent platforms run distinct personas — billing bot, onboarding guide, code assistant — under one API. Aggregate CSAT hides persona-specific regressions. Tag every session with `persona_id` at routing time:

```typescript
function routeToPersona(intent: string, tenant: Tenant): string {
  if (intent === "billing") return "billing-v3";
  if (intent === "onboarding") return "onboard-v2";
  return tenant.defaultPersona;
}
```

Dashboard CSAT per persona weekly; alert independently. A deploy that improves billing tone but breaks onboarding tool routing shows up clearly instead of averaging to zero delta.

## Weekly quality review ritual

Sustainable loops need a recurring meeting with engineering, product, and support — thirty minutes, standing agenda:

1. Top three negative reason tags by volume vs prior week
2. Two sampled thumbs-down sessions reviewed live with trace replay
3. Eval set additions approved from reviewed sessions
4. Open regressions tied to `prompt_hash` or `model_id` deploys

Without ritual, review queues backlog and CSAT becomes archival data. Assign rotating owner; publish notes to `#agent-quality` for async visibility.

## Instrumenting dismiss and partial feedback

Track `rating: dismissed` separately from no-prompt. High dismiss after long sessions signals survey timing wrong — move prompt before session timeout. Partial submissions (thumb without reason tag) still enrich aggregates; store `reason_tags: []` explicitly rather than dropping the event. Dismissed prompts count toward exposure denominator when computing response rate.

## The takeaway

CSAT feedback loops for agents are plumbing: structured capture, trace enrichment, reviewed exports to eval, regression alerts on prompt deploys, and human labels that explain why thumbs pointed down. Satisfaction scores without closed loops decorate dashboards; joined, reviewed, and tested feedback turns agent quality into an engineering discipline with rollback criteria — not a post-incident surprise.

## Resources

- [Microsoft HAX Toolkit — feedback patterns](https://learn.microsoft.com/en-us/hax-toolkit/ai-guidelines/)
- [OpenAI evals framework](https://github.com/openai/evals)
- [LangSmith feedback and annotation queues](https://docs.smith.langchain.com/)
- [dbt analytics engineering docs](https://docs.getdbt.com/)
- [HELM human feedback evaluation principles](https://crfm.stanford.edu/helm/latest/)
