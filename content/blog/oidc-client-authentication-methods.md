---
title: "OIDC Client Authentication Methods"
slug: "oidc-client-authentication-methods"
description: "Choose and implement client authentication — client_secret, private_key_jwt, mTLS, and self_signed_tls_client_auth for confidential OAuth clients."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags:
  - "Authentication"
  - "OIDC"
  - "Backend"
keywords: "oidc client authentication, private_key_jwt, client_secret_basic, mTLS client auth, token endpoint"
faq:
  - q: "When should I use private_key_jwt instead of client_secret?"
    a: "Use private_key_jwt when client secrets in environment variables are unacceptable — mobile backends, multi-region deployments, or compliance regimes requiring non-shared credentials. The client signs a JWT with its private key; the authorization server verifies with the registered public key. Rotation becomes key-pair replacement without coordinating a shared secret across every instance."
  - q: "What is the difference between tls_client_auth and self_signed_tls_client_auth?"
    a: "tls_client_auth validates the client certificate against a CA the authorization server trusts — typical for enterprise PKI. self_signed_tls_client_auth accepts a client-generated certificate whose public key or cert fingerprint was registered at client setup time. The latter avoids enterprise CA infrastructure but requires careful cert lifecycle management."
  - q: "Can public clients use client authentication at the token endpoint?"
    a: "Public clients (SPAs, mobile apps) cannot hold confidential credentials and must not use client_secret. They authenticate the authorization request with PKCE instead. Some mobile backends use private_key_jwt as a confidential client even when the user-facing app is public — the backend holds the key, not the device."
---

The OAuth 2.0 token endpoint is where authorization codes become tokens. Before issuing them, the authorization server must answer a fundamental question: **who is requesting these tokens, and are they the same client that initiated the authorization request?** Client authentication methods define that proof. Choosing the wrong method — or implementing the right one incorrectly — is a recurring source of token leakage, compliance audit findings, and midnight pages.

This guide covers each standardized method, when to use it, and the implementation details that tutorials skip.

## The token endpoint authentication problem

During the authorization code flow, the user authenticates at the IdP and the browser returns an authorization code to the client. The code alone is insufficient proof of client identity — an attacker who intercepts the code could exchange it at the token endpoint unless the server verifies the requester.

Confidential clients prove identity at the token endpoint. Public clients rely on PKCE (code verifier) instead because they cannot store secrets. The `token_endpoint_auth_method` registered for each client determines which proof mechanism applies.

## Method overview

| Method | Credential | Transport | Typical use |
| --- | --- | --- | --- |
| `client_secret_basic` | Shared secret | HTTP Basic Auth header | Legacy server apps |
| `client_secret_post` | Shared secret | POST body parameter | Legacy, discouraged |
| `client_secret_jwt` | Shared secret as HMAC key | Signed JWT assertion | Transitional |
| `private_key_jwt` | RSA/EC private key | Signed JWT assertion | Modern confidential clients |
| `tls_client_auth` | PKI client certificate | mTLS at transport layer | Enterprise, zero-trust |
| `self_signed_tls_client_auth` | Self-signed client cert | mTLS at transport layer | Cloud-native without PKI |
| `none` | PKCE only | No client auth | Public clients (SPAs, mobile) |

Register the method in client metadata. Mismatch between registered method and actual request causes hard 401 failures that are easy to misdiagnose as scope or redirect URI problems.

## client_secret_basic and client_secret_post

The oldest methods embed a shared secret. With `client_secret_basic`, the client sends:

```
POST /oauth/token HTTP/1.1
Authorization: Basic base64(client_id:client_secret)
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&code=...&redirect_uri=...
```

With `client_secret_post`, the secret appears in the body alongside other parameters. Both are functionally equivalent in security — the secret transits in the request.

Problems in production:

- Secrets appear in application logs when frameworks log request bodies
- Load balancers and API gateways may log Authorization headers
- Secret rotation requires coordinated deploys across all instances
- No cryptographic binding to the specific request — replay of captured requests works until secret rotation

Use `client_secret_basic` only for internal tools with short-lived secrets and strict log redaction. Prefer `private_key_jwt` for anything facing compliance review.

## private_key_jwt — the modern default

`private_key_jwt` replaces shared secrets with asymmetric cryptography. The client constructs a JWT assertion, signs it with its private key, and sends it as the `client_assertion` parameter:

```
POST /oauth/token HTTP/1.1
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=SplxlOBeZQQYbYS6WxSbIA
&redirect_uri=https://app.example.com/callback
&client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer
&client_assertion=eyJhbGciOiJSUzI1NiIs...
```

Assertion claims:

```json
{
  "iss": "billing-service-client-id",
  "sub": "billing-service-client-id",
  "aud": "https://idp.example.com/oauth/token",
  "jti": "unique-nonce-1704067200",
  "exp": 1704067260,
  "iat": 1704067200
}
```

Critical validation rules the authorization server enforces (and your client must satisfy):

- `iss` and `sub` must both equal the `client_id`
- `aud` must be the token endpoint URL (exact string match — trailing slash matters)
- `jti` must be unique; servers reject replay within the assertion lifetime window
- `exp` should be short — 5 minutes maximum, 60 seconds typical
- Signature verified against the public key in the client's JWKS registration

Client-side signing in Python:

```python
import jwt
import uuid
import time

def build_client_assertion(client_id: str, token_endpoint: str, private_key: str) -> str:
    now = int(time.time())
    payload = {
        "iss": client_id,
        "sub": client_id,
        "aud": token_endpoint,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + 60,
    }
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": "2026-01"})
```

Register the public key via JWKS URI or inline JWK at client registration:

```json
{
  "client_id": "billing-service",
  "token_endpoint_auth_method": "private_key_jwt",
  "jwks_uri": "https://billing.example.com/.well-known/jwks.json"
}
```

Key rotation: publish new key with new `kid` in JWKS, deploy client using new private key, remove old key after all in-flight assertions expire.

## client_secret_jwt — HMAC variant

Similar to `private_key_jwt` but the JWT is HMAC-signed with the client secret as the key. Provides per-request uniqueness via `jti` without eliminating the shared secret problem — the secret still lives in every application instance. Useful as a stepping stone when migrating from `client_secret_basic` to `private_key_jwt`, but not a destination.

## mTLS client authentication

Transport-layer authentication binds the TLS connection itself to the client identity. Two variants exist:

**tls_client_auth**: The client presents a certificate issued by a CA the authorization server trusts. The AS extracts the subject DN or SAN and maps it to a registered client.

**self_signed_tls_client_auth**: The client generates its own certificate. At registration, the client provides either the full certificate or a SHA-256 fingerprint (`tls_client_auth_subject_dn` or `jwks` with x5c). The AS validates the presented cert matches registration.

Token request over mTLS:

```
POST /oauth/token HTTP/1.1
[TLS with client certificate presented]

grant_type=client_credentials
&scope=payments:write
```

No `client_assertion` needed — the TLS handshake is the proof. This is the strongest client authentication when your infrastructure already terminates mTLS at a service mesh or API gateway.

Implementation considerations:

- Certificate expiry monitoring — expired client certs cause silent 401 storms
- Certificate binding to token (RFC 8705) prevents token export — the access token is only usable over a connection presenting the same cert
- Reverse proxy must forward client cert info (`X-Client-Cert` or re-negotiate mTLS at the AS)

## Public clients and the none method

SPAs and mobile apps register `token_endpoint_auth_method: none`. They authenticate via PKCE:

```
POST /oauth/token

grant_type=authorization_code
&code=...
&redirect_uri=...
&client_id=mobile-app-client-id
&code_verifier=dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk
```

Never embed client secrets in mobile binaries or JavaScript bundles — they will be extracted. The BFF (Backend-for-Frontend) pattern moves token exchange to a confidential `private_key_jwt` backend while the SPA remains a public client for the authorization redirect only.

## Dynamic client registration

RFC 7591 allows clients to register programmatically. The `token_endpoint_auth_method` is set during registration and can be updated via RFC 7592 management endpoints. Automated registration pipelines should:

1. Generate key pair in a secrets manager (Vault, AWS KMS)
2. Register JWKS with the authorization server
3. Store private key reference — never the raw key in application config
4. Set metadata: `grant_types`, `response_types`, `redirect_uris`, auth method

## Authorization server validation checklist

If you operate the AS (Keycloak customization, custom OAuth server), enforce:

```python
def validate_client_auth(request, registered_client):
    method = registered_client.token_endpoint_auth_method

    if method == "private_key_jwt":
        assertion = request.form.get("client_assertion")
        assert assertion_type == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
        claims = verify_jwt(assertion, registered_client.jwks)
        assert claims["iss"] == claims["sub"] == registered_client.client_id
        assert claims["aud"] == TOKEN_ENDPOINT_URL
        assert not is_jti_reused(claims["jti"])
        mark_jti_used(claims["jti"], claims["exp"])

    elif method == "client_secret_basic":
        client_id, secret = parse_basic_auth(request.headers["Authorization"])
        assert constant_time_compare(secret, registered_client.secret)

    elif method == "none":
        assert request.form.get("code_verifier")  # PKCE required
        # reject any client_secret presence
```

Log authentication method and client_id on every token request. Alert on spikes of `invalid_client` errors after deploys — usually a JWKS propagation delay.

## Method selection decision tree

```
Is the client a browser-only SPA?
  └─ Yes → none + PKCE (+ BFF if you need refresh tokens)
  └─ No → Is mTLS available end-to-end?
       └─ Yes → tls_client_auth or self_signed_tls_client_auth
       └─ No → private_key_jwt (preferred)
            └─ Legacy constraint only → client_secret_basic with rotation automation
```

## Common mistakes

**Wrong `aud` claim**: Using the issuer URL instead of the token endpoint URL. The spec requires the token endpoint URL exactly.

**Clock skew on `exp`**: Client clocks ahead of AS clock cause immediate rejection. Sync with NTP; keep assertion lifetime under 60 seconds.

**Reused `jti`**: Copy-pasting assertions or using timestamp-only nonces collides under load. Use UUIDs.

**Mixing methods**: Sending both Basic Auth and client_assertion confuses AS implementations. Send exactly what is registered.

**Public key not yet propagated**: Deploying a new private key before the JWKS endpoint serves the matching public key causes intermittent 401s during rollout.

## Compliance and audit angles

SOC 2 and ISO 27001 auditors specifically ask how confidential client credentials are stored and rotated. `private_key_jwt` with keys in HSM or cloud KMS satisfies "credentials not stored in application configuration." Document:

- Key generation procedure
- Rotation schedule and emergency rotation runbook
- Which method each registered client uses
- Evidence that public clients never receive client secrets

## Summary

Client authentication at the OAuth token endpoint is not interchangeable — each method trades off operational complexity, security strength, and deployment constraints. Default new confidential clients to `private_key_jwt`. Reserve mTLS methods for mesh-native architectures. Keep public clients on `none` with PKCE and never ship secrets to browsers. Validate assertions with the same rigor you apply to user ID tokens, and your token endpoint becomes significantly harder to abuse with stolen authorization codes.
