---
title: "Routing Between Many Agent Tools"
slug: "agent-tool-selection-routing"
description: "Scale agent tool selection beyond 10 tools: routing layers, tool groups, embedding-based selection, and keeping tool catalogs manageable."
datePublished: "2026-07-05"
dateModified: "2026-07-05"
tags: ["AI Agents", "LLM", "Architecture", "Backend"]
keywords: "agent tool selection, tool routing LLM, many tools agent, tool catalog agents, function calling scale"
faq:
  - q: "How many tools can an LLM agent handle reliably?"
    a: "Most models degrade in tool selection accuracy beyond 10–15 simultaneously available tools. Beyond that, use a routing layer that pre-selects a relevant subset (5–8 tools) based on intent classification or embedding similarity, then presents only those to the model for final selection."
  - q: "What is tool routing vs tool selection?"
    a: "Tool routing is a pre-filtering step that narrows 50 tools down to 5–8 candidates based on the user's intent. Tool selection is the model's choice among those candidates. Routing is deterministic or classifier-based; selection is LLM-based. Splitting the problem improves accuracy on both."
  - q: "Should tool routing use embeddings or a classifier?"
    a: "Use a lightweight intent classifier for well-defined domains with stable tool sets — it's faster and cheaper. Use embedding similarity between the user query and tool descriptions when tools are frequently added or the domain is open-ended. Hybrid approaches work best: classifier for coarse routing, embeddings for fine selection within a group."
---

Tool selection accuracy falls off a cliff around tool fifteen. I've watched an agent with thirty tools call `delete_user` when the user asked for account settings — not because the model is careless, but because thirty tool descriptions in context creates a needle-in-a-haystack problem that gets worse with every tool you add. The fix isn't better prompting; it's a routing layer that presents the model with five relevant tools instead of fifty. Tool routing is the scaling mechanism nobody builds until their agent starts calling the wrong API.

## The two-stage pattern

```
User query → Router (50 tools → 5-8 candidates) → LLM (picks 1-2 tools) → Execute
```

Stage 1 is fast and cheap. Stage 2 is the model doing what it's good at — choosing among a small, relevant set.

## Tool groups with intent routing

Organize tools into groups and classify intent first:

```python
TOOL_GROUPS = {
    "account": ["get_profile", "update_profile", "change_password", "delete_account"],
    "billing": ["get_invoices", "create_refund", "update_payment_method"],
    "orders": ["list_orders", "get_order", "cancel_order", "track_shipment"],
    "support": ["create_ticket", "search_kb", "escalate"],
}

async def route_tools(user_message: str) -> list[str]:
    intent = await classify_intent(user_message)  # cheap model call
    primary = TOOL_GROUPS.get(intent, [])
    # Always include search as fallback
    return primary + ["search_kb"]
```

The classifier is a 50-token call to a small model: "Classify this message: account, billing, orders, or support." It costs fractions of a cent and runs in 100ms.

## Embedding-based routing for dynamic catalogs

When tools change frequently or groups aren't obvious:

```python
async def route_by_embedding(query: str, top_k: int = 8) -> list[ToolDef]:
    query_embedding = await embed(query)
    scores = [
        (tool, cosine_similarity(query_embedding, tool.embedding))
        for tool in all_tools
    ]
    return [tool for tool, score in sorted(scores, key=lambda x: -x[1])[:top_k]]
```

Pre-compute tool description embeddings offline. At runtime, embed the query and return top-K. Include tool name, description, and one example use case in the embedded text for better matching.

## Tool description quality matters more than count

Before adding routing, fix your tool descriptions. The routing layer can't compensate for:

```python
# Bad — model can't distinguish tools
{"name": "process", "description": "Process a request"}

# Good — specific, disambiguated
{"name": "create_refund", "description": "Issue a refund for a completed order. Requires order_id and amount. Use only after verifying eligibility with get_order."}
```

Add negative scope to descriptions: "Use for X, NOT for Y." This helps both the router and the model.

## Dynamic tool loading per workflow phase

