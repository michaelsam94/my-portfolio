#!/usr/bin/env python3
"""Write four OAuth2 deep-dive posts (restored after template revert)."""
from pathlib import Path

BLOG = Path(__file__).resolve().parent.parent / "content" / "blog"

FILES = {}

FILES["oauth2-refresh-token-rotation"] = '''---
title: "OAuth2 Refresh Token Rotation"
slug: "oauth2-refresh-token-rotation"
description: "Rotate refresh tokens on every use, bind them to token families, and detect reuse as a breach signal—without breaking mobile clients on flaky networks."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "OAuth"
  - "Authentication"
  - "Backend"
keywords: "oauth2 refresh token rotation, token family revocation, refresh token reuse detection, RFC 9700, mobile oauth security"
faq:
  - q: "Why rotate refresh tokens on every use instead of issuing long-lived static tokens?"
    a: "A stolen refresh token that never changes gives attackers indefinite access. Rotation issues a new refresh token on each exchange and invalidates the previous one. If the old token appears again, you know a copy leaked—and you revoke the entire token family."
  - q: "How do you handle duplicate refresh requests from mobile apps on bad networks?"
    a: "Treat the first successful rotation as authoritative and return the same new token pair for a short grace window (30–120 seconds) when the same old refresh token is presented again. Without grace, flaky Wi‑Fi causes mass logouts."
  - q: "Should refresh token rotation apply to confidential server-side clients?"
    a: "RFC 9700 focuses on public clients where refresh tokens are high-value secrets on user devices. Confidential clients may use rotation optionally, but token families still help detect credential theft from compromised backends."
  - q: "What should happen when reuse is detected?"
    a: "Revoke the entire token family immediately—all outstanding access and refresh tokens descended from the original grant. Force re-authentication, log a security event, and rate-limit further attempts from that device fingerprint."
---

A security review found the same refresh token used from two countries within four minutes. The authorization server had issued a static refresh token with a 90-day TTL and no rotation. Revoking that one row logged out the attacker—and also every legitimate session for 40,000 users who shared the same client implementation. Refresh token rotation fixes the theft-detection story, but only if you design for mobile retries, concurrent tabs, and the moment reuse detection fires.

## The threat model refresh rotation addresses

Refresh tokens are bearer credentials. Anyone who possesses one can obtain new access tokens until expiry or revocation. Attack paths include malware reading local storage, XSS exfiltration, leaked mobile backups, and server logs that accidentally capture token response bodies. Static refresh tokens fail silently. Rotation adds a signal: when token R1 is exchanged for R2, only R2 should work next. If R1 appears again, two parties hold copies.

## Token families, not single rows

Model refresh tokens as nodes in a family tree rooted at the initial authorization grant. Store `family_id`, `parent_token_hash`, `issued_at`, `revoked_at`, and `client_id`. Hash tokens at rest—never store plaintext refresh tokens in your database.

```sql
CREATE TABLE refresh_token_family (
  family_id   uuid PRIMARY KEY,
  user_id     uuid NOT NULL,
  client_id   text NOT NULL,
  revoked_at  timestamptz
);

CREATE TABLE refresh_token (
  token_hash    text PRIMARY KEY,
  family_id     uuid NOT NULL REFERENCES refresh_token_family(family_id),
  parent_hash   text,
  expires_at    timestamptz NOT NULL,
  consumed_at   timestamptz,
  grace_until   timestamptz
);
```

On rotation: mark old token consumed, insert new token with same `family_id`, return new pair. On reuse of a consumed token outside grace: set `revoked_at` on the family and reject all descendants.

## Rotation exchange flow

Use `SELECT … FOR UPDATE` so two concurrent requests with the same old token cannot both succeed. On consumed token within grace window, return cached new token response (idempotent mobile retry). On reuse outside grace, revoke family and log `refresh_reuse` security event.

## Grace period: necessary, bounded

Without grace, lost responses on flaky networks cause mass logouts. A 60-second grace window where R1 returns the same R2 response fixes retries without reopening theft windows for hours. Document grace behavior in your mobile SDK.

## Public vs confidential clients

Mobile native and SPAs require mandatory rotation (RFC 9700). Pair rotation with sender-constrained access tokens (DPoP or mTLS) where possible—rotation limits refresh theft; sender constraint limits access token replay.

## Observability without leaking secrets

Metrics: `oauth_refresh_total{result}`, `oauth_refresh_duration_seconds`, `oauth_refresh_family_revocations_total{reason}`. Logs: `family_id`, `client_id`, `result`—never log refresh token values.

## Common mistakes

No transactional rotation; grace without cached response; family revocation that misses access tokens; rotation without client authentication on mobile; 90-day refresh TTL with no rotation policy.

## Rollout and testing

Ship rotation in shadow mode logging would-be reuse; enable for one client_id in beta; monitor `invalid_grant` rate; enforce family revocation for all public clients. Test: single refresh returns new token; duplicate within grace returns identical body; duplicate after grace revokes family; concurrent refresh exactly one succeeds.

Refresh token rotation is a state machine with concurrency, mobile networks, and security incidents baked in—not a checkbox on your IdP admin panel.
'''

