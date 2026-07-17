# Article bodies for system-design + terraform batch rewrite

POSTS["system-design-search-autocomplete"] = {
    "meta": {
        "title": "System Design: Search Autocomplete",
        "description": "Designing search autocomplete at scale: trie vs prefix indexes, Elasticsearch completion suggester, ranking signals, debouncing, and latency budgets under 100ms.",
        "datePublished": "2025-11-17",
        "tags": ["System Design", "Search", "Backend", "Architecture"],
        "keywords": "search autocomplete system design, typeahead, trie prefix search, Elasticsearch completion, search suggestions latency",
        "faq": [
            {
                "q": "What data structure powers autocomplete?",
                "a": "Prefix trees (tries) are the classic structure — each node represents a character and paths form indexed terms. Production systems often use specialized indexes instead: Elasticsearch completion suggester (FST-based), prefix queries on edge n-grams, or dedicated services like Algolia. The goal is sub-millisecond prefix lookup on millions of terms.",
            },
            {
                "q": "How do you rank autocomplete suggestions?",
                "a": "Rank by blended signals: prefix match quality (exact prefix beats fuzzy), historical click-through rate, search frequency, recency, personalization (user history), and business rules (boost sponsored terms). Most systems precompute top-K suggestions per prefix offline and serve from cache at query time.",
            },
            {
                "q": "What latency budget should autocomplete target?",
                "a": "Target p95 under 100ms end-to-end, with the server portion under 30ms. Users type fast — slower suggestions feel broken or show stale prefixes. Debounce client requests (150–300ms), cancel in-flight requests on new keystrokes, and serve from CDN or edge cache for popular prefixes when possible.",
            },
        ],
    },
    "body": r'''
A product manager once asked why autocomplete felt "broken" even though full search returned correct results in under two hundred milliseconds. The answer was keystroke physics: by the time a user types "blu" they have already moved on to "blur" or deleted a character. Suggestions that arrive late are worse than no suggestions — they flash stale prefixes and erode trust faster than a slow results page.

Autocomplete is not miniature search. It is a ranking problem compressed into a sub-100ms budget where every millisecond competes with the user's next keystroke. Netflix, Amazon, and Google trained billions of people to expect ranked, spelled-correct completions before the third character lands. Production systems must handle typo tolerance, fresh catalog indexing, personalization, sponsored placement, and A/B tests on ranking weights — while eighty percent of traffic hammers the same few thousand prefixes.

## What you are actually building

Clarify requirements before picking data structures. Functional scope usually includes: return five to ten suggestions after two or three characters; cover products, categories, brands, and recent searches; optionally tolerate light typos at the prefix stage. Non-functional requirements dominate: p95 end-to-end latency under 100ms, graceful degradation (empty suggestions, never a page error), and index freshness within minutes of catalog changes.

Capacity planning starts with query shape. Autocomplete QPS often exceeds full search QPS because every keystroke can fire a request (mitigated by debouncing). Peak traffic concentrates on short prefixes: "a", "ap", "app" during an iPhone launch. Long-tail prefixes are sparse but numerous. Design for hot-prefix amplification, not average load.

## Architecture: write path vs read path

Separate ingestion from serving. The write path flows: catalog change event → stream processor → indexer → completion structure update → cache invalidation for affected prefix families. The read path: debounced prefix → API gateway → suggest service → cache → index fallback → ranking → response.

```
[Client] --150ms debounce--> [Edge/API] --> [Suggest Service]
                                                |
                         +----------------------+---------------------+
                         |                      |                     |
                   [Redis/LFU cache]     [Completion index]    [Ranking weights]
                   hot prefix → top-K     FST / trie / ES       CTR, freq, rules
```

The suggest service should be stateless and horizontally scaled. Personalization adds a lightweight sidecar lookup (user's last ten searches) merged after global candidates are fetched — never block the critical path on a slow profile service.

## Index structures in practice

| Approach | Lookup cost | Update cost | Best when |
| --- | --- | --- | --- |
| In-memory trie | Microseconds | Hard (rebuild or delta trie) | Fixed vocab, <10M terms |
| Elasticsearch completion | Low ms at scale | Moderate (reindex fields) | Already on ES, need contexts |
| Edge n-gram + prefix query | Flexible fuzzy | Heavy index size | Typo tolerance required |
| Managed (Algolia, Typesense) | Very low | Vendor pipeline | Ship fast, pay ongoing |

Elasticsearch completion fields use finite state transducers (FSTs) compressed on disk. They support **contexts** — category, locale, store_id — so "app" in Electronics differs from "app" in Grocery:

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

For pure speed at extreme scale, many teams precompute top-K suggestions per prefix offline. A nightly job walks search logs, computes weighted candidates for every prefix of length 2–6 appearing more than N times, and writes to Redis:

```
Key: suggest:v3:{locale}:{prefix}
Value: JSON array [{text, score, payload_id}, ...]
TTL: 24h, refresh incrementally
```

Query time becomes a single Redis GET — sub-millisecond for known hot prefixes.

## Ranking beyond alphabetical order

Alphabetical order is never correct. Production ranking blends:

1. **Prefix match quality** — exact prefix match ranks above infix or fuzzy.
2. **Popularity** — global search frequency and conversion rate.
3. **Recency** — trending queries and newly launched SKUs.
4. **Personalization** — user's search and purchase history (applied as a boost, not a filter).
5. **Business rules** — sponsored suggestions, category pinning, blocked terms.

Precompute a base score offline; apply personalization and rules at query time in under 5ms:

```python
def rank_suggestions(prefix: str, candidates: list, user_ctx: dict) -> list:
    scored = []
    for c in candidates:
        score = c.base_score
        if c.text.startswith(prefix):
            score *= 1.2
        if c.text in user_ctx.get("recent_searches", []):
            score *= 1.15
        if c.sponsored and policy_allows_sponsored(user_ctx):
            score *= 1.1
        scored.append((score, c))
    return [c for _, c in sorted(scored, reverse=True)[:10]]
```

Log impressions and clicks with `suggestion_id`, `position`, and `prefix` for offline learning. Most teams start with hand-tuned weights, graduate to logistic regression on click-through, then experiment with lightweight neural rankers only if traffic justifies the serving cost.

## Client-side behavior matters as much as the server

Debounce 150–300ms depending on device class. Cancel in-flight requests when the prefix changes — stale responses reorder the dropdown incorrectly. Show the previous suggestion list with reduced opacity while loading; never clear to empty between keystrokes.

Minimum prefix length of two or three characters cuts index fan-out dramatically. Some systems use one character only for ultra-hot prefixes preloaded at app start.

Keyboard navigation, accessibility (ARIA listbox), and mobile IME composition events (CJK input) break naive implementations. During IME composition, suppress suggest requests until compositionend fires.

## Freshness, safety, and abuse

Index updates must propagate within minutes. Stream catalog changes through Kafka; incremental indexer updates affected FST segments or Redis keys. Full rebuilds nightly catch drift.

Blocklist offensive terms, competitor trademarks per legal policy, and empty suggestions for medical or regulated queries. Rate-limit suggest endpoints per IP and per session to prevent scraping your entire catalog via prefix enumeration.

## Failure modes and degradation

If Elasticsearch is down, serve from Redis cache only — partial suggestions beat timeout. If ranking service is slow, skip personalization and return popularity order. Set aggressive timeouts (20ms per dependency) and fail open to cached global lists.

Monitor: p50/p95/p99 latency per prefix length, cache hit ratio, empty-result rate, click-through rate by position, index lag behind catalog.

## Capacity back-of-envelope

10M daily active users, 20 suggest requests per session debounced to 8 effective, peak 2× average → ~160M suggest requests/day ≈ 1,850 QPS average, 5,000 QPS peak. At 2KB response, 10 MB/s egress — trivial. CPU on suggest nodes is the bottleneck if you query ES per request; precomputed Redis answers push bottleneck to network.

## What interviewers and production both probe

Walk through: requirements, hot-prefix caching, index choice, offline precomputation vs online query, ranking signals, client debounce/cancel, degradation strategy. The insight that separates senior answers: autocomplete is a **log-driven, cache-fronted prefix lookup** with ranking layered on top — not "run SELECT WHERE title LIKE 'blu%' on every keystroke."
''',
}

