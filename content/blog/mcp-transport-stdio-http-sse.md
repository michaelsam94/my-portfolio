---
title: "MCP Transports: stdio, HTTP, and SSE"
slug: "mcp-transport-stdio-http-sse"
description: "Choose the right MCP transport for your deployment: stdio for local tools, HTTP and SSE for remote servers, and Streamable HTTP for the latest spec."
datePublished: "2025-05-16"
dateModified: "2025-05-16"
tags: ["AI", "MCP", "Protocol", "Infrastructure"]
keywords: "MCP transport stdio, MCP HTTP SSE, Model Context Protocol transport, MCP Streamable HTTP, MCP remote server connection, MCP wire protocol"
faq:
  - q: "When should I use stdio vs HTTP for MCP?"
    a: "Use stdio when the MCP server runs on the same machine as the client — IDE integrations, local CLI tools, development workflows. Use HTTP/SSE or Streamable HTTP when the server runs remotely, multiple clients need access, or the server requires centralized credentials."
  - q: "What is the difference between SSE and Streamable HTTP transports?"
    a: "SSE transport uses Server-Sent Events for server-to-client messages and separate HTTP POST endpoints for client-to-server messages — two connection types. Streamable HTTP (the newer spec) uses a single HTTP endpoint for both directions with optional SSE upgrade, simplifying deployment and load balancer configuration."
  - q: "Can one MCP server support multiple transports simultaneously?"
    a: "Yes. Most SDK implementations let you expose the same server logic over stdio and HTTP. Run stdio for local development and HTTP for staging/production. The server code (tools, resources, prompts) is transport-agnostic — only the connection layer changes."
---

The MCP specification defines how clients and servers exchange messages. That "how" — the transport layer — determines whether your server runs as a local subprocess on your laptop or as a remote service behind a load balancer. Pick the wrong transport and you either over-engineer a local tool with HTTP infrastructure or under-engineer a shared service with stdio pipes that cannot cross network boundaries.

MCP supports three transport mechanisms: stdio for local communication, HTTP with SSE for remote connections, and Streamable HTTP as the evolving unified transport in the latest spec revision.

## The MCP wire protocol

All transports carry the same JSON-RPC 2.0 messages:

```json
{"jsonrpc": "2.0", "method": "tools/list", "id": 1}
{"jsonrpc": "2.0", "id": 1, "result": {"tools": [...]}}
```

The transport layer handles serialization, framing, and delivery. The application layer (tools, resources, prompts) is identical regardless of transport.

## Stdio transport

The simplest transport. The client spawns the server as a subprocess and communicates via stdin/stdout:

```
Client                    Server (subprocess)
  │── stdin  ──────────→  │  (reads JSON-RPC messages)
  │←─ stdout ───────────  │  (writes JSON-RPC responses)
  │── stderr ──────────→  │  (logs only, not protocol)
```

Configuration in Cursor or Claude Desktop:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/user/projects"],
      "env": {
        "LOG_LEVEL": "debug"
      }
    }
  }
}
```

**Pros:**
- Zero network configuration
- No authentication needed (same machine, same user)
- Lowest latency
- Simplest debugging (run the command manually)

**Cons:**
- One client per server process
- Cannot share across machines
- Server lifecycle tied to client (crashes when client disconnects)
- No load balancing or health checks

**Use for:** IDE integrations, local development tools, CLI assistants, single-user workflows.

## HTTP with SSE transport

For remote servers, MCP uses HTTP with Server-Sent Events:

```
Client                          Server
  │── GET /sse ──────────────→  │  (opens SSE stream)
  │←─ SSE: endpoint event ────  │  (returns message POST URL)
  │── POST /messages ────────→  │  (client → server messages)
  │←─ SSE: message event ─────  │  (server → client responses)
```

Server implementation:

```typescript
import express from "express";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";

const app = express();
const transports = new Map<string, SSEServerTransport>();

app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  transports.set(transport.sessionId, transport);
  await server.connect(transport);

  req.on("close", () => transports.delete(transport.sessionId));
});

app.post("/messages", express.json(), async (req, res) => {
  const sessionId = req.query.sessionId as string;
  const transport = transports.get(sessionId);
  if (!transport) return res.status(404).json({ error: "Session not found" });
  await transport.handlePostMessage(req, res);
});
```

**Pros:**
- Remote access over network
- Multiple clients can connect
- Standard HTTP infrastructure (load balancers, TLS, auth)
- Independent server lifecycle

**Cons:**
- Two connection types (SSE + POST) complicate load balancing
- SSE connections are long-lived — need idle timeout tuning
- Session state required to route POST messages to correct SSE stream
- Authentication required

**Use for:** shared team servers, cloud-hosted tools, CI/CD integrations, services behind authentication.

## Streamable HTTP transport

The MCP spec revision (2025-03-26) introduces Streamable HTTP as the preferred remote transport:

```
Client                          Server
  │── POST /mcp ─────────────→  │  (request + optional SSE upgrade)
  │←─ SSE stream or JSON ─────  │  (streaming or single response)
```

Single endpoint handles both directions:

```typescript
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";

app.post("/mcp", express.json(), async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => crypto.randomUUID(),
  });
  await server.connect(transport);
  await transport.handleRequest(req, res);
});
```

**Pros:**
- Single endpoint — simpler load balancer and firewall rules
- Stateless option (no session tracking for simple request-response)
- Optional SSE upgrade for streaming responses
- Better compatibility with HTTP/2 and HTTP/3

**Cons:**
- Newer — not all clients support it yet
- Migration needed from SSE transport

**Use for:** new remote deployments, replacing SSE transport, serverless-compatible designs.

## Choosing a transport

| Scenario | Transport | Why |
|----------|-----------|-----|
| Cursor IDE local tool | stdio | Same machine, no auth, simplest |
| Team-shared database MCP | HTTP/SSE or Streamable HTTP | Remote, multi-client, auth |
| CI pipeline tool | stdio or HTTP | Depends on where server runs |
| Serverless function | Streamable HTTP | Stateless, single endpoint |
| Development + production | stdio (dev) + HTTP (prod) | Same server code, different transport |

## Load balancer considerations

SSE and Streamable HTTP with streaming require special load balancer config:

```nginx
location /sse {
    proxy_pass http://mcp_backend;
    proxy_http_version 1.1;
    proxy_set_header Connection '';
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 600s;
    chunked_transfer_encoding off;
}
```

Key settings:
- **Disable buffering** — SSE events must flow immediately.
- **Long read timeout** — connections stay open for minutes.
- **Session affinity** — POST messages must reach the same server instance as the SSE connection (for SSE transport).

Streamable HTTP with stateless mode avoids session affinity requirements.

## Client connection examples

**Stdio (automatic in IDE config):**
```json
{ "command": "node", "args": ["server.js"] }
```

**Remote SSE:**
```json
{ "url": "https://mcp.example.com/sse", "headers": { "Authorization": "Bearer token" } }
```

**Remote Streamable HTTP:**
```json
{ "url": "https://mcp.example.com/mcp", "transport": "streamable-http" }
```

## Common production mistakes

Teams get transport stdio http sse wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of transport stdio http sse fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When transport stdio http sse misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MCP transport specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/)
- [MCP Streamable HTTP transport spec](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/#streamable-http)
- [MCP TypeScript SDK transport implementations](https://github.com/modelcontextprotocol/typescript-sdk)
- [Server-Sent Events (WHATWG spec)](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [MCP server deployment guide](https://modelcontextprotocol.io/docs/concepts/transports)
