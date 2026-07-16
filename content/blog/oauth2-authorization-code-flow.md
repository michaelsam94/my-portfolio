---
title: "The OAuth 2.0 Authorization Code Flow"
slug: "oauth2-authorization-code-flow"
description: "Implement the OAuth 2.0 authorization code flow with PKCE: redirects, token exchange, refresh tokens, and common security mistakes."
datePublished: "2025-09-15"
dateModified: "2025-09-15"
tags: ["Security", "Authentication", "API", "Web"]
keywords: "OAuth 2.0 authorization code flow, OAuth PKCE, authorization code grant, OAuth redirect URI, refresh token OAuth, OAuth security"
faq:
  - q: "Why is PKCE required for public clients?"
    a: "Public clients (SPAs, mobile apps) cannot store a client secret securely. PKCE replaces the secret with a per-request code verifier and challenge. Without PKCE, an attacker who intercepts the authorization code can exchange it for tokens at the token endpoint."
  - q: "What is the difference between authorization code and implicit flow?"
    a: "The implicit flow returned tokens directly in the URL fragment—exposing them to browser history and referrer headers. It is deprecated. Authorization code flow with PKCE exchanges a short-lived code server-side for tokens, keeping access tokens out of the browser URL."
  - q: "Where should I store tokens in a SPA?"
    a: "Store refresh tokens in HttpOnly, Secure, SameSite cookies set by your backend. Keep access tokens in memory (JavaScript variable) for API calls. Never store tokens in localStorage—any XSS vulnerability exposes them."
---

"We added Login with Google" usually means someone pasted a tutorial that skips PKCE, stores tokens in localStorage, and never validates the `state` parameter. The OAuth 2.0 authorization code flow is the correct pattern for web and mobile apps getting tokens from an identity provider—but only when implemented with PKCE, strict redirect URI matching, and server-side token exchange for confidential clients.

## Flow overview

```
User → App → Auth Server (login + consent)
     ← Authorization Code (redirect)
App → Auth Server (code + verifier → tokens)
     ← Access Token + Refresh Token
App → Resource Server (Bearer access_token)
```

The authorization code is single-use and short-lived (30–60 seconds). Tokens never appear in the browser URL.

## Step 1: Authorization request

```javascript
import crypto from "node:crypto";

function generatePKCE() {
  const verifier = crypto.randomBytes(32).toString("base64url");
  const challenge = crypto
    .createHash("sha256")
    .update(verifier)
    .digest("base64url");
  return { verifier, challenge };
}

const { verifier, challenge } = generatePKCE();
const state = crypto.randomBytes(16).toString("hex");

// Store verifier and state in session
session.pkceVerifier = verifier;
session.oauthState = state;

const params = new URLSearchParams({
  response_type: "code",
  client_id: process.env.OAUTH_CLIENT_ID,
  redirect_uri: "https://app.example.com/auth/callback",
  scope: "openid profile email",
  state,
  code_challenge: challenge,
  code_challenge_method: "S256",
});

res.redirect(`https://auth.example.com/authorize?${params}`);
```

## Step 2: Callback and token exchange

```javascript
app.get("/auth/callback", async (req, res) => {
  const { code, state, error } = req.query;

  if (error) return res.status(400).send(`Auth error: ${error}`);
  if (state !== req.session.oauthState) {
    return res.status(403).send("Invalid state");
  }

  const tokenRes = await fetch("https://auth.example.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: "https://app.example.com/auth/callback",
      client_id: process.env.OAUTH_CLIENT_ID,
      client_secret: process.env.OAUTH_CLIENT_SECRET,
      code_verifier: req.session.pkceVerifier,
    }),
  });

  const tokens = await tokenRes.json();
  // tokens: { access_token, refresh_token, expires_in, token_type }
});
```

## Step 3: Token storage

```javascript
// Set refresh token in HttpOnly cookie
res.cookie("refresh_token", tokens.refresh_token, {
  httpOnly: true,
  secure: true,
  sameSite: "lax",
  maxAge: 30 * 24 * 60 * 60 * 1000,
  path: "/auth/refresh",
});

// Access token in server session or return to client memory
req.session.accessToken = tokens.access_token;
res.redirect("/dashboard");
```

## Refresh flow

```javascript
app.post("/auth/refresh", async (req, res) => {
  const refreshToken = req.cookies.refresh_token;
  if (!refreshToken) return res.status(401).json({ error: "no refresh token" });

  const tokenRes = await fetch("https://auth.example.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: process.env.OAUTH_CLIENT_ID,
      client_secret: process.env.OAUTH_CLIENT_SECRET,
    }),
  });

  const tokens = await tokenRes.json();
  if (!tokenRes.ok) {
    res.clearCookie("refresh_token");
    return res.status(401).json({ error: "refresh failed" });
  }

  // Rotate refresh token if provider returns a new one
  if (tokens.refresh_token) {
    res.cookie("refresh_token", tokens.refresh_token, { /* same opts */ });
  }
  res.json({ access_token: tokens.access_token, expires_in: tokens.expires_in });
});
```

## Security checklist

| Check | Why |
|-------|-----|
| PKCE on all clients | Prevents code interception |
| Validate `state` | Prevents CSRF on callback |
| Exact redirect URI match | Prevents open redirect attacks |
| Server-side token exchange | Keeps client_secret off the browser |
| Short access token TTL (15 min) | Limits stolen token window |
| Refresh token rotation | Detects token theft |
| HTTPS everywhere | Tokens in transit are plaintext otherwise |

## Common mistakes

1. **Skipping `state` validation** — attacker tricks victim into logging into attacker's account.
2. **Wildcard redirect URIs** — `https://app.example.com/*` allows subdomain takeover exploits.
3. **Returning tokens in URL hash** — that's the deprecated implicit flow.
4. **Not handling `error` query param** — users see a blank page on consent denial.

## OIDC layer

Most providers implement OpenID Connect on top of OAuth 2.0. Add `scope: openid` and validate the `id_token` JWT:

```javascript
import { jwtVerify, createRemoteJWKSet } from "jose";

const JWKS = createRemoteJWKSet(
  new URL("https://auth.example.com/.well-known/jwks.json")
);

const { payload } = await jwtVerify(tokens.id_token, JWKS, {
  issuer: "https://auth.example.com",
  audience: process.env.OAUTH_CLIENT_ID,
});
// payload.sub is the user ID
```

## PKCE required for public clients

```javascript
const verifier = generateCodeVerifier();
const challenge = await sha256Base64Url(verifier);
// Authorize URL: code_challenge=...&code_challenge_method=S256
// Token exchange: code_verifier=verifier
```

Mobile and SPA apps must use PKCE — confidential client secret cannot be stored safely. Rotate refresh tokens on each use (OAuth 2.1 behavior).

## Common production mistakes

Teams get authorization code flow wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

OAuth flows involving authorization code flow leak sessions when refresh tokens are stored in localStorage, redirect URI validation is loose in staging, and token introspection is skipped for opaque bearer tokens.

## Debugging and triage workflow

When authorization code flow misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [RFC 6749 — OAuth 2.0](https://www.rfc-editor.org/rfc/rfc6749) — authorization framework spec
- [RFC 7636 — PKCE](https://www.rfc-editor.org/rfc/rfc7636) — proof key for code exchange
- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics) — current security guidance
- [Auth0 PKCE guide](https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow-with-pkce) — practical implementation walkthrough
- [jose JWT library](https://github.com/panva/jose) — ID token verification