POSTS["system-design-ticketing-booking"] = {
    "meta": {
        "title": "System Design: Ticketing System",
        "description": "Designing a ticketing and booking system: inventory holds, overselling prevention, seat maps, payment integration, and handling flash-sale traffic spikes.",
        "datePublished": "2025-11-21",
        "tags": ["System Design", "Backend", "Architecture", "Distributed Systems"],
        "keywords": "ticketing system design, seat reservation, inventory hold, concert ticket booking, overselling prevention, flash sale",
        "faq": [
            {
                "q": "How do ticketing systems prevent double booking?",
                "a": "Use atomic inventory decrements with database constraints or distributed locks. The hold pattern reserves seats temporarily (5–15 minutes) while the user pays; confirmed booking converts the hold to a sale. Compare-and-swap on remaining count, or row-level locks on seat records, prevent two transactions from claiming the same seat.",
            },
            {
                "q": "What is the difference between a hold and a confirmed booking?",
                "a": "A hold is a temporary reservation that expires if payment is not completed — inventory is soft-locked. A confirmed booking is permanent after successful payment, with a ticket issued. Holds must TTL-expire and release inventory automatically via scheduled jobs or Redis key expiry callbacks.",
            },
            {
                "q": "How do you handle flash sale traffic for popular events?",
                "a": "Queue users before they hit inventory (virtual waiting room), serve holds from a pre-sharded inventory pool, cache event metadata aggressively, and decouple payment from seat selection when possible. Rate limit per user, use CDN for static seat maps, and load test the hold-confirm path at expected peak QPS.",
            },
        ],
    },
    "body": r'''
At 10:00:00 AM, two hundred thousand browsers refresh a Ticketmaster page for eight thousand seats. Within three seconds, the inventory service sees more contention than most e-commerce systems see in a week. One double-booked seat generates lawsuits, news coverage, and permanent brand damage. Ticketing is inventory management under adversarial load with a visible clock counting down every hold.

The hard parts are not drawing a seat map UI. They are atomic reservation under peak concurrency, hold expiration that actually releases inventory, payment webhooks that arrive thirty seconds late, and bots that automate cart hoarding.

## Domain model

Core entities chain together:

```
Event ──< Section ──< Row ──< Seat
  │
  └── PricingTier (GA, VIP, early bird)

Hold (seat_id, user_id, expires_at, status)
Order (hold_ids[], payment_id, status)
Ticket (order_id, seat_id, barcode, status)
```

General admission collapses the graph to a pool counter: `GA_remaining` decremented atomically. Reserved seating requires per-seat state machines. Mixed venues run both patterns behind one checkout API.

## The hold lifecycle

Every seat traverses:

```
Available → Held (TTL) → Sold
                ↓
            Expired → Available
```

**Pessimistic locking** for interactive seat maps — lock the row, verify status, update:

```sql
BEGIN;
SELECT status FROM seats WHERE id = $1 FOR UPDATE;
-- abort if not 'available'
UPDATE seats SET status = 'held', hold_expires_at = now() + interval '10 min'
  WHERE id = $1 AND status = 'available';
COMMIT;
```

**Optimistic atomic decrement** for GA pools:

```sql
UPDATE ga_inventory
SET remaining = remaining - 1
WHERE event_id = $1 AND section_id = $2 AND remaining > 0
RETURNING remaining;
```

Zero rows updated means sold out — no application-level race if the SQL is correct.

## Redis-first holds for hot events

Postgres row locks under 50k QPS become a choke point. Pattern: attempt hold in Redis first, async persist to Postgres.

```redis
SET hold:evt-99:seat-14A user-42 EX 600 NX
```

`NX` fails instantly if another user holds the seat. On success, enqueue a persistence job. On payment capture, promote to `sold` in both stores. On TTL expiry, Redis deletes the key; a worker reconciles Postgres.

The trade-off is drift between Redis and Postgres. Run reconciliation every minute: scan held seats in DB whose Redis key vanished, release them. Accept eventual consistency only with tight reconciliation SLAs.

## Virtual waiting room

Before users touch inventory, admit them from a queue at a controlled rate (e.g., 5,000/minute). Cloudflare Waiting Room, Queue-it, or a homegrown token bucket at the edge issues admission cookies. Users without a valid admission token receive HTTP 429 on hold endpoints.

This sounds hostile; it prevents inventory service meltdown and gives honest users a fair shot against bots.

## Seat map vs best-available

**Interactive seat map** — user picks exact seats. Requires vector tiles CDN-cached, WebSocket or SSE for live seat status as others hold, and per-seat contention.

**Best available** — algorithm assigns contiguous blocks. Fewer round trips, easier sharding, lower lock contention. Flash sales often default here.

Many platforms offer both; high-demand on-sales may force best-available until load subsides.

## Payment integration and the dangerous gap

Never confirm a ticket on client-side payment success alone. Flow:

1. User completes hold → `POST /orders` with hold IDs
2. Payment intent created → user pays
3. Webhook `payment.captured` arrives (async, retriable)
4. Server converts holds to sold idempotently (`payment_id` as idempotency key)
5. Issue ticket with signed barcode (JWT or rotating TOTP)

If webhook is delayed, show "payment processing" — do not release holds until payment failure is confirmed or hold TTL expires. Extend hold TTL automatically when payment is in `processing` state.

## Bot and scalper mitigation

Device fingerprinting, CAPTCHA at queue admission, purchase limits per account and payment instrument, non-transferable holds tied to verified identity for high-demand shows, and velocity checks on hold creation. Scalpers exploit hold TTL — they lock prime seats, release at expiry, immediately re-hold with scripts.

Some jurisdictions require face-value resale platforms; architecture may need transfer APIs with price caps.

## Read scaling vs write contention

Event metadata (name, date, venue, static seat map geometry) is aggressively CDN-cached. Inventory writes are the bottleneck — partition by `event_id` shard so Beyoncé and Broadway don't share one lock namespace.

## Observability

Track: holds created/sec, hold-to-purchase conversion, expired holds, double-booking attempts blocked, payment webhook lag p99, reconciliation drift count. Alert on any seat with two active sold records — should be impossible if invariants hold.

## Interview and production synthesis

Strong answers cover: entity model, hold TTL, atomic decrement vs row lock, Redis acceleration with reconciliation, waiting room, payment webhook idempotency, and bot mitigation. The memorable line: **ticketing sells finite state machines, not tickets** — every seat is a small concurrent program with a clock.
''',
}
