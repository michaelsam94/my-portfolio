---
title: "Column-Level Encryption with PostgreSQL pgcrypto"
slug: "agent-column-encryption-pgcrypto"
description: "Encrypt sensitive agent data at the column level using PostgreSQL pgcrypto: key management, envelope encryption, searchable hashes, rotation, and query patterns that survive audits."
datePublished: "2025-01-04"
dateModified: "2025-01-04"
tags: ["PostgreSQL", "Security", "Encryption", "AI Agents"]
keywords: "pgcrypto column encryption, postgres encrypt column, agent data encryption, envelope encryption postgres, pgp_sym_encrypt"
faq:
  - q: "When is pgcrypto column encryption the right choice versus application-level encryption or TDE?"
    a: "Use pgcrypto when you need field-level protection inside PostgreSQL — PII in agent conversation logs, API keys in config tables — and want encryption close to data without a separate vault round-trip per row. Application-level encryption gives you more algorithm control; TDE (transparent data encryption) protects disks but not DBAs. Column encryption protects against snapshot leaks and casual SELECT * exposure."
  - q: "Can you search or index encrypted columns with pgcrypto?"
    a: "Not on ciphertext directly. Store a deterministic HMAC or hash of the plaintext in a separate column for equality lookups (email, external ID). Range queries and full-text search require plaintext sidecars, blind indexes, or accepting decrypt-in-app patterns. Plan access patterns before encrypting."
  - q: "How do you rotate encryption keys without downtime?"
    a: "Use envelope encryption: a data encryption key (DEK) per row or tenant, wrapped by a key encryption key (KEK) in KMS. Rotation re-wraps DEKs with a new KEK; background jobs re-encrypt row data with new DEKs during low traffic. Never store the KEK in the database."
  - q: "Does pgcrypto protect against privileged DBAs?"
    a: "Partially. A superuser can read keys if you pass them through SQL session variables carelessly. Combine column encryption with least-privilege roles, avoid superuser app connections, and use KMS-backed keys fetched by the application — not stored in Postgres settings. Assume DBA can see schema and ciphertext; plaintext requires key access you control."
---

Agent platforms persist conversation transcripts, tool outputs, OAuth tokens, and tenant API keys. Row-level security keeps tenant A from reading tenant B's rows, but a backup leak, replica snapshot, or over-privileged analyst account still exposes plaintext if columns store secrets directly. **PostgreSQL pgcrypto** encrypts at the column level inside the database boundary — useful when agents write sensitive fields through ORMs and you need defense in depth without rewriting every query path through an external vault.

The hard part is not calling `pgp_sym_encrypt`. It is key lifecycle, searchable ciphertext tradeoffs, and migration paths that do not lock you out of your own data.

## Threat model and placement

Column encryption with pgcrypto addresses:

- Backup/tape exposure (ciphertext without keys is useless)
- Accidental `SELECT *` in analytics replicas
- Compromised read-only credentials that should not see PII

It does **not** address:

- Application compromise (attacker inherits decrypt path)
- Superuser with key material in session
- SQL injection that exfiltrates after decrypt in query

```
┌─────────────┐     KEK in KMS/Vault     ┌──────────────┐
│  App layer  │ ─── fetch DEK wrap ────► │  PostgreSQL  │
│  (agent)    │     pgp_sym_encrypt      │  (ciphertext)│
└─────────────┘                          └──────────────┘
```

Place decryption in a thin repository layer — not scattered in every agent tool handler.

## Schema pattern

Enable extension and define encrypted columns as `bytea`:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE agent_sessions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL,
  user_id       UUID NOT NULL,
  -- searchable blind index for tenant+user lookups
  user_id_hmac  BYTEA NOT NULL,
  transcript    BYTEA,           -- encrypted JSON
  api_key       BYTEA,           -- encrypted secret
  dek_id        TEXT NOT NULL,   -- which DEK wrapped this row
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX agent_sessions_user_lookup
  ON agent_sessions (tenant_id, user_id_hmac);

-- RLS still required — encryption ≠ authorization
ALTER TABLE agent_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON agent_sessions
  USING (tenant_id = current_setting('app.tenant_id')::uuid);
```

Separate **encryption** from **authorization**. Encrypted columns without RLS still leak metadata and row counts.

## Encrypt and decrypt functions

Wrap pgcrypto in SQL functions so application code calls stable interfaces:

```sql
CREATE OR REPLACE FUNCTION encrypt_column(
  plaintext TEXT,
  dek BYTEA
) RETURNS BYTEA
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT pgp_sym_encrypt(plaintext, encode(dek, 'hex'), 'cipher-algo=aes256');
$$;

