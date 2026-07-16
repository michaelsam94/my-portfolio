---
title: "AI Code Review in CI: What Works and What Doesn't"
slug: "ai-code-review-in-ci"
description: "A senior engineer's take on AI code review in CI: where automated PR review bots genuinely help, where they waste reviewers' time, and how to wire them up."
datePublished: "2026-03-02"
dateModified: "2026-03-02"
tags: ["CI/CD", "Code Review", "AI Tooling", "Engineering Practices"]
keywords: "AI code review, automated code review, CI code review, code review bots, PR review AI, static analysis"
faq:
  - q: "Does AI code review replace human reviewers?"
    a: "No. AI code review is good at catching mechanical issues — null checks, obvious concurrency bugs, missing error handling — but it cannot judge whether the change is the right thing to build. Treat it as a first-pass filter that frees humans to review design and intent."
  - q: "Where does AI code review add the most value in CI?"
    a: "On large PRs, unfamiliar code areas, and repetitive checks like security patterns and API misuse. It also shines as a synchronous reviewer on time zones where no human is online, shortening the feedback loop before a human wakes up."
  - q: "What is the biggest risk of AI code review bots?"
    a: "Noise. A bot that posts twelve low-confidence comments per PR trains developers to ignore all of them, including the one that mattered. Tuning for precision over recall is the single most important configuration decision."
---

An AI code review bot posted 14 comments on a two-line PR last quarter. Eleven were style nits it could have fixed itself, two were flat wrong, and one flagged a real race condition. That ratio is the whole story of AI code review in CI: the tools can find genuinely useful things, but they will bury the signal in noise unless you configure them like you mean it.

I run AI code review across several repos — Kotlin Android apps, a Ktor backend, some Dart/Flutter — and the honest summary is that it works well as a *first-pass filter* and poorly as a *decision maker*. Here's what I've learned about where the line sits.

## What AI code review is actually good at

The strongest use case is the mechanical, high-volume stuff a tired human reviewer skims past at 6pm. Concretely, the wins I see repeatedly:

- **Missing error handling** — an unawaited coroutine, a swallowed exception, a `Result` that's never checked.
- **Obvious concurrency issues** — mutable shared state touched from two dispatchers, a `lateinit` read before init.
- **Security smells** — a secret hardcoded in a config file, SQL built by string concatenation, a permissive CORS header. These overlap with what [DevSecOps shift-left](https://blog.michaelsam94.com/devsecops-shift-left/) practices already push into CI.
- **API misuse** — calling a deprecated function, ignoring a return value that carries a cancellation signal.
- **Test gaps** — pointing out that a new branch has no covering test.

The reason it works here is that these are *local* judgments. The model can reason about a diff plus a bit of surrounding context and reach a correct conclusion without understanding the whole system. That's the sweet spot.

## What it's bad at (and probably always will be)

AI review cannot tell you whether you're building the right thing. It doesn't know that this feature is being deprecated next sprint, that the "duplicate" code exists on purpose because two teams need to diverge, or that the "inefficient" loop runs once a day on 40 rows and optimizing it is a waste of a senior engineer's afternoon.

It's also weak on **cross-file architectural judgment**. Ask it whether a change respects your module boundaries or your [clean architecture](https://blog.michaelsam94.com/clean-architecture-pragmatically/) layering and you'll get plausible-sounding answers that are frequently wrong, because the model can't see the whole dependency graph in one pass. And it hallucinates confidently: I've seen a bot "fix" a null check that was already guarded three lines up, because it didn't read up far enough.

## The noise problem is the real problem

The failure mode that kills these tools in practice isn't wrong comments — it's *too many* comments. Alert fatigue is real. Once developers learn that the bot is usually wrong, they stop reading it entirely, and you've spent money to train your team to ignore feedback.

The fix is to bias hard toward precision. In every tool I've configured, the highest-leverage settings are:

```yaml
# Example review-bot config: fewer, higher-confidence comments
review:
  max_comments_per_pr: 5
  min_confidence: high        # suppress speculative nits
  skip_paths:
    - "**/generated/**"
    - "**/*.pb.dart"
    - "**/build/**"
  auto_fix:
    formatting: true          # let it fix, not comment on, style
  comment_on:
    - security
    - correctness
    - concurrency
  ignore:
    - style
    - naming
```

The principle: if it can be auto-fixed (formatting, imports, trivial lint), let the bot fix it silently or hand it to a formatter — don't spend a comment on it. Reserve human-visible comments for things a human should actually decide on.

## Where it fits in the pipeline

I put AI review *after* the deterministic checks, not instead of them. Static analysis, linters, and type checkers are faster, cheaper, and don't hallucinate — run those first as required gates. The AI reviewer is a **non-blocking, advisory** step. Here's the ordering that's worked:

| Stage | Tool type | Blocking? | Cost |
|---|---|---|---|
| Format + lint | detekt / ktlint / dart analyze | Yes | ~seconds |
| Type + compile | Kotlin/Dart compiler | Yes | ~1-3 min |
| Unit tests | JUnit / flutter test | Yes | ~2-5 min |
| Static security | Semgrep / CodeQL | Yes (high sev) | ~1-4 min |
| AI review | LLM review bot | No (advisory) | ~30-90s + $ |
| Human review | People | Yes | async |

Making AI review non-blocking matters. A blocking AI gate means a hallucinated comment can hold up a hotfix at 2am, and you'll disable it within a week. Advisory keeps it useful without giving it veto power it hasn't earned.

## Cost and latency, briefly

These calls aren't free. A large PR fed to a frontier model can cost real money per review, and if you review every push instead of every PR, that multiplies fast. Two practical controls: only run on PR open and on explicit re-request (not every commit), and cap the diff size you send — beyond a few thousand changed lines, the review quality drops anyway and you're better off asking a human. If you're running review at scale, the same [LLM cost tactics](https://blog.michaelsam94.com/cutting-llm-costs-caching-routing-batching/) — routing simple diffs to smaller models, caching — apply directly.

## How I'd roll it out

If you're introducing AI code review to a team, don't turn it on for everything at once. Start advisory-only on one or two repos. Watch the true-positive rate for two weeks — if fewer than one in three comments is acted on, tighten the confidence threshold before you expand. Ask reviewers to react to bot comments (thumbs up/down) so you have data, not vibes, about whether it's earning its keep.

And be explicit with the team about what it's for: it's a junior reviewer that never sleeps and never gets bored, not an architect. The moment people expect it to catch design problems, they'll be disappointed and they'll blame the tool.

## The honest verdict

AI code review in CI is worth having. It genuinely catches bugs that slip past humans, and it shortens the loop on off-hours PRs. But its value is entirely a function of how ruthlessly you tune it for precision and how clearly you scope it to mechanical review. Left at defaults, it's noise. Configured with intent and kept advisory, it's a solid extra layer — one that makes your human reviewers' time go further, which was always the point.

If you're setting up review automation as part of a broader pipeline, it pairs naturally with [fast CI/CD pipelines](https://blog.michaelsam94.com/fast-cicd-pipelines/) and [AI coding agents for senior engineers](https://blog.michaelsam94.com/using-ai-coding-agents-senior-engineer/).

## Resources

- [GitHub Actions documentation](https://docs.github.com/en/actions)
- [Semgrep — static analysis rules](https://semgrep.dev/docs/)
- [CodeQL documentation](https://codeql.github.com/docs/)
- [detekt — static analysis for Kotlin](https://detekt.dev/)
- [OpenAI API reference](https://platform.openai.com/docs/api-reference)
- [Google Engineering Practices: Code Review](https://google.github.io/eng-practices/review/)
