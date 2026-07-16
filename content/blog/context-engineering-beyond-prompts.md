---
title: "Context Engineering: Beyond Prompt Engineering"
slug: "context-engineering-beyond-prompts"
description: "Context engineering for LLM apps: budget tokens, layer system prompts, retrieval, and tool results in the context window for reliable agent behavior."
datePublished: "2026-02-17"
dateModified: "2026-02-17"
tags: ["LLM", "Context Engineering", "Agents", "RAG"]
keywords: "context engineering, prompt engineering, context window, LLM context, retrieval context, context management"
faq:
  - q: "What is context engineering?"
    a: "Context engineering is the practice of deciding what information fills an LLM's context window at each step — which instructions, retrieved documents, tool results, and history to include, in what order, and what to leave out. It treats the context window as a managed resource, not a place to dump everything."
  - q: "How is context engineering different from prompt engineering?"
    a: "Prompt engineering focuses on wording a single instruction well. Context engineering is broader and more systemic: it's about assembling the whole context — retrieval, memory, tool outputs, history — dynamically across a multi-step task. In agents, context management matters far more than clever phrasing."
  - q: "Why does adding more context sometimes make results worse?"
    a: "Because of context rot and the lost-in-the-middle effect: as the window fills, models attend less reliably to any single fact, and information buried in the middle gets ignored. Irrelevant or redundant context also distracts the model. Curating less, better context usually beats stuffing in more."
---

Prompt engineering was the 2023 skill: phrase the instruction just right and the model behaves. It still matters, but for anything beyond a single-shot call — agents, RAG systems, long conversations — it's the smaller half of the problem. The bigger half is **context engineering**: deciding what actually occupies the model's context window at each step, in what order, and just as importantly, what to leave out.

The reframe is simple but consequential. The context window is a finite, contended resource, not an inbox you fill. Every token you add competes for the model's attention with every other token. Context engineering is the discipline of curating that window so the model has exactly what it needs to take the next step — no more, no less.

## Why "just add more context" fails

The naive instinct is to shove everything relevant into the prompt: full documents, entire conversation history, every tool result. Two well-documented failure modes punish this:

**Lost in the middle.** Models attend most reliably to the beginning and end of their context. Facts buried in the middle of a long window get quietly ignored, even when they're the answer. Put the critical instruction or retrieved fact at the edges.

**Context rot.** As a window fills toward its limit, retrieval accuracy over that context degrades — the model's ability to pull out any single specific detail drops as the haystack grows. A 200k-token window doesn't mean 200k tokens of reliably-usable context. More is not free.

There's also plain distraction: irrelevant or contradictory context actively pulls the model toward worse answers. Cutting junk out often improves quality more than adding good stuff in.

## The building blocks of a managed context

A well-engineered context is assembled from distinct components, each managed on purpose:

- **System instructions** — stable, at the top, and cache-friendly. Keep them tight; bloated system prompts crowd out working space.
- **Retrieved knowledge** — the right chunks from a [RAG](https://blog.michaelsam94.com/rag-in-production-chunking-reranking-evals/) pipeline, reranked so the best ones sit where the model attends.
- **Tool definitions and results** — only the tools relevant to the current sub-task; results summarized rather than dumped raw.
- **Conversation / task history** — compacted, not verbatim.
- **Memory** — durable facts pulled from an external store when relevant, rather than kept resident in every turn.

The art is in the verbs: retrieve, rerank, compact, summarize, evict, order.

## Retrieval is context selection

RAG is often framed as a knowledge feature, but it's really the core context-engineering primitive: instead of putting everything in the window, you *select* the small slice relevant to this query at this moment. That's why retrieval quality dominates RAG quality — a good [reranker](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/) that promotes the 3 truly relevant chunks over 20 mediocre ones does more for answer quality than a bigger context window ever will.

The same logic applies to tool results. When an agent calls an API that returns a 5,000-token JSON blob, don't paste the blob into context. Extract the fields the next step needs. The model reasons better over a clean 200-token summary than a raw dump it has to parse.

## Managing context across a long agent run

Single calls are easy. The interesting work is a multi-step agent that runs for dozens of turns and would blow past any window if it kept everything. Techniques that keep it coherent:

**Compaction.** Periodically summarize the run-so-far into a compact state and drop the verbatim history. The agent carries forward "what's been established and decided," not every intermediate token. This is the difference between an agent that stays sharp over 50 steps and one that degrades into confusion around step 15.

**Structured scratchpad / state.** Keep a small, explicit state object (goals, findings, open questions) that you re-inject each turn, rather than relying on the model to remember from a wall of history.

**External memory.** Long-term facts live in a store (a database or vector index) and are retrieved when relevant, not held in the window. The window is working memory; the store is long-term memory. Don't confuse the two.

**Sub-agent isolation.** Spin up a sub-agent with a *fresh, narrow* context for a bounded task, and return only its conclusion to the parent. This keeps the parent's context clean — the [orchestrator-workers pattern](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/) is largely a context-management strategy in disguise.

A rough budget for one agent turn might look like:

```text
[ system + tools        ] ~15%   stable, cached
[ compacted task state  ] ~15%   what's established so far
[ retrieved context     ] ~40%   reranked, top-k only
[ recent turns verbatim ] ~20%   last few exchanges
[ headroom for output   ] ~10%   leave room to think
```

The exact split depends on the task, but the principle holds: allocate the window like a budget, and leave headroom. A window packed to 99% before generation is a window with no room to reason.

## How to actually improve it

Treat context like any other part of the system you'd optimize — with measurement, not vibes:

1. **Log the assembled context** for real requests so you can see what the model actually received (this is where [LLM observability](https://blog.michaelsam94.com/llm-observability-opentelemetry-genai/) pays off).
2. **Ablate.** Remove a component and check whether quality drops on your eval set. If it doesn't, it was noise — cut it.
3. **Reorder** and measure. Moving the key fact from the middle to the top is often a free win.
4. **Compact aggressively** and verify the agent still completes multi-step tasks.

Context engineering doesn't replace prompt engineering — a clear instruction still matters — but for anything agentic it's the higher-leverage skill. The teams shipping reliable agents aren't the ones with the cleverest system prompt; they're the ones who treat the context window as the scarce, carefully-managed resource it is.

## Resources

- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- ["Lost in the Middle" — Liu et al. (arXiv)](https://arxiv.org/abs/2307.03172)
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [OpenAI — Prompt engineering guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [LangChain — Concepts documentation](https://python.langchain.com/docs/concepts/)
