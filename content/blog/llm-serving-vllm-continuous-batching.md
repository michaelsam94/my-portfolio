---
title: "Serving LLMs with vLLM"
slug: "llm-serving-vllm-continuous-batching"
description: "Deploy production LLM APIs with vLLM: continuous batching, PagedAttention, OpenAI-compatible endpoints, and the configuration knobs that actually matter."
datePublished: "2025-03-17"
dateModified: "2025-03-17"
tags: ["AI", "LLM", "vLLM", "Inference"]
keywords: "vLLM serving, continuous batching, PagedAttention, OpenAI compatible API, LLM production deployment, vLLM configuration"
faq:
  - q: "Why is vLLM faster than Hugging Face Transformers for serving?"
    a: "vLLM replaces static batching with continuous batching — new requests join an in-flight batch without waiting for all sequences to finish. PagedAttention manages KV cache in non-contiguous memory blocks like OS virtual memory, reducing fragmentation and allowing 2–4× more concurrent sequences than naive implementations."
  - q: "Can I drop vLLM in as an OpenAI API replacement?"
    a: "Yes. vLLM ships an OpenAI-compatible server at /v1/chat/completions and /v1/completions. Point your existing OpenAI SDK client at the vLLM endpoint by changing the base URL. Most parameters (temperature, max_tokens, stop sequences) work identically."
  - q: "How do I choose max_model_len and gpu_memory_utilization?"
    a: "max_model_len sets the maximum context window — higher values consume more KV cache memory per sequence, reducing concurrent capacity. gpu_memory_utilization (default 0.9) controls what fraction of GPU memory vLLM pre-allocates. Start at 0.9, reduce if you hit OOM during traffic spikes."
---

Hugging Face Transformers loads a model and generates one request at a time. That works for notebooks. In production, where 50 users hit your API simultaneously with different prompt lengths, static batching either queues requests (high latency) or pads every sequence to the longest prompt (wasted compute).

vLLM is the inference engine that fixed this for most self-hosted deployments. Its two core innovations — continuous batching and PagedAttention — let a single GPU serve many concurrent requests efficiently, and its OpenAI-compatible API server means you can swap it in without rewriting client code.

## Continuous batching vs. static batching

Static batching waits until N requests arrive, pads them to equal length, runs one forward pass, and waits for all N to finish generating. If one request produces 500 tokens and another produces 10, the short request's GPU slots sit idle while the long one finishes.

Continuous batching (also called iteration-level batching or in-flight batching) works differently:

```
Step 1: [Req A prefill] [Req B prefill] [Req C prefill]
Step 2: [Req A decode]  [Req B decode]  [Req C decode]
Step 3: [Req A decode]  [Req B decode]  [Req D prefill]  ← D joins mid-flight
Step 4: [Req A decode]  [Req C decode]  [Req D decode]   ← B finished, slot freed
```

Requests enter and exit the batch at every iteration. No padding waste, no waiting for stragglers. Throughput scales with concurrent request count rather than batch size alone.

## PagedAttention: KV cache without fragmentation

Standard implementations allocate a contiguous KV cache tensor sized to `max_seq_len` for each request. With 100 concurrent requests at 8K max length, you reserve 800K tokens of cache even if most sequences are 200 tokens. Memory fragments as sequences finish at different times.

PagedAttention borrows from OS virtual memory:

- KV cache is split into fixed-size **blocks** (typically 16 tokens).
- A **block table** maps logical sequence positions to physical blocks.
- Blocks are allocated on demand and freed when sequences complete.
- Non-contiguous blocks can be shared across sequences (prefix caching builds on this).

This typically allows 2–4× more concurrent sequences on the same GPU compared to contiguous allocation.

## Starting the OpenAI-compatible server

```bash
pip install vllm

python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype auto \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90
```

Point your client:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")

response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Explain PagedAttention"}],
    max_tokens=512,
    temperature=0.7,
)
```

Streaming works identically:

```python
stream = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[{"role": "user", "content": "Write a poem"}],
    stream=True,
)
for chunk in stream:
    print(chunk.choices[0].delta.content, end="")
```

## Configuration that matters in production

| Parameter | What it controls | Tuning guidance |
|-----------|-----------------|-----------------|
| `max_model_len` | Maximum context window | Set to your actual need, not the model maximum. 8192 vs 32768 can 4× your concurrency. |
| `gpu_memory_utilization` | Fraction of GPU memory for KV cache | 0.9 default. Lower if co-locating other processes. |
| `max_num_seqs` | Maximum concurrent sequences | Cap to prevent OOM under burst traffic. |
| `tensor_parallel_size` | GPUs for model sharding | See tensor parallelism post for sizing. |
| `enable_prefix_caching` | Reuse shared prompt KV cache | Enable for RAG and agent workloads. |
| `quantization` | Weight precision (awq, gptq, fp8) | Reduces memory, increases batch capacity. |

## Python API for programmatic control

For embedding vLLM in a custom service rather than using the HTTP server:

```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3.1-8B-Instruct",
    max_model_len=8192,
    gpu_memory_utilization=0.9,
)

params = SamplingParams(temperature=0.7, max_tokens=256)
outputs = llm.generate(["Hello!", "Explain gravity", "Write SQL for users table"], params)

for output in outputs:
    print(output.outputs[0].text)
```

The `LLM` class handles batching internally. Pass a list of prompts and vLLM schedules them with continuous batching automatically.

## Monitoring and observability

vLLM exposes Prometheus metrics at `/metrics`:

- `vllm:num_requests_running` — active sequences
- `vllm:num_requests_waiting` — queued requests
- `vllm:gpu_cache_usage_perc` — KV cache utilization
- `vllm:avg_generation_throughput_toks_per_s` — decode throughput
- `vllm:time_to_first_token_seconds` — TTFT histogram

Alert on `num_requests_waiting` sustained above zero — that means your GPU is saturated and you need more replicas or smaller models.

## Deployment patterns

**Single GPU, single replica:** fine for development and low-traffic internal tools.

**Multi-replica with load balancer:** run N independent vLLM instances behind nginx or a K8s Service. Each replica handles its own batching. Scale horizontally when `num_requests_waiting` grows.

**Kubernetes with LeaderWorkerSet:** vLLM supports multi-node tensor parallelism via Ray or native distributed executors for models that need multiple GPUs per replica.

```yaml
# Simplified K8s deployment
resources:
  limits:
    nvidia.com/gpu: 1
env:
  - name: VLLM_GPU_MEMORY_UTILIZATION
    value: "0.9"
```

## Common production mistakes

Teams get serving vllm continuous batching wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving vllm continuous batching break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Resources

- [vLLM documentation](https://docs.vllm.ai/)
- [PagedAttention paper (Kwon et al., 2023)](https://arxiv.org/abs/2309.06180)
- [vLLM GitHub repository](https://github.com/vllm-project/vllm)
- [Continuous batching explained (Anyscale blog)](https://www.anyscale.com/blog/continuous-batching-llm-inference)
- [vLLM production deployment guide](https://docs.vllm.ai/en/latest/serving/deploying_with_docker.html)
