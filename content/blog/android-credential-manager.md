---
title: "Sign-In with Credential Manager on Android"
slug: "android-credential-manager"
description: "Credential Manager on Android unifies passkeys, passwords, and Sign in with Google behind one Jetpack API, replacing the fragmented sign-in libraries of the past."
datePublished: "2026-03-12"
dateModified: "2026-03-12"
tags: ["Android", "Security", "Authentication"]
keywords: "Credential Manager, passkeys Android, sign in with Google, Android authentication, credential API"
faq:
  - q: "What is Credential Manager on Android?"
    a: "Credential Manager is a Jetpack API that unifies multiple sign-in methods — passkeys, saved passwords, and federated options like Sign in with Google — behind a single interface. Instead of integrating separate SDKs for each, you make one getCredential call and the system presents the user a unified bottom sheet showing every credential they have for your app, then returns whichever one they choose."
  - q: "How does Credential Manager relate to passkeys?"
    a: "Credential Manager is the recommended way to create and use passkeys on Android. You call createCredential with a CreatePublicKeyCredentialRequest to register a passkey and getCredential with a GetPublicKeyCredentialOption to authenticate, passing the WebAuthn JSON from your server. The system handles biometric prompts and secure storage, so your app never touches raw key material."
  - q: "Do I still need the old Google Sign-In and Smart Lock libraries?"
    a: "No, those are deprecated in favor of Credential Manager. Sign in with Google now goes through the Credential Manager API using the Google ID helper, and saved-password autofill via Smart Lock is subsumed by the password credential type. New apps should build on Credential Manager directly, and existing apps should plan a migration off the legacy SDKs."
---

Not long ago, adding sign-in to an Android app meant stitching together three unrelated things: the Google Sign-In SDK for federated login, Smart Lock for saved passwords, and whatever bespoke flow you'd built for your own credentials. Each had its own callbacks, its own UI, its own edge cases. Credential Manager collapses all of that into one Jetpack API. You make a single `getCredential` call and the system shows the user a unified sheet with every credential they have for your app — a passkey, a saved password, a Google account — and hands back whichever they pick.

More importantly, it's the sanctioned path to passkeys on Android. If you care about moving users off passwords and onto phishing-resistant authentication — and you should — Credential Manager is the API that gets you there without touching raw cryptographic material.

## Why the old world was painful

The fragmentation wasn't just annoying, it produced worse UX. A returning user might have a saved password *and* a Google login, and the two libraries didn't know about each other, so the app had to guess which button to emphasize or show both and hope. Meanwhile passkeys — the actually important development — had no clean integration point in the old stack. Every team I know that tried to support all three methods ended up with a tangle of conditional flows that was hard to test and easy to break.

Credential Manager fixes this by making the *system* the arbiter. It knows all the credentials the user has for your app across types, presents them in one place, and lets the user choose. Your app stops orchestrating competing SDKs and instead asks one question: "which of your credentials do you want to use?"

## The core flow

Authentication is a single request that can span multiple credential types. You build the options you support and call `getCredential`:

```kotlin
val credentialManager = CredentialManager.create(context)

val request = GetCredentialRequest.Builder()
    .addCredentialOption(GetPasswordOption())
    .addCredentialOption(
        GetPublicKeyCredentialOption(requestJson = serverAuthChallengeJson)
    )
    .addCredentialOption(
        GetSignInWithGoogleOption.Builder(serverClientId).build()
    )
    .build()

try {
    val response = credentialManager.getCredential(context, request)
    when (val cred = response.credential) {
        is PublicKeyCredential -> sendPasskeyToServer(cred.authenticationResponseJson)
        is PasswordCredential  -> signInWithPassword(cred.id, cred.password)
        is CustomCredential    -> handleGoogleIdToken(cred)
    }
} catch (e: GetCredentialException) {
    // User cancelled, or no credentials — fall through to sign-up
}
```

That's the whole thing. One call, a `when` over the credential type, and the system handled the UI, the biometric prompt for the passkey, and the account chooser. Compare that to three SDKs and their three callback shapes and the appeal is obvious.

## Passkeys: the part that actually matters

Passwords are a liability — reused, phished, leaked. Passkeys, built on WebAuthn/FIDO2, are the fix, and Credential Manager is how you create and use them. Registration mirrors authentication:

