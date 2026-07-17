---
title: "AI Agents: Nonce Expiry Validation"
slug: "agent-nonce-expiry-validation"
description: "Design nonce stores, TTL boundaries, and clock-skew tolerance so agent OAuth flows and signed tool requests resist replay without rejecting legitimate retries."
datePublished: "2025-09-20"
dateModified: "2025-09-20"
tags: ["AI", "Agent", "Nonce"]
keywords: "nonce validation, replay attack prevention, OAuth state parameter, agent authentication, Redis nonce store, clock skew"
faq:
  - q: "How long should a nonce remain valid for agent OAuth callbacks?"
    a: "Short—typically 10 to 15 minutes for interactive user consent flows. The nonce covers the window between redirecting the user to an IdP and receiving the callback. Longer TTLs increase replay surface; shorter TTLs frustrate users who pause on the consent screen."
  - q: "Should nonce validation fail open if the Redis store is unavailable?"
    a: "Never for write operations that mutate state or exfiltrate data. Fail closed with a 503 and retry-after header. Read-only health endpoints may fail open depending on risk appetite, but agent tool execution should treat nonce store outage as authentication infrastructure down."
  - q: "How do you handle duplicate requests from client retries?"
    a: "Separate idempotency keys from nonces. Idempotency keys live longer and return cached responses for safe retries. Nonces are single-use within a short TTL—once consumed, the same value must be rejected even if the original request succeeded."
  - q: "Does clock skew between agent pods break expiry checks?"
    a: "It can if you compare wall clocks naively. Store absolute expiry timestamps computed server-side at issuance, validate against the auth service's synchronized clock (NTP/chrony), and allow a small negative skew window—usually 30 seconds—for consumed-at comparison only, not for extending TTL."
---
Security replayed a captured tool-invocation request from Tuesday and it executed again on Thursday because nobody had wired nonce expiry into the agent gateway. The engineer who built auth assumed TLS and JWT `exp` were enough. They are not—`exp` proves the token was valid when signed, not that this specific request has not already been submitted. Nonce expiry validation closes that gap for OAuth state parameters, signed webhooks, and one-time agent action tokens.

## What a nonce is doing in agent systems

A **nonce** (number used once) binds a single HTTP request—or message—to a prior authorization step. Common agent touchpoints:

- **OAuth/OIDC login** — `state` and sometimes `nonce` in the authorization redirect prevent CSRF and token injection.
- **Signed tool webhooks** — HMAC-signed callbacks from SaaS integrations include a nonce header to block replay.
- **Human-in-the-loop approvals** — email or Slack approve links carry a nonce tied to one pending action.
- **Cross-service agent commands** — orchestrator signs `{action, nonce, exp}` payloads workers verify before side effects.

Each use case shares requirements: generate unpredictably, store until consumed or expired, reject duplicates, and expire aggressively.

## Threat model sketch

| Attacker capability | Without nonce expiry | With nonce expiry |
|--------------------|----------------------|-------------------|
| Replay captured HTTPS request | Succeeds until token revoked | Fails after first use or TTL |
| Brute-force nonce | Possible if entropy low | Rate-limited lookup + 128-bit min |
| Race two parallel replays | Both may succeed | Atomic consume prevents double win |
| Delay delivery past TTL | Old request still valid | Rejected at validation |

JWT access tokens alone fail the first row if the token remains valid and the operation is idempotent-looking to the server—`POST /agents/run` is not always safely repeatable.

## Issuing nonces with server-side expiry

Generate with cryptographic randomness; never UUID v4 alone if you need 128 bits—use `crypto.randomBytes`:

```typescript
import { randomBytes } from "node:crypto";

function issueNonce(ttlSeconds: number): { nonce: string; expiresAt: Date } {
  const nonce = randomBytes(32).toString("base64url");
  const expiresAt = new Date(Date.now() + ttlSeconds * 1000);
  return { nonce, expiresAt };
}
```

Persist atomically:

```typescript
async function storeNonce(
  redis: Redis,
  namespace: string,
  nonce: string,
  expiresAt: Date,
  metadata: Record<string, string>
): Promise<void> {
  const key = `nonce:${namespace}:${nonce}`;
  const ttlMs = expiresAt.getTime() - Date.now();
  if (ttlMs <= 0) throw new Error("expiry must be in the future");
  await redis.set(key, JSON.stringify(metadata), "PX", ttlMs, "NX");
}
```

`NX` ensures collision retry if astronomically unlikely duplicate occurs.

## Validation: consume once, fail loudly

Validation must be **atomic read-and-delete** (or set-to-consumed flag in a transaction):

```typescript
type NonceResult =
  | { ok: true; metadata: Record<string, string> }
  | { ok: false; reason: "missing" | "expired" | "reused" };

async function validateAndConsumeNonce(
  redis: Redis,
  namespace: string,
  nonce: string
): Promise<NonceResult> {
  const key = `nonce:${namespace}:${nonce}`;
  const lua = `
    local v = redis.call('GET', KEYS[1])
    if not v then return 0 end
    redis.call('DEL', KEYS[1])
    return v
  `;
  const raw = await redis.eval(lua, 1, key);
  if (!raw) return { ok: false, reason: "missing" };
  return { ok: true, metadata: JSON.parse(raw as string) };
}
```

