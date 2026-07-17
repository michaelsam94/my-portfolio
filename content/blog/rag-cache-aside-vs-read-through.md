---
title: "Cache-Aside vs Read-Through: Patterns for Hot Data Paths"
slug: "rag-cache-aside-vs-read-through"
description: "Stampede prevention, TTL jitter, invalidation on write, and when read-through simplifies consistency."
datePublished: "2025-06-12"
dateModified: "2026-07-17"
tags:
  - "Caching"
  - "Architecture"
  - "Performance"
keywords: "cache aside, read through, cache stampede, invalidation"
faq:
  - q: "What is cache-aside?"
    a: "Application reads cache first; on miss loads store, populates cache, returns — app owns cache logic explicitly."
  - q: "What is read-through?"
    a: "Cache library loads from store on miss transparently — simpler call site but library must understand data source and errors."
  - q: "When prefer write-through?"
    a: "When read-after-write consistency must be immediate and write volume moderate — writes update cache and store together."
---
Every performance guide mentions caching; production pain comes from stampedes on expiry, stale reads after writes, and cold starts after deploys. Cache-aside keeps application control; read-through centralizes load logic in the cache layer. Choosing wrong pattern shows up as thundering herd on TTL alignment or ghost reads after partial invalidation.

## Cache-aside flow and pitfalls

App: GET cache → miss → GET DB → SET cache. On write: update DB then DELETE cache key — not update cache with stale computed values race.

Document cache key naming convention including tenant and schema version — silent key format change causes mass miss without code deploy.

## Read-through with loading cache

Guava LoadingCache or Redis with custom module — singleflight dedupes concurrent misses on same key.

## TTL jitter against stampede

expire = base + random(0, jitter) spreads expirations; soft TTL refresh in background before hard expiry.

## Invalidation patterns

Version suffix in key on schema change; pubsub invalidation for multi-instance consistency.

## Negative caching

Cache short TTL for known missing keys — prevent DB hammer on invalid IDs.

## Observability

Hit rate, miss latency, reload errors, stampede detector on simultaneous misses — alert when miss storm.

## Cache warming after cold deploy

Empty cache after deploy causes miss storm — warm critical keys from read replica before shifting traffic. Blue-green cache instances per deploy version avoids cross-version stale entries during rolling migration of serialization format.

## Serialization format migrations

Changing JSON to protobuf in cache value breaks all entries — version prefix in key enables blue-green cache population before cutover. Monitor deserialize error rate after deploy.

## Multi-tier cache hierarchy

Local Caffeine in front of Redis — invalidation must propagate both tiers via pubsub. Stale L1 after L2 delete causes ghost reads until TTL expires unless explicit local invalidate on write.

Cache-aside versus read-through is who owns load on miss — either way add jitter, singleflight, and write invalidation discipline. Unbounded TTL is a consistency bug waiting for stale checkout prices.

Monitor cache hit rate drop after deploy separately from error rate — silent key version bug masquerades as database slowness.

Design review checklist item 1 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 1 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 1 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 1 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 2 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 2 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 2 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 2 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 3 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 3 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 3 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 3 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 4 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 4 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 4 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 4 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 5 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 5 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 5 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 5 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 6 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 6 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 6 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 6 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 7 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 7 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 7 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 7 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 8 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 8 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 8 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 8 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 9 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 9 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 9 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 9 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 10 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 10 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 10 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 10 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 11 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

Observability gap 11 in cache-aside versus read-through caching often appears as missing correlation IDs across async boundaries — fix before peak.

Regression test 11 for cache-aside versus read-through caching should assert behavior under duplicate requests and slow dependencies.

Runbook section 11 for cache-aside versus read-through caching documents escalation when primary and secondary on-call roles are unreachable.

Design review checklist item 12 for cache-aside versus read-through caching: validate failure modes, owner, and rollback before merge to main.

## What to watch after shipping cache aside vs read through

The first week after rollout is when silent misconfigurations show up. Watch p95 latency and error rate for the new path, compare against the previous baseline, and sample logs for unexpected status codes. Keep a feature flag or config kill switch until the metrics stabilize. Document the owner of the dashboard and the expected "green" ranges so the next on-call engineer is not reverse-engineering intent from a blank Grafana folder.
