---
title: "Quantizing Models for Phones"
slug: "on-device-llm-quantization-mobile"
description: "Choose the right LLM quantization for mobile: INT4 vs GPTQ vs AWQ, quality benchmarks, memory math, and practical export workflows for iOS and Android."
datePublished: "2025-12-19"
dateModified: "2026-07-17"
tags: ["AI", "Mobile", "Quantization", "On-Device"]
keywords: "LLM quantization mobile, INT4 quantization, GPTQ AWQ, model compression phone, quantized inference"
faq:
  - q: "How much memory does a 7B model use at different quantization levels?"
    a: "Roughly: FP16 needs ~14 GB, INT8 ~7 GB, INT4 ~3.5–4 GB plus KV cache overhead. On a phone you also need headroom for the OS and your app UI, so a 7B INT4 model realistically requires 6–8 GB total RAM available — which excludes most mid-range devices."
  - q: "Does INT4 quantization ruin model quality?"
    a: "For chat, summarization, and classification, well-calibrated INT4 (GPTQ or AWQ) often loses less than 2–3% on standard benchmarks compared to FP16. Reasoning-heavy tasks and code generation show more degradation. Always evaluate on your actual prompts, not MMLU alone."
  - q: "Should I quantize during training or post-training?"
    a: "Post-training quantization (PTQ) with GPTQ, AWQ, or llama.cpp's quantize script is what mobile teams use in practice. Quantization-aware training (QAT) can recover quality but requires a training pipeline most app teams don't have. Start with PTQ; move to QAT only if evals fail on domain-specific tasks."
---

The first time I deployed a 7B model on a phone, I used FP16 because "quality matters." The app crashed on launch for 60% of our beta cohort. Switching to INT4 cut model size from 14 GB to under 4 GB and turned an impossible feature into something a Pixel 7 could run — with summarization quality our PM couldn't distinguish from the cloud version.

Quantization is not a compression trick you apply at the end. It's a product decision that trades memory, latency, and output quality. Mobile has hard ceilings on all three.

## Quantization schemes you'll actually encounter

| Scheme | Bits | Typical use | Quality vs FP16 |
|--------|------|-------------|-----------------|
| FP16 | 16 | Server, dev baseline | Reference |
| INT8 | 8 | Edge servers, some NPUs | ~99% on most tasks |
| INT4 (GPTQ/AWQ) | 4 | Phone, laptop | ~95–98% depending on calibration |
| INT3 / mixed | 3–4 mixed | Extreme memory pressure | Noticeable on hard prompts |

GPTQ (Generative Pre-trained Transformer Quantization) and AWQ (Activation-aware Weight Quantization) differ in how they pick scale factors. AWQ tends to preserve quality on smaller models at aggressive bit widths because it protects salient weight channels. GPTQ has broader tooling support through `auto-gptq` and Hugging Face `optimum`.

For llama.cpp and MLC pipelines, you'll see naming like `Q4_K_M`, `Q5_K_S`, `Q8_0`. The `_K` variants use k-quant mixed precision — `Q4_K_M` is the community default for balancing size and quality on 7B models.

## The memory math before you pick a model

Don't trust the model card's parameter count alone:

```
model_bytes ≈ num_params × bits_per_weight / 8
kv_cache_bytes ≈ 2 × num_layers × hidden_dim × seq_len × bytes_per_element / num_kv_heads_factor
```

For Llama-3.2-3B at Q4 with 2048 context, expect ~1.8 GB weights + ~300 MB KV cache. Add 500 MB for runtime overhead and your app binary. If the device has 6 GB total RAM, you're competing with Chrome tabs the user won't close.

Rule of thumb: target models where `(weights + KV cache) × 1.5 < available RAM after OS reservation`. Android's `ActivityManager.getMemoryInfo()` and iOS `os_proc_available_memory()` should gate model loading, not a static device list.

## A practical export workflow

Starting from a Hugging Face checkpoint:

```python
# AWQ export with llm-compressor / autoawq (example pattern)
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

model_path = "meta-llama/Llama-3.2-3B-Instruct"
quant_path = "llama-3.2-3b-awq-int4"

model = AutoAWQForCausalLM.from_pretrained(model_path)
tokenizer = AutoTokenizer.from_pretrained(model_path)

model.quantize(tokenizer, quant_config={"w_bit": 4, "q_group_size": 128})
model.save_quantized(quant_path)
```

