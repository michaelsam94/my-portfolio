---
title: "Memory Architectures for AI Agents"
slug: "ai-agent-memory-architectures"
description: "Agent memory architectures decide what an AI agent remembers across sessions: short-term, long-term, episodic, and semantic memory and their tradeoffs."
datePublished: "2026-03-28"
dateModified: "2026-03-28"
tags: ["AI Agents", "LLM", "Architecture"]
keywords: "agent memory, short-term memory, long-term memory, vector memory, episodic memory, memory architecture agents"
faq:
  - q: "What is memory in an AI agent?"
    a: "Agent memory is the set of mechanisms that let an AI agent retain and reuse information beyond a single model call — across turns in a conversation and across separate sessions. Since a language model itself is stateless and limited by its context window, memory is external machinery that decides what to keep, how to store it, and what to load back into context when it's relevant. It's what makes an agent feel continuous rather than amnesiac."
  - q: "What is the difference between short-term and long-term agent memory?"
    a: "Short-term memory is the working context for the current task — recent messages, intermediate results, and scratchpad reasoning that live inside the context window and are discarded when the session ends. Long-term memory persists across sessions in external storage like a vector database or key-value store, and relevant pieces are retrieved back into context when needed. Short-term is bounded by the window; long-term is bounded by your storage and retrieval quality."
  - q: "Do agents need a vector database for memory?"
    a: "Not always. A vector database is useful for semantic recall over large, unstructured memory where you search by meaning, but plenty of agent memory is better served by structured stores — a key-value store for user preferences, a relational table for facts, or a simple summary buffer for conversation. Most production agents use a hybrid: structured stores for known fields and vector search for open-ended recall."
---

An AI agent without memory is a very smart goldfish. Each call, the underlying model starts from nothing but whatever you cram into its context window, so the moment a conversation exceeds that window — or the session ends — everything is gone. Agent memory is the external machinery that fixes this: it decides what the agent keeps, how it's stored, and what gets loaded back into context when it's relevant. Get it right and the agent feels continuous and personalized; get it wrong and it either forgets what you told it two minutes ago or drowns in irrelevant history.

There's a lot of loose talk about "giving agents memory" as if it's one feature. It isn't. There are several distinct kinds of memory that solve different problems, and the architecture decision is about which ones your agent actually needs. I'll break down the types, the storage choices, and the tradeoffs I weigh when designing one.

## The types of memory (borrowed from cognitive science)

The useful taxonomy maps loosely onto how psychologists describe human memory, and the analogy is genuinely helpful for design:

- **Short-term / working memory** — the current task's context: recent messages, tool results, scratchpad reasoning. Lives in the context window, discarded at session end.
- **Long-term memory** — persists across sessions in external storage. Splits into two flavors below.
- **Episodic memory** — specific past events and interactions ("last Tuesday the user asked about refunds and I escalated it"). It's the log of what happened.
- **Semantic memory** — distilled facts and knowledge ("the user prefers metric units", "the API rate limit is 100/min"). It's what the agent *knows*, abstracted from any single event.
- **Procedural memory** — learned how-to: successful strategies, reusable workflows, few-shot examples of good behavior.

Most agents need short-term memory (table stakes) plus some combination of episodic and semantic long-term memory. Procedural memory is the frontier and the most finicky.

## Short-term memory: managing the window

Short-term memory is really context-window management, and it's where most agents are quietly broken. The window is finite, so as a conversation grows you can't just keep appending. The strategies, in rough order of sophistication:

- **Full history** — keep everything. Simple, works until you blow the window or the bill.
- **Sliding window** — keep the last N turns. Cheap, but the agent forgets anything older.
- **Summarization buffer** — periodically compress old turns into a running summary, keeping recent turns verbatim. Good balance; the risk is lossy summaries dropping the one detail that mattered.
- **Structured working state** — maintain an explicit, updated state object (current goal, known facts, open questions) rather than raw transcript. More engineering, much more control.

The summarization buffer is my default for chat agents, but I've moved toward structured working state for task agents because raw transcript is a terrible representation of "what the agent is currently trying to do." This connects directly to [context engineering beyond prompts](https://blog.michaelsam94.com/context-engineering-beyond-prompts/) — deciding what occupies the window at each step is a first-class design problem, not an afterthought.

