---
title: "RLHF: How Preference Training Works"
slug: "fine-tuning-rlhf-overview"
description: "Understand RLHF end-to-end: supervised fine-tuning, reward modeling, PPO policy optimization, KL penalties, and why teams migrate to DPO variants."
datePublished: "2026-02-26"
dateModified: "2026-02-26"
tags: ["AI", "Machine Learning", "Fine-Tuning", "RLHF"]
keywords: "RLHF explained, reinforcement learning human feedback, reward model training, PPO LLM alignment, KL penalty RLHF, RLHF vs DPO, ChatGPT training pipeline"
faq:
  - q: "What are the three stages of classic RLHF?"
    a: "Stage 1: Supervised fine-tuning (SFT) on demonstration conversations. Stage 2: Train a reward model on human preference comparisons (chosen vs rejected). Stage 3: Optimize the policy with reinforcement learning (typically PPO) to maximize reward while penalizing divergence from the SFT model via KL constraint."
  - q: "Why add a KL penalty during RLHF?"
    a: "The reward model is imperfect — unconstrained policy optimization exploits reward model blind spots (reward hacking), producing fluent but useless or harmful outputs. KL penalty to the reference SFT policy keeps the model speaking coherent English and preserves capabilities while improving preferred behaviors."
  - q: "Is RLHF still used given DPO alternatives?"
    a: "Yes for large-scale production systems that benefit from separate reward models, online learning, and multi-objective rewards. Many teams use SFT + DPO/ORPO for simplicity. RLHF remains relevant when reward shaping, process supervision, or iterative human feedback loops require explicit reward networks."
---

ChatGPT did not emerge from pretraining alone — nor from instruction tuning alone. Classic RLHF (Reinforcement Learning from Human Feedback) added a loop where humans ranked model outputs, a reward model learned those preferences, and reinforcement learning nudged the policy toward high-reward responses without wandering into nonsense. The pipeline is heavier than DPO: three training phases, reward hacking risks, PPO hyperparameters that fight you at 2 AM. Understanding RLHF anyway clarifies what alignment products actually optimize, why KL penalties exist, and when the complexity buys control DPO cannot match.

## Stage 1: Supervised Fine-Tuning (SFT)

Train on human-written or curated `(prompt, ideal_response)` demonstrations.

Purpose: teach dialog format, basic helpfulness, domain entry point.

Output: **SFT policy** π_SFT — reference for later KL anchoring.

Skipping quality SFT makes later RL optimize gibberish that tricks a weak reward model.

## Stage 2: Reward Model (RM)

Collect comparisons: for prompt x, response A preferred over B.

Train Bradley-Terry style scorer R(x, y) predicting human preference:

```python
# pairwise loss sketch
loss = -log(sigmoid(R(prompt, chosen) - R(prompt, rejected)))
```

Architecture: often initialized from SFT backbone with scalar head on last token.

Data quality dominates — inconsistent labelers teach noisy R. Filter ambiguous pairs.

Hold out test pairs for **accuracy** and **calibration** — not training loss alone.

## Stage 3: PPO policy optimization

Treat LLM as policy π_θ generating tokens as actions. Maximize expected reward:

\[
J(\theta) = \mathbb{E}_{y \sim \pi_\theta}[R(x, y)] - \beta \cdot D_{KL}(\pi_\theta \| \pi_{\text{SFT}})\]
\]

**PPO (Proximal Policy Optimization)** updates in small trusted steps:

```python
# conceptual TRL RLHF stack
from trl import PPOTrainer, PPOConfig, AutoModelForCausalLMWithValueHead

ppo_config = PPOConfig(
    learning_rate=1e-5,
    batch_size=16,
    mini_batch_size=4,
    kl_penalty="kl",
    init_kl_coef=0.2,
)

# policy with value head, ref model, reward model
trainer = PPOTrainer(config=ppo_config, model=policy, ref_model=ref, ...)
```

Loop:

1. Sample prompts from dataset
2. Generate responses with current policy
3. Score with reward model (and optional penalties)
4. PPO update with advantage estimates
5. Monitor KL — if KL spikes, reduce learning rate or increase β

## Reward hacking

Policy discovers R blind spots:

- Overlong flattering responses score high
- Format exploits (reward model likes bullet lists)
- Hedging language gaming safety classifiers

