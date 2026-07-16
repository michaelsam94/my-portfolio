---
title: "System Design: URL Shortener"
slug: "system-design-url-shortener"
description: "Designing a URL shortener like bit.ly: base62 encoding, ID generation, read-heavy scaling, custom domains, analytics, and collision handling."
datePublished: "2025-11-25"
dateModified: "2025-11-25"
tags: ["System Design", "Backend", "Architecture", "Scalability"]
keywords: "URL shortener system design, bit.ly architecture, base62 encoding, snowflake ID, read heavy scaling, link analytics"
faq:
  - q: "How does a URL shortener generate short codes?"
    a: "Common approaches: auto-increment ID encoded in base62 (a-z, A-Z, 0-9), random strings with collision retry, or hash-based truncation of the long URL (risky for collisions). Production systems prefer monotonic IDs from a distributed ID generator (Snowflake, database sequence) converted to base62 for compact, URL-safe strings."
  - q: "Why are URL shorteners read-heavy and how do you scale reads?"
    a: "Create-to-click ratios are often 1:100 or higher — redirects dominate traffic. Scale with aggressive caching (CDN edge, Redis), read replicas for analytics lookups, and 301/302 redirects served from cache. Write path can tolerate slightly higher latency; read path must be sub-10ms at edge."
  - q: "Should redirects use 301 or 302?"
    a: "301 Moved Permanently tells browsers and search engines the short URL permanently maps to the target — good for stable marketing links but hard to change destination later. 302 Found is temporary — allows updating the target URL and is typical when you need analytics flexibility or may change destinations."
---

The URL shortener is the hello-world of system design interviews — and unfairly dismissed as trivial. bit.ly handles billions of redirects with analytics, custom domains, spam detection, and link editing. The core is a key-value lookup, but the engineering lives in ID generation at scale, read path latency, and not becoming a malware distribution network.

## Functional requirements

- Shorten long URL → unique short code
- Redirect short URL → original (HTTP 301/302)
- Optional: custom alias, expiration, click analytics, authenticated API

## Non-functional requirements

- **Read:write ratio** ~100:1 or higher
- Redirect p99 < 50ms (edge)
- Short codes 6–8 characters for billions of URLs
- High availability — broken redirects break user trust instantly

## API design

```
POST /api/v1/urls
{ "long_url": "https://example.com/very/long/path", "custom_slug": "optional" }
→ { "short_url": "https://sho.rt/abc12X" }

GET /abc12X
→ 302 Location: https://example.com/very/long/path
```

## ID generation and base62

Auto-increment counter 125_000_000 → base62 → `"8m0Kx"`.

```python
BASE62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def encode(num: int) -> str:
    if num == 0:
        return BASE62[0]
    chars = []
    while num:
        num, rem = divmod(num, 62)
        chars.append(BASE62[rem])
    return "".join(reversed(chars))
```

**Snowflake / DB sequence** for distributed unique IDs without coordination bottleneck.

**Random 7-char base62** — 62^7 ≈ 3.5 trillion space; retry on unique constraint violation. Simple but collision handling needed at scale.

**Hash truncation (MD5 first 7 chars)** — collision risk; avoid for user-generated URLs.

## Storage schema

```sql
CREATE TABLE urls (
  id          BIGSERIAL PRIMARY KEY,
  slug        VARCHAR(10) UNIQUE NOT NULL,
  long_url    TEXT NOT NULL,
  user_id     UUID,
  created_at  TIMESTAMPTZ DEFAULT now(),
  expires_at  TIMESTAMPTZ,
  is_active   BOOLEAN DEFAULT true
);

CREATE INDEX idx_urls_slug ON urls(slug);
```

Hot path: `SELECT long_url FROM urls WHERE slug = $1 AND is_active`.

## Read path — cache everything

```
Request → CDN edge (cache 301/302 if immutable)
        → miss → Redis GET slug
        → miss → Postgres → SET Redis → redirect
```

Redis stores `slug → long_url` with TTL for inactive links. CDN caches redirect responses — use shorter cache TTL if destinations change (302) or long TTL for permanent links (301).

**Geographic distribution:** Cloudflare Workers or regional Redis for global p99.

## Write path

```
POST → validate URL (length, malware scan, blocklist)
     → generate slug
     → INSERT (handle unique violation)
     → return short URL
```

Async: enqueue analytics indexing, spam classification.

## Analytics (optional but expected)

Separate write-heavy click stream:

```
Redirect → async log { slug, timestamp, referrer, ua, geo }
         → Kafka / Redis Stream → aggregate to click_counts table
```

Do not block redirect on analytics write — fire-and-forget with durable queue.

## Custom domains and multi-tenancy

`brand.co/promo` requires:

- DNS CNAME to your service
- TLS cert provisioning (Let's Encrypt automation)
- Host header → tenant routing → slug namespace per tenant

Slug uniqueness scoped to `(tenant_id, slug)`.

## Security

- Block phishing URLs (Google Safe Browsing API)
- Rate limit creation per IP/API key
- Preview interstitial for suspicious links
- Do not expose internal network URLs (SSRF on fetch-if-preview)

## Capacity estimate

- 1B URLs × ~500 bytes metadata ≈ 500GB DB
- 100k redirects/sec peak
- Redis: millions of hot slugs, LRU eviction for cold

Horizontal: stateless redirect servers, sharded Postgres or Cassandra for URL store at extreme scale.

## Abuse prevention and link safety

Rate-limit creation per IP and API key. Scan destination URLs against malware blocklists before shortening. Offer preview interstitial for flagged domains. Monitor redirect chains for SEO spam — attackers use shorteners to launder malicious links. Periodic audit of top referrers catches automated abuse early.




Pre-generate short codes in batches — generating codes synchronously on redirect request creates hot-row contention on insert.

## Base62 encoding and collision handling

```python
def encode_base62(num: int) -> str:
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result = []
    while num:
        num, rem = divmod(num, 62)
        result.append(alphabet[rem])
    return ''.join(reversed(result)) or '0'
```

Pre-allocate ID ranges from DB sequence — insert on create avoids collision retry loops under load.

## Common production mistakes

Teams get url shortener wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

System design for url shortener breaks at scale when hot keys, thundering herds, and cache stampedes are discovered during launch week instead of load test week.

## Debugging and triage workflow

When url shortener misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Metrics worth dashboarding

For url shortener, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Resources

- [TinyURL / bit.ly engineering blogs](https://bitly.com/pages/engineering)
- [Twitter Snowflake ID](https://github.com/twitter-archive/snowflake)
- [Base62 encoding](https://en.wikipedia.org/wiki/Base62)
- [HTTP 301 vs 302 (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [Google Safe Browsing API](https://developers.google.com/safe-browsing)
