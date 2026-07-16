---
title: "Rate Limiting and Backpressure"
slug: "rate-limiting-backpressure"
description: "How rate limiting and backpressure protect services under load: token bucket, throttling, load shedding, and pushing back on producers — with algorithms and code."
datePublished: "2026-06-08"
dateModified: "2026-06-08"
tags: ["Backend", "Reliability", "Distributed Systems", "Performance"]
keywords: "rate limiting, backpressure, token bucket, throttling, API rate limits, load shedding, sliding window, flow control"
faq:
  - q: "What is the difference between rate limiting and backpressure?"
    a: "Rate limiting caps how many requests a client may make in a window and rejects the excess, usually at the edge. Backpressure is a signal that flows backward through a system telling upstream producers to slow down because a downstream component is saturated. One says 'no'; the other says 'slower.'"
  - q: "Which rate limiting algorithm should I use?"
    a: "Token bucket is the pragmatic default: it caps sustained rate while allowing short bursts, and it's cheap to implement in Redis. Sliding-window counters give smoother enforcement at slightly higher cost. Fixed windows are simplest but allow double-rate bursts at window boundaries."
  - q: "What is load shedding?"
    a: "Load shedding is deliberately rejecting some requests when a system is overloaded so it can keep serving the rest. Rejecting 10% of traffic fast is far better than accepting 100% and collapsing under it, which would make the service unavailable for everyone."
---

Every service has a breaking point, and the difference between a resilient system and a fragile one is what happens as you approach it. A fragile system accepts every request until it falls over completely, taking everyone down. A resilient one recognizes it's near capacity and starts saying "no" — or "slower" — early enough to stay up. Rate limiting and backpressure are the two mechanisms for doing that, and they solve related but distinct problems.

Rate limiting is a *policy*: this client gets N requests per minute, and request N+1 is rejected. Backpressure is a *dynamic signal*: a saturated component telling whoever feeds it to ease off. You need both. Rate limiting protects you from clients; backpressure protects your components from each other.

## Why unbounded acceptance kills

The failure I've watched most often isn't a service being too slow — it's a service that accepts more work than it can finish, so its queues grow without bound, memory balloons, latency climbs, and eventually it dies holding a backlog it will never clear. Worse, in a distributed system that death cascades: the dying service times out its callers, who retry, who pile on more load, and a localized hiccup becomes a system-wide outage.

The counterintuitive lesson is that **rejecting work is a feature.** A service that serves 90% of requests well and cleanly rejects the other 10% is far more useful than one that accepts everything and serves 0% because it's on the floor. Rate limiting and backpressure are how you choose that first outcome on purpose.

## Token bucket: the workhorse

For rate limiting, token bucket is the algorithm I reach for by default. Picture a bucket that refills with tokens at a steady rate up to a maximum. Each request takes a token; if the bucket's empty, the request is rejected (or delayed). The refill rate caps your sustained throughput, and the bucket size sets how big a burst you'll tolerate.

```python
# Token bucket in Redis via a Lua script (atomic refill + take)
LUA = """
local tokens = tonumber(redis.call('GET', KEYS[1]) or ARGV[3])
local last = tonumber(redis.call('GET', KEYS[2]) or ARGV[4])
local now, rate, cap = tonumber(ARGV[4]), tonumber(ARGV[1]), tonumber(ARGV[2])
tokens = math.min(cap, tokens + (now - last) * rate)   -- refill
if tokens < 1 then return 0 end
redis.call('SET', KEYS[1], tokens - 1)                 -- take one
redis.call('SET', KEYS[2], now)
return 1
"""
allowed = redis.eval(LUA, 2, f"tb:{client}", f"tb:ts:{client}",
                     rate, capacity, capacity, now)
```

The reason token bucket wins in practice is that real traffic is bursty. A mobile app that syncs on foreground sends a clump of requests, then goes quiet. A strict "10 per second, evenly spaced" limiter punishes that legitimate pattern; token bucket lets the burst through as long as the average stays under the refill rate. It matches how clients actually behave.

## Picking a window algorithm

| Algorithm | Bursts | Accuracy | Cost |
|---|---|---|---|
| Fixed window | allows 2x at boundaries | coarse | cheapest |
| Sliding window log | precise | exact | memory-heavy |
| Sliding window counter | smooth | good | moderate |
| Token bucket | controlled bursts | good | cheap |

