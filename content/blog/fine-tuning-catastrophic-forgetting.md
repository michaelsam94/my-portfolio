---
title: "Avoiding Catastrophic Forgetting"
slug: "fine-tuning-catastrophic-forgetting"
description: "Prevent catastrophic forgetting when fine-tuning LLMs: replay buffers, LoRA rank choices, learning rates, elastic weight consolidation, and eval on old tasks."
datePublished: "2026-02-11"
dateModified: "2026-02-11"
tags: ["AI", "Machine Learning", "Fine-Tuning", "LLM"]
keywords: "catastrophic forgetting fine-tuning, LLM fine-tune forget pretraining, replay buffer fine-tuning, elastic weight consolidation, multi-task fine-tuning, LoRA catastrophic forgetting"
faq:
  - q: "What is catastrophic forgetting in fine-tuning?"
    a: "When a model adapts strongly to a narrow fine-tuning dataset, weights shift to minimize new task loss and degrade performance on previously learned capabilities — general reasoning, formatting, or earlier fine-tunes. The model did not unlearn data; optimization overwrote representations critical for other tasks."
  - q: "Does LoRA prevent catastrophic forgetting?"
    a: "LoRA reduces forgetting by updating low-rank adapters while freezing most base weights — preserving general capabilities better than full fine-tuning. It does not eliminate forgetting; aggressive LoRA rank, high learning rate, or too many epochs on narrow data can still damage base behavior."
  - q: "How do I detect forgetting during fine-tuning?"
    a: "Maintain a holdout eval set of general tasks (MMLU subset, instruction following, prior domain prompts) and track metrics each epoch. If general scores drop while domain scores rise, reduce learning rate, epochs, or add replay mixing."
---

You fine-tuned a 7B model on ten thousand internal support tickets — domain accuracy jumped twelve points, and suddenly it forgot how to follow JSON schema instructions it handled perfectly last week. That is catastrophic forgetting: not mystical AI amnesia, but gradient descent happily destroying general-purpose representations to minimize loss on your narrow distribution. Every fine-tuning run trades off adaptation against preservation. The job is to measure both sides and use techniques that move the Pareto frontier — not to hope a single epoch count works forever.

## Why forgetting happens

Pretrained models encode broad linguistic and reasoning structure in shared weights. Fine-tuning on specialized data applies updates ΔW that improve domain loss L_domain but increase loss on general tasks L_general.

Full fine-tuning updates all weights — high capacity to forget. Even adapter methods shift activations passing through frozen layers.

More epochs, higher learning rate, smaller diverse data → more forgetting risk.

## Evaluation harness (non-negotiable)

Before training, freeze baseline scores:

```python
eval_suites = {
    "domain_support": load_jsonl("eval/support_golden.jsonl"),
    "general_instr": load_jsonl("eval/mmlu_style_instr.jsonl"),
    "json_format": load_jsonl("eval/structured_output.jsonl"),
}

def evaluate(model, suite):
    # generation + automatic metrics or LLM judge
    ...

baseline = {name: evaluate(base_model, data) for name, data in eval_suites.items()}
```

After each epoch checkpoint:

```python
for name, data in eval_suites.items():
    score = evaluate(model, data)
    delta = score - baseline[name]
    log(name, score, delta)  # alert if general_instr delta < -0.03
```

Domain-only eval greenlights while production general behavior regresses.

## Mitigation strategies

### 1. Parameter-efficient fine-tuning (LoRA/QLoRA)

```python
from peft import LoraConfig, get_peft_model

config = LoraConfig(
    r=16,              # lower r = less capacity, often less forgetting
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.05,
)
model = get_peft_model(base_model, config)
```

Start `r=8` or `16`; increase only if underfitting domain eval.

### 2. Replay mixing

Combine domain data with general instruction sample:

```python
batch = concat(
    sample(domain_dataset, k=6),
    sample(general_instruction_pool, k=2),
)
```

Replay ratio 10–30% often stabilizes general metrics. Use diverse general pool — not duplicate of pretraining corpus necessarily, but varied task formats.

### 3. Conservative optimization

- Learning rate 1e-5 to 2e-4 for LoRA (model dependent)
- Few epochs (1–3) with early stopping on **general** eval decline
- Weight decay small but non-zero

