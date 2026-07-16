---
title: "Deploying Remote MCP Servers"
slug: "mcp-remote-servers-deployment"
description: "Deploy MCP servers for remote access over HTTP and SSE: authentication, containerization, scaling, and production patterns for the Model Context Protocol."
datePublished: "2025-04-22"
dateModified: "2025-04-22"
tags: ["AI", "MCP", "Deployment", "Infrastructure"]
keywords: "MCP remote server deployment, Model Context Protocol HTTP, MCP SSE transport, MCP server production, MCP server Docker, MCP cloud deployment"
faq:
  - q: "When should I deploy an MCP server remotely instead of running it locally via stdio?"
    a: "Deploy remotely when multiple users or agents need the same tools, when the server requires credentials you cannot distribute to clients, or when the tool backend (database, API) is only reachable from your network. Local stdio is simpler for single-developer workflows and IDE integrations."
  - q: "How do I secure a remote MCP server?"
    a: "Require OAuth 2.0 or API key authentication on every request, terminate TLS at the load balancer, scope tool permissions per client identity, and never expose MCP servers directly to the public internet without authentication. Treat MCP tools with the same security model as API endpoints."
  - q: "Can I run multiple MCP servers behind one endpoint?"
    a: "Each MCP server is typically a separate endpoint or path. A gateway can route /mcp/github to the GitHub tools server and /mcp/database to the database server. Clients connect to one server at a time — use an MCP client configuration that lists multiple server URLs."
---

Your team built an MCP server that gives AI agents access to your internal CRM, ticketing system, and deployment pipeline. It works perfectly on your laptop via stdio — Cursor connects, tools execute, life is good. Then a colleague in another timezone needs the same tools, your CI agent needs database access it cannot reach locally, and security says you cannot put production database credentials on every developer machine.

Remote MCP server deployment moves the server from a local subprocess to a network-accessible service. The protocol supports HTTP and SSE transports for exactly this scenario, but production deployment requires authentication, containerization, health monitoring, and the same operational discipline you apply to any API service.

## Local stdio vs. remote HTTP/SSE

**Stdio (local):**
```
Cursor IDE → spawns subprocess → MCP Server (stdin/stdout)
```

Simple, no network, no auth needed. One client, one server, same machine.

**HTTP/SSE (remote):**
```
Agent Client → HTTPS → Load Balancer → MCP Server (container)
                                       → Backend APIs / Databases
```

Multiple clients, centralized credentials, network latency, auth required.

## Building an MCP server with HTTP transport

Using the TypeScript SDK:

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { SSEServerTransport } from "@modelcontextprotocol/sdk/server/sse.js";
import express from "express";

const server = new McpServer({
  name: "crm-tools",
  version: "1.0.0",
});

server.tool("lookup_customer", {
  email: { type: "string", description: "Customer email address" },
}, async ({ email }) => {
  const customer = await crmClient.findByEmail(email);
  return { content: [{ type: "text", text: JSON.stringify(customer) }] };
});

const app = express();

app.get("/sse", async (req, res) => {
  const transport = new SSEServerTransport("/messages", res);
  await server.connect(transport);
});

app.post("/messages", express.json(), async (req, res) => {
  // Handle client messages
});

app.listen(8080, () => console.log("MCP server listening on :8080"));
```

The SSE transport uses Server-Sent Events for server-to-client messages and HTTP POST for client-to-server messages.

## Containerization

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY dist/ ./dist/
EXPOSE 8080
HEALTHCHECK CMD curl -f http://localhost:8080/health || exit 1
CMD ["node", "dist/server.js"]
```

```yaml
# docker-compose.yml for local staging
services:
  mcp-crm:
    build: .
    ports:
      - "8080:8080"
    environment:
      - CRM_API_KEY=${CRM_API_KEY}
      - AUTH_SECRET=${AUTH_SECRET}
    restart: unless-stopped
```

Keep secrets in environment variables or a secret manager — never in the image.

## Authentication

Remote MCP servers must authenticate clients. OAuth 2.0 is the MCP-specified approach:

```typescript
import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth.js";

app.use("/sse", requireBearerAuth({
  verifier: async (token) => {
    const payload = await verifyJWT(token, JWKS_URI);
    return { clientId: payload.sub, scopes: payload.scope.split(" ") };
  },
}));
```

For simpler deployments, API key authentication works:

```typescript
app.use((req, res, next) => {
  const key = req.headers.authorization?.replace("Bearer ", "");
  if (!key || !validKeys.has(key)) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
});
```

Scope tool access per client identity — a read-only agent should not invoke write tools.

## Kubernetes deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-crm-server
spec:
  replicas: 2
  selector:
    matchLabels:
      app: mcp-crm
  template:
    metadata:
      labels:
        app: mcp-crm
    spec:
      containers:
        - name: mcp-server
          image: registry.example.com/mcp-crm:1.0.0
          ports:
            - containerPort: 8080
          env:
            - name: CRM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: mcp-secrets
                  key: crm-api-key
          livenessProbe:
            httpGet:
              path: /health
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
```

SSE connections are long-lived. Set load balancer idle timeouts above your expected session duration (300–600 seconds). Use session affinity if your server holds in-memory state per connection.

## Client configuration for remote servers

Cursor and Claude Desktop configure remote MCP servers in their settings:

```json
{
  "mcpServers": {
    "crm-tools": {
      "url": "https://mcp.example.com/sse",
      "headers": {
        "Authorization": "Bearer ${CRM_MCP_TOKEN}"
      }
    }
  }
}
```

For Claude Desktop, remote server support depends on the client version. Check current transport support before deploying.

## Monitoring and observability

Track the same metrics you would for any API:

- **Request rate** per tool
- **Error rate** per tool (tool execution failures vs. transport errors)
- **Latency** p50/p99 per tool invocation
- **Active SSE connections**
- **Authentication failures**

Log every tool invocation with client identity, tool name, and arguments (redact sensitive fields):

```typescript
server.tool("lookup_customer", schema, async (args, context) => {
  logger.info("tool_invocation", {
    tool: "lookup_customer",
    client: context.clientId,
    email: args.email,
  });
  // ... execute tool
});
```

## Common production mistakes

Teams get remote servers deployment wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of remote servers deployment fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When remote servers deployment misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Model Context Protocol specification](https://spec.modelcontextprotocol.io/)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP transport specification (HTTP/SSE)](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/transports)
- [MCP server examples repository](https://github.com/modelcontextprotocol/servers)
- [Anthropic MCP documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp)
