---
title: "MCP Resources, Tools, and Prompts"
slug: "mcp-resources-vs-tools-vs-prompts"
description: "Understand the three MCP server capabilities — resources, tools, and prompts — and when to use each in agent and IDE integrations."
datePublished: "2025-04-26"
dateModified: "2026-07-17"
tags:
keywords: "MCP resources tools prompts, Model Context Protocol capabilities, MCP server design, MCP tool vs resource, MCP prompt templates"
faq:
  - q: "What is the difference between an MCP tool and an MCP resource?"
    a: "Tools are actions the model invokes — they have side effects like querying a database or creating a ticket. Resources are read-only data the model reads — file contents, API documentation, configuration. Tools are called; resources are fetched. If it changes state, it is a tool. If it provides context, it is a resource."
  - q: "When should I expose functionality as an MCP prompt instead of a tool?"
    a: "Prompts are reusable templates that guide the model's behavior — code review checklists, commit message formats, debugging workflows. Use prompts when you want to standardize how the model approaches a task, not when you want it to execute an action. Prompts shape thinking; tools take action."
  - q: "Can a single MCP server expose all three capability types?"
    a: "Yes, and most production servers should. A database MCP server might expose tools (run_query), resources (schema definitions, table descriptions), and prompts (SQL generation template). The client discovers all three during initialization and the model decides which to use based on the user's request."
---
You are building an MCP server for your project management system. Should "get task details" be a tool or a resource? Should "create a sprint plan" be a tool or a prompt? Should the API documentation be a resource or embedded in the system prompt?

MCP defines three distinct capability types — resources, tools, and prompts — and picking the wrong one creates awkward agent behavior. Tools that should be resources get invoked repeatedly with side effects. Resources that should be tools cannot trigger actions. Prompts that should be tools produce text instead of executing.

## The three capability types

| Capability | Direction | Side effects | Example |
|-----------|-----------|-------------|---------|
| **Resource** | Server → Client (read) | None | File contents, schema docs, config |
| **Tool** | Client → Server (action) | Yes | Query database, create ticket, send email |
| **Prompt** | Server → Client (template) | None | Code review checklist, commit message format |

During MCP initialization, the client calls `list_resources`, `list_tools`, and `list_prompts` to discover what the server offers.

## Resources: read-only context

Resources provide data the model reads to understand context. They are identified by URIs and fetched on demand:

```typescript
server.resource("schema://tables/users", async (uri) => ({
  contents: [{
    uri: uri.href,
    mimeType: "text/plain",
    text: `
      CREATE TABLE users (
        id UUID PRIMARY KEY,
        email VARCHAR(255) UNIQUE,
        created_at TIMESTAMPTZ
      );
    `,
  }],
}));

server.resource("docs://api/authentication", async (uri) => ({
  contents: [{
    uri: uri.href,
    mimeType: "text/markdown",
    text: await fs.readFile("docs/auth.md", "utf-8"),
  }],
}));
```

Resources can be static (fixed URI, fixed content) or dynamic (template URIs like `file://{path}`).

**When to use resources:**
- API documentation the model needs to write correct client code
- Database schemas for query generation
- Configuration files the model should reference
- Log files or status pages for debugging context

**Design principle:** if fetching it twice produces the same result and nothing changes, it is a resource.

## Tools: actions with side effects

Tools are functions the model invokes to take action in the world:

```typescript
server.tool("create_ticket", {
  title: { type: "string" },
  description: { type: "string" },
  priority: { type: "string", enum: ["low", "medium", "high", "critical"] },
}, async ({ title, description, priority }) => {
  const ticket = await jira.createIssue({ title, description, priority });
  return {
    content: [{ type: "text", text: `Created ticket ${ticket.key}` }],
  };
});

server.tool("run_query", {
  sql: { type: "string", description: "Read-only SQL query" },
}, async ({ sql }) => {
  validateReadOnly(sql);
  const results = await db.query(sql);
  return {
    content: [{ type: "text", text: JSON.stringify(results.rows) }],
  };
});
```

Tools have typed input schemas (JSON Schema) that the model uses to generate valid arguments. The model decides when to call a tool based on the user's request and the tool descriptions.

**When to use tools:**
- Any operation that creates, updates, or deletes data
- External API calls (send email, post message, trigger deployment)
- Computations that require server-side execution
- File writes

**Design principle:** if doing it twice produces different results or changes state, it is a tool.

## Prompts: reusable workflow templates

Prompts are parameterized templates that guide the model's approach to a task:

```typescript
server.prompt("code_review", {
  diff: { type: "string", description: "Git diff to review" },
  language: { type: "string", description: "Programming language" },
}, ({ diff, language }) => ({
  messages: [{
    role: "user",
    content: {
      type: "text",
      text: `Review this ${language} code change. Check for:
1. Logic errors and edge cases
2. Security vulnerabilities (injection, auth bypass)
3. Performance concerns
4. Test coverage gaps

Diff:
${diff}

Format: list each issue with severity (critical/major/minor) and suggested fix.`,
    },
  }],
}));
```

The client presents prompts as slash commands or menu options. When selected, the prompt template is sent to the model as a structured message.

**When to use prompts:**
- Standardized workflows (code review, commit messages, incident reports)
- Templates that combine instructions with user-provided data
- Onboarding patterns for new team members using AI tools

**Design principle:** if it shapes how the model thinks about a problem without executing an action, it is a prompt.

## Designing a cohesive MCP server

A well-designed server exposes all three types for the same domain:

```
Database MCP Server
├── Resources
│   ├── schema://tables/{name}     → table DDL
│   └── docs://query-guidelines      → SQL style guide
├── Tools
│   ├── run_query                    → execute read-only SQL
│   ├── explain_query                → EXPLAIN ANALYZE
│   └── list_tables                  → enumerate available tables
└── Prompts
    ├── generate_migration           → template for schema changes
    └── debug_slow_query             → structured debugging workflow
```

The model reads schema resources to understand the database, uses tools to query it, and applies prompts when the user asks for structured workflows.

## Common design mistakes

**Read operations as tools:** exposing `get_user(id)` as a tool instead of a resource means the model "invokes" a read operation, which feels like an action. Use a resource with a template URI: `users://{id}`.

**Write operations as prompts:** a prompt that says "create a ticket with these details" produces text describing a ticket instead of actually creating one. Writes must be tools.

**Static content as resources that change rarely:** if documentation updates once a month, a resource is fine. If it changes every request (live metrics), a tool is more appropriate because resources are cached by clients.

**Too many tools:** 50 tools overwhelm the model's tool selection. Group related operations, use clear descriptions, and prefer resources for read-only data access.

## Common production mistakes

Teams get resources vs tools vs prompts wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of resources vs tools vs prompts fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [MCP specification: server capabilities](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/)
- [MCP resources specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/resources/)
- [MCP tools specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/tools/)
- [MCP prompts specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/server/prompts/)
- [MCP server examples (GitHub, filesystem, postgres)](https://github.com/modelcontextprotocol/servers)
