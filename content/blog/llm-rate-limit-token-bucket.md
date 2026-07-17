---
title: "Rate Limit Token Bucket"
slug: "llm-rate-limit-token-bucket"
description: "Implement token-bucket rate limits for agent APIs: burst-friendly quotas for tool loops, Redis Lua atomicity, multi-dimensional limits on tokens and cost, and Retry-After headers clients actually respect for teams running LLM features in production."
datePublished: "2025-11-29"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "token bucket rate limit agents, Redis Lua rate limiting, LLM API quota burst, Retry-After agent clients, multi-dimensional rate limits"
faq:
  - q: "Why token bucket instead of fixed window for agent endpoints?"
    a: "Agent sessions burst: a user sends one message, the backend fires six tool calls in two seconds, then goes idle. Fixed windows either block legitimate bursts or allow 2x spikes at window boundaries. Token bucket permits controlled bursts while enforcing average rate over time."
  - q: "Should rate limits apply per user, per API key, or per tenant?"
    a: "All three, nested. Tenant limit protects your infrastructure; API key limit protects integrators from runaway scripts; user limit protects shared-tenant fairness. Check cheapest scope first to fail fast."
  - q: "How do you rate-limit token consumption vs HTTP requests?"
    a: "Maintain separate buckets: requests_per_minute for ingress, tokens_per_minute and cost_usd_per_hour for egress to model providers. A single slow request can exhaust token budget without high request count — one-dimensional limits miss that."
  - q: "What should Retry-After contain for agent clients?"
    a: "Seconds until the bucket has enough tokens for the requested cost, not a generic 60. Agent SDKs should read Retry-After, backoff with jitter, and surface a user-visible 'rate limited' state instead of retrying tool loops blindly."
---
A script called your agent API 400 times in a minute. Each call was "valid." Each triggered a three-tool loop averaging 8,000 completion tokens. The invoice arrived before the alert fired because you counted **requests** while the attacker — or more often, a buggy retry loop — consumed **tokens**. Fixed-window counters at the edge didn't help; the damage was downstream.

Token bucket rate limiting fits agent workloads because it models **sustained throughput with tolerated bursts** — exactly how humans and autonomous loops behave.

## Token bucket mechanics in plain terms

The bucket holds at most `capacity` tokens. Tokens refill continuously at `refill_rate` per second. Each operation consumes `cost` tokens. If insufficient tokens exist, reject or queue.

```
capacity = 100 tokens
refill_rate = 10 tokens/sec

t=0:   bucket=100, request cost 40 → allow, bucket=60
t=0:   request cost 40 → allow, bucket=20
t=0:   request cost 40 → DENY (need 40, have 20)
t=2:   refilled 20 → bucket=40 → allow if retried
```

Compare to leaky bucket (smoother output, less burst-friendly) and sliding window log (accurate, memory-heavy). For multi-tenant agent gateways, token bucket hits the sweet spot: predictable memory, burst tolerance, easy Redis implementation.

## Atomic Redis implementation with Lua

Race conditions destroy rate limiters. Two concurrent tool calls both read `tokens=5`, both deduct, both pass — you doubled spend. Use a single atomic script:

```lua
-- KEYS[1] = bucket key, ARGV[1]=now_ms, ARGV[2]=cost, ARGV[3]=capacity, ARGV[4]=refill_per_ms
local data = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(data[1])
local last = tonumber(data[2])
local now = tonumber(ARGV[1])
local cost = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])
local refill_per_ms = tonumber(ARGV[4])

if tokens == nil then
  tokens = capacity
  last = now
end

local elapsed = math.max(0, now - last)
tokens = math.min(capacity, tokens + elapsed * refill_per_ms)

if tokens < cost then
  local deficit = cost - tokens
  local retry_ms = math.ceil(deficit / refill_per_ms)
  return {0, tokens, retry_ms}
end

tokens = tokens - cost
redis.call('HMSET', KEYS[1], 'tokens', tokens, 'last_refill', now)
redis.call('PEXPIRE', KEYS[1], 86400000)
return {1, tokens, 0}
```

Wrap in TypeScript at the gateway:

```typescript
type LimitResult =
  | { allowed: true; remaining: number }
  | { allowed: false; remaining: number; retryAfterMs: number };

async function consumeTokenBucket(
  redis: Redis,
  key: string,
  cost: number,
  capacity: number,
  refillPerSecond: number
): Promise<LimitResult> {
  const [allowed, remaining, retryMs] = await redis.eval(
    TOKEN_BUCKET_LUA,
    1,
    key,
    Date.now(),
    cost,
    capacity,
    refillPerSecond / 1000
  ) as [number, number, number];

  if (allowed === 1) {
    return { allowed: true, remaining };
  }
  return { allowed: false, remaining, retryAfterMs: retryMs };
}
```

Key naming: `rl:tenant:{id}:tokens`, `rl:tenant:{id}:requests`, `rl:user:{id}:cost_usd`.

## Multi-dimensional limits for agent loops

One bucket is never enough. Check dimensions in order of cheapness:

```typescript
async function checkAgentLimits(ctx: RequestContext): Promise<LimitResult> {
  const checks = [
    { key: `rl:req:${ctx.tenantId}`, cost: 1, capacity: 300, refill: 5 },
    { key: `rl:tok:${ctx.tenantId}`, cost: ctx.estimatedTokens, capacity: 500_000, refill: 8000 },
    { key: `rl:usd:${ctx.tenantId}`, cost: ctx.estimatedCostMicros, capacity: 50_000_000, refill: 13889 },
  ];

  for (const c of checks) {
    const result = await consumeTokenBucket(redis, c.key, c.cost, c.capacity, c.refill);
    if (!result.allowed) {
      return result;
    }
  }
  return { allowed: true, remaining: 0 };
}
```

