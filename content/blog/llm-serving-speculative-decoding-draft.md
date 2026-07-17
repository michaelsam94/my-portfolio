---
title: "Speculative Decoding with Draft Models"
slug: "llm-serving-speculative-decoding-draft"
description: "Speed up LLM token generation with speculative decoding: how draft models propose tokens and target models verify them in parallel for 2-3× throughput gains."
datePublished: "2025-03-05"
dateModified: "2026-07-17"
tags:
keywords: "speculative decoding, draft model LLM, Medusa speculative decoding, EAGLE draft model, LLM inference acceleration, token verification"
faq:
  - q: "How much faster is speculative decoding in practice?"
    a: "With a well-matched draft model, acceptance rates of 60–80% are common, yielding 1.8–3× speedup on decode-heavy workloads. Speedup depends on draft-target agreement, draft model speed, and batch size. If the draft model diverges from the target's distribution, acceptance drops and you gain little."
  - q: "Do I need a separate model for the draft?"
    a: "Usually yes, but it can be much smaller — a 1B draft for a 70B target is typical. Some approaches like Medusa add lightweight prediction heads to the target model itself, avoiding a second full model load. EAGLE trains a small autoregressive head on the target's hidden states."
  - q: "Does speculative decoding change the output distribution?"
    a: "Standard speculative decoding with rejection sampling produces tokens from the exact same distribution as autoregressive decoding from the target model alone. It is mathematically equivalent — just faster. Approximate methods that skip rejection sampling may introduce slight distribution shifts."
---
Autoregressive LLM inference generates one token at a time. Each step requires a full forward pass through billions of parameters, and most of that time is spent waiting on memory bandwidth, not compute. Speculative decoding breaks the one-token-at-a-time bottleneck by having a small, fast draft model guess several tokens ahead, then asking the large target model to verify all guesses in a single parallel forward pass.

When the draft model agrees with what the target would have produced, you advance multiple tokens for the cost of one verification step. When it disagrees, you reject from the first mismatch and resume. Done correctly, the output distribution is identical to plain autoregressive decoding — just produced faster.

## The algorithm step by step

1. Draft model generates γ candidate tokens autoregressively (γ = 3–8 typically).
2. Target model runs one forward pass on the draft prefix, computing logits for all γ positions in parallel.
3. Compare draft tokens against target logits using rejection sampling.
4. Accept matching tokens; reject from the first mismatch onward.
5. Sample one correction token from the adjusted distribution at the rejection point.
6. Repeat.

```
Draft:   [The] [cat] [sat] [on]
Target:  [The] [cat] [dog] ✗  → accept "The cat", reject "sat", resample
Output:  [The] [cat] [dog] ...
```

The target model's parallel verification is the key insight. Transformer attention computes all positions simultaneously during prefill-style passes, so verifying five draft tokens costs roughly the same as generating one token autoregressively.

## Choosing a draft model

The draft model must be fast enough that drafting γ tokens takes less time than the target would take to generate one. Common pairings:

| Target | Draft | Typical acceptance rate |
|--------|-------|------------------------|
| Llama 3.1 70B | Llama 3.2 1B | 65–75% |
| Mistral 7B | Mistral 7B (Medusa heads) | 70–80% |
| Custom fine-tune | Same architecture, earlier checkpoint | 60–70% |

Same-tokenizer, same-vocabulary models are mandatory. A draft model trained on a different tokenizer cannot produce valid token sequences for the target to verify.

For domain-specific targets, fine-tune a small draft model on the same data. A generic 1B model drafting for a fine-tuned 70B legal assistant might accept only 40% of tokens because domain vocabulary diverges.

## Implementing with vLLM

vLLM supports speculative decoding via a draft model configuration:

```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3.1-70B-Instruct",
    speculative_model="meta-llama/Llama-3.2-1B-Instruct",
    num_speculative_tokens=5,
    use_v2_block_manager=True,
)

outputs = llm.generate("Explain quantum entanglement", SamplingParams(max_tokens=256))
```

Key parameters:

- `num_speculative_tokens`: how many tokens the draft proposes per round. Higher values increase potential speedup but also wasted computation on rejection.
- `speculative_model`: path to the draft checkpoint.

Monitor `spec_accept_rate` in vLLM metrics. Below 50%, your draft model is mismatched — either switch drafts or reduce `num_speculative_tokens`.

## Medusa: draft heads without a second model

Medusa attaches additional classification heads to the target model's hidden states. Each head predicts a token at a future position (head 1 → t+1, head 2 → t+2, etc.). This avoids loading a second model entirely:

```
Hidden state at t → Head₁ → token t+1
                   → Head₂ → token t+2
                   → Head₃ → token t+3
```

Medusa heads are lightweight (small MLPs) and trained with a distillation objective against the target's own predictions. Trade-off: heads are tied to the specific target checkpoint and require retraining when you update the base model.

## EAGLE: learned draft from hidden states

EAGLE (Extrapolation Algorithm for Greater LLM Efficiency) trains a small autoregressive model that conditions on the target's top-layer hidden states. It achieves higher acceptance rates than independent draft models because it sees the target's internal representations:

```python
# Conceptual EAGLE flow
hidden = target_model.forward(tokens).last_hidden_state
draft_tokens = eagle_model.generate(hidden, num_tokens=5)
accepted = target_model.verify(tokens + draft_tokens)
```

EAGLE-2 and EAGLE-3 improved acceptance rates further with dynamic draft length adjustment — proposing fewer tokens when uncertainty is high.

## When speculative decoding does not help

Skip it when:

- **Prefill dominates:** short prompts with long completions benefit most. If your workload is mostly short outputs from long inputs, prefill optimization (prefix caching) matters more.
- **Batch size is large:** at high concurrency, the GPU is already saturated and speculative overhead adds latency without throughput gain.
- **Draft-target mismatch:** a poorly chosen draft model wastes compute on rejected tokens.

Profile your workload's decode-to-prefill ratio before investing in draft model infrastructure.

## Common production mistakes

Teams get serving speculative decoding draft wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around serving speculative decoding draft break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When serving speculative decoding draft misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Fast Inference from Transformers via Speculative Decoding (Leviathan et al.)](https://arxiv.org/abs/2211.17192)
- [Medusa: Simple Framework for Accelerating LLM Generation](https://arxiv.org/abs/2401.10774)
- [EAGLE: Speculative Sampling Requires Rethinking Feature Uncertainty](https://arxiv.org/abs/2401.15077)
- [vLLM speculative decoding documentation](https://docs.vllm.ai/en/latest/models/spec_decode.html)
- [Google Research blog on speculative decoding](https://research.google/blog/looking-back-at-speculative-decoding/)
