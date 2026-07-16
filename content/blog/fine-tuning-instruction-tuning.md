---
title: "Instruction Tuning from Scratch"
slug: "fine-tuning-instruction-tuning"
description: "Build instruction-tuned models from base checkpoints: dataset mixing, chat templates, supervised fine-tuning hyperparameters, and eval for instruction following."
datePublished: "2026-02-20"
dateModified: "2026-02-20"
tags: ["AI", "Machine Learning", "Fine-Tuning", "LLM"]
keywords: "instruction tuning LLM, supervised fine-tuning SFT, chat template training, instruction dataset mixing, Llama fine-tune instructions, TRL SFTTrainer, instruction following eval"
faq:
  - q: "What is the difference between pretraining and instruction tuning?"
    a: "Pretraining predicts next tokens on raw text corpora — the model learns language and world knowledge but not conversational obedience. Instruction tuning (supervised fine-tuning on prompt-response pairs) teaches the model to follow user instructions, use chat formats, and behave helpfully in dialog — it is the step that turns a base model into an assistant."
  - q: "Should I instruction-tune a base model or start from an instruct checkpoint?"
    a: "Start from an existing instruct model for domain adaptation — faster and less forgetting. Tune a base model from scratch when you need full control over system behavior, proprietary chat format, or languages underserved by public instruct models — at higher compute and data requirements."
  - q: "How many instruction examples are enough for SFT?"
    a: "Public recipes like LIMA suggest ~1k high-quality examples can induce strong instruction following; production domain assistants often use 5k–50k curated pairs after quality filtering. Monitor validation loss and task-specific eval — more low-quality data hurts."
---

Base Llama completes "The capital of France is" with encyclopedic continuation — not "Paris, as you asked in your travel planning question." Instruction tuning closes that gap by supervised fine-tuning on thousands of `(instruction, response)` pairs so the model learns that user messages demand direct, task-shaped answers in a chat template. Whether you are adapting Mistral-Instruct to healthcare triage or building a private assistant from Llama-Base, instruction tuning is the first alignment layer before DPO or RLHF — and the layer most sensitive to dataset garbage and template mismatches.

## Base vs instruct starting point

| Start | When |
|-------|------|
| `*-Instruct` checkpoint | Domain adaptation, style, tools — most products |
| Base model | Full behavioral control, custom languages, research |

Instruct models already know roles; you add domain. Base models need general instruction capability mixed in:

```python
mix = {
    "domain": 0.7,
    "general_open_orca_sample": 0.2,
    "format_json_tool": 0.1,
}
```

Skipping general mix on base → brittle domain parrot.

## Chat template consistency

Tokenizer chat template must match inference:

```python
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3.1-8B-Instruct")

messages = [
    {"role": "system", "content": "You are a concise legal summarizer."},
    {"role": "user", "content": "Summarize clause 4 in plain English."},
    {"role": "assistant", "content": "Clause 4 requires..."},
]

text = tokenizer.apply_chat_template(messages, tokenize=False)
# train on `text` with labels masking non-assistant tokens
```

Mask loss on user/system tokens — train only assistant completion:

```python
labels = input_ids.copy()
labels[:assistant_start_token] = -100  # ignore in loss
```

Wrong masking trains model to predict user prompts — leakage weirdness.

## SFT with TRL

```python
from trl import SFTConfig, SFTTrainer
from datasets import load_dataset

dataset = load_dataset("json", data_files="instr_train.jsonl")

training_args = SFTConfig(
    output_dir="sft-out",
    num_train_epochs=2,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-5,
    max_seq_length=4096,
    packing=True,  # efficient short examples
    dataset_text_field=None,  # use formatting_func
)

def formatting_func(example):
    return tokenizer.apply_chat_template(example["messages"], tokenize=False)

trainer = SFTTrainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["validation"],
    processing_class=tokenizer,
    formatting_func=formatting_func,
)
trainer.train()
```

Use LoRA for 7B+ on consumer GPUs; full fine-tune only with budget and anti-forgetting eval.

## Hyperparameter starting points (7B LoRA)

