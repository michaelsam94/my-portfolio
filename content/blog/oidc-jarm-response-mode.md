---
title: "OIDC JARM Response Mode"
slug: "oidc-jarm-response-mode"
description: "Use JWT Secured Authorization Response Mode (JARM) to sign and optionally encrypt authorization responses instead of passing tokens in query strings."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags:
  - "Authentication"
  - "OIDC"
  - "Backend"
keywords: "JARM, jwt secured authorization response, oidc response mode, authorization response jwt, query tampering"
faq:
  - q: "What problem does JARM solve that PKCE alone does not?"
    a: "PKCE protects the authorization code from interception during exchange. JARM protects the authorization response itself — the code, state, and error parameters returned in the redirect. Without JARM, an attacker who can observe or modify query parameters (compromised proxy, open redirect adjacent to your callback) can tamper with error codes or inject parameters. JARM wraps the entire response in a signed JWT the client verifies before processing."
  - q: "Should I use signed-only or signed-and-encrypted JARM responses?"
    a: "Signed-only (response mode jwt) suffices when the authorization response transits over TLS and you need integrity verification. Add encryption (response mode jwt with encrypted response) when responses pass through intermediaries that should not read authorization codes — high-assurance financial flows or when regulations require payload confidentiality beyond transport encryption."
  - q: "How does JARM interact with PAR and the authorization code flow?"
    a: "JARM is orthogonal to PAR. PAR pushes authorization request parameters to the server beforehand; JARM secures the response on the way back. Production deployments commonly combine both: PAR eliminates large request URLs, JARM eliminates tamperable response query strings. The client registers supported response modes and the AS returns a response JWT instead of bare query parameters."
---

Authorization redirects are the most exposed moment in OAuth. The browser bounces from your application to the identity provider and back, carrying an authorization code, state parameter, and sometimes error details in the URL query string. Any intermediary — a corporate proxy, a browser extension, referrer headers leaking to third parties — can read those parameters. Worse, a manipulated response can trick client-side code into accepting a forged error or substituting parameters before your server-side token exchange runs.

