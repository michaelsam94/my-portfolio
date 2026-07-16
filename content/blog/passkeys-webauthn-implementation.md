---
title: "Implementing Passkeys and WebAuthn"
slug: "passkeys-webauthn-implementation"
description: "A hands-on guide to implementing passkeys with WebAuthn: registration and authentication flows, synced vs device-bound credentials, and safe fallbacks."
datePublished: "2026-07-04"
dateModified: "2026-07-04"
tags: ["Authentication", "WebAuthn", "Passkeys", "Security"]
keywords: "passkeys, WebAuthn, passwordless, FIDO2, authentication, credential management, public key credential"
faq:
  - q: "What is the difference between a passkey and WebAuthn?"
    a: "WebAuthn is the W3C browser API and protocol for public-key authentication; FIDO2 is the broader spec it's part of. A passkey is a WebAuthn credential — specifically the modern, often cloud-synced kind that can roam across a user's devices. Passkeys are the user-facing product; WebAuthn is the API you build on."
  - q: "Are passkeys phishing-resistant?"
    a: "Yes, and that's the main reason to adopt them. A passkey is cryptographically bound to the origin it was created for, so it simply won't work on a look-alike phishing domain. There's no shared secret to steal, no code to relay, so credential phishing attacks that beat passwords and OTPs don't work against passkeys."
  - q: "What happens if a user loses the device with their passkey?"
    a: "Synced passkeys (via iCloud Keychain, Google Password Manager, etc.) survive device loss because they're backed up to the user's cloud account and restore on a new device. Device-bound passkeys don't roam, so you must let users register multiple credentials and provide a recovery path for account access."
---

Passwords are the vulnerability we keep shipping on purpose. They get phished, reused, leaked in breaches, and stuffed into other accounts — and no amount of complexity rules fixes the fundamental problem that a password is a shared secret the user has to hand over to prove who they are. Passkeys remove the shared secret entirely. The user's device holds a private key that never leaves it, and authentication is a cryptographic challenge-response bound to your exact domain. Implementing passkeys with WebAuthn is how you actually get there in a browser.

I've wired WebAuthn into a couple of products, and the concepts are simpler than the API surface suggests once you see the two "ceremonies" clearly. Let me walk through both.

## The mental model: two ceremonies

WebAuthn has exactly two flows, and everything else is detail.

- **Registration (attestation):** the user's authenticator generates a new key pair, keeps the private key, and hands your server the public key. You store it against the user.
- **Authentication (assertion):** your server sends a random challenge, the authenticator signs it with the private key, and you verify the signature with the stored public key.

The private key never touches the wire. The server only ever sees public keys and signatures. That single property is why passkeys are phishing-resistant: the credential is bound to your origin, so a look-alike domain can't trigger it, and there's no secret to relay.

## Registration, step by step

The server starts by issuing registration options — critically, a fresh random `challenge` you store server-side to verify later:

```js
// Server: create registration options
const options = await generateRegistrationOptions({
  rpName: "Acme",
  rpID: "acme.com",
  userName: user.email,
  userID: user.id,
  attestationType: "none",           // don't demand attestation unless you must
  authenticatorSelection: {
    residentKey: "required",          // discoverable credential = passkey
    userVerification: "preferred",
  },
});
await store.saveChallenge(user.id, options.challenge);
```

The browser then invokes the platform authenticator, which prompts the user for biometrics or a PIN and creates the credential:

```js
// Browser
const credential = await navigator.credentials.create({
  publicKey: optionsFromServer,
});
// send credential back to the server to verify + store
```

Back on the server, verify the response against the stored challenge and your expected origin, then persist the credential ID, public key, and signature counter:

```js
const verification = await verifyRegistrationResponse({
  response: credentialFromBrowser,
  expectedChallenge: savedChallenge,
  expectedOrigin: "https://acme.com",
  expectedRPID: "acme.com",
});
if (verification.verified) {
  await store.saveCredential(user.id, verification.registrationInfo);
}
```

Do not hand-roll the CBOR/COSE parsing and signature verification. Use a maintained library — SimpleWebAuthn (JS), and the equivalents on other stacks — because the parts you'd get wrong are exactly the security-critical parts.

