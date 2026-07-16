---
title: "Cutting LLM Costs: Caching, Routing, and Batching"
slug: "cutting-llm-costs-caching-routing-batching"
description: "Practical LLM cost optimization: prompt caching, model routing, and request batching to cut token spend 40-80% without hurting quality — with real numbers and code."
datePublished: "2026-02-03"
dateModified: "2026-02-03"
tags: ["LLM", "Cost Optimization", "Architecture", "Backend"]
keywords: "LLM cost optimization, prompt caching, model routing, LLM batching, reduce LLM costs, token usage, inference cost"
faq:
  - q: "What is the fastest way to reduce LLM costs?"
    a: "Turn on prompt caching first. If your prompts share a large fixed prefix (system instructions, tools, few-shot examples), caching that prefix can cut input token cost by 50-90% with a one-line change and no quality loss."
  - q: "Does routing to cheaper models hurt quality?"
    a: "Not if you route by task difficulty. Most production traffic is easy classification or extraction that a small model handles fine; reserve the frontier model for the 10-20% of genuinely hard requests. Measure with evals before and after."
  - q: "When should I batch LLM requests instead of streaming them?"
    a: "Batch when latency does not matter to the user — offline enrichment, nightly summarization, backfills, evals. Providers like OpenAI and Anthropic offer batch APIs at roughly 50% off for these asynchronous jobs."
---

Most teams discover their LLM bill the same way I did: a Slack message from finance asking why the "AI feature" costs more than the database cluster. The good news is that LLM spend is one of the most compressible line items in a modern stack. Three levers — caching, routing, and batching — routinely take 40-80% off a bill without users noticing anything except, sometimes, faster responses.

LLM cost optimization is not one trick; it's a stack of them applied in the right order. Start with caching because it's nearly free to enable, then add routing to stop overpaying for easy work, then batch everything that isn't user-facing. Here's how each works and what to watch for.

## Start with the token math

Every optimization decision comes back to one invoice: you pay per input token and (more, usually 3-5x more) per output token. Before touching code, pull a week of traffic and bucket it. I usually find the distribution is lopsided — a handful of endpoints generate most of the spend, and it's almost always input tokens dominating because of fat system prompts and retrieved context.

A quick audit table for one service I worked on looked like this:

| Endpoint | Share of calls | Share of cost | Main driver |
|---|---|---|---|
| `/classify` | 61% | 12% | short prompts, small model |
| `/summarize-doc` | 9% | 47% | huge input context |
| `/chat` | 28% | 38% | repeated system prompt + history |
| `/extract` | 2% | 3% | structured output |

The `/summarize-doc` and `/chat` rows are where the money is, and both are cache- and batch-friendly. Do the audit; intuition about where the cost lives is usually wrong.

## Prompt caching: the cheapest win

If your requests repeat a large fixed prefix — a system prompt, tool definitions, a policy document, few-shot examples — you're paying to re-process identical tokens on every call. Prompt caching stores the model's internal state for that prefix so subsequent calls skip it.

With Anthropic's API you mark the stable section with a cache breakpoint:

```python
import anthropic

client = anthropic.Anthropic()
resp = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT_AND_POLICY,  # stable, reused
            "cache_control": {"type": "ephemeral"},
        }
    ],
    messages=[{"role": "user", "content": user_turn}],  # varies per call
)
```

OpenAI's prompt caching is automatic for prefixes over ~1024 tokens — you just need to keep the shared content at the *front* of the prompt and the variable content at the end. That ordering detail matters: caching keys off the prefix, so a single changed token near the top invalidates everything after it. Put timestamps, request IDs, and user input last.

Cached input tokens typically bill at 10-25% of the normal rate. For the `/chat` endpoint above, moving the 3,000-token system prompt behind a cache breakpoint cut its cost by roughly 55% on its own. The cache has a short TTL (minutes), so it helps most on bursty, conversational traffic.

## Semantic caching for repeated questions

