---
title: "OAuth2 Device Authorization for TV"
slug: "oauth2-device-authorization-tv"
description: "Ship RFC 8628 device authorization on smart TVs: user codes, polling, activation UX, refresh tokens, and security controls for input-constrained clients."
datePublished: "2025-09-20"
dateModified: "2026-07-17"
tags:
keywords: "OAuth2 device authorization, RFC 8628, smart TV login, user code flow, device authorization grant, TV OAuth"
faq:
  - q: "What is the difference between device authorization and authorization code flow on TV?"
    a: "Authorization code flow requires a browser redirect back to the TV app — impractical on most TV platforms. Device authorization shows a user code on TV; the user completes login on phone or laptop while the TV polls for tokens."
  - q: "How do I prevent user code phishing on shared screens?"
    a: "Short expiry (15–30 minutes), rate limits on code entry, bind issued tokens to device_id, and show the requesting app name clearly on the activation page so users confirm context."
  - q: "Should TVs store refresh tokens?"
    a: "Yes for living-room UX, but only in platform secure storage (Keystore/Keychain). Rotate refresh tokens, support remote logout that revokes the family server-side, and surface 'logged in devices' in account settings."
  - q: "Can smart displays running LLM assistants use device flow?"
    a: "Yes — same pattern for linking a household account to a voice/display device without typing passwords on a remote. Scope assistant tokens narrowly; TV devices are physically accessible to guests."
---
Smart TVs are the canonical **input-constrained OAuth client**: no reliable redirect URI, no keyboard, and firmware update cycles measured in years. RFC 8628 device authorization grant solves this by moving user authentication to a second device while the TV waits with a short, human-readable code.

## Endpoints and grants

| Step | Endpoint | Grant / action |
|------|----------|----------------|
| 1 | `/oauth/device/code` | Request `device_code` + `user_code` |
| 2 | `/activate` (browser) | User signs in, enters code |
| 3 | `/oauth/token` | Poll with `grant_type=device_code` |

The TV never sees the user's password. It only polls until the authorization server marks the device code approved.

## Server-side device code issuance

```python
@app.post("/oauth/device/code")
def device_code(body: DeviceCodeRequest):
    device_code = secrets.token_urlsafe(32)
    user_code = generate_user_code()  # e.g. WDJB-MJHT, no ambiguous chars
    store.save(device_code, {
        "user_code": user_code,
        "client_id": body.client_id,
        "scope": body.scope,
        "expires_at": now() + timedelta(minutes=15),
        "interval": 5,
        "status": "pending",
    })
    return {
        "device_code": device_code,
        "user_code": user_code,
        "verification_uri": "https://auth.example.com/activate",
        "verification_uri_complete": f"https://auth.example.com/activate?user_code={user_code}",
        "expires_in": 900,
        "interval": 5,
    }
```

Persist device codes hashed at rest. Rate-limit by client_id and IP to prevent farming.

## TV client polling loop

```kotlin
suspend fun awaitAuthorization(deviceCode: String, initialInterval: Int): TokenResponse {
    var interval = initialInterval
    val deadline = System.currentTimeMillis() + 15 * 60_000
    while (System.currentTimeMillis() < deadline) {
        delay(interval * 1000L + Random.nextLong(500))
        when (val result = tokenClient.pollDeviceCode(deviceCode)) {
            is Authorized -> return result.tokens
            is Pending -> continue
            is SlowDown -> interval += 5
            is Expired -> throw DeviceCodeExpiredException()
            is Denied -> throw AuthorizationDeniedException()
        }
    }
    throw DeviceCodeExpiredException()
}
```

Respect `slow_down` — aggressive polling triggers lockouts and bad UX on shared Wi‑Fi.

## Activation page requirements

The browser flow must:

- Authenticate the user (existing session OK)
- Display client name and requested scopes plainly
- Accept user code with normalization (strip dash, uppercase)
- Confirm consent before marking device code approved

```html
<p><strong>Living Room TV</strong> wants access to:</p>
<ul>
  <li>View your profile</li>
  <li>Play subscribed content</li>
</ul>
```

Phishing resistance comes from clarity — users should recognize the device name configured at registration time.

## Refresh token strategy

Living-room devices expect persistent login. Issue refresh tokens with:

- `refresh_token_expires_in` aligned to product policy (often 180–365 days)
- Rotation on each refresh where platform supports it
- Server-side revocation list checked on every refresh

On account password change or global logout, invalidate all device code families for that user.

## Binding tokens to hardware

Include a stable `device_id` (not MAC address in plaintext — use platform-provided ID) in token claims or parallel session record. Reject refresh attempts when device fingerprint changes unexpectedly — indicates token export from TV storage.

## LLM-enabled TV apps

Voice assistants on TVs combine device authorization with **narrow scopes**:

- `assistant:query` for on-device NLU calling your gateway
- No `account:payment` or `settings:admin` on the TV client
- Push sensitive account changes to mobile web only

Log `device_id`, `client_id`, and scope set at token issuance — support teams need to trace which living-room device triggered a bad purchase or data export.

## Operational metrics

Track:

- Median time from code display to authorization complete (target under 60s)
- Poll requests per successful auth (detect client bugs)
- Expired codes without authorization (UX friction signal)
- Refresh failure rate by device model (storage or clock issues)

