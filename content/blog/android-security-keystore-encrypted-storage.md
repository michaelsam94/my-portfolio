---
title: "Android Security: Keystore, Encrypted Storage, Secrets"
slug: "android-security-keystore-encrypted-storage"
description: "How to store secrets on Android the right way: Android Keystore, hardware-backed keys, biometric-gated crypto, and what to use now that EncryptedSharedPreferences is deprecated."
datePublished: "2026-04-22"
dateModified: "2026-04-22"
tags: ["Android", "Security", "Kotlin", "Cryptography"]
keywords: "Android Keystore, encrypted storage, Android security, secure storage, biometric auth, EncryptedSharedPreferences, hardware-backed keys"
faq:
  - q: "Is EncryptedSharedPreferences still recommended in 2026?"
    a: "No. The androidx.security:security-crypto library that provided EncryptedSharedPreferences is deprecated. For new code, use the Android Keystore directly with your own AES/GCM wrapper, or a maintained solution like Jetpack DataStore combined with a Keystore-derived key."
  - q: "What can the Android Keystore actually protect against?"
    a: "The Keystore keeps key material out of your app's process and, on most modern devices, inside a hardware security module (TEE or StrongBox). It protects secrets from other apps and from an attacker who extracts your app's files, but not from a fully rooted device running while the user is authenticated."
  - q: "How do I require a fingerprint before decrypting data?"
    a: "Generate a Keystore key with setUserAuthenticationRequired(true), then unlock a Cipher through BiometricPrompt's CryptoObject. The key only performs crypto operations after a successful biometric authentication, binding decryption to the user's presence."
---

The fastest way to fail a mobile security review is to store a token in `SharedPreferences` as plaintext and assume the app sandbox is enough. It isn't on a rooted device, it isn't in a backup, and it isn't when someone pulls the APK apart. Android gives you real primitives to do better — the **Android Keystore** for hardware-backed keys, and a small amount of AES/GCM glue to encrypt everything else. This is the setup I've shipped in fintech apps that had to pass third-party pen tests, written plainly.

The headline change since older guides: **`EncryptedSharedPreferences` is deprecated.** The `androidx.security:security-crypto` library is no longer the recommended path, so new code should lean on the Keystore directly. Let me walk through what the Keystore actually buys you, then the patterns that replace the old convenience wrappers.

## What the Keystore is — and isn't

The Android Keystore is a system service that generates and stores cryptographic keys so that the **key material never enters your app's process memory**. You ask it to encrypt or sign; it does the operation and hands back the result. On devices with a Trusted Execution Environment (TEE) or a dedicated StrongBox secure element, the keys live in hardware that the main OS can't read even if it's compromised.

That's a strong guarantee, but be honest about the boundary. The Keystore protects against another app reading your keys, against someone extracting your app's data directory, and against keys leaking into backups. It does **not** magically protect data that's decrypted and sitting in memory while the app runs, and a determined attacker on a rooted device with the app unlocked can still observe plaintext. Security is about raising cost, not achieving the impossible.

## Generating a hardware-backed key

You request a key with a `KeyGenParameterSpec`. The important flags are the algorithm, the block mode, and whether the key is bound to user authentication:

```kotlin
private fun getOrCreateKey(alias: String): SecretKey {
    val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
    (keyStore.getKey(alias, null) as? SecretKey)?.let { return it }

    val spec = KeyGenParameterSpec.Builder(
        alias,
        KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
    )
        .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
        .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
        .setKeySize(256)
        .setUserAuthenticationRequired(false) // flip to true for biometric gating
        .build()

    return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        .apply { init(spec) }
        .generateKey()
}
```

Use **AES-256 in GCM mode**. GCM is authenticated encryption, so it detects tampering — critical, because CBC without a MAC is a classic footgun. Never reuse an IV with GCM; generate a fresh one per encryption and store it alongside the ciphertext.

## Encrypting real data

