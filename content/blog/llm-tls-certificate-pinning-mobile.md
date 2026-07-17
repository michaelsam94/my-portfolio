---
title: "TLS Certificate Pinning for Mobile Agent Clients"
slug: "llm-tls-certificate-pinning-mobile"
description: "Pin agent API endpoints on iOS and Android: SPKI hashes, rotation strategy, backup pins, and why pinning agent streaming endpoints differs from generic REST for teams running LLM features in production."
datePublished: "2025-03-30"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "TLS certificate pinning mobile agent, SPKI pinning iOS Android, agent API MITM prevention, certificate rotation mobile"
faq:
  - q: "Should mobile agent apps pin the LLM provider or only your backend?"
    a: "Pin your agent gateway only — the domain whose certificates you control. Proxy all LLM traffic through that gateway server-side. Pinning OpenAI or Anthropic directly breaks when they rotate certs on their schedule, not yours."
  - q: "SPKI pinning or full certificate pinning?"
    a: "SPKI (public key) pinning survives certificate reissue with the same key pair. Full cert pinning fails on every Let's Encrypt renewal unless you coordinate timing perfectly. Always ship at least two pins: current primary and pre-published backup."
  - q: "How does pinning interact with agent SSE and WebSocket streams?"
    a: "Pin validation happens at TLS handshake — same as REST. If the server presents an unpinned key mid-session (extremely rare), the connection drops. Your reconnect loop must not fall back to unpinned mode; surface a clear error and cap retry storms."
  - q: "When is pinning the wrong tradeoff?"
    a: "Enterprise deployments behind SSL inspection with custom root CAs will fail pin checks unless you ship a separate enterprise build or MDM-managed config. For consumer finance and health agent apps on untrusted networks, pinning is worth the rotation overhead."
---
A hotel lobby Wi-Fi captive portal is not the threat model slide decks use, but it is where a mobile agent user approves a wire transfer while their session token rides over TLS. Certificate pinning binds your app to **expected server public keys**, so a user-installed rogue CA cannot silently terminate and re-encrypt traffic. Agent clients add complexity: long-lived Server-Sent Event streams, background sync workers, and tool-call retries all share the same pinned TLS stack — one botched rotation bricks every connection path at once.

## Where pinning sits in the agent mobile stack

Most production agent architectures keep the mobile client dumb and the gateway smart:

```
┌─────────────┐     pinned TLS      ┌──────────────────┐     provider keys     ┌─────────────┐
│  iOS/Android │ ─────────────────► │ agent-gateway.   │ ───────────────────► │ LLM / tools │
│  agent app   │   api.example.com  │ example.com      │   (server-side only) │             │
└─────────────┘                     └──────────────────┘                       └─────────────┘
```

The mobile app never holds provider API keys. It pins **one hostname** — your gateway — and treats every other endpoint as out of scope. This simplifies rotation: you control the cert lifecycle on `api.example.com`; OpenAI's cert churn is irrelevant.

| Pin target | Pin? | Rationale |
|------------|------|-----------|
| Agent gateway (`api.example.com`) | Yes | You own cert rotation and can embed backup pins in app releases |
| CDN for static assets | Optional | Lower risk; asset integrity via SRI is often sufficient |
| Third-party LLM API | No | Rotation outside your release cycle; proxy instead |
| Analytics / crash reporting | Usually no | Vendor-managed certs; pinning creates support burden |

## Extracting SPKI hashes

Pin the Subject Public Key Info hash, not the full certificate DER. Reissue with the same key pair and the pin still validates.

```bash
# Primary pin for api.example.com
echo | openssl s_client -connect api.example.com:443 -servername api.example.com 2>/dev/null \
  | openssl x509 -pubkey -noout \
  | openssl pkey -pubin -outform der \
  | openssl dgst -sha256 -binary \
  | openssl enc -base64
```

Run this in CI against staging **and** production after every cert deploy. Fail the pipeline if the live cert's SPKI is not in the app's embedded pin set for that release branch.

## iOS implementation with TrustKit

Apple's App Transport Security blocks cleartext but does not pin by default. TrustKit wraps `URLSession` delegate callbacks:

```swift
import TrustKit

let trustKitConfig: [String: Any] = [
  kTSKSwizzleNetworkDelegates: false,
  kTSKPinnedDomains: [
    "api.example.com": [
      kTSKEnforcePinning: true,
      kTSKIncludeSubdomains: true,
      kTSKPublicKeyHashes: [
        "PRIMARY_SPKI_BASE64=",
        "BACKUP_SPKI_BASE64="
      ],
      kTSKDisableDefaultReportUri: true
    ]
  ]
]
TrustKit.initSharedInstance(withConfiguration: trustKitConfig)
```

