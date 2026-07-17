---
title: "Authenticating MCP Servers with OAuth"
slug: "mcp-server-authentication-oauth"
description: "Implement OAuth 2.0 authentication for MCP servers: authorization flows, token management, scoped permissions, and client registration patterns."
datePublished: "2025-05-08"
dateModified: "2026-07-17"
tags:
keywords: "MCP OAuth authentication, Model Context Protocol OAuth 2.0, MCP server auth, MCP bearer token, OAuth PKCE MCP, MCP authorization server"
faq:
  - q: "Why does MCP specify OAuth instead of API keys?"
    a: "OAuth provides scoped access (read vs. write tools), user consent flows, token expiration and refresh, and revocation — all critical when MCP servers access user data on third-party services like GitHub, Google Drive, or Slack. API keys are simpler but grant full access with no expiration or user consent."
  - q: "Who runs the OAuth authorization server for MCP?"
    a: "The MCP server operator runs or delegates to an authorization server. For third-party integrations (GitHub MCP server accessing GitHub API), the server uses GitHub's OAuth. For custom MCP servers, you implement an authorization server or use a provider like Auth0, Keycloak, or Okta."
  - q: "How does token refresh work with long-lived MCP sessions?"
    a: "MCP clients store refresh tokens securely and request new access tokens before expiration. SSE connections may outlast a single access token lifetime — the client must refresh mid-session without disconnecting. Implement token refresh in the client's MCP transport layer, not in individual tool calls."
---
Your MCP server connects to GitHub, Slack, and your internal CRM. Each service needs credentials. Hardcoding API keys in the server config means every client gets the same all-or-nothing access, keys never expire, and revoking one user's access means rotating for everyone.

The MCP specification defines OAuth 2.0 as the standard authentication mechanism for remote servers. OAuth gives you scoped permissions, user consent, token expiration, and per-client access control — the same security properties you expect from any modern API integration.

## MCP OAuth architecture

```
┌──────────┐     1. Connect      ┌────────────┐
│  MCP     │ ──────────────────→ │  MCP       │
│  Client  │                     │  Server    │
│ (Cursor) │ ←────────────────── │            │
└──────────┘   2. Auth required  └────────────┘
      │                                  │
      │  3. OAuth flow                   │
      ▼                                  ▼
┌──────────────┐              ┌──────────────────┐
│ Authorization│              │ Resource Server  │
│ Server       │              │ (GitHub, CRM)    │
│ (Auth0/etc)  │              │                  │
└──────────────┘              └──────────────────┘
```

1. Client connects to MCP server.
2. Server responds that authentication is required, providing OAuth metadata.
3. Client initiates OAuth flow with the authorization server.
4. User grants consent for requested scopes.
5. Client receives access token and reconnects with Bearer auth.

## Server-side: advertising auth requirements

MCP servers declare their auth requirements during initialization:

```typescript
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";

const server = new McpServer({
  name: "github-tools",
  version: "1.0.0",
});

// OAuth metadata endpoint
server.setRequestHandler("auth/metadata", async () => ({
  authorizationUrl: "https://github.com/login/oauth/authorize",
  tokenUrl: "https://github.com/login/oauth/access_token",
  scopes: ["repo:read", "issues:write"],
  clientId: process.env.OAUTH_CLIENT_ID,
}));
```

When an unauthenticated client connects, the server returns a 401 with a `WWW-Authenticate` header pointing to the OAuth metadata:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Bearer realm="mcp", resource_metadata="https://mcp.example.com/.well-known/oauth-protected-resource"
```

## Client-side: OAuth flow with PKCE

MCP clients use OAuth 2.0 with PKCE (Proof Key for Code Exchange) for public clients that cannot store a client secret:

```typescript
import { createHash, randomBytes } from "crypto";

function generatePKCE() {
  const verifier = randomBytes(32).toString("base64url");
  const challenge = createHash("sha256").update(verifier).digest("base64url");
  return { verifier, challenge };
}

