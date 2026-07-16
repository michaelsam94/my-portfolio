---
title: "Building an LLM Router for Cost and Quality"
slug: "building-an-llm-router"
description: "An LLM router sends each request to the cheapest capable model. How to build classifier and cascade routing for real cost and quality wins."
datePublished: "2026-01-09"
dateModified: "2026-01-09"
tags: ["LLM", "AI Agents", "Cost", "Architecture"]
keywords: "LLM router, model routing, cost quality tradeoff, cascade routing, classifier routing, model selection"
faq:
  - q: "What is an LLM router?"
    a: "An LLM router is a component that inspects each incoming request and decides which model should handle it, so that easy queries go to cheap, fast models and hard queries go to expensive, capable ones. The goal is to hold answer quality roughly constant while cutting cost and latency, since most production traffic doesn't need a frontier model. It sits in front of your model providers as a routing layer."
  - q: "What is the difference between classifier routing and cascade routing?"
    a: "Classifier routing decides the target model up front, before any generation, using a lightweight model or heuristic to predict which tier the query needs. Cascade routing instead tries the cheap model first and only escalates to a stronger model if the cheap answer fails a quality check. Classifiers add near-zero latency but can misroute; cascades are more accurate but pay for extra calls on escalated requests."
  - q: "Does an LLM router hurt answer quality?"
    a: "Done well, barely — because a large share of real traffic is simple enough that a smaller model answers it just as well. The risk is misrouting hard queries to weak models, so you tune the router conservatively and monitor per-tier quality. The right framing is cost savings at a quality budget you set, not blind cost minimization."
---

Most production LLM traffic is easy. A large fraction of the requests hitting your endpoint are classification, extraction, short answers, or formatting — the kind of thing a small, cheap model handles perfectly well. Yet teams route everything to their most expensive model "to be safe," and pay 10–20x more than they need to. An LLM router fixes that: it looks at each request and sends it to the cheapest model that can still answer it well, keeping quality roughly flat while cutting cost and latency.

I've built this pattern a few times, and the interesting part isn't the routing logic — it's being honest about the quality budget. A router is a controlled quality/cost trade, not a free lunch. Set that expectation and it's one of the highest-ROI pieces of infrastructure you can add.

## The premise: traffic is not uniform

If you plot the difficulty of real requests, you get a long tail. A minority genuinely need frontier reasoning; the majority are mundane. Sending the mundane majority to a flagship model is the waste a router eliminates. The savings come from three tiers, roughly:

- **Cheap tier** — small/fast models for classification, extraction, simple Q&A, formatting.
- **Mid tier** — general-purpose models for most conversational and reasoning tasks.
- **Frontier tier** — the expensive models for hard reasoning, long-context synthesis, or high-stakes output.

The router's job is to assign each request to the lowest tier that meets your quality bar. Everything else is implementation.

## Approach 1: classifier routing (decide up front)

The cleanest design predicts the right tier *before* generating anything. A lightweight classifier — a small model, an embedding-based scorer, or even good heuristics — looks at the query and picks a target.

```python
def route(query: str) -> str:
    features = classify(query)  # cheap model or embedding scorer
    if features["needs_reasoning"] or features["long_context"]:
        return "frontier"
    if features["is_simple_lookup"] or features["is_extraction"]:
        return "cheap"
    return "mid"

model = route(user_query)
answer = call_model(model, user_query)
```

The appeal: it adds almost no latency and no extra generation cost — one cheap classification, then a single model call. The risk: the classifier is guessing before it's seen an answer, so it *will* occasionally send a hard query to a weak model. You manage that by tuning conservatively (when unsure, route up) and by training the classifier on your own labeled traffic rather than a generic benchmark, because "hard" is domain-specific.

## Approach 2: cascade routing (try cheap first)

Cascade routing flips the order: try the cheap model, check whether its answer is good enough, and escalate only if it isn't.

```python
def cascade(query: str):
    answer = call_model("cheap", query)
    if quality_ok(query, answer):        # verifier / self-check / rules
        return answer
    return call_model("frontier", query) # escalate on failure
```

