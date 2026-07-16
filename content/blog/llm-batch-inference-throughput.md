---
title: "Batch Inference for Throughput"
slug: "llm-batch-inference-throughput"
description: "Maximize LLM throughput with batch inference: provider batch APIs, self-hosted continuous batching, queue design, and when batching beats real-time by 10x on cost."
datePublished: "2024-10-22"
dateModified: "2024-10-22"
tags: ["AI", "LLM", "Machine Learning", "Backend"]
keywords: "LLM batch inference, batch API OpenAI, continuous batching vLLM, inference throughput, offline LLM processing"
faq:
  - q: "When should I use batch inference instead of real-time API calls?"
    a: "Use batch for workloads with latency tolerance over 15 minutes to 24 hours: overnight summarization, bulk classification, embedding generation, eval runs, and content moderation backlogs. Interactive chat and user-facing agents need real-time endpoints."
  - q: "How much cheaper is batch inference?"
    a: "Provider batch APIs (OpenAI, Anthropic) typically offer 50% off standard rates with 24-hour completion windows. Self-hosted continuous batching improves GPU utilization 3–5x over static batching but requires you to operate inference servers."
  - q: "What batch size should I target on self-hosted models?"
    a: "Let the inference engine decide. vLLM and TensorRT-LLM use continuous batching that dynamically adds/removes requests. Target GPU memory utilization of 85–90% and tune max_num_seqs based on your average sequence length — shorter prompts allow larger batches."
---

Running 50,000 product descriptions through an LLM for classification at $0.003 per call in real-time costs $150 and ties up rate limits your support bot needs during business hours. The same job via batch API costs $75, completes overnight, and never competes with production traffic. Batch inference is boring infrastructure — and it's how teams afford LLM features at scale.

## Provider batch APIs

OpenAI and Anthropic both offer async batch endpoints: upload a JSONL file of requests, get results hours later at reduced price.

```jsonl
{"custom_id": "prod-001", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Classify: ..."}]}}
{"custom_id": "prod-002", "method": "POST", "url": "/v1/chat/completions", "body": {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Classify: ..."}]}}
```

```python
async def submit_batch(requests: list[BatchRequest]) -> str:
    file_id = await client.files.create(
        file=to_jsonl(requests),
        purpose="batch",
    )
    batch = await client.batches.create(
        input_file_id=file_id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )
    return batch.id
```

Poll or webhook on completion. Map results back via `custom_id`. Handle partial failures — batches can succeed 98% with individual line errors.

Best for: embeddings at ingest time, nightly report generation, eval dataset runs, reprocessing after prompt changes.

## Self-hosted continuous batching

When provider batch isn't an option (private models, data residency, cost at volume), run vLLM or TGI with continuous batching:

```bash
python -m vllm.entrypoints.openai.api_server \
  --model meta-llama/Llama-3.1-8B-Instruct \
  --max-num-seqs 256 \
  --gpu-memory-utilization 0.90
```

Continuous batching (also called in-flight batching) adds new requests to the GPU batch as others finish — unlike static batching where you wait for N requests before starting.

Throughput gains come from:

- Amortized attention computation across sequences
- Better GPU occupancy (fewer idle cycles)
- KV cache management via PagedAttention

## Queue architecture for batch workloads

Separate batch from real-time at the queue level:

```
                    ┌──────────────┐
Producers ─────────→│  SQS/Kafka   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
     [Real-time workers]        [Batch aggregator]
     latency SLO: 2s            flush every 30s OR 64 items
              │                         │
              ▼                         ▼
     [vLLM priority queue]      [vLLM batch queue]
```

Batch aggregator collects requests until size or time threshold, submits as a group. Real-time requests never wait behind batch jobs.

## Sizing and backpressure

Monitor:

- **Tokens/second per GPU** — primary throughput metric
- **Queue depth** — growing depth means under-provisioned
- **Batch fill rate** — if batches are size 3 when target is 64, your aggregator window is too short or traffic is too sparse
- **P99 latency for real-time** — batch traffic shouldn't degrade this

Apply backpressure when queue depth exceeds threshold:

```python
if queue.depth > MAX_DEPTH:
    raise ServiceUnavailable(retry_after=30)
```

