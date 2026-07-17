---
title: "Debugging Android App Links Verification"
slug: "android-app-links-verification-debug"
description: "Why Android App Links fail to verify and how to fix them: assetlinks.json, SHA-256 fingerprints, the verification state commands, and common production traps."
datePublished: "2024-09-16"
dateModified: "2024-09-16"
tags: ["Android", "Deep Linking", "DevOps", "Security"]
keywords: "Android App Links verification, assetlinks.json, autoVerify, Digital Asset Links, App Links not opening, SHA-256 fingerprint"
faq:
  - q: "Why are my Android App Links not verifying?"
    a: "The most common causes are a missing or malformed assetlinks.json at the domain root, a SHA-256 fingerprint that does not match the signing key used for the installed build, a redirect or non-200 response when fetching the file, or the wrong package name. Verification is all-or-nothing per domain, so one bad fingerprint or a single unreachable host fails the whole domain."
  - q: "How do I check App Links verification status on a device?"
    a: "Use adb shell pm get-app-links your.package.name to see each declared host and its verification state — verified, none, or a failure code. You can force a re-verification with adb shell pm verify-app-links and reset the state during testing with pm set-app-links so you are not fighting cached results."
  - q: "What SHA-256 fingerprint goes in assetlinks.json?"
    a: "It must be the SHA-256 of the certificate that actually signs the installed build. For Play-distributed apps that means the Play App Signing key, not your upload key, so copy the fingerprint from the Play Console. If you also test debug builds, include the debug keystore fingerprint too, since each signing key needs its own entry."
---

When Android App Links won't verify, the cause is almost always one of four things: a missing or malformed `assetlinks.json`, a SHA-256 fingerprint that doesn't match the key signing the *installed* build, a non-200 or redirected response when the system fetches the file, or a mismatched package name. Verification is strict and all-or-nothing per domain — one wrong fingerprint or one unreachable host and the whole domain stays unverified, which is why "it works for my colleague but not me" is such a common and maddening report.

I've chased this bug across three apps, and the fix is never clever — it's methodical. Here's the debugging order that gets you there fastest.

## Understand what verification actually checks

App Links (as opposed to plain deep links) let your app open `https://` URLs *without* a disambiguation chooser, because Android has cryptographically verified that you own the domain. The verification is a handshake: your manifest declares `android:autoVerify="true"` on an intent filter for the domain, and your domain hosts a Digital Asset Links file at `https://yourdomain.com/.well-known/assetlinks.json` that names your app's package and signing fingerprint. At install (and periodically after), Android fetches that file and checks the two sides agree.

So a verification failure means one side of the handshake is wrong. The debugging is just figuring out which.

## Step 1: read the actual state on device

Don't guess — ask the system. This command prints every declared host and its verification state:

```bash
adb shell pm get-app-links your.package.name
```

You'll see each domain marked `verified`, `none`, or with a legacy status. If a host says `none` or shows a failure, that's your target. During testing, cached failure states cause confusion, so reset and re-run verification explicitly:

```bash
# Reset stored state for the package
adb shell pm set-app-links --package your.package.name 0 all
# Trigger verification again
adb shell pm verify-app-links --re-verify your.package.name
```

This alone resolves a lot of "I fixed it but it still fails" situations, because the device was holding a stale failed result.

## Step 2: verify the assetlinks.json is fetchable and correct

The single most common production cause is the file itself. Fetch it exactly as Android would:

```bash
curl -sSL https://yourdomain.com/.well-known/assetlinks.json
```

Check all of these:

- **HTTP 200, no redirect.** Android will not follow a redirect from `http` to `https` or from apex to `www` for this fetch. The file must return 200 directly at `https://yourdomain.com/.well-known/assetlinks.json`. A `301` to `www` is a classic silent failure.
- **`Content-Type: application/json`.** Some CDNs serve it as `text/plain` or, worse, an HTML 404 page with a 200 status.
- **Valid JSON**, no BOM, no trailing junk.
- **Every host you declare is covered.** If you support `example.com` and `www.example.com`, both need to serve a valid file (or resolve to the same one).

