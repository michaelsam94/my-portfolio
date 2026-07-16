---
title: "OpenID Connect, Explained"
slug: "oidc-openid-connect-explained"
description: "OpenID Connect demystified: ID tokens vs access tokens, authorization code flow, discovery, claims, and how OIDC layers identity on OAuth 2.0 for modern apps."
datePublished: "2025-08-08"
dateModified: "2025-08-08"
tags: ["Security", "Authentication", "OAuth", "Web"]
keywords: "OpenID Connect explained, OIDC vs OAuth, ID token, authorization code flow, OIDC discovery"
faq:
  - q: "What is the difference between OAuth 2.0 and OpenID Connect?"
    a: "OAuth 2.0 authorizes access to resources — it answers 'can this app access my data?' OpenID Connect adds an identity layer on top: an ID token proves who the user is. OAuth alone doesn't standardize user authentication; OIDC does via ID tokens and UserInfo."
  - q: "Should you validate ID tokens or access tokens for user identity?"
    a: "Use ID tokens for identity — subject, email, name claims. Access tokens authorize API calls to resource servers. Never treat an access token as proof of identity unless it's a specialized token format your resource server validates with explicit identity claims."
  - q: "Which OIDC flow should web apps use?"
    a: "Authorization Code flow with PKCE for SPAs and mobile apps. Implicit and hybrid flows are deprecated for new applications. Confidential server-side apps use authorization code without PKCE on the client but with client secret on the token endpoint."
---

Engineering implemented "Login with Google" using OAuth 2.0 access tokens and stored the access token in localStorage as proof of session. Product asked for email and profile photo — the access token didn't include them reliably, and Google's userinfo endpoint rate-limited under load. OpenID Connect fixes this by standardizing an **ID token** (JWT) with identity claims issued alongside the access token. OIDC isn't a replacement for OAuth — it's OAuth plus a signed statement about who logged in.

## OAuth vs OIDC: complementary layers

```
┌──────────────────────────────────────────────────────────────┐
│                     OpenID Connect                           │
│  ID Token (JWT) · UserInfo endpoint · Discovery · Claims     │
├──────────────────────────────────────────────────────────────┤
│                     OAuth 2.0                                │
│  Authorization · Access Token · Refresh Token · Scopes       │
└──────────────────────────────────────────────────────────────┘
```

| Artifact | Purpose | Format | Send to |
|----------|---------|--------|---------|
| ID token | Authentication — who is the user | JWT (usually) | Client app only |
| Access token | Authorization — what can the app access | Opaque or JWT | Resource API |
| Refresh token | Obtain new tokens without re-login | Opaque | Client + token endpoint |

Request **`openid` scope** to receive an ID token. Add `profile`, `email` for standard claims.

## Authorization Code + PKCE flow

The flow every new SPA and mobile app should use:

```
  User          Client App              OIDC Provider
   │                │                         │
   │── login ──────►│                         │
   │                │── redirect + code_challenge ──►│
   │◄── login UI ───│                         │
   │── credentials ─►                         │
   │                │◄── authorization code ──│
   │                │── code + code_verifier ──►│
   │                │◄── ID token + access token │
   │◄── session ────│                         │
```

Client generates PKCE verifier/challenge before redirect:

```javascript
const verifier = generateRandomString(64);
const challenge = base64url(sha256(verifier));
sessionStorage.setItem('pkce_verifier', verifier);

window.location = `${issuer}/authorize?` + new URLSearchParams({
  client_id: CLIENT_ID,
  redirect_uri: REDIRECT_URI,
  response_type: 'code',
  scope: 'openid profile email',
  code_challenge: challenge,
  code_challenge_method: 'S256',
  state: randomState,
});
```

Token exchange (server-side or SPA with strict CSP):

```javascript
const tokenRes = await fetch(`${issuer}/token`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  body: new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: REDIRECT_URI,
    client_id: CLIENT_ID,
    code_verifier: sessionStorage.getItem('pkce_verifier'),
  }),
});
const { id_token, access_token, refresh_token } = await tokenRes.json();
```

## Validating ID tokens

Never trust an ID token without verification:

1. **Signature** — verify against provider JWKS (`/.well-known/jwks.json`)
2. **`iss`** — matches expected issuer URL
3. **`aud`** — includes your `client_id`
4. **`exp` / `iat`** — not expired, clock skew tolerance ~5 min
5. **`nonce`** — matches value sent in authorize request (prevents replay)

