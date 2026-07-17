---
title: "AI Agents: Opaque Token Introspection"
slug: "agent-opaque-token-introspection"
description: "How agent gateways validate opaque OAuth2 access tokens via RFC 7662 introspection — caching, audience checks, revocation latency, and fail-closed middleware without parsing JWT claims locally."
datePublished: "2025-09-24"
dateModified: "2025-09-24"
tags: ["AI Agents", "OAuth2", "Security", "Authentication"]
keywords: "opaque token introspection, RFC 7662, OAuth2 agent gateway, token validation cache, authorization server introspection endpoint"
faq:
  - q: "When should an agent platform use opaque tokens instead of JWTs?"
    a: "Choose opaque tokens when you need immediate server-side revocation, short-lived sessions with centralized policy, or when embedding claims in a JWT would leak tenant metadata to clients. Agent orchestrators that call third-party APIs on behalf of users often receive opaque tokens from enterprise IdPs — introspection is the only validation path."
  - q: "What does RFC 7662 introspection return?"
    a: "A JSON object with `active` (boolean), and when active: `scope`, `client_id`, `username`, `sub`, `exp`, `iat`, `aud`, and custom claims your authorization server attaches. Inactive tokens return `{ \"active\": false }` with HTTP 200 — not 401."
  - q: "How do you cache introspection without serving revoked tokens?"
    a: "Cache positive results keyed by token hash with TTL capped at min(remaining token lifetime, your max cache window — typically 30–60 seconds). Never cache `active: false`. On logout or admin revocation webhooks, purge cache entries by `sub` or `jti` if your IdP exposes them."
  - q: "Should introspection failures fail open or closed?"
    a: "Fail closed for agent tool execution — an agent that cannot prove caller identity must not invoke side-effecting tools. Fail open only for read-only telemetry with explicit feature flags, and never for billing, deployment, or data-deletion paths."
---

A support engineer once traced a phantom refund to an agent run that executed forty minutes after the user clicked Sign Out. The access token looked valid in application logs — because the gateway cached a positive introspection result for five minutes while the authorization server had already marked the session inactive. Opaque tokens hide their payload; introspection is how you learn whether a bearer string still represents an authorized principal. Get caching, audience binding, or error handling wrong and your agent platform becomes a pipeline that executes tools for ghosts.

## What opaque tokens actually are

An opaque access token is an uninterpretable reference — often a random 256-bit value — issued by an authorization server (Auth0, Okta, Keycloak, Azure AD, a homegrown OAuth2 deployment). Resource servers cannot validate it locally the way they decode a JWT and verify a signature against a JWKS endpoint. They must call the introspection endpoint:

```
POST /oauth/introspect
Authorization: Basic <client_id:client_secret>
Content-Type: application/x-www-form-urlencoded

token=<access_token>&token_type_hint=access_token
```

The response tells you whether the token is **active** and, if so, which scopes, subject, audience, and expiry apply. For agent platforms, that subject maps to the human or service account whose permissions constrain tool calls.

JWT advocates will note introspection adds a network hop. That is the trade: centralized revocation beats local verification when sessions must die immediately after password reset, device loss, or SOC-mandated kill switches.

## Where introspection sits in an agent gateway

```
Client                Agent gateway              Auth server           Tool executor
  │                        │                          │                      │
  │  Bearer opaque token   │                          │                      │
  │ ──────────────────────►│                          │                      │
  │                        │  POST /introspect        │                      │
  │                        │ ────────────────────────►│                      │
  │                        │◄──────────────────────── │  { active, scope }   │
  │                        │  bind sub → tool policy  │                      │
  │                        │ ───────────────────────────────────────────────►│
  │◄────────────────────── │  streamed response       │                      │
```

Every inbound request to `/v1/agents/run` should introspect **once** at the edge middleware, attach normalized claims to request context, and never re-introspect on every internal microservice hop unless you lack a trusted internal identity layer.

## Reference middleware (Node.js)

```typescript
import { createHash } from "crypto";

interface IntrospectionResult {
  active: boolean;
  sub?: string;
  scope?: string;
  aud?: string | string[];
  exp?: number;
  client_id?: string;
}

const CACHE_TTL_MS = 45_000;

function tokenCacheKey(token: string): string {
  return createHash("sha256").update(token).digest("hex");
}

async function introspect(
  token: string,
  authServerUrl: string,
  clientId: string,
  clientSecret: string
): Promise<IntrospectionResult> {
  const body = new URLSearchParams({ token, token_type_hint: "access_token" });
  const basic = Buffer.from(`${clientId}:${clientSecret}`).toString("base64");

  const res = await fetch(`${authServerUrl}/oauth/introspect`, {
    method: "POST",
    headers: {
      Authorization: `Basic ${basic}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
    signal: AbortSignal.timeout(2_000),
  });

  if (!res.ok) {
    throw new Error(`introspection_http_${res.status}`);
  }
  return res.json() as Promise<IntrospectionResult>;
}

