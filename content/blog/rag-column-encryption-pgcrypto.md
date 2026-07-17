---
title: "RAG: Column Encryption Pgcrypto"
slug: "rag-column-encryption-pgcrypto"
description: "Encrypt sensitive RAG metadata at rest in Postgres with pgcrypto—document content hashes, user query logs, and API keys stored as AES-encrypted columns with key rotation via envelope encryption."
datePublished: "2025-01-03"
dateModified: "2026-07-17"
tags: ["AI", "Rag", "Column"]
keywords: "pgcrypto, column encryption, Postgres, RAG security, AES encryption, data at rest, PII protection, envelope encryption"
faq:
  - q: "What RAG data should be encrypted at the Postgres column level?"
    a: "Encrypt user query text in audit logs, document content previews stored for debugging, API keys for embedding providers, tenant configuration secrets, and any PII in retrieval metadata (user emails in access logs). Vector embeddings themselves are usually not encrypted—search requires plaintext vectors—but associated metadata may be."
  - q: "How does pgcrypto column encryption differ from Postgres TDE or disk encryption?"
    a: "Disk encryption (TDE) protects against physical media theft but exposes plaintext to anyone with SQL access. pgcrypto column encryption protects against DB-level breaches—an attacker with SQL read access gets ciphertext without the encryption key. Use both: TDE for infrastructure layer, pgcrypto for application-layer column protection."
  - q: "How do you rotate pgcrypto encryption keys without downtime?"
    a: "Use envelope encryption: pgcrypto encrypts with a data encryption key (DEK) stored encrypted by a master key (KEK) in KMS. Rotation re-encrypts DEKs with new KEK—column data stays unchanged. Full re-encryption of column data only needed when DEK itself rotates, done in background batches."
---
The RAG audit table stored every user query in plaintext for debugging retrieval quality. A read-replica misconfiguration exposed the table to an analytics tool with overly broad credentials. The queries contained customer names, account numbers, and internal project codenames. Column-level encryption with pgcrypto would have limited exposure to ciphertext—but it wasn't implemented because "Postgres already encrypts at rest." Disk encryption protects disks, not SQL sessions.

RAG systems persist sensitive data in Postgres: query audit logs, document metadata with PII, tenant API keys, and retrieval debug snapshots. pgcrypto provides application-layer column encryption when compliance requires defense-in-depth beyond infrastructure encryption.

## pgcrypto basics

Enable extension:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

Symmetric encryption functions:

```sql
-- Encrypt
SELECT encode(
  encrypt(
    'sensitive query text'::bytea,
    'encryption-key'::bytea,
    'aes-256-cbc'
  ),
  'base64'
);

-- Decrypt
SELECT convert_from(
  decrypt(
    decode('base64-ciphertext', 'base64'),
    'encryption-key'::bytea,
    'aes-256-cbc'
  ),
  'UTF8'
);
```

Never store the encryption key in the database or application config plaintext—use envelope encryption with KMS.

## Schema design for encrypted RAG columns

```sql
CREATE TABLE rag_query_audit (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL,
  user_id UUID NOT NULL,
  -- Encrypted columns store base64 ciphertext
  query_text_enc BYTEA NOT NULL,
  query_text_dek_id UUID NOT NULL,  -- which DEK encrypted this row
  retrieved_chunk_ids UUID[] NOT NULL,  -- not sensitive, plaintext OK
  corpus_version TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE rag_tenant_secrets (
  tenant_id UUID PRIMARY KEY,
  embedding_api_key_enc BYTEA NOT NULL,
  dek_id UUID NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DEK registry (DEKs themselves encrypted by KEK in KMS)
CREATE TABLE rag_encryption_deks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  kek_version INT NOT NULL,
  encrypted_dek BYTEA NOT NULL,  -- DEK encrypted by KMS KEK
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Separate DEK per row or per tenant depending on rotation requirements.

## Application-layer encrypt/decrypt

```python
# crypto/column_encryption.py
import base64
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import boto3

