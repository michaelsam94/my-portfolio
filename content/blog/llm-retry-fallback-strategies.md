---
title: "Retries and Fallbacks for LLM Calls"
slug: "llm-retry-fallback-strategies"
description: "Design retry and fallback strategies for LLM APIs: error classification, exponential backoff, model downgrade paths, circuit breakers, and resilience patterns for production LLM apps."
datePublished: "2025-01-05"
dateModified: "2025-01-05"
tags: ["AI", "LLM", "Backend", "Architecture"]
keywords: "LLM retry strategy, LLM fallback model, API error handling LLM, circuit breaker LLM, resilient LLM calls"
faq:
  - q: "Which LLM API errors should I retry?"
    a: "Retry: 429 (rate limit), 500, 502, 503, 504, and timeouts. Do NOT retry: 400 (bad request), 401/403 (auth), 404, and content policy violations — retrying won't fix these and wastes quota. Context length exceeded (400) needs truncation, not retry."
  - q: "What is a good fallback chain for LLM models?"
    a: "Primary model → same-tier alternate provider → cheaper/smaller model on same provider → cached response → graceful error message. Example: GPT-4o → Claude Sonnet → GPT-4o-mini → semantic cache → 'Service temporarily unavailable.' Each step degrades capability, not reliability."
  - q: "When should I use a circuit breaker for LLM providers?"
    a: "Open the circuit after 5 consecutive failures or >50% error rate over 60 seconds. Half-open after 30 seconds to test recovery. Prevents hammering a degraded provider and lets failover routes take traffic. Reset on successful probe request."
---

The LLM call timed out. Your code retried the same 80K-token request three times, burned $0.40, and returned a 500 to the user anyway. Retries without strategy are expensive optimism. Production LLM apps classify errors, backoff intelligently, fall back to alternate models, and know when to stop trying and tell the user something useful.

## Error classification

```python
class LLMErrorType(Enum):
    RETRYABLE = "retryable"       # 429, 5xx, timeout
    TRUNCATE = "truncate"         # context length exceeded
    FATAL = "fatal"               # 401, 403, 400 (non-length)
    CONTENT_POLICY = "content"    # moderation block

def classify_error(error: Exception) -> LLMErrorType:
    if isinstance(error, RateLimitError):
        return LLMErrorType.RETRYABLE
    if isinstance(error, TimeoutError):
        return LLMErrorType.RETRYABLE
    if isinstance(error, APIError):
        if error.status_code in (500, 502, 503, 504):
            return LLMErrorType.RETRYABLE
        if error.status_code == 400 and "context_length" in str(error):
            return LLMErrorType.TRUNCATE
        if error.status_code in (401, 403):
            return LLMErrorType.FATAL
    return LLMErrorType.FATAL
```

Different error types get different handling — not a blanket retry loop.

## Retry with backoff

```python
async def retry_call(
    fn: Callable,
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> Response:
    for attempt in range(max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            error_type = classify_error(e)
            if error_type != LLMErrorType.RETRYABLE or attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), 30)
            logger.warning(f"Retry {attempt + 1}, waiting {delay:.1f}s: {e}")
            await asyncio.sleep(delay)
```

Don't retry content policy violations — you'll get the same block and pay twice.

## Context length recovery

When context exceeds limits, truncate and retry once:

```python
async def call_with_truncation(request: CompletionRequest) -> Response:
    try:
        return await provider.complete(request)
    except ContextLengthError:
        trimmed = truncate_messages(request.messages, target_ratio=0.7)
        return await provider.complete(request.with_messages(trimmed))
```

Truncate oldest tool outputs and summarized history first — never the current user message.

## Fallback chain

