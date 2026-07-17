---
title: "Context Pruning Heuristics for Long-Running Agents"
slug: "agent-context-pruning-heuristics"
description: "Heuristic and scored pruning strategies that trim agent context windows without losing task-critical facts — recency bias, relevance scoring, tool-result compaction, and eval-gated rollouts."
datePublished: "2025-06-14"
dateModified: "2025-06-14"
tags: ["AI Agents", "Context", "LLM", "Optimization"]
keywords: "context pruning agent, token window management, RAG context trimming, agent memory heuristics, long context optimization"
faq:
  - q: "When should pruning run relative to retrieval and tool calls?"
    a: "Prune after tool results land and before the next model call — never mid-generation. Run a lightweight token estimate every turn; trigger pruning when projected usage exceeds 75–85% of the window minus reserved output tokens."
  - q: "Are heuristics enough or do you need an LLM summarizer?"
    a: "Heuristics handle 80% of volume: drop duplicate chunks, cap tool JSON arrays, and evict stale turns by recency. Reserve LLM summarization for dialogue segments where semantic compression matters and heuristics would delete named entities or IDs."
  - q: "How do you prevent pruning from breaking multi-step tasks?"
    a: "Maintain a protected facts block — order IDs, file paths, user confirmations — extracted before any pruning runs. Never prune tool call arguments, system prompts, or the last N turns involved in the active sub-task."
  - q: "What metrics prove pruning is safe to widen?"
    a: "Compare task success rate, tool-selection accuracy, and re-ask rate on golden multi-turn trajectories with pruning on vs off. Block rollout if success drops more than 1–2% or if users repeat the same question within three turns."
---

A support agent on turn forty still remembers the user's billing address from turn two — but also carries the full JSON payload of twelve failed API calls, four redundant RAG chunks about password resets, and a tool trace nobody will read again. The model does not need all of it. **Context pruning heuristics** decide what stays, what compacts, and what disappears — fast enough to run every turn, deterministic enough to debug, and conservative enough that you do not amputate the invoice number mid-refund.

Pruning is not summarization. Summarization is lossy and expensive. Heuristics are rules and scores applied to structured context segments before you spend tokens on a compression model pass. The best production stacks layer both: heuristics first, summarization only where heuristics cannot preserve semantics cheaply.

## Segment your context before pruning anything

Treat the agent prompt as a stack of independent segments, each with its own retention policy:

| Segment | Typical share | Default retention |
|---------|---------------|-------------------|
| System prompt + tool schemas | 15–25% | Never prune |
| Protected facts (extracted JSON) | 2–5% | Never prune |
| Active sub-task turns (last K) | 10–20% | Keep full fidelity |
| Older dialogue | 15–30% | Summarize or drop |
| Tool results | 25–45% | Field-prune, cap size |
| RAG retrieved chunks | 10–20% | Score and dedupe |

If you prune without segmentation, you will eventually delete a system instruction or a pending tool call — the two failure modes that produce the wildest agent behavior.

## Heuristic tier 1: deterministic eviction rules

These rules require no embeddings and no model calls. Apply them in order:

**Recency floor.** Never prune the last `K` user–assistant turn pairs (typically K=4–8 depending on task depth). Active slot-filling and clarification loops live here.

**Tool argument preservation.** Any message containing a `tool_calls` block or `tool_call_id` response stays until the sub-task completes or the tool result is promoted into protected facts.

**Duplicate chunk removal.** Hash normalized chunk text (lowercase, whitespace collapsed). Drop duplicates keeping the highest retrieval score.

**Stale turn eviction.** Turns older than `T` minutes with no reference in protected facts and no entity overlap with the current user message are candidates for removal. Start with T=30 for chat, T=120 for long research sessions.

**Array and payload caps.** Tool results returning JSON arrays get truncated: keep first N items plus total count metadata. Default N=20 for list endpoints, N=5 for log dumps.