With the key in hand, encryption is a few lines. Prepend the IV to the ciphertext so you can decrypt later:

```kotlin
fun encrypt(alias: String, plaintext: ByteArray): ByteArray {
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey(alias))
    val iv = cipher.iv // 12 bytes for GCM
    val ciphertext = cipher.doFinal(plaintext)
    return iv + ciphertext
}

fun decrypt(alias: String, data: ByteArray): ByteArray {
    val iv = data.copyOfRange(0, 12)
    val ciphertext = data.copyOfRange(12, data.size)
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(alias), GCMParameterSpec(128, iv))
    return cipher.doFinal(ciphertext)
}
```

Persist the resulting bytes wherever is convenient — a file, a Room column, or **Jetpack DataStore**. DataStore is the modern replacement for `SharedPreferences`, and pairing it with Keystore-encrypted values gives you the ergonomics people liked about `EncryptedSharedPreferences` without the deprecated dependency.

## Biometric-gated decryption

For high-value secrets — a banking session, a stored PIN — bind the key to the user's presence. Set `setUserAuthenticationRequired(true)` when generating, then unlock the cipher through `BiometricPrompt`:

```kotlin
val cipher = Cipher.getInstance("AES/GCM/NoPadding").apply {
    init(Cipher.DECRYPT_MODE, getOrCreateKey("session"), GCMParameterSpec(128, iv))
}
biometricPrompt.authenticate(
    promptInfo,
    BiometricPrompt.CryptoObject(cipher),
)
```

The key physically will not perform the operation until the biometric succeeds — the `CryptoObject` ties authentication to crypto at the hardware level. That's meaningfully stronger than "check a boolean, then decrypt," because there's no boolean an attacker can flip. Use `setUserAuthenticationParameters` to control how long an authentication stays valid before re-prompting.

## Practical rules I hold teams to

- **No secrets in the APK.** API keys baked into `BuildConfig` or resources are trivially extracted with `apktool`. Fetch runtime secrets from your backend after authentication, and keep truly sensitive logic server-side.
- **Exclude sensitive files from backup.** Set `android:allowBackup` carefully and use backup exclusion rules so encrypted blobs and keys don't get swept into cloud backups.
- **Detect obvious tampering, don't rely on it.** Root/emulator checks and Play Integrity raise the bar, but treat them as signals, not a wall. This mirrors the [zero-trust posture I take for mobile apps](https://blog.michaelsam94.com/zero-trust-mobile-apps/).
- **Handle key invalidation.** If the user changes their lock screen or adds a fingerprint, auth-bound keys can be permanently invalidated (`KeyPermanentlyInvalidatedException`). Catch it, wipe the stale secret, and re-provision gracefully instead of crashing.
- **StrongBox where available.** Call `setIsStrongBoxBacked(true)` and fall back if the device throws — it moves keys into a dedicated secure chip on supported hardware.

None of this is a huge amount of code. The mistakes that fail audits aren't exotic — they're plaintext tokens, reused IVs, secrets in the binary, and CBC without authentication. Get the Keystore wrapper right once, gate the crown jewels behind biometrics, and store everything through DataStore, and you have a storage layer that holds up under scrutiny. For the broader picture on protecting user data on device, I've written more in [privacy engineering for mobile and GDPR](https://blog.michaelsam94.com/privacy-engineering-mobile-gdpr/).

## Resources

- [Android Keystore system — developer guide](https://developer.android.com/privacy-and-security/keystore)
- [Cryptography best practices on Android](https://developer.android.com/privacy-and-security/cryptography)
- [BiometricPrompt reference](https://developer.android.com/reference/androidx/biometric/BiometricPrompt)
- [Work with data more securely](https://developer.android.com/privacy-and-security/security-tips)
- [Jetpack DataStore guide](https://developer.android.com/topic/libraries/architecture/datastore)
- [Play Integrity API](https://developer.android.com/google/play/integrity)
