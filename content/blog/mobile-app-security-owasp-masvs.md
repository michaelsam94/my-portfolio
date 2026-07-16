---
title: "Mobile App Security with MASVS"
slug: "mobile-app-security-owasp-masvs"
description: "Secure Android and iOS apps with OWASP MASVS: storage, cryptography, authentication, network, platform interaction, and code quality requirements."
datePublished: "2025-06-29"
dateModified: "2025-06-29"
tags: ["SEC", "Mobile", "Android", "iOS"]
keywords: "OWASP MASVS, mobile app security verification, MASVS L1 L2, mobile security standard, MSTG mobile testing guide, Android iOS security checklist"
faq:
  - q: "What is the difference between MASVS L1 and L2?"
    a: "MASVS L1 is baseline security for all apps — standard cryptography, secure storage, certificate pinning, no hardcoded secrets. MASVS L2 adds defense-in-depth for apps handling sensitive data (banking, health) — root/jailbreak detection, anti-tampering, debugger detection, and hardware-backed key storage. Most consumer apps target L1; financial and health apps target L2."
  - q: "Do I need MASVS compliance for App Store submission?"
    a: "Apple and Google do not require MASVS certification for submission. However, MASVS aligns with their security guidelines, and enterprise customers, regulators, and security audits increasingly reference MASVS as the mobile security baseline. PCI DSS and HIPAA assessments often map to MASVS controls."
  - q: "How do I test my app against MASVS?"
    a: "Use the OWASP Mobile Application Security Testing Guide (MASTG) — it maps test cases to each MASVS requirement. Combine automated tools (MobSF for static analysis, Frida for dynamic analysis) with manual testing for logic flaws, authentication bypass, and business logic vulnerabilities."
---

Your app stores the auth token in SharedPreferences. API keys are in the APK strings.xml. Certificate pinning was planned but never implemented. The backend team assumes the mobile client is trustworthy. A security researcher downloads your APK, extracts credentials in five minutes, and intercepts API traffic with a proxy.

OWASP Mobile Application Security Verification Standard (MASVS) defines what "secure enough" means for mobile apps. It is organized into seven control groups covering storage, cryptography, authentication, network communication, platform interaction, code quality, and resilience. MASVS Level 1 (L1) is the baseline every app should meet. Level 2 (L2) adds requirements for apps handling high-value data.

## MASVS control groups

| Group | Code | What it covers |
|-------|------|---------------|
| Storage | MASVS-STORAGE | Data at rest, secure deletion, no sensitive data in logs |
| Cryptography | MASVS-CRYPTO | Strong algorithms, proper key management, no custom crypto |
| Authentication | MASVS-AUTH | Secure auth flows, session management, biometric integration |
| Network | MASVS-NETWORK | TLS, certificate pinning, no cleartext traffic |
| Platform | MASVS-PLATFORM | Permission usage, WebView security, IPC |
| Code | MASVS-CODE | Code quality, tampering detection, debugging prevention |
| Resilience | MASVS-RESILIENCE | Root/jailbreak detection, anti-reversing (L2 only) |

## MASVS-STORAGE: protect data at rest

Never store sensitive data in plaintext:

```kotlin
// Android: EncryptedSharedPreferences for tokens
val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val securePrefs = EncryptedSharedPreferences.create(
    context, "auth_prefs", masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
)
securePrefs.edit().putString("access_token", token).apply()
```

```swift
// iOS: Keychain for credentials
let query: [String: Any] = [
    kSecClass as String: kSecClassGenericPassword,
    kSecAttrAccount as String: "access_token",
    kSecValueData as String: token.data(using: .utf8)!,
    kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
]
SecItemAdd(query as CFDictionary, nil)
```

Checklist:
- No sensitive data in logs (`Log.d`, `print`, `NSLog`).
- No sensitive data in backups (exclude from iCloud/Android backup).
- Secure deletion on logout (overwrite, not just delete key).
- No sensitive data in screenshots (FLAG_SECURE on Android, prevent screen capture on iOS for sensitive screens).

## MASVS-NETWORK: secure communication

Enforce TLS and certificate pinning:

```xml
<!-- Android: network security config -->
<network-security-config>
    <domain-config cleartextTrafficPermitted="false">
        <domain includeSubdomains="true">api.example.com</domain>
        <pin-set expiration="2027-01-01">
            <pin digest="SHA-256">base64PrimaryPin=</pin>
            <pin digest="SHA-256">base64BackupPin=</pin>
        </pin-set>
    </domain-config>
</network-security-config>
```

