---
title: "JWT Security Best Practices"
slug: "jwt-security-best-practices"
description: "Secure JWT implementations: algorithm selection, short-lived tokens, refresh rotation, key management, claim validation, and common JWT vulnerabilities to avoid."
datePublished: "2025-09-23"
dateModified: "2025-09-23"
tags: ["Security", "Backend", "API", "Architecture"]
keywords: "JWT security best practices, JWT vulnerabilities, secure JWT implementation, refresh token rotation, JWT algorithm confusion, token validation"
faq:
  - q: "What JWT algorithm should I use?"
    a: "RS256 (RSA + SHA-256) or ES256 (ECDSA + P-256) for asymmetric signing — the verifier uses a public key, so the signing key never leaves the auth server. Never use HS256 with a shared secret in microservices (secret must be shared with every verifier). Never allow 'none' algorithm. Explicitly whitelist allowed algorithms in your JWT library."
  - q: "How long should JWT access tokens live?"
    a: "15 minutes or less for access tokens. Short lifetimes limit the damage from a stolen token. Pair with refresh tokens (7-30 days, stored securely, rotated on each use) for session continuity. For high-security applications, use 5-minute access tokens with silent refresh."
  - q: "What JWT claims must I validate?"
    a: "Validate: signature (always), exp (not expired), iss (expected issuer), aud (intended audience), nbf (not before, if present). Check that alg in the header matches your expected algorithm (prevents algorithm confusion attacks). Never trust claims without signature verification."
---

JWT libraries make it easy to decode a token and read the payload. They don't stop you from skipping signature verification, accepting the `none` algorithm, or putting a 30-day expiry on an access token. I've audited JWT implementations where the "fix" for token theft was "make the token longer" — a 4,096-bit secret doesn't help if you never verify it, if the algorithm is `none`, or if a stolen token works for 30 days. JWT security is about how you issue, validate, and rotate tokens — not which library you pick.

## Token architecture

```
Login → Auth server issues:
         ├── Access token (JWT, 15 min, RS256)
         └── Refresh token (opaque, 7 days, stored server-side)

API request → Authorization: Bearer <access_token>
             → Verify signature, exp, iss, aud
             → Extract claims → authorize

Access expired → POST /token/refresh { refresh_token }
              → New access token + rotated refresh token
              → Old refresh token invalidated
```

Two tokens, two purposes. Access tokens are self-contained and short-lived. Refresh tokens are opaque, server-tracked, and revocable.

## Algorithm selection

```python
# Auth server — sign with RS256
import jwt

private_key = load_key("auth-server-private.pem")
access_token = jwt.encode(
    {
        "sub": user.id,
        "iss": "https://auth.example.com",
        "aud": "https://api.example.com",
        "exp": datetime.utcnow() + timedelta(minutes=15),
        "iat": datetime.utcnow(),
        "scope": "read:orders write:orders",
    },
    private_key,
    algorithm="RS256",
    headers={"kid": "key-2025-09"},  # key ID for rotation
)
```

```python
# API server — verify with public key
public_key = load_key("auth-server-public.pem")
payload = jwt.decode(
    token,
    public_key,
    algorithms=["RS256"],  # EXPLICIT whitelist — never ["HS256", "RS256", "none"]
    audience="https://api.example.com",
    issuer="https://auth.example.com",
)
```

The `algorithms` parameter is critical. Without it, an attacker can switch the algorithm to `HS256` and sign with the public key (which is often available):

```python
# VULNERABLE — accepts any algorithm
payload = jwt.decode(token, public_key)  # DON'T DO THIS

# SAFE — explicit algorithm whitelist
payload = jwt.decode(token, public_key, algorithms=["RS256"])
```

## Refresh token rotation

Every refresh token use issues a new pair and invalidates the old refresh token:

```python
def refresh_tokens(refresh_token: str):
    stored = db.get_refresh_token(refresh_token)
    if not stored or stored.revoked or stored.expires_at < now():
        # Token reuse detected — revoke entire token family
        if stored and stored.revoked:
            db.revoke_token_family(stored.family_id)
            alert_security("Refresh token reuse detected", family=stored.family_id)
        raise InvalidTokenError()

    db.revoke(stored.id)

    new_refresh = db.create_refresh_token(
        user_id=stored.user_id,
        family_id=stored.family_id,
    )
    new_access = create_access_token(stored.user_id)

    return {"access_token": new_access, "refresh_token": new_refresh.token}
```

If an attacker steals a refresh token and the legitimate user also uses it, the second use detects reuse and revokes the entire family — both attacker and user must re-authenticate.

## Claims to validate

| Claim | Check | Failure action |
|-------|-------|---------------|
| `sig` | Signature valid with expected key | 401 |
| `exp` | Not expired | 401 |
| `iss` | Matches your auth server | 401 |
| `aud` | Matches your API identifier | 401 |
| `nbf` | Not before time has passed | 401 |
| `alg` (header) | Matches whitelist | 401 |
| `sub` | User exists and is active | 401 or 403 |

```python
def validate_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)

    if header.get("alg") not in ALLOWED_ALGORITHMS:
        raise InvalidAlgorithmError(header["alg"])

    if header.get("alg") == "none":
        raise InvalidAlgorithmError("none")

    kid = header.get("kid")
    public_key = key_store.get_public_key(kid)

    payload = jwt.decode(
        token, public_key,
        algorithms=ALLOWED_ALGORITHMS,
        audience=EXPECTED_AUDIENCE,
        issuer=EXPECTED_ISSUER,
        options={"require": ["exp", "iss", "aud", "sub"]},
    )

    user = db.get_user(payload["sub"])
    if not user or user.status != "active":
        raise UserInactiveError()

    return payload
```

## What NOT to put in JWTs

| Don't store | Why |
|-------------|-----|
| Passwords | Obvious |
| PII (email, phone, address) | Tokens are base64, not encrypted — readable by anyone |
| Permissions that change frequently | Can't revoke until expiry — use short TTL or server-side checks |
| Large objects | Tokens travel on every request — keep under 1 KB |
| Session state | Defeats the purpose of stateless tokens |

Store `sub` (user ID) and `scope` (permissions). Look up user details server-side.

## Key rotation

Rotate signing keys without downtime:

```python
# JWKS endpoint exposes all active public keys
@app.get("/.well-known/jwks.json")
def jwks():
    return {"keys": [key.to_jwk() for key in key_store.active_keys()]}

# Sign with latest key
access_token = jwt.encode(payload, key_store.latest_private_key, algorithm="RS256",
                          headers={"kid": key_store.latest_key_id})

# Verify tries all active public keys
def verify(token):
    kid = jwt.get_unverified_header(token)["kid"]
    public_key = key_store.get_public_key(kid)
    return jwt.decode(token, public_key, algorithms=["RS256"], ...)
```

Keep old keys active for 2x the max access token TTL (30 min if tokens are 15 min). Then retire.

## Common vulnerabilities checklist

- [ ] Algorithm whitelist enforced (not just "don't use none")
- [ ] Access tokens ≤ 15 minutes
- [ ] Refresh tokens rotated on each use
- [ ] Refresh token reuse detection with family revocation
- [ ] `iss`, `aud`, `exp` validated on every request
- [ ] No sensitive data in payload
- [ ] Keys rotated with JWKS endpoint
- [ ] Tokens transmitted only over HTTPS
- [ ] Refresh tokens in HttpOnly Secure SameSite=Strict cookies (web) or secure storage (mobile)

## Common production mistakes

Teams get jwt security best practices wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of jwt security best practices fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [RFC 8725 — JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725) — IETF security recommendations for JWT
- [Auth0 JWT Handbook](https://auth0.com/resources/ebooks/jwt-handbook) — comprehensive JWT reference
- [OWASP JWT Cheat Sheet](https://cheatsheetseries.owasp.org/cheat-sheets/JSON_Web_Token_for_Java_Cheat_Sheet.html) — common vulnerabilities and mitigations
- [JWT.io debugger](https://jwt.io/) — decode and inspect tokens (never paste production tokens)
