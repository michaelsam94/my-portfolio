---
title: "GPU Scheduling for LLM Inference at Scale"
slug: "gpu-scheduling-llm-inference"
description: "GPU scheduling for LLM inference: continuous batching, prefill/decode separation, and tensor parallelism — the tradeoffs that decide throughput."
datePublished: "2026-04-25"
dateModified: "2026-04-25"
tags: ["LLM", "Infrastructure", "GPU", "Performance"]
keywords: "GPU scheduling, continuous batching, vLLM, LLM inference at scale, throughput, tensor parallelism"
faq:
  - q: "What is GPU scheduling for LLM inference?"
    a: "GPU scheduling for LLM inference is the set of decisions about which requests run together, when new requests join the running batch, and how work is split across GPUs. Because generation is iterative and requests arrive and finish at different times, the scheduler continuously decides how to pack the GPU to maximize throughput without blowing latency budgets. It's the layer that turns raw GPU FLOPs into serving capacity."
  - q: "What is continuous batching and why does it matter?"
    a: "Continuous batching (also called in-flight batching) lets new requests join and finished requests leave the batch at every decoding step, instead of waiting for the whole batch to complete. This keeps the GPU busy: a short request no longer forces a long one to wait, and the batch stays full as work flows through. It typically delivers several times the throughput of naive static batching on real, variable traffic."
  - q: "What is the difference between the prefill and decode phases?"
    a: "Prefill processes the entire input prompt in one parallel forward pass and is compute-bound. Decode then generates output tokens one at a time and is memory-bandwidth-bound. Because they stress different GPU resources, mixing them naively causes interference — long prefills stall ongoing decodes — which is why modern schedulers separate or carefully interleave the two phases."
---

Scheduling is where LLM serving is won or lost. You can pick the right model, quantize the KV cache, and buy the fastest GPUs, and still get a fraction of the throughput a good scheduler would give you — because the hard problem isn't running one request, it's deciding how thousands of concurrent, variable-length requests share a GPU without stepping on each other. GPU scheduling for LLM inference is the layer that turns raw FLOPs into requests-per-second, and it's mostly a queueing-theory problem wearing an ML costume.

I've spent enough time staring at GPU utilization graphs to have strong opinions here. The recurring lesson: the scheduler, not the model, usually sets your ceiling on cost-per-token at scale.

## Why LLM scheduling is weird

Most request schedulers assume roughly uniform, short-lived work. LLM inference violates that on every axis:

- **Requests are variable-length.** One user wants 10 tokens, another wants 2,000. Their generation times differ by orders of magnitude.
- **Work is iterative.** A request isn't one task; it's hundreds of sequential decoding steps, each depending on the last.
- **Memory grows during the request.** The [KV cache expands with every token](https://blog.michaelsam94.com/kv-cache-optimization-llm-serving/), so a request that fit when it started can run the GPU out of memory later.
- **Two phases, two bottlenecks.** Prefill is compute-bound; decode is memory-bandwidth-bound. The same request stresses the GPU differently at different times.

Any scheduler that ignores these gives you idle GPUs, stalled requests, or out-of-memory crashes. Everything below is a response to one of these facts.

## Continuous batching: the baseline win

The first thing any serious stack does is **continuous batching** (a.k.a. in-flight batching). Naive static batching collects N requests, runs them together, and waits for all N to finish before starting the next batch. On variable-length traffic that's a disaster — one 2,000-token request holds the whole batch hostage while short requests sit finished but unreturned, GPU cycles wasted on padding.

Continuous batching operates at the *step* level instead. After every decoding step, the scheduler evicts finished sequences and admits waiting ones, so the batch stays full and short requests exit immediately. On real traffic this is routinely a 3–5x throughput improvement over static batching, and it's the reason stacks like [vLLM](https://github.com/vllm-project/vllm) became the default. If you're building serving infrastructure and don't have continuous batching, that's the first thing to fix — it dwarfs most other tuning.

## Prefill and decode interference

Here's the subtlety that separates good schedulers from great ones. Prefill (processing the prompt) is a big parallel matmul — compute-bound, GPU-saturating. Decode (generating tokens) is memory-bound and leaves compute underused. If you naively interleave them, a large prefill lands in the middle of a batch of decodes and stalls them all, spiking tail latency for everyone.

Two responses have emerged:

1. **Chunked prefill.** Break a long prompt's prefill into smaller chunks and interleave them with ongoing decodes, so no single prefill monopolizes a step.
2. **Prefill/decode disaggregation.** Run prefill on one pool of GPUs and decode on another, shipping the KV cache between them. This isolates the two workloads so each pool runs at its ideal batch size and neither interferes with the other.

Disaggregation is more operationally complex — you're now moving KV cache across a network — but at large scale it lets you size prefill and decode capacity independently, which is a real cost win. Chunked prefill is the pragmatic middle ground for a single pool.

## Parallelism: splitting the model across GPUs

When a model doesn't fit on one GPU, or you want lower latency, you split it. The main flavors:

| Strategy | What it splits | Best for | Cost |
| --- | --- | --- | --- |
| Tensor parallelism | Individual layers across GPUs | Low latency, big models | High intra-node comms (needs NVLink) |
| Pipeline parallelism | Layers into stages across GPUs | Fitting very large models | Pipeline bubbles, higher latency |
| Data/replica parallelism | Whole model, many copies | Throughput scaling | Linear memory cost |
| Expert parallelism | MoE experts across GPUs | Sparse models | All-to-all comms |

Tensor parallelism is the go-to for latency because it splits each layer's matmuls across GPUs and reassembles per step — but it demands fast interconnect (NVLink within a node), because it communicates every layer. Pipeline parallelism spans nodes more gracefully but introduces bubbles. And if you're serving mixture-of-experts models, expert parallelism adds its own all-to-all traffic. The right combination is workload-specific; there's no universal answer, only a profiling exercise.

## The latency/throughput dial

Every scheduling decision is ultimately a trade between throughput (requests per second, which minimizes cost) and latency (time-to-first-token and inter-token latency, which users feel). Bigger batches raise throughput and hurt latency; smaller batches do the reverse. The knobs you actually turn:

- **Max batch size / max num sequences** — the throughput/latency dial.
- **Admission control** — refuse or queue new requests when memory is tight rather than OOM-crashing mid-generation.
- **Priority and preemption** — let a latency-critical request preempt a bulk batch job, recomputing or swapping out the victim's KV cache.
- **SLA-aware queueing** — separate queues for interactive vs. batch traffic so a nightly bulk job doesn't wreck chat latency.

The mistake I see teams make is tuning for one number in isolation. You want to define an SLA (say, p95 time-to-first-token under 500ms) and then maximize throughput *subject to that constraint*. This is exactly the kind of tradeoff I framed in the broader cost writeup, [cutting LLM costs with caching, routing, and batching](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) — batching is a cost lever, but only up to the point where latency breaks your product.

## What I'd actually do

If I were standing up LLM serving at scale today, the priority order:

1. **Start with a mature serving engine** that already implements continuous batching and paged attention. Don't hand-roll the scheduler.
2. **Enable chunked prefill** before reaching for full disaggregation; it fixes most prefill-interference pain with far less operational cost.
3. **Pick parallelism by constraint** — tensor parallelism within a well-connected node for latency, replicas for throughput, and only go multi-node when the model genuinely doesn't fit.
4. **Set an explicit SLA and admission control**, then push batch size up until you approach the SLA line. Measure p50 *and* p95; averages lie about tail behavior.
5. **Separate interactive and batch traffic** at the queue level.

The uncomfortable truth is that most of the serving cost story lives in this layer, not in the model. A team running a smaller model on a well-tuned scheduler will routinely beat a team running a bigger model on a naive one — on both cost and latency. Treat scheduling as a first-class engineering surface, profile relentlessly, and the GPUs you already have will go a lot further.

## Resources

- [Orca: A Distributed Serving System for Transformer-Based Generative Models (continuous batching, OSDI)](https://www.usenix.org/conference/osdi22/presentation/yu)
- [Efficient Memory Management for LLM Serving with PagedAttention (vLLM, arXiv)](https://arxiv.org/abs/2309.06180)
- [DistServe: Disaggregating Prefill and Decoding for LLM Serving (arXiv)](https://arxiv.org/abs/2401.09670)
- [SARATHI: Efficient LLM Inference with Chunked Prefills (arXiv)](https://arxiv.org/abs/2308.16369)
- [NVIDIA TensorRT-LLM documentation](https://nvidia.github.io/TensorRT-LLM/)
- [vLLM project and documentation](https://github.com/vllm-project/vllm)
