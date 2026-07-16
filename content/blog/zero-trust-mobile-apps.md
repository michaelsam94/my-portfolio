---
title: "Zero Trust for Mobile Apps"
slug: "zero-trust-mobile-apps"
description: "How zero trust applies to mobile: device attestation with Play Integrity and App Attest, per-request identity, and why the client is never trusted — with real patterns."
datePublished: "2026-07-10"
dateModified: "2026-07-10"
tags: ["Mobile Security", "Zero Trust", "Android", "iOS"]
keywords: "zero trust, mobile security, device attestation, zero trust architecture, app security, Play Integrity, App Attest"
faq:
  - q: "What does zero trust mean for a mobile app?"
    a: "It means the backend treats every request from the app as untrusted until proven otherwise — verifying user identity, device integrity, and request context on each call rather than trusting a session because it once logged in. The mobile client holds no authority the server relies on."
  - q: "Can I trust Play Integrity or App Attest to stop tampering?"
    a: "They raise the bar significantly but aren't absolute. Device attestation tells you the app binary and device look genuine at attestation time; treat it as a strong signal in a risk decision, not a boolean gate, and always enforce it server-side."
  - q: "Is certificate pinning still worth it in 2026?"
    a: "Yes, but pin to a CA or intermediate rather than a leaf certificate so rotation doesn't brick your app, and always ship a backup pin. Pinning defends against intercepting proxies and mis-issued certificates; it's one layer, not the whole defense."
---

The core mistake in mobile security is treating the app as a trusted part of your system. It isn't. The app runs on a device you don't control, can be decompiled, patched, run on an emulator, or driven by a script hitting your API directly. Zero trust for mobile starts from that premise: **the client is hostile until each request proves otherwise**, and the server never depends on the app to enforce anything that matters.

I've built this into fintech and real-time systems where a spoofed request has real financial consequences. The mental shift is from "authenticate at login, then trust the session" to "verify identity, device integrity, and context on every meaningful request." Nothing the client asserts is taken at face value — not the user ID, not the price, not the "I'm a real device" claim.

## The client is an untrusted input source

Every value that originates on the device is attacker-controllable. That has direct consequences:

- **Never trust client-supplied prices, balances, or authorization decisions.** The server computes and enforces them. The app is a rendering layer over server truth.
- **Never ship a secret in the binary.** API keys, signing secrets, and encryption keys in the APK or IPA are extracted in minutes with `apktool` or Frida. If it's in the binary, assume it's public.
- **Validate every request server-side**, including ones the UI "prevents." The UI is a suggestion; the API is the boundary.

This sounds obvious, but I've reviewed apps where a `PATCH /account` accepted a `role` field straight from the client. Zero trust means that field is ignored server-side unless the caller is provably authorized.

## Device attestation: a strong signal, not a gate

Attestation answers "is this a genuine app on a genuine device?" On Android that's the [Play Integrity API](https://developer.android.com/google/play/integrity); on iOS it's App Attest and DeviceCheck. The app requests a signed verdict, sends it to your backend, and the backend verifies it with Google/Apple.

```kotlin
// Android — request an integrity token, then verify server-side
val manager = IntegrityManagerFactory.create(context)
val request = IntegrityTokenRequest.builder()
    .setNonce(serverNonce) // fresh, server-generated, single-use
    .build()
manager.requestIntegrityToken(request)
    .addOnSuccessListener { response ->
        api.submit(response.token()) // backend decodes and validates
    }
```

Two rules make attestation actually useful. First, **the nonce must come from your server and be single-use**, or an attacker records one valid token and replays it forever. Second, **decode and enforce the verdict on the backend** — the app can't be trusted to check its own integrity. Treat the result as a risk signal: a failed verdict on a login might trigger step-up auth; on a high-value transfer it might block outright. Binary gating frustrates legitimate users on rooted-but-honest devices, so weight it.

## Identity on every request

Sessions that are trusted for hours are a zero-trust anti-pattern. Use short-lived access tokens (5–15 minutes) with refresh tokens, and bind tokens to the device where you can. Better still, move toward phishing-resistant credentials — [passkeys and WebAuthn](https://blog.michaelsam94.com/passkeys-webauthn-implementation/) give you hardware-backed authentication that a stolen password database can't reproduce.

The backend re-establishes context per request: who is the user, is the token valid and unexpired, does this device match, is the request consistent with recent behavior. This is continuous verification, the heart of the [NIST zero trust architecture](https://csrc.nist.gov/pubs/sp/800/207/final) model applied to a phone.

## Protect data at rest and in transit

Zero trust doesn't stop at the API. On device:

- Store tokens and sensitive data in the platform keystore — Android Keystore / EncryptedSharedPreferences, iOS Keychain — never in plain `SharedPreferences` or `UserDefaults`. I go deep on this in [Android Keystore and encrypted storage](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/).
- Pin TLS to a CA or intermediate certificate with a backup pin, so you defend against intercepting proxies without risking a rotation that bricks the app.
- Assume screenshots, clipboard, and logs leak — keep secrets and PII out of all three.

## Putting it together

A zero-trust request on a sensitive mobile action looks like this end to end:

| Layer | What's verified | Where |
| --- | --- | --- |
| Transport | Pinned TLS, valid cert | Client + network |
| Identity | Short-lived token, device-bound | Server |
| Integrity | Play Integrity / App Attest verdict | Server |
| Authorization | Server-computed permissions | Server |
| Business rule | Amounts/limits recomputed | Server |

Notice how much lives on the server. That's deliberate — every check the client performs is a convenience for UX, and every check the server performs is the actual security boundary.

The payoff is resilience against the realistic attacks: a repackaged app, a scripted client hitting your API, a stolen token replayed from another device, an intercepting proxy. None of them get far when the server assumes the client is lying and verifies accordingly. Build from that assumption and the rest of your mobile security — [privacy engineering](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/), secrets, transport hardening — slots in as reinforcing layers rather than the whole wall.

## Resources

- [NIST SP 800-207 — Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final)
- [Android Play Integrity API](https://developer.android.com/google/play/integrity)
- [Apple App Attest and DeviceCheck](https://developer.apple.com/documentation/devicecheck)
- [OWASP Mobile Application Security (MAS)](https://mas.owasp.org/)
- [OWASP Mobile Top 10](https://owasp.org/www-project-mobile-top-10/)
- [Android security best practices](https://developer.android.com/privacy-and-security/security-tips)