Agent SSE clients often use a custom `URLSession` with `URLSessionDataDelegate`. Ensure the delegate path calls TrustKit's validation — data tasks and streaming byte callbacks must share the same trust evaluation. A common bug: REST calls are pinned, SSE uses a separate session without the delegate hook, and QA never catches it because REST works.

For WebSocket tool streaming, `URLSessionWebSocketTask` follows the same delegate. Log pin failures as structured events (`tls_pin_rejected`, domain, app_version) without echoing cert details to the user.

## Android Network Security Config

Android 7+ supports declarative pinning in `res/xml/network_security_config.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
  <domain-config cleartextTrafficPermitted="false">
    <domain includeSubdomains="true">api.example.com</domain>
    <pin-set expiration="2027-06-01">
      <pin digest="SHA-256">PRIMARY_SPKI_BASE64=</pin>
      <pin digest="SHA-256">BACKUP_SPKI_BASE64=</pin>
    </pin-set>
  </domain-config>
</network-security-config>
```

Reference in `AndroidManifest.xml`:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... />
```

OkHttp's `CertificatePinner` should mirror the same hashes for any client not routed through the platform stack:

```kotlin
val pinner = CertificatePinner.Builder()
    .add("api.example.com", "sha256/PRIMARY_SPKI_BASE64=")
    .add("api.example.com", "sha256/BACKUP_SPKI_BASE64=")
    .build()

val client = OkHttpClient.Builder()
    .certificatePinner(pinner)
    .build()
```

WorkManager background sync and foreground agent chat must use the same pinned client factory — dependency injection helps enforce this.

## Rotation without bricking the fleet

Pin rotation is an operational procedure, not a one-time setup. A typical 90-day cert with a planned key rollover:

| Phase | Timeline | Action |
|-------|----------|--------|
| Pre-publish backup | T−60d | Generate new key pair; add backup SPKI to server config and next app release |
| App soak | T−30d | Ship app update containing backup pin; wait for ≥95% adoption |
| Cutover | T−0 | Switch server to new primary cert signed with new key |
| Retire old pin | T+90d | Remove retired SPKI from pin set in subsequent app release |

Never remove a pin from the app until server-side traffic shows zero clients on builds that lack the replacement pin. Track `tls_pin_failure_count` by `app_version` in your analytics pipeline.

## Failure UX and retry discipline

On pin validation failure:

1. Log internally with correlation ID — never expose cert fingerprints in UI.
2. Show: "Secure connection failed. Update the app or try another network."
3. **Never** offer "Continue anyway" — that negates the control.
4. Cap background retries (WorkManager backoff, max 3 attempts per hour) to avoid battery drain during fleet-wide rotation incidents.

Corporate MITM via SSL inspection is a support macro, not a code exception in consumer builds. Enterprise customers get a flavor without pinning or an MDM profile that installs your corporate root — document this in the sales engineering runbook.

## Streaming-specific gotchas

Agent UIs stream tokens over SSE for minutes. Pin failure at handshake is clean; partial reads after a proxy injects content are not — pinning prevents the proxy from being in-path at all. WebSocket tool calls that upgrade from HTTPS share the same pin set.

Background fetch amplifies failures: ten scheduled sync jobs × exponential retry = radio wake storm. Use a shared connectivity gate that checks pin health once and blocks downstream jobs until the user updates or network changes.

## Testing matrix

| Test | Setup | Expected |
|------|-------|----------|
| Valid pin | Staging with matching SPKI | All API + SSE paths succeed |
| Wrong cert | Charles Proxy with custom root | Hard fail, user message, no data leak |
| Backup pin only | Staging serving backup key | App with only backup pin connects |
| Rotation drill | Deploy new primary, old app version | Old app still works if backup was pre-shipped |

Instrument UI tests with a mock server presenting an unpinned cert — assert the agent chat screen shows the error state, not an infinite spinner.

## Complements, not replacements

Pinning does not replace: server-side auth, short-lived tokens, App Attest / Play Integrity for binary integrity, or Certificate Transparency monitoring for mis-issuance on your domain. It adds defense-in-depth for the mobile-to-gateway hop specifically.

## Resources

- [OWASP Certificate Pinning Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Pinning_Cheat_Sheet.html)
- [Android Network Security Configuration](https://developer.android.com/privacy-and-security/security-config)
- [TrustKit — iOS/macOS pinning library](https://github.com/datatheorem/TrustKit)
- [OkHttp CertificatePinner documentation](https://square.github.io/okhttp/features/certificate_pinning/)
- [RFC 7469 — Public Key Pinning Extension for HTTP (historical context)](https://datatracker.ietf.org/doc/html/rfc7469)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.