```python
# pruning/heuristics.py
from dataclasses import dataclass
from hashlib import sha256
import json

@dataclass
class ContextSegment:
    kind: str          # system | facts | dialogue | tool | rag
    content: str
    tokens: int
    turn_index: int
    retrieval_score: float = 0.0
    protected: bool = False

def dedupe_rag_chunks(segments: list[ContextSegment]) -> list[ContextSegment]:
    seen: set[str] = set()
    kept: list[ContextSegment] = []
    for seg in sorted(segments, key=lambda s: -s.retrieval_score):
        if seg.kind != "rag":
            kept.append(seg)
            continue
        key = sha256(seg.content.lower().split()).hexdigest()
        if key not in seen:
            seen.add(key)
            kept.append(seg)
    return kept

def cap_tool_json(segment: ContextSegment, max_items: int = 20) -> ContextSegment:
    if segment.kind != "tool":
        return segment
    try:
        data = json.loads(segment.content)
        if isinstance(data, list) and len(data) > max_items:
            trimmed = data[:max_items]
            segment.content = json.dumps({
                "items": trimmed,
                "_pruned": True,
                "_original_count": len(data),
            })
    except json.JSONDecodeError:
        pass
    return segment
```

These rules alone recover 30–50% of token budget on tool-heavy agents without touching dialogue.

## Heuristic tier 2: relevance scoring

When deterministic rules are not enough to hit your budget target, score each prunable segment against the current user intent and drop lowest scores until you fit.

**Query overlap score.** Tokenize the current user message and each segment. Score = |intersection| / |segment tokens|. Cheap and surprisingly effective for evicting unrelated RAG chunks.

**Entity persistence.** Extract entities (IDs, emails, amounts) from protected facts and the current message. Boost score for segments sharing entities; penalize segments with zero overlap when facts block is non-empty.

**Tool lineage.** Segments produced by tools invoked in the last two turns get a +0.3 score boost. Users often refer to "that list" or "the error above" — lineage prevents premature eviction.

**Recency decay.** Multiply score by `exp(-λ * turns_ago)` with λ≈0.15. Smooth preference for recent context without hard cutoffs.

```python
import math
import re

ENTITY_PATTERN = re.compile(r"\b[A-Z]{2,}-\d+\b|\b[\w.+-]+@[\w-]+\.\w+\b")

def relevance_score(segment: ContextSegment, user_msg: str, facts: set[str]) -> float:
    user_tokens = set(user_msg.lower().split())
    seg_tokens = set(segment.content.lower().split())
    overlap = len(user_tokens & seg_tokens) / max(len(seg_tokens), 1)

    seg_entities = set(ENTITY_PATTERN.findall(segment.content))
    fact_overlap = len(seg_entities & facts) / max(len(seg_entities), 1) if seg_entities else 0

    recency = math.exp(-0.15 * (100 - segment.turn_index))  # higher turn_index = more recent
    lineage_boost = 0.3 if segment.kind == "tool" and segment.turn_index >= 98 else 0

    return overlap + 0.5 * fact_overlap + 0.2 * recency + lineage_boost

def prune_to_budget(
    segments: list[ContextSegment],
    budget_tokens: int,
    user_msg: str,
    facts: set[str],
) -> list[ContextSegment]:
    protected = [s for s in segments if s.protected]
    prunable = [s for s in segments if not s.protected]

    protected_tokens = sum(s.tokens for s in protected)
    remaining = budget_tokens - protected_tokens

    prunable.sort(key=lambda s: relevance_score(s, user_msg, facts), reverse=True)
    kept, used = [], 0
    for seg in prunable:
        if used + seg.tokens <= remaining:
            kept.append(seg)
            used += seg.tokens
    return protected + kept
```

Log every pruned segment ID and score to your observability stack. When users say "the agent forgot X," you need to answer whether X was pruned at turn 37 and why its score was 0.04.

## Protected facts extraction

Heuristics fail when critical strings live only in prose. Extract before pruning:

```python
from pydantic import BaseModel

class ProtectedFacts(BaseModel):
    order_ids: list[str] = []
    confirmed_values: dict[str, str] = {}
    open_questions: list[str] = []

def extract_facts(messages: list[dict]) -> ProtectedFacts:
    # Rule-based pass: regex for IDs, amounts, dates
    # Optional small-model pass on last 6 turns for open_questions
    ...
```

Inject `ProtectedFacts` as a compact JSON block marked `protected=True`. Even if every dialogue turn from turn 10 is evicted, the agent still sees `order_ids: ["ORD-8842"]`.

## When to escalate from heuristics to summarization

Trigger LLM summarization only when:

1. Heuristic pruning still exceeds budget by >10%
2. The segments to evict include dialogue (not just tool/RAG bloat)
3. Protected facts extraction ran and the summary prompt explicitly lists facts to preserve

Summarize in chunks of 6–10 turns, producing 150–300 token summaries. Append summaries as a single `kind=dialogue_summary` segment rather than mutating original messages — you want auditability.

Never summarize tool call arguments or user confirmations worded as "yes, charge $500."

## Budget allocation and reserved output tokens

Pruning targets **input budget**, not the full context window:

```
input_budget = context_window - max_output_tokens - safety_margin
```

Reserve output tokens explicitly. Agents that plan multi-step tool chains need 2–4k output headroom. Pruning to 128k total then requesting 8k output causes mid-stream truncation — a different failure mode that looks like "the agent stopped mid-sentence."

Safety margin: 512–1024 tokens for tokenizer mismatch between your counter and the provider's.

## Eval gates before changing heuristics

Any change to K (recency floor), score weights, or array caps needs regression testing:

1. **Golden trajectories** — 50–200 recorded multi-turn sessions with expected tool calls and final answers
2. **Pruning diff report** — what each heuristic removed vs baseline
3. **Success rate delta** — automated grader or human label on sample
4. **Re-ask detector** — flag sessions where user repeats the same question within 3 turns post-pruning change

Ship heuristic changes behind feature flags per tenant. Compare `agent.pruning.tokens_saved_p50` against `agent.task.success_rate` weekly.

## Operational telemetry

Instrument these metrics from day one:

- `context.tokens.before_pruning` / `context.tokens.after_pruning`
- `context.segments.pruned_count` by kind (tool, rag, dialogue)
- `context.pruning.triggered` — boolean per turn
- `context.facts.extracted_count`
- `context.budget.exceeded_attempts` — pruning could not fit budget; emergency truncation fired

Alert when `budget.exceeded_attempts` rises above 1% of turns — your tool schemas or RAG chunk size is wrong upstream, not your pruning logic.

## Anti-patterns that cause incidents

**Pruning the system prompt to save tokens.** Some teams dynamically shorten tool schemas under pressure. That changes tool selection behavior silently. Shrink schemas at design time, not runtime.

**Global summarization without facts sidecar.** Summaries hallucinate IDs. Always extract first.

**Same heuristics for all agent types.** Research agents need long RAG retention; transactional agents need long tool lineage. Parameterize K, T, and score weights per agent profile.

**Pruning without user-visible latency budget.** Scoring 200 segments with embedding calls every turn adds 200ms. Heuristics tier 1 should complete in <5ms; tier 2 lexical scoring in <20ms. Embeddings belong offline or every N turns, not every message.

## The takeaway

Context pruning heuristics keep long-running agents inside token budgets without waiting for an expensive summarizer on every turn. Segment the prompt, protect facts and active turns, apply deterministic rules first, score what remains, and gate every parameter change with golden trajectories. The goal is not minimum tokens — it is maximum task success per dollar with debuggable, auditable decisions about what the agent still remembers.

## Resources

- [Lost in the Middle — LLM context position bias](https://arxiv.org/abs/2307.03172)
- [LangChain — Conversation buffer window memory](https://python.langchain.com/docs/modules/memory/types/buffer_window/)
- [Anthropic — Prompt caching and long context](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI — tiktoken token counting](https://github.com/openai/tiktoken)
- [LlamaIndex — Node postprocessors for retrieval](https://docs.llamaindex.ai/en/stable/module_guides/querying/node_postprocessors/)
