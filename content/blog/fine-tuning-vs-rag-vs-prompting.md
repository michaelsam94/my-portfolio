---
title: "Fine-Tuning vs RAG vs Prompting: A Decision Framework"
slug: "fine-tuning-vs-rag-vs-prompting"
description: "Fine-tuning vs RAG vs prompting decision framework: what each changes, when to use which, LoRA tradeoffs, and why most teams need RAG before fine-tuning."
datePublished: "2026-01-22"
dateModified: "2026-01-22"
tags: ["LLM", "RAG", "Fine-Tuning", "Architecture"]
keywords: "fine-tuning vs RAG, when to fine-tune, RAG vs fine-tuning, LLM customization, prompting, LoRA"
faq:
  - q: "Should I fine-tune or use RAG?"
    a: "Use RAG when you need the model to know specific, changing, or proprietary facts — it injects knowledge at query time. Fine-tune when you need to change the model's behavior, format, or style consistently. They solve different problems, and RAG is the right first move for most knowledge use cases."
  - q: "Does fine-tuning add knowledge to a model?"
    a: "Not reliably. Fine-tuning is good at shaping behavior, tone, and output format, but it's a poor and expensive way to inject facts — the model may still hallucinate and your data goes stale the moment your knowledge changes. For factual grounding, RAG is the better tool."
  - q: "What is the cheapest way to customize an LLM?"
    a: "Prompting. Start with a well-engineered prompt and few-shot examples before anything else — it has zero training cost, iterates in seconds, and solves a surprising share of use cases. Move to RAG or fine-tuning only when prompting demonstrably falls short."
---

The question comes up on nearly every LLM project: should we fine-tune the model? Usually the honest answer is "not yet, and maybe never." Fine-tuning is the technique teams reach for first and need least. The framework I use is simple once you internalize what each approach actually changes:

- **Prompting** changes *what you ask* — instructions and examples in the context.
- **RAG** changes *what the model knows at query time* — it retrieves relevant facts and injects them.
- **Fine-tuning** changes *how the model behaves* — it adjusts the weights to shift style, format, and task patterns.

Get that distinction right and most decisions make themselves. The classic mistake is fine-tuning to teach the model facts, which it does poorly and expensively, when RAG would have done it better and cheaper. Let me lay out the framework.

## Start with prompting, always

Prompting is the cheapest, fastest lever, and it's shocking how far it goes. Zero training cost, iteration measured in seconds, and no infrastructure. Before considering anything heavier, push prompting hard:

- Clear, specific instructions and a defined role.
- Few-shot examples showing the exact input/output pattern you want.
- Structured output constraints so parsing is reliable — see [structured outputs and function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/).
- [Context engineering](https://blog.michaelsam94.com/context-engineering-beyond-prompts/) to give the model the right information in the right shape.

A huge fraction of "we need to fine-tune" turns out to be "our prompt was vague." Exhaust prompting first, and measure the result with real [evals](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/) so you know whether you actually have a gap.

## Reach for RAG when the model needs to know things

If the shortfall is *knowledge* — the model doesn't know your product docs, your customer's order history, last week's policy change — the answer is [RAG](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/), not fine-tuning. RAG retrieves relevant information at query time and puts it in the context, which gives you three things fine-tuning can't:

- **Freshness.** Update the knowledge base and the model's answers update immediately. No retraining.
- **Attribution.** You can cite the source chunk, which matters enormously for trust and debugging.
- **Access control.** You can filter retrieval by the user's permissions, so the model only "knows" what that user is allowed to see.

Fine-tuning bakes knowledge into weights, where it goes stale, can't be cited, and can't be permission-filtered. For anything factual, proprietary, or changing, RAG wins. This is why I tell teams: RAG before fine-tuning for knowledge, nearly every time.

## Fine-tune when you need to change behavior

Fine-tuning earns its cost when the problem is *behavior*, not knowledge. Legitimate cases:

- **Consistent format or style** the model won't reliably hold from prompting alone — a specific JSON shape, a house tone, a domain's phrasing.
- **A specialized task** done at high volume where a smaller fine-tuned model matches a large prompted one at a fraction of the cost and latency.
- **Prompt compression.** If you're spending 2,000 tokens of instructions on every call, fine-tuning that behavior in can slash per-request cost.
- **A narrow classification or extraction task** where you have thousands of labeled examples.

Note the pattern: these are about *how* the model responds, learned from many examples, not *what it knows*. With modern **LoRA** and QLoRA, fine-tuning is far cheaper than it used to be — you train a small adapter rather than all the weights, often for tens of dollars on a rented GPU. But you still need a quality dataset (hundreds to thousands of examples), an eval to prove it helped, and a retraining pipeline for when the base model updates.

## The decision table

Here's the framework condensed:

| Need | Use | Why |
| --- | --- | --- |
| Better instructions, quick iteration | Prompting | Zero cost, seconds to change |
| Specific/fresh/proprietary facts | RAG | Freshness, citation, access control |
| Consistent format, tone, or task style | Fine-tuning | Behavior baked into weights |
| High volume, narrow task, lower cost | Fine-tuning (small model) | Cheaper, faster inference |
| Facts + behavior | RAG + fine-tuning | They compose |

That last row matters: these aren't mutually exclusive. A production system often fine-tunes a model for a consistent output format *and* uses RAG to feed it current facts. They operate on different axes and stack cleanly.

## Cost and effort, realistically

Ranked from cheapest to most involved:

1. **Prompting** — minutes, no infra, iterate live.
2. **RAG** — days to weeks; the work is in the retrieval pipeline (chunking, embeddings, [vector store](https://blog.michaelsam94.com/vector-databases-in-production/)), plus ongoing data maintenance.
3. **Fine-tuning** — weeks; dataset curation is the real cost, then training, evaluation, and a retraining cadence tied to base-model releases.

The effort ordering is also the recommended trying order. Escalate only when the cheaper approach demonstrably fails against your evals, not on a hunch.

## A pragmatic path

For most teams building an LLM feature, the sequence is: **prompt hard, add RAG for knowledge, and fine-tune only for stubborn behavioral or cost problems.** I've watched teams spend a month fine-tuning to fix hallucinations that a two-day RAG setup would have solved — the model was never missing behavior, it was missing facts.

Diagnose the gap before you pick the tool. If the model doesn't *know* something, that's RAG. If it doesn't *do* something the way you need, consistently, at scale — that's when fine-tuning finally earns its place.

## Resources

- [OpenAI — fine-tuning guide](https://platform.openai.com/docs/guides/fine-tuning)
- [Hugging Face — PEFT (LoRA/QLoRA) documentation](https://huggingface.co/docs/peft/index)
- [Anthropic — prompt engineering guide](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
- [QLoRA paper (arXiv)](https://arxiv.org/abs/2305.14314)
- [Retrieval-Augmented Generation paper (arXiv)](https://arxiv.org/abs/2005.11401)
- [Google AI — Gemini fine-tuning docs](https://ai.google.dev/gemini-api/docs/model-tuning)
