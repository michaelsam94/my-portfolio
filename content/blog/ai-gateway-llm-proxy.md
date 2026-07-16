---
title: "Building an AI Gateway for LLM Traffic"
slug: "ai-gateway-llm-proxy"
description: "Why an AI gateway belongs in front of your LLM traffic: centralized keys, rate limiting, model fallback, cost tracking, and how to build one that scales."
datePublished: "2026-06-02"
dateModified: "2026-06-02"
tags: ["LLM", "Infrastructure", "Architecture", "Cost"]
keywords: "AI gateway, LLM proxy, rate limiting LLM, model fallback, API key management, LLM observability gateway"
faq:
  - q: "What is an AI gateway?"
    a: "An AI gateway is a proxy that sits between your applications and one or more LLM providers, centralizing concerns that would otherwise be duplicated in every service: API key management, rate limiting, retries and fallback, caching, cost accounting, and observability. Applications call the gateway with a unified API instead of talking to providers directly. It is the LLM equivalent of an API gateway, adapted for the quirks of model traffic."
  - q: "Why not just call the LLM provider directly?"
    a: "Direct calls scatter API keys, retry logic, and cost tracking across every service, and give you no central place to enforce limits, switch providers, or observe spend. When a provider has an outage or you want to swap models, you are editing many codebases instead of one config. A gateway concentrates these cross-cutting concerns so they are consistent and changeable in one place."
  - q: "Does an AI gateway add too much latency?"
    a: "A well-built gateway adds single-digit to low-double-digit milliseconds, which is negligible next to multi-second model generation. The proxy hop is dwarfed by inference time, and features like semantic caching and smart routing usually reduce end-to-end latency and cost far more than the hop adds. The risk is not latency but making the gateway a single point of failure, which you mitigate with redundancy."
---

Once more than one service in your company calls an LLM, you have a distributed mess waiting to happen: API keys copied into three repos, each team's own half-baked retry logic, no shared view of spend, and no single lever to switch providers when one has a bad day. An AI gateway fixes this by sitting between your apps and the model providers as a proxy that centralizes keys, rate limiting, fallback, caching, cost tracking, and observability behind one unified API. It's the API gateway pattern, retrofitted for the specific weirdness of LLM traffic.

I've seen the "we'll just call OpenAI directly" approach age badly every time the company grows past one team. The gateway is boring infrastructure, and that's the compliment — it's the layer that makes everything above it consistent.

## What actually belongs in the gateway

The temptation is to make the gateway do everything. Resist it, but these responsibilities genuinely earn their place because they're cross-cutting — every caller needs them and duplicating them is waste:

- **Credential management.** Provider keys live in the gateway, not in a dozen services. Rotating a key is one change, and a leaked app never leaks a provider key.
- **Unified API.** Apps speak one schema; the gateway translates to OpenAI, Anthropic, Google, or a self-hosted model. Swapping a model becomes config, not a code change.
- **Rate limiting and quotas.** Per-team, per-key, per-model limits enforced centrally so one runaway job can't exhaust a shared quota. This is the same discipline as general [rate limiting and backpressure](https://blog.michaelsam94.com/rate-limiting-backpressure/), applied to token budgets instead of request counts.
- **Retries and fallback.** Transient 429s and 5xxs retried with backoff; hard provider outages failed over to an alternate model.
- **Caching.** Exact and semantic caching to avoid paying for repeated work.
- **Cost accounting and observability.** Every request logged with tokens, cost, latency, model, and caller, so spend is attributable.

## Model fallback is the killer feature

The single reason gateways justify themselves in production is resilience. Providers have outages, rate-limit spikes, and regional degradations, and if your app calls one provider directly, its bad day is your bad day. A gateway lets you define a fallback chain and fail over transparently.

```yaml
routes:
  - name: default-chat
    primary: openai/gpt-4o
    fallbacks:
      - anthropic/claude-sonnet
      - google/gemini-pro
    retry:
      attempts: 2
      backoff_ms: 500
    on_error: [429, 500, 502, 503, 529]
```

