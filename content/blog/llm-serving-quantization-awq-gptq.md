---
title: "Serving Quantized Models: AWQ and GPTQ"
slug: "llm-serving-quantization-awq-gptq"
description: "Compare AWQ and GPTQ for serving quantized LLMs in production: accuracy trade-offs, throughput gains, and how to pick the right format for your inference stack."
datePublished: "2025-03-03"
dateModified: "2026-07-17"
tags:
keywords: "AWQ GPTQ comparison, LLM quantization serving, 4-bit inference, weight-only quantization, vLLM AWQ, llama.cpp GPTQ"
faq:
  - q: "Should I use AWQ or GPTQ for production serving?"
    a: "AWQ generally preserves accuracy better on instruction-tuned models at 4-bit because it protects salient weight channels. GPTQ has broader tooling support and more pre-quantized model checkpoints on Hugging Face. If accuracy on your eval set matters most, benchmark both on your specific model and task before committing."
  - q: "How much speedup does 4-bit quantization actually give?"
    a: "On memory-bandwidth-bound workloads — which most LLM decode is — 4-bit weights cut memory traffic by roughly 4× compared to FP16, often yielding 1.5–2.5× throughput improvement depending on batch size and hardware. Prefill is less dramatic because compute, not bandwidth, often dominates."
  - q: "Can I quantize a fine-tuned model without retraining?"
    a: "Yes. Both AWQ and GPTQ are post-training quantization methods. You run calibration on a representative dataset (typically 128–512 samples) to determine scaling factors or salient channels, then produce a quantized checkpoint. No gradient updates required."
---
Running a 70B parameter model in FP16 needs roughly 140 GB of GPU memory. That is two A100 80GB cards just to load weights, before KV cache or batching headroom. Quantization compresses those weights to 4 bits — about 35 GB — and the model still answers questions competently on most tasks. AWQ and GPTQ are the two post-training quantization methods you will encounter most when serving open-weight models, and they are not interchangeable.

The choice affects accuracy on your eval set, which inference engines can load the checkpoint, and whether you need activation quantization on top of weight compression.

## What weight-only quantization does

Both AWQ and GPTQ reduce weight precision from FP16/BF16 to INT4 (or INT8) while keeping activations in higher precision during inference. The forward pass becomes:

```
output = dequantize(W_quant) @ activation
```

The dequantization happens on-the-fly in optimized CUDA kernels, so you never materialize full FP16 weights in memory. The speedup comes from reading 4-bit values from VRAM instead of 16-bit — decode is almost always memory-bandwidth bound.

## GPTQ: layer-wise Hessian-aware quantization

GPTQ (Generalized Post-Training Quantization) quantizes weights one layer at a time, using approximate second-order information (Hessian) to minimize the error introduced at each step. The algorithm:

1. Collect calibration activations for each layer.
2. Quantize weights column by column, adjusting remaining weights to compensate for quantization error.
3. Write INT4 weights plus per-group scaling factors.

```python
from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig

quantize_config = BaseQuantizeConfig(
    bits=4,
    group_size=128,
    desc_act=False,  # desc_act=True saves accuracy but hurts vLLM compat
)

model = AutoGPTQForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-8B-Instruct",
    quantize_config=quantize_config,
)
model.quantize(calibration_samples)
model.save_quantized("./llama-8b-gptq")
```

**Strengths:** mature ecosystem, thousands of pre-quantized models on Hugging Face, works with llama.cpp, text-generation-webui, and ExLlamaV2.

**Weaknesses:** `desc_act=True` (descending activation order) improves accuracy but breaks compatibility with some serving engines. Group size and bit width choices matter more than the docs suggest.

## AWQ: protecting salient weights

AWQ (Activation-aware Weight Quantization) takes a different approach. Instead of relying solely on Hessian error compensation, it identifies which weight channels matter most based on activation magnitudes and scales them less aggressively.

The insight: not all weights contribute equally. A small fraction of channels carry disproportionate signal. AWQ finds those channels and applies per-channel scaling before quantization, preserving accuracy at 4-bit where naive rounding would collapse.

```python
from awq import AutoAWQForCausalLM

model = AutoAWQForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B-Instruct")
model.quantize(tokenizer, quant_config={"w_bit": 4, "q_group_size": 128})
model.save_quantized("./llama-8b-awq")
```

**Strengths:** typically better accuracy on instruction-following and reasoning tasks at 4-bit. Native support in vLLM, TensorRT-LLM, and SGLang.

**Weaknesses:** fewer pre-built checkpoints than GPTQ. Quantization takes longer because of the saliency search step.

## Benchmarking on your workload

Do not trust generic MMLU scores alone. Run both formats against your actual prompts:

| Metric | What to measure |
|--------|----------------|
| Task accuracy | Your golden eval set (50–200 examples) |
| Perplexity | Held-out domain text if generative quality matters |
| Throughput | Tokens/sec at your target batch size |
| Latency | TTFT and inter-token latency at p99 |
| VRAM | Peak memory with your max context length |

On Llama 3.1 8B with a customer-support eval set, AWQ and GPTQ often land within 1–2% accuracy of each other. On 70B models with long-context RAG, AWQ's saliency protection can mean the difference between usable and hallucination-prone.

## Serving quantized checkpoints

**vLLM with AWQ:**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model ./llama-8b-awq \
  --quantization awq
```

**vLLM with GPTQ (via GPTQModel or compatible checkpoint):**

```bash
python -m vllm.entrypoints.openai.api_server \
  --model ./llama-8b-gptq \
  --quantization gptq
```

**llama.cpp** loads GGUF files (often converted from GPTQ) and runs on CPU or GPU with broad hardware support — useful for edge deployment but lower throughput than dedicated GPU kernels.

Match your quantization format to your serving engine before quantizing. Converting between formats is lossy and time-consuming.

## When not to quantize

Skip quantization if:

- Your model is already small enough (8B on a single 24GB card in FP16).
- You need maximum accuracy on high-stakes outputs (medical, legal) and eval shows degradation.
- Your workload is prefill-heavy with tiny batches — bandwidth savings matter less when compute dominates.

For models above 13B parameters where VRAM is the bottleneck, 4-bit quantization is usually the fastest path to production without buying more GPUs.

## Common production mistakes

Teams get serving quantization awq gptq wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving quantization awq gptq break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When serving quantization awq gptq misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [AWQ paper (Lin et al., 2023)](https://arxiv.org/abs/2306.00923)
- [GPTQ paper (Frantar et al., 2022)](https://arxiv.org/abs/2210.17323)
- [vLLM quantization support](https://docs.vllm.ai/en/latest/quantization/auto_awq.html)
- [AutoGPTQ GitHub repository](https://github.com/AutoGPTQ/AutoGPTQ)
- [Hugging Face optimum-quantization guide](https://huggingface.co/docs/optimum/en/conceptual_guides/quantization)
