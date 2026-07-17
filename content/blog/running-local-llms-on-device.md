---
title: "Running Local LLMs On-Device: llama.cpp, Ollama, Quantization"
slug: "running-local-llms-on-device"
description: "A practical guide to running local LLMs: llama.cpp, Ollama, GGUF quantization levels, hardware requirements, and how to pick a model that fits your RAM."
datePublished: "2026-01-15"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "local LLM, llama.cpp, Ollama, quantization, GGUF, on-device AI, run LLM locally"
faq:
  - q: "What do I need to run an LLM locally?"
    a: "You need a model in a supported format (usually GGUF), a runtime like llama.cpp or Ollama, and enough RAM or VRAM to hold the quantized model plus its context. A 7-8B model quantized to 4-bit runs comfortably on a machine with 16GB of memory."
  - q: "What is GGUF and why does quantization matter?"
    a: "GGUF is the file format used by llama.cpp for quantized models. Quantization shrinks model weights from 16-bit floats to 4, 5, or 8 bits, cutting memory and speeding inference with a small quality loss. It's what makes running capable models on consumer hardware possible."
  - q: "Should I use llama.cpp or Ollama?"
    a: "Use Ollama for the fastest path to a working local model — it wraps llama.cpp with a simple CLI and model registry. Use llama.cpp directly when you need fine control over build flags, quantization, or embedding it into your own application."
---

