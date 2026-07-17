---
title: "Migrating from Passwords to Passkeys"
slug: "passkeys-vs-passwords-migration"
description: "Migrate users from passwords to passkeys: WebAuthn rollout strategy, fallback flows, account recovery, and backend changes without locking out existing users."
datePublished: "2026-01-30"
dateModified: "2026-07-17"
tags: ["Security", "Authentication", "Passkeys", "WebAuthn"]
keywords: "passkey migration, WebAuthn rollout, passwordless authentication, FIDO2 passkeys, passkey fallback"
faq:
  - q: "Can users keep passwords while you roll out passkeys?"
    a: "Yes — and they should during migration. Passkeys become the primary auth method; passwords remain as fallback until users enroll a passkey and you explicitly deprecate password login. Forced cutover without fallback spikes support tickets."
  - q: "How do passkeys sync across devices?"
    a: "Platform passkeys sync via iCloud Keychain (Apple), Google Password Manager (Android/Chrome), or password managers like 1Password. Cross-platform users may need multiple passkeys registered — one per ecosystem — or a roaming passkey on a security key."
  - q: "What happens if a user loses all devices with their passkey?"
    a: "Account recovery requires pre-registered backup factors: a second passkey on another device, recovery codes generated at enrollment, or verified email/SMS step-up (weaker). Never leave recovery as 'contact support' without identity verification procedures."
---

We enabled passkeys and watched signup conversion improve 8%. We also watched 400 support tickets in week one from users who clicked "Sign in with passkey" on a shared family PC and couldn't understand why their phone didn't help. Passkey migration is a product project with security benefits, not a checkbox next to `navigator.credentials.create()`.

## Why migrate now

Passkeys (FIDO2/WebAuthn discoverable credentials) eliminate password reuse, phishing (credentials are origin-bound), and most credential stuffing. NIST and CISA push them for good reason. But your users have ten years of password habits and possibly no biometrics on their work laptop.

## Phased rollout

**Phase 1 — Opt-in enrollment.** After password login, prompt: "Add a passkey for faster sign-in." Store credential alongside password.

**Phase 2 — Passkey-first login.** Login page shows passkey button prominently; password under "Other options."

**Phase 3 — Deprecate password for enrolled users.** Require passkey or recovery code; password removed per account.

**Phase 4 — New users passkey-only.** Optional passwordless-from-day-one for consumer apps; B2B often keeps SSO.

Never skip phase 1. Forced enrollment before users understand passkeys generates churn.

## Backend data model

```sql
CREATE TABLE webauthn_credentials (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  credential_id BYTEA NOT NULL UNIQUE,
  public_key BYTEA NOT NULL,
  sign_count BIGINT NOT NULL DEFAULT 0,
  transports TEXT[],           -- 'internal', 'hybrid', 'usb'
  aaguid UUID,
  friendly_name TEXT,          -- "MacBook Pro", "iPhone 15"
  created_at TIMESTAMPTZ DEFAULT now(),
  last_used_at TIMESTAMPTZ
);
```

Track `sign_count` for clone detection. Reject authentication if `sign_count` doesn't increment.

Use a library — SimpleWebAuthn (Node), py_webauthn (Python), go-webauthn — don't implement CBOR parsing yourself.

## Registration flow (simplified)

```typescript
// Server: generate options
const options = await generateRegistrationOptions({
  rpName: 'Acme',
  rpID: 'acme.com',
  userID: user.id,
  userName: user.email,
  authenticatorSelection: {
    residentKey: 'preferred',
    userVerification: 'preferred',
  },
});

// Client: browser API
const credential = await navigator.credentials.create({ publicKey: options });

// Server: verify and store
const verification = await verifyRegistrationResponse({
  response: credential,
  expectedChallenge: options.challenge,
  expectedOrigin: 'https://acme.com',
  expectedRPID: 'acme.com',
});
```

`residentKey: 'preferred'` enables discoverable credentials (usernameless login). Requires broader device support testing.

## Authentication and fallback

Login page logic:

1. Try conditional UI (`mediation: 'conditional'`) for autofill passkey prompt
2. Explicit passkey button → `navigator.credentials.get()`
3. "Sign in with password" fallback
4. "Use recovery code" for lockout

For enterprise: SAML/OIDC SSO may bypass passkeys entirely — passkeys target direct consumer auth.

## Recovery without destroying security

Generate ten single-use recovery codes at first passkey enrollment. Store hashed (bcrypt). One code per recovery event.

Alternative: require a second passkey on a different device before removing the first. "Add backup passkey" should be as prominent as "Add passkey."

SMS recovery for passkey lockout reintroduces phishing risk — use only with step-up verification and rate limits.

## UX details that matter

- Explain passkeys use Face ID / fingerprint — not " cryptographic credential"
- Let users name passkeys ("Work laptop") for management screen
- Show last-used timestamp; allow revoke per credential
- Handle `NotAllowedError` gracefully when user cancels biometric prompt

Test on: iOS Safari, Android Chrome, Windows Hello, macOS Touch ID, and Firefox (passkey support improved but verify your target versions).

## Enterprise SSO coexistence

B2B apps often have SAML/OIDC SSO for corporate tenants and direct passkeys for consumer accounts. Model auth methods per tenant in your identity schema — do not assume one migration path fits all customers.

