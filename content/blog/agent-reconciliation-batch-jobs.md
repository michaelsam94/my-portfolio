---
title: "AI Agents: Reconciliation Batch Jobs"
slug: "agent-reconciliation-batch-jobs"
description: "Batch reconciliation jobs that compare agent usage meters, provider invoices, and ledger entries—catching drift before finance closes the books or customers dispute charges."
datePublished: "2025-09-11"
dateModified: "2025-09-11"
tags: ["AI", "Agent", "Reconciliation"]
keywords: "agent billing reconciliation, usage metering batch jobs, LLM cost reconciliation, idempotent ETL, financial close, drift detection"
faq:
  - q: "How often should agent usage reconciliation jobs run?"
    a: "Run incremental reconciliation hourly for operational visibility and a full windowed reconcile nightly aligned to your billing period boundaries. Hourly jobs catch provider API outages or metering pipeline stalls within the same business day; nightly jobs produce the authoritative numbers finance exports."
  - q: "What tolerance threshold is reasonable for token count mismatches?"
    a: "Treat anything above 0.5% of billed tokens as investigate, and above 2% as page. Sub-threshold drift often comes from rounding, timezone boundaries, or requests still in-flight at window close—log it but do not auto-adjust invoices without human review."
  - q: "Should reconciliation jobs mutate production billing tables directly?"
    a: "No. Write findings to a staging reconciliation table with proposed adjustments, then apply corrections through an audited approval workflow. Direct mutation makes rollback impossible when a job bug misclassifies thousands of tenant rows."
  - q: "How do you reconcile agent tool calls that span multiple providers?"
    a: "Normalize every event to a canonical schema with provider, model, request_id, tenant_id, token_in, token_out, and cost_usd_micros before comparison. Join on request_id where providers echo it; fall back to fuzzy matching on timestamp ±5s plus tenant plus model only when IDs are missing."
---
Finance opened a ticket because three enterprise tenants showed agent spend 18% above what our internal meter reported. The agent platform team insisted metering was fine; the data team pointed at stale warehouse loads. The actual bug lived in a reconciliation gap: nightly batch jobs compared invoice CSVs to a summary table, but nobody reconciled **per-request** agent events against provider usage APIs. When a retry duplicated tool calls without idempotency keys, both sides counted differently and drift accumulated silently for six weeks.

Reconciliation batch jobs for agent platforms are not glamorous ETL. They are the control plane that proves your unit economics are real before you scale traffic or renegotiate provider contracts.

## Three ledgers that never agree on their own

Every agent deployment eventually maintains three partial truths:

| Ledger | What it captures | Typical failure |
|--------|------------------|-----------------|
| **Runtime meter** | Tokens, tool invocations, latency tiers at request time | Lost events on crash, double-count on retry |
| **Provider bill** | OpenAI, Anthropic, Bedrock usage exports | Delayed files, different aggregation grain |
| **Internal ledger** | Credits consumed, plan limits, revenue recognition | Rounding, FX, promotional credits |

Reconciliation does not pick a winner—it surfaces **explainable deltas**. A healthy system produces a daily report where 95% of rows match exactly, 4% match within tolerance after documented transforms, and 1% land in a human queue with enough context to resolve in under ten minutes.

## Windowing: close the books without racing the pipeline

Agent traffic is continuous; finance thinks in **closed intervals**. Define reconciliation windows with explicit watermarks:

```python
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

@dataclass(frozen=True)
class ReconcileWindow:
    start: datetime
    end: datetime
    watermark_delay: timedelta  # allow in-flight events to land

    @classmethod
    def for_billing_day(cls, day: datetime, delay_minutes: int = 45):
        start = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return cls(start, end, timedelta(minutes=delay_minutes))

    def effective_end(self) -> datetime:
        return self.end - self.watermark_delay
```

The watermark delay matters because agent orchestrators flush usage asynchronously. Closing a window at 00:00 UTC while events arrive until 00:38 produces false drift. Document the delay in your finance runbook so auditors understand why March 1 numbers revised on March 2.

## Job skeleton: extract, normalize, diff, persist

Structure jobs as idempotent stages keyed by `(window_start, window_end, job_version)`:

```python
import hashlib
import json

def job_idempotency_key(window: ReconcileWindow, stage: str) -> str:
    payload = f"{window.start.isoformat()}|{window.end.isoformat()}|{stage}|v3"
    return hashlib.sha256(payload.encode()).hexdigest()

async def run_reconciliation(window: ReconcileWindow, db, object_store):
    key = job_idempotency_key(window, "full")
    if await db.job_completed(key):
        return await db.load_job_result(key)

    runtime_rows = await extract_runtime_meter(db, window)
    provider_rows = await extract_provider_usage(object_store, window)
    ledger_rows = await extract_internal_ledger(db, window)

    normalized = normalize_all(runtime_rows, provider_rows, ledger_rows)
    diffs = compute_diffs(normalized, tolerance_pct=0.005)

    await db.persist_reconciliation_result(key, diffs, status=classify(diffs))
    return diffs
```

**Extract** from source-of-truth APIs, not cached dashboards. **Normalize** to micro-dollars and integer token counts—floats hide reconciliation bugs. **Diff** with tolerances per dimension (tokens vs dollars vs request counts). **Persist** immutable results so re-runs compare apples to apples.

## Break taxonomy: not every delta is a bug

Train on-call engineers to classify breaks before escalating:

1. **Timing** — event recorded in window N, provider attributed to N+1. Fix: shift boundary or increase watermark.
2. **Retry duplication** — same `request_id` ingested twice in runtime meter. Fix: idempotency at ingest.
3. **Model mapping** — `gpt-4o-mini-2024-07-18` vs `gpt-4o-mini` price table mismatch. Fix: mapping table versioned alongside provider SKUs.
4. **Credit overlays** — promotional credits applied in ledger but absent from provider export. Fix: document as expected delta, exclude from alert threshold.
5. **True leakage** — meter under-counts streaming token chunks. Fix: engineering incident.

Store break type on each diff row. Monthly reviews of break distribution tell you whether to invest in pipeline reliability or finance tooling.

## Idempotency and exactly-once illusion

Batch jobs restart. Spot instances die mid-partition. Airflow retries on transient S3 errors. Every write path needs:

```sql
CREATE TABLE reconciliation_runs (
  idempotency_key   text PRIMARY KEY,
  window_start      timestamptz NOT NULL,
  window_end        timestamptz NOT NULL,
  status            text NOT NULL CHECK (status IN ('running','success','failed')),
  diff_count        int,
  result_uri        text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  finished_at       timestamptz
);

CREATE TABLE reconciliation_diffs (
  run_id            text NOT NULL REFERENCES reconciliation_runs(idempotency_key),
  tenant_id         text NOT NULL,
  dimension         text NOT NULL,
  runtime_value     bigint NOT NULL,
  provider_value    bigint NOT NULL,
  delta             bigint NOT NULL,
  break_type        text,
  PRIMARY KEY (run_id, tenant_id, dimension)
);
```

Partition large diff tables by `run_id` or month. Finance queries last successful run; engineering replays historical windows after fixing mapping bugs.

## Alerting that finance trusts

Page on **symptoms**, not raw diff counts:

- Any tenant with `|delta_tokens| / provider_tokens > 0.02` for two consecutive nightly runs
- Reconciliation job `failed` or `running` past SLA (e.g., 06:00 UTC)
- Runtime meter event lag > 30 minutes behind wall clock during business hours

Ticket on **causes**: mapping table stale, provider file missing, warehouse load delayed.

Avoid alerting on known credit overlays—maintain an exclusion list keyed by tenant and reason code.

## Testing before month-end surprises

**Golden fixtures**: synthetic tenant with 1,000 agent requests, known token counts, injected retry duplicate, and one deliberate model mapping error. Assert diff output matches expected break types.

**Property tests**: shuffle event order, rerun job, identical diff hash.

**Chaos**: drop 5% of runtime events in staging, verify job flags coverage gap separately from dollar drift.

Replay production traffic sanitized into staging weekly; compare diff trends against production runs to catch schema drift early.

## Handoff to finance and customer support

Export reconciled numbers as CSV with columns support can grep: `tenant_id`, `billing_period`, `runtime_tokens`, `provider_tokens`, `delta`, `break_type`, `resolution_status`. When a customer disputes an invoice, support pulls the diff row—not a Grafana screenshot.

Document who owns resolution: platform for break types 2 and 5, finance ops for 4, data platform for 1 and 3. Ambiguous ownership is why reconciliation rot sets in.

## Backfill after fixing a metering bug

When engineering discovers a systemic under-count, finance will ask for retroactive correction. Treat backfill as a **separate job lineage** from nightly reconcile—never overwrite historical diff rows. Clone the affected window with `job_version+1`, re-extract runtime events from raw append-only logs (not the summary table you are fixing), and attach a `correction_id` foreign key to adjusted ledger entries.

Run backfill in tenant shards of 500 to avoid locking invoice tables. Emit a reconciliation coverage report: `% of provider request_ids matched to runtime events`. If coverage is 99.2% before the fix and 99.8% after, the remaining gap is expected noise—not a reason to delay publishing corrected numbers.

Communicate revision policy upfront: tenants receive amended usage CSV only when delta exceeds both absolute ($50) and relative (1%) thresholds. Smaller deltas accumulate into the next billing cycle adjustment note. Without policy, support drowns in "why did my dashboard change?" tickets.

## Streaming agents and partial token accounting

Streaming completions emit token counts incrementally; some providers finalize usage only on `finish_reason=stop`. Reconciliation jobs must exclude in-flight streams at window close using the same watermark that warehouse ETL uses—otherwise nightly diffs show false under-count on the runtime side every day at midnight UTC.

Persist `stream_finalized_at` on each usage event. Jobs skip rows where that column is null and emit a `pending_stream_count` metric. When pending count exceeds 0.1% of daily volume, page the ingestion pipeline owner, not finance.

## Resources

- [Stripe — Idempotent requests](https://stripe.com/docs/api/idempotent_requests) — patterns for safe retries that agent billing pipelines should mirror
- [Apache Airflow — Best practices](https://airflow.apache.org/docs/apache-airflow/stable/best-practices.html) — scheduling, idempotency, and backfill semantics for nightly reconciliation DAGs
- [OpenAI — Usage API](https://platform.openai.com/docs/api-reference/usage) — provider-side usage extraction for cross-checking internal meters
- [dbt — Incremental models](https://docs.getdbt.com/docs/build/incremental-models) — warehouse-side staging layers that feed reconciliation extracts
- [Google SRE — Monitoring distributed systems](https://sre.google/sre-book/monitoring-distributed-systems/) — alerting on user-visible billing correctness, not batch completion alone