## Step 3: match the fingerprint to the installed build

This is the trap that burns the most hours. The `sha256_cert_fingerprints` in the file must match the certificate that *actually signed the APK on the device*. For an app distributed through Play with Play App Signing enabled, that's the **Play signing key**, not your upload key. People put their upload-key fingerprint in the file, test a Play build, and it never verifies.

Get the right fingerprints:

```bash
# Debug keystore (local testing builds)
keytool -list -v -keystore ~/.android/debug.keystore \
  -alias androiddebugkey -storepass android -keypass android

# From Play Console: App integrity > App signing > SHA-256 certificate fingerprint
```

Then include *every* signing key that might sign an installed build — debug, upload, and Play — as separate entries:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "com.example.app",
    "sha256_cert_fingerprints": [
      "AB:CD:...:debug",
      "12:34:...:play"
    ]
  }
}]
```

If you test a debug build, the debug fingerprint must be present or that build won't verify — which explains why the Play build works but your local one doesn't, or vice versa.

## Step 4: sanity-check the manifest

The app side is smaller but has its own gotchas. The intent filter needs `autoVerify` on the filter that handles the `https` scheme, correct host, and both `BROWSABLE` and `DEFAULT` categories:

```xml
<intent-filter android:autoVerify="true">
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="https" android:host="example.com" />
</intent-filter>
```

Two things: `autoVerify` only needs to be on *one* filter per domain, but I keep it explicit; and the `host` must match the domain in your assetlinks exactly. A `www` mismatch here is another silent failure.

## The failure-cause cheat sheet

| Symptom | Likely cause |
| --- | --- |
| Works on debug, fails on Play (or reverse) | Wrong / missing signing fingerprint |
| Chooser appears instead of direct open | Domain not verified — check `get-app-links` |
| File returns HTML or 404 | Path wrong or CDN serving error page |
| Verifies for apex, not `www` | Missing file/entry for the subdomain |
| Fixed it, still fails | Stale state — reset with `set-app-links` |

## The Play Console shortcut

Beyond the manual grind, Play Console surfaces App Links status under the app's setup section, flagging domains that fail to verify with the reason. On a Play-distributed app I check there first — it often names the exact problem (fingerprint mismatch, unreachable file) faster than the device commands. Treat it as a second opinion alongside `pm get-app-links`.

Deep links are also a security surface: an over-broad intent filter or a link handler that trusts unvalidated URL parameters can be abused, so validate everything a link carries before acting on it, the same input-trust discipline that applies across [Android security](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) work.

## What I'd take away

App Links verification failures are boring and systematic, so debug them systematically. Read the real state with `adb shell pm get-app-links` instead of guessing, and reset stale state so you're not fighting a cached failure. Fetch `assetlinks.json` with curl to confirm it returns a clean 200 with valid JSON and no redirect, covering every host you declare. Above all, match the SHA-256 fingerprint to the key that actually signs the *installed* build — for Play apps that's the Play App Signing key — and include every relevant signing key. Get the file reachable and the fingerprints right, and verification stops being mysterious.

## adb verification state machine

```bash
adb shell pm get-app-links com.example.app
adb shell pm verify-app-links --re-verify com.example.app
```

`legacy_failure` often means wrong SHA256 in assetlinks.json vs Play signing key — use Play App Signing certificate fingerprint, not upload key.

## Subdomain delegation

Each host needs own assetlinks or `delegate_permission/common.handle_all_urls` — marketing `www` vs `app` subdomain mismatch breaks auto-verify silently.

## Resources

- [Verify Android App Links (Android developers)](https://developer.android.com/training/app-links/verify-android-applinks)
- [Add Android App Links](https://developer.android.com/training/app-links)
- [Digital Asset Links specification](https://developers.google.com/digital-asset-links/v1/getting-started)
- [Handling Android App Links](https://developer.android.com/training/app-links/deep-linking)