For batch jobs, delay is acceptable. For real-time, shed load early.

## Chunking large batch jobs

A 500K-row job shouldn't be one batch file:

- Split into chunks of 5,000–10,000 requests
- Submit chunks in parallel (respect provider concurrent batch limits)
- Checkpoint progress — store completed `custom_id`s so retries skip done rows
- Idempotent writes on the output side

```python
for chunk in chunks(all_rows, size=5000):
    batch_id = await submit_batch(chunk)
    await db.save_checkpoint(job_id, batch_id, chunk.ids)
```

## Cost comparison framework

| Workload | Real-time cost | Batch cost | Latency tradeoff |
|----------|---------------|------------|------------------|
| 100K classifications/day | $300/day | $150/day | 24h vs 2s |
| Embedding 1M docs (one-time) | $2000 | $1000 + queue time | Hours vs days |
| Nightly summaries | Blocks prod quota | Isolated | Acceptable |

Run the math before building real-time pipelines for inherently async work.

## OpenAI Batch API workflow

Complete batch processing pipeline:

```python
import openai, json, time

# 1. Prepare JSONL input file
requests = [
    {"custom_id": f"req-{i}", "method": "POST",
     "url": "/v1/chat/completions",
     "body": {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": q}]}}
    for i, q in enumerate(queries)
]
with open("batch_input.jsonl", "w") as f:
    for req in requests:
        f.write(json.dumps(req) + "\n")

# 2. Upload and create batch
file = openai.files.create(file=open("batch_input.jsonl", "rb"), purpose="batch")
batch = openai.batches.create(input_file_id=file.id, endpoint="/v1/chat/completions", completion_window="24h")

# 3. Poll until complete
while batch.status not in ("completed", "failed"):
    time.sleep(60)
    batch = openai.batches.retrieve(batch.id)

# 4. Download results
results = openai.files.content(batch.output_file_id)
```

50% cost discount vs real-time. 24-hour completion window — not for latency-sensitive work.

## Self-hosted batch inference with vLLM

For on-prem or cost control at scale:

```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3.1-8B", max_num_seqs=256)
prompts = load_prompts("batch_job.csv")  # 100k prompts

sampling = SamplingParams(temperature=0, max_tokens=512)
outputs = llm.generate(prompts, sampling)  # continuous batching internally

save_results(outputs, "batch_output.parquet")
```

vLLM continuous batching processes requests as they complete — no fixed batch size. Throughput scales with GPU count linearly.

## Batch vs real-time decision matrix

| Factor | Batch | Real-time |
|---|---|---|
| Latency tolerance | Hours acceptable | Seconds required |
| Volume | >10k requests/day | Any |
| Cost sensitivity | High (50% discount) | Lower priority |
| Retry complexity | Simple (resubmit batch) | Complex (streaming) |
| User waiting | No | Yes |

Default to batch for: nightly summaries, bulk classification, embedding generation, eval runs. Default to real-time for: chat, search, agent tools.

## Failure modes

- **Real-time for overnight work** — 2× cost for no latency benefit
- **Single giant batch file** — failure loses all progress; chunk into 5k–10k
- **No checkpoint on batch job** — retry resubmits completed rows
- **Batch for user-facing chat** — 24h latency unacceptable
- **No idempotent output writes** — retry creates duplicate records

## Production checklist

- Batch API used for all async workloads >10k requests/day
- Input chunked into 5,000–10,000 request files
- Checkpoint saved after each chunk submission
- Output writes idempotent (upsert on custom_id)
- Cost comparison documented: batch vs real-time per workload
- Batch job status monitored; alert on failed status

## Resources

- [OpenAI Batch API documentation](https://platform.openai.com/docs/guides/batch)
- [Anthropic Message Batches API](https://docs.anthropic.com/en/docs/build-with-claude/message-batches)
- [vLLM continuous batching paper](https://arxiv.org/abs/2309.06180)
- [Hugging Face Text Generation Inference](https://github.com/huggingface/text-generation-inference)
- [NVIDIA TensorRT-LLM batching guide](https://nvidia.github.io/TensorRT-LLM/advanced/gpt-attention.html)