Mitigations:

- KL to SFT reference
- Reward model ensembles
- Human review of RL checkpoints
- Constraint penalties (length, repetition)

## RLHF vs DPO (when to pick which)

| RLHF | DPO |
|------|-----|
| Separate reward model reusable online | Pairwise data only |
| Multi-objective reward combination | Single preference signal baked in |
| Complex infra (PPO, value head) | Simpler classification loss |
| Mature tooling at scale (Anthropic, OpenAI paths) | Default for many open fine-tunes |

Hybrid flows exist: SFT → reward model → DPO distillation from RM scores.

## Modern variants

- **RLAIF** — AI labelers instead of humans for scale (with human audit)
- **Process reward models** — score reasoning steps, not just final answer
- **Online RLHF** — continuous collection from production comparisons
- **GRPO / newer RL variants** — research alternatives to PPO complexity

## Evaluation beyond reward

Reward model score increasing ≠ user happiness.

Track:

- Human win-rate vs baseline
- Instruction following benchmarks
- Toxicity / jailbreak suites
- Latency and cost (RL policies can ramble)

Shadow deploy candidate policy on sample traffic before cutover.

## Practical open-source stack

- **TRL** — `RewardTrainer`, `PPOTrainer`, `DPOTrainer`
- **OpenRLHF** — distributed RLHF
- **DeepSpeed-Chat** — end-to-end pipeline examples

Expect weeks of iteration — RLHF is not a single notebook run.

RLHF taught the industry that alignment is optimization against human intent signals — whether you implement that with PPO or DPO, the preference data and eval discipline determine outcomes.

## Preference data quality

RLHF output quality ceiling is the preference dataset. Common failure modes:

| Problem | Symptom | Fix |
|---------|---------|-----|
| Annotator inconsistency | Reward model overfits noise | Inter-rater agreement checks, gold questions |
| Position bias | Model prefers longer answers | Swap A/B order in pairs |
| Style over substance | Fluent but wrong wins | Add factuality checks to labels |
| Demographic skew | Tone mismatch for users | Diverse annotator pool, locale tags |
| Sparse coverage | Fails on edge cases | Stratify by intent category |

Minimum viable preference set: 5K–10K high-quality pairs for domain fine-tunes, not 500 rushed labels. One hour of label guideline iteration saves a week of reward model debugging.

## Cost and infrastructure reality

Full RLHF (SFT → reward model → PPO) at 7B+ scale needs multi-GPU clusters:

- **SFT:** 1–8× A100, hours to days depending on dataset
- **Reward model:** Similar to smaller classifier training
- **PPO:** 4–64 GPUs, unstable without careful hyperparameter tuning

DPO removes the online RL loop but still needs preference pairs and careful eval. For most product teams, start with SFT + DPO before attempting PPO — the alignment gain often doesn't justify PPO infra complexity until you have production traffic generating preferences continuously.

## When RLHF isn't the right tool

- **Factual recall tasks** — RAG + grounding beats alignment tuning
- **Format compliance** — constrained decoding or grammar beats RL
- **Low-data domains** — SFT on 500 examples may outperform RLHF on 200 noisy pairs
- **Latency-sensitive** — RL-tuned models sometimes increase verbosity

Pair with [fine-tuning dataset curation](https://blog.michaelsam94.com/fine-tuning-dataset-curation/) before investing in RL infrastructure — garbage SFT data poisons every downstream alignment step.

## Production checklist

- [ ] Preference data inter-rater agreement measured on gold set
- [ ] Human win-rate tracked vs baseline before RL deploy
- [ ] DPO attempted before PPO unless reward model reuse justifies infra
- [ ] Toxicity and jailbreak eval suites run on every checkpoint
- [ ] Shadow deploy on sample traffic before full cutover

## Resources

- [Training language models to follow instructions with human feedback (InstructGPT paper)](https://arxiv.org/abs/2203.02155)
- [TRL library documentation](https://huggingface.co/docs/trl)
- [Deep reinforcement learning from human preferences (Christiano et al.)](https://arxiv.org/abs/1706.03741)
- [OpenRLHF GitHub](https://github.com/OpenRLHF/OpenRLHF)
- [Direct Preference Optimization (DPO alternative)](https://arxiv.org/abs/2305.18290)
