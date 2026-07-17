---
title: "OIDC Token Exchange RFC 8693"
slug: "oidc-token-exchange-rfc8693"
description: "Exchange tokens across trust domains with RFC 8693 — delegation, impersonation, and service-to-service token translation."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags:
  - "Authentication"
  - "OIDC"
  - "Backend"
keywords: "RFC 8693, token exchange, oauth token exchange, delegation, impersonation, subject_token"
faq:
  - q: "When should I use token exchange instead of client credentials?"
    a: "Use token exchange when the downstream API must know which user initiated the action, not just which service is calling. Client credentials produce service identity only. Token exchange accepts a subject_token (user access token or ID token) and returns a new token scoped for a different audience — preserving user context across microservice boundaries."
  - q: "What is the difference between delegation and impersonation in token exchange?"
    a: "Delegation (no actor_token) means the calling service acts on behalf of the user with its own client identity reflected in the token. Impersonation (actor_token present) means one service assumes the user's identity entirely — the issued token represents the user as if they called directly. Impersonation is higher risk and should be restricted to tightly controlled internal services."
  - q: "Which token types can be exchanged as subject_token?"
    a: "RFC 8693 defines urn:ietf:params:oauth:token-type:access_token, id_token, and jwt as standard types. The authorization server validates the incoming token's signature, expiry, and audience before issuing the new token. Not all AS implementations accept all types — verify your IdP's supported token types in documentation."
---

Microservice architectures create a token boundary problem. A user authenticates at the edge and receives an access token scoped for the API gateway. The gateway calls a billing service, which calls a payment processor — each service expects tokens with different audiences, scopes, and lifetimes. Passing the user's original token downstream violates least-privilege (over-scoped for inner services) and often fails audience validation entirely.

