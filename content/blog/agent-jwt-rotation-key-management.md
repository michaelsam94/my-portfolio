---
title: "JWT Rotation and Key Management for Multi-Tenant Agent Platforms"
slug: "agent-jwt-rotation-key-management"
description: "Operate JWT signing key rotation for agent APIs—JWKS publishing, overlap windows, asymmetric RS256 vs ES256, revocation, and zero-downtime rotation without invalidating active agent sessions."
datePublished: "2025-09-22"
dateModified: "2025-09-22"
tags: ["AI Agents", "JWT", "Security", "Key Management"]
keywords: "jwt rotation, jwks, key management, agent authentication, RS256, token introspection, OIDC, session continuity"
faq:
  - q: "How long should JWT signing keys overlap during rotation?"
    a: "Publish the new key in JWKS immediately, sign new tokens with it, and keep the old key in JWKS until all tokens signed by it expire—typically 24–72 hours for access tokens, longer if you issue refresh tokens bound to a kid. Never remove a kid from JWKS while verifiers might still see tokens referencing it."
  - q: "Should agent platform JWTs use RS256 or ES256?"
    a: "ES256 (P-256) is smaller on the wire and faster to verify at scale; RS256 is more universally supported by legacy API gateways and HSMs. Pick one family per platform, document it, and avoid mixing algs in the same JWKS endpoint without explicit kid-to-alg mapping."
  - q: "Where should signing keys live for production agent services?"
    a: "Use a managed KMS (AWS KMS, GCP Cloud KMS, Azure Key Vault) or dedicated secrets manager with HSM-backed keys. Application pods should hold verification public keys or fetch JWKS, not long-lived private PEM files on disk. Rotation should be API-driven: generate new key in KMS, update kid mapping, publish JWKS."
  - q: "How do you revoke agent access without waiting for JWT expiry?"
    a: "Short-lived access tokens (5–15 minutes) plus refresh token rotation is the baseline. For immediate revocation, maintain a session blocklist or use token introspection for high-risk operations. Agent runs invoking destructive tools should re-check session validity against a central store, not trust JWT exp alone."
---

On-call got paged because every agent API call returned 401 after a "routine" key rotation. The platform team uploaded a new RSA private key to the auth service but forgot to add the previous public key to the JWKS document. Mobile clients and edge workers still held access tokens signed with the old `kid`. For six hours, production agents could not start runs.

JWT rotation is boring until it is catastrophic. Agent platforms amplify the pain: long-lived WebSocket sessions, background workers, SDKs that cache JWKS for an hour, and multi-region deploys that drift key material. Key management is not a one-time OpenSSL exercise—it is an operational loop with overlap windows, observability, and runbooks.

## Architecture: asymmetric signing with JWKS

Agent platforms should issue **asymmetric JWTs** (RS256 or ES256). The auth service holds private keys; API gateways and agent workers verify with public keys from `/.well-known/jwks.json`.

Standard claims for agent access tokens:

| Claim | Purpose |
|-------|---------|
| `sub` | User or service principal ID |
| `tenant_id` | Multi-tenant isolation |
| `agent_scopes` | Allowed tools, models, spend caps |
| `session_id` | Revocation and audit correlation |
| `kid` | Key identifier for verification |
| `exp` / `iat` | Short TTL, clock skew tolerance |

Never embed API keys or refresh tokens inside access JWTs. Access tokens are bearer credentials—treat leakage as compromise.

Example header:

```json
{
  "alg": "ES256",
  "typ": "JWT",
  "kid": "agent-signing-2025-09-a"
}
```

## Key generation and storage

Generate keys in KMS, not on a laptop:

```bash
# AWS KMS example — create signing key
aws kms create-key \
  --key-spec ECC_NIST_P256 \
  --key-usage SIGN_VERIFY \
  --description "agent-platform-jwt-es256"
```

Map KMS key IDs to logical `kid` values in a database table:

```sql
CREATE TABLE jwt_signing_keys (
  kid              TEXT PRIMARY KEY,
  alg              TEXT NOT NULL CHECK (alg IN ('ES256', 'RS256')),
  kms_key_id       TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('active', 'retiring', 'retired')),
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  retire_after     TIMESTAMPTZ,
  retired_at       TIMESTAMPTZ
);

CREATE UNIQUE INDEX one_active_signer
  ON jwt_signing_keys ((true))
  WHERE status = 'active';
```

Only one **active** signer for new tokens. Multiple **retiring** public keys may appear in JWKS simultaneously.

Export public JWK from KMS or openssl for JWKS publication—private material never leaves HSM/KMS except during initial migration.

## JWKS endpoint contract

Publish keys at a stable URL with cache headers:

```json
{
  "keys": [
    {
      "kty": "EC",
      "crv": "P-256",
      "kid": "agent-signing-2025-09-a",
      "use": "sig",
      "alg": "ES256",
      "x": "MKBCTNIcKUSDii11ySs3526iDZ8AiTo7Tu6kPAvd7L4",
      "y": "4Eld6e_x0JG53fEq5lBP0-uGO_-28reEHbh2vaPYQLHf"
    },
    {
      "kty": "EC",
      "crv": "P-256",
      "kid": "agent-signing-2025-06-b",
      "use": "sig",
      "alg": "ES256",
      "x": "...",
      "y": "..."
    }
  ]
}
```

Verification rules for consumers:

1. Fetch JWKS if `kid` unknown (respect `Cache-Control`, max 5–15 minute staleness for agent APIs)
2. Reject tokens with missing or unknown `kid` — no fallback to "try all keys" in production (timing attacks and ambiguity)
3. Enforce `alg` matches JWK entry — reject `none` and algorithm confusion
4. Validate `iss`, `aud`, `exp` with ±60s clock skew

