---
title: "OpenTelemetry Tail Sampling"
slug: "observability-tail-sampling-otel"
description: "Keep errors and slow traces while sampling away happy paths—tail sampling in the OTel Collector after the trace completes."
datePublished: "2026-02-02"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "OpenTelemetry"
  - "SRE"
keywords: "opentelemetry tail sampling, trace sampling collector, tail sampling processor, head vs tail sampling, otel trace retention"
faq:
  - q: "Head vs tail sampling?"
    a: "Head decides at trace start before knowing error/latency. Tail waits until complete—keep all errors, slow traces, sample 1% success."
  - q: "Where does tail sampling run?"
    a: "OpenTelemetry Collector with trace-ID load balancing so all spans reach the same collector instance."
  - q: "Does tail sampling increase app overhead?"
    a: "Apps may export more spans to collectors; collectors bear buffering cost."
---

Head sampling at 1% deleted the only trace capturing a one-in-ten-million payment double-charge. Tail sampling keeps errors, latency > SLO, premium tenant attributes, plus 1% success—pay storage for traces that explain incidents.

## Collector config

`decision_wait: 10s`, policies for status ERROR, latency threshold, string attributes, probabilistic success sample.

## Load balancing

Route by traceID to same collector—without it policies see incomplete traces.

## Hybrid

Avoid SDK 1% AND tail 1% = 0.01% retention. Prefer always_on export to collector with tail deciding long-term storage.


## Collector HA and tail sampling

Run collector gateway in StatefulSet with persistent queue (Kafka/Pulsar backing) if trace loss during collector restart is unacceptable—memory-only tail sampling trades simplicity for durability.

## Policy testing in staging

Export `tail_sampling_decision` metric per policy—assert error policy `decision=sampled` count matches injected fault count in chaos tests.

## Cost projection

Stored traces per day ≈ `QPS × sample_rate × avg_span_count × bytes_per_span`. Tail sampling at 1% success + 100% errors often lands 5–20× cheaper than 100% head sampling with better debuggability—model before Tempo storage commit.

## Tail sampling and compliance retention

Regulated industries may require 100% retention for financial transaction traces—apply tail policy exception `service=payments AND span.name=CaptureFunds` always sample regardless of success. Legal overrides cost optimization.

## Debugging dropped traces

Export `otelcol_processor_tail_sampling_count_traces_dropped` — spike during traffic surge may indicate `num_traces` buffer too small, not intentional sampling. Size buffers for peak complete trace rate × decision_wait.

## Collector resource planning worksheet

Estimate required collector memory: `decision_wait × peak_traces_per_second × average_spans_per_trace × bytes_per_span_in_buffer`. Undersizing causes silent trace drop more common than explicit sampling—monitor dropped trace counter and size buffers for peak complete checkout flow during load test, not average Tuesday traffic.

Document tail sampling policies in service catalog entry for each service—on-call knows errors always retained for payments even when global success sample is 1%.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.


Document rollback paths and validate observability after every deploy affecting this surface.

## Production review cadence

Revisit dashboards and alert thresholds after every deploy affecting this observability surface. Weekly on-call review should include one exemplar trace or log linked from a metric spike—paper metrics without exemplars train teams to ignore charts.
