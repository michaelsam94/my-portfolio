---
title: "PagedAttention and KV Memory"
slug: "llm-serving-paged-attention"
description: "Understand PagedAttention and KV cache memory management in LLM serving: fragmentation, block tables, vLLM architecture, prefix caching, and throughput implications."
datePublished: "2025-03-21"
dateModified: "2026-07-17"
tags:
keywords: "PagedAttention, KV cache memory, vLLM PagedAttention, LLM inference memory, prefix caching LLM, KV cache fragmentation"
faq:
  - q: "What problem does PagedAttention solve?"
    a: "PagedAttention fixes GPU memory fragmentation in the KV cache during LLM inference. Traditional serving pre-allocates contiguous GPU memory per request for maximum sequence length, wasting memory on short sequences and preventing batching when memory is fragmented. PagedAttention stores KV cache in non-contiguous fixed-size blocks, allocated on demand like OS virtual memory — higher utilization and larger batches."
  - q: "How much memory does the KV cache use during inference?"
    a: "KV cache size scales with batch_size × num_layers × num_heads × head_dim × sequence_length × 2 (K and V) × dtype_bytes. For Llama-3-8B at 4096 tokens, fp16, a single sequence uses roughly 1–2 GB of KV cache — often exceeding model weights for long contexts. PagedAttention does not reduce theoretical KV size but eliminates wasted reserved slots, fitting more concurrent sequences."
  - q: "What is prefix caching and how does it relate to PagedAttention?"
    a: "Prefix caching reuses KV blocks for identical prompt prefixes across requests — system prompts, RAG document headers, few-shot examples. vLLM hashes block contents and reference-counts shared blocks. Combined with PagedAttention's block addressing, multiple requests share physical GPU memory for common prefixes, cutting prefill compute and memory for repeated context."
---
We sized GPU memory for Llama-70B by model weights alone and wondered why inference OOM'd at batch size 4 with 512-token prompts. The KV cache — key and value tensors stored for every layer at every generated token — consumed more VRAM than the weights for long contexts, and our server's contiguous pre-allocation reserved max-length slots for requests that stopped at 200 tokens. PagedAttention, introduced in vLLM, treats KV cache like operating system paging: fixed blocks, non-contiguous layout, on-demand allocation. That design choice is why vLLM batches outperform naive HuggingFace generate loops by orders of magnitude.

## What the KV cache stores

During autoregressive decoding, each layer computes attention over prior tokens. Storing past K and V avoids recomputing them:

```
Token 1 → Layer L → K₁, V₁  ─┐
Token 2 → Layer L → K₂, V₂  ─┼──→ Attention uses all prior K, V
Token 3 → Layer L → K₃, V₃  ─┘
```

Memory per layer per token (simplified):

```
kv_bytes ≈ 2 × num_heads × head_dim × dtype_bytes
```

Multiply by `num_layers × seq_len × batch_size` for total KV footprint.

## The fragmentation problem

Naive serving allocates a contiguous buffer per request sized for `max_model_len`:

```
Request A: [====used====|........reserved........|]  max_len=8192, actual=512
Request B: [==used==|..........................|]  max_len=8192, actual=256
```

Reserved but unused memory cannot serve other requests. Long-running batches fragment GPU memory into unusable holes — like malloc fragmentation, but at GB scale on expensive H100s.

## PagedAttention: block-based KV storage

Inspired by OS virtual memory:

1. Divide KV cache into **fixed-size blocks** (e.g., 16 tokens per block)
2. Maintain a **block table** per sequence mapping logical block index → physical block ID
3. **Allocate** physical blocks as sequence grows
4. **Free** blocks when sequence completes

```
Logical seq blocks:  [0][1][2][3]
Block table:         phys 7, phys 2, phys 15, phys 4  (non-contiguous)
Physical GPU blocks: [0][1][2]...[N] shared pool
```

Attention kernels index KV via block table — custom CUDA kernels in vLLM make this efficient.

Result: memory utilization near theoretical minimum; batch size limited by actual token count, not max-length reservations.

## vLLM architecture sketch

```
Client requests
      ↓
Scheduler (continuous batching)
      ↓
Block manager (allocate/free KV blocks)
      ↓
Model executor (PagedAttention kernels)
      ↓
Detokenized output stream
```

**Continuous batching** — new requests join running batch between decode steps; finished sequences release blocks immediately. No waiting for whole batch to complete.

## Prefix caching

When many requests share an identical prefix (system prompt + RAG context):

```python
# Requests share prefix blocks via hash
prefix = "System: You are a helpful assistant.\n\nDocument: ..."
# Block hash matches → reuse KV blocks, skip prefill for prefix tokens
```

vLLM `--enable-prefix-caching` tracks block content hashes. Reference counting prevents premature free while any sequence uses a block.

Impact on RAG workloads:

- First request pays full prefill
- Subsequent requests with same document chunks reuse KV — lower latency and memory

Prefix must be **byte-identical** — whitespace and tokenization matter.

## Sizing GPU memory for production

Estimate before provisioning:

```python
def kv_cache_gb(
    n_layers: int,
    n_heads: int,
    head_dim: int,
    seq_len: int,
    batch: int,
    bytes_per_elem: int = 2,  # fp16
) -> float:
    kv_per_token = 2 * n_layers * n_heads * head_dim * bytes_per_elem
    return kv_per_token * seq_len * batch / 1e9

# Llama-3-8B-ish: 32 layers, 32 heads, 128 dim, 4096 seq, batch 8
print(kv_cache_gb(32, 32, 128, 4096, 8))  # ~17 GB
```

Add model weights, activation workspace, and CUDA overhead. PagedAttention improves **utilization** of allocated memory — you still need enough total VRAM.

## Tuning parameters

| Parameter | Effect |
|-----------|--------|
| `gpu_memory_utilization` | Fraction of VRAM vLLM claims (0.9 default) |
| `max_model_len` | Caps sequence length — lowers block pool sizing |
| `block_size` | Tokens per block — affects fragmentation vs overhead |
| `max_num_seqs` | Concurrent sequence limit |

Lower `max_model_len` if OOM persists — product decision, not just ops.

## Alternatives and ecosystem

- **TensorRT-LLM** — KV cache management and inflight batching
- **TGI (Hugging Face)** — continuous batching, paged KV in recent versions
- **FlashAttention** — efficient attention computation, complementary to PagedAttention memory layout
- **Quantized KV (INT8/FP8)** — reduces bytes per token; vLLM and others add support

PagedAttention addresses layout; quantization addresses per-token size — combine both for long context at scale.

## Operational metrics

Monitor:

- `gpu_cache_usage_perc` — block pool utilization
- `num_preemption` — sequences swapped when memory pressure
- `prefix_cache_hit_rate` — RAG optimization effectiveness
- `avg_sequence_length` vs `max_model_len` — sizing drift

Alert when cache usage sustained above 95% — batch latency spikes follow.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get serving paged attention wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving paged attention break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When serving paged attention misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [vLLM paper — PagedAttention (Kwon et al.)](https://arxiv.org/abs/2309.06180)
- [vLLM documentation](https://docs.vllm.ai/)
- [FlashAttention paper](https://arxiv.org/abs/2205.14135)
- [TensorRT-LLM KV cache management](https://nvidia.github.io/TensorRT-LLM/)
- [Hugging Face TGI architecture](https://github.com/huggingface/text-generation-inference)
