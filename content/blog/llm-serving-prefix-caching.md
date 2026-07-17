---
title: "Prefix Caching for Shared Prompts"
slug: "llm-serving-prefix-caching"
description: "How prefix caching reuses KV states across requests with identical prompt prefixes, cutting latency and GPU memory churn in production LLM serving."
datePublished: "2025-03-01"
dateModified: "2026-07-17"
tags:
keywords: "prefix caching LLM, KV cache reuse, vLLM prefix caching, shared system prompt, prompt caching Anthropic, LLM serving optimization"
faq:
  - q: "When does prefix caching actually help?"
    a: "Prefix caching pays off when many requests share an identical leading token sequence — system prompts, RAG context blocks, tool schemas, or multi-turn histories where only the last user message changes. If every request has a unique prefix, there is nothing to reuse and caching adds overhead without benefit."
  - q: "Does prefix caching change model output?"
    a: "No. Prefix caching stores the key-value tensors computed during the prefill phase for a shared prefix. The model still runs the same forward pass for new tokens. Mathematically identical inputs produce identical outputs; you are skipping redundant computation, not approximating."
  - q: "How do I measure whether prefix caching is working?"
    a: "Compare prefill latency and time-to-first-token (TTFT) for requests with and without a shared prefix. Good implementations expose cache hit rate, cached token count, and memory used by the prefix cache. A hit rate above 60% on production traffic usually means your prompt structure is cache-friendly."
---
Your support team ships a RAG assistant where every request starts with the same 3,000-token system prompt, tool definitions, and retrieved document chunk. Without prefix caching, the GPU recomputes attention over those 3,000 tokens on every single call — even when the only thing that changed is the user's latest question. Prefix caching fixes this by storing the KV (key-value) tensors from the prefill pass and reusing them when a new request shares the same leading tokens.

The win is straightforward: less compute, lower latency on time-to-first-token, and better GPU utilization when traffic clusters around shared context.

## How prefix caching works

During inference, LLMs run in two phases:

1. **Prefill:** process the entire input prompt in parallel, building KV cache entries for each token.
2. **Decode:** generate one token at a time, appending to the KV cache.

Prefix caching recognizes that the KV tensors for tokens 1..N depend only on tokens 1..N — not on anything after. If request B starts with the same token sequence as request A, you can copy A's KV cache for that prefix and skip recomputing it.

```
Request A: [system][tools][doc chunk][user: "reset password"]
Request B: [system][tools][doc chunk][user: "billing question"]
           └──── cached prefix ────┘  └─ new tokens ─┘
```

Most serving engines implement this with a hash tree or radix tree keyed by token IDs. vLLM's `AutomaticPrefixCaching` and similar features in TensorRT-LLM track block-level hashes so partial prefix matches still get partial reuse.

## What makes a prefix cache-friendly

Not every workload benefits equally. Structure your prompts so the static portion comes first and the dynamic portion comes last:

```python
# Cache-friendly: static first, dynamic last
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},      # identical
    {"role": "user", "content": f"Context:\n{docs}"},  # identical per session
    {"role": "user", "content": user_question},         # varies
]

# Cache-unfriendly: dynamic content before static
messages = [
    {"role": "user", "content": f"Today is {date}. {user_question}"},
    {"role": "system", "content": SYSTEM_PROMPT},
]
```

A single differing token at position 50 invalidates the cache from that point forward. Put timestamps, request IDs, and user-specific metadata after the shared block, not inside it.

## Enabling prefix caching in vLLM

vLLM exposes prefix caching as a startup flag:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --enable-prefix-caching \
  --max-model-len 8192
```

When enabled, vLLM hashes each cache block (typically 16 tokens). On a new request, it walks the hash chain until a mismatch, then prefill only the suffix. Monitor these metrics in production:

- `prefix_cache_hit_rate` — percentage of prefill tokens served from cache
- `gpu_cache_usage_perc` — how full the KV cache pool is
- TTFT p50/p99 with and without caching enabled

On a RAG workload where 80% of requests share a 2,000-token document context, we typically see TTFT drop from 800ms to under 200ms on an A100.

## Provider-level prompt caching

Managed APIs also offer prefix caching with different semantics:

- **Anthropic prompt caching** lets you mark cache breakpoints in the prompt. Cached blocks persist for five minutes (or longer on some tiers) and billing reflects reduced input token costs for cache reads.
- **OpenAI** has introduced cached input pricing for repeated prefixes on supported models.

The API pattern looks like:

```python
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    system=[
        {"type": "text", "text": LONG_SYSTEM_PROMPT,
         "cache_control": {"type": "ephemeral"}},
    ],
    messages=[{"role": "user", "content": user_msg}],
)
```

Provider caching and self-hosted prefix caching solve the same problem at different layers. If you control the serving stack, self-hosted gives you more flexibility. If you use an API, mark your static blocks explicitly.

## Memory and eviction trade-offs

Prefix caching consumes GPU memory. Each cached prefix holds KV tensors proportional to `num_layers × num_heads × head_dim × prefix_length`. With high concurrency and diverse prefixes, the cache can evict entries before they get reused.

Tuning knobs:

- **Block size:** smaller blocks mean finer-grained reuse but more hash lookups.
- **Cache capacity:** cap the percentage of GPU memory reserved for prefix cache vs. active sequences.
- **TTL / LRU eviction:** drop prefixes that haven't been hit recently.

If your cache hit rate stays below 20%, you are paying memory overhead for little gain. Either restructure prompts or disable caching and reclaim the memory for batching more concurrent requests.

## Designing for cache hits in multi-tenant apps

In SaaS products serving many customers, isolate per-tenant dynamic content from shared instructions:

1. Shared system prompt and tool schemas (global cache).
2. Per-tenant configuration injected as a separate cached block.
3. Per-request user message (never cached).

For multi-turn chat, append new messages rather than rewriting history. Rewriting the messages array with a fresh timestamp on every turn breaks the prefix chain even if the conversation content is identical.

## Resources

- [vLLM Automatic Prefix Caching documentation](https://docs.vllm.ai/en/latest/automatic_prefix_caching/apc.html)
- [Anthropic prompt caching guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [Attention Is All You Need (original transformer paper)](https://arxiv.org/abs/1706.03762)
- [PagedAttention paper (vLLM foundation)](https://arxiv.org/abs/2309.06180)
- [TensorRT-LLM KV cache reuse](https://nvidia.github.io/TensorRT-LLM/advanced/kv-cache-reuse.html)

## Production notes for LLM stacks

When `llm-serving-prefix-caching` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `prefix caching for shared prompts` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
