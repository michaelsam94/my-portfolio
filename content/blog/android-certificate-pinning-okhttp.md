---
title: "Certificate Pinning with OkHttp Without Bricking Your App"
slug: "android-certificate-pinning-okhttp"
description: "Certificate pinning with OkHttp on Android: how CertificatePinner works, why you pin the SPKI hash of an intermediate, and how to rotate pins without a bricked release."
datePublished: "2024-08-16"
dateModified: "2024-08-16"
tags: ["Android", "Security", "Kotlin"]
keywords: "OkHttp certificate pinning, CertificatePinner, SPKI pin, SSL pinning Android, pin rotation, backup pin"
faq:
  - q: "Should I pin the leaf certificate or an intermediate?"
    a: "Pin the Subject Public Key Info (SPKI) hash of an intermediate CA you control the relationship with, or the leaf's public key if it's long-lived, and always include a backup pin. Pinning the leaf alone means every routine certificate renewal breaks your app unless the key is reused. Pinning a stable intermediate survives leaf rotation while still narrowing trust well below the full CA set."
  - q: "How do I rotate certificate pins without bricking installed apps?"
    a: "Ship at least two pins at all times: the current one and a backup whose private key is already generated and stored offline. When you rotate, the new certificate matches the pre-shipped backup pin, so already-installed apps keep working. Never ship a single pin, because the day that certificate changes, every app in the field that can't update immediately is bricked."
  - q: "Does OkHttp certificate pinning protect against a compromised device?"
    a: "No. Pinning defends against man-in-the-middle attacks using fraudulently issued or intercepting certificates, such as a corporate proxy or a rogue CA. It does nothing against an attacker who controls the device and can hook OkHttp with Frida or patch the pins out of your APK. It's a transport-integrity control, not a device-integrity one."
---

Certificate pinning with OkHttp is one of those features that's five lines to enable and a support nightmare to get wrong. The five lines: give OkHttp a `CertificatePinner` with the public-key hash of the certificate you expect, and it will refuse any TLS connection whose chain doesn't include a matching key — even if the system trust store says the chain is valid. That's the whole point: you're narrowing trust from "any of the ~150 CAs Android trusts" down to "the specific key I expect," which kills man-in-the-middle attacks that rely on a rogue or intercepting CA.

The nightmare is the day your certificate rotates, every app in the field with the old pin can't connect, and you can't push an update fast enough. I've watched a team do exactly this. So this post is as much about *rotation discipline* as it is about the API.

## The API is deceptively simple

```kotlin
val pinner = CertificatePinner.Builder()
    .add(
        "api.example.com",
        "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", // current
        "sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=", // backup
    )
    .build()

val client = OkHttpClient.Builder()
    .certificatePinner(pinner)
    .build()
```

Two things to notice. The `sha256/...` value is the base64 of the SHA-256 hash of the certificate's **Subject Public Key Info (SPKI)** — not the whole certificate, not the fingerprint you see in a browser. Pinning the SPKI (the public key) rather than the full certificate matters because it survives a certificate reissue that reuses the same key. And I've added **two** pins on purpose. Never ship one.

## Pin the public key, and pin the right level in the chain

You can pin at three levels, and the choice is a trade-off between safety and blast radius:

- **Leaf certificate** — tightest, but breaks on every renewal unless you deliberately reuse the key pair. High maintenance.
- **Intermediate CA** — the sweet spot for most apps. Leaf certificates rotate under the same intermediate, so routine renewals don't break you, while trust is still far narrower than the whole root store.
- **Root CA** — broadest; survives almost everything but barely improves on the default trust store.

I pin an intermediate I'm confident my CA will keep using, plus a backup that points at an alternate issuer or a pre-provisioned key. If you're on a managed platform where you don't control issuance cadence, intermediate pinning is the only sane choice.

Extract the SPKI pin without guessing — OkHttp will tell you. Point it at a host with a deliberately empty pin set and read the exception, or use the CLI:

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com \
  | openssl x509 -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64
