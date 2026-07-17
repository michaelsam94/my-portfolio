---
title: "Backpressure and Flow Control in Streaming Pipelines"
slug: "rag-backpressure-flow-control"
description: "Reactive streams, credit-based flow control, and queue bounds that prevent OOM during traffic spikes."
datePublished: "2025-06-30"
dateModified: "2026-07-17"
tags:
  - "Streaming"
  - "Architecture"
  - "Performance"
keywords: "backpressure, flow control, reactive streams, queue bounds"
faq:
  - q: "What is backpressure in software systems?"
    a: "Downstream signals upstream to slow production when consumers cannot keep pace — preventing unbounded queues from exhausting memory."
  - q: "When is dropping messages acceptable?"
    a: "For metrics and logs at overload — sample or drop oldest with counters exposed; never silently drop payment or audit events without explicit policy."
  - q: "How does backpressure differ from throttling?"
    a: "Backpressure is cooperative within pipeline — consumers pull; throttling is often external rate limit rejecting entrants before enqueue."
---
Unbounded queues feel like decoupling until a traffic spike fills heap and kills the JVM. Backpressure propagates consumer capacity upstream — slowing producers, blocking writes, or shedding load — so the system degrades gracefully instead of dying suddenly. Whether using Kafka consumer pause, Reactive Streams demand, or explicit queue depth metrics, the design choice is where to block and what to measure.

## Signs you lack backpressure

Rising GC times, LinkedBlockingQueue size growth, consumer lag unbounded while producers max CPU — classic slow consumer fast producer.

Graph queue depth alongside thread pool active count — blocking on CallerRunsPolicy shows up as request latency before queue length metric crosses alert threshold.

## Reactive Streams demand signal

Publisher respects request(n) from subscriber — implement via Project Reactor, Akka Streams, or manual credit counters in custom pipelines.

## Kafka consumer flow control

pause partitions when downstream DB saturated; resume when backlog drains. Max poll records tuned to processing time.

## Bounded queues and rejection policy

ArrayBlockingQueue with CallerRunsPolicy pushes back to producer thread — natural slowdown. Document blocking risk on request threads vs async handoff.

## End-to-end pressure budgets

Each stage exposes depth metric; alert when product of stage depths indicates pipeline filling holistically.

## Load test with slow consumer

Deliberately throttle sink in staging; verify producers stall measurably without OOM — not just log warnings.

## Backpressure in HTTP APIs

Return 503 with Retry-After when internal queue depth exceeds threshold — better than accepting and timing out at 30s. Document client backoff expectations in API guidelines; mobile apps with aggressive retry loops amplify outages without jitter.

## GraphQL and fan-out backpressure

Single GraphQL query fan-out to dozens services — limit query depth cost and cancel downstream on timeout. Without per-field cost analysis, one expensive resolver blocks whole response buffer.

## Thread pool versus event loop models

Blocking JDBC in virtual thread platform still exhausts connection pool — backpressure at pool wait queue depth not thread count alone.

Backpressure is kindness to your heap — bound queues, signal demand, pause consumption, and test with artificially slow sinks. Unlimited buffers are delayed outages.

Game day: artificially slow sink dependency and verify upstream latency grows gracefully without OOM — backpressure should bend latency curve not cliff crash.

Design review checklist item 1 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for backpressure and flow control: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in backpressure and flow control often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for backpressure and flow control should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for backpressure and flow control documents escalation when primary and secondary on-call roles are unreachable.

## Integration notes for backpressure flow control

This rarely lives alone. Map upstream dependencies (auth, data stores, queues) and downstream consumers before you harden the happy path. Sequence the rollout: observability first, then flags, then the risky behavior change. That order turns rollback into a flag flip instead of a reverse migration under pressure. Keep the integration diagram in the same repo as the code so it cannot rot in a slide deck.
