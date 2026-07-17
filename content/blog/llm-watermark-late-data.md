---
title: "Event-Time Watermarks for Late Agent Telemetry"
slug: "llm-watermark-late-data"
description: "Handle late-arriving agent usage and trace events in stream processors: watermark generation, allowed lateness, side outputs, and reconciling billing windows with incomplete watermarks for teams running LLM features in production."
datePublished: "2025-05-21"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "watermark late data agent, event time stream processing, allowed lateness billing, Flink watermark agent telemetry"
faq:
  - q: "Why do agent telemetry events arrive late?"
    a: "Mobile clients buffer offline runs, edge gateways batch uploads, cross-region replication lag, and retried tool webhooks all delay event-time timestamps vs processing-time arrival. Billing and SLO dashboards keyed on event time need watermark discipline."
  - q: "What allowed lateness fits agent usage billing?"
    a: "24–72 hours for token metering reconciliation is common — mobile offline plus retry windows. Real-time dashboards use shorter lateness (5–15 min) with correction streams for billing-grade totals."
  - q: "Side output or update existing window on late data?"
    a: "Billing aggregates: emit side output to correction topic, apply delta adjustments with idempotency keys. Don't mutate closed Stripe submission windows silently — finance needs audit trail."
  - q: "Processing time vs event time for agent SLOs?"
    a: "SLO user-facing latency uses processing time alerts. Tenant invoice totals and 'usage this month' UI use event time with watermarks — label UI 'subject to reconciliation' until watermark passes period close."
---
Agent run `run_abc` completed at 23:58 UTC on the last day of the billing cycle — but the usage event lands in Kafka at 00:04 because the mobile client was offline. Without **event-time watermarks**, your Flink job attributes those tokens to next month, finance misses quota true-ups, and the customer disputes an invoice that looks correct from the processor's clock but wrong from contract event time. Late data is normal in agent telemetry; watermarks make lateness explicit.

## Event time vs processing time

| Clock | Meaning | Agent example |
|-------|---------|---------------|
| Event time | When run actually completed | `occurred_at` in usage JSON |
| Processing time | When stream processor sees it | Kafka consumer timestamp |
| Ingestion time | When gateway accepted event | API `received_at` |

Billing contracts usually follow **event time** in tenant timezone or UTC — document which in MSA.

## Watermark intuition

Watermark `W` at time `T` means: "we believe no events with event_time < T - allowed_lateness will arrive."

```
event timeline ─────────────────────────────────────►

events:     ●  ●    ● ●     ● (late!)
            │  │    │ │     │
watermark:  ───W1──────W2──────W3──►

When W passes window [Apr 1 00:00, Apr 1 01:00), close window
Late event after close → side output
```

## Flink implementation sketch

```java
DataStream<UsageEvent> events = env
    .fromSource(kafkaSource, WatermarkStrategy
        .<UsageEvent>forBoundedOutOfOrderness(Duration.ofHours(24))
        .withTimestampAssigner((e, ts) -> e.getOccurredAt().toEpochMilli()),
        "usage-source");

events
    .keyBy(e -> e.getTenantId())
    .window(TumblingEventTimeWindows.of(Time.hours(1)))
    .allowedLateness(Time.hours(24))
    .sideOutputLateData(LATE_TAG)
    .aggregate(new TokenSumAggregator())
    .addSink(billingSink);

DataStream<UsageEvent> late = events.getSideOutput(LATE_TAG);
late.addSink(correctionSink);
```

`allowedLateness(24h)` keeps windows updatable; after lateness expires, truly late events only go to side output.

## Idempotent correction stream

Late events must not double-count:

```python
def apply_correction(event: UsageEvent):
    key = f"corr:{event.idempotency_key}"
    if ledger.exists(key):
        return
    period = billing_period(event.occurred_at, event.tenant_tz)
    if period.is_closed():
        stripe.adjustment.create(
            customer=event.tenant_id,
            quantity=event.quantity,
            description=f"Late event {event.event_id} for {period}",
        )
    else:
        ledger.add_to_open_period(event)
    ledger.mark(key)
```

Closed period → Stripe credit/charge adjustment with ticket link.

## Watermark generation strategies

| Strategy | Use when | Risk |
|----------|----------|------|
| Bounded out-of-orderness (fixed delay) | Stable max lag known (24h) | Over-waits if lag spikes |
| Custom per-source watermark | Mobile vs datacenter sources differ | Complex ops |
| Idleness detection | Sparse tenants | Premature close — tune idle timeout |

Per-tenant idleness: if no events for 7 days, don't advance global watermark on that key alone in global windows — use session windows or `KeyedProcessFunction`.

## Agent telemetry sources and typical lag

| Source | p99 lag | Notes |
|--------|---------|-------|
| Gateway sync | <5s | Baseline |
| Mobile offline queue | 1–48h | Airplane mode completions |
| Tool webhook retry | 1–6h | Exponential backoff |
| Cross-region replicate | 30s–5m | Config dependent |

Set `maxOutOfOrderness` to p99.9 observed lag from metrics, not mean.

## Reconciling billing UI

Show two numbers during month-end close:

```typescript
interface UsageSummary {
  provisionalTokens: number;  // watermark not passed period end
  finalizedTokens: number;    // after watermark + lateness
  reconciliationPending: boolean;
}
```

Customer portal copy: "Usage finalized 72h after month end."

## Monitoring

- `watermark_lag_ms` = processing_time - watermark
- `late_events_rate` by source
- `correction_amount_sum` by tenant (spike → upstream bug)
- `window_close_delay` histogram

Alert if watermark lag exceeds 2× configured bound — job stuck or clock skew.

## Comparison to batch reconciliation

Nightly batch job re-scans raw lake still required as **audit backstop**:

```sql
SELECT tenant_id, date_trunc('hour', occurred_at) AS hr, sum(quantity)
FROM raw_usage_events
GROUP BY 1, 2
EXCEPT
SELECT tenant_id, hr, total FROM stream_aggregates;
```

Stream watermarks optimize real-time; batch diff catches processor bugs.

## Resources

- [Apache Flink — Event Time and Watermarks](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/time/)
- [Google Dataflow — Stream processing with windows](https://cloud.google.com/dataflow/docs/concepts/streaming-pipelines)
- [Vijay Gabbar — Stream Processing with Apache Flink (book)](https://www.oreilly.com/library/view/stream-processing-with/9781491974028/)
- [Kafka — event-time semantics in Kafka Streams](https://docs.confluent.io/platform/current/streams/concepts.html)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.
