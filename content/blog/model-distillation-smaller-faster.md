---
title: "Model Distillation for Smaller Models"
slug: "model-distillation-smaller-faster"
description: "Distill large language models into smaller, faster students: data generation, loss functions, evaluation traps, and when distillation beats quantization alone."
datePublished: "2025-07-15"
dateModified: "2025-07-15"
tags: ["AI", "Machine Learning", "LLM", "Optimization"]
keywords: "model distillation LLM, knowledge distillation, teacher student model, smaller faster LLM, synthetic training data"
faq:
  - q: "What is LLM distillation in practice?"
    a: "A large teacher model generates outputs (or logits) on a task-specific dataset; a smaller student model trains to match those outputs. The student learns the teacher's behavior on your domain without needing the teacher's full parameter count at inference time."
  - q: "How does distillation compare to quantization?"
    a: "Quantization shrinks the same model's weights (FP16 → INT4). Distillation trains a different, smaller architecture. They compose: distill first for capability, then quantize for speed. Quantizing alone doesn't recover skills the small model never learned."
  - q: "When does distillation fail?"
    a: "When the student is too small for the task complexity, when teacher outputs are noisy or inconsistent, when evaluation only measures format not correctness, or when the deployment task diverges from distillation data. Always benchmark on held-out real user queries."
---

We needed sub-200ms latency for a classification-and-extraction pipeline. GPT-4o hit 94% F1 but cost $0.012 per request at our volume. A 7B base model fine-tuned on 800 labeled examples reached 81% — good enough for nobody. Distillation closed the gap: the teacher labeled 40,000 synthetic examples, a 3B student trained on soft labels reached 91% F1 at one-tenth the latency. Model distillation isn't magic compression; it's transferring behavior from a model you can't afford to run into one you can.

## Teacher-student distillation basics

Classic knowledge distillation (Hinton et al.) minimizes two losses:

```
L = α · KL(softmax(z_teacher/T) || softmax(z_student/T)) + (1-α) · CE(y, z_student)
```

- **Soft label loss:** student matches teacher's probability distribution (temperature T softens peaks)
- **Hard label loss:** student still learns ground-truth labels where available

For LLMs, "distillation" often means **response-level distillation** — train the student on teacher-generated text via supervised fine-tuning (SFT), sometimes augmented with on-policy sampling from the student corrected by the teacher.

Both approaches share a requirement: **high-quality, domain-representative training data** from the teacher.

## Step 1: generate teacher data at scale

Don't distill on 500 hand-labeled rows unless your task is trivial.

```python
prompts = load_domain_prompts("support_tickets.jsonl")  # 50k real user queries

for batch in chunked(prompts, 32):
    responses = teacher_client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": p} for p in batch],
        temperature=0.3,  # lower temp for consistent labels
    )
    write_jsonl("teacher_outputs.jsonl", zip(prompts, responses))
```

Quality controls we learned the hard way:
- **Deduplicate** near-duplicate prompts (MinHash) — teacher memorization inflates eval scores
- **Filter refusals and hedging** — "I'm not sure" teaches the student to waffle
- **Stratify by difficulty** — include edge cases the teacher gets wrong; mark for human review or drop
- **Log teacher confidence** via token logprobs when available; down-weight low-confidence examples

For structured extraction, request JSON mode and reject malformed teacher outputs before they poison training.

## Step 2: choose student size and base model

| Student size | Typical use | Distillation ceiling |
|--------------|-------------|---------------------|
| 1–3B | Edge, mobile, high QPS routing | Simple classification, short extraction |
| 7–8B | Server-side copilots | Most enterprise tasks with good data |
| 14B+ | Quality-sensitive, still cheaper than frontier | Approaches teacher on narrow domains |

Start from an instruct-tuned base in the same family when possible (e.g., Llama-3.2-3B-Instruct). Random-init students need far more data.

## Step 3: training configuration

SFT on teacher outputs is the common path:

```yaml
# axolotl / LLaMA-Factory style config excerpt
model: meta-llama/Llama-3.2-3B-Instruct
datasets:
  - path: teacher_outputs.jsonl
    type: sharegpt
training:
  lr: 2e-5
  epochs: 3
  max_seq_len: 4096
  packing: true
lora:
  r: 64
  alpha: 128
  target_modules: [q_proj, v_proj, k_proj, o_proj]
```

**LoRA/QLoRA** keeps GPU memory manageable; merge adapters before deployment.

For logit-level distillation you need access to teacher logits — feasible with open teachers (Llama-70B self-distillation) but not API-only models. Response-level SFT is the practical default for closed teachers.

**Mix real labels with teacher data.** A 20/80 blend of human gold + teacher synthetic often beats 100% synthetic — anchors the student against teacher hallucinations.



**Evaluation that catches fake wins.**

Distilled models love to mimic teacher *format* while losing *factuality*.

Build eval sets from:
- Held-out **real user queries** never seen in distillation
- **Adversarial cases** where teacher previously failed (student shouldn't learn wrong answers)
- **Out-of-domain** prompts to measure refusal behavior

Track task metrics (F1, exact match), not just perplexity. We once shipped a distilled extractor that returned perfectly formatted JSON with invented field values — schema accuracy was 99%, content accuracy was 76%.

Compare against:
- Teacher (upper bound)
- Same-size base + SFT on human labels only (is distillation worth the teacher cost?)
- Quantized teacher (is distillation worth the training cost?)



**Distillation vs other compression.**

| Technique | Reduces params | Reduces latency | Preserves niche skills |
|-----------|---------------|-----------------|------------------------|
| Quantization (GPTQ/AWQ) | No | Yes | Mostly |
| Pruning | Yes | Somewhat | Risky |
| Distillation | Yes (new model) | Yes | If data is good |
| Prompt caching | No | Partial | N/A |

Our production stack: distill 70B → 8B for domain task, AWQ quantize to INT4, serve on single L4 GPU.



**Operational concerns.**

**Teacher cost upfront.** Generating 100k GPT-4o responses isn't free — budget $500–$5000 depending on output length. Still often cheaper than running the teacher at inference scale for a year.

**Drift.** When the teacher model version updates, re-distill or accept behavior shift. Version student artifacts with teacher model ID and data snapshot hash.

**Compliance.** Teacher outputs may contain PII from prompts — scrub inputs before generation, audit outputs before training.

**Cascade routing.** Run student first; escalate low-confidence requests to teacher. Distillation cost amortizes across the 85% of queries the student handles.



**When to skip distillation.**

- Task requires reasoning depth the student size can't represent (multi-hop legal analysis on 1B)
- You have abundant cheap human labels and a capable base model
- Latency budget allows a hosted 8B with aggressive quantization
- Teacher and student would see identical inference cost (distill API → API makes no sense)

Plan deployment before training finishes. Containerize the student with pinned tokenizer and chat template versions; distillation artifacts are useless if production serving uses a different prompt format than training. Set up shadow mode: run student and teacher in parallel on sampled production traffic, compare outputs offline, and promote the student only when win-rate exceeds your threshold on safety-critical fields. Budget for periodic refresh — domain language shifts (new product names, regulatory terms) degrade distilled models faster than general chat because the training distribution was frozen at distillation time. Track teacher spend as a line item; when monthly inference savings exceed amortized distillation cost, the program pays for itself.

## Resources

- [Distilling Step-by-Step (Google Research)](https://arxiv.org/abs/2305.02301)
- [Hugging Face TRL SFT trainer](https://huggingface.co/docs/trl/sft_trainer)
- [Llama 3.2 model card — distillation notes](https://github.com/meta-llama/llama-models)
- [OpenAI model distillation guide (GPT-4o mini)](https://platform.openai.com/docs/guides/distillation)
- [Axolotl fine-tuning framework](https://github.com/axolotl-ai-cloud/axolotl)
