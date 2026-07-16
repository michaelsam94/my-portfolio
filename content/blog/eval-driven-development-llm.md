---
title: "Eval-Driven Development for LLM Features"
slug: "eval-driven-development-llm"
description: "Eval-driven development for LLM features: build a golden dataset, wire evals into CI, and ship prompt and model changes with regression safety, not vibes."
datePublished: "2026-01-14"
dateModified: "2026-01-14"
tags: ["LLM", "Testing", "AI Agents"]
keywords: "eval driven development, LLM evals, offline evals, regression testing LLM, golden dataset, LLM CI"
faq:
  - q: "What is eval-driven development for LLM features?"
    a: "Eval-driven development is the practice of building and maintaining a measurable evaluation suite for an LLM feature and using it to guide every change, the way test-driven development uses unit tests. You define a golden dataset of inputs with expected behaviors, score outputs automatically, and require changes to prompts, models, or retrieval to improve or at least not regress those scores. It replaces 'this looks better to me' with a number you can defend."
  - q: "How is evaluating an LLM different from normal unit testing?"
    a: "LLM outputs are non-deterministic and rarely have a single correct string, so exact-match assertions mostly do not work. Instead you use graders: some deterministic (does the JSON parse, does it contain the required field), some model-based (does an LLM judge rate this answer as faithful to the source). You also think in aggregate pass rates over a dataset rather than a single pass or fail, because one flaky example is expected."
  - q: "Do I need a golden dataset before writing any prompt?"
    a: "You do not need a perfect one, but you should build a small one early — even twenty to fifty representative cases — before you start tuning prompts seriously. Without it you optimize blind and every change is a guess. The dataset grows over time as you add every production failure and edge case you discover, and that accumulation is what makes the suite valuable."
---

If your process for improving an LLM feature is "change the prompt, eyeball a few outputs, ship if it looks better," you're flying blind and you'll regress silently. Eval-driven development is the antidote: you build a golden dataset of inputs with expected behaviors, score model outputs automatically, and treat every prompt, model, or retrieval change as something that must move a number in the right direction. It's test-driven development adapted to a non-deterministic system — the discipline that turns "feels better" into "recall went from 0.78 to 0.86."

I've watched teams ship a "small prompt tweak" that quietly broke a whole category of inputs nobody thought to re-check. Evals are how you stop doing that. Here's how I build them.

## Why eyeballing fails

The instinct to judge LLM changes by reading a few outputs breaks down for reasons specific to these systems. Outputs are non-deterministic, so the same input can vary run to run — you can't reason from a single sample. There's rarely one correct answer, so exact-match assertions are useless. And the surface area is huge: a prompt that helps polite questions might wreck terse ones, and you'll never notice by spot-checking your three favorite examples. Worst of all, improvements and regressions travel together — the change that fixes case A often breaks case B — and without a dataset you only see the half you happened to look at.

The fix is to make quality a measured quantity over a representative population, not an impression from a handful of demos.

## Start with a golden dataset

Everything hinges on the dataset. It's a collection of representative inputs, each paired with what good behavior looks like — an expected answer, a set of required facts, a rubric, or a reference the output should be faithful to.

You don't need it to be big or perfect to start. Twenty to fifty cases that span your real input distribution beat a thousand cherry-picked easy ones. Then it grows in the most valuable way possible: **every production failure becomes a new eval case.** A user reports a bad answer? Add it. You find an edge case? Add it. Over months, the dataset accumulates institutional memory of every way your feature has ever broken, and that's what makes it a moat.

```python
# golden.jsonl — one case per line
{"id": "refund-policy-1",
 "input": "Can I get a refund after 40 days?",
 "must_contain": ["30 day", "no refund"],
 "must_not_contain": ["yes", "of course"]}
{"id": "empty-order",
 "input": "What's the status of my order?",
 "expected_behavior": "asks for order id, does not fabricate"}
```

Keep cases small, labeled, and versioned in the repo next to the code. Categorize them (by feature, difficulty, failure type) so you can see *which slice* regressed, not just the aggregate.

