---
title: "Secure Storage and Encryption in Flutter"
slug: "flutter-secure-storage-encryption"
description: "Store tokens and keys in platform secure enclaves, not SharedPreferences. flutter_secure_storage, encryption at rest, and threat model basics."
datePublished: "2025-03-11"
dateModified: "2025-03-11"
tags: ["Flutter", "Dart", "Security", "Mobile"]
keywords: "Flutter secure storage, flutter_secure_storage, encrypt tokens Flutter, Keychain Android Keystore, mobile secrets storage"
faq:
  - q: "Is SharedPreferences safe for auth tokens?"
    a: "No on rooted/jailbroken devices and often not on stock devices either—SharedPreferences is plaintext XML on Android and plist on iOS without hardware backing. Use flutter_secure_storage or platform Keystore/Keychain for secrets."
  - q: "What does flutter_secure_storage use under the hood?"
    a: "Android: EncryptedSharedPreferences or Keystore-backed keys depending on options. iOS: Keychain with accessibility flags. Web: Web Crypto API with limitations—treat web separately."
  - q: "Should I encrypt database files too?"
    a: "If local DB holds PII or health data, yes—SQLCipher via sqflite_sqlcipher or encrypt sensitive columns with keys from secure storage. Secure storage alone does not protect Room/ObjectBox files."
---

A penetration test found our refresh token in SharedPreferences on a test device—readable with backup extraction. We moved secrets to `flutter_secure_storage` in a day. The code change was small; the threat model conversation should have happened before shipping auth.

Mobile apps cache credentials, API keys, and encryption keys. Plain files and SharedPreferences are for preferences, not secrets. Platform secure storage uses hardware-backed keystores where available.

## flutter_secure_storage setup

```yaml
dependencies:
  flutter_secure_storage: ^9.2.0
```

```dart
const storage = FlutterSecureStorage(
  aOptions: AndroidOptions(encryptedSharedPreferences: true),
  iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
);

Future<void> saveTokens({required String access, required String refresh}) async {
  await storage.write(key: 'access_token', value: access);
  await storage.write(key: 'refresh_token', value: refresh);
}

Future<String?> readAccessToken() => storage.read(key: 'access_token');

Future<void> clearSession() async {
  await storage.delete(key: 'access_token');
  await storage.delete(key: 'refresh_token');
}
```

## iOS Keychain accessibility

Choose accessibility matching UX and security:

- `first_unlock` — available after first device unlock post-reboot; common for background refresh
- `when_unlocked` — stricter, fails in background until user unlocks
- `passcode_set` — requires device passcode configured

Document choice in security review.

## Android considerations

Prefer `encryptedSharedPreferences: true` on modern API levels. Test on API 23+ devices you support—Keystore behavior varies.

Avoid logging token values in Dio interceptors in release builds.

## Application-level encryption layer

For structured secrets or local DB field encryption, derive an AES key stored in secure storage:

```dart
Future<SecretKey> getOrCreateDbKey() async {
  const keyName = 'db_aes_key';
  final existing = await storage.read(key: keyName);
  if (existing != null) {
    return SecretKey(base64Decode(existing));
  }

  final key = await AesGcm.with256bits().newSecretKey();
  final bytes = await key.extractBytes();
  await storage.write(key: keyName, value: base64Encode(bytes));
  return key;
}
```

Use `cryptography` package for AES-GCM. Never hardcode keys in source.

## What secure storage does not protect against

- Rooted/jailbroken device memory inspection
- Debugger attached in debug builds
- Malware with accessibility scraping UI
- User screenshots of sensitive screens

Combine with certificate pinning, biometrics for re-auth, short-lived access tokens, and server-side revocation.

## Biometric gate for high-value actions

Use `local_auth` before reading certain keys or approving transactions—not for every app open unless product demands it.

## Web and desktop

`flutter_secure_storage` web uses limited browser storage—assume lower assurance. Desktop uses OS-specific vaults; test Windows/macOS/Linux separately if you ship those targets.

## Logout and wipe

On logout, delete all secure keys and in-memory caches:

```dart
await storage.deleteAll();
ref.invalidate(authProvider);
```

Missed keys leave ghost sessions.

## Compliance notes

GDPR and HIPAA care about data at rest and key management. Document where tokens live, retention period, and wipe on account deletion in your privacy assessment.

## Key rotation

When rotating encryption keys:

1. Read with old key
2. Write with new key
3. Delete old key material
4. Version key name (`db_aes_key_v2`)

Plan downtime or background migration for large local DBs.

## Biometric-bound keys

Android `setUserAuthenticationRequired` and iOS `AccessControl.biometryCurrentSet` tie key use to biometric auth—session unlock flow required before reading refresh token.

## Flutter web caveat

`flutter_secure_storage` web backend differs—assume lower assurance; minimize secrets on web client; prefer HTTP-only cookies for web auth where possible.

## Incident response

If token leak suspected: server-side revoke all sessions, ship app update forcing `storage.deleteAll()` on next launch via remote config flag, rotate signing keys if JWT private key exposed (server-side).


## Root and jailbreak detection

Combine secure storage with runtime integrity checks for high-value apps—knowing device compromised informs step-up auth rather than pretending storage is safe.

## Migration from SharedPreferences

Ship one-time migration on upgrade:

```dart
final legacy = prefs.getString('token');
if (legacy != null) {
  await storage.write(key: 'token', value: legacy);
  await prefs.remove('token');
}
```

Log migration metric; remove code path after 95% users upgraded.

## Hardware security module variance

Budget Android devices may lack strong TEE—document reduced assurance in threat model; server-side session limits compensate.

## Flutter integration tests

Override secure storage with in-memory fake via provider—never read real Keychain in CI.

## WatchOS and extensions

App extensions sharing Keychain access group need entitlements configured—tokens written in main app unreadable in extension without group setup; document in iOS runbook.

## Rollout guidance

Key rotation feature flagged internal users first week—monitor crash analytics storage read failures before gradual 100% rollout key migration job on app upgrade.

## Team practices

Shipping Flutter Secure Storage Encryption in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Flutter Secure Storage Encryption, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Flutter Secure Storage Encryption PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Flutter Secure Storage Encryption questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

Cross-functional review includes design for UX-facing work, security for auth or storage, and platform for native bridges. Flutter Secure Storage Encryption spans layers; skipping reviewers recreated bugs we fixed months ago.

## Resources

- [flutter_secure_storage package](https://pub.dev/packages/flutter_secure_storage)
- [Android Keystore system](https://developer.android.com/privacy-and-security/keystore)
- [iOS Keychain Services](https://developer.apple.com/documentation/security/keychain_services)
- [cryptography package](https://pub.dev/packages/cryptography)
- [OWASP Mobile Security Testing Guide](https://owasp.org/www-project-mobile-security-testing-guide/)
