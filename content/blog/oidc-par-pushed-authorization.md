---
title: "OIDC PAR Pushed Authorization"
slug: "oidc-par-pushed-authorization"
description: "Push authorization request parameters to the server with PAR — shorter URLs, request integrity, and protection against request tampering in the browser."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags:
  - "Authentication"
  - "OIDC"
  - "Backend"
keywords: "PAR, pushed authorization request, oauth request_uri, authorization request integrity, FAPI"
faq:
  - q: "Why push authorization parameters instead of sending them in the browser URL?"
    a: "Long authorization URLs exceed browser and proxy limits, expose sensitive parameters (acr_values, login_hint) to referrer headers and server logs, and allow parameter tampering in the browser before the redirect reaches the IdP. PAR sends parameters directly from your backend to the authorization server, returning a short request_uri reference the browser uses instead."
  - q: "How long is a PAR request_uri valid?"
    a: "The authorization server assigns expiry — typically 30 to 90 seconds, sometimes up to 600 seconds depending on configuration. The browser must reach /authorize with the request_uri before expiry. Your backend should push immediately before redirecting the user, not minutes ahead."
  - q: "Does PAR replace PKCE or JARM?"
    a: "No. PAR secures the outbound authorization request. PKCE still protects the authorization code exchange. JARM still secures the inbound authorization response. FAPI 2.0 profiles use all three together — they address different legs of the flow."
---

OAuth authorization requests can grow unwieldy. A financial API client might send `scope`, `acr_values`, `claims`, `authorization_details`, PKCE challenge, nonce, state, and custom parameters — easily exceeding 2,000 characters. Browser URL limits, CDN query string caps, and corporate proxy rules truncate or reject these requests silently. Even when the URL fits, every parameter is visible in browser history, referrer headers, and web server access logs.