| Param | Starting range |
|-------|----------------|
| Learning rate | 1e-5 – 2e-4 |
| Epochs | 1–3 |
| LoRA r | 8–32 |
| Warmup | 3–10% steps |
| Weight decay | 0.01 |

Early stop on validation loss **and** instruction eval — overfitting memorizes training phrasing.

## Evaluation suite

- **MT-Bench / domain golden set** — multi-turn
- **IFEval** — verifiable instruction constraints (word count, JSON keys)
- **Exact tool-call parse rate** — if agents
- **Toxicity/refusal** — safety regression

Qualitative error buckets weekly: "too verbose", "ignored context", "hallucinated citation."

## Instruction tuning vs DPO ordering

Standard pipeline:

1. **SFT** — teach format and domain knowledge
2. **DPO/RLHF** — refine preferences (tone, helpfulness trade-offs)

DPO without SFT on base for complex domains often underperforms — model lacks foundation to distinguish good/bad within format.

## Common mistakes

- Training on prompts without system policy you deploy with
- Max length truncating tail of long context examples silently
- Duplicate near-identical instructions → overfit phrasing
- Evaluating with different temperature than production

Instruction tuning is dataset engineering first — hyperparameters second.

## Dataset quality over quantity

LIMA showed 1,000 high-quality examples can outperform 52,000 mediocre ones. Quality criteria for instruction examples:

- **Correct** — verified answer, not hallucinated
- **Diverse** — cover task types, not 500 variations of "summarize this"
- **Formatted** — match production chat template exactly
- **Scoped** — include system prompt policy you deploy with
- **Challenging** — include edge cases, not just easy wins

```json
{
  "messages": [
    {"role": "system", "content": "You are a helpful coding assistant. Be concise."},
    {"role": "user", "content": "Write a Python function to merge two sorted lists."},
    {"role": "assistant", "content": "def merge(a, b):\n    result = []\n    i = j = 0\n    ..."}
  ]
}
```

Every training example should use the exact system prompt and chat template deployed in production.

## Multi-turn instruction datasets

Single-turn SFT teaches format; multi-turn teaches context maintenance:

```json
{
  "messages": [
    {"role": "user", "content": "What's the capital of France?"},
    {"role": "assistant", "content": "Paris."},
    {"role": "user", "content": "What's its population?"},
    {"role": "assistant", "content": "Paris has approximately 2.1 million people in the city proper."}
  ]
}
```

Include 30–50% multi-turn examples in domain datasets. Models trained only on single-turn fail at conversation context.

## Production deployment checklist

After SFT, validate before deploy:

- Run IFEval or domain golden set — instruction following rate
- Compare base vs SFT on held-out eval set — ensure improvement, not regression
- Test with production system prompt and chat template
- Safety eval — refusal rate on harmful prompts unchanged or improved
- Latency benchmark — SFT shouldn't change inference speed (same model size)
- Rollback plan — keep previous model weights tagged in registry

## Failure modes

- **Training/eval template mismatch** — train with Llama template, deploy with ChatML
- **System prompt not in training data** — model ignores system instructions at inference
- **Overfitting to training phrasing** — model parrots exact training responses
- **Truncated long examples** — tail of context window cut silently during training
- **No held-out eval set** — overfit discovered only in production

## Production checklist

- Chat template matches production deployment exactly
- System prompt included in every training example
- 1k+ diverse, verified examples minimum for domain SFT
- Multi-turn examples included (30%+ of dataset)
- Held-out eval set with IFEval or domain golden set
- LoRA for 7B+ models; full fine-tune only with budget
- Previous model version tagged for rollback

## Common production mistakes

Teams get fine tuning instruction tuning wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of fine tuning instruction tuning fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [TRL SFTTrainer documentation](https://huggingface.co/docs/trl/sft_trainer)
- [LIMA: Less Is More for Alignment](https://arxiv.org/abs/2305.11206)
- [Alpaca instruction tuning dataset](https://github.com/tatsu-lab/stanford_alpaca)
- [Chat templates (Hugging Face)](https://huggingface.co/docs/transformers/chat_templating)
- [IFEval instruction following benchmark](https://arxiv.org/abs/2311.07911)