Combine routing with [graph workflows](https://blog.michaelsam94.com/agent-graph-workflows-langgraph/) — different phases expose different tools:

| Phase | Available tools |
|-------|----------------|
| Intake | classify_intent, search_kb, get_profile |
| Research | search_kb, fetch_document, query_database |
| Action | create_refund, send_email, update_record |
| Review | get_audit_log, summarize |

The model never sees action tools during intake. This is routing by architecture, not by algorithm, and it's the most reliable approach.

## Sub-agents as extreme routing

When tool groups have different security boundaries, route to [sub-agents](https://blog.michaelsam94.com/agent-subagent-delegation-patterns/) instead of tool groups:

- Research sub-agent: 8 read tools
- Executor sub-agent: 5 write tools
- Orchestrator: 2 meta-tools (delegate, synthesize)

Each sub-agent's routing problem is trivial because its catalog is already narrow.

## Measuring routing quality

Track these metrics:

- **Tool selection accuracy**: did the model pick the right tool from the routed set?
- **Routing recall**: was the correct tool in the routed candidate set?
- **Routing precision**: what fraction of routed tools were actually used?

Low recall means your router is too aggressive — widen top-K or fix group boundaries. Low selection accuracy with high recall means descriptions or prompts need work, not routing.

Log routing decisions in your [agent traces](https://blog.michaelsam94.com/agent-observability-tracing-spans/) for debugging misfires.

## Embedding-based tool retrieval

When tool catalogs exceed 20–30 entries, flat routing groups aren't enough. Embed tool descriptions and retrieve top-K by query similarity:

```python
async def route_tools(query: str, k: int = 5) -> list[Tool]:
    query_vec = embed(query)
    candidates = vector_index.search(query_vec, top_k=k * 2)
    return [t for t in candidates if t.risk_tier <= session.max_risk_tier][:k]
```

Combine embedding retrieval with hard filters:

- **Permission filter** — user role excludes `delete_account`
- **Environment filter** — staging tools hidden in production
- **State filter** — `create_refund` only if order exists in session context

Embedding recall without filters causes dangerous tool exposure — a "delete" tool retrieved because the user said "remove from my cart."

## Fallback and escalation paths

Routing should degrade gracefully:

| Situation | Behavior |
|-----------|----------|
| No tool above confidence threshold | Ask clarifying question |
| Single low-confidence match | Confirm before executing write tools |
| Router timeout | Fall back to safe read-only tool set |
| Tool execution failure | Re-route with error context, max 2 retries |

Never loop indefinitely re-routing the same failed tool. Escalate to human after N failures on write operations.

## Production checklist

- [ ] Tool descriptions include parameters, returns, and negative scope
- [ ] Router logs: query hash, candidates, selected tools, latency
- [ ] Weekly review of unused tools — remove from catalog to reduce noise
- [ ] Integration tests per workflow phase with expected tool sets
- [ ] Write tools require explicit user confirmation or HITL approval

Pair with [tool use error recovery](https://blog.michaelsam94.com/agent-tool-use-error-recovery/) when routed tools fail mid-execution.

## Production checklist

- [ ] Tool descriptions include negative scope ("NOT for...")
- [ ] Router logs query hash, candidates, and selection latency
- [ ] Write tools gated by workflow phase, not just routing
- [ ] Weekly review of unused tools in catalog
- [ ] Embedding retrieval filtered by permission before similarity rank

Most production routing incidents trace to stale tool descriptions, not embedding model quality — schedule a monthly catalog review with the teams that own each tool.

## Embedding router drift

Tool routers trained on historical invocation logs bias toward overused tools. Weekly eval: holdout queries where correct tool is rare — if recall drops, retrain or add keyword fallback for safety-critical tools (billing, delete). Log router confidence; route below 0.6 to clarifying question instead of wrong tool.

## Latency-aware routing

Fast cheap tools vs slow accurate tools: router should accept `max_latency_ms` from orchestrator policy during incidents. Degrade to cached retrieval tool when vector DB p99 exceeds SLO instead of timing out user chat.

## Production validation for Tool Selection Routing Supplement 0

Ship behind a flag when touching Tool Selection Routing Supplement 0; measure error rate and latency against baseline for seven days. Document rollback steps and owner on-call before enabling for enterprise tenants.

## Incident signals to watch

Alert on spikes in 5xx, client ANR rate, or support tag volume referencing Tool Selection Routing Supplement 0. Correlate with server deploys and Remote Config changes within ±2 hours before deep debugging client-only hypotheses.

## Production validation for Tool Selection Routing Supplement 1

Ship behind a flag when touching Tool Selection Routing Supplement 1; measure error rate and latency against baseline for seven days. Document rollback steps and owner on-call before enabling for enterprise tenants.

## Incident signals to watch

Alert on spikes in 5xx, client ANR rate, or support tag volume referencing Tool Selection Routing Supplement 1. Correlate with server deploys and Remote Config changes within ±2 hours before deep debugging client-only hypotheses.

## Resources

- [OpenAI function calling best practices](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic tool use guide](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [LangChain tool retrieval](https://python.langchain.com/docs/how_to/tools_as_retrieval/)
- [Berkeley Function Calling Leaderboard](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html)
- [Parallel tool execution patterns](https://blog.michaelsam94.com/agent-parallel-tool-execution/)
