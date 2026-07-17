---
title: "System Design: URL Shortener"
slug: "system-design-url-shortener"
description: "Designing a URL shortener like bit.ly: base62 encoding, ID generation, read-heavy scaling, custom domains, analytics, and collision handling."
datePublished: "2025-11-25"
dateModified: "2026-07-17"
tags: ["System Design", "Backend", "Architecture", "Scalability"]
keywords: "URL shortener system design, bit.ly architecture, base62 encoding, snowflake ID, read heavy scaling, link analytics"
faq:
  - q: "How does a URL shortener generate short codes?"
    a: "Common approaches: auto-increment ID encoded in base62 (a-z, A-Z, 0-9), random strings with collision retry, or hash-based truncation of the long URL (risky for collisions). Production systems prefer monotonic IDs from a distributed ID generator (Snowflake, database sequence) converted to base62 for compact, URL-safe strings."
  - q: "Why are URL shorteners read-heavy and how do you scale reads?"
    a: "Create-to-click ratios are often 1:100 or higher — redirects dominate traffic. Scale with aggressive caching (CDN edge, Redis), read replicas for analytics lookups, and 301/302 redirects served from cache. Write path can tolerate slightly higher latency; read path must be sub-10ms at edge."
  - q: "Should redirects use 301 or 302?"
    a: "301 Moved Permanently tells browsers and search engines the short URL permanently maps to the target — good for stable marketing links but hard to change destination later. 302 Found is temporary — allows updating the target URL and is typical when you need analytics flexibility or may change destinations."
faqAnswers:
  - question: "When is system design url shortener the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for system design url shortener?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back system design url shortener safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## Metrics worth dashboarding

For url shortener, alert on symptoms users feel—not only infrastructure CPU:

| Signal | Why it matters |
|--------|----------------|
| p95/p99 latency | Tail latency drives timeouts and retries upstream |
| Error rate by operation | Separates transient blips from systemic failure |
| Saturation (pool, queue, disk) | Shows how close you are to hard limits |
| Business counter (success/failure) | Ties technical metrics to revenue or task completion |

Slice by version, region, and tenant during rollout. A flat global graph hides a bad canary.

## Custom domains and TLS at edge

Enterprise customers bring `links.customer.com` CNAME to your edge. Automate ACME certificate issuance per custom domain; failed cert provisioning blocks domain activation, not silent HTTP fallback. Resolve slug lookup after Host header — same slug can map differently per custom domain namespace. Analytics segment by domain for billing and abuse isolation.

## Custom slug collision policy

Custom aliases retry on conflict with user-visible error — do not silently append random suffix without telling marketing team. Reserve slug namespace for internal short links separate from customer vanity slugs.

## Resources

- [TinyURL / bit.ly engineering blogs](https://bitly.com/pages/engineering)
- [Twitter Snowflake ID](https://github.com/twitter-archive/snowflake)
- [Base62 encoding](https://en.wikipedia.org/wiki/Base62)
- [HTTP 301 vs 302 (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status)
- [Google Safe Browsing API](https://developers.google.com/safe-browsing)

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## system design url shortener rollout

Field RUM on Android 4G. RDS Proxy where relevant. Rollback in PR.

## Architecture decisions around system design url shortener

System design interviews and production systems diverge: system design url shortener in production needs SLOs, abuse controls, and multi-region failure stories. Sketch the data model and consistency requirements before drawing boxes.

For system design url shortener:
- Separate read and write scaling paths early if fan-out or search is involved
- Idempotency keys on payments, bookings, and message delivery
- Backpressure at every queue; unbounded buffers are delayed outages
- Hot-key and thundering-herd mitigations (jitter, singleflight, cache stampedes)

Write the load-test plan that would disprove your capacity claims — QPS, payload sizes, and regional failover RTO.

| Signal | Target | Alarm |
|--------|--------|-------|
| Plan apply time | Team-defined SLO | Page on burn rate |
| Drift open count | Baseline − noise | Ticket if sustained |
| Failed policy checks | Budget cap | Weekly review |

## Metrics and alarms for system design url shortener

Reviewers should challenge assumptions encoded in system design url shortener: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for system design url shortener: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for system design url shortener: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for system design url shortener: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Anti-patterns unique to system design url shortener

Roll out system design url shortener behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Observability cardinality around system design url shortener

Detail 1 (648): for system design url shortener, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When observability cardinality around system design url shortener becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design url shortener, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design url shortener: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Caching interactions with system design url shortener

Detail 2 (712): for system design url shortener, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When caching interactions with system design url shortener becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break system design url shortener, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about system design url shortener: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.