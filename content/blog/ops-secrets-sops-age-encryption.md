---
title: "GitOps Secrets with SOPS"
slug: "ops-secrets-sops-age-encryption"
description: "Encrypt secrets in Git with Mozilla SOPS and age: key management, Argo CD integration, rotation workflows, and why sealed-secrets isn't always the answer."
datePublished: "2026-01-20"
dateModified: "2026-01-20"
tags: ["DevOps", "GitOps", "Security", "Kubernetes"]
keywords: "SOPS age encryption, GitOps secrets, Argo CD SOPS, Mozilla SOPS Kubernetes, encrypted secrets Git"
faq:
  - q: "Why use SOPS instead of Kubernetes Sealed Secrets?"
    a: "SOPS encrypts secret values inside YAML/JSON files that remain partially readable — you can commit structure and non-secret fields in cleartext. Sealed Secrets encrypts entire Secret objects into opaque blobs. SOPS works across repos (Terraform, Helm, Kustomize); Sealed Secrets is Kubernetes-specific."
  - q: "How does age compare to PGP for SOPS?"
    a: "age is simpler: one small key file, no keyserver, no expiration ceremony. PGP works if your org already has GPG infrastructure. For new GitOps setups, age is the default recommendation in SOPS docs."
  - q: "Where should SOPS age private keys live in production?"
    a: "Never in Git. Store in a secrets manager (AWS Secrets Manager, Vault) or CI/CD OIDC-bound variable. Argo CD pulls the key via init container, sidecar (ksops), or the argocd-vault-plugin. Rotate by adding a new age recipient before removing the old one."
---

Storing `DATABASE_URL` in a private Git repo felt safe until a contractor's laptop synced the clone. Plaintext secrets in Git have infinite audit trail — the wrong kind. We moved to SOPS with age keys because the encrypted files still diff cleanly in PRs, reviewers see *which* secret changed without seeing the value, and the same files work in Terraform and Kubernetes manifests.

## How SOPS encryption works

SOPS encrypts values (or entire files) using AES, then encrypts the data key with one or more recipient public keys (age or PGP). The file stays valid YAML:

```yaml
# secrets.enc.yaml (committed to Git)
apiVersion: v1
kind: Secret
metadata:
  name: api-credentials
stringData:
  DATABASE_URL: ENC[AES256_GCM,data:8Kj2...,iv:...,tag:...,type:str]
  REDIS_PASSWORD: ENC[AES256_GCM,data:Xm9p...,iv:...,tag:...,type:str]
sops:
  age:
    - recipient: age1ql3z7hjy54gd3wtfaqgyp3fw8jfcj938qkdwxd0q47tgn3g2ss0qcrq8q
      enc: |
        -----BEGIN AGE ENCRYPTED FILE-----
        ...
  lastmodified: "2026-01-15T10:00:00Z
  version: 3.9.0
```

Only holders of the age private key decrypt. Everyone else reviews structure.

## Setup: age + SOPS

```bash
# Generate age key pair
age-keygen -o key.txt
# Public key goes in .sops.yaml; private key stays in 1Password / Vault

# .sops.yaml in repo root
creation_rules:
  - path_regex: \.enc\.yaml$
    age: age1ql3z7hjy54gd3wtfaqgyp3fw8jfcj938qkdwxd0q47tgn3g2ss0qcrq8q
```

Encrypt and edit:

```bash
sops -e secrets.yaml > secrets.enc.yaml   # encrypt
sops secrets.enc.yaml                      # decrypt to temp, edit, re-encrypt on save
```

Pre-commit hook runs `sops -e` or rejects commits containing `.dec.yaml` files.

## Argo CD integration with KSOPS

Argo CD doesn't natively decrypt SOPS. Options:

**KSOPS (Kustomize plugin)** — generate Secrets at build time:

```yaml
# kustomization.yaml
generators:
  - ksops-secret-generator.yaml

# ksops-secret-generator.yaml
apiVersion: viaduct.ai/v1
kind: ksops
metadata:
  name: api-secrets
files:
  - secrets.enc.yaml
```

Configure Argo CD repo-server with the age private key:

```yaml
# argocd-repo-server patch — mount key from K8s secret
volumeMounts:
  - name: sops-age
    mountPath: /home/argocd/.config/sops/age
    readOnly: true
volumes:
  - name: sops-age
    secret:
      secretName: sops-age-key
```

**Helm secrets plugin** — `helm-secrets` with SOPS backend for Helm-based apps.

**External Secrets Operator** — SOPS decrypts to ESO, ESO syncs to cluster Secret. Adds a hop but centralizes rotation.

## Multi-environment key strategy

Don't share one age key across prod and dev. Compromised dev laptop shouldn't decrypt prod.

| Environment | age recipient | Key storage |
|-------------|---------------|-------------|
| dev | dev-team public key | Developer 1Password |
| staging | CI + platform public keys | Vault |
| prod | platform-only public key | Vault + break-glass |

Same secret name, different encrypted files per overlay:

```
overlays/
├── dev/secrets.enc.yaml      # encrypted for dev key
├── staging/secrets.enc.yaml
└── prod/secrets.enc.yaml     # encrypted for prod key only
```

Developers edit dev secrets locally. Prod secrets changed only via platform team PR with four-eyes review.

## Rotation without downtime

**Secret value rotation:**
1. Update value in secrets manager / database
2. `sops secrets.enc.yaml` → change value → commit
3. Argo CD syncs → rolling restart picks up new Secret

**Key rotation:**
1. Generate new age key pair
2. Add new public key to `.sops.yaml` recipients (both old and new)
3. `sops updatekeys secrets.enc.yaml` re-encrypts with new key
4. Deploy new private key to Argo CD repo-server
5. Remove old recipient after confirming sync works

Never delete the old private key until all files are re-encrypted and deployed.

## Common pitfalls

**Encrypting only some fields.** SOPS `encrypted_regex` helps — `'^(data|stringData)$'` for K8s Secrets. Missing a field leaks cleartext in Git.

**PR bots printing decrypted diffs.** Configure CI to never echo decrypted output. Review encrypted blob changes + commit message.

**Local decrypt files committed.** Add `*.dec.yaml` and `*.dec.yml` to `.gitignore`. Pre-commit hook enforcement.

**Terraform state still has secrets.** SOPS encrypts files in Git; `terraform apply` may still write secrets to state. Use remote state encryption and restrict state bucket access.

## Rotation drills

Run quarterly SOPS rotation drills: generate new age key, re-encrypt one non-critical secret file, deploy to staging, verify Argo CD sync, roll back procedure documented. Drills surface broken KSOPS paths before emergency rotation after key compromise.

Never store age private keys in the same S3 bucket as encrypted secrets — separate blast radius. Break-glass key copy in physical vault for ransomware scenarios where cloud KMS access is lost.

## Common production mistakes

Teams get secrets sops age encryption wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of secrets sops age encryption fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When secrets sops age encryption misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Mozilla SOPS documentation](https://github.com/getsops/sops)
- [age encryption specification](https://age-encryption.org/v1)
- [KSOPS Kustomize plugin](https://github.com/viaduct-ai/kustomize-sops)
- [Argo CD SOPS integration guide](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/)
- [Helm secrets plugin](https://github.com/jkroepke/helm-secrets)