When the primary returns a 529 or times out, the gateway retries, then rolls to the next model — the calling app never knows. This is closely related to, but distinct from, quality-based routing (send cheap queries to a small model, hard ones to a frontier model), which I treat separately in [building an LLM router](https://blog.michaelsam94.com/building-an-llm-router/). Fallback is about *availability*; routing is about *fit*. A mature gateway does both, but keep the concepts separate or your config becomes unreadable.

## Cost visibility you can't get any other way

You cannot control spend you can't see, and LLM spend is uniquely opaque because it's priced in tokens that vary per request. When every service calls providers directly, your only cost signal is the monthly invoice — too late and unattributable. Route through a gateway and every request becomes a data point: which team, which model, input/output tokens, cache hit or miss, dollar cost.

That data is what makes optimization possible. You discover that one feature is 60% of spend, that a prompt could be trimmed by half, or that a cache would eliminate a chunk of traffic. Semantic caching in particular — returning a stored answer for a semantically-equivalent query — lives naturally at the gateway and can cut cost dramatically; I dig into it in [semantic caching for LLM APIs](https://blog.michaelsam94.com/semantic-caching-llm-apis/). Without the gateway's telemetry, you'd never know which queries repeat.

## A minimal proxy handler

Under the hood, the request path is not complicated. The gateway resolves the route, checks limits and cache, calls the provider with retry/fallback, records usage, and returns:

```python
async def handle(req: ChatRequest, caller: Caller) -> ChatResponse:
    route = routes.resolve(req.model)
    if not limiter.allow(caller, route):
        raise RateLimited(retry_after=limiter.reset(caller))

    if hit := cache.get(req):                     # exact or semantic
        meter.record(caller, route, cached=True)
        return hit

    for model in [route.primary, *route.fallbacks]:
        try:
            resp = await providers.call(model, req, timeout=route.timeout)
            meter.record(caller, model, usage=resp.usage)
            cache.set(req, resp)
            return resp
        except (RateLimited, ProviderError):
            continue                              # fall through to next model
    raise AllProvidersFailed()
```

The important properties: limits are checked before spending money, the cache short-circuits before any provider call, fallback is a simple loop, and *every* path records usage. Streaming responses complicate this — you meter tokens as they flow rather than at the end — but the skeleton holds.

## The failure modes to design against

A gateway concentrates power, and concentrated power concentrates risk. The two I plan for explicitly:

**Single point of failure.** Everything now flows through the gateway, so if it's down, every LLM feature is down. Run it stateless and horizontally scaled behind a load balancer, keep its own dependencies (the rate-limit store, the cache) redundant, and make sure a gateway failure degrades gracefully rather than hanging callers. Ironically, the thing you built for resilience becomes your biggest fragility if you deploy a single instance.

**Latency and buffering on streams.** For streaming responses, the gateway must pass chunks through immediately, not buffer the whole response — otherwise you destroy time-to-first-token and the responsive feel users expect. Proxy the stream, don't collect it.

There's also the observability payoff worth wiring in from day one: emit traces in a standard format so LLM calls show up alongside the rest of your system, so a single request can be followed from app through gateway to provider.

## Build or buy?

You don't always have to build this. Mature open-source options (LiteLLM, Portkey's gateway, Kong's AI plugins, Cloudflare's AI Gateway) cover the common cases, and for most teams adopting one beats hand-rolling. I'd build only when you have unusual routing logic, strict data-residency needs, or want the gateway tightly fused with internal auth and billing. Either way, the architectural decision — *route LLM traffic through a central proxy* — is the win. The gateway turns a sprawl of direct provider calls into one governed, observable, swappable seam, and that seam is where cost control, resilience, and consistency all live.

## Resources

- [LiteLLM — LLM gateway and proxy](https://github.com/BerriAI/litellm)
- [Cloudflare AI Gateway documentation](https://developers.cloudflare.com/ai-gateway/)
- [Kong — AI Gateway plugins](https://docs.konghq.com/hub/kong-inc/ai-proxy/)
- [OpenTelemetry — semantic conventions for GenAI](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Portkey — open-source AI gateway](https://github.com/Portkey-AI/gateway)
