---
title: "LLM Evals: How to Actually Measure Agent Quality"
slug: "llm-evals-measuring-agent-quality"
description: "Build LLM evals that catch regressions: golden datasets, LLM-as-judge, task-level metrics for agents, and wiring an eval harness into CI so quality is measurable."
datePublished: "2026-01-18"
dateModified: "2026-01-18"
tags: ["LLM", "Evaluation", "AI Agents", "Testing"]
keywords: "LLM evals, LLM evaluation, agent evaluation, eval harness, LLM as a judge, regression testing LLM"
faq:
  - q: "What is an LLM eval?"
    a: "An LLM eval is a repeatable test that measures the quality of a model or agent's output against known-good expectations. It turns 'the responses feel worse' into a number you can track, compare across versions, and gate deployments on — the same role unit tests play for regular code."
  - q: "What is LLM-as-a-judge?"
    a: "LLM-as-a-judge uses a strong language model to score another model's output against a rubric — for example rating faithfulness or helpfulness. It scales evaluation beyond what humans can label manually, but must be calibrated against human judgments to be trustworthy."
  - q: "How do I evaluate an agent versus a single prompt?"
    a: "For agents, evaluate the whole trajectory, not just the final text: did it pick the right tools, in the right order, with valid arguments, and reach the goal? Task-completion rate and tool-call correctness matter more than surface-level answer quality for agentic systems."
---

If you can't measure it, you're not improving it — you're just changing it. LLM evals are how you turn "the outputs feel worse since we swapped the model" into a number you can trust, compare, and gate releases on. Without them, every prompt tweak is a gamble and every model upgrade is a leap of faith. With them, quality becomes a metric on a dashboard, and regressions get caught in CI instead of by users.

The core idea maps cleanly onto testing you already do: a golden dataset is your test fixtures, a scorer is your assertion, and the eval harness is your test runner. What's different is that outputs are non-deterministic and "correct" is often fuzzy — so the scoring is where the craft lives. Here's how I build evals that are actually useful rather than reassuring theater.

## Start with a golden dataset

An eval is only as good as its dataset. You need a set of inputs paired with either exact expected outputs or a rubric for judging them. Where these come from matters:

- **Mine real usage.** The best eval cases come from actual user queries, especially the ones that failed. Every production incident becomes a permanent regression test.
- **Cover the edges deliberately.** Empty inputs, adversarial prompts, ambiguous requests, and the long tail of formats your users actually send.
- **Keep it versioned.** The dataset lives in the repo, reviewed like code. When someone adds a case, everyone's evals get stricter.

Fifty carefully chosen cases beat five thousand random ones. Aim for a set that, if it all passes, you'd be comfortable shipping.

## Pick the right scorer for the job

Not everything needs an LLM to judge it. Match the scorer to the output type, cheapest first:

| Output type | Scorer |
| --- | --- |
| Exact/structured (JSON, classification) | Exact match, schema validation, F1 |
| Extraction, retrieval | Precision/recall against labels |
| Freeform text | LLM-as-judge with a rubric |
| Code | Execute it and run tests |

Deterministic scorers are fast, free, and unambiguous — use them whenever the task allows. If your feature produces [structured outputs](https://blog.michaelsam94.com/structured-outputs-function-calling/), you can often assert on the JSON directly and skip subjective judging entirely.

## LLM-as-a-judge, used honestly

For freeform text, human labeling doesn't scale, so you enlist a strong model as the judge. It works, but only if you treat it as an instrument that needs calibration:

```text
You are grading an answer for FAITHFULNESS to the provided context.
Score 1-5. A 5 means every claim is supported by the context;
a 1 means the answer contradicts or invents facts.
Return JSON: {"score": <int>, "reason": "<one sentence>"}

Context: {context}
Answer: {answer}
```

Three rules keep judges trustworthy: give a **specific rubric** (not "rate quality 1–10"), ask for a **reason** so you can audit disagreements, and **calibrate against human labels** on a sample so you know your judge agrees with people. A judge that quietly drifts from human taste is worse than no judge, because it's confidently wrong. Prefer binary or small-scale rubrics — models are more consistent scoring "faithful: yes/no" than picking between a 6 and a 7.

## Evaluating agents, not just answers

Single-prompt evals judge the final text. Agents need more, because an agent can produce a good-looking answer by luck after taking a terrible path. Evaluate the **trajectory**:

- **Task completion** — did it actually achieve the goal? This is the headline metric.
- **Tool-call correctness** — right tools, right order, valid arguments.
- **Efficiency** — how many steps and tokens did it take? A correct answer in 30 tool calls is a problem.
- **Safety** — did it avoid unauthorized or destructive actions?

This is why agent evals pair naturally with the design discipline of [building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/) — you're testing the same properties you designed for. For multi-step systems like the [orchestrator-workers pattern](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/), also evaluate whether subtasks were decomposed sensibly, not just whether the final synthesis reads well.

## Wire it into CI

An eval you run manually is an eval you'll stop running. The payoff comes from automation: on every prompt change, model swap, or dependency bump, the harness runs the golden set and reports scores against a baseline.

```bash
# fails the build if pass-rate drops below threshold vs baseline
eval-harness run --dataset golden/*.jsonl \
  --model gpt-current --baseline gpt-prev \
  --min-pass-rate 0.92 --report ci-report.json
```

Set a threshold, block merges that drop below it, and track scores over time so slow drift is visible. This mirrors [AI code review in CI](https://blog.michaelsam94.com/ai-code-review-in-ci/) — quality checks that live in the pipeline, not in someone's memory. Frameworks like Promptfoo, OpenAI Evals, and Braintrust give you the harness; the datasets and rubrics are yours to own.

## The workflow that compounds

The teams that ship reliable LLM features run a tight loop: a user hits a bad case → it becomes a golden test → you fix the prompt/model/retrieval → the eval confirms the fix and guards against its return. Over months, the dataset becomes the most valuable asset you have — an encoded definition of "good" that survives model changes and team turnover.

Evals won't make your model smarter. They'll make your *system* trustworthy, which for anything shipping to real users is the thing that actually matters. Start with twenty real cases and a single judge prompt today; the discipline pays off the first time it catches a regression before your users do.

## Resources

- [OpenAI — Evals guide and framework](https://platform.openai.com/docs/guides/evals)
- [Anthropic — Building evaluations](https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests)
- [Promptfoo — LLM eval tooling](https://www.promptfoo.dev/)
- [Braintrust — eval platform](https://www.braintrust.dev/)
- [Hugging Face — evaluation library](https://huggingface.co/docs/evaluate/index)
- [Ragas — RAG-specific evaluation](https://docs.ragas.io/)