Prefix caching handles identical prefixes; it does nothing for two users asking the same question in different words. That's where a [semantic cache](https://blog.michaelsam94.com/semantic-caching-llm-apis/) helps: embed the incoming query, look for a near-duplicate in a vector store, and return the stored answer if similarity clears a threshold.

The trap is the threshold. Set it too loose and you serve "close enough" answers that are subtly wrong; too tight and you never hit. I gate semantic cache hits behind a similarity floor (cosine > 0.93 in one FAQ bot) *and* only cache responses for read-only, non-personalized queries. Anything that depends on the specific user or live data never touches the cache.

## Routing: stop sending easy work to the expensive model

The single biggest structural saving is model routing — matching each request to the cheapest model that can handle it. Frontier models are wonderful and wasteful; a lot of production traffic is classification, extraction, or short factual answers that a small model does just as well for a tenth of the price.

A pragmatic router has two tiers plus an escape hatch:

```python
def route(request) -> str:
    if request.task in ("classify", "extract", "tag"):
        return "gpt-4o-mini"          # cheap tier for structured/simple work
    if request.token_estimate > 30_000 or request.needs_reasoning:
        return "claude-sonnet-4-5"     # capable tier for hard/long work
    return "gpt-4o-mini"

def answer(request):
    model = route(request)
    result = call(model, request)
    if model != "claude-sonnet-4-5" and low_confidence(result):
        result = call("claude-sonnet-4-5", request)  # escalate on failure
    return result
```

The escalation path is what makes this safe. Route optimistically to the cheap model, detect low-quality or low-confidence outputs (short answers, refusals, failed schema validation), and retry on the strong model only then. In practice the escape hatch fires on 10-20% of traffic, so you keep near-frontier quality while paying cheap-tier prices for most calls. Validate the whole thing against an eval set — see [measuring agent quality with evals](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/) — so a routing change doesn't quietly regress accuracy.

## Batching: half price for anything that can wait

Real-time chat needs low latency, but a huge amount of LLM work is offline: enriching a catalog, summarizing yesterday's tickets, generating embeddings for a backfill, running an eval suite. For those, provider batch APIs cost about half of synchronous calls in exchange for a delivery window (often up to 24 hours).

```python
# OpenAI Batch API: submit a JSONL of requests, poll for completion
batch = client.batches.create(
    input_file_id=uploaded_file.id,
    endpoint="/v1/chat/completions",
    completion_window="24h",
)
```

Two rules keep batch jobs sane: make each request idempotent with a stable `custom_id` so you can retry without duplicating work, and design the pipeline to tolerate partial failures — a 50k-row batch will have a few rows that error, and you don't want to reprocess all 50k to recover them.

If you also control your own inference (self-hosted vLLM or similar), continuous batching at the serving layer packs concurrent requests onto the GPU and can lift throughput several times over naive one-at-a-time serving. That's a different mechanism than the provider batch API but the same principle: amortize fixed cost across more work.

## Put them together, then measure

The order matters. Enable prefix caching (near-zero risk), add a semantic cache for read-only queries, introduce two-tier routing with an escalation fallback, and push all non-interactive work to batch. Layered, these compound: caching shrinks the input tokens, routing shrinks the per-token price, and batching halves whatever's left of the offline load.

Then instrument it. Track cost per request, cache hit rate, escalation rate, and — critically — quality on a fixed eval set, so you can prove a cost change didn't cost you accuracy. Cheaper output that's wrong isn't a saving; it's a refund waiting to happen. If you want a broader tour of the systems side of running models in production, my writeup on [architecting real-time platforms](https://michaelsam94.com/) covers adjacent territory.

## Resources

- [OpenAI — Prompt caching](https://platform.openai.com/docs/guides/prompt-caching)
- [OpenAI — Batch API](https://platform.openai.com/docs/guides/batch)
- [Anthropic — Prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Anthropic — Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/batch-processing)
- [vLLM documentation (continuous batching)](https://docs.vllm.ai/)
- [Google Cloud — Vertex AI batch predictions](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/batch-prediction)
