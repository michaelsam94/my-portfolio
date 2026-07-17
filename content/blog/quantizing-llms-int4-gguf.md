---
title: "Quantizing LLMs: INT4, GPTQ, and GGUF Tradeoffs"
seoTitle: "LLM Quantization: INT4, GPTQ & GGUF Tradeoffs"
slug: "quantizing-llms-int4-gguf"
description: "LLM quantization tradeoffs for INT4, GPTQ, AWQ, and GGUF: quality loss, VRAM savings, on-device serving, and when each format is the right call."
datePublished: "2026-02-09"
dateModified: "2026-07-17"
tags: ["LLM", "Inference", "Performance", "On-Device"]
keywords: "LLM quantization, INT4, GPTQ, AWQ, GGUF, quantization tradeoffs, on-device LLM"
faq:
  - q: "What is LLM quantization?"
    a: "LLM quantization reduces the numeric precision of model weights — typically from 16-bit floats down to 8-bit or 4-bit integers — so the model uses less memory and can run faster on the same hardware. Done well, quality stays close to the full-precision model; done poorly, you get nonsense outputs that look fine until you measure them."
  - q: "What's the difference between GPTQ, AWQ, and GGUF?"
    a: "GPTQ and AWQ are post-training quantization methods that produce weight-only INT4 (or INT8) models, usually consumed by GPU runtimes like vLLM or Hugging Face Transformers. GGUF is a file format (and tooling ecosystem around llama.cpp) that packs quantized weights for CPU/GPU inference on local machines. You pick GPTQ/AWQ for server GPUs and GGUF when you want one file that runs well on laptops and phones."
  - q: "How much quality do you lose with INT4?"
    a: "On capable 7B–70B models, well-tuned INT4 (especially AWQ or GPTQ with calibration) often stays within a few points of FP16 on standard benchmarks. Smaller models and math/coding tasks degrade faster. Always eval your own prompts — a 'good' MMLU score can still break your product-specific edge cases."
---

LLM quantization is how you fit a model that was trained in 16-bit floats onto hardware that doesn't have that much VRAM — by storing weights in INT8 or INT4 and accepting a measured quality trade. If you've ever wanted a 70B-class model on a single consumer GPU, or a 7B model on a phone, quantization is the lever you're actually pulling. The alphabet soup (GPTQ, AWQ, GGUF, bitsandbytes) matters less than understanding *what* each method preserves and *where* it fails.

I treat quantization as an engineering decision with a budget: memory, latency, and eval score. Here's how I pick among the common options in 2026.

## What you're actually compressing

Transformers spend most of their footprint on weight matrices. Activations still matter at runtime, but for deployment the first win is shrinking the checkpoint. Rough memory for a dense model:

| Precision | Approx. bytes/param | 7B model | 70B model |
| --- | --- | --- | --- |
| FP16 / BF16 | 2 | ~14 GB | ~140 GB |
| INT8 | 1 | ~7 GB | ~70 GB |
| INT4 | 0.5 | ~3.5 GB | ~35 GB |

