---
title: "Protecting Apps with the Play Integrity API"
slug: "android-play-integrity-api"
description: "Use the Play Integrity API to check device, app, and account integrity: how verdicts work, why you must verify server-side, and how to respond without locking out users."
datePublished: "2024-06-30"
dateModified: "2024-06-30"
tags: ["Android", "Security", "Play Integrity", "Anti-Abuse"]
keywords: "Play Integrity API, integrity verdict, device integrity, app integrity, SafetyNet replacement, attestation, server-side verification"
faq:
  - q: "What does the Play Integrity API actually tell me?"
    a: "It returns signed verdicts about three things: whether the request comes from a genuine, unmodified build of your app (app integrity), whether it runs on a genuine Android device with Play services (device integrity), and whether the user has a licensed Play account (account details). It does not identify the user or replace authentication — it's a signal about the environment and app authenticity that you fold into a risk decision."
  - q: "Why must Play Integrity verdicts be verified on the server?"
    a: "Because any check performed purely on the client can be patched out by an attacker who controls the device. The token is meant to be passed to your backend and either decrypted with your keys or verified via Google's servers, then acted on there. If you make the trust decision on-device, you've built security theater — the whole point is a verdict your server can trust about a client it can't."
  - q: "Is Play Integrity a replacement for SafetyNet Attestation?"
    a: "Yes. SafetyNet Attestation is deprecated and Play Integrity is its successor, with a broader set of verdicts and a standard and classic request model. If you still call SafetyNet, migrate — it's being wound down. Play Integrity also adds app-licensing and re-decryption options SafetyNet never had."
---

The Play Integrity API answers a question your backend genuinely cannot answer on its own: *is this request coming from an unmodified build of my app, running on a genuine Android device, from a licensed Play account?* It's the successor to the deprecated SafetyNet Attestation, and it returns signed verdicts you fold into anti-abuse and risk decisions — blocking cheating in a game, gating a high-value transaction, throttling bot-driven account creation. The one rule that matters more than any other: **the verdict is only meaningful if your server verifies and acts on it.** Anything you decide on-device, an attacker who controls that device can patch out. Play Integrity is a tool for teaching your *server* to distrust clients intelligently, not for the client to vouch for itself.

## What the verdicts mean

An integrity response contains a few distinct signals, and conflating them is a common design error:

- **App integrity** (`appRecognitionVerdict`): is this the exact app binary that Play distributed, unmodified, and installed/updated by Play? Catches repackaged or tampered APKs.
- **Device integrity** (`deviceRecognitionVerdict`): is this a genuine Android device passing integrity checks, with Google Play services? Values distinguish a fully trusted device from a basic one from an emulator/rooted environment.
- **Account details** (`appLicensingVerdict`): does the user have a licensed entitlement (installed/paid for via Play)?

Each is a separate axis. A request can come from your genuine app on a rooted device, or a tampered app on a genuine device. Decide per axis what you tolerate for a given action.

## The request flow

There are two request models. The **standard** request is the modern default — lower latency, uses Play-managed token caching, suited to frequent checks. The **classic** request is for one-off, high-value checks where you generate a fresh nonce. A standard request looks like:

```kotlin
val manager = IntegrityManagerFactory.createStandard(context)

val tokenProvider = manager.prepareIntegrityToken(
    PrepareIntegrityTokenRequest.builder()
        .setCloudProjectNumber(CLOUD_PROJECT_NUMBER)
        .build()
)

// Later, when you need a verdict for a specific action:
tokenProvider.request(
    StandardIntegrityTokenRequest.builder()
        .setRequestHash(hashOf(requestPayload))   // binds token to this request
        .build()
).addOnSuccessListener { response ->
    val token = response.token()
    sendToBackend(token)     // <-- the important part
}
```

The `requestHash` binds the token to the specific request payload, which prevents an attacker from replaying a valid token against a different request. Always set it to a hash of the operation you're protecting.

## Server-side verification is the whole point

The client gets an opaque, signed token. Your backend then either:

1. Sends it to Google's Play Integrity endpoint to decode it, or
2. Decrypts it locally with response encryption keys you manage.

Either way, **the decode and the decision happen on your server**, over a channel the client can't tamper with. Then you read the verdicts and apply your risk policy server-side. The anti-pattern — decode-on-device, then tell the server "trust me, I'm legit" — is worthless, because the attacker owns the device and can make it say anything. This is the same principle behind not trusting the client anywhere in your trust boundary, the core of a [zero-trust posture for mobile apps](https://blog.michaelsam94.com/zero-trust-mobile-apps/): the server verifies, the client asserts nothing on its own authority.

## Respond proportionally — don't hard-block everyone

The biggest real-world mistake isn't technical, it's product judgment: treating any imperfect verdict as "block." Integrity signals are probabilistic and the population of *legitimate* users on rooted phones, custom ROMs, or devices without Play services is larger than security-minded engineers expect. Hard-blocking them generates support tickets, one-star reviews, and lost revenue.

A tiered response works far better:

| Verdict strength | Example response |
|---|---|
| Strong (genuine device + app + license) | Allow, no friction |
| Weak device signal | Allow but add a step-up (2FA, extra check) for sensitive actions |
| Tampered app / failed app integrity | Block the sensitive action; app authenticity failing is a strong signal |
| Repeated abuse patterns + weak signals | Rate-limit, shadow-restrict, or flag for review |

Reserve hard blocks for the signals you actually trust as adversarial — a failed *app integrity* verdict (tampered binary) is a much stronger reason to block a transaction than a merely "basic" device verdict. Match the severity of your response to the confidence of the signal and the value of the action.

## Where it fits, and where it doesn't

Play Integrity is a *risk signal*, not authentication and not DRM. It tells you about the environment; it does not tell you *who* the user is — that's still your auth layer's job (and something like [OAuth with PKCE](https://blog.michaelsam94.com/oauth-pkce-mobile/) handles). It won't stop a determined attacker on a genuine device from abusing a legitimately-signed app through your API; it raises the cost of the easy attacks (emulator farms, repackaged APKs, rooted bot devices) and gives your server a signal to layer with rate limiting, anomaly detection, and step-up auth.

Good uses: gating in-app purchases and unlocks, protecting game leaderboards from cheats, throttling bulk account creation, and adding friction to high-value or fraud-prone flows. Bad uses: as your *only* line of defense, or as a blunt instrument that bricks the app for anyone whose device doesn't score perfectly.

## Practical rollout advice

Roll it out in *monitor mode* first: collect verdicts server-side, log the distribution, and see what fraction of your real traffic falls into each bucket *before* you enforce anything. You'll almost always find the "suspicious" population is bigger than you feared, and you'll calibrate thresholds against reality instead of guesses. Then enforce gradually, starting with the highest-value actions and the strongest signals. Migrate off SafetyNet if you haven't — it's deprecated — and remember to rotate and protect the keys your server uses to decode tokens, since those keys are what make the whole chain trustworthy.

Play Integrity earns its place when you treat it as one weighted input to a server-side risk decision, respond in proportion to confidence, and never let it lock out the legitimate users who happen to run unusual devices.

## Resources

- [Play Integrity API overview](https://developer.android.com/google/play/integrity)
- [Integrity verdicts and their meaning](https://developer.android.com/google/play/integrity/verdicts)
- [Standard vs classic requests](https://developer.android.com/google/play/integrity/standard)
- [Verify integrity tokens server-side](https://developer.android.com/google/play/integrity/verdicts#decrypt-verify)
- [OWASP MASVS — mobile app security verification](https://mas.owasp.org/MASVS/)
