---
title: "Token Budget Compression for Long Agent Contexts"
slug: "agent-token-budget-compression"
description: "Fit more agent memory into fixed context windows: summarization compressors, structured state extraction, tool result pruning, and lossy vs lossless strategies with eval gates."
datePublished: "2025-04-07"
dateModified: "2026-07-17"
tags: ["AI Agents", "LLM", "Context", "Optimization"]
keywords: "token budget compression agent, context window pruning, agent memory summarization, tool result compression"
faq:
  - q: "When should compression run — every turn or only near the limit?"
    a: "Run a cheap token estimate every turn; trigger compression when usage crosses 70–80% of the model window minus reserved output tokens. Compressing too early loses detail; compressing at 99% risks mid-request truncation on tool results."
  - q: "Is summarization lossy compression acceptable for agent state?"
    a: "For narrative chat history, yes — with structured sidecar state for IDs, amounts, and decisions. Never summarize away tool call arguments, API response IDs, or user-confirmed values; extract those into a JSON state block first."
  - q: "How do you evaluate compression quality?"
    a: "Run golden agent trajectories with and without compression; compare task success rate, tool selection accuracy, and hallucination rate on held-out multi-turn scenarios. Block deploys if success drops more than your agreed threshold (typically 1–3%)."
  - q: "Should tool results be truncated or summarized?"
    a: "Truncate structured payloads first (drop large arrays, keep schema skeleton). Summarize prose results. For JSON APIs, prefer jq-style field selection over LLM summarization — it is deterministic and auditable."
---

A 128k context window sounds infinite until your agent ingests a 40-page PDF, twelve tool calls return full JSON payloads, and the planner still needs room for reasoning tokens. **Token budget compression** is how production agents stay coherent without silently dropping the invoice ID from turn three. The goal is not minimum tokens — it is maximum task success per dollar under a hard ceiling.

## Anatomy of agent context bloat

Typical long-running agent sessions accumulate weight unevenly:

| Segment | Share of tokens (typical) | Compressibility |
|---------|---------------------------|-----------------|
| System prompt + tool schemas | 15–25% | Low (cache instead) |
| User/assistant dialogue | 20–35% | Medium (summarize older turns) |
| Tool results (JSON/HTML) | 30–50% | High (prune fields) |
| Retrieved RAG chunks | 10–20% | Medium (re-rank, dedupe) |
| Working scratchpad | 5–15% | Low until task completes |

Measure with your tokenizer (tiktoken, model-native counter) — character heuristics lie by 20%+ on code and CJK text.

## Layered compression pipeline

Apply stages in order from cheapest to most destructive:

```
Turn N incoming
    │
    ▼
[1] Structured state extraction ──► sidecar JSON (lossless for facts)
    │
    ▼
[2] Tool result pruning ──► field allowlists, array caps
    │
    ▼
[3] RAG deduplication ──► merge overlapping chunks
    │
    ▼
[4] Dialogue summarization ──► rolling summary of turns 1..k
    │
    ▼
[5] Emergency truncation ──► drop middle turns (last resort)
```

Stage 5 should fire rarely and emit telemetry — if it triggers often, your tool schemas or RAG chunk size is wrong upstream.

## Structured state extraction before summarization

Before summarizing "the user asked about order 8842," extract machine-readable facts:

```python
from pydantic import BaseModel
from typing import Optional

class SessionFacts(BaseModel):
    order_ids: list[str] = []
    confirmed_amounts: dict[str, str] = {}
    pending_tool_calls: list[str] = []
    user_constraints: list[str] = []

def extract_facts(messages: list[dict]) -> SessionFacts:
    # Rule-based + small model pass on last K turns
    ...
```

Inject `SessionFacts` as a compact JSON prefix on every request. Summaries can drift; facts should not.

## Tool result pruning

A CRM search returning 200 contacts is a token bomb. Define per-tool response profiles:

```yaml
# tools/crm_search.response_profile.yaml
max_tokens: 2000
field_allowlist:
  - id
  - name
  - email
  - account.status
array_limits:
  contacts: 10
truncate_strategy: head  # or relevance_score if sorted
```

Implement in the tool gateway, not the LLM:

```python
def prune_tool_result(tool_name: str, raw: dict) -> dict:
    profile = load_profile(tool_name)
    pruned = select_fields(raw, profile.field_allowlist)
    pruned = cap_arrays(pruned, profile.array_limits)
    return pruned
```

Log `original_tokens`, `pruned_tokens`, `tool_name` for cost attribution.

## Rolling dialogue summarization

When dialogue history exceeds `SUMMARY_THRESHOLD` tokens, compress turns `[1..m]` into a summary block and keep `[m+1..now]` verbatim:

```python
COMPRESS_PROMPT = """Summarize the agent conversation below for continuation.
Preserve: decisions made, user preferences, error recovery steps, unresolved tasks.
Omit: pleasantries, repeated tool errors already fixed.
Format: bullet points, max 400 words.

Conversation:
{turns}
"""

async def maybe_compress(session: Session) -> Session:
    if session.token_count() < session.budget * 0.75:
        return session
    old_turns = session.turns[:-6]  # keep last 6 turns raw
    summary = await llm.complete(COMPRESS_PROMPT.format(turns=old_turns))
    session.replace_prefix(summary, keep_turns=session.turns[-6:])
    return session
```

Use a smaller/cheaper model for compression than for the main agent — quality requirements are lower.

## Prompt caching vs compression

Models with prompt caching (Anthropic, OpenAI prefix caching) reward stable prefixes. Structure context so static content comes first:

1. System prompt + tool definitions (cached)
2. Session facts JSON (semi-stable)
3. Rolling summary (changes slowly)
4. Recent turns + new user message (mutable tail)

Compression of the tail preserves cache hits on the prefix — re-summarizing the entire history every turn destroys cache economics.

## Eval gates before shipping compression

Maintain a **compression regression suite**:

| Metric | Baseline | With compression | Gate |
|--------|----------|------------------|------|
| Multi-turn task success | 94% | ? | ≥ 92% |
| Tool arg accuracy | 98% | ? | ≥ 97% |
| Fact hallucination (held-out IDs) | 0.5% | ? | ≤ 1% |
| p95 latency | 2.1s | ? | ≤ 2.5s |

Run on CI for every change to thresholds, summary prompts, or prune profiles.

## Lossy vs lossless decision tree

- **Lossless:** session facts, confirmed user inputs, active tool call IDs, legal/compliance utterances.
- **Lossy OK:** exploratory search results already acted upon, failed retry attempts superseded by success, verbose API docs retrieved once.
- **Never lossy:** financial amounts after user confirmation, medical dosages, security credentials (should never be in context — reject upstream).

## Operational observability

Dashboard panels:

- `context_tokens_by_segment` (stacked area)
- `compression_events_total` by stage
- `compression_trigger_ratio` = compressions / turns
- Cost saved estimate = (tokens_before - tokens_after) × price_per_token

Alert if emergency truncation exceeds 5% of sessions — users are losing coherence.

## Resources

- [Anthropic — Prompt caching documentation](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
- [OpenAI — tiktoken tokenizer](https://github.com/openai/tiktoken)
- [LangChain — Conversation summary memory](https://python.langchain.com/docs/modules/memory/types/summary/)
- [Lost in the Middle — LLM context position bias paper](https://arxiv.org/abs/2307.03172)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