# Additional oauth posts appended in same file - resource indicators, dpop, introspection
# (content continues in write loop below from OAUTH_REST dict)

OAUTH_REST = {
"oauth2-resource-indicators-audience": '''---
title: "OAuth2 Resource Indicators and Audience"
slug: "oauth2-resource-indicators-audience"
description: "Use RFC 8707 resource indicators so access tokens are minted for the correct API audience—stopping token passthrough and confused-deputy attacks."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags: ["Security", "OAuth", "Authentication", "Backend"]
keywords: "oauth2 resource indicators, RFC 8707, token audience, audience claim, api authorization"
faq:
  - q: "What is a resource indicator in OAuth2?"
    a: "A URI passed via the resource parameter telling the authorization server which API the access token should be valid for, so the token audience matches that API."
  - q: "How is resource different from scope?"
    a: "Scope expresses what the client may do. Audience expresses where the token may be used. Correct scopes with wrong audience should be rejected by the resource server."
  - q: "Why does token passthrough happen without audience binding?"
    a: "When all APIs accept the same JWT without checking aud, a token for a low-privilege API can be forwarded to a high-privilege internal service."
  - q: "Should every microservice have its own resource URI?"
    a: "Prefer one resource URI per security boundary—typically per API gateway or service cluster—not per endpoint."
---

An internal admin tool obtained an access token for the read-only catalog API and used it against the payments service. Payments accepted it—the JWT was signed by the corporate AS, scopes included `read:payments` from an earlier experiment, and nobody validated `aud`. Resource indicators (RFC 8707) fix audience at issuance so payments rejects tokens minted for catalog.

## Audience vs scope

Scope: what actions may this client perform? Audience: which resource server should accept this token? Without explicit audience, many AS products default to `aud: client_id` or a single global API identifier.

## RFC 8707 resource parameter

Clients include `resource` in token requests. The AS validates the client is allowed to request that resource, sets token audience accordingly, and returns JWT or opaque token with correct `aud` claim. Resource servers validate `aud` before scope checks.

## Token passthrough and confused deputy

Service A forwarding a user token to privileged Service B is unsafe unless B validates audience. B must reject tokens unless `aud` is B's identifier. A should use on-behalf-of token exchange or service credentials to call B.

## Gateway vs service validation

Validate JWT signature, `iss`, `exp`, and `aud` at the API gateway. Each microservice still validates `aud` if tokens can arrive without passing through the gateway.

## Client notes

Mobile apps: separate access tokens per resource or array `aud` with agreed validation. SPAs with BFF: browser never holds multi-audience tokens; BFF requests tokens server-side with explicit `resource`.

## Migration

Inventory APIs sharing one issuer; assign canonical resource URIs; update AS to accept `resource`; deploy resource servers with aud validation in log-only mode; enforce after error rate proves clients send correct resource.

Resource indicators turn "signed by our AS" into "signed for this API"—the difference between identity plumbing and an authorization boundary.
''',
"oauth2-token-binding-dpop": '''---
title: "OAuth2 Token Binding with DPoP"
slug: "oauth2-token-binding-dpop"
description: "Bind access tokens to a client-held key with DPoP proofs—so stolen bearer tokens fail at the resource server even before expiry."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags: ["Security", "OAuth", "Authentication", "Backend"]
keywords: "oauth2 dpop, demonstration of proof of possession, token binding, RFC 9449"
faq:
  - q: "What problem does DPoP solve that HTTPS does not?"
    a: "HTTPS protects tokens in transit. DPoP protects against tokens stolen after delivery—XSS, logs, malware. Bearer tokens alone prove nothing about who presents them."
  - q: "How is DPoP different from mTLS?"
    a: "mTLS binds at TLS layer—great for service-to-service. DPoP works at HTTP layer with ephemeral keys in mobile and browser clients via BFF."
  - q: "Does DPoP replace refresh token rotation?"
    a: "No. Rotation detects refresh reuse; DPoP constrains access token replay. Use both for public clients."
  - q: "What if the resource server skips DPoP validation?"
    a: "Attackers with stolen tokens operate normally. DPoP is security theater unless every resource server validates proofs."
---

A pen test exfiltrated a valid access token from browser devtools. Curl from an attacker's laptop returned 200 until expiry. DPoP (RFC 9449) binds the access token to an ephemeral key pair—require a signed proof on every resource request.

## Bearer vs sender-constrained

DPoP fits public clients generating EC keys in Web Crypto or Secure Enclave without PKI provisioning per device.

## DPoP proof JWT

Payload includes `htm`, `htu`, `iat`, `jti`, and `ath` (access token hash when presenting bearer token). Resource servers validate signature, method, URI, jkt thumbprint match to token `cnf.jkt`, and jti replay cache.

## Authorization server

On token endpoint validate DPoP proof; issue access token with `cnf.jkt` confirmation claim. Bind refresh tokens to DPoP key where policy requires.

## SPA architecture

BFF holds DPoP keys server-side; browser gets session cookie only—XSS cannot exfiltrate bearer token directly.

## Failure modes

Gateway validates but internal services do not; clock skew on `iat`; load balancer URL mismatch in htu normalization; logging full DPoP headers unnecessarily.

## Rollout

Client SDK attach DPoP; AS issue cnf.jkt; APIs log-only validation then enforce; coordinate mobile release with backend enforcement.

DPoP stops export of reusable bearer credentials to another machine—it does not stop XSS acting as the user inside the browser.
''',
"oauth2-token-introspection-revocation": '''---
title: "OAuth2 Token Introspection and Revocation"
slug: "oauth2-token-introspection-revocation"
description: "Use RFC 7662 introspection and RFC 7009 revocation correctly—when opaque tokens and immediate logout require more than JWT self-validation."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags: ["Security", "OAuth", "Authentication", "Backend"]
keywords: "oauth2 token introspection, token revocation RFC 7009, opaque access tokens, RFC 7662"
faq:
  - q: "When should I use token introspection instead of local JWT validation?"
    a: "For opaque tokens or when you need real-time revocation after offboarding or stolen token response. JWT local validation cannot know a token was revoked until expiry without a blocklist."
  - q: "Does revocation invalidate access tokens immediately?"
    a: "RFC 7009 revokes refresh tokens; access token behavior depends on AS implementation. Pair revocation store with introspection or keep access TTL ≤ 5 minutes for sensitive scopes."
  - q: "Who may call the introspection endpoint?"
    a: "Only confidential resource servers with authenticated client credentials—never expose to browsers."
  - q: "How do I avoid introspection as a single point of failure?"
    a: "Cache active results briefly (30–60s), fail closed for high-risk APIs, scale introspection horizontally, prefer JWT with short TTL for read-heavy paths where delayed revocation is acceptable."
---

HR terminated an employee at 09:00. Their JWT still had 45 minutes of `exp`. The gateway validated signature locally. Introspection would have returned `"active": false` after sessions were revoked at 09:01.

## JWT vs introspection

Local JWT verify is fast but cannot know revocation unless `jti` blocklist or short TTL. Opaque tokens require introspection.

## RFC 7662

POST token to introspection endpoint; response includes `active`, `scope`, `sub`, `aud`, `exp`. Resource server rejects inactive like invalid bearer. Cache active results only with short TTL—never cache inactive=false long.

## RFC 7009 revocation

Revoke refresh or access tokens; AS returns 200 even if already invalid. Document whether access tokens die immediately or live until exp after refresh revocation.

## Pairing revocation with introspection

Revocation writes to store keyed by `jti`; introspection checks store before `active: true`. Push `jti` blocklist to gateways for JWT paths.

## Performance

20k RPS cannot introspect every request without cache. Circuit breaker: fail closed for admin routes. Alert on introspection p99 and error rate.

## Compliance drills

Quarterly: revoke test user, assert resource API rejects within TTL + cache window. Log `{actor, subject, jti, reason}` without token plaintext.

Introspection and revocation bridge "logout in the IdP" and "this access token stops working now"—implement with caching discipline and honest documentation of access token lifetime after logout.
''',
}

FILES.update(OAUTH_REST)

def main():
    for slug, content in FILES.items():
        path = BLOG / f"{slug}.md"
        path.write_text(content.strip() + "\n")
        wc = len(content.split())
        print(f"{wc:5} {slug}")

if __name__ == "__main__":
    main()
