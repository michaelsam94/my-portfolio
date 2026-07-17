---
title: "Prompt Caching in Practice (Anthropic and OpenAI)"
slug: "prompt-caching-in-practice"
description: "Prompt caching cuts LLM cost and latency by reusing prefix computation. How Anthropic and OpenAI caching differ, plus cache breakpoints and gotchas."
datePublished: "2026-05-25"
dateModified: "2026-07-17"
tags: ["LLM", "Performance", "Cost"]
keywords: "prompt caching, Anthropic prompt cache, OpenAI prompt caching, cache breakpoints, LLM cost reduction"
faq:
  - q: "What is prompt caching?"
    a: "Prompt caching stores the model's internal computation (the KV cache) for a stable prefix of your prompt so repeated calls that share that prefix skip recomputing it. On the second and later calls, the cached prefix is billed at a large discount and processed faster, because the expensive prefill step is reused. It's the API-level exposure of the same KV-cache reuse that serving engines do internally."
  - q: "How is Anthropic prompt caching different from OpenAI's?"
    a: "Anthropic requires you to explicitly mark cache breakpoints with a cache_control parameter and charges a small premium to write to the cache, then a steep discount to read it. OpenAI caches automatically for prompts over a length threshold with no code changes and no write premium, but gives you less explicit control over what gets cached. Anthropic trades convenience for precision; OpenAI trades precision for zero effort."
  - q: "What breaks a prompt cache?"
    a: "Any change to the cached prefix invalidates it, because caching matches on an exact token prefix. Putting variable content — timestamps, user IDs, dynamic retrieval results — near the top of the prompt busts the cache on every call. Caches also expire after a short idle window (a few minutes for Anthropic by default), so low-traffic endpoints may rarely get hits."
---

Prompt caching is the cheapest performance win in the LLM API world, and most teams leave it on the table. The idea: when many of your calls share a long, stable prefix — a system prompt, a tool schema, a big reference document — the model can reuse the expensive prefill computation for that prefix instead of redoing it every request. You get the cached portion at a steep discount and a noticeably lower time-to-first-token. On workloads with heavy shared context, I've seen it cut input costs by 50–90% and shave real latency, with a code change measured in minutes.

Under the hood it's the same KV-cache prefix reuse that serving engines do internally, now exposed as an API feature. But Anthropic and OpenAI implement it with different philosophies, and the gotchas are all about prompt *ordering*. Here's what actually matters in production.

## Why it works: prefill is the expensive part

When a model processes your prompt, the costly step is **prefill** — computing keys and values for every input token in one big forward pass before it generates anything. For a 5,000-token system prompt, that prefill dominates the cost and the time-to-first-token, especially when the actual response is short.

Prompt caching stores the KV state for a prefix so that the next call with the *same* prefix skips recomputing it. The critical constraint falls out of that mechanism: caching matches on an **exact token prefix**. Change one token near the top and everything after it is invalidated, because the KV state downstream depended on it. This single fact drives every practical decision below. It's the same KV-cache reuse that serving engines do internally — prompt caching is just that mechanism handed to you through the API.

## Anthropic: explicit breakpoints

Anthropic's approach is opt-in and precise. You mark where the cacheable prefix ends using a `cache_control` breakpoint, and the API caches everything up to that point.

```python
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": LONG_STABLE_INSTRUCTIONS,   # thousands of tokens
            "cache_control": {"type": "ephemeral"},
        }
    ],
    messages=[{"role": "user", "content": user_question}],
)
```

The economics: writing to the cache costs a small premium over normal input tokens, and reading from it is heavily discounted. So caching *loses* money if a prefix is used once and never again, and *wins* big when it's reused many times before the cache expires (a few-minute idle TTL by default, extendable). You can place multiple breakpoints to cache nested layers — say, a stable tool schema, then a per-conversation document — which is powerful but requires you to think about which layers actually repeat.

## OpenAI: automatic, less control

OpenAI's prompt caching is automatic. For prompts above a length threshold, it caches longer prefixes transparently and applies a discount to cached input tokens on subsequent calls — no `cache_control`, no write premium, no code change. Route the same long prefix through repeatedly and you simply start seeing cached-token discounts in your usage.

