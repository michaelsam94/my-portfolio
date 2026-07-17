---
title: "OIDC Back-Channel Logout Revocation"
slug: "oidc-backchannel-logout-revocation"
description: "Implement back-channel logout — session termination across apps when IdP signs out user."
datePublished: "2026-02-04"
dateModified: "2026-07-17"
tags:
  - "Authentication"
  - "OIDC"
  - "Backend"
keywords: "oidc backchannel logout, session revocation, openid connect logout, sid claim, rp-initiated logout"
faq:
  - q: "How is back-channel logout different from front-channel logout?"
    a: "Front-channel logout uses the browser as a messenger — the IdP loads iframes or redirects to each RP's logout endpoint. Back-channel logout sends signed HTTP POST requests directly from the IdP to each RP's back-channel logout URI, so sessions terminate even when the user closes the browser immediately after signing out."
  - q: "What must an RP store to process a back-channel logout token?"
    a: "At minimum, the RP must persist the sid (session ID) or sub (subject) claim from the original ID token alongside the local session record. When a logout token arrives, match sid or sub, invalidate the session server-side, and return HTTP 200. Without this mapping, logout notifications cannot be correlated."
  - q: "Should I verify the logout token signature on every request?"
    a: "Yes. Treat logout tokens like ID tokens: validate signature against the IdP JWKS, check iss, aud, exp, and the events claim containing the logout event URI. Reject tokens missing sid and sub together, and enforce single-use semantics if your threat model includes replay."
---

When a user clicks **Sign out** at your identity provider, every relying party application that still holds an active session becomes a security liability. The user believes they are logged out everywhere; in reality, a stolen session cookie at a satellite SaaS integration may remain valid for hours. OpenID Connect defines two complementary mechanisms to propagate logout: **front-channel logout** (browser-mediated) and **back-channel logout** (server-to-server). Back-channel logout is the mechanism that closes the gap when the browser is unreliable, closed, or never involved in the first place.

This article walks through the specification mechanics, implementation decisions that actually matter in production, and the failure modes that show up during enterprise rollouts.

## Why browser-only logout fails

Front-channel logout depends on the IdP loading hidden iframes or redirecting the user's browser to each registered `end_session_endpoint` or `frontchannel_logout_uri`. That design has predictable weaknesses:

- **Tab closure**: The user signs out and immediately closes the browser tab before iframes finish loading.
- **Third-party cookie blocking**: Safari ITP and Chrome's third-party cookie deprecation break iframe-based session termination for cross-site RPs.
- **Mobile and native clients**: Native apps do not participate in iframe logout flows at all.
- **Long-lived refresh tokens**: Even if the browser session ends, refresh tokens issued to backend services may still mint access tokens unless explicitly revoked.

Back-channel logout addresses these by having the IdP POST a **Logout Token** — a JWT distinct from an ID token — directly to each RP's registered `backchannel_logout_uri`. No browser required.

## Logout token anatomy

