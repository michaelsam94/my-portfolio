---
title: "Mixture-of-Experts Models Explained for Engineers"
slug: "mixture-of-experts-explained"
description: "A mixture-of-experts model activates only a few parameters per token via a router. What MoE means for cost, memory, and serving, for engineers."
datePublished: "2026-03-25"
dateModified: "2026-07-17"
tags:
keywords: "mixture of experts, MoE, sparse models, expert routing, active parameters, Mixtral"
faq:
  - q: "What is a mixture-of-experts (MoE) model?"
    a: "A mixture-of-experts model is a neural network whose feed-forward layers are split into many parallel sub-networks called experts, with a small router that selects only a few experts to run for each token. This makes the model 'sparse': it has a large total parameter count but activates only a fraction of it per token. The result is the capacity of a huge model at the compute cost of a much smaller one."
  - q: "What is the difference between total and active parameters?"
    a: "Total parameters are all the weights the model contains and must be stored in memory. Active parameters are the subset actually used to process a given token, determined by how many experts the router selects. A model like Mixtral 8x7B has roughly 47B total parameters but only activates about 13B per token, so it costs like a 13B model to run but must be loaded like a 47B one."
  - q: "Why are MoE models harder to serve than dense models?"
    a: "Because you pay dense-model memory costs to store all experts but must handle uneven, dynamic routing at runtime. Some experts get more tokens than others, which complicates batching and load balancing across GPUs. Expert-parallel deployments also add cross-device communication that dense models don't need, so the systems engineering is meaningfully more involved."
---
A mixture-of-experts (MoE) model is a transformer that cheats the usual "bigger means slower" rule. Instead of running every parameter for every token, it splits its feed-forward layers into many parallel experts and uses a small router to pick just a few of them per token. So the model can hold hundreds of billions of parameters worth of knowledge while only doing the compute of a model a fraction of that size. That gap — big capacity, small per-token cost — is the entire reason MoE has taken over the frontier.

The confusion I see from engineers is treating MoE as a pure win. It buys you compute efficiency, but it hands you a memory bill and a serving-complexity bill in return. Understanding that trade is the difference between deploying one successfully and being surprised by your GPU invoice.

## The mechanism: routing to experts

In a dense transformer, every token passes through the same feed-forward network (FFN) at each layer. MoE replaces that single FFN with `N` separate FFNs — the experts — plus a **router** (a small learned linear layer) that scores the experts for each token and sends the token to the top `k` of them.

```python
# Conceptual top-2 routing for one token
def moe_layer(token, experts, router, k=2):
    scores = router(token)                 # one score per expert
    top = topk(scores, k)                  # pick k experts
    weights = softmax(top.values)          # normalize their gates
    out = sum(w * experts[i](token)        # run only those k experts
              for w, i in zip(weights, top.indices))
    return out
```

The router is the whole trick. It's tiny, but it decides which slice of the model's knowledge each token gets. Different tokens light up different experts, and over training the experts specialize — loosely, some handle syntax, some handle code, some handle particular domains, though the specialization is rarely as clean as the intuition suggests.

## Total vs. active parameters (the number that matters)

The two numbers you must separate:

- **Total parameters** — everything stored in memory. All experts, even the ones not used for a given token.
- **Active parameters** — what actually runs per token, roughly `k` experts' worth plus attention.

Take the canonical [Mixtral 8x7B](https://mistral.ai/news/mixtral-of-experts/): 8 experts, top-2 routing. It has ~47B total parameters but activates ~13B per token. So its *inference FLOPs* look like a 13B model, but its *memory footprint* looks like a 47B model — you must load all eight experts because you don't know in advance which the router will pick.

| Metric | Dense 13B | Mixtral 8x7B | Dense 47B |
| --- | --- | --- | --- |
| Compute per token | ~13B | ~13B | ~47B |
| Memory to load | ~13B | ~47B | ~47B |
| Quality (rough) | 13B-class | Well above 13B | 47B-class |

That table is the pitch and the catch on one page: MoE gives you near-47B quality at near-13B compute, but you still pay 47B memory. If you're memory-constrained rather than compute-constrained, MoE may not be your friend.

## Why the frontier went sparse

Sparsity scales capacity without scaling FLOPs, and that's exactly the axis that was getting expensive. Adding dense parameters raises both training and inference cost linearly; adding experts raises *capacity* while inference cost stays roughly flat (you still activate top-k). For labs trying to keep pushing quality without their serving costs exploding per token, MoE is the obvious lever, which is why so many recent frontier and open-weight models are sparse.

There's a subtler benefit for on-device and small-model work too: the *active* footprint being small means MoE ideas show up in efforts to run capable models on constrained hardware, adjacent to the tradeoffs I discussed in [small language models on mobile](https://blog.michaelsam94.com/small-language-models-on-mobile/). The memory bill is the blocker there — you can't easily hold all experts in phone RAM — but the compute efficiency is genuinely attractive.

## The hard parts nobody demos

MoE's problems are systems problems, and they're real:

- **Load imbalance.** The router can favor a few "popular" experts, starving others. Left unchecked, some experts get overloaded (dropped tokens) while others idle. Training uses an **auxiliary load-balancing loss** to spread tokens more evenly, and serving uses expert-capacity limits.
- **Batching gets awkward.** In a dense model every token in a batch does identical work. In MoE, tokens in the same batch route to different experts, so you're doing a scatter/gather to group tokens by expert, run each expert on its group, then reassemble. That irregularity fights the neat batching that GPU serving loves.
- **Expert parallelism and communication.** At scale you shard experts across GPUs, so routing becomes an all-to-all communication step every layer. That cross-device traffic is a new bottleneck dense models simply don't have, and it interacts heavily with how you schedule the hardware and how much memory each device must reserve.
- **Fine-tuning is finickier.** The router can overfit or collapse, and small fine-tuning datasets sometimes make an already-specialized model worse.

None of these are dealbreakers, but they explain why MoE serving stacks are more elaborate than dense ones, and why "just download the weights" is a lot easier than "serve it efficiently at scale."

## When to reach for MoE

My rule of thumb: MoE makes sense when you are **compute- or cost-per-token-bound and have the GPU memory to hold all the experts**. That's the sweet spot — you get better quality per FLOP and per dollar of *compute*. It makes less sense when memory is your hard constraint (edge, single small GPU) because you pay for all parameters whether you use them or not.

For picking a model to actually deploy, look past the headline parameter count to the active-parameter number for cost estimation and the total-parameter number for memory planning — they answer different questions, and conflating them is the most common MoE mistake I see. The same "know exactly what you're paying for" discipline applies when [choosing an embeddings model](https://blog.michaelsam94.com/choosing-an-embeddings-model/): the impressive-sounding number and the number that governs your bill are often not the same one.

MoE isn't a free lunch, but it's a genuinely good deal if your bottleneck is compute and your budget can cover memory. Read the architecture as what it is — a routing trick that trades memory for FLOPs — and it stops being mysterious and starts being a line item you can reason about.

## Resources

- [Mixtral of Experts (Mistral AI, arXiv)](https://arxiv.org/abs/2401.04088)
- [Switch Transformers: Scaling to Trillion Parameter Models (arXiv)](https://arxiv.org/abs/2101.03961)
- [Outrageously Large Neural Networks: The Sparsely-Gated MoE Layer (arXiv)](https://arxiv.org/abs/1701.06538)
- [GShard: Scaling Giant Models with Conditional Computation (arXiv)](https://arxiv.org/abs/2006.16668)
- [Hugging Face blog — Mixture of Experts explained](https://huggingface.co/blog/moe)