Then convert to your runtime format — GGUF for llama.cpp, MLC bundle for TVM, or ONNX for Core ML / NNAPI depending on your stack.

**Calibration data matters.** GPTQ and AWQ use a sample dataset (often WikiText or a few hundred of your own prompts) to minimize quantization error. If your app does medical or legal summarization, calibrate on domain text. I've seen 5-point F1 swings just from swapping calibration corpora.

## Evaluating quality on your prompts, not benchmarks

Run a golden set of 50–100 real user prompts through FP16 (cloud baseline) and each quant variant. Score with:

- ROUGE/BERTScore for summarization
- Exact match or LLM-as-judge for extraction tasks
- Human spot-check on the worst 10 regressions

Watch for specific failure modes: INT4 models hallucinate numbers more often, lose instruction-following on multi-step prompts, and degrade on non-English text if calibration was English-only.

Log `quant_scheme` in production analytics. When users report bad output, you need to know whether they're on Q3 or Q4_K_M.

## Runtime considerations on device

Quantized weights aren't enough — the inference engine must fuse dequantization with matmul efficiently. llama.cpp's GGML kernels and MLC's TVM schedules do this well. Raw ONNX INT4 without vendor-specific NPU support often runs slower than INT4 on GPU because the graph isn't optimized.

On Apple Silicon, ANE (Apple Neural Engine) support for LLMs is evolving; check whether your quant format is compatible before assuming NPU acceleration. Many teams still run INT4 on GPU via Metal and get acceptable battery life for short sessions.

Thermal throttling hits quantized models too — smaller weights mean faster compute, which means more heat per wall-clock second. Cap max generation length and offer "quick summary" vs "detailed summary" modes with different token budgets.

## Common production mistakes

Teams get on device llm quantization mobile wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of on device llm quantization mobile fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When on device llm quantization mobile misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Quant format selection guide

| Format | Size | Quality | Mobile fit |
|--------|------|---------|------------|
| Q4_K_M | Baseline | Good | Default |
| Q5_K_M | +15% | Better reasoning | Flagship optional |
| Q8_0 | +100% | Near FP16 | Rare on phone |
| IQ4_XS | Smallest | Variable | Watch quality evals |

Run perplexity and task-specific evals (summarization ROUGE, extraction F1) — perplexity alone misleads on instruction-tuned models.

## Per-channel vs per-tensor quant

GGUF Q4_K uses mixed precision — some layers at higher bit width. Custom quant scripts that force Q4_0 everywhere save MB but collapse instruction following. Trust published quants from reputable quantizers before rolling your own.

## Calibration data for INT8 ONNX

When quantizing via ONNX Runtime, use 100–500 representative prompts from your app domain — not WikiText. Calibration mismatch shows up as hallucinated formatting in structured extraction tasks.

## NPU vs CPU quant compatibility

INT4 quants speed CPU but may lack NPU op coverage — profile per delegate. Some NPUs require channel-wise scales only available in Q4_K formats.

## A/B quality monitoring in production

Log thumbs up/down on summaries with quant version header — aggregate quality by quant format weekly. Shift default quant when Q4_K_M satisfaction drops below Q5_K_M on flagship devices despite size cost.

## Side-by-side QA rubric

Score summaries 1–5 by three raters on 50 prompts per quant format — pick default quant only when median score within 0.2 of larger model at acceptable latency.

## Export quant benchmarks in telemetry

Anonymous aggregate: device model, quant format, tokens/sec — informs which quants to deprecate without PII.

## Resources

- [Hugging Face Optimum quantization guide](https://huggingface.co/docs/optimum/en/intel/optimization_inc)
- [AutoAWQ repository](https://github.com/casper-hansen/AutoAWQ)
- [llama.cpp quantization documentation](https://github.com/ggerganov/llama.cpp/blob/master/examples/quantize/README.md)
- [MLC LLM quantization options](https://llm.mlc.ai/docs/compilation/convert_weights.html)
- [GPTQ paper (Frantar et al.)](https://arxiv.org/abs/2210.17323)
