---
title: "Designing a Conversation Memory Store"
slug: "llm-app-conversation-memory-store"
description: "How to persist and retrieve conversation memory for LLM apps: short-term context, summarization tiers, vector recall, and schema design that scales past toy Redis dumps."
datePublished: "2024-10-10"
dateModified: "2024-10-10"
tags: ["AI", "LLM", "Architecture", "Backend"]
keywords: "conversation memory LLM, chat history storage, LLM session state, memory summarization, long-term agent memory"
faq:
  - q: "Should conversation history live in the database or a cache?"
    a: "Both. Redis or similar for hot session state (last N turns, fast reads on every request). Postgres for durable history, search, and analytics. On session end or every K turns, flush from cache to durable storage. Never rely on cache alone — evictions happen."
  - q: "How many past turns should I send to the model?"
    a: "Send the last 4–8 turns verbatim plus a rolling summary of everything before. Exact count depends on turn length and your context budget. Measure: if dropping from 10 to 6 verbatim turns doesn't change eval scores, you're wasting tokens."
  - q: "When do I need vector search over past conversations?"
    a: "When users reference things from weeks ago ('like we discussed last month about the API change'). Keyword search handles explicit references; vector recall handles paraphrased callbacks. Most support bots need this by month two."
---

The support bot forgot what the customer said three messages ago. Not because the model has amnesia — because someone stored the session in a process-local variable and the next request hit a different pod. Conversation memory is infrastructure, not a prompt trick. Get the store wrong and no amount of prompt engineering fixes the user experience.

## Memory tiers

Production apps need at least three tiers:

| Tier | Contents | Storage | TTL |
|------|----------|---------|-----|
| Working | Last N turns, tool outputs | Redis | Session lifetime |
| Episodic | Full transcript, metadata | Postgres | Months–years |
| Semantic | Summaries, extracted facts, embeddings | Postgres + vector index | Permanent |

Working memory feeds the model on every turn. Episodic memory is the audit trail. Semantic memory is what you retrieve when the user says "remember when we talked about pricing?"

## Schema that doesn't paint you into a corner

```sql
CREATE TABLE conversations (
  id          UUID PRIMARY KEY,
  tenant_id   UUID NOT NULL,
  user_id     UUID NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata    JSONB DEFAULT '{}'
);

CREATE TABLE turns (
  id              UUID PRIMARY KEY,
  conversation_id UUID REFERENCES conversations(id),
  role            TEXT NOT NULL CHECK (role IN ('user','assistant','tool','system')),
  content         TEXT NOT NULL,
  token_count     INT,
  tool_calls      JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX turns_conv_created ON turns(conversation_id, created_at);
```

Store tool calls separately from assistant text — you'll need them for debugging and replay, but they bloat context if sent verbatim every turn.

Add a `summaries` table for rolling compression:

```sql
CREATE TABLE conversation_summaries (
  conversation_id UUID PRIMARY KEY REFERENCES conversations(id),
  summary         TEXT NOT NULL,
  covers_through  UUID REFERENCES turns(id),  -- last turn included
  updated_at      TIMESTAMPTZ NOT NULL
);
```

## Context assembly

The orchestrator builds the prompt context — not the client, not the model:

```python
async def build_context(conversation_id: str, budget: int) -> list[Message]:
    summary = await store.get_summary(conversation_id)
    recent = await store.get_recent_turns(conversation_id, limit=8)
    recalled = await store.semantic_recall(conversation_id, recent[-1].content, k=3)

    messages = [SystemMessage(SYSTEM_PROMPT)]
    if summary:
        messages.append(SystemMessage(f"Prior context: {summary}"))
    for chunk in recalled:
        messages.append(SystemMessage(f"Recalled: {chunk.text}"))
    messages.extend(recent)
    return trim_to_budget(messages, budget)
```

Order matters: system → summary → recalled facts → recent turns. Recalled chunks before recent turns prevents the model from overweighting stale information at the end of context.

## Summarization triggers

Don't summarize every turn — it's expensive and lossy. Trigger on:

- Token count exceeds 60% of context budget
- Session idle for 5+ minutes (good time to compress async)
- Explicit session end
- Topic shift detected (optional classifier)

```python
async def maybe_summarize(conversation_id: str) -> None:
    tokens = await store.count_tokens_since_summary(conversation_id)
    if tokens < SUMMARIZE_THRESHOLD:
        return
    turns = await store.get_unsummarized_turns(conversation_id)
    new_summary = await summarizer.merge(
        existing=await store.get_summary(conversation_id),
        turns=turns,
    )
    await store.save_summary(conversation_id, new_summary, turns[-1].id)
```

Use a cheap model for summarization. The summary doesn't need to be literary — it needs to preserve decisions, names, numbers, and open questions.

## Semantic recall

Embed conversation segments (summary chunks or turn groups) into your vector index scoped by `tenant_id` and `user_id`:

```python
async def semantic_recall(conversation_id: str, query: str, k: int) -> list[Chunk]:
    embedding = await embed(query)
    return await vector_db.search(
        embedding,
        filter={"conversation_id": conversation_id},
        top_k=k,
    )
```

Scope carefully. A recall query that searches all tenant conversations is a data leak waiting for a missing filter clause.

## Multi-device and concurrent sessions

Users open the same chat on phone and desktop. Options:

- **Single session per user** — simpler, but concurrent edits conflict
- **Session per device, shared memory** — semantic tier is shared; working memory is per-device
- **Optimistic locking** on turns with `version` column — reject stale writes

I've seen the single-session model break on WebSocket reconnects. Store a `client_message_id` for deduplication.

## Privacy and retention

Memory stores accumulate PII fast. Build in:

- Retention policies per tenant (30/90/365 days)
- Right-to-erasure that deletes all three tiers
- PII redaction before embedding (names, emails, card numbers)
- Encryption at rest on Postgres, TLS to Redis

GDPR deletion means cascading deletes across turns, summaries, and vector embeddings — test this path before a legal request arrives.

## Common production mistakes

Teams get app conversation memory store wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around app conversation memory store break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When app conversation memory store misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560)
- [LangChain conversation memory modules](https://python.langchain.com/docs/concepts/chat_history/)
- [Redis session management patterns](https://redis.io/docs/latest/develop/use/patterns/session-storage/)
- [pgvector for Postgres embeddings](https://github.com/pgvector/pgvector)
- [Anthropic long context prompting tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
