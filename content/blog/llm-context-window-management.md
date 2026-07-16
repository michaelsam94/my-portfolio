---
title: "Managing the LLM Context Window"
slug: "llm-context-window-management"
description: "Fit more into less: context budgeting, chunk prioritization, summarization tiers, middle-context degradation, and techniques that keep long conversations coherent without blowing token budgets."
datePublished: "2024-11-12"
dateModified: "2024-11-12"
tags: ["AI", "LLM", "Architecture", "Machine Learning"]
keywords: "LLM context window management, token budget, context compression, long context LLM, prompt truncation strategies"
faq:
  - q: "How much of the context window should I actually use?"
    a: "Reserve 20–30% for output tokens and safety margin. If your model supports 128K input, targeting 80–90K of composed context leaves room for response and avoids edge-case truncation bugs. More context isn't always better — retrieval quality and prompt structure often beat stuffing everything in."
  - q: "What gets cut first when context overflows?"
    a: "Cut in this order: oldest tool outputs (summarize first), middle conversation turns (keep first and last verbatim), lowest-scored retrieval chunks, then older user messages. Never cut the system prompt or the current user message. Log what was dropped so you can debug quality regressions."
  - q: "Do long-context models eliminate the need for RAG?"
    a: "No. Long context solves capacity, not relevance. Stuffing 500 pages and asking a question still hits 'lost in the middle' degradation — models miss facts buried in the center. RAG selects relevant chunks; long context holds the conversation and retrieved set. Use both."
---

A 128K context window feels infinite until you embed a 40-page PDF, attach six tool outputs, and include twelve turns of conversation history — and the API returns a 400 because you're at 131,072 tokens. Context window management isn't about buying bigger models. It's about deciding what the model sees, in what order, and what gets compressed or dropped when space runs out.

## Budget allocation

Define explicit budgets per request:

```python
@dataclass
class ContextBudget:
    total: int = 100_000
    system_prompt: int = 2_000
    retrieval: int = 30_000
    conversation: int = 40_000
    tool_outputs: int = 20_000
    output_reserved: int = 8_000
```

Allocate before assembly. When retrieval returns 50K tokens of chunks, rerank and trim to 30K — don't silently overflow.

## Priority-based packing

Assign priority scores, pack greedily until budget fills:

```python
def pack_context(items: list[ContextItem], budget: int) -> list[ContextItem]:
    ranked = sorted(items, key=lambda x: x.priority, reverse=True)
    packed, used = [], 0
    for item in ranked:
        if used + item.tokens <= budget:
            packed.append(item)
            used += item.tokens
    return packed
```

Typical priorities:

| Content | Priority | Reason |
|---------|----------|--------|
| System prompt | 100 | Always include |
| Current user message | 100 | Always include |
| Last 2–3 turns | 90 | Immediate continuity |
| Top retrieval chunks | 70–85 | Grounding |
| Summarized history | 50 | Background |
| Old tool outputs | 20 | Rarely needed verbatim |

## Lost in the middle

Models disproportionately attend to the beginning and end of context. Mitigations:

- **Place critical instructions at top AND bottom** of context (repeat key constraints)
- **Put best retrieval chunks at edges**, lower-ranked in middle
- **Use explicit references**: "Based on [Doc-A] and [Doc-B] above..."
- **Rerank aggressively** — 10 great chunks beat 40 mediocre ones

Research consistently shows U-shaped attention. Design for it.

## Summarization tiers

Don't choose between full history and no history — tier it:

```python
async def assemble_conversation(session_id: str, budget: int) -> list[Message]:
    recent = await store.get_turns(session_id, last=6)           # verbatim
    summary = await store.get_summary(session_id)                # compressed older
    if summary:
        return [
            SystemMessage(f"Conversation summary: {summary}"),
            *recent,
        ]
    return recent
```

Refresh summaries asynchronously when token count crosses threshold — don't block the user request.

## Tool output compression

Tool outputs are context killers. A single `fetch_webpage` can return 15K tokens.

```python
def compress_tool_output(output: str, max_tokens: int) -> str:
    if count_tokens(output) <= max_tokens:
        return output
    # Structured extraction for JSON/HTML
    if is_json(output):
        return extract_relevant_fields(output, max_tokens)
    # LLM summarize for prose
    return summarizer.summarize(output, max_tokens=max_tokens)
```

Store full output in the session store; send compressed version to the model. User can ask "show me the full result" if needed.

