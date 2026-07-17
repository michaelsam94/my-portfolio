---
title: "System Design: Search Autocomplete"
slug: "system-design-search-autocomplete"
description: "Designing search autocomplete at scale: trie vs prefix indexes, Elasticsearch completion suggester, ranking signals, debouncing, and latency budgets under 100ms."
datePublished: "2025-11-17"
dateModified: "2026-07-17"
tags: ["System Design", "Search", "Backend", "Architecture"]
keywords: "search autocomplete system design, typeahead, trie prefix search, Elasticsearch completion, search suggestions latency"
faq:
  - q: "What data structure powers autocomplete?"
    a: "Prefix trees (tries) are the classic structure — each node represents a character and paths form indexed terms. Production systems often use specialized indexes instead: Elasticsearch completion suggester (FST-based), prefix queries on edge n-grams, or dedicated services like Algolia. The goal is sub-millisecond prefix lookup on millions of terms."
  - q: "How do you rank autocomplete suggestions?"
    a: "Rank by blended signals: prefix match quality (exact prefix beats fuzzy), historical click-through rate, search frequency, recency, personalization (user history), and business rules (boost sponsored terms). Most systems precompute top-K suggestions per prefix offline and serve from cache at query time."
  - q: "What latency budget should autocomplete target?"
    a: "Target p95 under 100ms end-to-end, with the server portion under 30ms. Users type fast — slower suggestions feel broken or show stale prefixes. Debounce client requests (150–300ms), cancel in-flight requests on new keystrokes, and serve from CDN or edge cache for popular prefixes when possible."
faqAnswers:
  - question: "When is system design search autocomplete the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design search autocomplete?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design search autocomplete safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Autocomplete is a search system compressed into a keystroke budget. Users expect suggestions before they finish typing "blu" — ranked, spelled correctly, and irrelevant noise hidden. Netflix, Amazon, and Google trained everyone that slow or dumb suggestions mean the product is broken, even when full search works fine.

The design interview version asks for millions of queries, personalized ranking, and 50ms p99. The production version adds typo tolerance, fresh content indexing, A/B tests on ranking weights, and the reality that 80% of traffic hits the same few thousand prefixes.

## Requirements framing

**Functional:**

- Suggest top 5–10 completions as user types (minimum 2–3 characters)
- Support products, categories, and recent searches
- Handle typos lightly (optional at prefix stage)

**Non-functional:**

- p95 latency < 100ms
- High availability (degraded = empty suggestions, not page error)
- Index updates within minutes of catalog change

## High-level architecture

```
[Client] --debounced--> [API Gateway] --> [Suggest Service]
                                              |
                    +-------------------------+------------------+
                    |                         |                  |
              [Redis cache]           [Elasticsearch]    [Ranking service]
              hot prefixes              completion index     CTR weights
```

**Write path:** catalog changes → stream to indexer → update completion FST / trie → invalidate cache keys for affected prefixes.

**Read path:** prefix → cache lookup → on miss, query index → apply ranking → cache result → return.

## Index options

| Approach | Pros | Cons |
| --- | --- | --- |
| In-memory trie | Microsecond lookup | Memory, update complexity |
| ES completion suggester | Built-in, FST compressed | ES ops burden |
| Prefix + edge n-gram | Flexible matching | Heavier index size |
| Dedicated SaaS (Algolia) | Fast to ship | Cost, less control |

Elasticsearch completion field example:

```json
PUT products
{
  "mappings": {
    "properties": {
      "suggest": {
        "type": "completion",
        "contexts": {
          "category": { "type": "category" }
        }
      }
    }
  }
}
```

```json
POST products/_search
{
  "suggest": {
    "product-suggest": {
      "prefix": "blu",
      "completion": {
        "field": "suggest",
        "size": 10,
        "contexts": { "category": "electronics" }
      }
    }
  }
}
```

Context filtering (category, locale, tenant) is essential for multi-tenant catalogs.

## Ranking beyond alphabetically first

Precomputed popularity weights attached to each suggestion entry:

```
"bluetooth speaker" weight: 942
"blue ray player"   weight: 12
```

At query time, merge index order with:

- **Global popularity** — query log aggregation offline
- **Personalization** — user's recent clicks boost related prefixes
- **Freshness** — new product launch boost window
- **Business rules** — pinned campaigns (label clearly in UI)

