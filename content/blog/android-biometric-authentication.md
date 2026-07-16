---
title: "Biometric Authentication on Android"
slug: "android-biometric-authentication"
description: "Implement biometric authentication on Android with BiometricPrompt and CryptoObject: authenticator types, key-bound crypto, and fallbacks that don't lock users out."
datePublished: "2024-07-01"
dateModified: "2024-07-01"
tags: ["Android", "Security", "Biometrics", "Authentication"]
keywords: "biometric authentication Android, BiometricPrompt, CryptoObject, BIOMETRIC_STRONG, Keystore, setUserAuthenticationRequired, device credential fallback"
faq:
  - q: "What is the difference between BIOMETRIC_STRONG and BIOMETRIC_WEAK?"
    a: "BIOMETRIC_STRONG (Class 3) meets stricter spoof-acceptance and false-acceptance thresholds and is the only tier allowed to gate cryptographic keys via CryptoObject. BIOMETRIC_WEAK (Class 2) is fine for low-risk convenience unlocks but cannot release Keystore keys. If your biometric protects real secrets, you must require BIOMETRIC_STRONG."
  - q: "Why should I use a CryptoObject with BiometricPrompt?"
    a: "Without a CryptoObject, a successful authentication is just a boolean your app trusts — which malware or a patched app could fake. Binding the prompt to a Keystore key that requires user authentication means the successful biometric actually unlocks a cryptographic operation, so the security is enforced by the hardware-backed keystore, not by your app's control flow. That's the difference between real biometric security and a UI gesture."
  - q: "How do I handle a user who has no biometrics enrolled?"
    a: "Call canAuthenticate() with your required authenticators before showing the prompt, and branch on the result: enroll flow if none are set up, hardware-unavailable messaging if the sensor is busy, or fall back to device credential (PIN/pattern/password) via setAllowedAuthenticators including DEVICE_CREDENTIAL. Never make biometrics the only way in, or you'll lock out users whose fingerprint stopped working."
---

Biometric authentication on Android done properly is not "show a fingerprint dialog and set `isLoggedIn = true`." That version is security theater — a boolean any tampered build or accessibility exploit can flip. Real biometric security uses `BiometricPrompt` bound to a `CryptoObject`, so a successful fingerprint or face match actually *unlocks a hardware-backed Keystore key*, and the sensitive operation cannot proceed unless the biometric genuinely succeeded. The framework unifies fingerprint, face, and iris behind one API and one system dialog; your job is to pick the right authenticator class, bind it to crypto when it matters, and design fallbacks that never lock a legitimate user out.

## Know your authenticator classes

Android grades biometrics by spoof-resistance, and the class you require has real consequences:

- **`BIOMETRIC_STRONG` (Class 3):** meets strict false-accept and spoof-accept thresholds. **Only Class 3 can gate Keystore keys via `CryptoObject`.** If your biometric protects anything cryptographic, this is mandatory.
- **`BIOMETRIC_WEAK` (Class 2):** convenient but weaker; fine for a low-stakes "unlock the app UI" that isn't protecting secrets. Cannot release keys.
- **`DEVICE_CREDENTIAL`:** the device PIN, pattern, or password. Your fallback and, for some flows, a perfectly acceptable primary.

The decision rule I use: if a successful auth releases a secret, decrypts data, or authorizes a payment, require `BIOMETRIC_STRONG` and bind a key. If it merely reveals already-loaded, non-sensitive UI, `WEAK` is acceptable.

## Check availability before you prompt

Never show the prompt blind. `canAuthenticate` tells you exactly what state the device is in so you can route correctly:

```kotlin
val manager = BiometricManager.from(context)
when (manager.canAuthenticate(BIOMETRIC_STRONG or DEVICE_CREDENTIAL)) {
    BiometricManager.BIOMETRIC_SUCCESS -> showPrompt()
    BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED -> promptEnrollment()
    BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE,
    BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE -> fallToPassword()
    BiometricManager.BIOMETRIC_ERROR_SECURITY_UPDATE_REQUIRED -> promptSecurityUpdate()
}
```

Each branch is a distinct UX. `NONE_ENROLLED` should offer to open enrollment settings; `NO_HARDWARE` should quietly fall back to your own auth. Handling these explicitly is what separates an app that "works on my Pixel" from one that behaves on the whole device landscape.

## Bind the prompt to a Keystore key

Here's the part that makes it real. Generate a key in the Android Keystore that *requires user authentication*, then wrap the resulting `Cipher` in a `CryptoObject`:

```kotlin
val keyGen = KeyGenerator.getInstance(
    KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore"
)
keyGen.init(
    KeyGenParameterSpec.Builder("biometric_key",
        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .setUserAuthenticationRequired(true)          // key needs a fresh auth
        .setInvalidatedByBiometricEnrollment(true)    // new fingerprint => key dies
        .build()
)

val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
    init(Cipher.ENCRYPT_MODE, keyStore.getKey("biometric_key", null) as SecretKey)
}
prompt.authenticate(promptInfo, BiometricPrompt.CryptoObject(cipher))
```

Two flags carry the security. `setUserAuthenticationRequired(true)` means the key is unusable until a biometric (or credential) authorizes it — enforced by the keystore, in hardware where available. `setInvalidatedByBiometricEnrollment(true)` means enrolling a *new* fingerprint invalidates the key, so an attacker who adds their own biometric to a stolen unlocked phone can't then decrypt your data. In the success callback you use `result.cryptoObject?.cipher` — that cipher only exists because the auth genuinely succeeded. This is why the crypto binding beats a boolean: the security lives in the [hardware-backed keystore](https://blog.michaelsam94.com/hardware-backed-keys-attestation/), not your control flow.

## Show the prompt and handle every outcome

```kotlin
val prompt = BiometricPrompt(activity, executor,
    object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(r: AuthenticationResult) {
            val cipher = r.cryptoObject?.cipher ?: return
            decryptWith(cipher)
        }
        override fun onAuthenticationError(code: Int, msg: CharSequence) {
            when (code) {
                BiometricPrompt.ERROR_NEGATIVE_BUTTON,
                BiometricPrompt.ERROR_USER_CANCELED -> { /* user chose out */ }
                BiometricPrompt.ERROR_LOCKOUT,
                BiometricPrompt.ERROR_LOCKOUT_PERMANENT -> offerCredentialFallback()
                else -> showTransientError(msg)
            }
        }
        override fun onAuthenticationFailed() { /* one bad attempt; prompt stays */ }
    })
```

The distinction that trips people up: `onAuthenticationFailed()` is a single non-matching attempt (the prompt stays up, let it retry), while `onAuthenticationError()` with `ERROR_LOCKOUT` means too many failures and the sensor is temporarily disabled — *this* is where you route to device credential so the user isn't stuck. `ERROR_LOCKOUT_PERMANENT` needs a device unlock to clear. Treating "failed" and "error" the same is how apps end up either giving up too early or looping uselessly.

## Fallbacks are a security feature, not an afterthought

The fastest way to generate angry reviews is to make biometrics the *only* door. Fingerprints stop reading with dry skin or a screen protector; face unlock fails in the dark; sensors break. Always provide a path:

- Include `DEVICE_CREDENTIAL` in `setAllowedAuthenticators` so the system dialog offers PIN/pattern/password natively — no custom fallback UI needed.
- For a full auth (not just decrypting local data), keep your account password / [OAuth flow](https://blog.michaelsam94.com/oauth-pkce-mobile/) available so a user on a new device with no enrolled biometrics can still get in.

Note one API subtlety: you cannot combine `BIOMETRIC_STRONG or DEVICE_CREDENTIAL` with a `CryptoObject` on all API levels the same way, and `setNegativeButtonText` is mutually exclusive with allowing device credential. Read the current constraints for your `minSdk` rather than assuming — the framework has tightened these over versions.

## What "done right" looks like

A correct biometric implementation: checks `canAuthenticate` and routes each state, requires `BIOMETRIC_STRONG` whenever a secret is involved, binds the prompt to a Keystore key with `setUserAuthenticationRequired` and enrollment invalidation, distinguishes transient failures from lockout errors, and *always* offers a credential fallback. Get those five things right and you have authentication whose security is enforced by hardware and whose UX doesn't strand users when a fingerprint won't read. Skip the crypto binding and you've built a pretty dialog that protects nothing.

## Resources

- [BiometricPrompt and the Biometric library (Android)](https://developer.android.com/identity/sign-in/biometric-auth)
- [BiometricManager authenticator types](https://developer.android.com/reference/androidx/biometric/BiometricManager.Authenticators)
- [Android Keystore system](https://developer.android.com/privacy-and-security/keystore)
- [Measuring biometric security (Android CDD)](https://source.android.com/docs/security/features/biometric)
- [OWASP MASVS authentication requirements](https://mas.owasp.org/MASVS/)
