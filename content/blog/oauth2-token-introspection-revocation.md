---
title: "Token Introspection and Revocation"
slug: "oauth2-token-introspection-revocation"
description: "Implement OAuth 2.0 token introspection and revocation: validate opaque tokens, revoke access and refresh tokens, and build logout that actually works."
datePublished: "2025-09-24"
dateModified: "2025-09-24"
tags: ["Security", "Authentication", "API", "Backend"]
keywords: "OAuth token introspection, token revocation RFC 7009, RFC 7662, opaque token validation, logout token revocation, OAuth revoke endpoint"
faq:
  - q: "When do I need token introspection instead of JWT validation?"
    a: "Use introspection for opaque (reference) tokens where the resource server cannot verify the token locally. JWTs carry claims and a signature—validate without calling the auth server. Opaque tokens are random strings whose meaning only the auth server knows—introspection is required."
  - q: "Does revoking a refresh token also revoke the access token?"
    a: "Not automatically per RFC 7009. Revoking a refresh token prevents new access tokens from being issued. The current access token remains valid until it expires. For immediate logout, revoke both tokens explicitly or maintain a token blocklist checked on every request."
  - q: "How do I handle introspection latency in high-traffic APIs?"
    a: "Cache introspection results keyed by token hash with TTL matching remaining token lifetime (or max 60 seconds). Invalidate cache on revocation events. For JWTs, skip introspection entirely—validate locally with JWKS."
---

A user clicks "Log out" and your app deletes the token from localStorage. The token remains valid for another 14 minutes—anyone who captured it can still call your API. Token revocation (RFC 7009) tells the authorization server to invalidate a token immediately. Token introspection (RFC 7662) lets resource servers ask "is this token still active?" for opaque tokens. Together they close the gap between client-side logout and server-side enforcement.

## Token types

| Type | Format | Validation |
|------|--------|------------|
| JWT (self-contained) | `eyJhbGciOi...` | Local signature check via JWKS |
| Opaque (reference) | `a8f3b2c1d0e9...` | Introspection endpoint |
| Refresh token | Usually opaque | Revocation endpoint |

If your auth server returns JWTs, you may not need introspection for access tokens—but you still need revocation for refresh tokens.

## Token introspection (RFC 7662)

```bash
curl -X POST https://auth.example.com/oauth/introspect \
  -u "resource-server:secret" \
  -d "token=a8f3b2c1d0e9f8a7b6c5d4e3f2a1b0"
```

Response for an active token:

```json
{
  "active": true,
  "scope": "read write",
  "client_id": "mobile-app",
  "username": "michael@example.com",
  "sub": "user-42",
  "exp": 1726500000,
  "iat": 1726496400,
  "iss": "https://auth.example.com",
  "token_type": "Bearer"
}
```

Response for revoked or expired token:

```json
{ "active": false }
```

## Resource server middleware

```python
import httpx
import hashlib
import time

_introspect_cache: dict[str, tuple[dict, float]] = {}

def introspect_token(token: str) -> dict | None:
    cache_key = hashlib.sha256(token.encode()).hexdigest()
    cached = _introspect_cache.get(cache_key)
    if cached and time.time() < cached[1]:
        return cached[0] if cached[0].get("active") else None

    resp = httpx.post(
        "https://auth.example.com/oauth/introspect",
        auth=("resource-server", RESOURCE_SECRET),
        data={"token": token},
    )
    data = resp.json()
    ttl = min(60, max(0, data.get("exp", 0) - time.time()))
    _introspect_cache[cache_key] = (data, time.time() + ttl)

    return data if data.get("active") else None

@app.middleware("http")
async def auth_middleware(request, call_next):
    token = extract_bearer(request)
    if not token:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    info = introspect_token(token)
    if not info:
        return JSONResponse({"error": "invalid_token"}, status_code=401)

    request.state.user_id = info["sub"]
    request.state.scopes = info.get("scope", "").split()
    return await call_next(request)
```

