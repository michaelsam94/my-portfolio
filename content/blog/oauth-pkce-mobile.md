---
title: "OAuth 2.0 PKCE for Mobile Apps"
slug: "oauth-pkce-mobile"
description: "How OAuth 2.0 PKCE secures mobile login: the authorization code flow, code_verifier and code_challenge, why implicit flow is dead, and mobile-specific pitfalls."
datePublished: "2026-03-26"
dateModified: "2026-07-17"
tags:
keywords: "OAuth PKCE, authorization code flow, mobile OAuth, PKCE mobile, secure login mobile, token exchange"
faq:
  - q: "What is OAuth 2.0 PKCE?"
    a: "PKCE (Proof Key for Code Exchange, pronounced 'pixy') is an extension to the OAuth 2.0 authorization code flow that protects public clients like mobile apps from authorization code interception. The client generates a random secret (code_verifier), sends a hashed version (code_challenge) when starting the flow, and proves it holds the original verifier when exchanging the code for tokens. An attacker who steals the authorization code can't use it without the verifier."
  - q: "Why can't mobile apps just use a client secret?"
    a: "A mobile app is a public client — its binary is distributed to every user and can be decompiled, so any embedded client secret is effectively public. Because you can't keep a secret in an app, the traditional confidential-client protection doesn't apply. PKCE replaces the static client secret with a per-request dynamic secret that never has to be stored in the app, which is exactly why it's mandatory for mobile."
  - q: "Is the implicit flow still acceptable for mobile?"
    a: "No. The implicit flow returned tokens directly in the redirect, which exposed them to interception and left no way to prove client legitimacy. OAuth 2.0 Security Best Current Practice and OAuth 2.1 formally deprecate it. The authorization code flow with PKCE is now the required approach for mobile and single-page apps; there is no good reason to use implicit flow in a new app."
---
Mobile login has a structural problem that web apps with a backend don't: there's nowhere safe to keep a secret. Your app ships to a million phones, any one of which can be rooted and decompiled, so an embedded client secret is a public secret. OAuth 2.0 PKCE — Proof Key for Code Exchange — is the fix. It secures the authorization code flow for these "public clients" by replacing the static secret with a fresh, per-login secret that never lives in the app binary and never crosses the network in the clear.

I've reviewed mobile auth implementations that were technically "using OAuth" and still trivially interceptable because they skipped PKCE or, worse, clung to the long-dead implicit flow. If you're building mobile login in 2026, PKCE isn't optional — it's the baseline. Here's how it works and the mobile-specific traps that break it.

## The interception attack PKCE stops

To see why PKCE exists, picture the attack it defeats. In the plain authorization code flow, the app opens a browser, the user authenticates, and the authorization server redirects back to the app with a `code`. The app exchanges that code for tokens. The weakness: on mobile, that redirect happens over a custom URI scheme or app link, and a malicious app on the same device can register the same scheme and intercept the `code`.