## Authentication mirrors it

Authentication is the same shape in reverse: issue a challenge, let the authenticator sign it, verify the signature against the stored public key.

```js
// Server issues a challenge; browser signs it
const options = await generateAuthenticationOptions({ rpID: "acme.com" });
// ... navigator.credentials.get({ publicKey }) on the browser ...
const verification = await verifyAuthenticationResponse({
  response, expectedChallenge, expectedOrigin: "https://acme.com",
  expectedRPID: "acme.com", credential: storedCredential,
});
```

With **discoverable credentials** (resident keys), the user doesn't even type a username — the authenticator offers the accounts it holds for your origin, and they pick one. That's the "just tap your face/finger and you're in" experience people associate with passkeys.

## Synced vs device-bound: the decision that shapes recovery

This is the design choice that trips teams up. Passkeys come in two flavors:

| Type | Roams across devices | Survives device loss | Typical use |
|---|---|---|---|
| Synced | Yes (cloud keychain) | Yes | Consumer sign-in |
| Device-bound | No | No | High-assurance, hardware keys |

**Synced passkeys** (iCloud Keychain, Google Password Manager, and cross-provider syncing) back up to the user's cloud account and restore on a new device. For consumer products this is what you want — it solves the "lost phone = locked out" problem that killed earlier passwordless attempts.

**Device-bound passkeys** never leave the authenticator, which is stronger for high-assurance scenarios but means losing the device loses the credential. If you use these, you *must* let users register multiple authenticators and provide account recovery.

Either way, the rule holds: **let users register more than one passkey**, and always have a recovery path. A single credential with no backup is a support-ticket generator.

## Fallbacks and rollout

Nobody flips the whole user base to passwordless overnight. The realistic path:

1. **Add passkeys alongside passwords.** Offer passkey registration in account settings; let users opt in. Watch adoption before you push harder.
2. **Prompt at the right moments.** Offer to create a passkey right after a successful password login — the user's already authenticated and engaged.
3. **Keep a fallback**, but a good one. Falling back to SMS OTP undoes the phishing resistance you just gained; prefer an email magic link or another registered passkey. If you must keep passwords, don't let a weak reset flow become the new attack surface.

On mobile, passkeys tie into platform credential managers directly, and it fits naturally with a broader [zero-trust posture for mobile apps](https://blog.michaelsam94.com/zero-trust-mobile-apps/) — device-bound cryptographic identity is a strong signal. If you're storing anything sensitive locally alongside this, the same care I've written about for [Android Keystore and encrypted storage](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/) applies.

## The gotchas I've hit

**RP ID mismatches.** The `rpID` must match your domain, and it interacts with subdomains in ways that will silently break credentials if you get it wrong. Nail this down before you have real users with registered passkeys, because changing it later orphans them.

**Challenge reuse.** The challenge must be random, single-use, and verified server-side. Skipping this reintroduces replay attacks — the whole point of the ceremony is that the challenge is fresh.

**Signature counter handling.** WebAuthn includes a counter to detect cloned authenticators. Synced passkeys often report zero, so treat a non-incrementing counter as informational rather than hard-failing, or you'll lock out legitimate synced users.

**Testing across platforms.** Behavior differs across Safari/iOS, Chrome/Android, and desktop. Test on real devices; the emulator experience lies.

## Worth doing

Passkeys are the rare security upgrade that also improves UX — users tap a fingerprint instead of remembering a password, and you delete an entire class of attacks from your threat model. Build on WebAuthn with a solid library, default to synced passkeys for consumers, let users register multiple credentials, keep a phishing-resistant recovery path, and roll out alongside passwords before you retire them. The API looks intimidating for about a day; the two-ceremony model is the whole thing.

## Resources

- [W3C — Web Authentication (WebAuthn) Level 3](https://www.w3.org/TR/webauthn-3/)
- [passkeys.dev — developer guide](https://passkeys.dev/)
- [SimpleWebAuthn — libraries and docs](https://simplewebauthn.dev/)
- [FIDO Alliance — passkeys](https://fidoalliance.org/passkeys/)
- [MDN — Web Authentication API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Authentication_API)
- [OWASP — Authentication cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