Fixed windows have a well-known flaw: a client can fire a full window's worth of requests at 11:59:59 and another full window at 12:00:00, doubling the intended rate across the boundary. Sliding-window counters fix that by weighting the previous window, at modest cost. Unless you have a specific reason, token bucket or sliding-window counter covers the vast majority of API rate limiting needs.

## Returning limits like a good citizen

How you *communicate* a limit matters as much as enforcing it. Reject with HTTP `429 Too Many Requests`, and include a `Retry-After` header so well-behaved clients know exactly when to come back:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 12
RateLimit-Limit: 100
RateLimit-Remaining: 0
RateLimit-Reset: 12
```

On the client side, honor it. A retry loop that ignores `Retry-After` and hammers a `429` immediately is how a rate limit turns into a self-inflicted denial of service. On mobile, where I've spent a lot of time dealing with [flaky networks and retry behavior](https://blog.michaelsam94.com/handling-flaky-networks-mobile/), the right pattern is exponential backoff with jitter, seeded by the server's `Retry-After` when present. Retries are necessary; unbounded retries are an attack on your own backend.

## Backpressure: pushing the signal upstream

Rate limiting lives at the edge and deals with external clients. Backpressure lives *inside* your system and coordinates components. When a downstream stage — a database, a queue consumer, a worker pool — can't keep up, it needs to tell its upstream to slow down rather than silently accumulating an unbounded queue.

The cleanest expression of this is a bounded queue. When the queue fills, producers block (or get rejected) instead of piling on more work:

```kotlin
// A bounded channel applies backpressure: send() suspends when full
val channel = Channel<Job>(capacity = 1000)

// producer suspends here when the consumer falls behind — that's the signal
channel.send(job)
```

I've leaned on exactly this in real-time systems. Streaming telemetry from hardware — chargers, sensors — produces data faster than downstream can sometimes absorb it, and a bounded buffer with backpressure is what keeps a burst from exhausting memory. Reactive stacks (Kotlin Flow, Reactive Streams, gRPC streaming flow control) build backpressure into the protocol so a slow consumer automatically throttles a fast producer without any component making unbounded promises.

## Load shedding: choosing what to drop

When you're genuinely overloaded despite limits, the last line of defense is load shedding: deliberately dropping requests to protect the ones you keep. The key is to shed *intelligently*. Drop low-priority work first — background refreshes, analytics, prefetches — before user-facing critical paths. Health checks and already-in-flight requests should survive; new low-value requests are the first to go.

A good load shedder watches a saturation signal (queue depth, CPU, latency against your SLO) and sheds proportionally as it climbs. This ties directly into [SLOs and error budgets](https://blog.michaelsam94.com/designing-for-observability-slos/): your SLO defines what "overloaded" even means, and shedding is how you spend a little availability on the low-priority tail to protect the high-priority core. Combined with [rate limiting at the API gateway](https://blog.michaelsam94.com/backend-for-frontend-bff/), you get layered defense — the edge caps clients, internal backpressure coordinates stages, and load shedding is the fuse that blows before the whole thing melts.

## The mindset

Rate limiting, backpressure, and load shedding are all the same idea wearing different clothes: a system should know its limits and respond to approaching them deliberately, not accidentally. Cap clients with token buckets and honest `429`s, push backpressure through bounded queues so no component over-promises, and shed low-value load before the high-value load suffers. The goal is never to serve infinite traffic — it's to degrade gracefully instead of catastrophically. A system that says "no" cleanly under pressure is one you can sleep through the night with.

## Resources

- [Google SRE Book — Handling Overload](https://sre.google/sre-book/handling-overload/)
- [Google SRE Book — Addressing Cascading Failures](https://sre.google/sre-book/addressing-cascading-failures/)
- [Amazon Builders' Library — Timeouts, retries, and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/)
- [Stripe — Scaling your API with rate limiters](https://stripe.com/blog/rate-limiters)
- [Reactive Streams — Specification](https://www.reactive-streams.org/)
- [IETF — RateLimit header fields for HTTP](https://datatracker.ietf.org/doc/draft-ietf-httpapi-ratelimit-headers/)
