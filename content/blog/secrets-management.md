---
title: "Secrets Management Done Right"
slug: "secrets-management"
description: "A practical guide to secrets management: why .env files leak, how to use Vault and KMS, dynamic credentials, rotation, and keeping secrets out of your mobile app."
datePublished: "2026-07-11"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "secrets management, HashiCorp Vault, secret rotation, environment secrets, credential security, KMS, dynamic secrets"
faq:
  - q: "Why are .env files bad?"
    a: "Plaintext, easily committed, not centrally rotatable or auditable."
  - q: "KMS vs secrets manager?"
    a: "KMS manages keys; secrets managers store and distribute secrets using KMS underneath."
  - q: "What are dynamic secrets?"
    a: "Short-lived credentials generated on demand and auto-revoked."
---

Most breaches I've seen up close didn't start with a clever exploit — they started with a credential in the wrong place. An AWS key in a git commit. A database password in a Slack thread. A `.env` file copied to a laptop that later got stolen. Secrets management is the discipline of making sure credentials are stored, delivered, rotated, and audited so that a single leak doesn't hand an attacker your whole system.

The uncomfortable truth is that `.env` files and hard-coded constants are where most teams start and far too many teams stay. They work until they don't, and when they don't, the failure is catastrophic and silent — you often learn a key leaked months after it happened. Getting secrets management right is mostly about removing standing, long-lived credentials from places humans and code can accidentally expose them.

## Why plaintext and .env files fail

A `.env` file is convenient and that's exactly the problem. It ends up committed to a repo, baked into a Docker image layer, printed in CI logs, or synced to a backup. There's no rotation story, no access audit, and no revocation short of changing the secret everywhere by hand. You can't answer "who accessed the production DB password last week?" because nothing recorded it.

The first improvement isn't a fancy tool — it's a boundary: **secrets never live in source control, never in image layers, never in logs.** Add a pre-commit scanner like `gitleaks` and a CI scan so a leaked key fails the build:

```bash
gitleaks detect --source . --redact --exit-code 1
```

That alone catches a huge class of accidents. But detection is a backstop. The real fix is that applications fetch secrets at runtime from a system built for it.

## Centralize with Vault or a cloud secrets manager