## Token counting accuracy

Different providers count differently. Use their tokenizer:

```python
import tiktoken

def count_messages(messages: list[dict], model: str) -> int:
    enc = tiktoken.encoding_for_model(model)
    # Include per-message overhead (role tokens, formatting)
    ...
```

Count before sending. Build 5% headroom for counting drift.

## Dynamic model routing by context size

```python
def select_model(messages: list, retrieval: list) -> str:
    total = count_tokens(messages) + count_tokens(retrieval)
    if total < 8_000:
        return "gpt-4o-mini"
    if total < 100_000:
        return "gpt-4o"
    return "gpt-4o-long"  # or trigger RAG harder, reject oversized uploads
```

Small context on small models saves money. Don't send 500 tokens to a 128K model.

## Monitoring

Track per request:

- Total input tokens by component (system, RAG, history, tools)
- Truncation events (what was dropped)
- Output quality vs context size (eval correlation)

If quality drops above 60K input tokens, your retrieval or summarization needs work — not a bigger window.

## Lost-in-the-middle mitigation

LLMs attend poorly to information in the middle of long contexts:

```
[System prompt] [RECENT TURN] [middle chunks — often ignored] [FIRST TURN]
```

Mitigation strategies:

```python
def reorder_for_attention(chunks: list[str], query: str) -> list[str]:
    # Place most relevant chunks at start and end
    scored = [(chunk, relevance_score(query, chunk)) for chunk in chunks]
    scored.sort(key=lambda x: -x[1])
    # Interleave: best at start, second-best at end, rest in middle
    reordered = [scored[0][0]]
    if len(scored) > 1:
        reordered.extend([c for c, _ in scored[2:]])
        reordered.append(scored[1][0])
    return reordered
```

Place highest-relevance chunks at beginning and end of context. Middle positions get lowest attention — don't put critical information there.

## Conversation history compression

Long conversations exceed context limits — compress older turns:

```python
async def compress_history(messages: list[Message], target_tokens: int) -> list[Message]:
    if count_tokens(messages) <= target_tokens:
        return messages

    # Keep system prompt + last 4 turns verbatim
    system = [m for m in messages if m.role == "system"]
    recent = messages[-8:]  # last 4 exchanges
    middle = messages[len(system):-8]

    if middle:
        summary = await llm.generate(
            f"Summarize this conversation history concisely:\n{format(middle)}"
        )
        compressed = system + [Message(role="system", content=f"Prior context: {summary}")] + recent
    else:
        compressed = system + recent

    return compressed
```

Summarize middle turns; keep recent turns verbatim. Quality degrades with aggressive compression — test on eval set before deploying.

## Token budget allocation

Allocate context window explicitly across components:

```python
TOKEN_BUDGET = {
    "system_prompt": 500,
    "retrieval_context": 3000,
    "conversation_history": 2000,
    "tool_results": 1000,
    "output_reserved": 1000,
    "headroom": 500,
}
# Total: 8000 tokens for 8k context model

def allocate_context(model_limit: int) -> dict:
    scale = model_limit / sum(TOKEN_BUDGET.values())
    return {k: int(v * scale) for k, v in TOKEN_BUDGET.items()}
```

Scale budget proportionally for larger models. Never let one component consume unbounded context.

## Failure modes

- **Critical info in middle of context** — lost-in-the-middle; poor retrieval quality
- **No token counting before send** — context overflow truncation without warning
- **Full history sent every turn** — cost scales quadratically with conversation length
- **Bigger model instead of compression** — 128k model for 20k token conversation wastes budget
- **No truncation event logging** — silent quality degradation when context exceeded

## Production checklist

- Token budget allocated per component (system, retrieval, history, output)
- Most relevant retrieval chunks placed at start and end of context
- Conversation history compressed after 8+ turns
- Token count verified before every API call with 5% headroom
- Truncation events logged and monitored
- Quality evaluated at target context size — not just maximum window

## Resources

- [Lost in the Middle paper (Liu et al.)](https://arxiv.org/abs/2307.03172)
- [Anthropic long context tips](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips)
- [OpenAI tokenizer tools](https://platform.openai.com/tokenizer)
- [LangChain context compression modules](https://python.langchain.com/docs/how_to/extraction_long_text/)
- [LlamaIndex node postprocessors for trimming](https://docs.llamaindex.ai/en/stable/module_guides/querying/node_postprocessors/)