### 4. Elastic Weight Consolidation (EWC)

Penalize changes to weights important for prior tasks:

\[
L = L_{\text{domain}} + \lambda \sum_i F_i (\theta_i - \theta_i^*)^2
\]

Fisher information F from general task gradients — research-heavy; replay often simpler in practice.

### 5. Multi-stage fine-tuning

General instruction tune → domain tune with replay → optional DPO with same replay — each stage eval both suites.

## When some forgetting is acceptable

Narrow classifiers inside enterprise with controlled prompts may tolerate general regression if guardrailed. Customer-facing assistants and coding agents cannot.

Define **acceptance thresholds** upfront: "json_format exact match ≥ 95% of baseline."

## Production monitoring post-deploy

- Shadow traffic compare base vs fine-tuned on general prompt sample
- User reports / thumbs down taxonomy
- Structured output parse failure rate spike

Rollback adapter weights without redeploying base model — keep previous LoRA artifact versioned.

## Building a general capability eval suite

Before any fine-tune, establish baseline scores on tasks the model must retain:

```python
GENERAL_EVAL = [
    {"prompt": "Summarize this in 3 bullet points: ...", "metric": "format_compliance"},
    {"prompt": "Translate to French: Hello world", "metric": "exact_match", "expected": "Bonjour le monde"},
    {"prompt": "Is this JSON valid? {...}", "metric": "classification"},
    {"prompt": "Write a Python function to reverse a string", "metric": "code_exec"},
]

def eval_general(model, suite):
    scores = {}
    for item in suite:
        output = model.generate(item["prompt"])
        scores[item["metric"]] = score_fn(item, output)
    return scores
```

Run this suite before fine-tune (baseline), after each epoch, and after deploy. Alert if any metric drops >5% from baseline.

## Replay buffer design

Mix general examples into domain training data:

```python
# 80% domain, 20% general replay
train_dataset = concatenate([
    domain_dataset.select(range(int(len(domain_dataset) * 0.8))),
    general_replay_dataset.select(range(int(len(domain_dataset) * 0.2))),
]).shuffle()
```

General replay examples should cover: instruction following, JSON output, code generation, summarization, translation. Source from the model's original instruction-tuning dataset if available — those examples are proven to maintain general capability.

For LoRA fine-tunes, even 500–1000 replay examples significantly reduce forgetting vs domain-only training.

## Layer freezing strategy

When using full fine-tune (not LoRA), freeze early layers:

```python
for name, param in model.named_parameters():
    if "layers.0" in name or "layers.1" in name:  # first 2 of 32 layers
        param.requires_grad = False
```

Early layers capture general language features; later layers capture task-specific patterns. Freezing early layers preserves general capability while allowing domain adaptation in later layers.

LoRA naturally limits forgetting by only updating low-rank adapters — prefer LoRA over full fine-tune when general capability retention matters.

## Failure modes

- **No general eval before fine-tune** — forgetting discovered only in production
- **Domain-only training data** — model loses JSON/code/translation capability
- **Full fine-tune on small domain dataset** — catastrophic forgetting guaranteed
- **No adapter versioning** — can't rollback when forgetting detected post-deploy
- **Eval with different template than training** — false regression signals

## Production checklist

- General capability eval suite established before fine-tune
- Replay buffer (15–20% general examples) in training data
- LoRA preferred over full fine-tune for capability retention
- Eval run after each epoch — early stop on general regression
- Previous adapter version tagged for rollback
- Shadow traffic comparison post-deploy for 48 hours

Evaluate base model capabilities after every fine-tune epoch — forgetting shows up on general benchmarks before your domain metrics degrade.

## Resources

- [LoRA: Low-Rank Adaptation (Hu et al.)](https://arxiv.org/abs/2106.09685)
- [Overcoming catastrophic forgetting in neural networks (EWC)](https://arxiv.org/abs/1612.00796)
- [QLoRA paper](https://arxiv.org/abs/2305.14314)
- [Hugging Face PEFT library](https://huggingface.co/docs/peft)
- [LIMA: Less Is More for Alignment (general capability reference)](https://arxiv.org/abs/2305.11206)