Returning `missing` for both expired and consumed is intentional—do not leak which case occurred to unauthenticated callers.

HTTP handler wiring:

```typescript
app.post("/oauth/callback", async (req, res) => {
  const { state, code } = req.query;
  const check = await validateAndConsumeNonce(redis, "oauth-state", state as string);
  if (!check.ok) {
    return res.status(400).json({ error: "invalid_state" });
  }
  if (check.metadata.redirectUri !== expectedRedirect(req)) {
    return res.status(400).json({ error: "redirect_mismatch" });
  }
  // exchange code...
});
```

## OAuth state vs OIDC nonce

Do not conflate them:

- **`state`** — CSRF protection for the redirect flow; your auth server generates and validates it.
- **`nonce` (OIDC)** — binds ID token to the authentication request; validated against claim in ID token after exchange.

Both need expiry. Store OIDC nonce until ID token validation completes, typically same 10–15 minute window as `state`.

```typescript
const state = issueNonce(900);
await storeNonce(redis, "oauth-state", state.nonce, state.expiresAt, {
  tenantId,
  pkceVerifier,
});

const authUrl = buildAuthorizeUrl({
  state: state.nonce,
  nonce: issueNonce(900).nonce, // separate store entry under oauth-nonce namespace
  code_challenge: pkceChallenge,
});
```

## Clock skew and TTL boundaries

Pods must run chrony or equivalent—alert if offset exceeds 100ms. Expiry is enforced by Redis TTL, not by comparing client timestamps.

For signed payloads with embedded `exp`:

```typescript
function verifySignedAgentCommand(
  payload: { nonce: string; exp: number; action: string },
  signature: string,
  publicKey: KeyObject
): void {
  const skewSec = 30;
  const now = Math.floor(Date.now() / 1000);
  if (payload.exp < now - skewSec) {
    throw new AuthError("command_expired");
  }
  verifySignature(payload, signature, publicKey);
  // then consume nonce from store — signature validity ≠ replay safety
}
```

Skew window applies only to signed `exp`, not to extending Redis TTL.

## Scaling the nonce store horizontally

Redis Cluster works if all keys for a nonce hash to the same slot—include hash tag:

```
nonce:{oauth-state}:<value>
```

For multi-region active-active, prefer a CRDT-backed store or accept regional stickiness for OAuth callbacks (user returns to same region via geo-DNS). Cross-region nonce replication adds latency and split-brain consume races—most teams route auth through a single primary region.

Memory planning: peak concurrent OAuth flows × average metadata bytes × 1.5 headroom. A 32-byte nonce key plus 200 bytes metadata at 50k concurrent flows ≈ 12 MB—trivial until metadata balloons with debug fields.

## Distinguishing nonce from idempotency key

| Property | Nonce | Idempotency-Key |
|----------|-------|-----------------|
| Lifetime | Seconds to minutes | Hours to days |
| Reuse on success | Forbidden | Returns cached response |
| Purpose | Prevent replay | Prevent duplicate side effects |
| Storage | Delete on use | Keep response mapping |

Agent run endpoint should accept both:

```http
POST /v1/agents/run
Idempotency-Key: run-7f3a9c2e
X-Agent-Nonce: k8sRndomNonceValue
```

Validate nonce first; if idempotency key seen, return 200 with stored body without re-executing—even if nonce was already consumed in the successful first call.

## Observability and alerting

Metrics:

- `nonce_issued_total{namespace}`
- `nonce_validation_failures_total{namespace, reason}`
- `nonce_store_latency_ms` histogram

Alert if failure rate spikes above 5× baseline—often indicates Redis outage or deployment clock drift. Dashboard OAuth funnel: issued → validated → token exchanged. Drop between validated and exchanged implicates nonce consume bugs vs IdP issues.

Log nonce values hashed (`sha256(nonce)`)—never plaintext in centralized logging.

## Testing replay resistance

Integration tests:

1. Issue nonce, validate successfully, validate again → expect `missing`.
2. Issue nonce, wait TTL+1s → expect `missing`.
3. Parallel double-submit with `Promise.all` → exactly one succeeds.

Use fault injection to kill Redis between issue and validate—handler must 503, not bypass.

Pen-test replay of captured curl from staging against prod should fail on environment mismatch before nonce even matters—keep environments cryptographically isolated too.

## Migration from JWT-only auth

Phase 1: Add nonce validation on highest-risk routes (payments, data export, privilege elevation).

Phase 2: Require nonces on all mutating agent tool calls; log-only mode for one release if needed.

Phase 3: Remove legacy endpoints that accepted bare bearer tokens without request binding.

Document TTL choices in your security architecture doc so future engineers do not "temporarily" extend TTL to 24 hours and forget.

## Resources

- [RFC 6749 — OAuth 2.0 (state parameter)](https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.1)
- [OpenID Connect Core — nonce claim](https://openid.net/specs/openid-connect-core-1_0.html#AuthRequest)
- [OWASP — CSRF prevention cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [Redis — SET command (NX, PX options)](https://redis.io/docs/latest/commands/set/)
- [Stripe — idempotency keys (contrast with single-use tokens)](https://docs.stripe.com/api/idempotent_requests)