Offline job computes `prefix → [term, score]` tables for top 100k prefixes; long tail hits ES directly.

## Caching strategy

Key: `suggest:{locale}:{category}:{prefix}` with TTL 5–15 minutes. Invalidate on index update for affected terms. Popular prefixes ("iph", "sam") stay permanently warm.

**Thundering herd on cache miss:** single-flight rebuild per prefix key.

## Client-side concerns

```javascript
let controller;
function onInput(prefix) {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(async () => {
    controller?.abort();
    controller = new AbortController();
    const res = await fetch(`/api/suggest?q=${encodeURIComponent(prefix)}`, {
      signal: controller.signal,
    });
    renderSuggestions(await res.json());
  }, 200);
}
```

Debounce 150–300ms. Abort stale requests. Keyboard navigation (arrows, enter) without extra round trips.

## Failure and degradation

If suggest service fails, return empty array — do not block page. Log miss rate. Full search still works. Consider static fallback for top queries during outages.

## Scale numbers (order of magnitude)

- 10M indexed terms
- 50k suggest QPS peak
- ~500MB in-memory hot prefix cache
- Index rebuild: incremental updates, full rebuild weekly

Sharding ES by locale or tenant. Redis cluster for cache.

## Observability for suggest services

Track p50/p95 latency per prefix length, cache hit rate, and zero-result rate. Spikes in zero-results often mean index drift or a bad deploy — not user behavior change. Log anonymized prefix + selected suggestion position for offline ranking tuning without storing raw queries tied to users if policy restricts it.

## Ranking signals for autocomplete

Blend signals with tunable weights:

```
score = 0.4 * prefix_match + 0.3 * popularity + 0.2 * recency + 0.1 * personalization
```

Debounce client input 150ms. Cache top queries in Redis — "lap" → precomputed suggestions. Protect against empty-prefix browse overload with rate limits.

## Metrics worth dashboarding

For search autocomplete, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Multilingual and locale-specific indexes

Autocomplete indexes are per-locale — German compound words, CJK n-gram tokenization, and RTL display order each need separate index pipelines. Never mix locales in one completion field; "gift" means present in English and poison in German. Route suggest requests to locale-specific index shards via `Accept-Language` or explicit user preference. Pre-warm cache keys per locale during deploy so cold-start after index rebuild does not spike latency globally.

## Latency SLO for suggest API

Target p99 under 50 ms for autocomplete — users type faster than 100 ms intervals. Cache prefix trie in memory per region; warm on deploy from snapshot file to avoid cold-start latency spike.

## Resources

- [Elasticsearch completion suggester](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-suggesters.html#completion-suggester)
- [Google search autocomplete patent concepts](https://patents.google.com/patent/US8799763)
- [Algolia autocomplete architecture](https://www.algolia.com/doc/ui-libraries/autocomplete/introduction/what-is-autocomplete/)
- [FST data structure overview](https://en.wikipedia.org/wiki/Finite-state_transducer)
- [Debounce vs throttle (web.dev)](https://web.dev/articles/debounce-your-input-handlers)

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design search autocomplete rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Trade-offs I keep revisiting for system design search autocomplete

System design interviews and production systems diverge: system design search autocomplete in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design search autocomplete:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Coverage % | Team-defined SLO | Page on burn rate |
| Mean time to detect | Baseline − noise | Ticket if sustained |
| Escapes to prod | Budget cap | Weekly review |

## What reviewers should challenge in system design search autocomplete PRs

Reviewers should challenge assumptions encoded in system design search autocomplete: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario C for system design search autocomplete: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
2. Scenario A for system design search autocomplete: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
3. Scenario B for system design search autocomplete: bad config shipped — prove rollback within the declared RTO without data corruption.

## Post-incident changes after system design search autocomplete failures

Roll out system design search autocomplete behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Multi-tenant concerns in system design search autocomplete

Detail 1 (140): for system design search autocomplete, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When multi-tenant concerns in system design search autocomplete becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design search autocomplete, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design search autocomplete: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Compliance evidence for system design search autocomplete

Detail 2 (230): for system design search autocomplete, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for system design search autocomplete becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design search autocomplete, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design search autocomplete: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.