The logout token is a JWT with specific required claims defined in [OpenID Connect Back-Channel Logout 1.0](https://openid.net/specs/openid-connect-backchannel-1_0.html):

| Claim | Requirement | Purpose |
| --- | --- | --- |
| `iss` | Required | IdP issuer identifier |
| `aud` | Required | Must include the RP's client_id |
| `iat` | Required | Issued-at timestamp |
| `jti` | Recommended | Unique token ID for replay detection |
| `events` | Required | JSON object with key `http://schemas.openid.net/event/backchannel-logout` |
| `sid` | Conditional | Session ID from original authentication |
| `sub` | Conditional | Subject identifier |

At least one of `sid` or `sub` must be present. The `events` claim is the signal that distinguishes a logout token from an ID token — RPs must reject tokens where `events` is absent or does not contain the backchannel-logout event type.

Example decoded payload:

```json
{
  "iss": "https://idp.example.com",
  "aud": "billing-app-client-id",
  "iat": 1718659200,
  "jti": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "events": {
    "http://schemas.openid.net/event/backchannel-logout": {}
  },
  "sid": "8a7b6c5d-4e3f-2a1b-0c9d-8e7f6a5b4c3d"
}
```

## RP registration and discovery

During client registration, the RP provides its `backchannel_logout_uri` — an HTTPS endpoint that accepts `application/x-www-form-urlencoded` POST bodies with a `logout_token` parameter. The IdP's `.well-known/openid-configuration` document advertises `backchannel_logout_supported: true` and optionally `backchannel_logout_session_supported` when `sid` is included in logout tokens.

Discovery checklist:

1. Confirm IdP supports back-channel logout in metadata
2. Register HTTPS URI (HTTP is forbidden in production)
3. Decide whether to require `sid` matching (stricter) or accept `sub`-only logout (broader session invalidation)
4. Configure mTLS or signed request validation if your IdP supports it

## Implementing the RP endpoint

A minimal Node.js/Express handler illustrates the validation pipeline:

```javascript
app.post('/oauth/backchannel-logout', express.urlencoded({ extended: false }), async (req, res) => {
  const logoutToken = req.body.logout_token;
  if (!logoutToken) return res.status(400).end();

  let payload;
  try {
    payload = await verifyJwt(logoutToken, {
      issuer: IDP_ISSUER,
      audience: CLIENT_ID,
      algorithms: ['RS256'],
    });
  } catch (err) {
    return res.status(401).end();
  }

  // Reject ID tokens masquerading as logout tokens
  const events = payload.events;
  if (!events?.['http://schemas.openid.net/event/backchannel-logout']) {
    return res.status(400).end();
  }
  if (payload.nonce) {
    return res.status(400).end(); // logout tokens must NOT contain nonce
  }

  // Idempotency: reject replayed jti
  if (payload.jti && await isJtiConsumed(payload.jti)) {
    return res.status(200).end(); // already processed — return success
  }

  if (payload.sid) {
    await invalidateSessionBySid(payload.sid);
  } else if (payload.sub) {
    await invalidateAllSessionsForSubject(payload.sub);
  } else {
    return res.status(400).end();
  }

  if (payload.jti) await markJtiConsumed(payload.jti, payload.exp);
  return res.status(200).end();
});
```

Key implementation details often missed:

- **Return 200 on success, not 204** — some IdPs treat non-200 as failure and retry aggressively
- **Process logout before responding** — do not enqueue async invalidation unless you accept a race where the user re-authenticates before the queue drains
- **Invalidate refresh tokens** — session cookie deletion alone is insufficient if refresh tokens remain in a mobile keychain

## Session binding at login time

Back-channel logout only works if you stored the binding at authentication. When processing the authorization code flow, persist:

```sql
CREATE TABLE oidc_sessions (
  session_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sid               text,          -- from ID token
  sub               text NOT NULL,
  id_token_jti      text,
  refresh_token_hash text,
  created_at        timestamptz NOT NULL DEFAULT now(),
  revoked_at        timestamptz
);

CREATE INDEX ON oidc_sessions (sid) WHERE revoked_at IS NULL;
CREATE INDEX ON oidc_sessions (sub) WHERE revoked_at IS NULL;
```

Extract `sid` from the ID token during the token exchange response. If the IdP does not issue `sid`, fall back to `sub`-based invalidation — but understand that logging out one browser session will terminate all sessions for that user across your application.

## IdP-side behavior and retry semantics

When the IdP initiates back-channel logout, it POSTs to every registered RP in parallel. Typical IdP behavior (Keycloak, Auth0, Okta) includes:

- **Retry on 5xx or timeout** — exponential backoff over minutes to hours
- **No retry on 4xx** — misconfiguration is not transient
- **Parallel delivery** — one slow RP does not block others

Monitor your endpoint latency. IdPs often use short timeouts (5–10 seconds). Session invalidation that triggers cascading Redis SCAN operations may exceed that window.

## Combining with token revocation

Back-channel logout terminates **sessions**; it does not automatically revoke **OAuth tokens** unless your RP implements that coupling. For defense in depth:

1. On logout token receipt, call the IdP token revocation endpoint (`/oauth/revoke`) for stored refresh tokens
2. Maintain a local token blocklist keyed by `jti` for access tokens until natural expiry
3. If using token introspection, mark sessions as revoked in your introspection cache

RFC 7009 token revocation and OIDC back-channel logout are complementary — neither replaces the other.

## Front-channel plus back-channel together

Mature deployments register both URIs. Front-channel provides immediate browser feedback (the user sees redirect loops completing). Back-channel guarantees server-side termination when the browser path fails. Sequence:

```
User clicks logout at IdP
    │
    ├─► Front-channel: browser iframes → RP logout pages
    │
    └─► Back-channel: IdP POST → each RP backchannel_logout_uri
              │
              └─► RP invalidates session + refresh tokens
```

Do not assume one mechanism suffices. Test with third-party cookies blocked — you will likely find front-channel alone leaves sessions alive.

## Security considerations

**Logout token replay**: An attacker who intercepts a logout token could force session termination (a denial-of-service against the user, not a session hijack). Mitigate with short `exp` claims, `jti` single-use tracking, and TLS everywhere.

**Endpoint authentication**: The spec allows optional `backchannel_logout_session_required` and mTLS client authentication. For high-assurance environments, require the IdP to present a client certificate when POSTing logout tokens, and validate the certificate against a pinned CA.

**CSRF is not applicable** to back-channel POSTs from the IdP — there is no browser cookie context. However, ensure your endpoint is not reachable via GET and does not reflect the token in responses.

**Information leakage**: Return identical 200 responses whether or not a matching session existed. Do not return 404 for unknown `sid` — that enables session enumeration.

## Testing strategy

1. **Unit tests**: Validate JWT parsing, events claim checking, nonce rejection, jti idempotency
2. **Integration tests**: Use a test IdP container (Keycloak dev mode) to trigger real logout flows
3. **Chaos tests**: Kill the RP endpoint mid-request, verify IdP retries and eventual consistency
4. **Cookie blocking tests**: Run front-channel and back-channel logout with Safari strict mode; confirm back-channel alone clears sessions

Log every logout token receipt with `sid`, `sub`, `jti`, and processing latency. Alert on error rate spikes — they often indicate JWKS rotation misconfiguration rather than attack traffic.

## Operational rollout

Roll out in phases:

1. **Shadow mode**: Validate logout tokens but do not invalidate sessions; log would-be invalidations
2. **Opt-in tenants**: Enable for internal apps first
3. **Full enforcement**: Invalidate on receipt; monitor session-related support tickets

Coordinate with your IdP team on logout event ordering relative to token revocation. Some IdPs revoke refresh tokens before sending back-channel logout; others reverse the order. Your RP should handle either sequence idempotently.

## Summary

OIDC back-channel logout closes the session propagation gap that front-channel browser flows leave open. Success requires storing `sid`/`sub` at login, validating logout tokens with the same rigor as ID tokens, invalidating refresh tokens alongside session cookies, and designing for IdP retry semantics. Treat it as a durability mechanism for logout — not an optional nice-to-have when your application handles sensitive data across multiple integrated services.