Cascades are more accurate than classifiers because the escalation decision is based on a real attempt, not a prediction. The cost is latency and double-billing on escalated requests — you paid for the cheap call *and* the expensive one. So the economics hinge on your **escalation rate**: if 80% of queries are satisfied by the cheap tier, cascading is a huge win; if 60% escalate, you're paying more than if you'd routed straight to the frontier model. The other hard part is the `quality_ok` verifier — a bad verifier either escalates everything (no savings) or accepts junk (quality loss). A small judge model or task-specific rules usually beats trying to have the cheap model grade itself.

## Choosing between them

| Dimension | Classifier routing | Cascade routing |
| --- | --- | --- |
| Extra latency | Negligible | High on escalated requests |
| Extra cost | ~None | Double-pay on escalations |
| Accuracy of routing | Lower (predictive) | Higher (based on real output) |
| Complexity | Classifier training | Reliable verifier |
| Best when | High volume, latency-sensitive | Quality-critical, moderate volume |

In practice I often combine them: a classifier catches the obvious cheap and obvious frontier cases, and a cascade handles the ambiguous middle. That hybrid keeps latency low for the clear-cut majority while reserving the try-first-then-escalate cost for genuinely uncertain queries.

## Building the verifier and the labels

Whichever approach you pick, the quality signal is where the project actually lives. Options, cheapest to most robust:

- **Rules/heuristics** — length, refusal detection, JSON schema validation, presence of required fields. Free, catches obvious failures.
- **Confidence signals** — logprobs or self-reported confidence. Cheap but noisy.
- **A judge model** — a small model scoring the answer against the query. More reliable, adds a call.

Collect real production queries, label them by which tier actually satisfied them, and use that to both train the classifier and set your escalation threshold. Without your own labeled data you're routing on vibes. This is the same "measure before you optimize" discipline that runs through the whole cost story I laid out in [cutting LLM costs with caching, routing, and batching](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) — routing is one lever in that toolkit, and it stacks with caching and batching rather than replacing them.

## Where the router lives

A router is naturally a gateway concern. Rather than baking routing logic into every application, put it behind a single [AI gateway / LLM proxy](https://blog.michaelsam94.com/ai-gateway-llm-proxy/) that handles routing, retries, fallbacks, caching, and observability in one place. That gives you provider-agnostic routing (route across vendors, not just tiers of one vendor), a single spot to change policy, and centralized metrics on per-tier cost and quality. It also makes fallback trivial: if the chosen model errors or times out, the gateway reroutes to an alternate — routing and resilience share the same seam.

## The pitfalls I'd warn you about

- **Optimizing cost without a quality guardrail.** A router that only minimizes cost will happily send everything to the cheapest model and quietly degrade your product. Always route against an explicit quality budget and monitor it.
- **Static routing rules that rot.** Traffic shifts, models change, prices change. Re-evaluate the router periodically or it drifts out of tune.
- **Ignoring latency in cascades.** A double-call cascade can blow interactive latency budgets even when it saves money. Measure p95, not just cost.
- **No per-tier observability.** You need to see, per tier, the volume, cost, escalation rate, and quality. Without that you can't tell a healthy router from a broken one.

Built with those guardrails, an LLM router is one of the rare optimizations that improves cost *and* latency for most requests while holding quality where you decide it should be. The engineering is modest; the discipline of defining "good enough" and measuring it is the real work.

## Resources

- [RouteLLM: Learning to Route LLMs with Preference Data (arXiv)](https://arxiv.org/abs/2406.18665)
- [FrugalGPT: How to Use LLMs While Reducing Cost and Improving Performance (arXiv)](https://arxiv.org/abs/2305.05176)
- [LiteLLM — routing and proxy documentation](https://docs.litellm.ai/docs/routing)
- [OpenAI — model selection and pricing](https://platform.openai.com/docs/models)
- [Anthropic — models overview](https://docs.anthropic.com/en/docs/about-claude/models)
