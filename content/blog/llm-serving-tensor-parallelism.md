---
title: "Tensor Parallelism for Large Models"
slug: "llm-serving-tensor-parallelism"
description: "Split large LLM weights across multiple GPUs with tensor parallelism: how all-reduce communication works, when to combine with pipeline parallelism, and tuning for production serving."
datePublished: "2025-03-13"
dateModified: "2025-03-13"
tags: ["AI", "LLM", "Distributed Inference", "GPU"]
keywords: "tensor parallelism LLM, TP inference, Megatron-LM tensor parallel, vLLM tensor parallel size, multi-GPU LLM serving, all-reduce inference"
faq:
  - q: "When should I use tensor parallelism instead of loading the model on one GPU?"
    a: "Use tensor parallelism when a single GPU cannot hold the model weights plus KV cache at your target context length and batch size. A 70B model in FP16 needs ~140 GB — that requires TP=2 on 80 GB A100s or TP=4 on 40 GB cards. If the model fits on one GPU, TP adds communication overhead without benefit."
  - q: "What is the difference between tensor parallelism and pipeline parallelism?"
    a: "Tensor parallelism splits individual weight matrices across GPUs within the same layer, requiring all-reduce after each layer. Pipeline parallelism assigns entire layers to different GPUs, creating a sequential pipeline. TP reduces per-GPU memory with moderate communication; PP reduces memory further but introduces pipeline bubbles unless batch size is large."
  - q: "How does tensor parallel size affect latency?"
    a: "Small TP sizes (2–4) on NVLink-connected GPUs add 5–15% latency overhead from all-reduce. TP=8 across PCIe-connected GPUs can add 30%+ overhead and may not improve throughput. Always prefer NVLink or NVSwitch topology for TP beyond 2."
---

A 405B parameter model does not fit on any single GPU. Even 70B in FP16 exceeds one A100 80GB once you account for KV cache, activation buffers, and batching headroom. Tensor parallelism solves this by splitting each weight matrix across multiple GPUs so no single device holds the full model.

The trade-off is communication: every layer's forward pass requires an all-reduce collective to synchronize partial results across GPUs. Get the parallel degree wrong and you spend more time moving tensors than computing them.

## How tensor parallelism splits weights

In a transformer layer, the main weight matrices are:

- **QKV projection:** `[hidden_dim, 3 × hidden_dim]`
- **Output projection:** `[hidden_dim, hidden_dim]`
- **FFN up/down:** `[hidden_dim, ffn_dim]` and `[ffn_dim, hidden_dim]`

Tensor parallelism splits these along the inner dimension. With TP=2 on the QKV projection:

```
GPU 0: W_qkv[:, :half]  → partial output_0
GPU 1: W_qkv[:, half:]  → partial output_1
All-reduce → full QKV output
```

Each GPU computes its shard independently, then an all-reduce sums the partial results. Memory per GPU drops proportionally to TP size.

Megatron-LM formalized this approach for training, and inference engines (vLLM, TensorRT-LLM, DeepSpeed-Inference) adopted the same sharding strategy.

## Configuring tensor parallelism in vLLM

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-70B-Instruct \
  --tensor-parallel-size 4 \
  --dtype bfloat16
```

This shards the 70B model across 4 GPUs. Each holds roughly 35 GB of weights in BF16 — comfortable on A100 40GB with room for KV cache.

For multi-node deployment, combine TP with pipeline parallelism:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-405B-Instruct \
  --tensor-parallel-size 8 \
  --pipeline-parallel-size 2
```

TP=8 within each node (fast NVLink), PP=2 across nodes (slower InfiniBand). This is the standard pattern for 405B-class models.

## Communication topology matters

All-reduce latency depends on interconnect:

| Interconnect | All-reduce bandwidth | TP recommendation |
|-------------|---------------------|-------------------|
| NVLink (900 GB/s) | Excellent | TP up to 8 |
| PCIe Gen4 x16 | ~32 GB/s | TP=2 max |
| InfiniBand HDR | ~200 Gb/s | TP across nodes only with PP |

Running TP=4 on PCIe-connected GPUs often makes inference slower than TP=2 with quantization. Profile before scaling TP on consumer hardware.

NCCL environment variables tune collective performance:

```bash
export NCCL_P2P_LEVEL=NVL          # prefer NVLink paths
export NCCL_IB_DISABLE=0           # enable InfiniBand for multi-node
export NCCL_SOCKET_IFNAME=eth0     # correct network interface
```

## Combining TP with quantization

Quantization and TP are complementary. A 70B model at 4-bit needs ~35 GB total — one GPU. But at 4-bit with TP=2, each GPU holds ~17.5 GB, leaving massive headroom for KV cache and larger batches:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model ./llama-70b-awq \
  --quantization awq \
  --tensor-parallel-size 2 \
  --max-model-len 32768
```

This configuration serves 70B at 32K context on two 40GB GPUs — impossible without both quantization and TP.

## Pipeline parallelism for very large models

When TP alone is insufficient (model too large for one node), pipeline parallelism assigns layer groups to different GPUs:

```
Node 0 (TP=4): Layers 0–19   → activations →
Node 1 (TP=4): Layers 20–39  → activations →
Node 2 (TP=4): Layers 40–59  → activations →
Node 3 (TP=4): Layers 60–79  → output
```

Pipeline bubbles occur when a stage waits for the previous stage's output. Micro-batching (processing multiple requests through the pipeline simultaneously) reduces bubble overhead. At batch size 1, PP adds significant latency.

## Sizing TP for your deployment

Decision framework:

1. **Calculate memory need:** `params × bytes_per_param + KV_cache + overhead`
2. **Divide by GPU memory:** determines minimum TP size.
3. **Check interconnect:** NVLink available? If not, cap TP at 2.
4. **Measure latency:** compare TP=1 (if possible), TP=2, TP=4 on your hardware.
5. **Factor in batch size:** higher concurrency amortizes communication cost.

For Llama 3.1 70B BF16 on 4× A100 80GB: TP=4 gives each GPU ~35 GB weights, ~45 GB free for KV cache — enough for batch 32 at 4K context. That is a solid production configuration.

## TP vs PP for large models

| Parallelism | Splits | Best for |
|-------------|--------|----------|
| Tensor parallel (TP) | Layers across GPUs | Low latency, single node |
| Pipeline parallel (PP) | Layers sequentially | Very large models |
| Expert parallel (MoE) | Experts across GPUs | Mixtral-class models |

TP requires NVLink between GPUs — cross-node TP adds latency. Typical: TP=8 within node, PP across nodes.

## Common production mistakes

Teams get serving tensor parallelism wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving tensor parallelism break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When serving tensor parallelism misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Megatron-LM tensor parallelism paper](https://arxiv.org/abs/1909.08053)
- [vLLM distributed inference guide](https://docs.vllm.ai/en/latest/serving/distributed_serving.html)
- [NVIDIA NCCL documentation](https://docs.nvidia.com/deeplearning/nccl/user-guide/docs/index.html)
- [TensorRT-LLM multi-GPU inference](https://nvidia.github.io/TensorRT-LLM/advanced/multi-gpu.html)
- [DeepSpeed-Inference tensor parallelism](https://www.deepspeed.ai/inference/)
