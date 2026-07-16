---
title: "Handling LLM Rate Limits Gracefully"
slug: "llm-rate-limits-token-buckets"
description: "Handle LLM API rate limits with token buckets, request queuing, backoff strategies, multi-provider failover, and client patterns that degrade gracefully instead of failing loudly."
datePublished: "2024-12-30"
dateModified: "2024-12-30"
tags: ["AI", "LLM", "Backend", "Architecture"]
keywords: "LLM rate limits, token bucket rate limiting, API rate limit handling, OpenAI rate limit retry, LLM request queue"
faq:
  - q: "What is the difference between RPM and TPM rate limits?"
    a: "RPM (requests per minute) caps how many API calls you make. TPM (tokens per minute) caps total tokens processed across calls. A single long-context request can hit TPM while RPM is fine. Size your token bucket on both dimensions — track input + output tokens per minute separately from request count."
  - q: "Should I retry immediately on 429 errors?"
    a: "Never immediately. Respect the Retry-After header if present; otherwise exponential backoff starting at 1–2 seconds with jitter. Immediate retries amplify rate limit pressure and can get your API key temporarily suspended. Max 3–5 retries before failing or routing to fallback provider."
  - q: "How do I prevent one tenant from consuming all rate limit capacity?"
    a: "Per-tenant token buckets inside your gateway. Each tenant gets a fair share of your org-level quota. When a tenant exhausts their bucket, queue or reject their requests — don't let them starve other tenants by burning shared provider limits."
---

429 Too Many Requests at 2pm on a launch day. Your agent retries instantly — 429 again. And again. Now you're in a retry storm that makes things worse, users see errors, and the provider hasn't reset your quota because you never backed off. Rate limits are a shared resource contract, not an obstacle to brute-force. Handling them gracefully is basic reliability engineering.

## Understanding provider limits

| Limit type | What it measures | Typical trigger |
|------------|-----------------|-----------------|
| RPM | Requests per minute | High QPS, many small calls |
| TPM | Tokens per minute | Few calls with large context |
| RPD | Requests per day | Sustained high volume |
| Concurrent | Simultaneous requests | Parallel agent tool calls |

Check limits for your tier. They change with usage history and tier upgrades.

## Token bucket implementation

```python
import time
import asyncio

class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate          # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1) -> float:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now

            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0  # no wait

            deficit = tokens - self.tokens
            wait = deficit / self.rate
            self.tokens = 0
            return wait

# Org-level: 2M TPM → ~33,333 tokens/sec capacity
tpm_bucket = TokenBucket(rate=33333, capacity=100000)

async def rate_limited_call(request: CompletionRequest) -> Response:
    estimated = request.estimated_tokens
    wait = await tpm_bucket.acquire(estimated)
    if wait > 0:
        await asyncio.sleep(wait)
    return await provider.complete(request)
```

Separate buckets for RPM and TPM. Acquire from both before calling.

## Retry with exponential backoff

```python
async def call_with_retry(fn, max_retries: int = 4) -> Response:
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except RateLimitError as e:
            if attempt == max_retries:
                raise
            retry_after = e.headers.get("Retry-After")
            if retry_after:
                delay = float(retry_after)
            else:
                delay = min(2 ** attempt + random.uniform(0, 1), 60)
            await asyncio.sleep(delay)
```

Always add jitter. Synchronized retries from multiple pods create thundering herd.

## Request queuing

For non-latency-sensitive workloads, queue instead of failing:

```python
class LLMRequestQueue:
    def __init__(self, max_concurrent: int = 20):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.queue = asyncio.Queue(maxsize=1000)

    async def submit(self, request: CompletionRequest) -> Response:
        if self.queue.full():
            raise QueueFull("LLM queue at capacity — try again later")
        future = asyncio.get_event_loop().create_future()
        await self.queue.put((request, future))
        return await future

    async def worker(self):
        while True:
            request, future = await self.queue.get()
            async with self.semaphore:
                try:
                    result = await call_with_retry(lambda: provider.complete(request))
                    future.set_result(result)
                except Exception as e:
                    future.set_exception(e)
```

Return 202 Accepted with a poll URL for async jobs. Return 503 with Retry-After for sync endpoints.

## Multi-provider failover

```python
PROVIDERS = [
    {"name": "openai", "model": "gpt-4o", "priority": 1},
    {"name": "anthropic", "model": "claude-sonnet-4-20250514", "priority": 2},
    {"name": "openai", "model": "gpt-4o-mini", "priority": 3},  # downgrade
]

async def complete_with_fallback(request: CompletionRequest) -> Response:
    for provider in PROVIDERS:
        try:
            return await provider.complete(request.with_model(provider["model"]))
        except RateLimitError:
            logger.warning(f"Rate limited on {provider['name']}, trying next")
            continue
    raise AllProvidersRateLimited()
```

Failover to a different model tier beats failing entirely. Log failover events — frequent failover means you need a higher quota tier.

## Per-tenant fairness

```python
tenant_buckets = defaultdict(lambda: TokenBucket(rate=1000, capacity=5000))

async def tenant_fair_call(tenant_id: str, request: CompletionRequest) -> Response:
    bucket = tenant_buckets[tenant_id]
    wait = await bucket.acquire(request.estimated_tokens)
    if wait > 5.0:  # tenant exceeded fair share
        raise TenantRateLimited(tenant_id, retry_after=wait)
    if wait > 0:
        await asyncio.sleep(wait)
    return await org_rate_limited_call(request)
```

## Client-facing degradation

When limits are hit, degrade gracefully:

```python
DEGRADATION_LADDER = [
    ("full", "gpt-4o", "full_rag"),
    ("reduced", "gpt-4o-mini", "top_3_chunks"),
    ("cached", None, "semantic_cache_only"),
    ("static", None, "canned_response"),
]
```

Step down the ladder as pressure increases. Users get a simpler answer instead of an error.

## Monitoring

Track:

- 429 rate by provider and model
- Retry count distribution
- Queue depth and wait time
- Token bucket utilization (% of capacity)
- Failover frequency

Alert when 429 rate exceeds 1% of requests — you're under-provisioned on quota.

## Token bucket per tenant

Separate buckets for input and output tokens — output-heavy summarization shouldn't block input-light classification. Burst allowance handles legitimate spikes; sustained overage returns 429.

## Common production mistakes

Teams get rate limits token buckets wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around rate limits token buckets break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When rate limits token buckets misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [OpenAI rate limits documentation](https://platform.openai.com/docs/guides/rate-limits)
- [Anthropic rate limits](https://docs.anthropic.com/en/api/rate-limits)
- [Token bucket algorithm (Wikipedia)](https://en.wikipedia.org/wiki/Token_bucket)
- [AWS exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [aio-limiter async rate limiting library](https://github.com/mjpiotrowski/aio-limiter)
