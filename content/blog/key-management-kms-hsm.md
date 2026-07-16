---
title: "KMS and HSM Fundamentals"
slug: "key-management-kms-hsm"
description: "Key management with KMS and HSM: envelope encryption, key hierarchy, rotation, cloud vs hardware modules, and application patterns that keep plaintext keys out of code."
datePublished: "2025-11-09"
dateModified: "2025-11-09"
tags: ["Security", "KMS"]
keywords: "KMS, HSM, envelope encryption, key rotation, AWS KMS, data encryption key, FIPS 140-2"
faq:
  - q: "What is the difference between KMS and an HSM?"
    a: "KMS is a key management service—APIs, policies, rotation schedules, and audit logs around cryptographic keys. An HSM is hardware (or cloud-backed hardware) that generates and stores keys in tamper-resistant modules where private key material never leaves the device in plaintext. Cloud KMS products often use HSMs under the hood for root keys."
  - q: "Why use envelope encryption instead of encrypting data directly with KMS?"
    a: "KMS encrypt/decrypt operations have latency limits and payload size caps—typically 4 KB on AWS KMS. Envelope encryption generates a data encryption key locally, encrypts bulk data with AES, and wraps the DEK with a KMS master key. You encrypt gigabytes without sending them through KMS APIs."
  - q: "How often should encryption keys rotate?"
    a: "Master keys in KMS often rotate automatically on a yearly cadence or on demand after compromise. Data encryption keys should be unique per object or session and discarded after use. Rotation does not require re-encrypting all historical data immediately if you version keys and retain decrypt capability for old ciphertext."
---

An engineer pasted an AES-256 key into a Slack channel so staging could decrypt a database dump. The key lived in chat history, a `.env` file, and three laptops. Rotating it meant redeploying six services and re-encrypting a terabyte of backups over a weekend. KMS exists so that story never happens: keys stay in a vault with IAM boundaries, every use is logged, and rotation is a API call—not a scavenger hunt through config repos.

**Key Management Service (KMS)** and **Hardware Security Modules (HSM)** form the backbone of production encryption. KMS is the control plane—who can use which key, when, and from where. HSM is the trust anchor—where keys are born and where private material stays unexportable.

## Key hierarchy and envelope encryption

Most applications should never hold long-lived master keys. The pattern:

1. KMS holds a **Customer Master Key (CMK)** or **Key Encryption Key (KEK)**
2. Application generates a random **Data Encryption Key (DEK)**
3. Encrypt payload locally with DEK (AES-GCM)
4. Call KMS to encrypt the DEK → store ciphertext + wrapped DEK together

```kotlin
// Conceptual flow with AWS SDK v2
val kms = KmsClient.create()
val generateResponse = kms.generateDataKey {
    it.keyId(keyArn)
    it.keySpec(DataKeySpec.AES_256)
}
val plaintextDek = generateResponse.plaintext().asByteArray()
val wrappedDek = generateResponse.ciphertextBlob().asByteArray()

try {
    val cipher = Cipher.getInstance("AES/GCM/NoPadding")
    cipher.init(Cipher.ENCRYPT_MODE, SecretKeySpec(plaintextDek, "AES"))
    val ciphertext = cipher.doFinal(userData)
    store(wrappedDek, cipher.iv, ciphertext)
} finally {
    plaintextDek.fill(0) // zeroize
}
```

Decrypt reverses: KMS unwraps DEK, local AES decrypts payload. Master key never touched bulk data.

## Cloud KMS vs dedicated HSM

| Aspect | Cloud KMS (AWS, GCP, Azure) | Dedicated HSM (CloudHSM, on-prem) |
|--------|----------------------------|-----------------------------------|
| Operations | Fully managed, API-driven | You manage cluster, PKCS#11 |
| Compliance | FIPS 140-2 Level 2 typical | Level 3 options for stricter regimes |
| Multi-tenant | Shared infrastructure | Single-tenant hardware |
| Cost model | Per-request + key monthly | Fixed cluster cost |
| Latency | Low ms, regional | Depends on placement |

Use managed KMS for application encryption, secrets wrapping, and database TDE integration. Move to dedicated HSM when regulations require single-tenant hardware, custom key ceremonies, or PKCS#11 signing with non-exportable keys for PKI roots.