The tradeoff is control. You don't decide exactly what gets cached or where the breakpoint sits; you rely on the platform's heuristics. In practice this is great for the common case (stable system prompt at the top) and less flexible when you want fine-grained, multi-layer caching.

## The two philosophies side by side

| Aspect | Anthropic | OpenAI |
| --- | --- | --- |
| Activation | Explicit `cache_control` breakpoints | Automatic above a token threshold |
| Write cost | Small premium to write cache | No write premium |
| Read discount | Large (e.g. ~90%) | Meaningful (e.g. ~50%) |
| Control | Fine-grained, multi-breakpoint | Coarse, platform-decided |
| Best for | Complex, layered, high-reuse prompts | "Just make my stable prefix cheaper" |

Neither is strictly better. Anthropic rewards teams willing to engineer their prompt structure; OpenAI rewards teams who want the win with zero effort. If you're multi-provider, you build your prompts to be cache-friendly for both and let each do its thing.

## The one rule: stable stuff first

Everything about using prompt caching well reduces to prompt *ordering*. Because caching keys off an exact prefix, you put the most stable content at the top and the most variable content at the bottom:

1. **System instructions / persona** (rarely change) — top.
2. **Tool and function schemas** (change on deploy) — next.
3. **Large reference documents / few-shot examples** (stable per use case) — next.
4. **Conversation history** (grows, but append-only) — next.
5. **The current user turn and any dynamic data** (changes every call) — bottom.

The classic cache-buster is a timestamp, request ID, or freshly retrieved RAG chunk sitting near the top of the prompt. It invalidates the cache on every single call, and you get zero hits while wondering why your bill didn't move. Move volatile content to the end. This ordering discipline is the whole game — get it wrong and caching does nothing; get it right and it's nearly free money.

## Where it fits in a cost strategy

Prompt caching is one tool among several, and it composes with the others. It's especially potent for:

- **Agents and tool use**, where every turn resends the same big tool schema and system prompt.
- **RAG with a stable instruction block** — cache the instructions and few-shot examples even if the retrieved passages vary (keep those at the bottom).
- **Chat**, where the growing-but-stable history prefix caches well as long as you don't inject volatile tokens up top.

It pairs naturally with the other levers I laid out in [cutting LLM costs with caching, routing, and batching](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) and with response-level [semantic caching for LLM APIs](https://blog.michaelsam94.com/semantic-caching-llm-apis/) — which is a different animal. Semantic caching returns a stored *answer* when a new query is similar enough; prompt caching reuses *prefix computation* for a fresh generation. Use both: semantic caching to skip the model entirely on repeat questions, prompt caching to make the calls that do run cheaper.

## The honest caveats

Prompt caching isn't free of sharp edges. Low-traffic endpoints may never build up hits because the cache expires between requests. Writing large prefixes you don't reuse enough can *increase* cost on Anthropic due to the write premium. And you must monitor cache-hit metrics — both providers report cached-token counts in usage, so watch them; a "cached" prompt with a 5% hit rate is a bug in your prompt ordering, not a caching failure.

Turn it on, put your stable content first, watch the hit rate, and prompt caching quietly becomes one of the best cost-per-quality trades available — no model change, no quality loss, just not paying twice for the same computation.


## Cache hit dashboards worth building

Export daily ratio `cache_read_input_tokens / (cache_read + cache_creation + uncached_input)` per prompt template version. Sudden drops after deploy usually mean someone added `Date.now()` to the system block — not a model regression. Alert when hit rate falls below baseline minus 15 points for 24 hours.

## Gemini and long-TTL workloads

For batch jobs that reuse the same 50-page policy doc hourly, compare Anthropic ephemeral TTL against Gemini context cache with explicit TTL hours. Include storage-minute charges in total cost models — a cheap read rate with expensive storage still loses on low-frequency jobs.

## Resources

- [Anthropic — prompt caching documentation](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI — prompt caching guide](https://platform.openai.com/docs/guides/prompt-caching)
- [OpenAI — prompt caching announcement](https://openai.com/index/api-prompt-caching/)
- [Google Gemini — context caching documentation](https://ai.google.dev/gemini-api/docs/caching)
- [Efficient Memory Management for LLM Serving with PagedAttention (arXiv)](https://arxiv.org/abs/2309.06180)