With a stolen code and no client secret to stop them (because the app can't have one), the attacker exchanges the code for the victim's tokens. Game over. PKCE closes this by making the code useless without a secret that the attacker never saw.

## The flow, step by step

PKCE adds two values to the standard flow: a `code_verifier` and its hash, the `code_challenge`.

1. Before starting, the app generates a cryptographically random `code_verifier` (43–128 chars).
2. It computes `code_challenge = BASE64URL(SHA256(code_verifier))` and sends *that* with the authorization request.
3. The user authenticates; the authorization server stores the challenge alongside the issued code.
4. The app receives the `code` (which an attacker might intercept).
5. The app exchanges the code for tokens, this time sending the original `code_verifier`.
6. The server hashes the verifier and checks it matches the stored challenge. No match, no tokens.

The magic is in the asymmetry: the challenge travels over the interceptable authorization request, but it's a one-way hash. The verifier — the thing that actually proves legitimacy — only travels on the back-channel token exchange, and only the app that generated it knows it. A stolen code is worthless.

## Generating the verifier and challenge

Here's the client side in Kotlin, which is where I've implemented this most often:

```kotlin
import android.util.Base64
import java.security.MessageDigest
import java.security.SecureRandom

fun generateCodeVerifier(): String {
    val bytes = ByteArray(64)
    SecureRandom().nextBytes(bytes)
    return Base64.encodeToString(
        bytes, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
    )
}

fun codeChallenge(verifier: String): String {
    val digest = MessageDigest.getInstance("SHA-256")
        .digest(verifier.toByteArray(Charsets.US_ASCII))
    return Base64.encodeToString(
        digest, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP
    )
}
```

Two things I insist on in review: use `SecureRandom`, never `Random` — a predictable verifier defeats the entire mechanism — and always use the `S256` challenge method (SHA-256), never `plain`. The `plain` method sends the verifier as the challenge, which offers no protection against interception; it exists only for constrained environments that can't compute SHA-256, which is not your phone.

## Use a system browser, not a WebView

This is the mobile pitfall that undoes everything even when PKCE is correct. Do **not** run the authorization step in an in-app `WebView`. A WebView is fully controlled by the host app, so it can read the user's credentials, cookies, and the authorization response — and worse, users are being trained to type their password into an untrusted surface. Use the platform's secure in-app browser tab: `Custom Tabs` on Android, `ASWebAuthenticationSession` on iOS. These run outside your app's control, share the system browser's session, and can't be snooped by your process.

The canonical guidance here is RFC 8252, "OAuth 2.0 for Native Apps," and it's worth reading in full. The AppAuth libraries implement its recommendations correctly, and I'd steer any team toward them rather than hand-rolling the redirect handling. This is part of the same defense-in-depth mindset as [zero-trust mobile app architecture](https://blog.michaelsam94.com/zero-trust-mobile-apps/) — never trust the transport or the surrounding environment; prove legitimacy cryptographically at every step.

## Where to put the tokens afterward

PKCE gets you the tokens; storing them is a separate responsibility that people botch. Access and refresh tokens must go in the platform secure storage — the Android Keystore-backed `EncryptedSharedPreferences` or the iOS Keychain — never in plain `SharedPreferences`, `UserDefaults`, or a local file. Prefer short-lived access tokens with refresh token rotation, so a leaked refresh token has a limited blast radius and reuse is detectable.

| Anti-pattern | Do this instead |
|---|---|
| Implicit flow | Authorization code + PKCE |
| `plain` challenge method | `S256` (SHA-256) |
| In-app WebView for login | Custom Tabs / ASWebAuthenticationSession |
| Tokens in plain storage | Keystore / Keychain |
| Predictable `Random` verifier | `SecureRandom` |

## PKCE and the move to passwordless

PKCE secures the authorization *transport*, but it says nothing about *how* the user authenticated inside that browser tab. That's a feature — you can pair PKCE with any authentication method the authorization server supports, including phishing-resistant ones. The strongest combination I've deployed uses PKCE for the OAuth flow and [passkeys with WebAuthn](https://blog.michaelsam94.com/passkeys-webauthn-implementation/) for the actual credential, which eliminates the password entirely while keeping the standard, well-understood OAuth token machinery underneath.

The bottom line from someone who's shipped this in production apps: get the four things right — code flow with PKCE, `S256`, a system browser, and secure token storage — and mobile login is genuinely solid. Skip any one of them and you've built something that looks like OAuth and fails like a toy. The spec authors did the hard thinking; the job is to implement it faithfully rather than cutting the corner that happens to be inconvenient this sprint.

## Resources

- [RFC 7636 — Proof Key for Code Exchange (PKCE)](https://datatracker.ietf.org/doc/html/rfc7636)
- [RFC 8252 — OAuth 2.0 for Native Apps](https://datatracker.ietf.org/doc/html/rfc8252)
- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/rfc9700)
- [OAuth 2.1 draft specification](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1)
- [AppAuth for Android](https://github.com/openid/AppAuth-Android)
- [AppAuth for iOS](https://github.com/openid/AppAuth-iOS)


## Production validation (1)

Ship changes behind feature flags when behavior crosses route or service boundaries. Canary deploy with automatic rollback when error rate or p95 latency regresses beyond SLO budget. Document which metrics prove success—user-visible latency, error ratio, conversion—not only CPU graphs.

When operating **OAuth pkce mobile** (`oauth-pkce-mobile`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Failure modes (2)

Recurring incidents: missing idempotency on retried paths, connection pool exhaustion masquerading as slow queries, retry storms amplifying partial outages. Design explicit timeouts on every outbound call.

When operating **OAuth pkce mobile** (`oauth-pkce-mobile`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.

## Observability (3)

Structured logs include trace_id and tenant_id on every error path. Metrics: request rate, error ratio, duration histogram, queue depth or pool wait. Traces: one span per dependency.

When operating **OAuth pkce mobile** (`oauth-pkce-mobile`), tie this section to a measurable SLI—latency, error rate, freshness, or throughput—and review it in weekly ops until the pattern is boringly stable.