**Pushed Authorization Requests (PAR)**, standardized in [RFC 9126](https://datatracker.ietf.org/doc/html/rfc9126), inverts the delivery model. Your backend POSTs the full authorization request to the authorization server's PAR endpoint. The server stores it, returns a `request_uri` handle, and the browser opens a minimal `/authorize` URL referencing that handle.

## Standard flow vs PAR flow

**Standard flow** — parameters travel through the browser:

```
Browser → GET /authorize?client_id=...&scope=...&code_challenge=...&[50 more params]
```

**PAR flow** — parameters travel server-to-server:

```
Backend → POST /oauth/par (authenticated)
       ← { "request_uri": "urn:ietf:params:oauth:request_uri:abc123", "expires_in": 60 }

Browser → GET /authorize?client_id=...&request_uri=urn:ietf:params:oauth:request_uri:abc123
```

The browser never sees the full parameter set.

## PAR endpoint request

POST to the PAR endpoint (discovered via `pushed_authorization_request_endpoint` in OpenID Provider Metadata):

```
POST /oauth/par HTTP/1.1
Host: idp.example.com
Content-Type: application/x-www-form-urlencoded
Authorization: [client authentication — private_key_jwt preferred]

response_type=code
&client_id=billing-app
&redirect_uri=https://app.example.com/callback
&scope=openid%20profile%20payments:read
&state=c7f8a9b2e1d04f6a8b3c2d1e0f9a8b7c
&nonce=n-0S6_WzA2Mj
&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
&code_challenge_method=S256
&acr_values=urn:mace:incommon:iap:silver
&claims={"userinfo":{"email":{"essential":true}}}
```

Successful response:

```json
{
  "request_uri": "urn:ietf:params:oauth:request_uri:bwc4JK-ESC0w8daf191hhrL20",
  "expires_in": 60
}
```

The `request_uri` is single-use and short-lived. The authorization server rejects reuse and expired handles.

## Client authentication requirement

PAR endpoints require authenticated clients. Acceptable methods mirror the token endpoint: `private_key_jwt`, `tls_client_auth`, or `client_secret_basic`. Public clients cannot push requests — this is intentional. The push must originate from your backend where credentials are safe.

Python example pushing a PAR request:

```python
import httpx
import secrets

async def push_authorization_request(client_assertion: str) -> str:
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = pkce_challenge(code_verifier)

    # Store state and code_verifier in session before redirect
    await session_store.set(state, {"code_verifier": code_verifier})

    resp = await httpx.AsyncClient().post(
        f"{IDP_BASE}/oauth/par",
        data={
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": "openid profile",
            "state": state,
            "nonce": secrets.token_urlsafe(16),
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        },
        headers={"Authorization": f"Bearer {client_assertion}"},
        # Or use client_assertion in body for private_key_jwt
    )
    resp.raise_for_status()
    return resp.json()["request_uri"]
```

Then redirect the browser:

```python
request_uri = await push_authorization_request(assertion)
redirect_url = f"{IDP_BASE}/authorize?client_id={CLIENT_ID}&request_uri={request_uri}"
return RedirectResponse(redirect_url)
```

## Request object alternative

PAR accepts either form-encoded parameters or a signed **Request Object** JWT:

```
POST /oauth/par

request=eyJhbGciOiPS256...  (signed JWT containing all auth params)
&client_id=billing-app
&client_assertion=...
```

The Request Object JWT includes standard claims (`client_id`, `redirect_uri`, `scope`, etc.) plus `iss` (client_id) and `aud` (authorization server issuer). The AS verifies the client signature on the Request Object — providing end-to-end integrity from client backend to AS storage.

Request Object payload example:

```json
{
  "iss": "billing-app",
  "aud": "https://idp.example.com",
  "response_type": "code",
  "client_id": "billing-app",
  "redirect_uri": "https://app.example.com/callback",
  "scope": "openid payments:read",
  "state": "c7f8a9b2...",
  "nonce": "n-0S6_WzA2Mj",
  "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
  "code_challenge_method": "S256"
}
```

Signed Request Objects prevent the AS from accepting tampered parameters even if the PAR POST is somehow intercepted.

## Authorization endpoint with request_uri

The browser-facing authorize call is deliberately minimal:

```
GET /authorize?
  client_id=billing-app
  &request_uri=urn:ietf:params:oauth:request_uri:bwc4JK-ESC0w8daf191hhrL20
```

The AS looks up stored parameters by `request_uri`. Additional query parameters in the browser request are ignored or cause errors — the stored request is authoritative. This prevents a user or attacker from modifying `scope` or `redirect_uri` in the browser address bar after your backend pushed the original request.

## Expiry and timing constraints

PAR handles expire quickly. Failure modes:

| Symptom | Cause | Fix |
| --- | --- | --- |
| `invalid_request_uri` | Handle expired | Push and redirect in same user action; no pre-staging |
| `invalid_request_uri` | Handle already used | Browser back button re-submitted old URI |
| Slow redirect | User paused on interstitial | Show loading page; push on button click, not page load |

Do not cache `request_uri` values. Generate fresh on every login attempt.

## Combining PAR with JARM

FAPI 2.0 Baseline profile requires both:

1. Backend pushes authorization request (PAR)
2. AS returns signed authorization response JWT (JARM)

The push protects the outbound leg; JARM protects the inbound leg. Together they eliminate cleartext OAuth parameters from both directions of the front-channel redirect.

Client metadata registration:

```json
{
  "require_pushed_authorization_requests": true,
  "authorization_signed_response_alg": "PS256",
  "token_endpoint_auth_method": "private_key_jwt"
}
```

When `require_pushed_authorization_requests` is true, the AS rejects direct `/authorize` calls with inline parameters for that client.

## IdP support and discovery

Verify AS capabilities:

```bash
curl -s https://idp.example.com/.well-known/openid-configuration | jq '{
  par: .pushed_authorization_request_endpoint,
  require_par: .require_pushed_authorization_requests
}'
```

Keycloak enables PAR per client via advanced settings. Auth0 supports PAR for FAPI-compliant applications. If your IdP lacks PAR, a reverse proxy cannot fully substitute — the AS must store and resolve `request_uri` handles.

## Operational monitoring

Metrics to track:

- PAR push latency (p95 should stay under 200ms — it blocks user redirect)
- PAR push failure rate (client auth errors, AS downtime)
- `invalid_request_uri` rate at authorize endpoint (expiry tuning signal)
- Ratio of PAR pushes to successful token exchanges (drop-off detection)

Log PAR pushes with `client_id`, parameter hash (not raw PII from `login_hint`), and `request_uri` prefix. Never log full authorization parameters containing PII.

## BFF pattern integration

Single-page applications should never hold client credentials. The Backend-for-Frontend handles PAR:

```
SPA click "Login"
  → POST /api/auth/login (to your BFF)
  → BFF pushes PAR, stores state in HttpOnly cookie
  → BFF returns redirect URL to SPA
  → SPA sets window.location
  → Callback hits BFF /api/auth/callback
  → BFF exchanges code with private_key_jwt
  → BFF sets session cookie
```

The SPA never touches OAuth parameters, PAR credentials, or authorization codes.

## Common implementation mistakes

**Pushing too early**: Pre-generating `request_uri` on page load wastes handles and increases expiry failures when users hesitate before clicking login.

**Missing client authentication**: PAR without auth is rejected — ensure `private_key_jwt` assertion accompanies every push.

**Parameter mismatch**: `client_id` in the browser authorize URL must match the pushed request. Mismatch causes opaque AS errors.

**Assuming PAR replaces server-side state validation**: Still validate `state` on callback. PAR protects request parameters, not your session binding.

**Oversized pushed requests**: PAR removes URL length limits but AS storage may cap request size (typically 8KB–64KB). Split complex `authorization_details` across multiple flows if needed.

## Enterprise rollout checklist

Before enabling PAR in production, validate each item:

1. Authorization server advertises `pushed_authorization_request_endpoint` in discovery metadata
2. Client credentials for PAR push use `private_key_jwt` or mTLS — not embedded secrets in frontend code
3. Push endpoint latency stays under 200ms p95 from all deployment regions
4. `request_uri` expiry aligns with UX — push on button click, not page load
5. Callback handler validates `state` independently of PAR (PAR secures outbound params, not session binding)
6. Load test concurrent login bursts — PAR endpoint becomes synchronous dependency for every authentication
7. Audit logs capture PAR push events with client_id and request hash (not raw PII from login_hint)

Roll out behind a feature flag: percentage of login flows use PAR while others use standard authorize URLs. Compare error rates and latency before full cutover.

## Summary

Pushed Authorization Requests move OAuth authorization parameters off the browser wire and into authenticated server-to-server communication. The result is shorter redirect URLs, tamper-resistant request parameters, and cleaner separation between public frontends and confidential backends. Pair PAR with PKCE for code exchange protection and JARM for response integrity when building high-assurance OIDC integrations. Push immediately before redirect, authenticate every push, and treat `request_uri` handles as single-use, short-lived resources.
