---
title: "Envelope Encryption at Rest"
slug: "encryption-at-rest-envelope"
description: "Protect stored data with envelope encryption: DEKs wrapped by KMS, key rotation without re-encrypting terabytes, and patterns for databases and object storage."
datePublished: "2025-12-19"
dateModified: "2025-12-19"
tags: ["Security", "Encryption", "KMS", "Cloud"]
keywords: "envelope encryption, data encryption key DEK, KMS key wrapping, encryption at rest, key rotation envelope, AWS KMS envelope encryption, TDE vs envelope"
faq:
  - q: "What is the difference between envelope encryption and full-disk encryption?"
    a: "Full-disk or volume encryption (LUKS, BitLocker, EBS encryption) protects storage media from physical theft. Envelope encryption protects individual objects or records with unique data keys wrapped by a KMS master key — enabling per-tenant keys, granular rotation, and crypto-shredding without re-encrypting entire disks."
  - q: "How often should I rotate DEKs versus KMS keys?"
    a: "Rotate KMS master keys annually or on compromise per policy — wrapped DEKs re-wrap without decrypting data. Rotate or version DEKs when you need crypto-shredding (delete customer data irreversibly) or on a schedule for high-sensitivity fields. Re-encrypting all data with new DEKs is expensive — design for lazy rotation on read/write."
  - q: "Can I implement envelope encryption without a cloud KMS?"
    a: "Yes — use HashiCorp Vault transit, SoftHSM with PKCS#11, or on-prem HSMs. The pattern is the same: master key never leaves HSM; application requests GenerateDataKey and Decrypt(wrapped_dek). Cloud KMS reduces HSM ops burden but adds vendor dependency."
---

Storing AES-256 keys next to the data they encrypt is security theater with better labels. Envelope encryption separates the problem: a random data encryption key (DEK) encrypts your payload; a key encryption key (KEK) managed in KMS or an HSM wraps the DEK. Compromise of one database backup exposes only wrapped blobs — useless without KMS Decrypt permission and audit-logged access. Rotation becomes wrapping a new DEK instead of decrypting a terabyte warehouse and re-encrypting overnight.

## The envelope pattern

```
                    ┌─────────────┐
 Plaintext ──DEK──► │ Ciphertext  │
                    └─────────────┘
                           │
 DEK ──KEK (KMS)──► Wrapped DEK stored alongside ciphertext
```

Operations:

1. **GenerateDataKey** — KMS returns plaintext DEK (memory only) + wrapped DEK blob
2. Encrypt data locally with plaintext DEK (AES-GCM)
3. Discard plaintext DEK from memory
4. Store `{ciphertext, wrapped_dek, iv, aad}` — never store plaintext DEK at rest

Decrypt reverses: KMS unwraps DEK, local AES-GCM decrypts payload.

## AWS KMS example

```python
import boto3
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

kms = boto3.client("kms")
KEK_ID = "arn:aws:kms:us-east-1:123456789012:key/abcd-..."

def encrypt_field(plaintext: bytes, aad: bytes) -> dict:
    resp = kms.generate_data_key(KeyId=KEK_ID, KeySpec="AES_256")
    dek = resp["Plaintext"]
    wrapped = resp["CiphertextBlob"]

    iv = os.urandom(12)
    aesgcm = AESGCM(dek)
    ct = aesgcm.encrypt(iv, plaintext, aad)

    dek = b"\x00" * len(dek)  # zeroize best-effort
    return {"ct": ct, "wrapped_dek": wrapped, "iv": iv}

def decrypt_field(blob: dict, aad: bytes) -> bytes:
    dek = kms.decrypt(CiphertextBlob=blob["wrapped_dek"])["Plaintext"]
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(blob["iv"], blob["ct"], aad)
```

Use AAD (additional authenticated data) for tenant ID or record type — tampering with metadata fails GCM verification.

## Per-tenant and per-object DEKs

Shared DEK across all rows simplifies implementation but enables bulk decrypt on one key leak. Per-tenant DEKs:

```python
def tenant_kek_alias(tenant_id: str) -> str:
    return f"alias/tenant-{tenant_id}"
```

KMS supports per-tenant CMKs or envelope with tenant ID in AAD. Crypto-shredding a tenant: delete their CMK or wrapped DEKs — data becomes unrecoverable even if ciphertext leaks.

Object storage (S3) client-side envelope encryption before upload ensures ciphertext at rest even if bucket policy misconfigured — SSE-KMS server-side is simpler but less portable across clouds.

## Key rotation without downtime