Estimate `cost` before the LLM call using historical p90 tokens for `(tool_name, tenant tier)`. Reconcile after the call with a **refund** or **debt** adjustment — otherwise underestimates erode limits and overestimates frustrate users.

For streaming responses, reserve tokens upfront, stream partial deduction every N chunks, release unused reservation on `done`.

## HTTP surface: headers clients need

Return standard headers so SDKs behave:

```
HTTP/1.1 429 Too Many Requests
Retry-After: 3
X-RateLimit-Limit: 500000
X-RateLimit-Remaining: 1240
X-RateLimit-Reset: 1732890123
X-RateLimit-Policy: token-bucket; capacity=500000; refill=8000; scope=tenant
```

Agent SDK retry policy:

```typescript
async function withRateLimitRetry<T>(fn: () => Promise<T>, max = 3): Promise<T> {
  for (let attempt = 0; attempt <= max; attempt++) {
    try {
      return await fn();
    } catch (e) {
      if (!isRateLimitError(e) || attempt === max) throw e;
      const retryAfter = parseRetryAfter(e.headers) ?? backoffMs(attempt);
      await sleep(retryAfter + jitter(0, 250));
    }
  }
  throw new Error("unreachable");
}
```

Never retry tool side effects blindly. Pair rate limit backoff with **idempotency keys** on mutating tools.

## Fairness under noisy neighbors

Within a tenant, one power user can drain the shared bucket. Options:

- **Weighted sub-buckets** per user with minimum guaranteed refill
- **Priority tiers** — enterprise tenants get higher capacity, not just higher refill
- **Concurrency limits** separate from token bucket (max in-flight agent runs)

Token bucket controls average rate; a concurrency semaphore controls simultaneous tool fan-out. You need both when agents parallelize retrieval.

## Observability and tuning

Dashboard per scope:

- `rate_limit_rejected_total{scope, reason}`
- `rate_limit_retry_after_ms_histogram`
- `bucket_remaining_ratio` sampled pre-request
- Correlation with `llm_tokens_total` — if rejections are low but cost spikes, your token estimates are wrong

Load-test with **burst then idle** patterns, not uniform QPS. Tune capacity to absorb p99 burst of a single agent session; tune refill to match your model provider's sustained TPM contract.

Alert when rejection rate exceeds 1% for five minutes for paid tiers — that is a product-visible event, not noise.

## Edge cases that bite

- **Clock skew** across gateway nodes — use Redis TIME or centralized `now_ms` from the script caller consistently
- **Cold start after key expiry** — resetting to full capacity is a gift to bursters; consider starting at `capacity * 0.5`
- **Partial failures** — if LLM call fails after reservation, refund tokens in a `finally` block
- **Webhooks inbound** — rate limit by sender IP and signature key, separate bucket from user-facing API

Token bucket rate limiting will not make agents cheap. It will make cost predictable, bursts survivable, and 429 responses actionable instead of mysterious.

## Global vs local buckets at the edge

Single-region Redis works until you deploy multi-region gateways. Options:

| Approach | Pros | Cons |
|----------|------|------|
| Central Redis (one region) | Exact global count | Cross-region latency, single point of failure |
| Regional buckets at 1/N capacity | Fast, resilient | User can burst N × regional limit via geo routing |
| CRDT / gossip sync | True global burst | Complex, eventual consistency |

Most agent APIs accept **regional buckets** with capacity set to `global_capacity / region_count` plus 10% headroom for uneven traffic. Enterprise contracts that promise hard global caps need central Redis or a dedicated rate-limit service (Envoy RLS, Kong).

At the CDN edge, enforce coarse request limits only — edge nodes lack token-cost context. Fine-grained token buckets belong on the gateway that knows model pricing.

## Coordinating with upstream provider limits

Your bucket is not the only bucket. OpenAI, Anthropic, and Bedrock enforce TPM/RPM independently. Mirror provider limits as nested buckets:

```typescript
const tenantOk = await consumeTokenBucket(redis, `rl:tok:${tenantId}`, estimated, ...);
if (!tenantOk.allowed) return reject429(tenantOk);

const providerOk = await consumeTokenBucket(
  redis,
  `rl:provider:openai:tpm`,
  estimated,
  providerTpmCapacity,
  providerTpmRefill
);
if (!providerOk.allowed) {
  // queue or route to fallback model — don't burn tenant budget retrying doomed calls
  return queueForRetry(providerOk.retryAfterMs);
}
```

When provider limits bind before tenant limits, expose a different error code (`503_provider_capacity`) so clients don't blame the tenant quota. Ops dashboards should show provider bucket saturation separately — that is a vendor or contract problem, not a user abuse problem.

## Graceful degradation tiers

When buckets empty, degrade in stages rather than hard-failing everything:

1. **Disable nonessential tools** (web browse, image gen) — cheap check via feature flag
2. **Switch model tier** — smaller model still answers, higher bucket effective capacity
3. **Queue batch requests** — async webhook when complete
4. **Hard 429** — only when revenue or abuse policy requires it

Document degradation order in customer-facing SLA appendices. Surprises here generate more support tickets than honest throttling.

## Resources

- [Token bucket algorithm (Wikipedia)](https://en.wikipedia.org/wiki/Token_bucket)
- [Redis EVAL atomicity documentation](https://redis.io/docs/interact/programmability/eval-intro/)
- [IETF RateLimit header fields draft](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers)
- [Retry-After header (RFC 9110)](https://httpwg.org/specs/rfc9110.html#field.retry-after)
- [Envoy rate limit service architecture](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/other_features/global_rate_limiting)
