---
title: "Speculative Decoding to Speed Up LLM Inference"
slug: "speculative-decoding-llm-inference"
description: "Speculative decoding speeds up LLM inference: a small draft model guesses tokens the big model verifies in one pass — 2-3x faster, same output."
datePublished: "2026-02-27"
dateModified: "2026-07-17"
tags: ["LLM", "Inference", "Performance"]
keywords: "speculative decoding, draft model, LLM inference speed, token acceptance, medusa, EAGLE"
faq:
  - q: "What is speculative decoding?"
    a: "Speculative decoding is an inference technique where a small, fast 'draft' model proposes several tokens ahead, and the large 'target' model verifies all of them in a single forward pass. Because the big model can check multiple guessed tokens at once instead of generating them one at a time, you get the same output distribution at 2-3x the speed. The math guarantees the final tokens are exactly what the target model would have produced on its own."
  - q: "Does speculative decoding change the model's output?"
    a: "No, not when implemented correctly. The verification step uses a rejection-sampling scheme that preserves the target model's exact output distribution, so the generated text is statistically identical to standard decoding. This is the key selling point over lossy speedups like aggressive quantization — you pay in complexity and draft-model overhead, not in quality."
  - q: "When does speculative decoding fail to help?"
    a: "It helps least when the draft model rarely agrees with the target — high-entropy, creative, or out-of-distribution text — because most speculated tokens get rejected and you've paid for the draft passes with nothing to show. It also struggles at very large batch sizes, where the target model is already compute-bound and the extra verification work competes for the same GPU cycles. It shines in low-batch, latency-sensitive, predictable-text scenarios."
faqAnswers:
  - question: "When is speculative decoding llm inference the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for speculative decoding llm inference?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back speculative decoding llm inference safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
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

## Acceptance rate monitoring

Alert below 55% acceptance — usually draft/target tokenizer mismatch after model update. Both models loaded in GPU RAM; size draft to fit with max batch KV cache — OOM mid-request worse than disabling speculation entirely.

## Resources

- [Fast Inference from Transformers via Speculative Decoding (arXiv)](https://arxiv.org/abs/2211.17192)
- [Accelerating Large Language Model Decoding with Speculative Sampling (DeepMind, arXiv)](https://arxiv.org/abs/2302.01318)
- [Medusa: Simple LLM Inference Acceleration Framework (arXiv)](https://arxiv.org/abs/2401.10774)
- [EAGLE: Speculative Sampling Requires Rethinking Feature Uncertainty (arXiv)](https://arxiv.org/abs/2401.15077)
- [Hugging Face — assisted generation / speculative decoding docs](https://huggingface.co/docs/transformers/en/generation_strategies)

## Failure modes specific to speculative decoding llm inference

AI systems around speculative decoding llm inference fail on evaluation blindness and cost cliffs. Define golden sets and latency/cost budgets before tuning ANN parameters or prompt length.

For speculative decoding llm inference:
- Separate embedding model version from index generation — rebuilds are migrations
- Filter/metadata strategy matters as much as HNSW params
- Cache semantic results carefully; stale answers look like model regressions
- Log prompts/outputs with PII redaction and retention limits

Ship a thin eval harness in CI for critical intents so prompt changes cannot silent-break production.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Migration path into speculative decoding llm inference

Reviewers should challenge assumptions encoded in speculative decoding llm inference: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario A for speculative decoding llm inference: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.
2. Scenario B for speculative decoding llm inference: bad config shipped — prove rollback within the declared RTO without data corruption.
3. Scenario C for speculative decoding llm inference: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.

## Capacity planning with speculative decoding llm inference in mind

Roll out speculative decoding llm inference behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for speculative decoding llm inference

Detail 1 (782): for speculative decoding llm inference, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for speculative decoding llm inference becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break speculative decoding llm inference, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about speculative decoding llm inference: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing speculative decoding llm inference

Detail 2 (525): for speculative decoding llm inference, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing speculative decoding llm inference becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break speculative decoding llm inference, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about speculative decoding llm inference: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.