kms = boto3.client("kms")
KEK_ID = os.environ["KMS_KEY_ID"]

def get_dek(dek_id: str) -> bytes:
    """Fetch and decrypt DEK from registry using KMS"""
    encrypted_dek = db.get_encrypted_dek(dek_id)
    response = kms.decrypt(CiphertextBlob=encrypted_dek)
    return response["Plaintext"]

def encrypt_column(plaintext: str, dek_id: str) -> bytes:
    dek = get_dek(dek_id)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(dek), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padded = pkcs7_pad(plaintext.encode())
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return iv + ciphertext  # prepend IV for decryption

def decrypt_column(ciphertext: bytes, dek_id: str) -> str:
    dek = get_dek(dek_id)
    iv, encrypted = ciphertext[:16], ciphertext[16:]
    cipher = Cipher(algorithms.AES(dek), modes.CBC(iv))
    decryptor = cipher.decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()
    return pkcs7_unpad(padded).decode()
```

Or use pgcrypto directly in SQL for simpler cases:

```python
async def insert_audit_log(query_text: str, tenant_id: str, dek_id: str):
    dek = get_dek(dek_id)
    await db.execute(
        """
        INSERT INTO rag_query_audit (tenant_id, query_text_enc, query_text_dek_id, ...)
        VALUES ($1, encrypt($2::bytea, $3::bytea, 'aes-256-cbc'), $4, ...)
        """,
        tenant_id, query_text, dek, dek_id,
    )
```

## Envelope encryption with KMS

Master key (KEK) lives in AWS KMS, GCP Cloud KMS, or HashiCorp Vault. Data encryption keys (DEKs) encrypt column data:

```
KMS KEK encrypts DEK → encrypted_dek stored in Postgres
DEK encrypts column data → ciphertext stored in Postgres
```

New tenant onboarding:

```python
async def create_tenant_dek(tenant_id: str) -> str:
    dek = os.urandom(32)  # 256-bit AES key
    encrypted_dek = kms.encrypt(KeyId=KEK_ID, Plaintext=dek)["CiphertextBlob"]
    dek_id = str(uuid.uuid4())
    await db.execute(
        "INSERT INTO rag_encryption_deks (id, kek_version, encrypted_dek) VALUES ($1, $2, $3)",
        dek_id, CURRENT_KEK_VERSION, encrypted_dek,
    )
    return dek_id
```

KMS never sees column plaintext—only DEK material.

## Key rotation

**KEK rotation (annual):** KMS rotates KEK automatically. Re-encrypt DEKs:

```python
async def rotate_kek():
    old_deks = await db.fetch("SELECT id, encrypted_dek FROM rag_encryption_deks WHERE active")
    for dek_row in old_deks:
        # KMS re-encrypt: decrypt with old KEK version, encrypt with new
        new_encrypted_dek = kms.re_encrypt(
            CiphertextBlob=dek_row["encrypted_dek"],
            DestinationKeyId=KEK_ID,
        )["CiphertextBlob"]
        await db.execute(
            "UPDATE rag_encryption_deks SET encrypted_dek = $1, kek_version = $2 WHERE id = $3",
            new_encrypted_dek, NEW_KEK_VERSION, dek_row["id"],
        )
```

Column ciphertext unchanged—only DEK wrapper re-encrypted.

**DEK rotation (on compromise or policy):** Generate new DEK, background re-encrypt all rows:

```python
async def rotate_dek(old_dek_id: str, new_dek_id: str, table: str, column: str):
    rows = await db.fetch(f"SELECT id, {column} FROM {table} WHERE query_text_dek_id = $1", old_dek_id)
    for row in rows:
        plaintext = decrypt_column(row[column], old_dek_id)
        new_ciphertext = encrypt_column(plaintext, new_dek_id)
        await db.execute(
            f"UPDATE {table} SET {column} = $1, query_text_dek_id = $2 WHERE id = $3",
            new_ciphertext, new_dek_id, row["id"],
        )
    await db.execute("UPDATE rag_encryption_deks SET active = FALSE WHERE id = $1", old_dek_id)
