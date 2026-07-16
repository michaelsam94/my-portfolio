---
title: "JWT vs PASETO"
slug: "jwt-vs-paseto-tokens"
description: "Compare JWT and PASETO for token-based authentication: security defaults, footguns, API design, and when to choose PASETO over JWT for new projects."
datePublished: "2025-09-26"
dateModified: "2025-09-26"
tags: ["Security", "Backend", "API", "Architecture"]
keywords: "JWT vs PASETO, PASETO tokens, Platform-Agnostic Security Tokens, JWT alternatives, secure token format, PASETO v4"
faq:
  - q: "What is PASETO?"
    a: "PASETO (Platform-Agnostic Security Tokens) is a token format designed as a secure alternative to JWT. Unlike JWT, PASETO doesn't allow insecure algorithms — there's no 'none' algorithm, no algorithm confusion, and no optional signature. Every PASETO token is always signed (and optionally encrypted). The format is simpler and harder to misconfigure."
  - q: "Is PASETO better than JWT?"
    a: "PASETO has safer defaults — you can't accidentally disable signature verification or use a weak algorithm. But JWT has vastly broader library support, ecosystem tooling (OAuth 2.0, OpenID Connect), and industry adoption. For new projects where you control both issuer and verifier, PASETO reduces security footguns. For OAuth/OIDC integrations, JWT is required."
  - q: "Can PASETO replace JWT in existing OAuth 2.0 systems?"
    a: "Not directly. OAuth 2.0 and OpenID Connect are built around JWT (ID tokens, access tokens). PASETO doesn't have OIDC integration. Use PASETO for internal service-to-service tokens, session tokens, or API keys where you control the full stack. Use JWT where OAuth/OIDC interoperability is required."
---

JWT's biggest weakness isn't the format — it's the configuration space. Choose the wrong algorithm, skip a validation step, or trust the `alg` header, and your "secure" tokens are worthless. PASETO was designed by the same community that found these bugs to eliminate the footguns entirely: no algorithm negotiation, no unauthenticated modes, no base64-encoded-json-masquerading-as-secure. It's not magic — it won't fix bad key management — but it removes the misconfigurations that cause most JWT breaches.

## Side-by-side comparison

| Feature | JWT | PASETO v4 |
|---------|-----|-----------|
| Format | `header.payload.signature` (base64) | `v4.public.payload.signature` |
| Algorithms | HS256, RS256, ES256, none, ... | Ed25519 (sign), XChaCh20-Poly1305 (encrypt) |
| Unsecured mode | Yes (`alg: none`) | No — always signed |
| Algorithm confusion | Possible if not careful | Impossible — algorithm is in the prefix |
| Encryption | JWE (separate, rarely used) | Built-in (v4.local prefix) |
| Library support | Universal | Growing (PHP, Python, Go, Rust, Node) |
| OAuth/OIDC | Required | Not supported |
| Payload encoding | Base64URL JSON | Base64URL JSON (same) |
| Key size | Variable | Ed25519 = 32 bytes |

## JWT footguns that PASETO eliminates

**1. Algorithm `none`:**

```json
{"alg": "none", "typ": "JWT"}
```

Many JWT libraries accept this if not explicitly blocked. PASETO has no `alg` field — the version prefix (`v4.public`) determines the algorithm.

**2. Algorithm confusion (RS256 → HS256):**

An attacker takes the RS256 public key, sets `alg` to HS256, and signs with the public key as HMAC secret. The server verifies with the public key as HMAC secret and accepts the token. PASETO uses Ed25519 for public tokens — there's no symmetric mode to confuse with.

**3. Optional signature verification:**

```python
# JWT — dangerously easy to decode without verifying
payload = jwt.decode(token, options={"verify_signature": False})
```

PASETO has no option to skip verification. `paseto.decode()` always verifies.

## PASETO token format

```
v4.public.eyJzdWIiOi...<payload>...signature_bytes
│  │      │                        │
│  │      └── base64url JSON payload └── 64-byte Ed25519 signature
│  └── public (signed) or local (encrypted)
└── version 4 (current)
```

Two modes:
- **`v4.public`** — signed, readable by anyone (like JWT)
- **`v4.local`** — encrypted + signed, readable only with the shared secret

## PASETO in practice

Python:

```python
from pyseto import Key, Paseto

private_key = Key.new(version=4, purpose="public", key=b"\x00" * 32)
public_key = private_key.public

paseto = Paseto()
token = paseto.encode(
    private_key,
    {"sub": "user-123", "exp": "2025-09-26T15:30:00Z", "scope": "read:orders"},
    footer=b"api.example.com",
)

decoded = paseto.decode(public_key, token, footer=b"api.example.com")
payload = json.loads(decoded.payload)
```

Node.js:

```javascript
const { V4 } = require('paseto');

const key = await V4.generateKey('public', { format: 'paserk' });
const token = await V4.sign({ sub: 'user-123', exp: '2025-09-26T15:30:00Z' }, key.secretKey);
const payload = await V4.verify(token, key.publicKey);
```

No algorithm parameter. No verification options to forget.

## Encrypted tokens with v4.local

When the payload contains sensitive data:

```python
local_key = Key.new(version=4, purpose="local", key=os.urandom(32))

token = paseto.encode(
    local_key,
    {"sub": "user-123", "email": "user@example.com", "role": "admin"},
)
# → v4.local.encrypted_blob (not readable without key)
```

JWT's equivalent (JWE) exists but is rarely implemented. PASETO makes encryption a first-class operation.

## When to use which

**Use JWT when:**
- OAuth 2.0 / OpenID Connect is required
- Third-party integrations expect JWT (Auth0, Cognito, Firebase Auth)
- You need JWKS endpoints for key discovery
- Library support in your language is a priority

**Use PASETO when:**
- Internal service-to-service authentication
- Session tokens for your own API
- You want secure defaults without auditing JWT config
- New greenfield project with no OAuth dependency
- Tokens may contain sensitive claims (use v4.local)

**Use neither when:**
- Simple API key authentication suffices
- Session cookies with server-side storage work
- mTLS provides authentication (service mesh, device-to-cloud)

## Migration from JWT to PASETO

For internal tokens (not OAuth):

```python
def validate_token(token: str):
    if token.startswith("v4."):
        return validate_paseto(token)
    else:
        return validate_jwt(token)  # legacy during migration
```

Don't migrate OAuth/OIDC tokens — those must remain JWT by specification.

## The pragmatic take

JWT isn't going away. OAuth, OIDC, and every major identity provider use it. But if you're building internal API tokens and you've seen algorithm confusion, `none` acceptance, or missing expiry validation — PASETO is a reasonable choice with better defaults. For most teams: use JWT with the security checklist (algorithm whitelist, short TTL, refresh rotation). Consider PASETO for internal tokens where the format enforces security rather than relying on every developer getting the config right.

Treat production rollout as a measured change: ship with observability, validate rollback, and review metrics 24 hours after deploy — patterns that look obvious in docs fail when skipped under release pressure.

## Common production mistakes

Teams get jwt vs paseto tokens wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of jwt vs paseto tokens fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When jwt vs paseto tokens misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [PASETO specification](https://paseto.io/) — official spec and design rationale
- [pyseto Python library](https://github.com/hamano-t/paseto-py) — PASETO v4 implementation
- [paseto npm package](https://github.com/panva/paseto) — Node.js PASETO v4
- [RFC 8725 — JWT Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725) — if you stick with JWT, follow this