async function authenticateMCP(serverUrl: string): Promise<string> {
  const metadata = await fetch(`${serverUrl}/.well-known/oauth-protected-resource`).then(r => r.json());
  const { verifier, challenge } = generatePKCE();

  const authUrl = new URL(metadata.authorizationUrl);
  authUrl.searchParams.set("client_id", metadata.clientId);
  authUrl.searchParams.set("redirect_uri", "http://localhost:9876/callback");
  authUrl.searchParams.set("scope", metadata.scopes.join(" "));
  authUrl.searchParams.set("code_challenge", challenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("response_type", "code");

  await openBrowser(authUrl.toString());
  const code = await waitForCallback("http://localhost:9876/callback");

  const tokenResponse = await fetch(metadata.tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: "http://localhost:9876/callback",
      client_id: metadata.clientId,
      code_verifier: verifier,
    }),
  });

  const { access_token, refresh_token, expires_in } = await tokenResponse.json();
  await storeTokens(serverUrl, { access_token, refresh_token, expires_in });
  return access_token;
}
```

## Scoped permissions per tool

Map OAuth scopes to tool access:

```typescript
const TOOL_SCOPES: Record<string, string[]> = {
  "list_repos": ["repo:read"],
  "create_issue": ["repo:read", "issues:write"],
  "delete_repo": ["repo:admin"],
};

server.tool("create_issue", schema, async (args, context) => {
  const tokenScopes = context.authInfo?.scopes ?? [];
  const required = TOOL_SCOPES["create_issue"];

  if (!required.every(s => tokenScopes.includes(s))) {
    throw new McpError("Insufficient permissions. Required scopes: " + required.join(", "));
  }

  return createGitHubIssue(args, context.authInfo.token);
});
```

Users grant only the scopes they are comfortable with. A read-only agent gets `repo:read` and cannot invoke write tools.

## Token refresh for long sessions

SSE connections may last longer than access token lifetime:

```typescript
class TokenManager {
  private tokens: Map<string, TokenSet> = new Map();

  async getValidToken(serverUrl: string): Promise<string> {
    const tokens = this.tokens.get(serverUrl);
    if (!tokens) throw new Error("Not authenticated");

    if (Date.now() > tokens.expiresAt - 60_000) {
      const refreshed = await this.refresh(serverUrl, tokens.refreshToken);
      this.tokens.set(serverUrl, refreshed);
      return refreshed.accessToken;
    }
    return tokens.accessToken;
  }

  private async refresh(serverUrl: string, refreshToken: string): Promise<TokenSet> {
    const metadata = await getAuthMetadata(serverUrl);
    const response = await fetch(metadata.tokenUrl, {
      method: "POST",
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: refreshToken,
        client_id: metadata.clientId,
      }),
    });
    return parseTokenResponse(await response.json());
  }
}
```

Refresh tokens before they expire — 60 seconds of buffer prevents mid-request failures.

## Dynamic client registration

For MCP servers that do not pre-register clients, OAuth 2.0 Dynamic Client Registration (RFC 7591) allows the MCP client to register itself:

```typescript
async function registerClient(authServerUrl: string): Promise<ClientCredentials> {
  const response = await fetch(`${authServerUrl}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_name: "Cursor IDE",
      redirect_uris: ["http://localhost:9876/callback"],
      grant_types: ["authorization_code", "refresh_token"],
      response_types: ["code"],
      token_endpoint_auth_method: "none",
    }),
  });
  return response.json();
}
```

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get server authentication oauth wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of server authentication oauth fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When server authentication oauth misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [MCP authorization specification](https://spec.modelcontextprotocol.io/specification/2025-03-26/basic/authorization/)
- [OAuth 2.0 PKCE (RFC 7636)](https://datatracker.ietf.org/doc/html/rfc7636)
- [OAuth 2.0 Dynamic Client Registration (RFC 7591)](https://datatracker.ietf.org/doc/html/rfc7591)
- [MCP TypeScript SDK auth module](https://github.com/modelcontextprotocol/typescript-sdk)
- [Auth0 OAuth 2.0 documentation](https://auth0.com/docs/authenticate/protocols/oauth)