CREATE OR REPLACE FUNCTION decrypt_column(
  ciphertext BYTEA,
  dek BYTEA
) RETURNS TEXT
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT pgp_sym_decrypt(ciphertext, encode(dek, 'hex'))::text;
$$;

-- Blind index for equality search (use tenant-scoped pepper)
CREATE OR REPLACE FUNCTION blind_index(
  value TEXT,
  pepper BYTEA
) RETURNS BYTEA
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT hmac(value, pepper, 'sha256');
$$;
```

Application repository (TypeScript):

```typescript
import { Pool } from "pg";
import { getDekForTenant } from "./kms";

export class SessionRepository {
  constructor(private pool: Pool) {}

  async insertSession(tenantId: string, userId: string, transcript: object) {
    const dek = await getDekForTenant(tenantId);
    const pepper = await getBlindIndexPepper(tenantId);

    await this.pool.query(
      `INSERT INTO agent_sessions (tenant_id, user_id, user_id_hmac, transcript, dek_id)
       VALUES ($1, $2, blind_index($3, $4), encrypt_column($5, $6), $7)`,
      [
        tenantId,
        userId,
        userId,
        pepper,
        JSON.stringify(transcript),
        dek.material,
        dek.id,
      ]
    );
  }

  async getTranscript(sessionId: string, tenantId: string): Promise<object> {
    const dek = await getDekForTenant(tenantId);
    const { rows } = await this.pool.query(
      `SELECT decrypt_column(transcript, $1) AS plaintext
       FROM agent_sessions WHERE id = $2 AND tenant_id = $3`,
      [dek.material, sessionId, tenantId]
    );
    return JSON.parse(rows[0].plaintext);
  }
}
```

Never log DEKs or decrypted plaintext in agent tracing spans.

## Key management architecture

**Anti-pattern**: one global passphrase in `DATABASE_URL` or a Postgres GUC.

**Production pattern**: envelope encryption per tenant or per table class.

```typescript
interface DataEncryptionKey {
  id: string;
  material: Buffer;  // 32 bytes AES-256
  wrapped: Buffer;   // ciphertext stored in kms_wrapped_deks table
}

async function getDekForTenant(tenantId: string): Promise<DataEncryptionKey> {
  const cached = dekCache.get(tenantId);
  if (cached) return cached;

  const row = await db.query(
    `SELECT dek_id, wrapped_blob FROM kms_wrapped_deks WHERE tenant_id = $1 AND active = true`,
    [tenantId]
  );
  const material = await kms.decrypt(row.wrapped_blob); // AWS KMS, GCP CKMS, Vault
  const dek = { id: row.dek_id, material, wrapped: row.wrapped_blob };
  dekCache.set(tenantId, dek, { ttl: 300_000 });
  return dek;
}
```

Store only wrapped DEKs in Postgres. Raw key material lives in memory briefly.

## Migration from plaintext columns

Strangle migration in four phases:

```sql
-- Phase 1: add nullable encrypted columns
ALTER TABLE agent_sessions ADD COLUMN transcript_enc BYTEA;
ALTER TABLE agent_sessions ADD COLUMN dek_id TEXT;

-- Phase 2: backfill (batch job, rate-limited)
-- UPDATE ... SET transcript_enc = encrypt_column(transcript::text, dek), dek_id = ...

-- Phase 3: dual-read — app tries enc first, falls back to plaintext
-- Phase 4: drop plaintext column after verification window
ALTER TABLE agent_sessions DROP COLUMN transcript;
ALTER TABLE agent_sessions RENAME COLUMN transcript_enc TO transcript;
```

Track backfill progress:

```sql
CREATE TABLE encryption_migration_status (
  table_name TEXT PRIMARY KEY,
  rows_total BIGINT,
  rows_encrypted BIGINT,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);
