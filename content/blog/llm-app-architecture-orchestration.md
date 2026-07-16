---
title: "Architecting an LLM Application"
slug: "llm-app-architecture-orchestration"
description: "Production LLM app architecture: request flow, model gateway, retrieval, tool execution, observability, and the layers that keep prompts from becoming your entire backend."
datePublished: "2024-10-07"
dateModified: "2024-10-07"
tags: ["AI", "LLM", "Architecture", "Backend"]
keywords: "LLM application architecture, LLM orchestration, RAG architecture, model gateway, production LLM design"
faq:
  - q: "What belongs in the LLM layer vs traditional backend code?"
    a: "LLMs handle language understanding, generation, and fuzzy matching. Everything deterministic — auth, billing, database writes, validation — stays in regular code. The LLM layer orchestrates and synthesizes; it should never be the sole gatekeeper for security or money."
  - q: "Do I need a separate model gateway?"
    a: "Once you have more than one model provider or environment, yes. A gateway centralizes API keys, rate limiting, retries, logging, and cost attribution. Without it, every service reinvents the same wrapper and you can't swap models without redeploying app code."
  - q: "How do I structure a RAG pipeline in production?"
    a: "Split it into discrete services: ingestion (chunk, embed, index), retrieval (query rewrite, hybrid search, rerank), and generation (context assembly, prompt, stream). Each stage gets its own metrics. Monolithic 'RAG functions' become impossible to debug when retrieval quality drops."
---

Most LLM apps start as a Flask route with a prompt string. That works for a demo. In production, the same route needs auth, rate limits, retrieval, tool execution, streaming, fallback models, cost tracking, and content filtering — and if all of that lives in one 800-line handler, every prompt tweak becomes a deploy.

The architecture that survives contact with real users separates concerns the same way a normal backend would. The LLM is a component, not the architecture.

## Reference request flow

A typical production path:

```
Client → API Gateway → Auth → Orchestrator → [Retrieval | Tools | LLM] → Post-process → Stream
                                    ↓
                              Observability (traces, costs, logs)
```

Each box is a boundary you can test independently.

**API Gateway**: TLS, WAF, request size limits.

**Auth**: JWT validation, tenant extraction. Happens before any LLM call — never trust the model to enforce access control.

**Orchestrator**: the brain of your app. Loads conversation state, decides whether to retrieve, which tools to call, which model tier to use. This is code, not a prompt.

**Post-process**: output filtering, citation formatting, PII redaction, schema validation on structured responses.

## The model gateway pattern

Don't call OpenAI/Anthropic directly from every microservice. Put a gateway in front:

```python
# gateway/client.py — every service uses this
async def complete(
    messages: list[dict],
    *,
    model: str | None = None,      # None → router picks
    tenant_id: str,
    feature: str,                   # "support_chat", "summarize"
) -> CompletionResult:
    model = model or router.select(feature, messages)
    async with rate_limiter.acquire(tenant_id):
        return await provider.complete(
            model=model,
            messages=messages,
            metadata={"tenant_id": tenant_id, "feature": feature},
        )
```

The gateway owns:

- Provider API keys (rotated centrally)
- Retry with exponential backoff
- Token counting and cost attribution
- Request/response logging with PII scrubbing
- Circuit breakers when a provider degrades

When GPT-5 launches or you need to route EU tenants to a local model, you change the gateway — not twelve services.

## Retrieval as a separate stage

RAG isn't "add vectors to the prompt." Treat retrieval as its own pipeline:

1. **Query understanding** — rewrite vague user input, extract filters
2. **Hybrid search** — BM25 + dense vectors, merged with RRF
3. **Reranking** — cross-encoder or lightweight LLM reranker on top-50
4. **Context packing** — fit chunks into token budget, deduplicate, order by relevance

```python
async def retrieve(query: str, tenant_id: str, budget_tokens: int) -> list[Chunk]:
    rewritten = await query_rewriter.rewrite(query, tenant_id)
    candidates = await hybrid_search(rewritten, tenant_id, k=50)
    ranked = await reranker.rank(query, candidates, top_k=10)
    return pack_context(ranked, max_tokens=budget_tokens)
```

Instrument recall@k and nDCG per tenant. When users say "the bot doesn't know about our new pricing," you'll know whether ingestion lagged or retrieval failed.

## Tool execution sandbox

Agents that call external APIs need isolation:

- **Allowlisted tools** per feature — support chat can't call `delete_user`
- **Timeout per tool** — 10 seconds default, configurable
- **Idempotency keys** on mutating operations
- **Human approval** for irreversible actions (refunds, deploys)

Run tool handlers in the same process for low-latency reads; use sandboxed workers (containers, WASM) for code execution.

## State and conversation memory

Store conversations outside the LLM context:

```python
@dataclass
class ConversationStore:
    async def append(self, session_id: str, turn: Turn) -> None: ...
    async def get_context(self, session_id: str, max_tokens: int) -> list[Message]:
        # Recent turns verbatim + summarized older history
        ...
```

The orchestrator assembles context from the store, retrieval, and system prompt — the model never owns state.

## Observability from day one

Every LLM call should emit a trace span with:

- `gen_ai.request.model`, token counts, latency
- Retrieval hit count, chunk IDs used
- Tool calls with arguments (redacted) and results
- Estimated cost in USD

Dashboards: p95 latency by feature, cost per tenant per day, error rate by provider, retrieval empty-rate.

Without traces, "it's slower this week" becomes a multi-day archaeology project.

## Deployment topology

Common patterns:

| Scale | Topology |
|-------|----------|
| MVP | Monolith + managed vector DB + gateway library |
| Growth | Orchestrator service + async ingestion workers + Redis session store |
| Enterprise | Per-tenant isolation, dedicated indexes, regional model routing |

Start monolith. Extract services when a stage has different scaling characteristics — ingestion is batch-heavy; chat is latency-sensitive.

## Orchestrator responsibilities

- Route intent to specialist handlers
- Maintain session state and memory budget
- Enforce tool policies and budgets
- Aggregate sub-agent outputs

Keep orchestrator model smaller/cheaper — delegate heavy reasoning to worker model only when needed.

## Common production mistakes

Teams get app architecture orchestration wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

LLM features around app architecture orchestration break in production when prompts assume deterministic output, context windows are sized for dev datasets, or token costs are never budgeted per user session. Always log prompt hash, model version, and latency—not raw prompts with PII.

## Debugging and triage workflow

When app architecture orchestration misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Martin Fowler — LLM application patterns](https://martinfowler.com/articles/engineering-practices-for-LLM-applications.html)
- [OpenAI production best practices](https://platform.openai.com/docs/guides/production-best-practices)
- [LangChain architecture concepts](https://python.langchain.com/docs/concepts/architecture/)
- [OpenTelemetry GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/)
- [Pinecone RAG production guide](https://docs.pinecone.io/guides/get-started/overview)