```python
FALLBACK_CHAIN = [
    ModelRoute("openai", "gpt-4o"),
    ModelRoute("anthropic", "claude-sonnet-4-20250514"),
    ModelRoute("openai", "gpt-4o-mini"),
]

async def complete_with_fallback(request: CompletionRequest) -> Response:
    errors = []
    for route in FALLBACK_CHAIN:
        try:
            return await route.complete(request)
        except Exception as e:
            if classify_error(e) == LLMErrorType.FATAL:
                raise
            errors.append((route, e))
            logger.warning(f"Fallback: {route} failed, trying next")
    raise AllProvidersFailed(errors)
```

Log which fallback level served the request — persistent L3 fallback means primary is unhealthy.

## Circuit breaker

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30):
        self.failures = 0
        self.state = "closed"  # closed = normal, open = failing, half-open = testing
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0

    async def call(self, fn) -> Response:
        if self.state == "open":
            if time.monotonic() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
            else:
                raise CircuitOpen(self)
        try:
            result = await fn()
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
            return result
        except Exception:
            self.failures += 1
            self.last_failure_time = time.monotonic()
            if self.failures >= self.threshold:
                self.state = "open"
            raise
```

One circuit breaker per provider. When OpenAI's circuit is open, skip directly to Anthropic.

## Idempotency

Retries can duplicate side effects if the LLM call triggers tools:

- Use idempotency keys on mutating tool calls
- Check if a retry is re-executing a partially completed request
- For pure generation (no tools), duplication is wasteful but safe

## User-facing degradation

Final fallback when all models fail:

```python
DEGRADED_RESPONSES = {
    "support_chat": "I'm having trouble right now. Your message has been saved — a team member will follow up shortly.",
    "summarize": None,  # queue for retry, don't show error
}
```

Never show raw API errors to users. Queue async tasks for retry when sync fails.

## Observability

Track:

- Retry count per request (p50, p95)
- Fallback level distribution
- Circuit breaker state changes
- Error type breakdown
- Cost of retries (retries aren't free)

Alert when retry rate exceeds 5% — something systemic is wrong.

## Retry budget pattern

Cap total retry cost per request to prevent runaway bills:

```python
MAX_RETRY_COST_USD = 0.05
cost_so_far = 0.0

for attempt in range(max_retries):
    try:
        return await call_llm(model=current_model)
    except RateLimitError:
        cost_so_far += estimate_cost(current_model, tokens_sent)
        if cost_so_far > MAX_RETRY_COST_USD:
            raise BudgetExceeded()
        await backoff(attempt)
        current_model = fallback_chain[attempt]
```

Separate retry budgets for sync user requests vs async batch jobs — batch can afford more retries spread over hours.

## Provider-specific quirks

| Provider | Retry on | Don't retry on |
|----------|----------|----------------|
| OpenAI | 429, 500, 503 | 400, 401, invalid model |
| Anthropic | 529 overloaded | 400 content policy |
| Azure OpenAI | 429 with retry-after | 404 deployment not found |
| Self-hosted | Connection reset | OOM kill (fix infra) |

Parse `Retry-After` header when present — respect server guidance over exponential backoff formula.

## Graceful degradation chains

Design explicit fallback tiers:

1. Primary model (GPT-4o)
2. Cheaper model same provider (GPT-4o-mini)
3. Alternate provider (Claude)
4. Cached/template response
5. Queue for async retry + user acknowledgment

Log which tier served each request — if tier 3+ exceeds 10%, primary provider relationship needs attention, not more retries.

Pair with [LLM cost control budgets](https://blog.michaelsam94.com/agent-cost-control-budgets/) for org-wide spend caps beyond per-request retry limits.

## Common production mistakes

Teams get retry fallback strategies wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around retry fallback strategies break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Resources

- [OpenAI error codes and handling](https://platform.openai.com/docs/guides/error-codes)
- [Anthropic API errors documentation](https://docs.anthropic.com/en/api/errors)
- [Martin Fowler — Circuit Breaker pattern](https://martinfowler.com/bliki/CircuitBreaker.html)
- [tenacity Python retry library](https://tenacity.readthedocs.io/)
- [Polly .NET resilience library](https://www.pollydocs.org/)