```

Pause agent writes to affected tables only if you cannot dual-write — prefer dual-write with feature flag.

## Query patterns and limitations

| Access pattern | Approach |
|----------------|----------|
| Fetch by primary key | Decrypt in SELECT |
| Filter by email/user ID | `blind_index` column + HMAC |
| Full-text on transcript | Do not encrypt fields you must search — tokenize/redact instead |
| Analytics aggregates | ETL to warehouse with separate access controls; no decrypt in BI |
| ORDER BY encrypted field | Not supported — sort keys stay plaintext or derived |

Agent memory systems often need semantic search on transcripts. Options:

1. **Redact before index**: store encrypted full transcript + plaintext summary with PII stripped for embedding index.
2. **Searchable encryption** (specialized, heavy): usually not worth it for agent logs.
3. **Decrypt in secure enclave** for batch indexing — rare outside regulated environments.

## Rotation runbook

**KEK rotation** (annual or on incident):

1. Create `kek_v2` in KMS.
2. Background job: `wrapped_v2 = kms.encrypt(dek, kek_v2)` for each row in `kms_wrapped_deks`.
3. Flip `active` flag to v2 wrapped blobs.
4. Retire v1 after all rows re-wrapped.

**DEK rotation** (per tenant compromise):

1. Generate new DEK for tenant.
2. Re-encrypt all rows: `UPDATE ... SET col = encrypt_column(decrypt_column(col, old_dek), new_dek)`.
3. Batch in chunks of 1000 with `FOR UPDATE SKIP LOCKED` to avoid table locks.

```sql
-- Chunked re-encrypt
WITH batch AS (
  SELECT id FROM agent_sessions
  WHERE tenant_id = $1 AND dek_id = $2
  LIMIT 1000
  FOR UPDATE SKIP LOCKED
)
UPDATE agent_sessions s
SET transcript = encrypt_column(decrypt_column(transcript, $3), $4),
    dek_id = $5
FROM batch b WHERE s.id = b.id;
```

## Performance considerations

`pgp_sym_encrypt/decrypt` is CPU-bound. Measure on production-shaped row sizes:

- Agent transcripts (10–500 KB JSON): decrypt adds 1–5 ms per row at p95 — acceptable for single-session fetch, painful for bulk export.
- API keys (short strings): negligible overhead.

Mitigations:

- Cache decrypted session headers in Redis with short TTL for hot agent threads.
- Do not decrypt in list endpoints — return metadata only.
- Use connection pooling; crypto in Postgres consumes CPU on the primary — watch `pg_stat_activity` wait events during backfill.

## Compliance and audit

Document in your data map:

- Algorithm: `aes256` via OpenPGP symmetric (pgcrypto default path)
- Key storage: KMS ARN, rotation schedule
- Who can decrypt: application role `agent_app` — not `analytics_readonly`

Audit log decrypt access at application layer:

```typescript
async function getTranscriptAudited(sessionId: string, actor: string) {
  await auditLog.write({ action: "decrypt", resource: sessionId, actor });
  return repo.getTranscript(sessionId);
}
```

Pg audit extensions log SQL but not which human triggered the app path — app-level audit is mandatory for SOC2/HIPAA narratives.

## Testing

Integration test with real Postgres + pgcrypto:

```typescript
test("round-trip encrypt decrypt", async () => {
  const dek = crypto.randomBytes(32);
  const { rows } = await pool.query(
    `SELECT decrypt_column(encrypt_column($1, $2), $2) AS out`,
    ['{"role":"user","content":"secret"}', dek]
  );
  expect(rows[0].out).toBe('{"role":"user","content":"secret"}');
});

test("blind index stable per pepper", async () => {
  const pepper = crypto.randomBytes(32);
  const a = await pool.query(`SELECT blind_index('user@x.com', $1) AS h`, [pepper]);
  const b = await pool.query(`SELECT blind_index('user@x.com', $1) AS h`, [pepper]);
  expect(a.rows[0].h).toEqual(b.rows[0].h);
});
```

Include migration tests that verify dual-read paths and backfill completeness gates.

## The takeaway

pgcrypto column encryption gives agent platforms a practical middle ground between plaintext Postgres and full application-side crypto. Success depends on envelope key management, blind indexes for lookups you still need, chunked rotation jobs, and keeping decryption in one repository layer — not spread across fifty agent tools. Encrypt what must stay confidential at rest; do not encrypt fields you still need to search — redesign those paths instead.

## Resources

- [PostgreSQL pgcrypto documentation](https://www.postgresql.org/docs/current/pgcrypto.html)
- [PostgreSQL column encryption best practices (Crunchy Data)](https://www.crunchydata.com/blog/postgres-data-encryption-at-rest)
- [AWS KMS envelope encryption guide](https://docs.aws.amazon.com/kms/latest/developerguide/concepts.html#enveloping)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
- [Blind index pattern for searchable encryption limitations](https://paragonie.com/blog/2017/05/building-searchable-encrypted-databases-with-php-and-sql)