## Token revocation (RFC 7009)

```bash
# Revoke access token
curl -X POST https://auth.example.com/oauth/revoke \
  -u "client-id:client-secret" \
  -d "token=ACCESS_TOKEN" \
  -d "token_type_hint=access_token"

# Revoke refresh token (prevents new access tokens)
curl -X POST https://auth.example.com/oauth/revoke \
  -u "client-id:client-secret" \
  -d "token=REFRESH_TOKEN" \
  -d "token_type_hint=refresh_token"
```

The endpoint returns `200 OK` regardless of whether the token existed—prevents token existence oracle attacks.

## Logout implementation

```javascript
async function logout(accessToken, refreshToken) {
  // Revoke both tokens server-side
  await Promise.all([
    revokeToken(accessToken, "access_token"),
    revokeToken(refreshToken, "refresh_token"),
  ]);

  // Clear client storage
  sessionStorage.removeItem("access_token");
  document.cookie = "refresh_token=; Max-Age=0; path=/auth/refresh";
}

async function revokeToken(token, hint) {
  await fetch("https://auth.example.com/oauth/revoke", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${btoa(`${CLIENT_ID}:${CLIENT_SECRET}`)}`,
    },
    body: new URLSearchParams({ token, token_type_hint: hint }),
  });
}
```

## JWT blocklist for immediate revocation

JWTs cannot be revoked without additional infrastructure. Options:

**Short TTL + no refresh:** Access tokens expire in 5 minutes. Acceptable for low-security apps.

**Token blocklist (Redis):**

```python
def is_revoked(jti: str) -> bool:
    return redis.exists(f"revoked:{jti}")

def revoke_jwt(jti: str, exp: int):
    ttl = exp - int(time.time())
    if ttl > 0:
        redis.setex(f"revoked:{jti}", ttl, "1")
```

Extract `jti` (JWT ID) claim on revocation. Check blocklist on every request. TTL matches token expiry so Redis does not grow forever.

**Introspection for JWTs:** Some providers support introspection even for JWT-format tokens, checking a server-side revocation registry.

## Introspection vs local JWT validation

| Factor | Introspection | Local JWT |
|--------|--------------|-----------|
| Latency | 5–50 ms per call (cached: ~0) | <1 ms |
| Revocation awareness | Immediate | Delayed (until expiry) |
| Network dependency | Yes | No (JWKS cache) |
| Token format | Opaque required | JWT required |

Hybrid: validate JWT locally for speed, introspect only when `jti` appears in a revocation event stream (webhook → Redis blocklist).

## Introspection vs local JWT validation

| Approach | Latency | Revocation |
|----------|---------|------------|
| Local JWT verify | ~1ms | Delayed until expiry |
| Introspection endpoint | ~20ms | Immediate |
| Short JWT + refresh | ~1ms | Refresh denied |

Use introspection for opaque tokens and high-security APIs. Cache introspection results 30–60s with revocation pub/sub invalidation.

## Common production mistakes

Teams get token introspection revocation wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

OAuth flows involving token introspection revocation leak sessions when refresh tokens are stored in localStorage, redirect URI validation is loose in staging, and token introspection is skipped for opaque bearer tokens.

## Debugging and triage workflow

When token introspection revocation misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [RFC 7662 — Token Introspection](https://www.rfc-editor.org/rfc/rfc7662) — introspection endpoint spec
- [RFC 7009 — Token Revocation](https://www.rfc-editor.org/rfc/rfc7009) — revocation endpoint spec
- [Auth0 token introspection](https://auth0.com/docs/secure/tokens/token-introspection) — implementation guide
- [Keycloak token introspection endpoint](https://www.keycloak.org/docs/latest/securing_apps/#token-introspection-endpoint) — self-hosted option
- [OAuth 2.0 Token Exchange (RFC 8693)](https://www.rfc-editor.org/rfc/rfc8693) — delegating tokens between services
