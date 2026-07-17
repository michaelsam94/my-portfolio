---
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

## Authorization server configuration

Enable refresh token rotation in your IdP (Auth0, Okta, Keycloak, Cognito) and verify the behavior in a staging tenant before mobile clients ship. Rotation should issue a **new refresh token** on every refresh response and invalidate the previous token in the same family. Store only hashed refresh token identifiers server-side so database leaks do not grant session persistence.

Document the client behavior matrix: public clients must use PKCE; confidential backends may use client authentication on the token endpoint; never mix refresh token policies across platforms using the same OAuth client ID if redirect and storage models differ.

## Detecting token reuse in production

When a refresh token is presented twice outside the grace window, treat it as compromise: revoke the entire token family, force re-authentication for that user session, and emit a security event with device fingerprint and IP. Rate-limit refresh endpoints separately from login to prevent brute force against leaked tokens.

Pair rotation with short access token TTL (5–15 minutes) so family revocation takes effect quickly even if access tokens were copied before reuse detection fired.

## LLM and mobile client notes

Native apps embedding LLM features often cache refresh tokens in Keychain. Ensure SDK retry logic respects grace windows—duplicate refresh after timeout must not trigger family revocation for legitimate users. Never log refresh response bodies in analytics pipelines; token leakage in crash reports is a common rotation bypass.
## IdP-specific implementation notes

**Auth0:** Enable rotating refresh tokens per application; configure reuse detection interval aligned with your grace window. **Okta:** Use custom authorization server policies; verify refresh behavior for SPA vs native clients separately. **Keycloak:** Client policy for refresh token max reuse; test offline sessions vs standard refresh. **Cognito:** Document which app clients support rotation natively vs require custom Lambda triggers.

Regardless of vendor, export metrics on `invalid_grant` spikes after enabling rotation—often reveals SDK double-refresh bugs before users flood support.

## Database migration for token families

Backfill `family_id` for existing refresh tokens before enforcing rotation. Run dual-write period where old tokens work without family metadata but new tokens populate families. After 30 days, revoke legacy non-rotating tokens with comms to users on ancient app versions.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.
