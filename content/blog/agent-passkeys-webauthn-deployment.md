---
title: "AI Agents: Passkeys Webauthn Deployment"
slug: "agent-passkeys-webauthn-deployment"
description: "Deploy FIDO2 passkeys with correct RP ID binding, challenge lifecycle, attestation policy, and cross-platform recovery—without breaking login on day two."
datePublished: "2025-12-15"
dateModified: "2025-12-15"
tags: ["AI", "Agent", "Passkeys"]
keywords: "passkeys, WebAuthn, FIDO2, authenticator, RP ID, attestation, passwordless deployment"
faq:
  - q: "Should production passkey deployments verify attestation?"
    a: "Most consumer apps skip full attestation and rely on platform authenticators plus risk signals. Regulated or high-value accounts may require attestation with an allowlist of authenticator AAGUIDs and a fallback path for unsupported devices."
  - q: "What breaks when RP ID and domain do not match?"
    a: "Registration succeeds in staging but authentication fails in production because the browser binds credentials to the exact RP ID hostname. Subdomain changes, apex vs www mismatches, and preview deploy URLs are the usual culprits."
  - q: "How do you handle users who lose all passkey devices?"
    a: "Keep a separate, step-up verified recovery channel—backup codes, hardware key enrollment, or helpdesk identity proofing. Never store a recoverable private key; issue new credentials after verified recovery."
  - q: "Can passkeys coexist with password login during rollout?"
    a: "Yes. Run parallel authentication methods with explicit UX that nudges enrollment without blocking legacy login until metrics show enrollment coverage and support load are acceptable."
---
A product team shipped passkeys in a sprint demo and celebrated a 40% enrollment rate in the first week. Three weeks later, support volume doubled: users on corporate Windows laptops could register but not sign in after a domain migration, Android users hit "No available authenticator" on older WebViews, and the security team asked why attestation was disabled while finance asked why hardware keys were not supported. Passkeys are not a checkbox feature—they are a ceremony protocol with sharp edges around hostname binding, challenge replay, and device sync.

This guide walks through deploying WebAuthn passkeys in production: the server-side state you must persist, the browser ceremonies that actually run, and the rollout decisions that determine whether you retire passwords or inherit a new category of auth incidents.

## What a passkey actually is

A passkey is a FIDO2 credential: a key pair generated inside a platform authenticator (Touch ID, Windows Hello, Android Keystore) or a roaming authenticator (YubiKey). The private key never leaves the authenticator. Your server stores only the public key, a credential ID, a signature counter, and metadata about how the credential was created.

WebAuthn defines two ceremonies:

- **Registration (create)** — proves the user controls an authenticator and binds it to your Relying Party (RP).
- **Authentication (get)** — proves possession of the private key by signing a server-issued challenge.

Both ceremonies are mediated by the browser's `navigator.credentials` API. Your backend validates the signed payloads using libraries such as `@simplewebauthn/server` or equivalent implementations in other languages.

## Architecture decisions before you write code

### RP ID and origins

The RP ID is typically your registrable domain (`example.com`, not `app.example.com` unless you intentionally scope it). Browsers enforce that the page origin matches the RP ID. Document every hostname that will serve login UI—`www`, apex, regional subdomains, and mobile deep-link hosts—and align them before enrollment begins.

Maintain an explicit allowlist of origins in server configuration. Reject ceremonies from origins not on the list even if the RP ID matches; this blocks phishing clones on lookalike domains.

### Challenge store and TTL

Every ceremony starts with a random challenge stored server-side (Redis, session table, or encrypted cookie) with a short TTL—60 to 120 seconds is typical. The challenge must be single-use: delete it on successful verification or explicit failure. Reused challenges are a replay vector.

Bind the challenge to the user session or a pending registration token so an attacker cannot complete someone else's half-finished flow.

### User verification and resident keys

Passkeys for consumer apps usually require **resident keys** (discoverable credentials) and **user verification** (biometric or PIN). Set `authenticatorSelection.residentKey` to `required` and `userVerification` to `required` unless you have a concrete reason to relax either—password managers and platform sync depend on discoverable credentials.

### Attestation policy

Full attestation tells you which authenticator model created the credential. Many teams set `attestation` to `none` for simplicity and fraud-model with device signals instead. If you need hardware-backed guarantees, maintain an AAGUID allowlist and provide a fallback enrollment path for unsupported devices.

## Registration ceremony: server and client

The registration flow has four beats: issue options, call the browser, post the attestation, verify and persist.

**Server — generate registration options:**

```typescript
import {
  generateRegistrationOptions,
  verifyRegistrationResponse,
} from "@simplewebauthn/server";

const options = await generateRegistrationOptions({
  rpName: "Acme App",
  rpID: "acme.com",
  userID: user.uuid,
  userName: user.email,
  userDisplayName: user.displayName,
  attestationType: "none",
  authenticatorSelection: {
    residentKey: "required",
    userVerification: "required",
  },
  excludeCredentials: existingCredentials.map((c) => ({
    id: c.credentialId,
    transports: c.transports,
  })),
});

await challengeStore.set(`reg:${user.id}`, options.challenge, { ttlSeconds: 90 });
return options;
```

