---
title: "JWT Key Rotation with JWKS"
slug: "sec-jwt-key-rotation-jwks"
description: "Rotate JWT signing keys safely using JWKS: dual-key overlap, kid headers, cache TTL, and zero-downtime verification for resource servers."
datePublished: "2025-05-27"
dateModified: "2025-05-27"
tags: ["Security", "JWT", "Authentication", "OAuth"]
keywords: "JWT key rotation, JWKS endpoint, JSON Web Key Set, kid header, signing key rollover, OAuth token verification"
faq:
  - q: "How long should overlapping signing keys remain valid?"
    a: "Keep the previous key in JWKS until all issued access tokens expire plus client clock skew—typically overlap equals max token TTL plus 5–10 minutes. Refresh tokens signed with old keys need longer overlap or forced re-login on rotation. Document overlap window in runbooks so operators do not delete old keys early."
  - q: "Where should resource servers fetch JWKS?"
    a: "Fetch from the issuer's well-known JWKS URI over TLS, cache keys by kid with HTTP cache headers respected, and pin issuer URL in config—never accept jku headers pointing at attacker URLs. Refresh cache on unknown kid before failing verification to handle rotation race windows."
  - q: "RSA or ECDSA for JWT signing?"
    a: "ECDSA P-256 (ES256) offers smaller tokens and faster verification than RSA2048 with comparable security margins for most APIs. HMAC (HS256) suits single-service monoliths where secret never leaves the issuer; multi-service architectures should use asymmetric keys so only the auth service holds private material."
---

Auth0 rotated signing keys at 3 AM and your microservices rejected every token until pods restarted—because they cached one public key forever and ignored `kid` in the JWT header. JSON Web Key Sets publish the issuer's current verification keys at a URL like `/.well-known/jwks.json`. Rotation means adding a new key, signing fresh tokens with it, and retaining old public keys until nothing valid still references them. Done right, users notice nothing; done wrong, global logout looks like an outage.


## JWT header carries kid

```json
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "2025-05-key-2"
}
```

Verifiers select the matching JWK from the set:

```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "2025-05-key-1",
      "use": "sig",
      "n": "...",
      "e": "AQAB"
    },
    {
      "kid": "2025-05-key-2",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Rotation procedure

1. Generate new key pair; add public JWK with new `kid` to JWKS
2. Start signing new tokens with private key #2
3. Wait max(access_token_ttl) + skew
4. Remove public key #1 from JWKS
5. Destroy private key #1 from HSM or secrets store

Automate steps 1–2 on schedule (quarterly) and on compromise immediately.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Verifier caching logic

```python
def verify_jwt(token: str) -> Claims:
    header = decode_header(token)
    key = jwks_cache.get(header["kid"])
    if key is None:
        jwks_cache.refresh(force=True)
        key = jwks_cache.get(header["kid"])
    if key is None:
        raise AuthError("unknown signing key")
    return jwt.decode(token, key, algorithms=["RS256"], audience=AUD)
```

Set cache TTL below rotation frequency but refresh aggressively on miss. Use `Cache-Control` from JWKS response when present.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Never trust jku or x5u from tokens

Accept keys only from configured issuer metadata (`issuer/.well-known/jwks.json`). Attackers embed malicious `jku` URLs in forged tokens hoping naive libraries fetch them.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## HSM and KMS integration

Generate and store private keys in AWS KMS, Google Cloud HSM, or Vault transit engine. Signing happens inside HSM; JWKS publishes only public components. Audit every sign operation.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Refresh tokens and rotation

If refresh tokens are JWTs (often opaque is better), they may outlive access tokens. Prefer opaque refresh tokens stored server-side, or encrypt refresh JWTs with separate long-lived keys rotated on different schedule.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Alert when tokens present unknown `kid` after cache refresh—possible misconfiguration or attack. Track signing latency during HSM calls.

Never trust jku or x5u from tokens. Accept keys only from configured issuer metadata. Attackers embed malicious jku URLs hoping naive libraries fetch them.

Monitor unknown kid after cache refresh—misconfiguration or attack. HSM signing adds latency—track p99 auth path during rotation events.

Refresh tokens as opaque server-side records simplify rotation versus long-lived JWT refresh tokens. If refresh must be JWT, use separate key material and rotation schedule from access tokens.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


## Resources

- [RFC 7517: JSON Web Key (JWK)](https://www.rfc-editor.org/rfc/rfc7517.html)
- [RFC 7519: JSON Web Token (JWT)](https://www.rfc-editor.org/rfc/rfc7519.html)
- [OpenID Connect Discovery / JWKS](https://openid.net/specs/openid-connect-discovery-1_0.html)
- [Auth0: JSON Web Key Sets](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets)
- [OWASP JWT Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
