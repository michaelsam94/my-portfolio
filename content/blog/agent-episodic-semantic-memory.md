---
title: "Episodic vs Semantic Agent Memory"
slug: "agent-episodic-semantic-memory"
description: "Design agent memory as episodic (what happened) and semantic (what is true): storage patterns, retrieval, forgetting, and avoiding context bloat."
datePublished: "2026-06-24"
dateModified: "2026-06-24"
tags: ["AI Agents", "LLM", "RAG", "Architecture"]
keywords: "agent memory, episodic memory LLM, semantic memory agents, long-term agent memory, agent context management"
faq:
  - q: "What is the difference between episodic and semantic agent memory?"
    a: "Episodic memory stores specific past interactions — what the user asked, what tools returned, what decisions were made. Semantic memory stores distilled facts and preferences independent of when they were learned — 'user prefers metric units,' 'project deadline is March 15.' Episodic is the raw log; semantic is the knowledge extracted from it."
  - q: "When should agents write to semantic memory?"
    a: "After interactions where durable facts emerge: stated preferences, corrections, project context, recurring entities. Use an extraction step — LLM or rules — to pull facts from episodic logs and upsert into semantic store. Don't write every chat turn to semantic memory or you'll pollute retrieval with noise."
  - q: "How do you prevent agent memory from growing unbounded?"
    a: "Episodic memory rolls up: summarize sessions into paragraph summaries, archive raw logs to cold storage, retrieve only recent episodes plus relevant semantic facts. Semantic memory deduplicates and decays — merge conflicting facts, drop low-confidence entries, and TTL stale preferences unless reconfirmed."
---

Agent memory is not "put everything in the vector database and hope retrieval works." That's how you get an agent that remembers the user mentioned pizza three weeks ago and injects it into a billing support conversation. Production memory needs two distinct stores — episodic (what happened) and semantic (what is true) — with explicit promotion rules between them. I've rebuilt agent memory twice because I conflated these layers the first time; the second architecture cut irrelevant retrievals by roughly 80%.

## Two memory types, two retrieval patterns

**Episodic memory** is the event log:
- "On June 3, user asked to reschedule order #4521"
- "Tool `search_docs` returned 3 chunks about OAuth"
- "Agent failed at step 7, user corrected the date format"

**Semantic memory** is the knowledge base:
- "User's timezone is America/Chicago"
- "User's company uses SAML SSO"
- "Project Alpha deadline: 2026-03-15"

| Property | Episodic | Semantic |
|----------|----------|----------|
| Granularity | Per turn / per session | Per fact |
| Retrieval | Recency + relevance | Similarity + entity match |
| Storage | Append-heavy | Upsert / merge |
| Context use | "What did we discuss?" | "What do I know about this user?" |

## Architecture

```
Interaction → Episodic store (raw log)
                    ↓ extraction job
              Semantic store (facts + entities)
                    ↓ retrieval at session start
              Context assembly → LLM prompt
```

