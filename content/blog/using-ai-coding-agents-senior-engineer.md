---
title: "How I Actually Use AI Coding Agents as a Senior Engineer"
slug: "using-ai-coding-agents-senior-engineer"
description: "A senior mobile engineer's real workflow with AI coding agents: where they help, where they hurt, and how to review agent-written code without shipping garbage."
datePublished: "2026-02-07"
dateModified: "2026-02-07"
tags: ["AI Coding", "Developer Productivity", "Engineering", "Workflow"]
keywords: "AI coding agents, agentic coding, AI pair programming, coding with AI, developer productivity, code review AI"
faq:
  - q: "Do AI coding agents make senior engineers faster?"
    a: "Yes, but unevenly. They excel at boilerplate, test scaffolding, migrations, and unfamiliar-API exploration — easily a 2-3x speedup there. On core architecture and subtle concurrency they're a net drag if you accept output without review. The gain comes from delegating the right tasks."
  - q: "Should I let an AI agent commit code without review?"
    a: "No. Treat agent output like a pull request from a fast, confident junior who never says 'I don't know.' Read every diff, run the tests, and own the result. The engineer who merges the code is responsible for it, not the model."
  - q: "What tasks should I not give an AI coding agent?"
    a: "Anything where the cost of a subtle wrong answer is high and hard to detect: security-critical code, concurrency and race conditions, data migrations, and core domain logic you don't yet understand yourself. Use the agent to explore these, not to author them unsupervised."
---

I've been writing mobile code for over a decade, and for the last couple of years an AI agent has been in the loop for most of it. The honest summary: coding agents are a genuine multiplier on the boring 60% of the job and a liability on the critical 10% if you let them run unsupervised. The skill isn't prompting — it's knowing which tasks to hand over and how hard to interrogate what comes back.

This is the workflow I actually use across Android, Flutter, and backend work, including the failure modes that cost me time before I learned to spot them. If you're a senior engineer wondering whether these tools are hype, the answer is: they're real, but the productivity comes from judgment, not from typing "make it work" and hoping.

## Where agents genuinely earn their keep

Some tasks are almost pure upside. I reach for an agent without hesitation on:

- **Boilerplate and scaffolding.** A new Jetpack Compose screen with a ViewModel, state holder, and preview — the shape is identical every time and the agent nails it. Same for Riverpod providers, Ktor route handlers, and test fixtures.
- **Mechanical migrations.** Moving XML layouts to Compose, bumping a deprecated API across 40 call sites, converting callbacks to coroutines. These are tedious, well-defined, and easy to verify.
- **Unfamiliar APIs.** Instead of reading a whole SDK doc, I ask the agent to produce a minimal working example, then I read *that* against the real docs. It's a faster on-ramp than a tutorial.
- **Test generation.** Agents write thorough, if occasionally redundant, unit tests. I let them draft, then prune. Coverage of edge cases I'd have skipped out of laziness is a real win.

On this class of work the speedup is real — often 2-3x — because verification is cheap. I can look at a generated Compose screen and know in seconds whether it's right.

## Where they quietly cost you time

The trouble starts when verification is expensive. Agents are confident everywhere, including where they're wrong, and they never signal uncertainty. The categories where I've been burned:

**Concurrency and races.** An agent will happily produce coroutine code that compiles, passes the happy-path test, and deadlocks under contention once a month in production. The bug isn't in the diff you're reading; it's in the interleaving you're not. I never accept concurrency changes without reasoning through them myself — see [coroutines and Flow patterns](https://blog.michaelsam94.com/kotlin-coroutines-flow-patterns/) for the kind of subtlety involved.

**Core domain logic.** If I don't understand the problem yet, an agent's plausible-looking solution can anchor me to a wrong model of it. I've learned to design the hard parts myself and delegate the implementation, not the other way round.

**"Helpful" over-reach.** Ask for a small fix and an agent may refactor three unrelated files, rename a public API, and swallow an exception it decided was noise. Scope creep in a diff is a real review burden.

## My actual loop

The workflow that works for me looks less like chatting and more like managing a very fast contractor:

1. **I write the plan.** Before the agent touches anything, I decide the approach — the files, the interfaces, the edge cases. On a non-trivial task I'll have the agent *propose* a plan and I edit it, but the architecture decision stays with me.
2. **Small, scoped tasks.** I give one coherent unit of work at a time with explicit boundaries ("only touch `ChargerRepository`; don't change the public interface"). Big vague asks produce big vague diffs.
3. **Tests and types as guardrails.** A strong type system and a real test suite are what make agent code safe to accept quickly. The compiler and CI catch a lot; I catch the rest.
4. **Read every line.** This is the non-negotiable. I read the diff as if reviewing a PR from a junior who is brilliant, fast, and occasionally confidently wrong. If I can't explain why a line is there, it doesn't merge.

That last point is the whole game. The engineer who clicks merge owns the code — not the model, not "the AI wrote it." Accountability doesn't transfer.

## Reviewing agent code without going insane

The volume of code an agent produces can overwhelm normal review habits. A few tactics keep it manageable:

- **Diff hygiene.** Reject changes that touch files outside the task. A tight blast radius makes review tractable.
- **Ask it to explain, then verify.** "Why did you use `SupervisorJob` here?" A good justification builds confidence; a hand-wavy one is a red flag to dig deeper.
- **Automated gates.** Lint, type checks, and [AI-assisted review in CI](https://blog.michaelsam94.com/ai-code-review-in-ci/) catch a class of issues before a human looks. They don't replace review; they raise the floor.
- **Run it.** Static review misses runtime behavior. For anything with real logic I run it and watch it, especially on edge inputs the agent claimed to handle.

## The uncomfortable honest part

Agents make it dangerously easy to ship code you don't understand. That's the actual risk — not that the tools are bad, but that they let you skip comprehension and still produce something that compiles. For a junior that's how skills atrophy; for a senior it's how subtle bugs slip past the one person who should have caught them.

So I use them aggressively, and I refuse to let them make me stupid. The parts of the system that matter — the architecture, the concurrency model, the security boundaries — I still hold in my own head. The agent handles the typing. I handle the thinking. That division is why the net effect on my work has been strongly positive, and why I'd tell any senior engineer to adopt these tools without surrendering the judgment that makes them senior. If you want to see the kind of systems I build with this workflow, my [portfolio](https://michaelsam94.com/) has the details.

## Resources

- [Cursor documentation](https://docs.cursor.com/)
- [GitHub Copilot documentation](https://docs.github.com/en/copilot)
- [Anthropic — Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview)
- [Google — 2024 DORA report (AI and software delivery)](https://dora.dev/research/)
- [Martin Fowler — Exploring generative AI](https://martinfowler.com/articles/exploring-gen-ai.html)
- [Simon Willison's blog on LLMs and coding](https://simonwillison.net/)
