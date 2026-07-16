---
title: "Fine-Tuning with LoRA and QLoRA"
slug: "fine-tuning-lora-qlora-guide"
description: "Fine-tune large LLMs on limited GPUs with LoRA and QLoRA: rank selection, target modules, 4-bit quantization, memory math, and merging adapters for deployment."
datePublished: "2026-02-23"
dateModified: "2026-02-23"
tags: ["AI", "Machine Learning", "Fine-Tuning", "LoRA"]
keywords: "LoRA fine-tuning guide, QLoRA 4-bit fine-tuning, PEFT LoRA, fine-tune LLM single GPU, LoRA rank target modules, merge LoRA weights, bitsandbytes QLoRA"
faq:
  - q: "What GPU memory do I need for QLoRA fine-tuning a 7B model?"
    a: "QLoRA on 7B typically fits in 16–24 GB VRAM with batch size 1–4, sequence length 2048, r=16, and gradient checkpointing — varies by implementation. Full fine-tuning 7B often needs 4×+ memory. 70B QLoRA may require 48 GB+ or multi-GPU with FSDP."
  - q: "Which layers should LoRA target?"
    a: "Common defaults: attention q_proj, k_proj, v_proj, o_proj and sometimes MLP gate/up/down projections. Larger rank on attention only often suffices; adding MLP adapters increases capacity and memory. Match target_modules to your model architecture strings in PEFT config."
  - q: "Should I merge LoRA weights into the base model for deployment?"
    a: "Merge for lowest inference latency and simplest serving (single weight file). Keep adapters separate for multi-tenant customization (swap LoRA per customer) and smaller artifact storage. vLLM and TGI support hot-swapping LoRA adapters without merging."
---

Full fine-tune of a 13B model wanted eighty gigabytes of VRAM your team does not have. QLoRA loaded the base in 4-bit NormalFloat, attached rank-16 adapters to attention projections, and trained on a single A10 overnight — ninety-three percent of the domain metric gain at a fraction of the memory. LoRA (Low-Rank Adaptation) and QLoRA are how most teams actually fine-tune open models in 2025: freeze the pretrained weights, inject trainable low-rank matrices into selected layers, backprop only through adapters. The art is rank, target module selection, and knowing when to merge for production.

## LoRA mechanics

For weight matrix W, LoRA adds ΔW = BA where B ∈ ℝ^{d×r}, A ∈ ℝ^{r×k}, r ≪ min(d,k):

```python
from peft import LoraConfig, get_peft_model

config = LoraConfig(
    r=16,
    lora_alpha=32,       # scaling: alpha/r applied to LoRA output
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

model = get_peft_model(base_model, config)
model.print_trainable_parameters()
# trainable params: ~0.5% of total typical for r=16 on 7B
```

Effective scaling `lora_alpha / r` — common pattern alpha = 2r.

## QLoRA setup

Load base in 4-bit, attach LoRA in bf16/fp16:

```python
import torch
from transformers import AutoModelForCausalLM, BitsAndBytesConfig

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_use_double_quant=True,
)

model = AutoModelForCausalLM.from_pretrained(
    "meta-llama/Llama-3.1-8B",
    quantization_config=bnb_config,
    device_map="auto",
)

model = get_peft_model(model, config)
model.gradient_checkpointing_enable()
```

NF4 + double quant preserves quality for fine-tuning per QLoRA paper; train adapters in higher precision.

## Memory estimation (rough)

QLoRA 7B:

- 4-bit weights ~4 GB
- Adapters + optimizer states ~2–6 GB depending on batch/r
- Activations dominate at long seq — checkpointing helps

Reduce `max_seq_length`, increase `gradient_accumulation_steps` before giving up.

## Training loop essentials

```python
from trl import SFTConfig, SFTTrainer

args = SFTConfig(
    output_dir="./lora-out",
    learning_rate=2e-4,
    lr_scheduler_type="cosine",
    warmup_ratio=0.03,
    num_train_epochs=2,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    bf16=True,
    logging_steps=10,
    save_strategy="epoch",
    optim="paged_adamw_8bit",  # QLoRA-friendly
)

trainer = SFTTrainer(model=model, args=args, ...)
trainer.train()
trainer.save_model("lora-out/final")
```

`paged_adamw_8bit` reduces optimizer memory spikes.

## Rank and module tuning

