---
title: "OAuth2 Resource Indicators and Audience"
slug: "oauth2-resource-indicators-audience"
description: "Use RFC 8707 resource indicators so access tokens are minted for the correct API audience—stopping token passthrough and confused-deputy attacks."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags: ["Security", "OAuth", "Authentication", "Backend"]
keywords: "oauth2 resource indicators, RFC 8707, token audience, audience claim, api authorization"
faq:
  - q: "What is a resource indicator in OAuth2?"
    a: "A URI passed via the resource parameter telling the authorization server which API the access token should be valid for, so the token audience matches that API."
  - q: "How is resource different from scope?"
    a: "Scope expresses what the client may do. Audience expresses where the token may be used. Correct scopes with wrong audience should be rejected by the resource server."
  - q: "Why does token passthrough happen without audience binding?"
    a: "When all APIs accept the same JWT without checking aud, a token for a low-privilege API can be forwarded to a high-privilege internal service."
  - q: "Should every microservice have its own resource URI?"
    a: "Prefer one resource URI per security boundary—typically per API gateway or service cluster—not per endpoint."
---

An internal admin tool obtained an access token for the read-only catalog API and used it against the payments service. Payments accepted it—the JWT was signed by the corporate AS, scopes included `read:payments` from an earlier experiment, and nobody validated `aud`. Resource indicators (RFC 8707) fix audience at issuance so payments rejects tokens minted for catalog.

## Audience vs scope

Scope: what actions may this client perform? Audience: which resource server should accept this token? Without explicit audience, many AS products default to `aud: client_id` or a single global API identifier.

## RFC 8707 resource parameter

Clients include `resource` in token requests. The AS validates the client is allowed to request that resource, sets token audience accordingly, and returns JWT or opaque token with correct `aud` claim. Resource servers validate `aud` before scope checks.

## Token passthrough and confused deputy

Service A forwarding a user token to privileged Service B is unsafe unless B validates audience. B must reject tokens unless `aud` is B's identifier. A should use on-behalf-of token exchange or service credentials to call B.

## Gateway vs service validation

Validate JWT signature, `iss`, `exp`, and `aud` at the API gateway. Each microservice still validates `aud` if tokens can arrive without passing through the gateway.

## Client notes

Mobile apps: separate access tokens per resource or array `aud` with agreed validation. SPAs with BFF: browser never holds multi-audience tokens; BFF requests tokens server-side with explicit `resource`.

## Migration

Inventory APIs sharing one issuer; assign canonical resource URIs; update AS to accept `resource`; deploy resource servers with aud validation in log-only mode; enforce after error rate proves clients send correct resource.

Resource indicators turn "signed by our AS" into "signed for this API"—the difference between identity plumbing and an authorization boundary.

## Worked example: catalog vs payments

1. Catalog API resource URI: `https://api.example.com/catalog`
2. Payments API resource URI: `https://api.example.com/payments`
3. Mobile app requests token with `resource=https://api.example.com/catalog` for browse-only features.
4. Payments middleware rejects tokens whose `aud` is catalog—even if scopes accidentally include payment scopes from a misconfigured consent screen.

Log token issuance with requested `resource` and resulting `aud` to debug client misconfiguration without guessing from 403 errors alone.

## LLM gateway audience binding

When an LLM gateway calls internal tools on behalf of users, mint **tool-specific tokens** via token exchange with explicit resource indicators—not one super-token for all backends. A compromised prompt injection that steals a catalog-scoped token should not reach payroll APIs.

## Testing audience validation

Contract tests per API: present token with wrong `aud`, assert 401 with stable error code `invalid_token_audience`. CI should fail if a new route ships without audience middleware registered.
## JWT validation middleware

```typescript
function validateAudience(token: JwtPayload, expectedResource: string) {
  const aud = token.aud;
  const allowed = Array.isArray(aud) ? aud : [aud];
  if (!allowed.includes(expectedResource)) {
    throw new UnauthorizedError("invalid_token_audience");
  }
}
```

Register expected resource URI in each service's config—not hardcoded in shared library without per-service override.

## Array audience pitfalls

Some AS products emit multiple `aud` values for multi-API tokens. Document whether your resource server accepts array membership or requires single-aud tokens. LLM orchestrators calling five internal APIs should prefer token exchange per hop rather than one JWT with five audiences that every API must parse defensively.

## Error responses

Return OAuth-style errors: `401` with `WWW-Authenticate: Bearer error="invalid_token", error_description="audience mismatch"`. Clients and support teams diagnose faster than generic forbidden messages.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.
