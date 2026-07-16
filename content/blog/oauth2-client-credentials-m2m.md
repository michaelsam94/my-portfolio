---
title: "Client Credentials for Machine-to-Machine"
slug: "oauth2-client-credentials-m2m"
description: "Implement OAuth 2.0 client credentials flow for service-to-service auth: token endpoints, scopes, credential rotation, and comparison with mTLS."
datePublished: "2025-09-18"
dateModified: "2025-09-18"
tags: ["Security", "Authentication", "API", "Backend"]
keywords: "OAuth client credentials, machine to machine authentication, M2M OAuth, service account OAuth, client credentials grant, API service auth"
faq:
  - q: "When should I use client credentials instead of API keys?"
    a: "Use client credentials when you need scoped access (read-only vs write), token expiration with automatic renewal, audit trails tied to client identity, or integration with an existing OAuth infrastructure. API keys are simpler for single-purpose internal tools with one permission level."
  - q: "Can client credentials flow access user data?"
    a: "No. Client credentials grants access on behalf of the application itself, not a user. The token represents the service account. To act on behalf of a user, use authorization code flow or token exchange (RFC 8693)."
  - q: "How do I rotate client secrets without downtime?"
    a: "Issue a new client secret while the old one remains valid for an overlap period (7–14 days). Deploy the new secret to all consuming services, verify traffic succeeds, then revoke the old secret. Automate rotation quarterly."
---

Your billing service calls the inventory API with a shared API key in an environment variable. When the key rotates, someone manually updates twelve deployment configs and hopes nothing was missed. OAuth 2.0 client credentials flow gives machine-to-machine authentication with scoped tokens, expiration, and centralized revocation—without a human user in the loop. The service authenticates as itself using a `client_id` and `client_secret`, receives a short-lived access token, and presents it on API calls.

## Flow

```
Service A                    Auth Server                Service B (API)
   |--- client_id + secret -->|                              |
   |<-- access_token ---------|                              |
   |--- GET /resources ------>|                              |
   |   Authorization: Bearer  |                              |
   |                          |<--- validate token ----------|
   |<-- response -------------|                              |
```

No browser, no redirect, no user consent screen.

## Token request

```bash
curl -X POST https://auth.example.com/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=billing-service" \
  -d "client_secret=s3cret" \
  -d "scope=inventory:read orders:write"
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "inventory:read orders:write"
}
```

## Client implementation with caching

```python
import time
import httpx

class M2MClient:
    def __init__(self, token_url, client_id, client_secret, scopes):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scopes = scopes
        self._token = None
        self._expires_at = 0

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token

        resp = httpx.post(self.token_url, data={
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scopes,
        })
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = time.time() + data["expires_in"]
        return self._token

    def request(self, method, url, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.get_token()}"
        return httpx.request(method, url, headers=headers, **kwargs)
```

Cache tokens until 60 seconds before expiry. Requesting a new token per API call wastes latency and loads the auth server.

## Scope design

```
billing-service    → inventory:read, orders:write
analytics-worker   → events:read
admin-tool         → * (avoid in production)
```

Principle of least privilege: each service gets only the scopes it needs. Audit scope grants like firewall rules.

## JWT access tokens

Many providers return JWTs as access tokens:

```json
{
  "iss": "https://auth.example.com",
  "sub": "billing-service",
  "aud": "api.example.com",
  "scope": "inventory:read orders:write",
  "exp": 1726500000,
  "iat": 1726496400
}
```

API resource servers validate locally:

```python
from jose import jwt, JWTError

def validate_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            PUBLIC_KEY,
            algorithms=["RS256"],
            audience="api.example.com",
            issuer="https://auth.example.com",
        )
    except JWTError:
        raise Unauthorized()
```

No call to the auth server per request—just signature verification.

## Credential storage