```kotlin
val createRequest = CreatePublicKeyCredentialRequest(
    requestJson = serverRegistrationOptionsJson // from your server's WebAuthn ceremony
)
val result = credentialManager.createCredential(context, createRequest)
    as CreatePublicKeyCredentialResponse
sendRegistrationResponseToServer(result.registrationResponseJson)
```

The critical thing to understand: **Credential Manager is the client half of a WebAuthn ceremony, not the whole thing.** Your server generates the registration and authentication options (challenge, relying party ID, allowed credentials) and verifies the signed responses. The Android API shuttles that JSON to and from the platform authenticator and triggers biometrics. If you want the full server-side picture — challenge generation, attestation, relying party configuration — that lives in the same standard covered in [passkeys and WebAuthn implementation](https://blog.michaelsam94.com/passkeys-webauthn-implementation/). Get the server ceremony right first; the Android integration is the easy half.

One deployment detail that trips people up: passkeys require **Digital Asset Links** so the platform can associate your app with your web domain (the relying party). If the `assetlinks.json` on your domain doesn't list your app's signing certificate, passkey creation fails with an error that doesn't obviously point at the cause. Set that up early.

## Credential types at a glance

| Credential type | Backing tech | User experience |
| --- | --- | --- |
| Passkey | WebAuthn / FIDO2 | Biometric prompt, phishing-resistant, no shared secret |
| Password | Saved credentials | Autofilled from provider, still a shared secret |
| Sign in with Google | Google ID token | Account chooser, federated identity |

My opinionated ranking: lead with passkeys, keep password support for users who haven't migrated, and offer Sign in with Google where it fits your product. The goal over time is to nudge everyone to passkeys and let password support wither. Credential Manager makes that gradual migration natural because all three coexist in one sheet — you don't have to force a hard cutover.

## Security responsibilities you still own

Credential Manager handles the credential *ceremony* safely — you never see raw private keys, and biometrics gate access. But it doesn't absolve you of the rest of your security posture:

- **Verify on the server.** A passkey assertion or Google ID token is only trustworthy after your backend verifies the signature/token against the expected challenge and audience. Never trust the client's word that auth succeeded.
- **Protect tokens at rest.** Whatever session token you receive after sign-in needs safe local storage. That's the domain of [the Android Keystore and encrypted storage](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/) — put refresh tokens in the Keystore-backed store, not plain `SharedPreferences`.
- **Handle the no-credential path gracefully.** A `GetCredentialException` often just means a new user with nothing saved. Route them to sign-up, don't show an error.
- **Don't over-prompt.** Calling `getCredential` unprompted on every cold start annoys users. Trigger it on an explicit sign-in intent or when a session genuinely expires.

## Should you migrate now?

Yes, and with some urgency, because the legacy Google Sign-In and Smart Lock libraries are deprecated — they'll get maintenance at best, and new capabilities land only on Credential Manager. Beyond the deprecation pressure, the real reason is passkeys: there is no good non-deprecated way to offer them on Android without this API, and passkeys are the single biggest authentication upgrade available to a mobile app right now.

The migration itself is bounded. Replace the Google Sign-In calls with a `GetSignInWithGoogleOption`, fold saved passwords into `GetPasswordOption`, and add the passkey options once your server speaks WebAuthn. The client code shrinks — that's the pleasant surprise. I've done this migration on a production app and came out with *fewer* lines of auth code than I started with, plus passkeys we didn't have before. Front-load the server-side WebAuthn work and the asset links, and the Android side is a good week's work rather than a saga.

## Passkey hybrid transport

Users with passkey on phone signing into web need hybrid transport UI — Credential Manager surfaces QR/cable flow. Test sign-in on Chrome desktop + Android phone pair; fallback to password must not loop infinitely on cancel.

## Provider configuration priority

Multiple password managers register — `CredentialManager.create(context)` picks default; expose in-app settings to open provider chooser when enterprise mandates specific vault.

## Resources

- [Credential Manager — Android docs](https://developer.android.com/training/sign-in/credential-manager)
- [Passkeys on Android](https://developer.android.com/training/sign-in/passkeys)
- [Sign in with Google via Credential Manager](https://developer.android.com/identity/sign-in/credential-manager-siwg)
- [WebAuthn specification (W3C)](https://www.w3.org/TR/webauthn-2/)
- [FIDO Alliance passkeys resources](https://fidoalliance.org/passkeys/)
- [Digital Asset Links](https://developers.google.com/digital-asset-links)