```python
from authlib.jose import jwt

claims = jwt.decode(
    id_token,
    jwks,
    claims_options={
        "iss": {"essential": True, "value": "https://accounts.example.com"},
        "aud": {"essential": True, "value": CLIENT_ID},
    },
)
claims.validate()
user_sub = claims["sub"]
```

Use a library — hand-rolled JWT validation misses edge cases (`alg: none`, key confusion).



**Standard claims.**

| Claim | Meaning |
|-------|---------|
| `sub` | Stable user identifier — use as primary key |
| `email` | Email (may be unverified — check `email_verified`) |
| `name`, `picture` | Profile display |
| `iss` | Issuer |
| `aud` | Audience (client ID) |
| `exp`, `iat`, `auth_time` | Expiry, issued-at, when user authenticated |

**Don't use email as primary key** — it changes, isn't unique across all providers, and may be scoped (`user+tag@gmail.com`).



**Discovery document.**

OIDC providers expose metadata at:

```
https://{issuer}/.well-known/openid-configuration
```

Returns `authorization_endpoint`, `token_endpoint`, `jwks_uri`, `userinfo_endpoint`, supported scopes and response types. Configure clients dynamically — hardcoding endpoints breaks when providers rotate URLs.

```json
{
  "issuer": "https://login.example.com",
  "authorization_endpoint": "https://login.example.com/authorize",
  "token_endpoint": "https://login.example.com/token",
  "jwks_uri": "https://login.example.com/.well-known/jwks.json",
  "response_types_supported": ["code"],
  "scopes_supported": ["openid", "profile", "email"]
}
```



**UserInfo endpoint.**

Alternative to reading claims from ID token — fetch with access token:

```bash
curl -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  https://login.example.com/userinfo
```

Use when you need fresh profile data or ID token is minimal. ID token should still drive session establishment; UserInfo supplements.



**Common providers.**

| Provider | Issuer discovery | Notes |
|----------|------------------|-------|
| Auth0 | `https://{tenant}.auth0.com/.well-known/openid-configuration` | Custom domains for production |
| Google | `https://accounts.google.com/.well-known/openid-configuration` | `openid email profile` scopes |
| Azure AD | `https://login.microsoftonline.com/{tenant}/v2.0/.well-known/openid-configuration` | Multi-tenant vs single |
| Keycloak | `https://{host}/realms/{realm}/.well-known/openid-configuration` | Self-hosted |
| Okta | `https://{domain}.okta.com/.well-known/openid-configuration` | Org authorization server |



**Session management.**

**Backend-for-frontend (BFF):** SPA has no tokens in browser storage. BFF holds refresh token in HttpOnly cookie, issues session cookie to SPA. ID token validated once at login; session ID replaces it client-side.

**Token in memory:** access/ID tokens in JS variable — lost on refresh, mitigates XSS exfiltration vs localStorage. Refresh via silent iframe or re-auth.

We moved from localStorage access tokens to BFF + rotating refresh — XSS could still act as user but couldn't exfiltrate long-lived tokens.



**OIDC pitfalls.**

- **Confusing access token for session** — access tokens expire quickly; refresh flow or server session needed
- **Skipping PKCE on public clients** — authorization code interception
- **Not validating ID token** — forged JWT if attacker substitutes token
- **Wrong `aud`** — accepting tokens issued for another client
- **Ignoring logout** — OIDC RP-initiated logout and front-channel/back-channel specs exist; implement or sessions linger at provider

Rotate signing keys gracefully: cache JWKS with `kid` lookup but refresh on signature failure in case of provider key rotation. Log authentication failures with `error`, `error_description`, and `state` — never log authorization codes or refresh tokens. For multi-tenant SaaS, map `sub` plus `iss` as composite primary key; the same person logging in via Google and email-password OIDC will have different `sub` values. Document session length policy: ID tokens expire in minutes; application sessions may last days via refresh tokens stored server-side. Compliance reviews often ask for RP-initiated logout — implement end-session endpoint redirects even if most users just close the tab. Test clock skew by advancing container time during integration tests; brittle `exp` validation breaks logins silently in VMs with drifted clocks.

## Resources

- [OpenID Connect Core 1.0 specification](https://openid.net/specs/openid-connect-core-1_0.html)
- [OAuth 2.0 for Browser-Based Apps (BCP)](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-browser-based-apps)
- [Auth0 — ID token vs access token](https://auth0.com/docs/secure/tokens/id-tokens)
- [PKCE RFC 7636](https://datatracker.ietf.org/doc/html/rfc7636)
- [OpenID Connect Discovery 1.0](https://openid.net/specs/openid-connect-discovery-1_0.html)