```kotlin
// OkHttp certificate pinning
val client = OkHttpClient.Builder()
    .certificatePinner(CertificatePinner.Builder()
        .add("api.example.com", "sha256/PRIMARY_PIN")
        .add("api.example.com", "sha256/BACKUP_PIN")
        .build())
    .build()
```

Also enforce:
- No cleartext HTTP (Android `usesCleartextTraffic="false"`, iOS ATS).
- TLS 1.2+ only.
- Validate certificate chain (no self-signed in production).

## MASVS-AUTH: session management

```kotlin
// Short-lived access token + refresh token rotation
class TokenManager(private val securePrefs: SharedPreferences) {
    fun getAccessToken(): String? {
        val token = securePrefs.getString("access_token", null) ?: return null
        if (isExpired(token)) {
            return refreshAccessToken()
        }
        return token
    }

    private fun refreshAccessToken(): String? {
        val refreshToken = securePrefs.getString("refresh_token", null) ?: return null
        val response = authApi.refresh(refreshToken)
        if (response.refreshToken != refreshToken) {
            // Token rotation: store new refresh token
            securePrefs.edit()
                .putString("access_token", response.accessToken)
                .putString("refresh_token", response.refreshToken)
                .apply()
        }
        return response.accessToken
    }

    fun logout() {
        securePrefs.edit().clear().apply()
        authApi.revokeToken()
    }
}
```

Requirements:
- Tokens in secure storage (Keychain/EncryptedSharedPreferences), never in UserDefaults/SharedPreferences plaintext.
- Session timeout on inactivity.
- Remote logout capability (token revocation).
- Biometric re-authentication for sensitive operations.

## MASVS-CODE: no secrets in the binary

API keys, encryption keys, and backend URLs embedded in the app binary are extractable:

```bash
# Anyone can do this to your APK
apktool d app.apk
grep -r "api_key\|secret\|password" app/
strings classes.dex | grep -i key
```

Instead:
- Fetch configuration from a remote config service at runtime.
- Use certificate pinning to protect the config endpoint.
- Assume all client-side secrets will be extracted — design the backend to not trust the client.

## MASVS-RESILIENCE (L2): anti-tampering

For high-security apps:

```kotlin
fun checkIntegrity(): Boolean {
    if (RootBeer(context).isRooted) return false
    if (isDebuggerConnected()) return false
    if (!verifySignature(context, EXPECTED_SIGNATURE)) return false
    return true
}
```

L2 requirements include root/jailbreak detection, debugger detection, emulator detection, and app integrity verification. These are bypassable by determined attackers — treat them as speed bumps, not walls.

## MASVS-STORAGE: data at rest

```kotlin
// EncryptedSharedPreferences for tokens
val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val securePrefs = EncryptedSharedPreferences.create(
    context, "secure_prefs", masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
)
```

Room database encryption via SQLCipher for sensitive local data. Exclude backup:

```xml
<application android:allowBackup="false" android:fullBackupContent="false" />
```

## Penetration testing workflow

1. **MobSF static scan** on every release candidate
2. **MASTG checklist** — manual test of top 10 controls per release
3. **Dynamic analysis** — Frida/objection on staging build quarterly
4. **Dependency audit** — Dependabot + OWASP dependency-check

Track findings in security backlog with severity — L1 apps fix critical before store submission.

## Platform-specific hardening

| Control | Android | iOS |
|---------|---------|-----|
| Cert pinning | Network Security Config | TrustKit / ATS |
| Root detection | RootBeer, Play Integrity | jailbreak checks |
| Obfuscation | R8 | Swift symbol stripping |
| Secure enclave | StrongBox Keystore | Secure Enclave |

Pair with [Android certificate pinning OkHttp](https://blog.michaelsam94.com/android-certificate-pinning-okhttp/) for network layer MASVS compliance.

## Common production mistakes

Teams get mobile app security owasp masvs wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of mobile app security owasp masvs fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Resources

- [OWASP MASVS standard](https://mas.owasp.org/MASVS/)
- [OWASP MASTG (testing guide)](https://mas.owasp.org/MASTG/)
- [MobSF mobile security framework](https://github.com/MobSF/Mobile-Security-Framework-MobSF)
- [Android security best practices](https://developer.android.com/privacy-and-security/security-best-practices)
- [Apple Platform Security guide](https://support.apple.com/guide/security/welcome/web)