| Environment | Storage |
|-------------|---------|
| Kubernetes | Secret mounted as env var or file |
| AWS | Secrets Manager, referenced in task definition |
| CI/CD | GitHub Actions secrets, OIDC for keyless |
| Local dev | `.env` (never committed) |

Never hardcode `client_secret` in source code. Rotate quarterly.

## Client credentials vs alternatives

| Method | Scoped | Expiring | Revocable | Complexity |
|--------|--------|----------|-----------|------------|
| API key | No | No | Yes (delete key) | Low |
| Client credentials | Yes | Yes | Yes | Medium |
| mTLS | Yes (cert CN) | Yes (cert expiry) | Yes (revoke cert) | High |
| JWT (self-signed) | Yes | Yes | Hard | Medium |

Use client credentials when you already run an OAuth authorization server (Auth0, Keycloak, Okta, Cognito). Use mTLS when transport-layer identity is required. Use API keys for internal tools with one permission level.

## Auth0 / Okta example

```javascript
import fetch from "node-fetch";

async function getManagementToken() {
  const res = await fetch(`https://${DOMAIN}/oauth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      client_id: CLIENT_ID,
      client_secret: CLIENT_SECRET,
      audience: `https://${DOMAIN}/api/v2/`,
      grant_type: "client_credentials",
    }),
  });
  const { access_token } = await res.json();
  return access_token;
}
```

## Token caching and refresh

M2M tokens typically expire in 3600 seconds. Cache aggressively:

```javascript
let cachedToken = null;
let expiresAt = 0;

async function getToken() {
  if (Date.now() < expiresAt - 60_000) return cachedToken; // 60s skew buffer
  const res = await fetchToken();
  cachedToken = res.access_token;
  expiresAt = Date.now() + res.expires_in * 1000;
  return cachedToken;
}
```

Share cache per process, not per request — hammering `/oauth/token` triggers rate limits and marks your service as misconfigured in IdP dashboards.

## Scope design for service accounts

One client credential per service, scopes per capability:

```
billing-service    → billing:read billing:write
reporting-worker   → analytics:read (read-only)
admin-backfill     → admin:write (break-glass, short-lived)
```

Avoid `scope: *` on M2M clients. Rotate credentials by creating new client, deploying, revoking old — blue-green for secrets.

## Observability and audit

Log token requests without secrets:

```json
{"event":"token_issued","client_id":"billing-service","scopes":["billing:write"],"duration_ms":45}
```

Alert on:
- Token request rate 10× baseline (possible credential leak)
- 401 spike on resource server (clock skew, wrong audience)
- New client_id requesting tokens (unauthorized registration)

Pair with [API authentication JWT vs sessions](https://blog.michaelsam94.com/api-authentication-jwt-vs-sessions/) when choosing token format for M2M vs user contexts.

## Production checklist

- [ ] One client credential per service, scoped minimally
- [ ] Token cache with 60-second expiry skew buffer
- [ ] Credential rotation via blue-green client deploy
- [ ] Token request rate monitored for anomaly detection
- [ ] Client secrets in Secrets Manager, never in source

## Common production mistakes

Teams get client credentials m2m wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

OAuth flows involving client credentials m2m leak sessions when refresh tokens are stored in localStorage, redirect URI validation is loose in staging, and token introspection is skipped for opaque bearer tokens.

## Resources

- [RFC 6749 Section 4.4](https://www.rfc-editor.org/rfc/rfc6749#section-4.4) — client credentials grant spec
- [OAuth 2.0 Token Introspection (RFC 7662)](https://www.rfc-editor.org/rfc/rfc7662) — validating opaque tokens
- [Auth0 client credentials flow](https://auth0.com/docs/get-started/authentication-and-authorization-flow/client-credentials-flow) — implementation guide
- [Keycloak service accounts](https://www.keycloak.org/docs/latest/server_admin/#_service_accounts) — self-hosted M2M auth
- [AWS Cognito client credentials](https://docs.aws.amazon.com/cognito/latest/developerguide/token-endpoint.html) — managed token endpoint
