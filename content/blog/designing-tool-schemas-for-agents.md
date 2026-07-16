---
title: "Designing Tool Schemas Agents Can Actually Use"
slug: "designing-tool-schemas-for-agents"
description: "Practical tool schema design for agents: naming, descriptions, parameters, and error contracts that make function calling reliable, not a guessing game."
datePublished: "2026-05-29"
dateModified: "2026-05-29"
tags: ["AI Agents", "LLM", "API Design"]
keywords: "tool schema design, function calling schema, agent tools, JSON schema tools, tool descriptions, LLM tool use"
faq:
  - q: "What is tool schema design for agents?"
    a: "Tool schema design is the practice of specifying the name, description, parameters, and output contract of the functions an LLM agent can call, so the model reliably picks the right tool and fills the arguments correctly. The schema is usually JSON Schema attached to each function, and it doubles as documentation the model reads at inference time. Good schema design is the difference between an agent that calls tools accurately and one that hallucinates arguments."
  - q: "How detailed should a tool description be?"
    a: "Detailed enough that the model can decide when to use the tool and what each argument means, but not so verbose that it wastes context. Aim for a one-line summary of what the tool does and what it returns, plus a short note on limits or preconditions. Treat it like public API documentation, because to the model it is the only documentation."
  - q: "Should I expose many small tools or a few big ones?"
    a: "Prefer several focused tools over one overloaded tool with a mode flag. Focused tools have clearer schemas, are easier for the model to select correctly, and fail in more diagnosable ways. The exception is when tools are so numerous they crowd the context window, at which point grouping or dynamic tool selection becomes worth the complexity."
---

The schema is the API the model programs against, and like any API, a sloppy one produces sloppy callers. Tool schema design is the work of writing the names, descriptions, parameter types, and error contracts for the functions your agent can invoke so that function calling becomes predictable rather than a dice roll. Get it right and the model reaches for the correct tool with correct arguments on the first try; get it wrong and you'll spend weeks blaming the model for what is really a documentation problem.

I've shipped agents where swapping a vague description for a precise one cut tool-selection errors by more than half without touching the model. The schema is that leveraged. Here's how I approach it.

## The model reads the schema, so write it for a reader

A function-calling schema has parts the model actually consumes: the tool `name`, the top-level `description`, and per-parameter descriptions inside a JSON Schema. All of it is prompt. The model has never seen your code — this text is the entire interface.

```json
{
  "name": "search_orders",
  "description": "Find a customer's orders by email. Returns up to 20 orders, newest first. Use when the user asks about order status, history, or a specific purchase.",
  "parameters": {
    "type": "object",
    "properties": {
      "email": {
        "type": "string",
        "format": "email",
        "description": "Customer email to search. Must be a full address, not a name."
      },
      "limit": {
        "type": "integer",
        "minimum": 1,
        "maximum": 20,
        "default": 10,
        "description": "Max orders to return."
      }
    },
    "required": ["email"]
  }
}
```

Notice the description says what it does, what it returns, *and when to use it*. That last clause is what disambiguates `search_orders` from a neighboring `get_order_details`. The parameter description tells the model an email is required, not a name — which preempts the single most common failure, the model shoving `"John Smith"` into an email field.

## Naming is disambiguation

Names carry more signal than people credit. `get_user` and `get_user_profile` sitting next to each other is a trap: the model can't tell which returns what, so it picks by coin flip. Name tools by the *distinct outcome* they produce — `get_user_contact_info` vs `get_user_order_history` — so the name alone narrows the choice. Use consistent verbs: `search_` for queries returning lists, `get_` for a single record by id, `create_`/`update_`/`delete_` for mutations. Consistency lets the model generalize from one tool to the next. This is the same schema discipline that makes an [MCP server practical to build](https://blog.michaelsam94.com/building-an-mcp-server-practical-guide/) — MCP just standardizes the packaging around exactly these definitions.

## Constrain parameters instead of hoping

Every degree of freedom you leave open is a place the model can guess wrong. Close them in the schema:

- Use `enum` for anything categorical. `status: "open" | "closed" | "pending"` is unmissable; `status: string` invites `"in progress"`, `"Open"`, and `"still waiting"`.
- Set `minimum`/`maximum` on numbers and `maxLength` on strings so the model can't request 10,000 rows.
- Prefer flat objects. Deeply nested parameters raise the rate of malformed arguments; if you need nesting, keep it one level and describe each field.
- Avoid free-form "options" bags. A `params: object` with no defined properties is where reliability goes to die.

When output structure matters as much as input, the same principles carry over to how you shape responses — I go deeper on that in [structured outputs and function calling](https://blog.michaelsam94.com/structured-outputs-function-calling/).

## Design the error contract on purpose

Tools fail: bad input, empty results, downstream timeouts. How you report failure decides whether the agent recovers or spirals. The rule I hold to: **errors are data, not exceptions.** Return a structured result the model can read and act on, rather than throwing and killing the turn.

```python
def search_orders(email: str, limit: int = 10) -> dict:
    if not is_valid_email(email):
        return {"ok": False, "error": "invalid_email",
                "message": "Provide a full email address, e.g. name@host.com."}
    rows = db.find(email, min(limit, 20))
    if not rows:
        return {"ok": False, "error": "no_results",
                "message": f"No orders for {email}. Confirm the address with the user."}
    return {"ok": True, "orders": rows}
```

An empty result is not an error — it's a distinct outcome, and the message tells the model what to do next (confirm the address). Vague failures like `{"error": "something went wrong"}` give the model nothing to reason with, so it retries blindly or fabricates an answer. A good error message is a nudge back onto the happy path.

## Keep the toolset small and the payloads lean

Two forces degrade agents at scale: too many tools and too much output.

Every tool you add is more text in context and one more option the model weighs on every step. Past roughly a dozen tools, selection accuracy starts sliding. Group related capabilities, retire unused ones, and if you truly need dozens, look at retrieving a relevant subset per request instead of dumping all of them. On the output side, a tool that returns 40 KB of JSON burns budget and buries the signal. Paginate, project down to the fields the task needs, or return ids the model can drill into with a follow-up call. This restraint is part of the broader craft of [building reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/) — a lean, well-described tool surface is one of the highest-return investments there.

## A checklist before you ship a tool

Before a tool goes live, I run it past this:

1. Does the name describe a distinct outcome, with a consistent verb?
2. Does the description say what it does, what it returns, and when to use it?
3. Is every parameter typed, constrained (`enum`/min/max), and described?
4. Are failures and empty results returned as structured, actionable data?
5. Is the response projected down to what the task needs?

None of this is glamorous, and that's the point. The most reliable agents I've built run on boring, well-documented, tightly-constrained tools. The cleverness belongs in the orchestration; the tool layer should be so clearly specified that the model has nothing left to guess.

## Resources

- [JSON Schema — official specification](https://json-schema.org/)
- [OpenAI — function calling guide](https://platform.openai.com/docs/guides/function-calling)
- [Anthropic — tool use documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Model Context Protocol — specification](https://spec.modelcontextprotocol.io/)
- [Google — Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling)