```typescript
import { createRemoteJWKSet, jwtVerify } from "jose";

const JWKS = createRemoteJWKSet(new URL("https://auth.example.com/.well-known/jwks.json"));

export async function verifyAgentToken(token: string) {
  const { payload, protectedHeader } = await jwtVerify(token, JWKS, {
    issuer: "https://auth.example.com",
    audience: "agent-api",
    algorithms: ["ES256"],
  });
  if (!payload.tenant_id || !payload.session_id) {
    throw new Error("missing tenant or session claims");
  }
  return { payload, kid: protectedHeader.kid };
}
```

## Rotation procedure (zero-downtime)

Document this runbook and rehearse quarterly:

**Phase 1 — Introduce new key (T+0)**

1. Create KMS key, insert row with `status = retiring` is wrong — use `active` for new, mark old as `retiring`
2. Actually: new key `status = active` for signing; previous `active` → `retiring`
3. Publish both public keys in JWKS immediately
4. New tokens get new `kid`; old tokens still verify

**Phase 2 — Overlap window (T+0 to T+max_token_ttl)**

5. Monitor `jwt.verify.failure` grouped by `kid`
6. Do not remove retiring key until `now > last_token_iat + max_access_ttl + skew_buffer`

**Phase 3 — Decommission (T+overlap)**

7. Remove retiring public key from JWKS
8. Mark DB row `retired`, disable KMS key (don't delete—audit retention)

Automate overlap calculation:

```python
def can_retire_key(kid: str, max_access_ttl_seconds: int, buffer: int = 3600) -> bool:
    last_used = db.query(
        "SELECT max(iat) FROM issued_tokens WHERE signing_kid = %s", kid
    )
    if last_used is None:
        return True
    return time.time() > last_used + max_access_ttl_seconds + buffer
```

## Refresh tokens and session binding

Agent UIs keep sessions alive across access token expiry. Use **rotating refresh tokens** stored server-side:

```sql
CREATE TABLE refresh_sessions (
  session_id       UUID PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  user_id          TEXT NOT NULL,
  token_hash       TEXT NOT NULL,
  family_id        UUID NOT NULL,
  revoked          BOOLEAN NOT NULL DEFAULT false,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_used_at     TIMESTAMPTZ
);
```

On refresh: issue new access JWT with current active `kid`, rotate refresh token hash, detect reuse (revoke entire `family_id` on mismatch). This contains theft without long-lived JWTs.

## Emergency revocation

Short TTL access tokens limit blast radius. For immediate kill:

```typescript
async function assertSessionActive(sessionId: string, tenantId: string): Promise<void> {
  const session = await redis.get(`session:${tenantId}:${sessionId}`);
  if (session === "revoked") throw new UnauthorizedError("session_revoked");
}
```

Call `assertSessionActive` at:

- Agent run creation
- Tool invocations with side effects
- Spend threshold crossings

Do not hit Redis on every read-only poll—balance cost vs risk.

## Multi-region consistency

JWKS must be identical in all regions within seconds of rotation. Options:

1. **Single source of truth** — S3/GCS object with CloudFront, short TTL
2. **Replicated config service** — push JWKS to all clusters before switching active signer
3. **GitOps** — commit JWKS JSON, deploy via pipeline (slower but auditable)

Never rotate in us-east-1 first and us-west-2 an hour later while both sign tokens.

## Monitoring and alerts

Track:

- `jwt.sign.kid` — distribution should shift gradually during rotation
- `jwt.verify.failure` by reason (`unknown_kid`, `expired`, `bad_sig`, `wrong_aud`)
- `jwks.fetch.error_rate` — spikes cause cascading 401s
- `refresh.reuse_detected` — possible token theft

Alert when `unknown_kid` exceeds baseline during overlap—it may mean JWKS publish lag or a rogue signer.

## Compliance and audit

Log key lifecycle events immutably: created, activated, retiring, retired. Tie `kid` to change ticket. Regulators and enterprise customers ask "when did this key exist and who approved rotation?"

Annual rotation is a minimum; some teams rotate quarterly or on personnel changes with HSM access. Document RTO for compromised key: activate break-glass key, revoke sessions, publish emergency JWKS within 15 minutes.

## Testing rotation in CI

Run integration tests that simulate overlap:

```typescript
describe("JWT rotation overlap", () => {
  it("verifies tokens from retiring and active keys", async () => {
    const oldToken = await signTestToken({ kid: "retiring-kid" });
    const newToken = await signTestToken({ kid: "active-kid" });
    await expect(verifyAgentToken(oldToken)).resolves.toBeDefined();
    await expect(verifyAgentToken(newToken)).resolves.toBeDefined();
  });
});
```

Schedule a staging rotation game day monthly—engineers should not learn JWKS on production incident #1.

## The takeaway

JWT rotation for agent platforms is JWKS publishing plus disciplined overlap: one active signer, retiring keys until tokens expire, KMS-backed private material, and session revocation for emergencies. Automate the runbook, monitor verify failures by `kid`, and rehearse rotation before a compromised key forces you to learn under fire.

## Resources

- [RFC 7517 — JSON Web Key (JWK)](https://datatracker.ietf.org/doc/html/rfc7517)
- [RFC 8725 — JSON Web Token Best Current Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [Auth0 — JSON Web Key Sets documentation](https://auth0.com/docs/secure/tokens/json-web-tokens/json-web-key-sets)
- [jose — JavaScript JWT/JWKS library](https://github.com/panva/jose)
- [NIST SP 800-57 — Key management recommendations](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