**JWT Secured Authorization Response Mode (JARM)**, defined in [FAPI 2.0 Part 2](https://openid.net/specs/openid-financial-api-jarm.html), replaces cleartext query parameters with a signed (and optionally encrypted) JWT. The client verifies issuer signature and claims before extracting the authorization code. This article explains the mechanics, response mode values, and how to implement JARM without breaking existing redirect handlers.

## Cleartext redirects and their weaknesses

Standard authorization code flow redirect:

```
HTTP/1.1 302 Found
Location: https://app.example.com/callback?code=SplxlOBeZQQYbYS6WxSbIA&state=xyz123
```

Problems:

- **Query string logging**: Web servers, CDNs, and browser history persist query parameters
- **Referrer leakage**: Subsequent navigation may leak the full callback URL
- **Parameter injection**: If the client parses query strings naively, extra parameters from an attacker-controlled redirect can merge with legitimate ones
- **Error ambiguity**: `error=access_denied` in the URL is indistinguishable from a legitimate IdP response without out-of-band verification

PKCE protects the code exchange step but does not sign the redirect itself. JARM closes that gap.

## JARM response modes

Register supported modes in client metadata via `authorization_signed_response_alg` and `authorization_encrypted_response_alg`:

| Response mode | Response delivery | Contents |
| --- | --- | --- |
| `query.jwt` | `?response=eyJ...` | Signed JWT in query |
| `fragment.jwt` | `#response=eyJ...` | Signed JWT in fragment |
| `form_post.jwt` | HTML form POST body | Signed JWT in hidden field |
| `query.jwt` + encryption | Same, encrypted JWT | Signed then encrypted |

The `response` parameter contains the JWT. All other OAuth/OIDC response parameters (`code`, `state`, `error`) move **inside** the JWT payload — they no longer appear as separate query parameters.

Example authorization request with JARM:

```
GET /authorize?
  response_type=code
  &client_id=billing-app
  &redirect_uri=https://app.example.com/callback
  &scope=openid%20profile
  &state=xyz123
  &nonce=abc456
  &response_mode=query.jwt
  &code_challenge=...
  &code_challenge_method=S256
```

Example redirect response:

```
HTTP/1.1 302 Found
Location: https://app.example.com/callback?response=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImlkcC1zaWduaW5nLWtleSJ9...
```

## Authorization response JWT structure

Signed payload claims:

```json
{
  "iss": "https://idp.example.com",
  "aud": "billing-app",
  "exp": 1704067260,
  "iat": 1704067200,
  "code": "SplxlOBeZQQYbYS6WxSbIA",
  "state": "xyz123"
}
```

Error responses embed OAuth error fields inside the JWT:

```json
{
  "iss": "https://idp.example.com",
  "aud": "billing-app",
  "exp": 1704067260,
  "iat": 1704067200,
  "error": "access_denied",
  "error_description": "User cancelled login",
  "state": "xyz123"
}
```

Client validation steps:

1. Parse JWT from `response` parameter
2. Verify signature using IdP JWKS (`iss` must match registered issuer)
3. Verify `aud` matches your `client_id`
4. Verify `exp` has not passed (allow small clock skew)
5. Extract `code`/`error` and `state` from payload — ignore any duplicate query parameters outside the JWT

```typescript
async function handleCallback(url: URL): Promise<AuthResult> {
  const responseJwt = url.searchParams.get('response');
  if (!responseJwt) throw new Error('Missing JARM response');

  const payload = await verifyJwt(responseJwt, {
    issuer: IDP_ISSUER,
    audience: CLIENT_ID,
    algorithms: ['RS256', 'PS256'],
  });

  // Defense in depth: reject if cleartext code also present
  if (url.searchParams.has('code')) {
    throw new Error('Ambiguous response: code outside JWT');
  }

  const state = payload.state as string;
  if (state !== expectedState) throw new Error('State mismatch');

  if (payload.error) {
    return { type: 'error', error: payload.error as string };
  }

  return { type: 'success', code: payload.code as string };
}
```

## Encryption layer

For `authorization_encrypted_response_alg` (typically `RSA-OAEP` with `A256GCM`), the IdP encrypts the signed JWT to the client's registered public key. Only the confidential client can decrypt — useful when even the authorization code must remain hidden from browser JavaScript (hybrid flows) or logging infrastructure.

Registration:

```json
{
  "client_id": "billing-app",
  "authorization_signed_response_alg": "PS256",
  "authorization_encrypted_response_alg": "RSA-OAEP-256",
  "jwks": {
    "keys": [{
      "kty": "RSA",
      "kid": "enc-2026-01",
      "use": "enc",
      "n": "...",
      "e": "AQAB"
    }]
  }
}
```

Processing order: IdP signs payload → encrypts signed JWT → returns in `response` parameter. Client decrypts → verifies signature → reads claims.

## form_post.jwt for front-channel security

`query.jwt` still exposes the JWT in server access logs if the callback endpoint logs full URLs. `form_post.jwt` delivers the response via auto-submitting HTML form — the JWT transits in POST body, not query string:

```html
<html><body onload="document.forms[0].submit()">
<form method="post" action="https://app.example.com/callback">
  <input type="hidden" name="response" value="eyJ..."/>
</form>
</body></html>
```

Your callback handler reads `response` from POST body instead of query. Combine with CSRF protection on the callback endpoint since POST requests are forgeable without state validation inside the JWT.

## JARM with PAR

Pushed Authorization Requests (PAR) and JARM compose cleanly:

1. Client pushes authorization request to PAR endpoint → receives `request_uri`
2. Browser opens `/authorize?client_id=...&request_uri=urn:ietf:params:oauth:request_uri:...`
3. IdP returns JARM-wrapped response

The large parameter set lives server-side (PAR); the response integrity is JWT-protected (JARM). FAPI 2.0 security profiles require both for high-assurance clients.

## IdP configuration

Keycloak, Auth0, and Okta support JARM with varying defaults:

- **Keycloak**: Enable FAPI profiles per client; set `authorization.response.mode` attributes
- **Auth0**: JARM available for FAPI-compliant applications in enterprise tiers
- **Custom AS**: Implement response mode negotiation — if client registers `authorization_signed_response_alg`, return JWT responses

Authorization server signing key rotation follows the same JWKS pattern as ID token signing. Clients must refresh JWKS periodically and honor `kid` in JWT headers.

## Migration from standard redirects

Roll out incrementally:

1. Register JARM algorithms in client metadata alongside existing redirect URIs
2. Add `response_mode=query.jwt` to authorization requests from new app versions only
3. Callback handler accepts both cleartext and JARM responses during transition
4. Remove cleartext fallback after all client versions support JARM

Dual-mode callback pseudocode:

```typescript
function parseAuthorizationResponse(url: URL, body: FormData | null) {
  const jwt = url.searchParams.get('response')
    ?? body?.get('response')?.toString();

  if (jwt) return parseJarmResponse(jwt);

  // Legacy path — deprecate after migration
  return {
    code: url.searchParams.get('code'),
    state: url.searchParams.get('state'),
    error: url.searchParams.get('error'),
  };
}
```

## Security analysis

**What JARM protects**: Response integrity and authenticity. An attacker cannot forge a successful authorization response without the IdP private key.

**What JARM does not protect**: Phishing (user enters credentials on fake IdP site), authorization code interception if PKCE is absent, token endpoint attacks.

**JWT in browser history**: `query.jwt` still stores the JWT in history — the code is inside the JWT, not cleartext, but the JWT itself is bearer-equivalent until expiry. Prefer `form_post.jwt` or ensure JWT `exp` is very short (minutes).

**Algorithm confusion**: Accept only explicitly registered algorithms. Reject `none` and unexpected algs during JWKS verification.

## Testing checklist

- Valid signed response extracts code and state correctly
- Tampered JWT signature rejected
- Expired JWT rejected
- Wrong `aud` rejected
- Error responses inside JWT parsed correctly
- Cleartext `code` parameter alongside JWT rejected (parameter injection)
- Encrypted responses decrypt and verify when encryption enabled
- JWKS rotation: new `kid` works without client deploy

## Summary

JARM transforms OAuth authorization redirects from tamperable query strings into verifiable JWTs. It complements PKCE and PAR rather than replacing them. Implement response JWT verification on the client before trusting any authorization code, prefer `form_post.jwt` when query logging is a concern, and add encryption when authorization codes require confidentiality beyond TLS. For regulated or high-value applications, JARM is the difference between hoping redirect parameters were not modified and knowing they were not.


Validate state from inside the signed JWT claims, not only from the outer query string, so a tampered outer state cannot slip past verification.
