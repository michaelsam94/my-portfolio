---
title: "System Design: Search Autocomplete"
slug: "system-design-search-autocomplete"
description: "Designing search autocomplete at scale: trie vs prefix indexes, Elasticsearch completion suggester, ranking signals, debouncing, and latency budgets under 100ms."
datePublished: "2025-11-17"
dateModified: "2025-11-17"
tags: ["System Design", "Search", "Backend", "Architecture"]
keywords: "search autocomplete system design, typeahead, trie prefix search, Elasticsearch completion, search suggestions latency"
faq:
  - q: "What data structure powers autocomplete?"
    a: "Prefix trees (tries) are the classic structure — each node represents a character and paths form indexed terms. Production systems often use specialized indexes instead: Elasticsearch completion suggester (FST-based), prefix queries on edge n-grams, or dedicated services like Algolia. The goal is sub-millisecond prefix lookup on millions of terms."
  - q: "How do you rank autocomplete suggestions?"
    a: "Rank by blended signals: prefix match quality (exact prefix beats fuzzy), historical click-through rate, search frequency, recency, personalization (user history), and business rules (boost sponsored terms). Most systems precompute top-K suggestions per prefix offline and serve from cache at query time."
  - q: "What latency budget should autocomplete target?"
    a: "Target p95 under 100ms end-to-end, with the server portion under 30ms. Users type fast — slower suggestions feel broken or show stale prefixes. Debounce client requests (150–300ms), cancel in-flight requests on new keystrokes, and serve from CDN or edge cache for popular prefixes when possible."
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

## Common production mistakes

Teams get search autocomplete wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for search autocomplete breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When search autocomplete misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Metrics worth dashboarding

For search autocomplete, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Resources

- [Elasticsearch completion suggester](https://www.elastic.co/guide/en/elasticsearch/reference/current/search-suggesters.html#completion-suggester)
- [Google search autocomplete patent concepts](https://patents.google.com/patent/US8799763)
- [Algolia autocomplete architecture](https://www.algolia.com/doc/ui-libraries/autocomplete/introduction/what-is-autocomplete/)
- [FST data structure overview](https://en.wikipedia.org/wiki/Finite-state_transducer)
- [Debounce vs throttle (web.dev)](https://web.dev/articles/debounce-your-input-handlers)