## Choose graders that fit the task

A grader turns an output into a score. The art is picking the cheapest grader that's trustworthy for each case:

| Grader type | Good for | Cost | Trust |
| --- | --- | --- | --- |
| Deterministic (regex, JSON parse, contains) | Format, required facts, refusals | Free | High where applicable |
| Similarity (embedding, ROUGE) | "Close to reference" answers | Low | Medium |
| Model-based (LLM judge) | Faithfulness, tone, helpfulness | Higher | Medium, needs calibration |
| Human review | Ground truth, judge calibration | Highest | Highest |

Lead with deterministic graders — they're free and unambiguous, and a shocking amount of quality is checkable this way (did it output valid JSON, did it cite a source, did it refuse the out-of-scope request). Reach for an LLM judge only for the genuinely fuzzy properties like faithfulness or tone, and *calibrate the judge against human labels* before you trust it, because an uncalibrated judge just launders your bias into a number. This whole grading craft — especially for agents that take multi-step actions — deserves its own depth, which I cover in [LLM evals and measuring agent quality](https://blog.michaelsam94.com/llm-evals-measuring-agent-quality/).

## Wire evals into CI

An eval suite you run manually gets run when you remember, which is never at the moment you most need it. The payoff comes when evals run automatically on every change to a prompt, model, or retrieval config — exactly like a test suite gating a merge.

```yaml
# .github/workflows/evals.yml
on: { pull_request: { paths: ["prompts/**", "src/llm/**"] } }
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m evals run --dataset golden.jsonl --report out.json
      - run: python -m evals gate --report out.json --min-pass 0.90 --no-regress
```

The `--no-regress` flag is the heart of it: block the merge if any category's pass rate drops, even if the overall average rises. That's what catches the "fixed A, broke B" trades that eyeballing misses. For RAG features, the retrieval half of the pipeline needs its own metrics gated the same way — recall and nDCG over a labeled set — which is the subject of [evaluating retrieval metrics for RAG](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/).

## Offline evals and online reality

Offline evals on your golden set are fast, cheap, and gate every change — that's your inner loop. But they only measure inputs you thought to include. Production always surfaces inputs you didn't imagine, so pair offline evals with online signals: sample real traffic, log outputs, collect thumbs-up/down and downstream success metrics, and mine that stream for new failure cases to fold back into the golden set. The loop is: offline evals catch regressions before ship, online monitoring finds the gaps in your dataset, and those gaps become new offline cases. Skip the online half and your evals slowly drift away from what users actually do.

## The discipline that makes it work

Eval-driven development isn't a tool you install; it's a habit the team commits to. The practices that separate teams who benefit from those who have a dusty eval script nobody runs:

- **No prompt change without an eval run.** Make it as reflexive as running tests before a push.
- **Every incident becomes a case.** The dataset should grow every time something breaks in production.
- **Report by slice.** Aggregate numbers hide category regressions; always break scores down by input type.
- **Version everything together.** Prompt, model name, dataset, and scores versioned so you can attribute a change to a cause.
- **Gate on no-regression, not just a threshold.** The trades between examples are where quality quietly leaks.

The honest downside is that this is real work — building and curating the dataset, calibrating judges, maintaining the CI — and it feels slower than shipping on vibes. It is slower, right up until the first regression it catches that would have shipped to every user. After that, nobody on the team wants to go back. Evals are the closest thing the LLM world has to a type system: not a guarantee of correctness, but a fast, automated signal that turns "I hope this is better" into evidence you can stand behind.

## Resources

- [OpenAI Evals framework](https://github.com/openai/evals)
- [Anthropic — building evaluations](https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests)
- [Promptfoo — LLM eval and testing tool](https://github.com/promptfoo/promptfoo)
- [Ragas — evaluation for RAG pipelines](https://github.com/explodinggradients/ragas)
- [Hugging Face — LLM evaluation guidebook](https://github.com/huggingface/evaluation-guidebook)
