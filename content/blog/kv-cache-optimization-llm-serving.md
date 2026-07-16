---
title: "KV Cache Optimization for LLM Serving"
slug: "kv-cache-optimization-llm-serving"
description: "KV cache optimization is the biggest lever in LLM serving: how paged attention, quantization, and eviction cut memory and raise throughput."
datePublished: "2026-01-31"
dateModified: "2026-01-31"
tags: ["LLM", "Inference", "Performance", "GPU"]
keywords: "KV cache, LLM serving, paged attention, vLLM, inference optimization, KV cache quantization"
faq:
  - q: "What is the KV cache in LLM inference?"
    a: "The KV cache stores the key and value tensors computed for every token already processed, so the model doesn't recompute attention over the whole sequence at each new token. It's what makes autoregressive generation O(n) per token instead of O(n²). The tradeoff is memory: the cache grows linearly with sequence length and batch size and often dominates GPU memory during serving."
  - q: "How does paged attention reduce KV cache waste?"
    a: "Paged attention stores the KV cache in fixed-size blocks that don't need to be contiguous in memory, the same way an OS pages virtual memory. This eliminates the internal fragmentation you get when you pre-allocate a contiguous buffer for the maximum sequence length, so you can fit far more concurrent requests in the same GPU. vLLM popularized the technique and reports near-zero memory waste versus 60–80% waste in naive allocation."
  - q: "Does KV cache quantization hurt output quality?"
    a: "Usually only slightly. Dropping the KV cache from FP16 to INT8 or FP8 roughly halves cache memory with minimal measurable quality loss on most workloads. Going to INT4 saves more but starts to show up in long-context accuracy, so it needs per-workload evaluation. The keys are generally more sensitive to quantization than the values."
---

If you're serving a large language model and wondering where your GPU memory went, the answer is almost always the KV cache. It's the store of key and value tensors for every token the model has already seen, and it grows linearly with sequence length times batch size — which means at production concurrency it routinely eats more memory than the model weights themselves. Optimizing it is the highest-leverage thing you can do for serving throughput and cost, full stop.

I'll go through why the cache exists, why it's so expensive, and the four techniques that actually move the needle: paged attention, quantization, smarter eviction, and cache reuse. This is the plumbing behind every "how did they serve that so cheaply" story.

## Why the cache exists and why it's expensive

A transformer generating text is autoregressive — it produces one token at a time, and each new token attends to every previous token. Without a cache, generating token 1,000 would recompute the keys and values for tokens 1 through 999 every single step. That's quadratic and unusable. The KV cache stores those tensors once so each new step is linear.

The cost is memory, and the formula is unforgiving. For a given model, cache size scales as:

```
kv_bytes = 2 * n_layers * n_kv_heads * head_dim * seq_len * batch * dtype_bytes
```

The `2` is keys plus values. Plug in a mid-size model at long context and high batch and you're into tens of gigabytes fast. A 70B model can spend more memory on KV cache at serving concurrency than on its own weights. That single fact is why the techniques below exist.

## Paged attention: stop pre-allocating

The naive approach reserves one contiguous buffer per request, sized for the maximum possible sequence length. Most requests never reach that length, so you strand enormous amounts of memory — internal fragmentation of 60–80% is common. You also can't easily share memory across requests.