Those numbers ignore KV cache and activations — [KV cache optimization](https://blog.michaelsam94.com/kv-cache-optimization-llm-serving/) still bites you at long context — but they explain why INT4 is the default conversation for "run this locally."

Quantization can be **weight-only** (weights INT4, activations higher precision during matmul) or **full** (weights and activations). Weight-only is what most production stacks ship today because it's simpler and usually accurate enough.

## GPTQ vs AWQ vs bitsandbytes

Three post-training approaches dominate GPU serving:

- **GPTQ** — layer-wise quantization with Hessian-based error compensation. Needs a calibration set. Strong quality; historically a bit slower to apply. Widely supported in vLLM and Transformers.
- **AWQ (Activation-aware Weight Quantization)** — protects the minority of weights that matter most for activations. Often wins on quality-per-bit for instruction models. Calibration is lighter than GPTQ in practice.
- **bitsandbytes / QLoRA-style NF4** — great for *training* adapters and for quick load-and-run experiments. Less often my first choice for high-throughput serving compared to GPTQ/AWQ checkpoints.

A minimal load path with Hugging Face Transformers + AWQ looks like:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

model_id = "TheBloke/Mistral-7B-Instruct-v0.2-AWQ"
tokenizer = AutoTokenizer.from_pretrained(model_id)
model = AutoModelForCausalLM.from_pretrained(
    model_id,
    device_map="auto",
    trust_remote_code=True,
)

prompt = "Summarize OCPP 1.6 in two sentences."
inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
out = model.generate(**inputs, max_new_tokens=128)
print(tokenizer.decode(out[0], skip_special_tokens=True))
```

For serving, prefer a dedicated engine (vLLM, TGI, TensorRT-LLM) that fused the quantized kernels — loading AWQ into a research notebook is not the same as sustained tokens/sec under load.

## GGUF and the llama.cpp world

GGUF is the format the local/on-device crowd standardized on. One file holds metadata, tokenizer pieces, and quantized tensors. Quant variants are named by scheme and bits — `Q4_K_M`, `Q5_K_S`, `Q8_0`, and so on. The K-quants (k-means style block quantization) are usually the sweet spot for quality vs size.

Why GGUF wins on a laptop or [on-device stack](https://blog.michaelsam94.com/running-local-llms-on-device/):

1. **Portable** — same file runs via llama.cpp, Ollama, LM Studio, and many mobile wrappers.
2. **CPU-friendly** — not everything has a CUDA card; GGUF kernels are tuned for CPU and Apple Silicon Metal.
3. **Simple ops** — pull a file, run. No separate calibration pipeline on the user's machine.

The tradeoff: GPU server fleets that already run vLLM usually prefer GPTQ/AWQ/FP8 paths with continuous batching. GGUF is not wrong on a GPU — it's just not where the high-throughput ecosystem invested first.

## Quality cliffs I actually measure

Don't trust a blog's "negligible loss" claim. I run three checks before shipping a quantized checkpoint:

1. **Task eval** — your golden set, not only MMLU. For agents, tool-call JSON validity rates matter more than trivia.
2. **Long-context sanity** — quantization can amplify attention noise; test the context lengths you sell.
3. **Domain jargon** — rare tokens (protocol names, product SKUs) are where 4-bit often slips first.

Rules of thumb from shipping work:

- **70B INT4** — usually fine for chat and summarization if calibrated well.
- **7B–8B INT4** — usable, but watch coding and multi-step reasoning; sometimes INT5/Q5 or INT8 is worth the VRAM.
- **Sub-3B INT4** — you're already in [small language model](https://blog.michaelsam94.com/small-language-models-on-mobile/) territory; quantization compounds with capacity limits. Prefer the strongest small base you can afford before squeezing further.

## Choosing a path

| Goal | Prefer |
| --- | --- |
| Max tokens/sec on A100/H100 fleet | AWQ or GPTQ (or FP8) in vLLM / TensorRT-LLM |
| Laptop / offline desktop app | GGUF via llama.cpp or Ollama |
| Mobile / edge prototype | GGUF or vendor NPU formats; start with a small model |
| Fine-tune on one GPU | QLoRA / NF4, then export a serving quant |
| Absolute quality, money available | BF16 / FP8, skip aggressive INT4 |

Also decide *who* quantizes. Community GGUF repos are convenient and sometimes wrong (mismatched chat templates, silent corruption). Prefer official or well-known publishers, verify SHA hashes, and smoke-test generation before you wire the file into a product.

## Operational gotchas

- **Chat templates** — a quantized file with the wrong template looks like a "dumb model." Fix the template before you blame INT4.
- **Tokenizer parity** — GGUF must match the tokenizer the model was trained with. Don't mix pieces.
- **KV cache dtype** — weight quant ≠ activation/KV quant. You can still OOM on long contexts with a tiny weight file.
- **Licensing** — the base model license still applies to the quantized weights. Redistributing GGUF doesn't wash that away.
- **Eval before / after** — store scores next to the artifact. When someone asks "why did support quality drop last Tuesday?", you want a diff, not vibes.

Quantization is not magic compression — it's a controlled precision trade. Pick INT4 when the memory math demands it, pick the method that matches your runtime, and prove quality on *your* prompts. Everything else is branding on the Hugging Face card.


## Calibration sets from production logs

Sample 1k redacted production prompts stratified by intent (chat, extract, tool-call) for AWQ/GPTQ calibration — WikiText calibration optimizes perplexity, not your JSON tool-call validity. Store calibration hash with model artifact in registry.

## GGUF quant tier picking

On 7B instruct models, compare Q4_K_M vs Q5_K_M on your golden set before defaulting — reasoning tasks often need Q5 while FAQ bots tolerate Q4. Document quant choice next to eval scores so Tuesday's quality drop traces to artifact change, not mystery.

## Batch inference on quantized models

Batch size affects throughput nonlinearly on INT4 — benchmark batch 1 vs 8 vs 32 on target GPU before capacity planning. Quantized kernels may saturate memory bandwidth at lower batch than FP16.

## Legal review of redistributed quants

Community quants of Llama-derived models still carry license terms — legal review before shipping GGUF in commercial product update channel.

## Production rollout notes

Track GPU driver version with quant model deployments — driver updates occasionally change INT4 kernel behavior slightly. Pin driver version in serving runbook same as model artifact hash for reproducible inference.
## A/B quant in shadow

Serve FP16 to 1% shadow traffic comparing output logprob margin or exact match on golden prompts vs INT4 primary — detect quality regression before full quant rollout when calibration set missed edge case domain jargon.

## Resources

- [AutoAWQ documentation](https://github.com/casper-hansen/AutoAWQ)
- [GPTQ paper (arXiv)](https://arxiv.org/abs/2210.17323)
- [AWQ paper (arXiv)](https://arxiv.org/abs/2306.00978)
- [GGUF specification (ggml)](https://github.com/ggerganov/ggml/blob/master/docs/gguf.md)
- [llama.cpp project](https://github.com/ggerganov/llama.cpp)
- [Hugging Face quantization overview](https://huggingface.co/docs/transformers/main/en/quantization/overview)