```

Run in batches during low traffic.

## What not to encrypt in RAG Postgres

| Data | Encrypt? | Reason |
|------|----------|--------|
| User query text (audit) | ✅ Yes | PII, sensitive |
| Vector embeddings | ❌ No | Search requires plaintext |
| Chunk text content | ⚠️ Maybe | If stored for debug; prefer not storing |
| doc_id, tenant_id | ❌ No | Needed for indexed queries |
| corpus_version | ❌ No | Non-sensitive metadata |
| Embedding API keys | ✅ Yes | Secrets |
| Retrieval scores | ❌ No | Non-sensitive |

Encrypting vectors breaks pgvector similarity search unless using specialized encrypted search (research stage, not production ready).

## Query patterns with encrypted columns

Encrypted columns cannot be searched or indexed directly:

```sql
-- ❌ Cannot do this on encrypted column
SELECT * FROM rag_query_audit WHERE query_text_enc ILIKE '%refund%';

-- ✅ Search on non-sensitive metadata, decrypt on read
SELECT id, tenant_id, created_at FROM rag_query_audit
WHERE tenant_id = $1 AND created_at > $2
ORDER BY created_at DESC
LIMIT 100;
-- Decrypt query_text_enc in application layer for display
```

For audit search requirements, store searchable tokenized hashes separately (non-reversible) or use a dedicated audit search index with access controls.

## Compliance mapping

- **GDPR Article 32** — encryption as technical measure for personal data
- **HIPAA** — addressable encryption specification for ePHI
- **PCI DSS** — encryption of cardholder data at rest (if payment queries logged)
- **SOC 2 CC6.1** — logical access controls including encryption

Document encryption architecture in data flow diagrams for security reviews.

## Performance considerations

pgcrypto adds CPU overhead per encrypt/decrypt operation:

- Batch audit log inserts: encrypt in application before INSERT
- Read-heavy audit UI: decrypt on fetch, cache decrypted results briefly
- Connection pooling: DEK cache in application memory (TTL 5 min) avoids KMS call per row

Benchmark: AES-256-CBC encrypt/decrypt ~10μs per KB on modern CPU—negligible for audit log rows, measurable at 10k QPS.

Column encryption with pgcrypto is defense-in-depth for RAG Postgres data—not a substitute for access controls, network isolation, or avoiding storage of sensitive query text when not needed. Encrypt what you must store; minimize what you store.

## Audit log retention with encrypted columns

Encrypted audit columns complicate log retention policies—deletion must remove ciphertext rows, not rely on TTL on plaintext search indexes. Implement retention job that deletes rag_query_audit rows older than policy window by created_at without needing decryption. Legal hold flags prevent deletion of ciphertext rows for specific tenants during litigation—hold applies to encrypted data same as plaintext.

## Developer experience for encrypted columns

ORM abstraction hides encrypt/decrypt from business logic—developers query audit logs without handling ciphertext directly. TypeDecorator in SQLAlchemy or custom Prisma middleware transparently encrypts on write and decrypts on read. Document which columns encrypted in schema comments. Onboarding docs explain: never log decrypted query text, never include in error messages sent to clients, never cache decrypted values in Redis without separate encryption.

## Field checklist for column encryption pgcrypto

Before calling this done in production, confirm you can measure success and failure independently: a positive metric (throughput, conversion, recall) and a negative one (abuse rate, false accepts, lag). Add one alert that pages on the negative metric and one dashboard panel for the positive. Run a staging drill that forces the failure mode — timeout, poison input, or partial outage — and capture the exact commands in the runbook next to the config. If the drill takes longer than fifteen minutes to execute, simplify the recovery path before you need it at 2am.

## Resources

- PostgreSQL pgcrypto documentation
- AWS KMS envelope encryption patterns
- NIST SP 800-57 key management recommendations
- OWASP Cryptographic Storage Cheat Sheet