**OAuth 2.0 Token Exchange** ([RFC 8693](https://datatracker.ietf.org/doc/html/rfc8693)) provides a standardized grant type for translating tokens across trust domains. Your service presents a **subject token** (and optionally an **actor token**) to the authorization server and receives a new token fit for the target resource server.

## Token exchange request format

```
POST /oauth/token HTTP/1.1
Content-Type: application/x-www-form-urlencoded
Authorization: [client authentication]

grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&subject_token=eyJhbGciOiJSUzI1NiIs...
&subject_token_type=urn:ietf:params:oauth:token-type:access_token
&audience=https://payments.example.com
&scope=payments:charge
&requested_token_type=urn:ietf:params:oauth:token-type:access_token
```

Optional actor token for impersonation:

```
&actor_token=eyJhbGciOiJSUzI1NiIs...
&actor_token_type=urn:ietf:params:oauth:token-type:access_token
```

Response:

```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIs...",
  "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
  "token_type": "Bearer",
  "expires_in": 300,
  "scope": "payments:charge"
}
```

The issued token carries the subject's identity, scoped for the requested audience — not the original token's audience.

## Delegation vs impersonation

**Delegation** — service acts on user's behalf:

```
User → Gateway (user token)
Gateway → Token Exchange (subject_token = user token, no actor_token)
       ← Downstream token (sub = user, may include client_id of gateway)
Gateway → Billing Service (downstream token)
```

The billing service knows the user initiated the action and which gateway service proxied it. Audit logs show both identities.

**Impersonation** — service fully assumes user identity:

```
Admin Service → Token Exchange (subject_token = user token, actor_token = admin service token)
             ← Token indistinguishable from user's direct token
Admin Service → User Data API (impersonation token)
```

Impersonation tokens should be visually flagged in audit systems and restricted by policy. Support and debugging tools use impersonation; routine service calls should use delegation.

## Subject token validation

The authorization server validates the subject token before exchange:

1. Signature verification against issuer JWKS
2. `exp` not passed (with clock skew tolerance)
3. Token not revoked (if introspection or revocation checking enabled)
4. Original scopes satisfy requested downstream scopes (scope narrowing, never widening)
5. Client performing exchange is authorized for the requested `audience`

Scope narrowing example: user token has `orders:read orders:write payments:read`. Exchange request for audience `payments.example.com` with `scope=payments:read` succeeds. Request for `scope=payments:write` fails if the subject token lacks that scope.

## Implementation: gateway token exchange

A Node.js API gateway exchanging tokens before proxying:

```typescript
const exchangeCache = new Map<string, { token: string; expiresAt: number }>();

async function getDownstreamToken(
  userAccessToken: string,
  audience: string,
  scope: string,
): Promise<string> {
  const cacheKey = hashToken(userAccessToken) + audience + scope;
  const cached = exchangeCache.get(cacheKey);
  if (cached && cached.expiresAt > Date.now() + 30_000) {
    return cached.token;
  }

  const resp = await fetch(`${IDP}/oauth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      ...clientAuthHeaders(), // private_key_jwt
    },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:token-exchange',
      subject_token: userAccessToken,
      subject_token_type: 'urn:ietf:params:oauth:token-type:access_token',
      audience,
      scope,
      requested_token_type: 'urn:ietf:params:oauth:token-type:access_token',
    }),
  });

  if (!resp.ok) throw new TokenExchangeError(await resp.text());
  const data = await resp.json();

  exchangeCache.set(cacheKey, {
    token: data.access_token,
    expiresAt: Date.now() + data.expires_in * 1000,
  });

  return data.access_token;
}
```

Cache exchanged tokens briefly — but never longer than the subject token's remaining lifetime. When the subject token expires, cached downstream tokens must invalidate regardless of their own `expires_in`.

## Identity propagation in issued tokens

RFC 8693 allows the AS to embed exchange context in the issued token:

- `sub` — the original subject (user)
- `client_id` or `azp` — the client that performed the exchange
- `act` claim ([RFC 8693 Section 4.1](https://datatracker.ietf.org/doc/html/rfc8693#section-4.1)) — actor claim when actor_token was present
- `may_act` — indicates who may further delegate

Example issued token payload with actor:

```json
{
  "sub": "user-uuid-1234",
  "aud": "https://payments.example.com",
  "scope": "payments:charge",
  "act": {
    "sub": "billing-service-client-id"
  },
  "iss": "https://idp.example.com"
}
```

Downstream services should log both `sub` and `act.sub` for audit trails.

## Security policy design

Token exchange is powerful and dangerous if uncontrolled. Authorization server policies should enforce:

| Policy | Purpose |
| --- | --- |
| Allowed audiences per client | Billing service can exchange for payments API, not admin API |
| Scope ceiling | Exchange cannot exceed subject token scopes |
| Impersonation whitelist | Only `support-tool` client may include actor_token |
| Rate limits | Prevent exchange endpoint abuse for token farming |
| Subject token freshness | Reject exchange if subject token older than N minutes |

Keycloak implements token exchange via fine-grained admin permissions and client policies. Auth0 supports custom token exchange via Actions. Custom AS implementations need explicit policy engines — default allow-all is unacceptable.

## Token exchange vs alternatives

**Pass-through (forwarding user token)**: Simple but violates audience isolation. Inner services receive over-privileged tokens. Fail.

**Client credentials per service call**: Service identity only — loses user context. Acceptable for batch jobs, wrong for user-initiated flows.

**Custom session-to-token translation**: Reinvents RFC 8693 without interoperability. Maintenance burden.

**On-behalf-of flow (Azure AD)**: Vendor-specific variant of token exchange. Same concept, different endpoint parameters.

Token exchange wins when you need standards-based, audience-scoped, user-context-preserving tokens across service boundaries.

## Refresh token exchange

Some IdPs allow exchanging a refresh token for a new access token with different audience — useful when a long-lived session needs periodic downstream token minting without re-authentication:

```
grant_type=urn:ietf:params:oauth:grant-type:token-exchange
&subject_token=[refresh_token]
&subject_token_type=urn:ietf:params:oauth:token-type:refresh_token
&audience=https://analytics.example.com
&scope=analytics:read
```

Treat refresh token exchange as high sensitivity — refresh tokens are long-lived credentials. Restrict to confidential backend clients.

## Error handling

Common error responses:

| Error | Meaning | Action |
| --- | --- | --- |
| `invalid_request` | Missing subject_token or audience | Fix request parameters |
| `invalid_grant` | Subject token expired or revoked | Re-authenticate user |
| `unauthorized_client` | Client not permitted to exchange | Update AS policy |
| `access_denied` | Requested scope exceeds subject scope | Reduce scope request |
| `invalid_target` | Audience not recognized | Register audience/resource |

Implement circuit breakers on exchange failures. If the IdP is down, your gateway should fail the user request cleanly rather than forwarding unvalidated tokens.

## Observability

Log every exchange with:

- Exchanging client_id
- Subject `sub` (from parsed subject token)
- Requested audience and scope
- Issued token `expires_in`
- Whether actor_token was present

Metrics: exchange rate, latency, error rate by error code, cache hit ratio. Alert on `access_denied` spikes — often indicates a scope misconfiguration after a deploy.

## Testing strategy

1. Exchange valid access token → receive audience-scoped token
2. Downstream API accepts exchanged token, rejects original token (audience isolation)
3. Expired subject token → `invalid_grant`
4. Over-scoped request → `access_denied`
5. Unauthorized client → `unauthorized_client`
6. Actor token present → issued token contains `act` claim
7. Cache invalidation when subject token expires mid-cache

## Summary

RFC 8693 token exchange solves cross-service identity propagation without sharing over-scoped user tokens or losing user context via service-only credentials. Implement strict audience and scope policies at the authorization server, cache exchanged tokens conservatively, and distinguish delegation from impersonation in your audit model. For microservice architectures behind an API gateway, token exchange is the standards-based bridge between edge authentication and least-privilege inner service access.


Reject scope escalation during exchange — requested scopes must be a subset of the subject token — and keep downstream TTLs shorter than the original access token.

Log every exchange with actor, subject, audience, and scope for audit; rate-limit the grant endpoint — it is a high-value privilege boundary.

## Exchange policy tests worth automating

Cover scope escalation rejection, expired subject tokens, untrusted clients, and audience mismatches in CI against a real IdP or a faithful mock. These four cases catch most dangerous misconfigurations before they reach production.
