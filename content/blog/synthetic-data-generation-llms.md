---
title: "Generating Synthetic Training Data with LLMs"
slug: "synthetic-data-generation-llms"
description: "Synthetic data generation with LLMs builds fine-tuning sets, evals, and augmentations fast — how to do it without model collapse or quality loss."
datePublished: "2026-03-01"
dateModified: "2026-03-01"
tags: ["LLM", "Machine Learning", "Data"]
keywords: "synthetic data, LLM data generation, distillation, data augmentation, fine-tuning data, evaluation sets"
faq:
  - q: "What is synthetic data generation with LLMs?"
    a: "It's using a language model to produce artificial training or evaluation examples — instructions, question-answer pairs, labeled classifications, or edge cases — instead of collecting and hand-labeling them from real sources. A strong 'teacher' model generates the data, which is then used to fine-tune a smaller 'student' model, build evaluation sets, or augment a scarce real dataset. It trades human labeling cost and time for model inference cost and a quality-control problem."
  - q: "What is model collapse and how do I avoid it?"
    a: "Model collapse is the degradation that happens when models are trained repeatedly on their own or other models' outputs, causing them to lose diversity and drift toward bland, average text. You avoid it by anchoring synthetic data to real seed data, enforcing diversity through varied prompts and personas, aggressively filtering low-quality samples, and mixing synthetic with real data rather than training on synthetic alone."
  - q: "Is it legal and allowed to train on another model's outputs?"
    a: "It depends on the provider's terms of service, which often restrict using their model's outputs to train competing models. Always check the license and terms of the teacher model before distilling from it, and prefer open-weight models with permissive licenses when the intent is to train and release a student model. This is a business and legal decision, not just a technical one."
---

You need 10,000 labeled examples to fine-tune a classifier, an eval set that covers the weird edge cases your users hit, or more variety in a dataset that's too small. Hand-labeling that is slow and expensive. Synthetic data generation with LLMs is the shortcut: point a strong model at the problem and have it *generate* the examples — instruction/response pairs, labeled samples, adversarial edge cases — then use them to train a smaller model, build evaluations, or pad a thin dataset. Done well it collapses weeks of labeling into hours. Done carelessly it teaches your model to be confidently mediocre.

I've used this to bootstrap datasets that would've been impractical to collect manually, and I've also watched a synthetic set quietly poison a fine-tune. The difference is entirely in the quality control, so that's where most of this article lives.

## What it's actually good for

Three use cases dominate, and they have different risk profiles:

- **Distillation** — a large teacher model generates high-quality outputs that fine-tune a smaller, cheaper student. This is how a lot of capable small models get their manners.
- **Evaluation sets** — generate test cases, especially edge cases and adversarial inputs, to stress a system. Lower risk, because a human still judges the results and you're not training on them.
- **Augmentation** — expand a small real dataset with paraphrases, variations, and synthesized minority-class examples to fix class imbalance.

Notice that eval generation is the safest starting point: bad synthetic evals waste a review pass, while bad synthetic *training* data changes your model's behavior. If you're new to this, generate evals first and build trust before you let synthetic data touch a fine-tune.

## The core recipe

A basic generation pipeline looks like this, and the structure matters more than the specific prompt:

```python
def generate_examples(teacher, seed_topics, n_per_topic):
    dataset = []
    for topic in seed_topics:
        for _ in range(n_per_topic):
            prompt = build_prompt(
                topic=topic,
                persona=random.choice(PERSONAS),   # vary the voice
                difficulty=random.choice(LEVELS),   # vary the difficulty
                style=random.choice(STYLES),
            )
            example = teacher.generate(prompt)
            if passes_filters(example):             # never skip this
                dataset.append(example)
    return dedupe(dataset)
```

Two design choices carry the whole thing. First, **seed and vary** — start from real seed topics or documents and inject controlled randomness (personas, difficulty, style) so you don't get 10,000 near-identical samples. Second, **filter before you keep** — generation is cheap, so over-generate and throw away aggressively.

## The enemy: model collapse and blandness

The failure mode that ruins synthetic data is **model collapse** — the well-documented degradation that occurs when models train on model-generated text. Each generation loses a little diversity, drifts toward the average, and forgets the tails of the distribution. Train a model purely on another model's output over enough iterations and it converges to bland, samey, low-entropy text.