Document which tenants remain password-only for contractual reasons. Sales promises about "passwordless by Q3" fail when enterprise IdP does not support passkey federation yet.

## Operational notes

Track passkey adoption funnel in product analytics: offered, started, completed, failed with WebAuthn error code. `NotAllowedError` spikes indicate UX timing issues; `NotSupportedError` clusters on older Android WebViews — adjust minimum supported browser matrix with data.

Publish a browser support matrix on your help center before launch — reduces support volume when users on unsupported browsers attempt WebAuthn and receive opaque errors.

Coordinate passkey launch with customer support training — agents need scripts for account recovery when users lose devices, including when to escalate to manual identity verification versus self-service recovery codes.

Schedule penetration test focused on WebAuthn implementation before removing password fallback — passkey-only surface is smaller but errors are costlier for locked-out users.

## Server-side WebAuthn implementation

Complete registration and authentication flow:

```typescript
import {
  generateRegistrationOptions,
  verifyRegistrationResponse,
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
} from '@simplewebauthn/server';

// Registration
const options = await generateRegistrationOptions({
  rpName: 'My App',
  rpID: 'example.com',
  userID: user.id,
  userName: user.email,
  attestationType: 'none',  // 'direct' for high-security environments
  authenticatorSelection: {
    residentKey: 'preferred',
    userVerification: 'preferred',
  },
});

// After client responds
const verification = await verifyRegistrationResponse({
  response: clientResponse,
  expectedChallenge: options.challenge,
  expectedOrigin: 'https://example.com',
  expectedRPID: 'example.com',
});
if (verification.verified) {
  await storeCredential(user.id, verification.registrationInfo);
}
```

Store `credentialID`, `credentialPublicKey`, `counter`, and `transports` per credential. Counter prevents credential cloning replay.

## Conditional UI (autofill passkeys)

Show passkeys in autofill dropdown alongside passwords:

```javascript
// Browser autofill integration
const abortController = new AbortController();
const options = await fetch('/auth/passkey/authenticate-options').then(r => r.json());

const credential = await navigator.credentials.get({
  publicKey: options,
  mediation: 'conditional',  // shows in autofill dropdown
  signal: abortController.signal,
});
```

`mediation: 'conditional'` enables passkey autofill on login page load — user sees passkey option without clicking a button first.

## Migration funnel metrics

Track adoption to inform fallback removal timing:

```python
MIGRATION_METRICS = {
    "passkey_offered":       "users shown passkey registration prompt",
    "passkey_started":       "users who clicked 'Add passkey'",
    "passkey_completed":     "successful WebAuthn registration",
    "passkey_login_rate":    "logins via passkey vs password",
    "passkey_error_rate":    "WebAuthn errors by code",
    "password_fallback_rate": "logins still using password",
}

# Target before removing password fallback:
# passkey_login_rate > 80% of active users
# passkey_error_rate < 5%
```

Remove password fallback only when passkey login rate exceeds 80% of active users for 30 consecutive days.

## Failure modes

- **No backup passkey flow** — single device loss locks user out permanently
- **Counter not checked** — cloned credential replay possible
- **Password removed before 80% adoption** — mass lockout event
- **NotSupportedError on older Android WebView** — no graceful fallback message
- **Enterprise SSO not considered** — B2B tenants can't use passkey migration path

## Production checklist

- Backup passkey registration prominently offered at first passkey setup
- Credential counter checked on every authentication
- Conditional UI (`mediation: 'conditional'`) enabled on login page
- Migration funnel tracked: offered → started → completed → login rate
- Password fallback retained until passkey login rate >80% for 30 days
- Browser support matrix published on help center before launch

## Communicating passkeys to users

Copy matters more than crypto. Avoid "Replace your password with a passkey" on day one. Use:

- "Sign in faster with Face ID / fingerprint"
- "Add a passkey — works on this phone and syncs to your iCloud account"

Tooltips explaining **which device** holds the passkey reduce family-PC confusion. Show `friendly_name` from WebAuthn registration in account settings.

## Analytics for migration funnel

Track funnel events: `passkey_offer_shown`, `passkey_registered`, `passkey_login_success`, `passkey_login_fallback_password`. Plateau in registration often means UX friction, not security skepticism — A/B test prompt timing (post-login vs settings-only).

## Enterprise SSO coexistence

B2B apps with SAML SSO may defer passkeys until workforce IdP supports FIDO2 delegation. Document: passkeys for native app + consumer tier; SSO for corporate domain users. Don't block SAML users from optional passkey enrollment for personal devices.

## Support tooling for passkey lockout

Support agents verify identity via video + government ID before deleting all credentials — self-serve "lost passkey" flows are phishing targets. Audit credential deletion with ticket ID.

## Conditional UI autofill

`mediation: 'conditional'` shows passkey autofill hint on login fields — increases discovery without dedicated button. Test Safari and Chrome Android differences; fallback button always visible.

## Resources

- [WebAuthn specification (W3C)](https://www.w3.org/TR/webauthn-3/)
- [passkeys.dev documentation](https://passkeys.dev/)
- [SimpleWebAuthn library](https://simplewebauthn.dev/)
- [FIDO Alliance passkey guidelines](https://fidoalliance.org/passkeys/)
- [Google passkeys for developers](https://developers.google.com/identity/passkeys)