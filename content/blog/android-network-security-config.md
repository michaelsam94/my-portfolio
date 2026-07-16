---
title: "Android Network Security Configuration, Explained by Example"
slug: "android-network-security-config"
description: "Android network security configuration: use declarative XML to enforce cleartext blocking, trust anchors, debug overrides, and pinning without touching app code."
datePublished: "2024-08-17"
dateModified: "2024-08-17"
tags: ["Android", "Security"]
keywords: "network security configuration, cleartextTrafficPermitted, debug-overrides, trust anchors, Android TLS, base-config domain-config"
faq:
  - q: "What does Android network security configuration do?"
    a: "It's a declarative XML file that lets you control your app's network trust behavior without writing code: block cleartext HTTP, restrict which CAs are trusted per domain, add debug-only trust anchors, and even declare certificate pins. The system enforces it across OkHttp, HttpURLConnection, and most networking libraries automatically, which is why it's more reliable than scattering trust logic through your code."
  - q: "Does cleartext traffic get blocked by default on Android?"
    a: "Yes, from Android 9 (API 28) onward, cleartext HTTP is disabled by default for apps targeting that level or higher. Any plain http:// request throws an exception unless you explicitly opt back in via network security configuration for specific domains. This default is a deliberate push toward HTTPS everywhere."
  - q: "Can I trust a custom CA only in debug builds?"
    a: "Yes, that's exactly what the debug-overrides element is for. It only takes effect when android:debuggable is true, so you can trust a proxy or test CA (for Charles, mitmproxy, or an internal QA server) without ever weakening security in your release build. The overrides are ignored entirely in production."
---

Android network security configuration is the most underused security feature in the platform: a single XML file that controls your app's TLS trust behavior declaratively, enforced by the system across almost every networking path without you writing a line of code. Instead of sprinkling `TrustManager` hacks and cleartext exceptions through your codebase, you describe the policy once — block cleartext, trust these CAs for this domain, add a debug-only test CA — and the framework applies it to OkHttp, Retrofit, `HttpURLConnection`, and WebViews alike.

I reach for it before I reach for code-level TLS customization, because code-level trust changes are easy to get subtly, catastrophically wrong (the classic "trust all certificates" `TrustManager` that ships to production). The config file is harder to misuse and easier to review.

## Wire it up

Declare it in the manifest, then create the XML in `res/xml/`:

```xml
<!-- AndroidManifest.xml -->
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
```

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

That `base-config` above says: no cleartext HTTP anywhere, trust only system CAs. On Android 9+ cleartext is already off by default, but declaring it explicitly documents intent and protects you if you ever have to lower your `targetSdk`.

## Cleartext blocking is the first win

The most common real-world use is finding the one legacy endpoint still on `http://`. Rather than opening cleartext globally, scope it to exactly that host and nothing else:

```xml
<domain-config cleartextTrafficPermitted="true">
    <domain includeSubdomains="false">legacy-metrics.internal.example.com</domain>
</domain-config>
```

Everything else stays HTTPS-only. This surgical approach beats the old `android:usesCleartextTraffic="true"` sledgehammer, which permitted plaintext for the entire app. When someone inevitably files a bug that "the app can't reach the analytics host," this file is the first place I look.

## Per-domain trust anchors

The `domain-config` element lets you narrow *which* CAs are acceptable for a given host. If your API sits behind an internal CA, you can trust that CA for your domain only, without adding it to the trust set for the rest of the internet:

```xml
<domain-config>
    <domain includeSubdomains="true">api.corp.example.com</domain>
    <trust-anchors>
        <certificates src="@raw/corp_root_ca" />
        <certificates src="system" />
    </trust-anchors>
</domain-config>
```

Drop the PEM/DER into `res/raw/`. This is cleaner than a custom `TrustManager` and, crucially, scoped: a bug here can't accidentally weaken trust for `payments.example.com`.

## Debug overrides: the feature I use daily

Here's the element that solves a real workflow pain. To inspect traffic with Charles or mitmproxy, you need the app to trust the proxy's CA — but you must never let that trust reach production. `debug-overrides` only applies when `android:debuggable` is true:

```xml
<debug-overrides>
    <trust-anchors>
        <certificates src="user" />
        <certificates src="system" />
    </trust-anchors>
</debug-overrides>
```

Trusting `user`-installed CAs in debug builds means QA can install a proxy certificate and intercept traffic, while release builds ignore this block entirely. Since Android 7 stopped trusting user CAs by default, this is the sanctioned way to get debuggability back without the `debuggable`-only branch you'd otherwise hand-roll. It pairs naturally with [OkHttp certificate pinning](https://blog.michaelsam94.com/android-certificate-pinning-okhttp/), which you keep strict in release.

## Declarative pinning (with a caution)

You can even pin certificates here instead of in OkHttp code:

```xml
<domain-config>
    <domain includeSubdomains="true">api.example.com</domain>
    <pin-set expiration="2025-01-01">
        <pin digest="SHA-256">AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=</pin>
        <pin digest="SHA-256">BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=</pin>
    </pin-set>
</domain-config>
```

The `expiration` attribute is a safety valve absent from OkHttp's programmatic pinner: after that date, pinning stops being enforced instead of bricking connections. That said, I usually prefer pinning in OkHttp because it gives me runtime control and a remote kill switch, and the same *always ship a backup pin* rule applies here too. Pick one place to pin; don't do both.

## How enforcement actually behaves

A few gotchas from shipping this:

- The config is read at process start. It's not dynamic — you can't flip cleartext at runtime.
- It governs the platform networking stack and libraries built on it (OkHttp/Retrofit included). Native code doing its own TLS (some C/C++ or Flutter engine paths) may bypass it, so verify for cross-platform stacks.
- `includeSubdomains` is exact-match-plus-subdomains, not a wildcard; get the base domain right.
- WebView traffic honors the config too, which surprises people — a good thing, since WebViews are a classic soft spot.

## What I standardize on

Every new project gets a network security config on day one: cleartext off in `base-config`, system trust anchors, a `debug-overrides` block trusting user CAs so QA can proxy, and cleartext opened only for specific legacy hosts if truly unavoidable. It's a five-minute investment that makes the app's trust posture reviewable in one file instead of archaeology across the codebase — and it closes the door on the single most dangerous Android networking mistake, the trust-everything `TrustManager`.

## Common production mistakes

Teams get network security config wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Shipping network security config on Android fails quietly when you test only on flagship devices, skip process-death scenarios, or assume `minSdk` behavior matches latest API docs. Emulator-only validation misses OEM-specific battery optimizations and background execution limits.

## Resources

- [Network security configuration (Android)](https://developer.android.com/privacy-and-security/security-config)
- [Security with HTTPS and SSL](https://developer.android.com/privacy-and-security/security-ssl)
- [Behavior changes: apps targeting API 28+ (cleartext)](https://developer.android.com/about/versions/pie/android-9.0-changes-28)
- [OWASP Mobile Application Security Verification Standard](https://mas.owasp.org/MASVS/)
- [Charles Proxy SSL configuration](https://www.charlesproxy.com/documentation/using-charles/ssl-certificates/)