## IAM, policies, and least privilege

Keys are useless without policy discipline. Grant `kms:Decrypt` only to the role that reads ciphertext, `kms:GenerateDataKey` only to writers:

```json
{
  "Effect": "Allow",
  "Action": ["kms:GenerateDataKey", "kms:Decrypt"],
  "Resource": "arn:aws:kms:eu-west-1:123456789012:key/abc-123",
  "Condition": {
    "StringEquals": {
      "kms:EncryptionContext:service": "payments-api"
    }
  }
}
```

**Encryption context** is authenticated auxiliary data—bind ciphertext to tenant or resource ID so a stolen blob cannot decrypt under a generic grant.

Enable CloudTrail or equivalent on every `Decrypt` call. Alert on spikes from unexpected principals.

## Rotation without downtime

Automatic CMK rotation generates new backing material while preserving decrypt of old ciphertext. Application code using `keyId` alias (`alias/payments-master`) picks up new material transparently.

For envelope-encrypted objects, each object stores which key version wrapped its DEK. Re-encryption jobs can rewrite objects with new DEKs during maintenance—prioritize high-sensitivity buckets first.

Never embed key IDs in client apps. Mobile and browser clients should not call KMS directly; use a backend that performs crypto or issue short-lived tokens.

## HSM use cases beyond storage encryption

- **Code signing** — private key non-exportable, signing happens inside HSM
- **TLS private keys** — terminate TLS with keys that never hit disk
- **Database TDE** — Oracle/SQL Server integrated HSM providers
- **PKCS#11** — standard API for hardware tokens and payment HSMs

Payment networks often mandate HSMs for PIN translation and MAC generation. Application teams still interact through KMS-like APIs; only crypto officers touch physical modules.

## Common mistakes

- Encrypting large blobs directly with RSA KMS calls
- Storing wrapped DEKs without integrity protection (use AES-GCM, not AES-CBC alone)
- Sharing one DEK across all tenants
- Disabling audit logs to save cost
- Using `Encrypt` on predictable plaintext—use hashing or add random padding for small secrets

Test failure modes: KMS throttling, regional outage, expired credentials. Cache DEKs in memory with TTL for hot paths only—never persist plaintext DEKs.

## Dual control for root keys

Cloud KMS automatic rotation does not replace dual-control ceremonies for root keys in regulated environments—document who can `ScheduleKeyDeletion` and require MFA plus ticket.


## What to measure after rollout

Track error rates, tail latency, and resource utilization for two weeks after changes land—most regressions appear under real traffic mixes, not in staging smoke tests. Keep a rollback path documented: feature flags, Helm revision, or Git revert with known good digest. Review on-call pages tied to the topic quarterly; delete alerts that never fire and add thresholds that would have caught your last incident.

Run a short blameless postmortem if production surprised you, even for minor issues. The goal is updating this runbook section with one concrete lesson per quarter so the next engineer inherits context, not just configuration snippets.


## Pre-production checklist

Before promoting to production, walk through this list with someone who was not the primary author—fresh eyes catch assumptions.

- **Staging parity**: The staging environment exercises the same code paths as production, including failure modes you expect to handle (timeouts, retries, partial outages).
- **Observability**: Dashboards and alerts exist for the metrics and log patterns discussed above; on-call knows where to look first.
- **Rollback**: You can revert to the previous known-good state in one documented step without improvising.
- **Access control**: Only the principals that need access have it; audit logs are enabled where the topic touches secrets or infrastructure APIs.
- **Load test**: You have evidence—not intuition—about behavior at expected peak plus headroom.

If any item is "we will do that later," treat it as a release blocker for tier-1 services.


## Resources

- [AWS KMS developer guide](https://docs.aws.amazon.com/kms/latest/developerguide/overview.html) — envelope encryption walkthrough and quotas
- [NIST SP 800-57 key management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final) — key lifecycle recommendations
- [Google Cloud KMS documentation](https://cloud.google.com/kms/docs) — key rings, versions, and EKM
- [FIPS 140-2/140-3 overview](https://csrc.nist.gov/projects/cryptographic-module-validation-program) — validation levels for HSM procurement