export function requireActiveToken(
  cache: Map<string, { result: IntrospectionResult; expiresAt: number }>,
  expectedAudience: string
) {
  return async (req: Request, ctx: { claims?: IntrospectionResult }) => {
    const auth = req.headers.get("authorization");
    if (!auth?.startsWith("Bearer ")) {
      return Response.json({ error: "missing_token" }, { status: 401 });
    }
    const token = auth.slice(7);
    const key = tokenCacheKey(token);
    const now = Date.now();

    let result = cache.get(key)?.expiresAt > now ? cache.get(key)!.result : undefined;

    if (!result) {
      try {
        result = await introspect(
          token,
          process.env.AUTH_SERVER_URL!,
          process.env.INTROSPECT_CLIENT_ID!,
          process.env.INTROSPECT_CLIENT_SECRET!
        );
      } catch {
        // Fail closed — do not execute tools on auth uncertainty
        return Response.json({ error: "introspection_unavailable" }, { status: 503 });
      }
      if (result.active) {
        const ttl = Math.min(
          CACHE_TTL_MS,
          result.exp ? Math.max(0, result.exp * 1000 - now) : CACHE_TTL_MS
        );
        cache.set(key, { result, expiresAt: now + ttl });
      }
    }

    if (!result.active) {
      return Response.json({ error: "token_inactive" }, { status: 401 });
    }

    const aud = result.aud;
    const audiences = Array.isArray(aud) ? aud : aud ? [aud] : [];
    if (audiences.length && !audiences.includes(expectedAudience)) {
      return Response.json({ error: "wrong_audience" }, { status: 403 });
    }

    ctx.claims = result;
    return null; // continue pipeline
  };
}
```

Three details easy to miss: hash tokens before using them as cache keys (never log raw bearer values), cap cache TTL by remaining `exp`, and validate `aud` against your agent API identifier — tokens valid for another resource server must not invoke your tools.

## Scope-to-tool mapping

Introspection tells you **who** and **what scopes**; your agent registry decides **which tools** those scopes unlock. Keep that mapping in version-controlled configuration, not scattered `if` statements:

```yaml
# tool-policy.yaml
tools:
  stripe.refund:
    required_scopes: ["billing:write"]
  github.merge_pr:
    required_scopes: ["repos:write"]
  slack.post_message:
    required_scopes: ["chat:write"]
```

At runtime, split `scope` on spaces and require intersection with each tool's `required_scopes` before enqueueing execution. When product adds a destructive tool, you add a scope line — auditable in PR review.

## Caching layers beyond process memory

Single-node `Map` caches fail under horizontal scaling — each pod holds different state, and revocation takes longest on cold pods. Production setups use Redis with the same key scheme:

```python
import hashlib
import json
import redis

r = redis.Redis.from_url("redis://cache:6379/0")

def cache_get(token: str) -> dict | None:
    key = "intro:" + hashlib.sha256(token.encode()).hexdigest()
    raw = r.get(key)
    return json.loads(raw) if raw else None

def cache_set(token: str, payload: dict, ttl_sec: int) -> None:
    if not payload.get("active"):
        return  # never cache inactive
    key = "intro:" + hashlib.sha256(token.encode()).hexdigest()
    r.setex(key, ttl_sec, json.dumps(payload))

def purge_subject(subject: str) -> None:
    # Called from IdP logout webhook — maintain reverse index sub → keys if needed
    for key in r.scan_iter(f"intro:sub:{subject}:*"):
        r.delete(key)
```

Wire your IdP's session-revocation webhook (Okta `user.session.end`, Auth0 `guardian` events) to call `purge_subject`. Without that hook, cache TTL is your only revocation bound.

## Operational failure modes

| Symptom | Likely cause | Mitigation |
|---------|--------------|------------|
| 503 spikes on agent runs | Auth server slow/down | Circuit breaker; short negative cache forbidden; degrade read-only paths only |
| Users stay "logged in" after logout | Cache TTL too long | Cap at 30s; webhook purge; never cache inactive |
| Cross-tenant tool calls | Missing `aud` check | Bind audience at gateway; reject mismatched tokens |
| Introspection storm at scale | Per-microservice calls | Introspect once at gateway; propagate signed internal identity |

Instrument `introspection_latency_ms`, `introspection_cache_hit_ratio`, and `token_inactive_rejected_total`. Alert when cache hit ratio drops suddenly — often means token rotation or an attack spray of random bearer strings.

## Introspection versus JWT local validation

| Concern | Opaque + introspection | JWT + JWKS |
|---------|------------------------|------------|
| Revocation latency | Bounded by cache TTL + webhook purge | Until `exp`; denylist optional |
| Network dependency | Per cache miss | JWKS fetch periodically |
| Token size | Small reference | Larger; claims visible to client |
| Custom claims | Auth server controlled | Embedded; rotation needs key mgmt |

Hybrid stacks issue JWTs to first-party SPAs and opaque tokens to confidential agent clients — your gateway middleware should branch on token shape (`eyJ` prefix heuristic is insufficient; inspect `token_type` from introspection or use separate auth routes).

## Closing note

Opaque token introspection is not exotic OAuth trivia — it is the front door for enterprise agent deployments where security teams refuse client-visible JWT claims and demand instant session kill. Treat introspection as part of your availability story: timeout budgets, fail-closed semantics, audience enforcement, and cache invalidation wired to real logout events. The phantom refund incident ended with a forty-five-second cache cap and an Okta webhook that flushes Redis keys by `sub`. Boring changes; no more ghost agents.

## Resources

- [RFC 7662 — OAuth 2.0 Token Introspection](https://datatracker.ietf.org/doc/html/rfc7662)
- [OAuth 2.0 Bearer Token Usage (RFC 6750)](https://datatracker.ietf.org/doc/html/rfc6750)
- [Keycloak Token Introspection Endpoint](https://www.keycloak.org/docs/latest/securing_apps/#_token-introspection-endpoint)
- [Auth0 Token Introspection](https://auth0.com/docs/secure/tokens/token-introspection)
- [OWASP OAuth 2.0 Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/OAuth2_Cheat_Sheet.html)
