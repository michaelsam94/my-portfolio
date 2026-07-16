---
title: "Speculative Decoding to Speed Up LLM Inference"
slug: "speculative-decoding-llm-inference"
description: "Speculative decoding speeds up LLM inference: a small draft model guesses tokens the big model verifies in one pass — 2-3x faster, same output."
datePublished: "2026-02-27"
dateModified: "2026-02-27"
tags: ["LLM", "Inference", "Performance"]
keywords: "speculative decoding, draft model, LLM inference speed, token acceptance, medusa, EAGLE"
faq:
  - q: "What is speculative decoding?"
    a: "Speculative decoding is an inference technique where a small, fast 'draft' model proposes several tokens ahead, and the large 'target' model verifies all of them in a single forward pass. Because the big model can check multiple guessed tokens at once instead of generating them one at a time, you get the same output distribution at 2-3x the speed. The math guarantees the final tokens are exactly what the target model would have produced on its own."
  - q: "Does speculative decoding change the model's output?"
    a: "No, not when implemented correctly. The verification step uses a rejection-sampling scheme that preserves the target model's exact output distribution, so the generated text is statistically identical to standard decoding. This is the key selling point over lossy speedups like aggressive quantization — you pay in complexity and draft-model overhead, not in quality."
  - q: "When does speculative decoding fail to help?"
    a: "It helps least when the draft model rarely agrees with the target — high-entropy, creative, or out-of-distribution text — because most speculated tokens get rejected and you've paid for the draft passes with nothing to show. It also struggles at very large batch sizes, where the target model is already compute-bound and the extra verification work competes for the same GPU cycles. It shines in low-batch, latency-sensitive, predictable-text scenarios."
---

Speculative decoding is one of those rare optimizations that feels like cheating: you make a large language model generate tokens 2–3x faster without changing a single output token. The trick is to stop generating one token at a time. A small, cheap "draft" model guesses several tokens ahead, and the big "target" model verifies that whole guess in one forward pass — accepting the run of tokens it agrees with and correcting the first one it doesn't.

The reason it works is a mismatch in how transformers spend time. Generating a token is *memory-bound* — you're mostly moving weights, not doing heavy math — so verifying five tokens at once costs almost the same as generating one. Speculative decoding exploits exactly that slack. Here's how the pieces fit and where it quietly stops paying off.

## The core idea: guess, then verify

Standard autoregressive decoding is strictly sequential: token N must exist before you can compute token N+1. That serialization is the bottleneck, not raw compute — for a single request the GPU is underutilized because it's waiting on memory reads.

Speculative decoding breaks the serialization:

1. A **draft model** (small, fast) generates a candidate continuation of, say, 5 tokens.
2. The **target model** (large, accurate) runs one forward pass over the prompt plus those 5 draft tokens.
3. A verification step walks the draft left to right, accepting each token that matches what the target would have sampled, and rejecting from the first mismatch onward.
4. The rejected position is resampled from the target's own distribution, so correctness is preserved.

Best case, all 5 tokens are accepted and you got 5 tokens for the price of roughly one target pass. Worst case, only the first is accepted and you've wasted the draft work. Real workloads land in between.

## Why it's mathematically lossless

The part people distrust: "if a small model is guessing, isn't the output worse?" No — and this is the elegant bit. The verification uses a modified rejection-sampling scheme that provably reproduces the target model's exact output distribution. The draft model only affects *speed*, never *which* tokens come out. A draft that's usually right makes you fast; a draft that's usually wrong makes you slow, but never wrong.

