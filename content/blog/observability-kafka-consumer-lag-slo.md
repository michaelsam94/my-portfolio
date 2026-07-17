---
title: "Kafka Consumer Lag SLOs"
slug: "observability-kafka-consumer-lag-slo"
description: "Define SLOs on Kafka consumer lag so processing delays become user-visible symptoms with burn-rate alerts."
datePublished: "2026-01-20"
dateModified: "2026-07-17"
tags:
  - "DevOps"
  - "Observability"
  - "Kafka"
  - "SRE"
keywords: "kafka consumer lag slo, consumer lag alerting, kafka lag metrics, processing delay slo, kafka observability"
faq:
  - q: "What is consumer lag in SLO terms?"
    a: "Lag is offset difference between log end and committed offset—staleness users feel in search or analytics freshness."
  - q: "Should I alert on absolute lag or growth rate?"
    a: "Both. Absolute lag pages when backlog hurts users; growth rate pages when falling behind faster than catching up."
  - q: "How does partition count affect lag metrics?"
    a: "Alert on max partition lag—hot partitions hide in sums."
---

Search stopped updating while Kafka brokers looked green—`order-indexer` lag 847k growing 2k/sec. Without consumer lag SLO, event-driven systems look fine until data staleness becomes support tickets.

## Metrics

`kafka_consumer_group_lag`, lag derivative, max partition lag, end-to-end processing latency histogram.

## Alerting

Symptom: processing too slow for users—lag seconds > SLO threshold. Early warning: positive `deriv(lag)`.

## Root causes

Step jump after deploy, gradual climb from traffic growth, hot partition key skew, broker IO issues.

## Operations

Max consumer parallelism = partition count. Document offset reset approval process. KEDA scale on lag with cooldown.


## Lag vs processing time SLO

Offset lag conflates publish rate with consume rate. Prefer **end-to-end latency** histogram: `event_processed_timestamp - event_published_timestamp`. Kafka lag becomes secondary alert when processing latency SLO already fires.

## Compact topics and lag interpretation

Compacted topics delete old offsets—lag metrics behave differently. Document which consumer groups use compacted topics; Burrow config excludes them from false ERR status.

## Autoscaling on lag

KEDA ScaledObject on `kafka lag`:

```yaml
triggers:
  - type: kafka
    metadata:
      consumerGroup: order-indexer
      lagThreshold: "1000"
      activationLagThreshold: "100"
```

Scale-down cooldown prevents flapping when lag hovers near threshold. Max replicas capped at partition count.

## Exactly-once and lag semantics

Transactions and idempotent consumers may commit offset after side effect—lag drops only after slow processing completes. Document expected lag during large replay after consumer downtime; avoid false pages during intentional catch-up with raised threshold window.

## MirrorMaker lag

Cross-cluster replication adds second lag dimension—alert on MM2 lag separately from consumer group lag. Users see stale data if MM2 falls behind even when downstream consumer is current on secondary cluster.

## Business stakeholder alignment

Product managers understand "search results 15 minutes stale" better than "lag 900000"—dashboards should show lag converted to freshness SLA with color thresholds agreed in quarterly planning. Engineering owns measurement; product owns acceptable staleness numbers.

During Kafka cluster upgrades, temporarily widen lag alert thresholds with change ticket reference—controlled lag spike during partition reassignment should not page if processing latency SLO still green.


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