```

## The rotation playbook that keeps you out of trouble

This is the part that actually prevents outages. Treat pins like keys you have to roll, because they are.

1. **Always have a live backup pin in the field.** The moment version N ships, it already trusts both the current key and a backup key whose private key you generated and locked away offline.
2. **When you rotate,** the new certificate uses the pre-shipped backup key, so every installed app — including ones that haven't updated in months — keeps connecting.
3. **In the same release that starts using the backup,** you add the *next* backup pin, so you're never down to a single point of failure.
4. **Set an expiry mindset.** Assume some users won't update for a year. Your pin set must remain valid for anyone running a release from the last ~12 months.

Skip step 1 and you're gambling that you can force-update the entire install base before the old certificate dies. You can't.

## Don't strand users: soft-fail and a kill switch

Pinning failures are terminal for the connection, so give yourself an escape hatch. I keep a server-controlled remote config flag that can disable pinning app-wide. It sounds heretical — turning off a security control remotely — but the alternative is a global outage with no recovery path short of an emergency app release. The flag is protected and audited; the ability to recover from a botched rotation is worth it.

For debug builds, I also relax pinning so QA can use a proxy like Charles or mitmproxy. This is where [network security configuration](https://blog.michaelsam94.com/android-network-security-config/) pairs nicely: use it to trust a debug CA only in debuggable builds, and keep pinning strict in release.

## What pinning does and doesn't buy you

Be honest about the threat model. Pinning defends the *transport*: it stops an attacker who can present a validly-chained-but-fraudulent certificate — a corporate TLS-intercepting proxy, a mis-issued cert, a compromised CA. That's a real and worthwhile class of attack.

It does **nothing** against an attacker who owns the device. Frida can hook `CertificatePinner.check()` and return unconditionally; a repackaged APK can strip the pins entirely. That's a different problem, addressed by [root and tampering detection](https://blog.michaelsam94.com/android-root-detection-tampering/) and Play Integrity, not by pinning. Don't let pinning lull you into thinking the channel is trustworthy on a rooted device — it isn't.

## The short version

Pin the SPKI hash of a stable intermediate, always ship a backup pin whose key is pre-provisioned, and treat rotation as a rolling, overlapping process rather than a swap. Keep a remote kill switch for emergencies, relax pinning only in debug builds, and remember that pinning secures the wire, not the device. Get the rotation discipline right and pinning is a quiet, effective control. Get it wrong and it's the reason your app can't reach the internet for a week.

## Pin rotation with backup pins

Ship two SPKI pins (production + next cert) before cert renewal — apps without backup pin brick until store update. OkHttp `CertificatePinner` failure messages must not leak pin hashes to user-visible error text.

## Debug vs release pin sets

Never ship debug pins in release manifest flavor — use `network_security_config` product flavor merge. Charles proxy for QA uses debug-only cleartext config, not pin disable in release.

## Certificate Pinning Okhttp Supplement 0 on Samsung and Pixel divergence

Exercise certificate pinning okhttp supplement 0 on Galaxy A-series and Pixel a-series — emulators hide OEM battery and storage quirks. Capture Macrobenchmark or Firebase trace for the critical path touching certificate; regressions above 8% block release for `android-certificate-pinning-okhttp-supplement-0`.

Document permission and background behavior in internal runbook: what breaks under Doze, what requires foreground service, and what Play policy declarations apply. Support tickets referencing "Certificate Pinning Okhttp Supplement 0" should map to a single runbook section with known workarounds.

## Okhttp regression gates for Play Vitals

Before promoting `android-certificate-pinning-okhttp-supplement-0` changes past 20% rollout, compare ANR rate, slow cold start, and excessive wakeups against seven-day baseline. Fail rollback review if 0 path shows >5% increase in `slow frames` without documented trade-off approval.

## Field testing certificate with battery saver enabled

Xiaomi and Oppo ship aggressive background killers. After implementing certificate pinning okhttp supplement 0, run 24-hour monkey test on three OEM devices with battery saver enabled. Failures here predict one-star reviews that Crashlytics never captures — especially for 0 flows that assume reliable background delivery.

## Resources

- [OkHttp CertificatePinner documentation](https://square.github.io/okhttp/features/https/)
- [OkHttp CertificatePinner API reference](https://square.github.io/okhttp/4.x/okhttp/okhttp3/-certificate-pinner/)
- [OWASP certificate and public key pinning](https://owasp.org/www-community/controls/Certificate_and_Public_Key_Pinning)
- [Android network security configuration](https://developer.android.com/privacy-and-security/security-config)
- [RFC 7469 — Public Key Pinning Extension for HTTP](https://datatracker.ietf.org/doc/html/rfc7469)