## Long-term memory: what to store and how

Long-term memory means writing information to external storage and retrieving relevant pieces back into context later. The two hard questions are *what to write* and *how to retrieve it*.

The storage layer is usually a hybrid, not a single database:

| Memory kind | Best storage | Retrieval method |
| --- | --- | --- |
| Semantic facts (open-ended) | Vector database | Similarity search by meaning |
| Structured facts (known fields) | Key-value / relational | Exact lookup by key |
| Episodic events | Append log + vector index | Recency + relevance |
| Procedural strategies | Curated example store | Task similarity |

The mistake I see is defaulting everything to a vector database because it's the fashionable answer. If the memory is "user's preferred language = Arabic", that's a key-value pair, not an embedding — store it structured and look it up exactly. Vector search shines for open-ended recall ("has the user mentioned anything about their car before?") where you're searching by meaning over unstructured notes. Most real agents want both, and the operational side of running the vector piece is its own topic I won't relitigate here.

## The write path is harder than the read path

Everyone focuses on retrieval, but the harder problem is *what to write to long-term memory in the first place*. Store every message and your memory fills with noise that pollutes future retrieval. Store nothing and there's nothing to recall. The write policy is the real design lever:

- **Reflection/extraction** — after a session, an LLM pass extracts durable facts ("user is vegetarian") and discards chit-chat. This is where semantic memory gets built.
- **Salience filtering** — only write things that seem important or that the user explicitly flagged.
- **Deduplication and updating** — new information should *update* existing memory, not just append. If the user changes their preference, the old fact must be superseded, or retrieval returns contradictions.

That last point causes real bugs. An agent that stored "user lives in Cairo" and later "user moved to Dubai" will, without a merge/update policy, retrieve both and get confused. Memory needs a notion of recency and correction, not just accumulation.

## Reliability: memory as a failure surface

Memory is a dependency, and like any dependency it introduces failure modes: stale facts, contradictory retrievals, retrieval that surfaces irrelevant memories and derails the agent, and — the scary one — memory poisoning, where bad or adversarial content written earlier corrupts later behavior. The same discipline that keeps agents dependable in general applies here, which I covered in [building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/): treat every retrieved memory as untrusted input, bound how much memory can enter context, and make memory writes auditable so you can trace why the agent "knew" something wrong.

A concrete guardrail I use: never let retrieved memory silently override the current instruction. Memory informs, the current task governs. That ordering prevents a stale preference from hijacking a fresh request.

## How much memory does your agent actually need?

The temptation is to build the full cognitive-architecture stack on day one. Resist it. My progression:

1. **Start with short-term only.** A good summarization buffer or structured working state handles a surprising range of agents.
2. **Add semantic long-term memory** (facts about the user/domain) when the agent visibly needs to remember across sessions. Reflection to extract facts, structured storage for known fields, vector search for open-ended notes.
3. **Add episodic memory** when the agent needs to recall specific past interactions.
4. **Add procedural memory** last, and only if you have evidence the agent benefits from remembering successful strategies.

Each layer adds retrieval latency, storage cost, and new failure modes. The best agent memory is the least memory that makes the agent behave right — every stored token is something that can later be retrieved at the wrong moment. Build it incrementally, measure whether recall actually improves outcomes, and keep the write policy tight. Memory is what turns a stateless model into something that feels like it knows you; it's also, if you're careless, what turns it into something that confidently misremembers.

## Resources

- [Generative Agents: Interactive Simulacra of Human Behavior (memory + reflection, arXiv)](https://arxiv.org/abs/2304.03442)
- [MemGPT: Towards LLMs as Operating Systems (arXiv)](https://arxiv.org/abs/2310.08560)
- [LangGraph — memory concepts documentation](https://langchain-ai.github.io/langgraph/concepts/memory/)
- [Mem0 — memory layer for AI agents](https://github.com/mem0ai/mem0)
- [A Survey on the Memory Mechanism of Large Language Model based Agents (arXiv)](https://arxiv.org/abs/2404.13501)