**Client — create credential:**

```typescript
const options = await fetch("/webauthn/register/options").then((r) => r.json());

const credential = await navigator.credentials.create({
  publicKey: {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    user: { ...options.user, id: base64urlToBuffer(options.user.id) },
  },
});

await fetch("/webauthn/register/verify", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(credential),
});
```

**Server — verify and persist:**

```typescript
const expectedChallenge = await challengeStore.get(`reg:${user.id}`);
if (!expectedChallenge) throw new AuthError("challenge_expired");

const verification = await verifyRegistrationResponse({
  response: req.body,
  expectedChallenge,
  expectedOrigin: ALLOWED_ORIGINS,
  expectedRPID: "acme.com",
});

if (!verification.verified || !verification.registrationInfo) {
  throw new AuthError("registration_failed");
}

await credentialRepo.insert({
  userId: user.id,
  credentialId: verification.registrationInfo.credentialID,
  publicKey: verification.registrationInfo.credentialPublicKey,
  counter: verification.registrationInfo.counter,
  transports: req.body.response.transports,
  aaguid: verification.registrationInfo.aaguid,
});

await challengeStore.delete(`reg:${user.id}`);
```

Store the signature counter. On each authentication, reject credentials whose counter does not strictly increase—cloned authenticators often stall the counter.

## Authentication ceremony

Authentication is leaner: no user handle in the request if you use discoverable credentials—the browser shows an account picker.

```typescript
const options = await generateAuthenticationOptions({
  rpID: "acme.com",
  userVerification: "required",
  allowCredentials: userHasOnlyLegacy
    ? user.credentials.map((c) => ({ id: c.credentialId, transports: c.transports }))
    : undefined, // undefined => discoverable passkey UX
});

await challengeStore.set(`auth:${sessionId}`, options.challenge, { ttlSeconds: 90 });
```

After `navigator.credentials.get`, verify with `verifyAuthenticationResponse`, update the counter, rotate session, and invalidate any pre-auth session fixation risk by issuing a fresh server-side session ID.

## Cross-device, sync, and enterprise friction

Apple iCloud Keychain and Google Password Manager sync passkeys across devices tied to the same vendor account. That improves UX but shifts trust to the user's cloud account. Document this in your security FAQ.

**Cross-device sign-in** (phone signs into desktop via QR) requires supported browsers and is still uneven on older Android WebViews. Test on real devices, not only desktop Chrome.

Enterprise managed devices may block platform authenticators or mandate smart cards. Offer a parallel WebAuthn path with `allowCredentials` populated from enrolled security keys, and keep a break-glass SSO option for IT-controlled fleets.

## Rollout sequence that survives audit

1. **Internal dogfood** — staff accounts on production RP ID, not a staging hostname.
2. **Opt-in enrollment** — settings page after password login; measure completion funnel drop-offs by platform.
3. **Conditional UI** — use `mediation: "conditional"` on login fields so passkeys appear inline without a separate button maze.
4. **Step-up for sensitive actions** — re-auth with WebAuthn before payout, API key creation, or account deletion even if session is fresh.
5. **Password sunset** — only after recovery paths are tested and enrollment exceeds your risk threshold (often 70–80% for consumer, lower for B2B with SSO).

Instrument these events: `passkey_register_started`, `passkey_register_failed` (with reason code, not raw browser errors), `passkey_auth_success`, `passkey_auth_failed`, `passkey_recovery_used`.

## Failure modes you will hit in week three

| Symptom | Likely cause | Fix |
|--------|--------------|-----|
| Works on Mac, fails on Windows | RP ID mismatch or wrong origin | Align apex/www; fix `expectedOrigin` list |
| "No credentials" on login | Non-resident key or wrong `allowCredentials` | Re-enroll with resident keys; enable discoverable flow |
| Counter verification errors | Backup restore or cloned key | Force re-enrollment; alert security |
| Infinite spinner on Android | WebView without WebAuthn | Detect and fall back to password + email magic link |
| Users locked out after device loss | No recovery path | Backup codes + verified support flow |

## Operational checklist

- Run quarterly DR tests: restore credential DB, verify ceremonies still work.
- Rotate nothing about the key material—you rotate sessions and challenges, not passkeys.
- Log ceremony outcomes with correlation IDs; never log challenges or public key bytes in client analytics.
- Put WebAuthn endpoints on the same latency SLO as password login; slow ceremonies feel broken on mobile.

Passkeys reward teams that treat WebAuthn as protocol engineering: explicit RP ID strategy, single-use challenges, counter discipline, and a recovery story that does not secretly reintroduce passwords through the back door.

## Resources

- [WebAuthn Level 2 Specification (W3C)](https://www.w3.org/TR/webauthn-2/)
- [FIDO Alliance Passkeys documentation](https://fidoalliance.org/passkeys/)
- [SimpleWebAuthn server library](https://simplewebauthn.dev/docs/packages/server)
- [MDN: Web Authentication API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API)
- [Google Identity: Passkeys implementation guide](https://developers.google.com/identity/passkeys)
