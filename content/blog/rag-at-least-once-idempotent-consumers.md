---
title: "At-Least-Once Delivery with Idempotent Consumers"
slug: "rag-at-least-once-idempotent-consumers"
description: "Kafka and queue consumers that survive duplicates — idempotency keys, dedup stores, and exactly-once illusion patterns."
datePublished: "2025-07-25"
dateModified: "2026-07-17"
tags:
  - "Kafka"
  - "Distributed Systems"
  - "Backend"
keywords: "at-least-once, idempotent consumers, kafka, deduplication"
faq:
  - q: "Why not aim for exactly-once everywhere?"
    a: "True exactly-once across heterogeneous systems is rare and expensive — idempotent at-least-once is simpler and sufficient when dedup is enforced at business operation layer."
  - q: "Where should idempotency keys live?"
    a: "In a durable store with TTL exceeding max redelivery window — database unique constraint or Redis SET NX with compaction job."
  - q: "What happens on poison messages?"
    a: "After N failures, move to DLQ with original offset preserved — replay only after fix with same idempotency keys preventing double apply."
---
Message brokers guarantee at-least-once in realistic deployments — networks retry, consumers crash after process but before commit. Idempotent consumers make duplicate delivery harmless by recording processed keys or relying on natural uniqueness constraints. Teams that skip this ship double charges, duplicate emails, and inconsistent ledger entries that reconcile only at month-end.

## Delivery semantics recap

At-most-once loses messages; at-least-once duplicates; exactly-once needs transactional outbox or broker transactions plus idempotent sinks. Pick semantics deliberately per topic criticality.

Size idempotency store TTL to max consumer lag plus max replay window documented in runbook — shorter TTL reintroduces duplicate side effects after broker maintenance.

## Idempotency key design

Use business key — payment_id, order_id, event_id — not offset alone. Keys must be stable across republish. Include producer version when schema changes affect side effects.

## Dedup store patterns

Postgres unique on idempotency_key with outcome JSON for safe reply replay. Redis for hot path with async write-through to DB. TTL must exceed consumer lag worst case.

## Consumer offset commit ordering

Process then commit offset only after dedup record durable — crash between causes redelivery handled by idempotency. Never commit before side effects complete.

## Bulk consume and partial batch failure

Kafka batch processing: mark individual messages processed; do not fail whole batch if one duplicate — selective commit strategies per framework.

## Testing duplicate delivery

Chaos inject redelivery in staging; property tests that f(f(x)) equals f(x) for handler f. Load test dedup store write contention.

## Reconciliation jobs for drift detection

Nightly compare sum of processed business events with source system totals — idempotency prevents duplicates but bugs can skip processing entirely. Alert on divergence beyond rounding tolerance; replay missing keys from archived topic with same idempotency store.

## Ordering with idempotency

Idempotency prevents duplicate effect not out-of-order — use partition key ordering for state machine transitions. Version column reject stale event even if idempotency key unique.

## Bulk idempotent batch consumers

Batch of 100 messages partial failure — commit offset per message processed not whole batch unless all idempotent individually. Document partial batch retry semantics in consumer README.

At-least-once plus idempotency beats fragile exactly-once dreams. Design keys from business identity, store outcomes, commit offsets after durability, and test duplicates on purpose.

Load test consumer with artificial duplicate delivery at 10x normal rate — dedup store must handle write contention without timing out handler.

Design review checklist item 1 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in at-least-once idempotent consumers often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for at-least-once idempotent consumers should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for at-least-once idempotent consumers documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 12 for at-least-once idempotent consumers: validate failure modes, owner, and rollback before merge to main.

## Common regressions around at least once idempotent consumers

Teams often pass a demo and then regress under load: retries without jitter, missing idempotency keys, or caches that never invalidate. Write a short regression list specific to at least once idempotent consumers and turn each item into an automated check or a game-day step. Prefer failing CI on the regression over discovering it from customer tickets. When you change defaults, update alerts in the same pull request so observability stays coupled to behavior.