That's a fundamentally different tradeoff from quantization, which trades quality for speed. Speculative decoding trades *complexity and some wasted compute* for speed while holding quality fixed. If you've already accepted quality loss elsewhere in your stack — say aggressive KV cache quantization, which I covered in [KV cache optimization for LLM serving](https://blog.michaelsam94.com/kv-cache-optimization-llm-serving/) — speculative decoding is a nice complement because it gives back latency without spending any more quality budget.

## Acceptance rate is everything

The single number that determines whether speculative decoding helps is the **acceptance rate** — the fraction of drafted tokens the target accepts. The expected speedup is roughly the average number of tokens accepted per verification pass, discounted by the draft model's cost.

```python
# Simplified intuition, not production code
def expected_speedup(accept_rate, gamma, draft_cost_ratio):
    # gamma = tokens drafted per step
    # accept_rate = per-token probability of acceptance
    accepted = (1 - accept_rate ** (gamma + 1)) / (1 - accept_rate)
    target_passes = 1
    total_cost = target_passes + gamma * draft_cost_ratio
    return accepted / total_cost
```

Two levers fall out of this. First, the draft must be *aligned* with the target — trained on similar data, ideally distilled from it. A random small model gives a low acceptance rate and no speedup. Second, the draft must be genuinely *cheap*; if it's 20% the cost of the target, the `gamma * draft_cost_ratio` term eats your savings.

## The variants: draft models, Medusa, EAGLE

There are three families worth knowing, and they trade off differently:

| Approach | How it drafts | Pros | Cons |
| --- | --- | --- | --- |
| Draft model (classic) | A separate small model | Simple, model-agnostic | Needs a well-aligned small model |
| Medusa | Extra decoding heads on the target itself | No separate model to serve | Requires training heads; tree attention |
| EAGLE | Lightweight autoregressive head over target features | High acceptance, strong speedups | More involved training |

Classic draft-model speculation is the easiest to reason about and deploy if you already have a small sibling model (e.g. a 1B alongside a 70B from the same family). **Medusa** avoids the second model entirely by bolting extra prediction heads onto the target and verifying a *tree* of candidates. **EAGLE** predicts at the feature level rather than the token level and currently posts some of the best acceptance rates. If I were choosing today for a hosted deployment, I'd reach for EAGLE-style methods when I can train, and a distilled draft model when I can't.

## Where it stops paying off

Speculative decoding is not a universal win, and vendors rarely say so out loud:

- **High batch sizes.** At large batch, the target model is already compute-bound — the GPU is busy, not idle. Verification now competes for the same cycles, and the memory-bound slack that made speculation cheap has evaporated. Speculative decoding is primarily a *low-batch, latency-sensitive* technique.
- **High-entropy text.** Creative writing, brainstorming, and out-of-distribution prompts have flat next-token distributions, so the draft guesses wrong often and acceptance collapses.
- **Poorly aligned drafts.** A draft from a different model family will drag acceptance down to where the overhead outweighs the gains.

This is why speculative decoding sits at odds with pure-throughput serving, which is all about cramming the batch full. The [GPU scheduling and continuous batching tradeoffs](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) matter here: speculation optimizes *per-request latency*, batching optimizes *aggregate throughput*, and the two pull in opposite directions on the same hardware. Interactive chat and agentic loops — where a human or another model is waiting on each token — are where speculative decoding earns its keep.

## Practical advice

If you're serving your own models and latency matters, turn it on and measure the acceptance rate on *your* traffic before celebrating. Pick a draft from the same family as the target. Tune `gamma` (draft length) empirically — too long wastes work when a rejection happens early, too short leaves speedup on the table; 4–8 is a common sweet spot. And don't stack it blindly with maxed-out batching; profile the combination, because one can cannibalize the other.

The honest summary: speculative decoding is a genuinely lossless 2–3x latency win for interactive workloads, backed by clean math, and it's supported out of the box in most serious serving stacks now. It's not magic for throughput-bound batch jobs, and its payoff is entirely gated by how well your draft predicts your target. Get that alignment right and it's close to a free speedup.

## Resources

- [Fast Inference from Transformers via Speculative Decoding (arXiv)](https://arxiv.org/abs/2211.17192)
- [Accelerating Large Language Model Decoding with Speculative Sampling (DeepMind, arXiv)](https://arxiv.org/abs/2302.01318)
- [Medusa: Simple LLM Inference Acceleration Framework (arXiv)](https://arxiv.org/abs/2401.10774)
- [EAGLE: Speculative Sampling Requires Rethinking Feature Uncertainty (arXiv)](https://arxiv.org/abs/2401.15077)
- [Hugging Face — assisted generation / speculative decoding docs](https://huggingface.co/docs/transformers/en/generation_strategies)