Paged attention, introduced by [vLLM](https://github.com/vllm-project/vllm), borrows the operating-system trick of virtual memory. The cache lives in fixed-size **blocks** (say 16 tokens each) that need not be contiguous. A per-request block table maps logical positions to physical blocks, exactly like a page table. The wins are concrete:

- Near-zero internal fragmentation — you allocate blocks as the sequence grows, not up front.
- Higher effective batch size in the same memory, which directly raises throughput.
- Copy-on-write sharing of blocks across requests, which makes the next technique cheap.

If you take one thing from this article: use a serving stack with paged attention. Rolling your own contiguous cache in 2026 is leaving most of your GPU on the floor.

## Quantize the cache

The KV cache doesn't have to live in FP16. Storing it in INT8 or FP8 roughly halves its footprint, which either doubles your batch size or lets you serve longer contexts. The quality hit is small for most workloads because attention is fairly tolerant of low-precision keys and values — though in my experience the *keys* are more sensitive than the values, and long-context accuracy is where INT4 starts to wobble.

A rough decision table from what I've measured and what the literature reports:

| Cache precision | Memory vs FP16 | Quality impact | When to use |
| --- | --- | --- | --- |
| FP16 | 1.0x | Baseline | Short contexts, quality-critical |
| FP8 / INT8 | ~0.5x | Negligible on most tasks | Default for high-throughput serving |
| INT4 | ~0.25x | Noticeable at long context | Memory-bound, tolerant workloads |

Always validate on *your* eval set, not a generic benchmark. A summarization workload and a code-completion workload can react very differently to the same quantization, which is the same lesson that shows up whenever you push models onto constrained hardware — see [running local LLMs on device](https://blog.michaelsam94.com/running-local-llms-on-device/) for how brutal the memory math gets when you don't have a datacenter GPU to hide behind.

## Eviction, windows, and attention sinks

Sometimes you can't afford to keep the whole cache, especially for very long sessions. Eviction strategies drop tokens you're unlikely to need:

- **Sliding window** — keep only the most recent N tokens. Simple, but naively dropping the oldest tokens tanks quality.
- **Attention sinks (StreamingLLM)** — keep the first few tokens *and* a recent window. The surprising empirical result is that those initial tokens act as "sinks" that stabilize attention, so keeping them preserves quality far better than a pure sliding window.
- **Importance-based eviction (H2O and friends)** — score tokens by accumulated attention and evict the least important. More compute, better retention.

These matter most for chat with very long histories or streaming transcription. For typical request/response serving, paging plus quantization usually gets you where you need to be before eviction becomes necessary.

## Reuse: the free lunch of prefix caching

The cheapest KV cache is the one you don't recompute. Any tokens shared across requests — a long system prompt, a few-shot preamble, a common document prefix — produce identical keys and values, so their cache blocks can be computed once and reused. With paged attention this is nearly free: shared blocks are simply referenced by multiple requests via the block table.

This is enormous for real workloads. A RAG system that prepends the same 2,000-token instruction block to every query can skip recomputing that prefill entirely after the first request. That's less a KV-cache trick and more a serving-architecture decision, and it dovetails with the broader cost work I broke down in [cutting LLM costs with caching, routing, and batching](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) — prefix reuse is the KV-level mechanism underneath a lot of "prompt caching" features.

## Putting it together

The order of operations I recommend when you're memory-bound:

1. **Adopt paged attention** first. It's the biggest structural win and unlocks the rest.
2. **Turn on prefix/prefix-block reuse** for any shared preamble. Free throughput.
3. **Quantize the cache to FP8/INT8** and validate on your evals. Usually a clean doubling of capacity.
4. **Add eviction or attention sinks** only if you have genuinely unbounded contexts.

The through-line is that KV cache optimization is a memory-management problem masquerading as an ML problem. Treat it like systems engineering — measure fragmentation, measure per-request memory, measure the quality cost of every bit you shave — and you'll consistently serve more requests per GPU than teams that only tune sampling parameters. The model architecture sets the ceiling; the cache strategy decides how close to it you actually get.

## Resources

- [Efficient Memory Management for LLM Serving with PagedAttention (vLLM paper, arXiv)](https://arxiv.org/abs/2309.06180)
- [vLLM — project and documentation](https://github.com/vllm-project/vllm)
- [Efficient Streaming Language Models with Attention Sinks (StreamingLLM, arXiv)](https://arxiv.org/abs/2309.17453)
- [H2O: Heavy-Hitter Oracle for Efficient Generative Inference (arXiv)](https://arxiv.org/abs/2306.14048)
- [NVIDIA TensorRT-LLM documentation](https://nvidia.github.io/TensorRT-LLM/)
- [Hugging Face — KV cache and generation strategies](https://huggingface.co/docs/transformers/en/llm_optims)