At session start, assemble context from:
1. **Semantic facts** matching user/tenant (top-K by entity ID, not vector similarity alone)
2. **Recent episodic summary** (last session's rollup, not raw transcript)
3. **Current session episodic** (in-context, compressed as it grows)

Never dump the full episodic log into the prompt. That's linear token growth and retrieval noise.

## Extraction: episodic → semantic

Run extraction after session end or at natural breakpoints:

```python
EXTRACTION_PROMPT = """
Given this conversation, extract durable facts about the user or project.
Return JSON: [{"fact": "...", "confidence": 0.0-1.0, "entity": "user|project|..."}]
Only include facts likely useful in future sessions. Skip transient task details.
"""

async def promote_to_semantic(session_id: str):
    transcript = await episodic.get_session(session_id)
    facts = await llm.extract(EXTRACTION_PROMPT, transcript)
    for fact in facts:
        if fact.confidence >= 0.7:
            await semantic.upsert(
                entity=fact.entity,
                fact=fact.fact,
                source_session=session_id,
            )
```

Upsert semantics matter: "User prefers dark mode" + later "User switched to light mode" should merge, not coexist. Store timestamps and prefer the newer fact on conflict.

## Retrieval that doesn't hallucinate context

Semantic retrieval by vector similarity alone retrieves "similar-sounding" facts that may be about different entities. Always filter by entity ID (user ID, tenant ID, project ID) first, then rank by relevance within that scope.

For episodic retrieval, prefer recency-weighted search over pure embedding similarity. "What we discussed yesterday about the API" is a recency query, not a semantic one.

## Forgetting is a feature

Memory without forgetting becomes adversarial context — old facts contradict new ones, irrelevant episodes crowd out useful ones. Policies I use:

- **Episodic raw logs**: 30-day hot storage, then summarize-and-archive
- **Episodic summaries**: 90-day retention, then drop unless tagged important
- **Semantic facts**: decay confidence 10% per month without reconfirmation; drop below 0.3
- **User deletion**: hard delete both stores on GDPR request — design for this upfront

The [summarization strategies](https://blog.michaelsam94.com/agent-memory-summarization-strategies/) for long sessions are how episodic memory stays bounded without losing thread.

## Common mistakes

**Storing tool outputs in semantic memory.** Raw API responses aren't facts. Extract structured fields first.

**Retrieving memory every turn.** Retrieve once at session start and after explicit "remember this" commands. Per-turn retrieval adds latency and drift.

**No source attribution.** Every semantic fact should link to the session that created it. When the agent cites a fact, you need provenance for debugging and user correction ("that's outdated").

## Memory architecture diagram

```
User message
    → Episodic store (raw turn + tool I/O)
    → Summarizer (async, end of session)
    → Semantic store (extracted facts + embeddings)
    → Next session: retrieve semantic + recent episodic summary
```

Keep episodic and semantic in separate indexes — different retention, different query patterns. Mixing them in one vector DB complicates GDPR deletion and TTL policies.

## Conflict resolution

When semantic memory contains contradictions:

```python
async def merge_fact(new: Fact, existing: Fact) -> Fact:
    if new.timestamp > existing.timestamp:
        return new.replace(confidence=min(1.0, new.confidence + 0.1))
    if existing.confidence > new.confidence + 0.2:
        return existing  # strong prior wins
    return new.replace(confidence=0.5)  # flag for clarification
```

Surface low-confidence conflicts to the user: "Last time you mentioned preferring email, but today you asked for SMS — which should I use?"

## Evaluation metrics

Track memory quality, not just retrieval hit rate:

- **Fact accuracy** — human audit sample of stored facts monthly
- **Retrieval precision** — retrieved facts relevant to current turn
- **Stale fact rate** — facts older than 90 days still retrieved
- **Contradiction rate** — conflicting facts in same entity scope

Pair with [multi-turn state management](https://blog.michaelsam94.com/agent-multi-turn-state-management/) for session-scoped state vs long-term memory boundaries.

## Production checklist

- [ ] Episodic and semantic stores physically separated
- [ ] Every semantic fact linked to source session ID
- [ ] Confidence decay policy for stale facts
- [ ] GDPR hard-delete workflow for both stores
- [ ] Contradiction detection surfaces low-confidence conflicts to user

Memory retrieval latency adds up — cache the top semantic facts per user at session start rather than embedding-searching on every turn.

## Common production mistakes

Teams get episodic semantic memory wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using episodic semantic memory loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Resources

- [MemGPT / virtual context management paper](https://arxiv.org/abs/2310.08560)
- [LangGraph memory documentation](https://langchain-ai.github.io/langgraph/concepts/memory/)
- [Zep — long-term memory for AI assistants](https://docs.getzep.com/)
- [OpenAI assistants API — thread memory](https://platform.openai.com/docs/assistants/overview)
- [Evaluating retrieval for RAG systems](https://blog.michaelsam94.com/evaluating-retrieval-metrics-rag/)
