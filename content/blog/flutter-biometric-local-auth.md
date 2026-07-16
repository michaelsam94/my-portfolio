---
title: "Biometric Auth with local_auth"
slug: "flutter-biometric-local-auth"
description: "Add fingerprint and Face ID login with local_auth: availability checks, fallback flows, secure token storage, and the platform quirks that break auth on release builds."
datePublished: "2024-09-22"
dateModified: "2024-09-22"
tags: ["Flutter", "Dart"]
keywords: "Flutter local_auth, biometric authentication, Face ID Flutter, fingerprint login, flutter_secure_storage"
faq:
  - q: "How does local_auth work in Flutter?"
    a: "The local_auth plugin wraps iOS LocalAuthentication and Android BiometricPrompt APIs. You check device capability with canCheckBiometrics and isDeviceSupported, then call authenticate with localized reason strings. Successful auth returns true; failures and cancellations throw PlatformException with specific error codes you must handle."
  - q: "Should I store passwords with biometric auth in Flutter?"
    a: "Never store raw passwords behind biometrics. Store a short-lived refresh token or session key in flutter_secure_storage, gated by biometric re-authentication. Biometrics unlock access to the secure enclave item—they are not encryption themselves. Treat biometric login as convenience re-entry, not primary authentication."
  - q: "Why does local_auth fail on iOS release builds?"
    a: "Missing NSFaceIDUsageDescription in Info.plist causes immediate failure on physical devices. Test on real hardware—simulators don't exercise the full LocalAuthentication stack. Also verify you haven't disabled biometrics by calling authenticate with biometricOnly: true on devices with only passcode enrolled."
---

Biometric login feels like magic until TestFlight users report "authentication failed" on every attempt. The `local_auth` plugin is thin glue over iOS LocalAuthentication and Android BiometricPrompt—two APIs with different edge cases, fallback rules, and permission requirements. I've shipped biometric re-auth in three Flutter apps; the Dart code is twenty lines. The other eighty percent is platform config, secure storage, and handling the user who disabled Face ID last week.

## Setup and permissions

Add to `pubspec.yaml`:

```yaml
dependencies:
  local_auth: ^2.3.0
  flutter_secure_storage: ^9.2.2
```

**iOS — Info.plist:**

```xml
<key>NSFaceIDUsageDescription</key>
<string>Unlock your account quickly with Face ID</string>
```

Without this key, `authenticate()` fails silently or throws on device.

**Android — AndroidManifest.xml:**

```xml
<uses-permission android:name="android.permission.USE_BIOMETRIC"/>
```

For Android 9 and below, `USE_FINGERPRINT` as fallback. `local_auth` handles BiometricPrompt vs legacy fingerprint manager internally.

## Checking availability

Never assume biometrics exist:

```dart
final auth = LocalAuthentication();

Future<bool> canUseBiometrics() async {
  if (!await auth.isDeviceSupported()) return false;
  if (!await auth.canCheckBiometrics()) return false;
  final types = await auth.getAvailableBiometrics();
  return types.isNotEmpty;
}
```

`getAvailableBiometrics()` returns `BiometricType.face`, `.fingerprint`, `.strong`, `.weak` depending on platform. Use this to customize UI copy ("Use Face ID" vs "Use fingerprint").

## The authenticate call

```dart
Future<bool> authenticateWithBiometrics() async {
  try {
    return await auth.authenticate(
      localizedReason: 'Verify your identity to access your account',
      options: const AuthenticationOptions(
        stickyAuth: true,
        biometricOnly: false, // allow PIN/pattern fallback on Android
        useErrorDialogs: true,
        sensitiveTransaction: true,
      ),
    );
  } on PlatformException catch (e) {
    if (e.code == auth_error.notAvailable ||
        e.code == auth_error.notEnrolled) {
      return false;
    }
    if (e.code == auth_error.lockedOut ||
        e.code == auth_error.permanentlyLockedOut) {
      // Too many failures — force password login
      return false;
    }
    rethrow;
  }
}
```

Key options:

- **`stickyAuth: true`** — survives app backgrounding mid-prompt (Android).
- **`biometricOnly: false`** — allows device PIN when biometrics unavailable. Set `true` only if policy requires hardware biometrics specifically.
- **`sensitiveTransaction: true`** — iOS treats as payment-grade auth.

## Secure storage pattern

Biometric auth should unlock stored credentials, not replace server authentication:

```dart
class BiometricSessionStore {
  final _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );

  static const _refreshTokenKey = 'refresh_token';

  Future<void> saveRefreshToken(String token) async {
    await _storage.write(key: _refreshTokenKey, value: token);
  }

  Future<String?> unlockWithBiometrics() async {
    final ok = await authenticateWithBiometrics();
    if (!ok) return null;
    return _storage.read(key: _refreshTokenKey);
  }
}
```

Flow:

1. User logs in with password → server returns refresh token → store in secure storage.
2. Next launch → prompt biometrics → read token → exchange for session.
3. Biometric failure → fall back to password login screen.

On iOS, consider `IOSOptions(accessibility: KeychainAccessibility.whenPasscodeSetThisDeviceOnly)` for stricter binding to device passcode.

## UX patterns that work

**Opt-in, not forced.** Offer "Enable Face ID login?" after first successful password auth—not on cold install before trust exists.

**Visible fallback.** Always show "Use password instead" below the biometric prompt trigger.

**Re-auth for sensitive actions.** Transfer money, change email—biometric again even if session is valid. Use a short in-memory "elevated until" timestamp (5 minutes).

**Handle enrollment changes.** iOS invalidates Keychain items when biometrics are added/removed. Catch read failures and require password re-login:

```dart
try {
  return await _storage.read(key: _refreshTokenKey);
} on PlatformException {
  await _storage.deleteAll();
  return null; // Force full login
}
```

## Platform differences to test

| Scenario | iOS | Android |
|----------|-----|---------|
| No biometrics enrolled | Passcode fallback if allowed | PIN/pattern via BiometricPrompt |
| Too many failures | lockout → passcode | `lockedOut` error code |
| App in background during prompt | `stickyAuth` helps | May cancel prompt |
| Emulator testing | Limited Face ID simulation | Emulator fingerprint via adb |

Test matrix: iPhone with Face ID, Android with fingerprint, device with biometrics disabled, device with no lock screen (should refuse or fallback gracefully).

### Common production bugs

1. **Missing Info.plist key** — #1 iOS release failure.
2. **`biometricOnly: true` on passcode-only devices** — instant failure.
3. **Storing passwords in SharedPreferences** — trivially extracted; use secure storage.
4. **Not handling `permanentlyLockedOut`** — user stuck in retry loop.
5. **Calling authenticate on web/desktop** — returns false; guard with platform checks.

Wrap biometric features in `if (Platform.isIOS || Platform.isAndroid)` and provide password-only path elsewhere.

### Compliance and threat modeling

Biometric auth satisfies convenience, not high-assurance MFA alone. For PCI or HIPAA flows, pair biometrics with server-side step-up verification for sensitive mutations. Log biometric unlock events locally for fraud investigation—timestamp and success/failure without storing biometric data (you can't and shouldn't).

On Android, confirm `BIOMETRIC_STRONG` vs `BIOMETRIC_WEAK` matches your policy; face unlock on some devices registers as weak. Use `local_auth` Android options or platform checks when regulations require Class 3 biometrics only.

Test biometric flow after device migration restore—Keychain items may not transfer as expected. Enterprise MDM policies can disable biometrics org-wide; detect early and hide biometric login UI rather than showing broken prompts that confuse users.

Production teams should treat this guidance as living documentation: revisit assumptions after major platform upgrades, measure outcomes with real metrics rather than checklist compliance, and pair written standards with automated checks in CI. The patterns here reflect what held up in shipped apps—not theoretical perfection. Adapt thresholds, timeouts, and tooling to your stack, but keep the underlying principles: explicit configuration, testable behavior, and failure modes users can understand.

When onboarding new engineers, walk through one end-to-end example in a debug build before asking them to extend the pattern. Most failures I have seen came from skipped platform setup steps—manifest entries, API keys, code generation, or permission prompts—not from misunderstanding the Dart layer. Keep a troubleshooting section in your team wiki linking official docs and the exact commands that worked for your last upgrade.

## Resources

- [local_auth package](https://pub.dev/packages/local_auth)
- [flutter_secure_storage package](https://pub.dev/packages/flutter_secure_storage)
- [Apple LocalAuthentication framework](https://developer.apple.com/documentation/localauthentication)
- [Android BiometricPrompt guide](https://developer.android.com/identity/sign-in/biometric-auth)
- [local_auth API reference](https://pub.dev/documentation/local_auth/latest/)