| Symptom | Try |
|---------|-----|
| Underfit domain | Increase r to 32, add MLP modules |
| Forgetting general | Decrease r, lower LR, fewer epochs |
| OOM | r=8, shorter seq, more accumulation |
| Slow convergence | Slightly higher LR (cap 3e-4 LoRA) |

Do not grid-search blindly — one eval metric per change.

## Merge and deploy

Merge adapters into base for static deployment:

```python
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-3.1-8B", torch_dtype=torch.bfloat16)
merged = PeftModel.from_pretrained(base, "lora-out/final")
merged = merged.merge_and_unload()
merged.save_pretrained("merged-model")
```

Or serve with LoRA hot-swap (vLLM):

```bash
vllm serve meta-llama/Llama-3.1-8B --enable-lora --lora-modules domain=lora-out/final
```

Version adapter artifacts alongside base model hash — incompatible base upgrades break adapters silently.

## Pitfalls

- Training with `load_in_4bit` but evaluating merged fp16 without re-benchmark
- Wrong `target_modules` for architecture (GQA models name layers differently)
- Saving only adapter without `adapter_config.json` — cannot reload
- Quantizing merged model immediately — re-eval quality post-quantization

LoRA/QLoRA democratized fine-tuning; discipline in eval and deployment separates demo from production.

## Choosing rank and alpha

Rank (`r`) controls adapter capacity; alpha scales the adapter contribution:

| Use case | r | alpha | target_modules |
|---|---|---|---|
| Style/tone adjustment | 8 | 16 | q_proj, v_proj |
| Domain knowledge (7B) | 16–32 | 32–64 | all attention + MLP |
| Tool-use / function calling | 32 | 64 | all linear layers |
| Full behavior change | 64+ | 128 | all linear layers |

Rule of thumb: `alpha = 2 × r`. Higher rank increases trainable params and VRAM — 7B model with r=16 adds ~4M params vs r=64 adding ~16M.

```python
LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                     "gate_proj", "up_proj", "down_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)
```

For QLoRA, 4-bit base + r=16 typically fits 7B on 24GB GPU.

## Multi-adapter serving

Production often needs domain-specific adapters on one base model:

```bash
# vLLM: load multiple LoRA adapters
vllm serve meta-llama/Llama-3.1-8B \
  --enable-lora \
  --lora-modules legal=./adapters/legal medical=./adapters/medical \
  --max-lora-rank 64
```

Route requests by domain header or classifier. Adapter swap at inference is microseconds — no model reload required.

Track adapter-base compatibility: document which base model hash each adapter was trained against. Upgrading base without retraining adapters causes silent quality degradation.

## QLoRA vs full LoRA tradeoffs

| | QLoRA (4-bit base) | LoRA (fp16 base) |
|---|---|---|
| VRAM (7B) | ~10GB | ~20GB |
| Training speed | Slower (dequant overhead) | Faster |
| Final quality | 95–98% of full LoRA | Baseline |
| Merge to fp16 | Required before merge | Direct merge |

For experimentation and iteration, QLoRA wins on hardware cost. For final production adapter, consider full LoRA fine-tune on the best hyperparameters found via QLoRA.

## Failure modes

- **Wrong target_modules for architecture** — GQA models (Llama 3) use different layer names than MHA (Llama 2)
- **Adapter trained on 4-bit, deployed merged without re-eval** — quality gap vs QLoRA checkpoint
- **Rank too low for task complexity** — model can't learn domain; increase r before adding data
- **No adapter versioning** — base model upgrade breaks all adapters silently
- **Saving adapter without adapter_config.json** — cannot reload or merge

## Production checklist

- Target modules verified for model architecture
- Eval on held-out set before and after merge
- Adapter artifacts versioned with base model hash
- vLLM or compatible serving for multi-adapter deployment
- Rollback: previous adapter tagged in model registry
- Post-quantization eval if deploying INT8/INT4 merged model

Merge LoRA adapters and run regression eval before production deploy — merged weights behave differently than adapter-at-inference paths.

Track adapter rank and target module choices in experiment metadata — rank-8 on `q_proj` only vs rank-16 on all attention layers produces incomparable eval results across runs.

## Resources

- [LoRA paper (Hu et al.)](https://arxiv.org/abs/2106.09685)
- [QLoRA paper (Dettmers et al.)](https://arxiv.org/abs/2305.14314)
- [PEFT library documentation](https://huggingface.co/docs/peft)
- [bitsandbytes quantization](https://github.com/TimDettmers/bitsandbytes)
- [vLLM LoRA serving](https://docs.vllm.ai/en/latest/models/lora.html)
