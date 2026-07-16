---
title: "Building an MCP Server: A Practical Guide for Engineers"
seoTitle: "Building an MCP Server: A Practical Engineer's Guide"
slug: "building-an-mcp-server-practical-guide"
description: "A hands-on guide to building an MCP server: tools, resources, transports, and the failure modes nobody warns you about — with TypeScript and Python examples."
datePublished: "2026-01-06"
dateModified: "2026-01-06"
tags: ["MCP", "AI Agents", "TypeScript", "Python"]
keywords: "Model Context Protocol, MCP server, MCP tools, LLM tool calling, agent tools, MCP TypeScript, MCP Python"
faq:
  - q: "What is the Model Context Protocol (MCP)?"
    a: "MCP is an open protocol that standardizes how LLM applications connect to external tools, data, and prompts. An MCP server exposes capabilities — tools, resources, and prompts — and any MCP-compatible client (like Claude Desktop or an IDE agent) can call them over a defined transport."
  - q: "What's the difference between an MCP tool and a resource?"
    a: "A tool is a callable function the model can invoke to perform an action or computation, with typed inputs and outputs. A resource is read-only data the client can fetch and put into context, addressed by a URI. Tools do things; resources supply information."
  - q: "Should I use stdio or HTTP transport for my MCP server?"
    a: "Use stdio when the server runs locally alongside the client, such as a desktop app spawning a subprocess — it's simplest and needs no networking. Use streamable HTTP when the server is remote, shared across users, or needs independent scaling and auth."
---

An MCP server is the cleanest way to give a language model access to your systems without hard-coding an integration into every client. You write the server once — exposing tools, resources, and prompts — and any MCP-compatible client can discover and use them. That's the whole pitch of the [Model Context Protocol](https://modelcontextprotocol.io/): stop building a bespoke tool layer per app and speak a common protocol instead.

I'll walk through what actually goes into a production-minded MCP server: the three primitives, the transports and when to pick each, a working example in both TypeScript and Python, and the failure modes that will bite you the first week. This is written for engineers who've wired up an LLM before and want the tool layer to be boring and reliable rather than clever.

## The three primitives you expose

An MCP server offers three kinds of capability, and it helps to be precise about which is which:

- **Tools** — callable functions with typed inputs. The model decides when to call them. This is where actions live: `create_ticket`, `run_sql`, `search_orders`.
- **Resources** — read-only data addressed by URI, e.g. `file:///logs/app.log` or `db://customers/4821`. The client pulls these into context; the model doesn't "call" them so much as read them.
- **Prompts** — reusable, parameterized message templates the user can invoke, often surfaced as slash commands in the client.

Most servers I've built are 80% tools, 15% resources, 5% prompts. The temptation is to expose everything as a tool. Resist it — if something is just data the model should read, make it a resource so it doesn't clutter the tool list the model has to reason over.

## A minimal server in TypeScript

The official [TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk) keeps the boilerplate low. Here's a server that exposes one tool with a validated schema:

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

const server = new McpServer({ name: "orders", version: "1.0.0" });

server.tool(
  "search_orders",
  "Find orders by customer email. Returns at most 20 results.",
  { email: z.string().email(), limit: z.number().int().max(20).default(10) },
  async ({ email, limit }) => {
    const rows = await db.orders.findByEmail(email, limit);
    return {
      content: [{ type: "text", text: JSON.stringify(rows, null, 2) }],
    };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
```

Two things matter here. First, the **description** is not decoration — it's the only thing the model sees when deciding whether to call the tool, so write it like an API doc, not a comment. Second, the **Zod schema** becomes the JSON Schema the client validates against, so a bad `email` never reaches your handler.

## The same idea in Python

The Python SDK's `FastMCP` is even terser and reads well:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("orders")

@mcp.tool()
def search_orders(email: str, limit: int = 10) -> str:
    """Find orders by customer email. Returns at most 20 results."""
    rows = db.find_by_email(email, min(limit, 20))
    return json.dumps(rows, indent=2)

if __name__ == "__main__":
    mcp.run()  # stdio by default
```

Type hints drive the schema, and the docstring becomes the tool description. For a first internal server, Python gets you to "the model called my function" in about ten minutes.

## Transports: stdio vs streamable HTTP

MCP defines how the client and server talk. Two transports dominate:

| Transport | When to use | Auth story |
| --- | --- | --- |
| **stdio** | Local, one server per client, spawned as a subprocess | Inherits the local process; no network auth |
| **Streamable HTTP** | Remote or shared servers, independent scaling | You own it — OAuth, bearer tokens, mTLS |

Start with stdio for anything local — a desktop client launches your server as a child process and pipes JSON-RPC over stdin/stdout. Move to streamable HTTP when the server is remote or multi-tenant. The important trap: **the moment you go HTTP, authentication and authorization are your problem.** An MCP tool that runs `run_sql` behind an unauthenticated HTTP endpoint is a database exposed to the internet. Put real auth in front of it and scope every tool to the caller's permissions.

## Failure modes that will bite you

These are the ones I've actually hit, not the theoretical ones:

1. **Vague tool descriptions.** If the model can't tell `get_user` from `get_user_profile`, it picks wrong or asks the user. Descriptions should state what the tool does, what it returns, and any limits.
2. **Returning giant blobs.** A tool that dumps 50 KB of JSON burns context and money and drowns the answer. Paginate, summarize, or return IDs the model can drill into.
3. **No timeouts on the handler.** A tool that hangs takes the whole turn with it. Wrap external calls with a timeout and return a clean error message the model can reason about.
4. **Errors as exceptions instead of content.** When a tool fails, return a structured error in the tool result so the model can recover or apologize — don't just throw and kill the connection.
5. **Over-broad tools.** A single `admin` tool that does ten things is harder for the model to use correctly than five focused tools. This mirrors the same discipline that makes [reliable AI agents](https://blog.michaelsam94.com/building-reliable-ai-agents/) work.

## Testing and shipping

Test the server independently of any model. The MCP Inspector lets you list tools, call them with sample inputs, and see raw responses — treat it like Postman for MCP. Write ordinary unit tests around the handler functions too; they're just typed functions. Before you expose anything destructive, gate it behind confirmation and think through [prompt injection and tool security](https://blog.michaelsam94.com/prompt-injection-agent-security/), because a tool the model can call is a tool an attacker's injected instructions can try to call.

Once the server behaves under the Inspector and your tests, wiring it into a client is a config entry. From there, the same server serves a desktop client, an IDE agent, and your own orchestration layer — which is the entire point of standardizing on the protocol. If you're building out a larger system, an MCP server is usually one node in a bigger [multi-agent orchestration](https://blog.michaelsam94.com/multi-agent-orchestration-orchestrator-workers/) design.

Keep the tool surface small, the descriptions honest, and the auth real, and an MCP server becomes the least exciting part of your AI stack — which is exactly what you want.

## Resources

- [Model Context Protocol — official site and spec](https://modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP specification (protocol reference)](https://spec.modelcontextprotocol.io/)
- [Anthropic — Model Context Protocol announcement](https://www.anthropic.com/news/model-context-protocol)
- [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification)
