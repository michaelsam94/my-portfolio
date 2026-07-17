---
title: "MCP Sampling and Elicitation"
slug: "mcp-sampling-elicitation"
description: "Use MCP sampling to let servers request LLM completions and elicitation to gather structured user input — reversing the typical client-server flow."
datePublished: "2025-04-30"
dateModified: "2026-07-17"
tags:
keywords: "MCP sampling, MCP elicitation, Model Context Protocol sampling, server-initiated LLM, MCP user input, MCP reverse RPC"
faq:
  - q: "What is MCP sampling and why would a server need it?"
    a: "Sampling lets an MCP server request an LLM completion from the client's model. A database MCP server might ask the model to generate SQL from a natural language question before executing it. The server needs LLM capability but should not embed its own model — sampling delegates inference to the client's existing model connection."
  - q: "How is elicitation different from a regular tool call?"
    a: "Elicitation lets the server ask the user for additional input mid-workflow — a confirmation dialog, a form field, or a choice between options. Tool calls execute actions; elicitation pauses execution to gather information the server cannot infer. The user sees a prompt and responds before the workflow continues."
  - q: "Are sampling and elicitation supported by all MCP clients?"
    a: "Support varies. Claude Desktop and Cursor support sampling in recent versions. Elicitation is newer and client support is still rolling out. Check your client's capability negotiation during MCP initialization — the server should gracefully degrade if the client does not advertise sampling or elicitation support."
---
Most MCP interactions flow one direction: the client sends a user message to the model, the model decides to call a tool, the server executes it and returns results. But some server workflows need to ask the model a question or ask the user for input mid-execution. A code review server wants the model to analyze a diff before posting comments. A deployment server needs the user to confirm before pushing to production.

MCP sampling and elicitation reverse the typical flow. Sampling lets servers request LLM completions. Elicitation lets servers request structured input from the user. Together they enable multi-step server workflows that were previously impossible without embedding an LLM inside the server itself.

## Sampling: server-initiated LLM requests

In normal MCP flow, the model calls server tools. With sampling, the server calls the client's model:

```
Standard flow:
  User → Model → tool_call → Server → result → Model → User

Sampling flow:
  User → Model → tool_call → Server → sampling_request → Model → Server → result → Model → User
```

The server sends a `sampling/createMessage` request to the client, which forwards it to the connected LLM:

```typescript
// Server-side: request LLM analysis during tool execution
server.tool("review_code", {
  diff: { type: "string" },
}, async ({ diff }, context) => {
  // Ask the client's model to analyze the diff
  const analysis = await context.sample({
    messages: [{
      role: "user",
      content: {
        type: "text",
        text: `Analyze this diff for security issues:\n${diff}`,
      },
    }],
    maxTokens: 1000,
  });

  const issues = parseIssues(analysis.content);
  return {
    content: [{ type: "text", text: JSON.stringify(issues) }],
  };
});
```

The client controls which models the server can access and can set rate limits, token budgets, and content policies on sampling requests.

## Sampling use cases

**SQL generation before execution:**
```typescript
server.tool("natural_language_query", {
  question: { type: "string" },
}, async ({ question }, context) => {
  const schema = await getSchemaResource();

  const sqlResponse = await context.sample({
    messages: [{
      role: "user",
      content: {
        type: "text",
        text: `Given schema:\n${schema}\n\nGenerate SQL for: ${question}`,
      },
    }],
    maxTokens: 200,
  });

  const sql = extractSQL(sqlResponse.content);
  validateReadOnly(sql);
  const results = await db.query(sql);
  return { content: [{ type: "text", text: JSON.stringify(results.rows) }] };
});
```

**Content classification before routing:**
```typescript
const category = await context.sample({
  messages: [{
    role: "user",
    content: { type: "text", text: `Classify as bug/feature/question: ${ticketText}` },
  }],
  maxTokens: 10,
});
// Route based on classification
```

**Multi-step reasoning within a tool:**
A tool that needs the model to plan before executing — generate a migration plan, then execute each step.

## Elicitation: gathering user input mid-workflow

Elicitation lets the server pause and ask the user for structured input:

```typescript
server.tool("deploy_to_production", {
  service: { type: "string" },
  version: { type: "string" },
}, async ({ service, version }, context) => {
  // Confirm with the user before deploying
  const confirmation = await context.elicit({
    message: `Deploy ${service} v${version} to production?`,
    requestedSchema: {
      type: "object",
      properties: {
        confirmed: { type: "boolean", description: "Confirm deployment" },
        rollback_plan: { type: "string", description: "Rollback procedure if needed" },
      },
      required: ["confirmed"],
    },
  });

  if (!confirmation.confirmed) {
    return { content: [{ type: "text", text: "Deployment cancelled by user." }] };
  }

  await deployService(service, version);
  return { content: [{ type: "text", text: `Deployed ${service} v${version}` }] };
});
```

The client renders the elicitation request as a dialog, form, or inline prompt. The user responds, and the server continues execution with the provided data.

## Elicitation use cases

**Confirmation for destructive actions:**
Delete, deploy, send — anything irreversible should elicit confirmation rather than relying on the model to ask.

**Missing required parameters:**
When the user's request is ambiguous, elicit the specific missing field:

```typescript
const details = await context.elicit({
  message: "Which environment should I deploy to?",
  requestedSchema: {
    type: "object",
    properties: {
      environment: { type: "string", enum: ["staging", "production"] },
    },
    required: ["environment"],
  },
});
```

**Multi-step wizards:**
Complex workflows that need sequential user input — creating a project with name, template, team, and permissions.

## Capability negotiation

During MCP initialization, the client advertises its capabilities:

```json
{
  "capabilities": {
    "sampling": {},
    "elicitation": {}
  }
}
```

Servers must check before using either feature:

```typescript
server.tool("smart_query", schema, async (args, context) => {
  if (!context.clientCapabilities.sampling) {
    // Fallback: require the user to provide SQL directly
    return { content: [{ type: "text", text: "Please provide a SQL query." }] };
  }

  const sql = await context.sample({ /* ... */ });
  // ...
});
```

Graceful degradation ensures servers work with clients that lack newer capabilities.

## Security considerations

Sampling and elicitation introduce new attack surfaces:

**Sampling:**
- Servers can exfiltrate data by embedding it in sampling prompts sent to the model.
- Rate-limit sampling requests per server.
- Log all sampling requests for audit.

**Elicitation:**
- Servers can phish users with fake confirmation dialogs.
- Clients should clearly label elicitation UI as coming from a specific MCP server.
- Never elicit credentials or secrets — use OAuth flows instead.

```typescript
// Client-side: validate sampling requests
function handleSamplingRequest(request: SamplingRequest): boolean {
  if (request.messages.some(m => containsSensitiveData(m.content))) {
    logger.warn("Blocked sampling request with sensitive data");
    return false;
  }
  if (samplingRateLimiter.isExceeded(request.serverId)) {
    return false;
  }
  return true;
}
```

## Common production mistakes

Teams get sampling elicitation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of sampling elicitation fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When sampling elicitation misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MCP sampling specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/client/sampling/)
- [MCP elicitation specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/utilities/elicitation/)
- [MCP client capabilities negotiation](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle/)
- [MCP TypeScript SDK sampling examples](https://github.com/modelcontextprotocol/typescript-sdk)
- [Anthropic MCP client documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