The practical defenses:

- **Anchor to real data.** Seed generation from real documents, real questions, or a real taxonomy so the synthetic set inherits real structure.
- **Force diversity.** Vary personas, difficulty, phrasing, and length explicitly. Left alone, LLMs are repetitive; you have to fight it in the prompt.
- **Mix, don't replace.** Blend synthetic with real data rather than training on synthetic alone. A synthetic-heavy set anchored by real examples is far safer than a pure one.
- **Filter hard.** Deduplicate near-identical samples (embedding-based clustering helps), drop malformed outputs, and remove anything that fails a quality check.

## Quality control is the whole job

Generating text is easy; generating *good, diverse, correct* text is the actual work. The QC tactics I lean on, cheapest first:

| Technique | Catches | Cost |
| --- | --- | --- |
| Schema/format validation | Malformed outputs, missing fields | Free |
| Deduplication (exact + semantic) | Repetition, low diversity | Cheap |
| LLM-as-judge scoring | Low-quality or off-topic samples | Moderate (extra calls) |
| Verification/execution | Wrong answers (code, math, facts) | Varies |
| Human spot-check | Everything the above miss | Expensive but essential |

The highest-leverage one people skip is **verification** for verifiable domains. If you're generating code examples, run them. If you're generating math, check the answers. If you're generating classifications, use a separate judge model and keep only samples where generation and judgment agree. For non-verifiable text, LLM-as-judge plus a human spot-check on a sample is the realistic bar. This measurement mindset is the same one that underpins good [retrieval evaluation metrics for RAG](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/) — you can't trust data you haven't measured, synthetic or not.

## Where it fits versus the alternatives

Synthetic data is one option among several for adapting a model to your problem, and it's worth being clear about when it's the right one. If you mainly need the model to *know* your facts, retrieval is usually better than baking facts into weights; if you need it to *behave* a certain way, fine-tuning on good examples wins. I laid out that decision in [fine-tuning vs. RAG vs. prompting](https://blog.michaelsam94.com/fine-tuning-vs-rag-vs-prompting/), and synthetic data is what makes the fine-tuning path affordable — it's the supply chain for the training examples, not a substitute for deciding whether you should fine-tune at all.

The distillation case deserves a specific caution: generating training data from a proprietary model to train a competitor is often *prohibited by that model's terms of service*. This is a legal and business call, not just a technical one — check the license, and prefer permissively-licensed open-weight teachers when your student model will ship. I've seen teams build impressive pipelines on shaky legal ground and have to rip them out.

## My practical advice

If I were bootstrapping a dataset today:

1. **Start with evals**, not training data. Lower risk, faster feedback, builds intuition for the teacher's quality.
2. **Seed from real data** and vary aggressively — personas, difficulty, format. Diversity is a design requirement, not an accident.
3. **Over-generate and filter ruthlessly.** Assume 30–50% of raw generations aren't good enough to keep, and build the filters to prove it.
4. **Verify anything verifiable**, judge the rest, spot-check by hand.
5. **Blend with real data** and never train on pure synthetic if you can avoid it.
6. **Check the license** before you distill from anyone else's model.

Used with that discipline, synthetic data is genuinely transformative — it makes datasets exist that otherwise wouldn't. Skip the QC and diversity work and you've built an efficient machine for teaching your model to be average. The generation is the easy 10%; the filtering, verification, and diversity engineering are the 90% that decides whether the result is worth training on.

## Resources

- [Self-Instruct: Aligning Language Models with Self-Generated Instructions (arXiv)](https://arxiv.org/abs/2212.10560)
- [The Curse of Recursion: Training on Generated Data Makes Models Forget (model collapse, arXiv)](https://arxiv.org/abs/2305.17493)
- [Textbooks Are All You Need (phi models, synthetic data, arXiv)](https://arxiv.org/abs/2306.11644)
- [WizardLM: Empowering LLMs to Follow Complex Instructions (Evol-Instruct, arXiv)](https://arxiv.org/abs/2304.12244)
- [Hugging Face — synthetic data generation cookbook](https://huggingface.co/learn/cookbook/en/synthetic_data_generator)
