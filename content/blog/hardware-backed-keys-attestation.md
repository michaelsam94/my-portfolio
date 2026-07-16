---
title: "Hardware-Backed Keys and Key Attestation"
slug: "hardware-backed-keys-attestation"
description: "Hardware-backed keys and key attestation on Android explained: StrongBox vs TEE, how attestation proves a key never left secure hardware, and where the guarantees end."
datePublished: "2026-04-28"
dateModified: "2026-04-28"
tags: ["Security", "Android", "Cryptography"]
keywords: "hardware backed keys, key attestation, StrongBox, TEE, secure enclave, Android Keystore attestation"
faq:
  - q: "What are hardware-backed keys?"
    a: "Hardware-backed keys are cryptographic keys generated and stored inside dedicated secure hardware — a Trusted Execution Environment (TEE) or a StrongBox secure element — rather than in normal app memory or disk. The private key material never leaves that hardware; your app can only ask the hardware to sign or decrypt with it. This means even a fully compromised OS or rooted device cannot extract the raw key."
  - q: "What is key attestation and why does it matter?"
    a: "Key attestation is a signed certificate chain, rooted in a manufacturer key, that proves a specific key was generated inside genuine secure hardware and describes its properties — whether it requires biometric auth, whether it's in StrongBox, the device's boot state, and more. It lets your backend verify these guarantees remotely instead of trusting the client's word, which is essential for high-assurance flows like payments or device binding."
  - q: "What is the difference between StrongBox and the TEE?"
    a: "The TEE is a secure area of the main application processor, isolated from the normal OS by hardware. StrongBox is a separate, dedicated tamper-resistant security chip (a secure element) with its own CPU and memory, offering stronger protection against physical and side-channel attacks. StrongBox is more secure but slower and not present on every device, so you request it with a graceful fallback to the TEE."
---

If your app protects anything worth stealing — auth tokens, payment credentials, encryption keys for local data — the question that matters is not "is the key encrypted" but "where does the private key actually live, and can malware get at it." Hardware-backed keys answer that: the key is generated inside secure silicon, the raw private material never crosses into the OS, and your code can only *use* the key by asking the hardware to perform an operation. Key attestation is the companion mechanism that lets a remote server *prove* this is true for a given key, rather than taking a possibly-compromised client's word for it.

I've shipped device-binding and secure-storage features on Android for years, and the gap between "we used the Keystore" and "we used the Keystore *correctly, with attestation*" is enormous. The first is table stakes; the second is what actually resists a determined attacker.

## What "hardware-backed" buys you

On Android, the [Keystore system](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/) can create keys whose private material is confined to secure hardware. The practical guarantee is *key non-exportability*: there is no API, even for the OS, to read the raw bytes out. An attacker who fully roots the device and dumps app memory finds handles and ciphertext, not the key.

Two hardware tiers back this:

| Tier | Where it runs | Protection level | Availability |
| --- | --- | --- | --- |
| **TEE** | Secure world on the main SoC | Isolated from OS, resists software attacks | Nearly all modern Android devices |
| **StrongBox** | Separate tamper-resistant secure element | Resists physical + side-channel attacks | Newer/flagship devices only |

The TEE (implementations like ARM TrustZone) isolates a "secure world" on the same processor. StrongBox is a physically separate chip — its own CPU, RAM, and secure storage — hardened against fault injection and probing. StrongBox is stronger but slower and not universal, so the right pattern is request-with-fallback, not assume-present.

## Generating a hardware-backed key

Here's a signing key that prefers StrongBox, falls back to the TEE, and requires user authentication before each use:

```kotlin
val spec = KeyGenParameterSpec.Builder(
    "device_binding_key",
    KeyProperties.PURPOSE_SIGN or KeyProperties.PURPOSE_VERIFY
).run {
    setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
    setDigests(KeyProperties.DIGEST_SHA256)
    setUserAuthenticationRequired(true)
    setUserAuthenticationParameters(0, KeyProperties.AUTH_BIOMETRIC_STRONG)
    setIsStrongBoxBacked(true)          // ask for StrongBox
    setAttestationChallenge(serverNonce) // request an attestation cert chain
    build()
}

val kpg = KeyPairGenerator.getInstance(
    KeyProperties.KEY_ALGORITHM_EC, "AndroidKeyStore"
)
try {
    kpg.initialize(spec)
} catch (e: StrongBoxUnavailableException) {
    kpg.initialize(spec.rebuiltWithoutStrongBox()) // graceful fallback to TEE
}
val keyPair = kpg.generateKeyPair()
```