A secrets manager — [HashiCorp Vault](https://developer.hashicorp.com/vault), AWS Secrets Manager, Google Secret Manager, Azure Key Vault — becomes the single source of truth. Apps authenticate to it with a workload identity and fetch secrets at boot or on demand. The manager handles encryption at rest, access policy, audit logging, and rotation.

The authentication piece is where people cut corners. Don't give the app a static token to talk to Vault — that's just a secret to protect the secrets. Use workload identity: the pod's Kubernetes service account, the cloud instance's IAM role, or Vault's own auth methods.

```hcl
# Vault policy: this app may only read its own database secret
path "database/creds/orders-api" {
  capabilities = ["read"]
}
```

Scope tightly. An app should read only the secrets it needs, nothing more. Broad "read all secrets" policies turn one compromised service into a total compromise.

## Dynamic secrets beat static ones

The best static secret is no static secret. Vault's dynamic secrets engine generates a credential on request with a short lease and revokes it automatically when the lease expires:

```bash
# App requests a database credential valid for 1 hour
vault read database/creds/orders-api
# => username: v-token-orders-x7f2, password: A1a-..., lease_duration: 1h
```

Now a leaked database password is useful for at most an hour, and every issuance is logged against the requesting identity. The same pattern works for cloud credentials, PKI certificates, and SSH access. This is the same short-lived-credential philosophy behind [keyless artifact signing](https://blog.michaelsam94.com/supply-chain-security-slsa-sbom/) — reduce the window a leaked credential is useful to near zero.

## Rotation is a schedule, not a fire drill

If rotating a secret requires a maintenance window and three engineers, it won't happen, and a secret that never rotates is a secret that's been compromised long enough to matter. Rotation should be automatic and boring:

| Secret type | Rotation approach |
| --- | --- |
| Database passwords | Dynamic secrets (rotate per lease) or scheduled auto-rotation |
| API keys to third parties | Scheduled rotation with dual-key overlap |
| TLS certificates | Automated issuance (cert-manager, Vault PKI, ACME) |
| Signing keys | Keyless (Sigstore) or KMS-managed with rotation |
| Encryption keys | KMS with automatic key rotation enabled |

The dual-key overlap trick matters for third-party APIs that don't support dynamic secrets: provision the new key, deploy it, verify traffic, then revoke the old one. No downtime, no scramble.

## KMS for the keys themselves

A KMS handles the cryptographic layer — it holds master keys in hardware-backed modules and performs encrypt/decrypt operations without ever exposing the key material. Use envelope encryption: the KMS encrypts a data key, the data key encrypts your data, and you store the encrypted data key alongside the ciphertext. This is what secrets managers use under the hood, and it's what you'd use directly to encrypt a database column or a backup.

## Secrets on mobile: assume nothing stays secret

Mobile deserves its own warning. Anything shipped in an APK or IPA is extractable — there is no such thing as a secret embedded in a client binary. If your app needs to call a third-party API with a secret key, that call belongs on your backend, with the app authenticating to *your* server instead. Where the app must store something sensitive locally, like a session token, use the platform keystore as I describe in [Android Keystore and encrypted storage](https://blog.michaelsam94.com/android-security-keystore-encrypted-storage/), and keep the standing authority on the server per [zero-trust mobile](https://blog.michaelsam94.com/zero-trust-mobile-apps/) principles.

## Where to start

If you're staring at a pile of `.env` files, don't boil the ocean:

1. Add secret scanning to pre-commit and CI today — stop the bleeding.
2. Move production credentials into a secrets manager with workload-identity auth.
3. Rotate everything once, so you know nothing predates the migration.
4. Convert your highest-value static secrets (database, cloud creds) to dynamic.
5. Automate rotation so step 3 never has to be manual again.

Secrets management done right means that when a laptop is stolen or a repo goes public, your answer isn't panic — it's "those credentials were short-lived, scoped, and already rotated." That's the difference between an incident and a breach.

## Operational notes for secrets management

Audit secret access monthly: Vault audit log or cloud trail for Secrets Manager GetSecretValue filtered by production paths. Revoke credentials owned by departed employees the same day — standing API keys in shared vault folders accumulate owners quickly. Run game day: rotate database dynamic secret while traffic flows, measure app reconnect time, ensure connection pools refresh leases without manual pod restart unless your framework requires it.

## Notes on secrets management

Audit secret access monthly: Vault audit log or cloud trail for Secrets Manager GetSecretValue filtered by production paths. Revoke credentials owned by departed employees the same day — standing API keys in shared vault folders accumulate owners quickly. Run game day: rotate database dynamic secret while traffic flows, measure app reconnect time, ensure connection pools refresh leases without manual pod restart unless your framework requires it.

## Resources

- [HashiCorp Vault documentation](https://developer.hashicorp.com/vault/docs)
- [AWS Secrets Manager](https://docs.aws.amazon.com/secretsmanager/)
- [Google Cloud Secret Manager](https://cloud.google.com/secret-manager/docs)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [NIST SP 800-57 — Key Management Recommendations](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [gitleaks — secret scanning](https://github.com/gitleaks/gitleaks)

Break-glass credentials need hardware MFA, ticket reference, and weekly review; dynamic secrets reduce how often break-glass is needed.

Review secrets management metrics after the next release train on mid-tier mobile devices — regressions that pass lab Lighthouse often fail CrUX field data.

## Envelope encryption pattern

KMS encrypts a data key; the data key encrypts application secrets at rest. Rotate KMS keys annually; re-encrypt data keys without application downtime using KMS automatic rotation where supported.