**KMS CMK rotation** — AWS rotates backing material annually; re-wrap DEKs on next read:

```python
def rewrap_if_needed(wrapped_dek: bytes) -> bytes:
    # Decrypt still works with old material; ReEncrypt wraps under new
    return kms.re_encrypt(
        CiphertextBlob=wrapped_dek,
        DestinationKeyId=KEK_ID,
    )["CiphertextBlob"]
```

**Lazy DEK rotation** — on write path, generate new DEK; old records decrypt with stored wrapped blob until touched.

Never log plaintext DEKs or KMS responses containing them.

## Database field encryption

For PostgreSQL application-level encryption:

| Column | Contents |
|--------|----------|
| `ssn_ciphertext` | bytea |
| `ssn_wrapped_dek` | bytea |
| `ssn_iv` | bytea |
| `dek_version` | int |

Index on hash of searchable fields (HMAC with separate key) if equality search needed — encrypted columns are not indexable for range queries without deterministic encryption (weaker — use sparingly).

## Threat model clarity

Envelope encryption protects **data at rest** on stolen disks/backups. It does not protect against:

- Compromised application with KMS Decrypt IAM role
- SQL injection returning decrypted rows in-app
- Memory dumps on live servers

Combine with TLS in transit, least-privilege IAM, and field-level access controls in application code.

## KMS key hierarchy and rotation

Organize keys in a hierarchy for blast radius control:

```
AWS Account
└── CMK: master-key (annual rotation)
    ├── DEK: tenant-a-data-key (per-tenant isolation)
    ├── DEK: tenant-b-data-key
    └── DEK: application-secrets-key
```

CMK (Customer Master Key) never encrypts data directly — only wraps DEKs. Rotate CMK annually; re-wrap DEKs with new CMK version. DEK rotation on write path — old records decrypt with stored wrapped blob until touched.

```python
def encrypt_field(plaintext: bytes, kms_client, cmk_id: str) -> EncryptedField:
    # Generate fresh DEK per record
    dek = os.urandom(32)
    ciphertext = aes_gcm_encrypt(plaintext, dek)
    wrapped_dek = kms_client.encrypt(KeyId=cmk_id, Plaintext=dek)
    return EncryptedField(ciphertext=ciphertext, wrapped_dek=wrapped_dek['CiphertextBlob'])
```

## Envelope encryption performance

KMS calls add latency — batch and cache:

| Operation | Latency | Mitigation |
|---|---|---|
| KMS GenerateDataKey | 10–50ms | Generate DEK locally, wrap async |
| KMS Decrypt | 10–50ms | Cache unwrapped DEK in memory (TTL 5min) |
| AES-GCM encrypt | <1ms | Always local |

Cache unwrapped DEKs in application memory with short TTL — never cache in Redis or shared storage. KMS call only on cache miss.

## Compliance and key custody

| Requirement | Implementation |
|---|---|
| PCI DSS | CMK in HSM; no plaintext key export |
| HIPAA | Encryption at rest + access audit log |
| GDPR | Key deletion = crypto-shredding |
| SOC 2 | Key rotation documented and tested |

Crypto-shredding: delete wrapped DEK → data permanently unrecoverable without brute force. Faster and more complete than overwriting ciphertext.

## Failure modes

- **DEK logged in plaintext** — encryption worthless; audit all log statements
- **Single CMK for all tenants** — blast radius on key compromise
- **KMS call per field read** — latency explosion; cache unwrapped DEKs
- **No key rotation procedure** — compliance audit failure
- **Application has KMS Decrypt on all data** — envelope encryption doesn't protect against app compromise

## Production checklist

- CMK in HSM-backed KMS (AWS KMS, GCP Cloud KMS, Vault)
- Per-tenant or per-data-class DEK isolation
- Unwrapped DEK cached in memory with short TTL (not shared storage)
- Key rotation procedure documented and tested annually
- Crypto-shredding procedure for GDPR right-to-erasure
- Access audit log enabled on all KMS Decrypt operations

Test key rotation in staging quarterly — a rotation procedure that hasn't been exercised is a compliance checkbox, not a recovery capability.

## Resources

- [AWS KMS envelope encryption](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#enveloping)
- [Google Cloud KMS envelope encryption](https://cloud.google.com/kms/docs/envelope-encryption)
- [NIST SP 800-57 key management recommendations](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [HashiCorp Vault transit secrets engine](https://developer.hashicorp.com/vault/docs/secrets/transit)
- [RFC 5116 — AES-GCM for authenticated encryption](https://www.rfc-editor.org/rfc/rfc5116)