Two things are doing the real work. `setUserAuthenticationRequired(true)` binds key usage to a fresh biometric or device-credential check — the hardware won't sign unless the user just authenticated. And `setAttestationChallenge(serverNonce)` is what makes the next section possible.

## Attestation: proving it to a server

A hardware-backed key is only half the story. Your backend still has to believe the client. Key attestation closes that gap: when you set an attestation challenge, the hardware produces an X.509 certificate chain that chains up to a Google (or manufacturer) root, with a leaf certificate whose extension encodes the key's exact properties.

The flow that actually holds up:

1. The server generates a random nonce and sends it to the app.
2. The app generates the key with that nonce as the attestation challenge.
3. The app sends the resulting certificate chain to the server.
4. The server verifies the chain to a trusted root, confirms the nonce matches (defeats replay), and reads the attestation extension.

From that extension the server learns things the client cannot lie about: whether the key is in StrongBox or the TEE, whether user authentication is enforced, the verified boot state of the device, the OS patch level, and more. Because the whole chain is signed by hardware the attacker doesn't control, a rooted device can't fabricate a "this key is in StrongBox with biometric protection" claim.

```kotlin
val chain = keyStore.getCertificateChain("device_binding_key")
// POST chain to the backend; the server does the trust decision, not the app.
val encoded = chain.map { it.encoded }
apiClient.submitAttestation(encoded)
```

The design principle I hammer on: **the trust decision lives on the server.** Doing attestation parsing on-device and then reporting "yep, we're secure" is pointless — that's the exact code an attacker patches out. The certificate chain exists so an *untrusted* client can hand an artifact to a *trusted* server for verification.

## Where the guarantees actually end

Hardware-backed keys and attestation are strong, but I've seen them over-trusted, so here's the honest boundary.

- **Attestation proves properties of the key and device, not that your app is unmodified.** A repackaged app can still generate a legitimate hardware key. Combine attestation with Play Integrity / app-level checks if app authenticity matters.
- **"User present" is only as good as the auth policy.** If you set a long authentication validity window, malware acting soon after a legitimate unlock may still trigger signing. For high-value operations, require auth per-use.
- **The root of trust is the manufacturer.** You're transitively trusting Google's and OEMs' provisioning. There have been key-provisioning incidents; keep your list of trusted roots and revocation current.
- **Algorithms age.** Today's EC/RSA hardware keys will eventually face quantum-capable adversaries, which is why long-lived key material should be part of your [post-quantum cryptography migration](https://blog.michaelsam94.com/post-quantum-cryptography-migration/) planning rather than assumed permanent.

## When it's worth the complexity

Not every app needs this. For a note-taking app, standard Keystore encryption is plenty. I reach for full hardware-backed keys plus server-verified attestation when the stakes justify it: payment and wallet apps, device binding for step-up auth, DRM, enterprise MDM, and anything where "prove this device is genuine hardware in a good state" is a real business requirement.

The cost is real — StrongBox operations are noticeably slower, attestation adds a server-side verification service you must maintain, and the fallback matrix across device tiers needs testing on actual hardware, not just emulators. But when you need to *cryptographically prove* that a secret lives in tamper-resistant silicon and can only be used by an authenticated user, there's no software substitute. That provable, hardware-rooted assurance is exactly what these APIs exist to give you.

## Resources

- [Android Developers — Android Keystore system](https://developer.android.com/privacy-and-security/keystore)
- [Android Developers — Verifying hardware-backed key pairs with Key Attestation](https://developer.android.com/privacy-and-security/security-key-attestation)
- [Android — Hardware-backed Keystore (AOSP)](https://source.android.com/docs/security/features/keystore)
- [Android — StrongBox and secure elements](https://source.android.com/docs/compatibility/cdd)
- [Google — Play Integrity API](https://developer.android.com/google/play/integrity)
- [NIST — Recommendation for Key Management (SP 800-57)](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