Alert on spikes in `access_denied` for a single client_id — may indicate confused users or abuse.

## Testing without a physical TV

Use CLI harness implementing the same grant:

```bash
./tv-sim login --client-id tv-staging
# prints user code; open activation URL in browser
# polls until tokens returned; writes to /tmp/tv-sim.tokens.json
```

Run integration tests in CI against a dockerized IdP with fixed clock for expiry edge cases.

## Living-room UX details

Show the user code in grouped blocks (XXXX-XXXX) with a QR encoding `verification_uri_complete`. Auto-refresh the code 30 seconds before expiry without forcing navigation — users abandon flows when codes die silently mid-entry. Pair audio cues sparingly; accessibility matters for visually impaired users on connected TVs.

For LLM-powered TVs, display which account will be linked before polling completes so households with multiple profiles do not attach the wrong subscription tier.

## Accessibility and localization

User codes must remain readable with large-type modes enabled. Localize activation instructions but keep codes ASCII — do not transliterate codes into non-Latin scripts. Screen readers on companion mobile apps should announce the verification URL and code length, not the raw secret device_code stored on TV.

## Partner OEM integrations

OEM partners embedding your app may supply custom activation domains. Register redirect and verification URI allowlists per `client_id` and test on factory images — preproduction TVs often ship with outdated CA bundles that break HTTPS to your auth server until firmware updates land.

## Security review checklist

Before launching device authorization on a new platform:

- Hash device codes at rest; never log raw device codes alongside user PII in the same event.
- Enforce maximum poll rate per device_code and per IP subnet.
- Require user confirmation screen showing client logo and name matched to registered metadata.
- Support global logout that revokes all device refresh tokens for the account.
- Pen-test the activation page for CSRF on consent submission and user code brute force (rate limit + lockout).

## Comparison with authorization code on hybrid TVs

Some smart TV browsers now support Custom Tabs or embedded WebView logins. Prefer device authorization when the platform cannot reliably receive redirect URIs or when OEM security review forbids storing OAuth client secrets in firmware. Hybrid flows that embed a full browser login often break silently after WebView certificate updates — device codes fail loudly with visible expiry, which is easier to support remotely.

## Resources

- [RFC 8628 — OAuth 2.0 Device Authorization Grant](https://www.rfc-editor.org/rfc/rfc8628)
- [OAuth.net device authorization](https://oauth.net/2/grant-types/device-code/)
- [Google limited-input device flow](https://developers.google.com/identity/protocols/oauth2/limited-input-device)

## Production notes for LLM stacks

When `oauth2-device-authorization-tv` sits on an inference or RAG path, treat user prompts and retrieved chunks as untrusted input. Log correlation IDs and policy decisions—not raw prompts—in production telemetry. Gate risky operations behind explicit authorization at the gateway, not inside ad-hoc tool handlers.

Roll out changes with shadow mode first: record what **would** have happened under the new rule without blocking traffic. Compare deny rates, latency impact, and false positives for at least one business week before enforcing. Pair enforcement with a runbook entry: symptom, dashboard, rollback (feature flag or config), and owner.

Load-test with production-shaped concurrency. LLM workloads burst differently from CRUD APIs—tail latency and token throttling dominate. If `oauth2 device authorization for tv` protects an invariant (security, billing, data residency), prove the invariant with an automated test that fails CI when someone removes the check.

## What teams get wrong

Teams copy a reference architecture without matching their compliance tier, then discover in audit that logs, backups, or support exports reintroduced the data they thought they had eliminated. Another pattern: shipping the demo integration without idempotency, then fighting duplicate side effects when clients retry on model timeouts.

Document the tradeoff you chose—strictness vs recall, cost vs quality, sync vs async—and the metric that tells you if the choice still holds six months later.

## Authorization server configuration

Enable refresh token rotation in your IdP (Auth0, Okta, Keycloak, Cognito) and verify the behavior in a staging tenant before mobile clients ship. Rotation should issue a **new refresh token** on every refresh response and invalidate the previous token in the same family. Store only hashed refresh token identifiers server-side so database leaks do not grant session persistence.

Document the client behavior matrix: public clients must use PKCE; confidential backends may use client authentication on the token endpoint; never mix refresh token policies across platforms using the same OAuth client ID if redirect and storage models differ.

## Detecting token reuse

When a refresh token is presented twice, treat it as compromise: revoke the entire token family, force re-authentication for that user session, and emit a security event with device fingerprint and IP. Rate-limit refresh endpoints separately from login to prevent brute force against leaked tokens.

```typescript
async function rotateRefresh(oldToken: string): Promise<TokenPair> {
  const row = await db.refreshTokens.findByHash(hash(oldToken));
  if (!row || row.revoked) {
    await revokeFamily(row?.familyId);
    throw new ReuseDetectedError();
  }
  await db.refreshTokens.revoke(row.id);
  return issueNewPair(row.familyId, row.userId);
}
```

## Mobile and SPA considerations

SPAs should not store refresh tokens in localStorage. Prefer HttpOnly cookies with SameSite constraints for web, and secure enclave / Keychain storage for native. LLM features that call backends on behalf of users should use short-lived access tokens minted server-side—not long-lived refresh tokens embedded in client-side agent runtimes.
