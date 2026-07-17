---
title: "Testing MCP Servers with the Inspector"
slug: "mcp-server-testing-inspector"
description: "Debug and test MCP servers with the MCP Inspector: tool invocation, resource fetching, prompt testing, and protocol compliance verification."
datePublished: "2025-05-12"
dateModified: "2026-07-17"
tags:
keywords: "MCP Inspector, MCP server testing, Model Context Protocol debug, MCP tool testing, MCP Inspector CLI, MCP protocol testing"
faq:
  - q: "What is the MCP Inspector?"
    a: "The MCP Inspector is an official browser-based debugging tool for MCP servers. It connects to a server via stdio or HTTP/SSE and provides a UI to list tools, invoke them with custom arguments, fetch resources, test prompts, and inspect the raw JSON-RPC messages exchanged between client and server."
  - q: "Can I use the MCP Inspector in CI/CD pipelines?"
    a: "The Inspector itself is a GUI tool, but you can test MCP servers programmatically using the MCP SDK client in test scripts. Connect to the server, call list_tools, invoke each tool with test inputs, and assert on responses. The Inspector is for development debugging; automated tests use the SDK."
  - q: "How do I test an MCP server that requires authentication?"
    a: "For stdio servers, pass credentials via environment variables in the Inspector's server config. For remote HTTP servers, configure the Authorization header in the Inspector's connection settings. The Inspector supports Bearer token auth for testing OAuth-protected servers."
---
You built an MCP server with twelve tools, eight resources, and three prompts. It connects in Cursor without errors. But when the model calls `search_tickets`, it returns empty results. When it calls `create_ticket`, the required fields error message is confusing. You need to test each tool in isolation, inspect the raw protocol messages, and verify your schemas before the model ever sees them.

The MCP Inspector is the official debugging tool for this. It connects to your server, exposes every capability in a testable UI, and shows the JSON-RPC wire protocol so you can see exactly what the client and server exchange.

## Starting the Inspector

Install and launch against your server:

```bash
npx @modelcontextprotocol/inspector node dist/server.js
```

For a server with environment variables:

```bash
npx @modelcontextprotocol/inspector \
  -e DATABASE_URL=postgresql://localhost/test \
  -e API_KEY=test-key \
  node dist/server.js
```

For a remote HTTP/SSE server:

```bash
npx @modelcontextprotocol/inspector \
  --url http://localhost:8080/sse \
  --header "Authorization: Bearer test-token"
```

The Inspector opens a browser UI at `http://localhost:6274` (default port).

## Testing tools

The Tools tab lists every registered tool with its input schema:

1. Select a tool from the list.
2. Fill in argument fields (the UI renders the JSON Schema as a form).
3. Click "Invoke" to execute.
4. Inspect the response content and any errors.

This catches issues before the model encounters them:

- **Schema errors:** required fields missing from the form indicate schema registration bugs.
- **Validation failures:** invoke with edge cases — empty strings, special characters, max-length values.
- **Error messages:** verify error responses are helpful, not stack traces.
- **Response format:** confirm the model receives parseable content blocks.

Test matrix for each tool:

| Test case | Input | Expected |
|-----------|-------|----------|
| Happy path | Valid arguments | Correct result |
| Missing required field | Omit required param | Clear validation error |
| Invalid enum value | Out-of-range enum | Schema rejection |
| Empty result | Query matching nothing | Empty array, not error |
| Permission denied | Unauthorized operation | 403-style error message |
| Timeout | Slow backend | Graceful timeout error |

## Testing resources

The Resources tab shows registered resources and their URIs:

1. Browse the resource list or enter a URI manually.
2. Click "Fetch" to retrieve content.
3. Verify MIME type, content encoding, and data correctness.

For template URIs like `file://{path}`, test with multiple parameter values:

```
file:///README.md        → expect markdown content
file:///nonexistent.txt  → expect clear error
file:///../etc/passwd    → expect path traversal rejection
```

## Testing prompts

The Prompts tab renders prompt templates with their arguments:

1. Select a prompt.
2. Fill in parameters.
3. Preview the generated messages.
4. Verify the template produces well-structured instructions.

Prompts should generate messages that work as-is when sent to the model — check formatting, variable substitution, and instruction clarity.

## Inspecting the protocol

The Inspector's notification/log panel shows raw JSON-RPC messages:

```json
// Client → Server: tool call
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_tickets",
    "arguments": { "query": "login issue", "status": "open" }
  }
}

// Server → Client: tool result
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [{ "type": "text", "text": "[{\"id\": 1, \"title\": \"Login timeout\"}]" }],
    "isError": false
  }
}
```

Use this to debug:

- **Serialization issues:** arguments arriving differently than expected.
- **Response format errors:** missing `content` array, wrong content type.
- **Protocol violations:** missing `jsonrpc` field, wrong method names.

## Automated testing with the SDK

For CI/CD, test programmatically:

```typescript
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { describe, it, expect, beforeAll, afterAll } from "vitest";

describe("CRM MCP Server", () => {
  let client: Client;

  beforeAll(async () => {
    const transport = new StdioClientTransport({
      command: "node",
      args: ["dist/server.js"],
      env: { DATABASE_URL: "postgresql://localhost/test" },
    });
    client = new Client({ name: "test", version: "1.0.0" });
    await client.connect(transport);
  });

  afterAll(async () => {
    await client.close();
  });

  it("lists all expected tools", async () => {
    const { tools } = await client.listTools();
    const names = tools.map(t => t.name);
    expect(names).toContain("search_tickets");
    expect(names).toContain("create_ticket");
  });

  it("search_tickets returns results", async () => {
    const result = await client.callTool({
      name: "search_tickets",
      arguments: { query: "login", status: "open" },
    });
    expect(result.isError).toBeFalsy();
    const tickets = JSON.parse(result.content[0].text);
    expect(Array.isArray(tickets)).toBe(true);
  });

  it("create_ticket validates required fields", async () => {
    const result = await client.callTool({
      name: "create_ticket",
      arguments: { title: "" },
    });
    expect(result.isError).toBe(true);
  });
});
```

Run in CI on every pull request that modifies the MCP server.

## Common issues the Inspector catches

**Tool not appearing in list:** registration code not reached, server crash during startup, async registration not awaited.

**Schema validation too strict:** model generates arguments that fail validation because enum values or type constraints are too narrow.

**Response too large:** tool returns megabytes of data that exceed context limits. Add pagination or truncation.

**Missing error handling:** unhandled exceptions crash the server process instead of returning `isError: true`.

**Resource URI mismatch:** template URIs registered but fetch handler does not parse parameters correctly.

## Resources

- [MCP Inspector GitHub repository](https://github.com/modelcontextprotocol/inspector)
- [MCP Inspector npm package](https://www.npmjs.com/package/@modelcontextprotocol/inspector)
- [MCP TypeScript SDK client documentation](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP specification: protocol messages](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports/)
- [MCP server examples for testing reference](https://github.com/modelcontextprotocol/servers)

## Production notes for LLM stacks

When `mcp-server-testing-inspector` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `testing mcp servers with the inspector` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.
