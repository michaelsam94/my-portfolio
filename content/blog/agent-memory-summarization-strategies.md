---
title: "Memory Summarization for Long Sessions"
slug: "agent-memory-summarization-strategies"
description: "Keep long agent sessions coherent with memory summarization: rolling summaries, hierarchical compression, and when to summarize vs retrieve raw history."
datePublished: "2026-06-29"
dateModified: "2026-06-29"
tags: ["AI Agents", "LLM", "Architecture", "RAG"]
keywords: "agent memory summarization, long context agents, conversation compression, agent session memory, context window management"
faq:
  - q: "When should an agent summarize conversation history?"
    a: "Summarize when the conversation exceeds 60–70% of your effective context budget, after completing a distinct subtask, or when switching topics. Don't summarize mid-task while the agent still needs exact tool outputs — summarize the completed phase and carry forward only conclusions and state."
  - q: "What should be preserved vs discarded in summarization?"
    a: "Preserve: user goals, confirmed facts, decisions made, pending action items, entity IDs, and error corrections. Discard: raw tool outputs already processed, repeated clarifications, failed attempts superseded by later success, and conversational filler. When in doubt, keep structured state (JSON) and summarize narrative."
  - q: "How do rolling summaries differ from one-shot compression?"
    a: "Rolling summaries update incrementally — each new summary incorporates the previous summary plus recent turns. One-shot compression rebuilds from scratch when a threshold is hit. Rolling is cheaper and preserves continuity; one-shot avoids summary-of-summary drift but costs more. Most production agents use rolling with periodic one-shot refresh every 5–10 rollups."
---

Long agent sessions die from context bloat long before they die from model capability. By turn 30, you're paying to re-send fifteen tool outputs the agent already processed, three failed attempts it corrected, and a sidebar about lunch preferences that snuck in during a clarification. Summarization isn't optional compression — it's how agents stay coherent, affordable, and fast across sessions that span dozens of turns. The teams whose agents "remember everything" are either lying or running summarization they haven't documented.

## The context budget problem

A typical agent at turn 25:

| Component | Tokens | Needed? |
|-----------|--------|---------|
| System prompt | 800 | Yes |
| Semantic memory | 500 | Yes |
| Turns 1–20 (raw) | 18,000 | Mostly no |
| Turns 21–25 (recent) | 4,000 | Yes |
| Tool outputs in history | 8,000 | Rarely |

That 18K of old turns is where your budget goes. Summarize it to 400 tokens and you've freed room for five more productive turns.

## Rolling summary architecture

Maintain three layers in your context assembly:

```
[System prompt]
[Semantic facts about user/project]
[Session summary — compressed turns 1..N-5]
[Recent turns — raw, last 5 turns verbatim]
[Current turn]
```

Update the session summary after each completed subtask:

```python
SUMMARIZE_PROMPT = """
Update this session summary with the new turns. Preserve:
- User's overall goal and any changes to it
- Key decisions and their rationale
- Important entity IDs, names, dates
- Pending items and blockers
- Corrections the user made

Drop: tool output details already acted on, failed attempts that were resolved.

Previous summary:
{previous_summary}

New turns to incorporate:
{new_turns}

Return the updated summary in 200-400 words.
"""

async def maybe_summarize(session: Session):
    if session.token_count() < SUMMARIZE_THRESHOLD:
        return
    session.summary = await llm.complete(
        SUMMARIZE_PROMPT.format(
            previous_summary=session.summary or "(none)",
            new_turns=session.turns_since_last_summary(),
        )
    )
    session.archive_turns(session.turns_since_last_summary())
    session.mark_summarized()
```

## Hierarchical compression for very long sessions

Sessions exceeding 50+ turns need two levels:

1. **Phase summaries** — one per completed subtask ("Researched 3 vendors, selected Vendor B based on price")
2. **Session summary** — rollup of phase summaries ("User is setting up monitoring for Project Alpha; vendor selected, deployment pending")

```
Session summary (300 tokens)
  ├── Phase 1: Requirements gathering (80 tokens)
  ├── Phase 2: Vendor research (100 tokens)
  └── Phase 3: Deployment planning (in progress, raw turns)
```

When the session summary itself exceeds 500 tokens, compress phases into the session summary and drop individual phase detail. This is the periodic one-shot refresh that prevents summary-of-summary drift.

## Structured state beats narrative for facts

Don't rely on summarization to preserve exact values. Maintain a typed state object alongside the narrative summary:

```python
@dataclass
class SessionState:
    goal: str
    entities: dict[str, str]       # {"order_id": "4521", "vendor": "Acme"}
    completed_steps: list[str]
    pending_actions: list[str]
    user_preferences: dict[str, str]
```

Inject `SessionState` as JSON in the system prompt. Summaries handle *narrative* continuity; structured state handles *factual* continuity. An LLM summary might paraphrase "order 4521" as "the customer's recent order" — structured state won't.

This pairs directly with [episodic vs semantic memory](https://blog.michaelsam94.com/agent-episodic-semantic-memory/): promote durable facts from session state to semantic store at session end.

## When NOT to summarize

- **Mid-tool-chain**: agent called search, got results, hasn't acted yet — it needs the raw results
- **Active debugging**: user is correcting agent errors — keep the error context verbatim
- **Legal/compliance transcripts**: some domains require full verbatim logs in cold storage even if the active context is summarized

Summarize the archive, not the deletion. Raw turns go to cold storage (S3, logging pipeline) even when dropped from active context.

## Measuring summarization quality

Bad summarization silently drops critical facts. Detect it:

- **Fact retention evals**: after summarization, ask the model fact-specific questions ("what order ID were we discussing?") and check against ground truth
- **Task completion rate**: if completion drops after enabling summarization, your summaries are lossy
- **User correction rate**: spike in "no, I said X" messages indicates summary drift

Run these on a held-out set of long session transcripts monthly. Summarization prompts drift too.

## Cost impact

Summarization itself costs tokens — a 500-token summary call every 10 turns is roughly 50 tokens per turn amortized. Compare that to re-sending 5,000 tokens of history every turn after turn 20. The break-even is usually around turn 8–12. Track both costs in your [agent budget dashboard](https://blog.michaelsam94.com/agent-cost-control-budgets/).

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get memory summarization strategies wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Agent systems using memory summarization strategies loop infinitely when tool errors are swallowed, subagent budgets have no hard cap, and human-in-the-loop gates are bypassed under latency pressure.

## Debugging and triage workflow

When memory summarization strategies misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MemGPT — virtual context management](https://arxiv.org/abs/2310.08560)
- [LangChain conversation summary memory](https://python.langchain.com/docs/versions/migrating_memory/)
- [Anthropic prompt caching for long contexts](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI context window best practices](https://platform.openai.com/docs/guides/prompt-engineering)
- [Multi-turn state management for agents](https://blog.michaelsam94.com/agent-multi-turn-state-management/)