Running an LLM on your own hardware is no longer exotic. A capable 7–8B model, quantized to 4-bit, runs on a laptop with 16GB of RAM and answers in real time. The two tools that made this normal are [llama.cpp](https://github.com/ggml-org/llama.cpp), the C/C++ inference engine, and [Ollama](https://ollama.com/), which wraps it in a friendly CLI and model registry. If you want private, offline, zero-marginal-cost inference, this is the stack.

The catch is that "which model fits" is a memory-math question, and getting quantization wrong means either an out-of-memory crash or needlessly degraded output. I'll cover the fast path with Ollama, the control path with llama.cpp, how to read GGUF quantization labels, and how to size a model to your machine so it actually runs.

## The fast path: Ollama

Ollama is the shortest distance to a working local model. Install it, pull a model, and you have an interactive session and a local HTTP API:

```bash
ollama run llama3.1:8b
# or just start the server and hit the API
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Explain quantization in one paragraph."
}'
```

Ollama pulls a sensibly quantized GGUF by default (typically a 4-bit variant), manages the model cache, and exposes an OpenAI-compatible endpoint at `/v1` so existing client code often works with a base-URL swap. For most people building a local prototype or a privacy-sensitive feature, this is all you need. It's also the easiest way to test several models — `ollama pull` a few and compare.

## The control path: llama.cpp

When you need more — a specific quantization, custom build flags for your GPU, or embedding inference directly into an app — go to llama.cpp. You build it with the acceleration backend for your hardware:

```bash
# Apple Silicon (Metal is on by default)
make

# NVIDIA (CUDA)
cmake -B build -DGGML_CUDA=ON && cmake --build build

# run a GGUF model
./llama-cli -m models/llama-3.1-8b-Q4_K_M.gguf -p "Hello" -n 128
```

llama.cpp is what actually runs the model under Ollama, LM Studio, and most local tools. Going direct gives you the `llama-server` for an OpenAI-compatible API, control over context length and GPU layer offload (`-ngl`), and the ability to quantize models yourself. It's the right layer when local inference is a product feature, not a convenience.

## Reading GGUF quantization labels

GGUF filenames carry the quantization scheme, and decoding them saves a lot of trial and error. A label like `Q4_K_M` means 4-bit, K-quant, medium. Here's the practical guide:

| Quant | Bits | Size (8B model) | When to use |
| --- | --- | --- | --- |
| Q8_0 | 8 | ~8.5 GB | Max quality, plenty of RAM |
| Q6_K | 6 | ~6.6 GB | Near-lossless, good balance |
| Q5_K_M | 5 | ~5.7 GB | Strong quality, moderate size |
| Q4_K_M | 4 | ~4.9 GB | The default sweet spot |
| Q3_K_M | 3 | ~4.0 GB | Tight memory, visible quality drop |
| Q2_K | 2 | ~3.2 GB | Last resort, noticeably degraded |

**Q4_K_M is the default for a reason** — it's where memory savings stop being nearly free. Below 4-bit, quality degrades fast; above it, you pay a lot of RAM for small gains. Start at Q4_K_M, move up to Q5 or Q6 if you have headroom and notice quality issues, and only drop to Q3 if you must fit a bigger model into limited memory.

## Sizing a model to your machine

The memory math is straightforward: you need enough RAM (or VRAM on GPU) for the quantized weights **plus** the context (KV cache), which grows with context length. A rough rule:

```
required_memory ≈ model_file_size + kv_cache
kv_cache grows with context length and model size
```

Practical guidance by memory:

- **8 GB** — 3–4B models at Q4, or a 7B at Q3 with short context. Usable, tight.
- **16 GB** — 7–8B at Q4_K_M comfortably; the mainstream local target.
- **32 GB** — 13–14B at Q4/Q5, or 8B at Q8 with long context.
- **64 GB+** — 30–70B class models at Q4, slowly on CPU, faster with a GPU.

On Apple Silicon, unified memory means the GPU shares system RAM, so a 32GB Mac punches above its weight for local inference. On PCs, VRAM is the binding constraint — offload as many layers to the GPU as fit (`-ngl`) and let the rest run on CPU.

## Where local inference makes sense

Local LLMs win on three axes: **privacy** (data never leaves the device), **cost** (no per-token bill), and **offline** operation. They lose on raw capability — a local 8B model is not GPT-class — and on throughput under concurrent load. So the fit is: on-device assistants, private document analysis, offline features, and cost-sensitive high-volume tasks where a smaller model is good enough.

This is exactly the trend reshaping mobile too, where [small language models on mobile](https://blog.michaelsam94.com/small-language-models-on-mobile/) and platform runtimes like [Gemini Nano on Android](https://blog.michaelsam94.com/on-device-ai-android-gemini-nano/) bring the same idea to phones. For privacy-first products, running inference on the user's hardware isn't just a cost optimization — it's an [architecture for privacy](https://blog.michaelsam94.com/on-device-ai-for-privacy/). Start with Ollama to prove the model is good enough, then drop to llama.cpp when you're ready to ship it into something real.

## Model quantization tradeoffs

Q4_K_M fits MacBook RAM but hallucinates more on structured extraction than Q8. Benchmark your actual prompts — MMLU scores mislead. llama.cpp and MLX support different model formats; standardize on GGUF or MLX weights per platform team.

## Privacy and offline guarantees

On-device inference keeps prompts local — document that crash logs may still contain snippets if logging is verbose. Air-gapped deployments need model update mechanism (USB, internal mirror) separate from cloud `ollama pull`. Compliance teams care about data residency; local LLM is not automatic GDPR win if telemetry phones home.

## Practical follow-through (1)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (2)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Practical follow-through (3)

Ship the smallest vertical slice first — one route, one widget, one index configuration — with rollback documented before expanding scope. Baseline the user-visible metric this work protects (latency, recall, conversion, task success rate) for seven days before change and seven days after in your largest market.

Compare canary p75 to control before full rollout. Exercise edge paths manually: refresh, back navigation, double-submit, offline mode, and keyboard-only flows. When assumptions change — traffic doubles, vendor upgrades, org restructure — revisit whether the original design still fits; quiet periods hide drift until the next incident.

## Resources

- [llama.cpp — GitHub](https://github.com/ggml-org/llama.cpp)
- [Ollama — official site](https://ollama.com/)
- [Hugging Face — GGUF models and format docs](https://huggingface.co/docs/hub/en/gguf)
- [LM Studio — desktop local LLM app](https://lmstudio.ai/)
- [llama.cpp quantization discussion](https://github.com/ggml-org/llama.cpp/blob/master/examples/quantize/README.md)
- [Hugging Face — open LLM leaderboard](https://huggingface.co/open-llm-leaderboard)
