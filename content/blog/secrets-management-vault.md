---
title: "Secrets Management with Vault"
slug: "secrets-management-vault"
description: "Centralize secrets with HashiCorp Vault: dynamic credentials, policies, Kubernetes auth, and patterns that beat .env files."
datePublished: "2025-06-28"
dateModified: "2026-07-17"
tags:
  - "Security"
  - "Vault"
  - "DevOps"
  - "Secrets"
keywords: "HashiCorp Vault secrets, dynamic database credentials, Vault Kubernetes auth, secret management, Vault policies, lease revocation"
faq:
  - q: "When should I use Vault instead of cloud secret managers?"
    a: "Vault fits multi-cloud, on-prem hybrid, and dynamic secret generation across uniform API. Cloud-native teams often use AWS Secrets Manager or GCP Secret Manager with less ops overhead. Vault wins when you need one abstraction spanning Kubernetes, VMs, and CI with detailed policy-as-code."
  - q: "What are dynamic secrets?"
    a: "Vault generates short-lived credentials on demand—Postgres user valid 1 hour, then auto-revoked. Applications request creds at startup and refresh before lease expiry. Compromised credentials self-destruct instead of living until someone rotates a static password in a spreadsheet."
  - q: "How do pods authenticate to Vault?"
    a: "Kubernetes auth method maps service account JWT to Vault role and policy. Pod mounts projected SA token, exchanges for Vault token, reads secret path. No long-lived Vault root token in cluster—bootstrap with auto-unseal and break-glass procedures only."
---
Forty microservices each mount a Kubernetes Secret copied from last year's onboarding doc. Rotation means editing YAML in forty repos and hoping nobody cached the old DB password in a crash dump. HashiCorp Vault stores secrets centrally, audits every read, and can mint database credentials that expire in an hour. The operational cost is real—unseal, HA, backups—but static secrets in git is technical debt with compound interest.

## Core concepts

- **Secrets engine:** KV (static), database (dynamic), PKI, AWS IAM
- **Policy:** path-based ACL (`secret/data/prod/api` read)
- **Auth method:** Kubernetes, AppRole, OIDC, AWS IAM
- **Lease:** TTL after which secret revokes automatically

## Static secrets in KV v2

```bash
vault kv put secret/prod/payment stripe_key=$STRIPE_KEY
vault kv get -field=stripe_key secret/prod/payment
```

Versioned; rollback supported. Still static—rotate via CI pushing new version and signaling apps to reload.

## Dynamic PostgreSQL credentials

Configure database secrets engine with connection URL and creation SQL:

```sql
CREATE ROLE "{{name}}" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}';
GRANT SELECT ON orders TO "{{name}}";
```

Application:

```python
 creds = vault.read("database/creds/orders-readonly")
 conn = psycopg2.connect(user=creds["username"], password=creds["password"], ...)
```

Renew lease before TTL; Vault revokes role on expiry.

## Kubernetes auth

```yaml
# Pod annotation for Vault Agent Injector
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "api-service"
vault.hashicorp.com/agent-inject-secret-config: "secret/data/prod/api"
```

Sidecar renders file or env vars; app unchanged. Map `ServiceAccount` → Vault role with minimal policy.

## Policy least privilege

```hcl
path "secret/data/prod/api" {
  capabilities = ["read"]
}
path "database/creds/orders-readonly" {
  capabilities = ["read"]
}
```

Separate policies per service. Deny by default.

## Unseal and HA

Production uses auto-unseal via cloud KMS. Shamir shards for break-glass only. Monitor seal status; sealed Vault denies all reads—page immediately.

Enable audit device to immutable storage. Every secret read ties to identity—compliance and incident forensics.

Unseal monitoring pages immediately—sealed Vault denies all reads. Auto-unseal via KMS for production; Shamir shards break-glass only.

Policy least privilege per service account. Deny by default. Audit device to immutable storage for every secret read during incidents.

Kubernetes auth maps service account JWT to role—no root token in cluster. Vault Agent Injector sidecar pattern keeps apps unchanged while credentials rotate.

## Dynamic database credentials

Vault database secrets engine issues two-hour PostgreSQL users per application role. Application connects with short-lived creds; DBA revokes lease on compromise. Connection pool must handle credential rotation mid-process—refresh on auth error with backoff.

## Namespace isolation per environment

`prod/`, `staging/`, `dev/` Vault namespaces or path prefixes prevent staging CI from reading prod secrets. Policy as code in Terraform reviews path grants in PR.

## Break-glass procedures

Emergency root token sealed in physical safe with quarterly drill. Automated alerts on root token usage. Normal operations use OIDC auth to Vault with group mappings from IdP.

## Secrets Management Vault: operational depth

Centralized secrets management fails when applications still read Kubernetes secrets as plaintext env vars at rest. Teams that skip instrumentation ship blind—baseline p75 latency and error rate on affected routes one week before change and compare seven days after.

Integration boundaries deserve contract tests with golden fixtures sampled from production traffic anonymized. Synthetic empty payloads pass CI while production fails on nullable fields you never modeled.

Security review asks three questions: what untrusted input enters, what secrets could leak in logs, and what happens when upstream is slow or malicious. Answers belong in the PR, not a post-launch wiki page.

Rollout prefers feature flags or canary deploys when behavior touches authentication, payments, or PII. Rollback command documented in runbook header—not discovered during incident via git archaeology.

On-call dashboards slice metrics by region and device class. Global averages hide mobile regressions until App Store reviews mention slowness—field data honesty beats demo Lighthouse scores.

## Resources

- [HashiCorp Vault documentation](https://developer.hashicorp.com/vault/docs)
- [Vault Kubernetes auth method](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [Vault database secrets engine](https://developer.hashicorp.com/vault/docs/secrets/databases)
- [Vault Agent Injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

## Extended guidance (1) for Secrets Management Vault

Operators owning secrets management vault should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (2) for Secrets Management Vault

Operators owning secrets management vault should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (3) for Secrets Management Vault

Operators owning secrets management vault should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (4) for Secrets Management Vault

Operators owning secrets management vault should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.

## Extended guidance (5) for Secrets Management Vault

Operators owning secrets management vault should run a pre-mortem before launch: dependency unavailable, duplicate events, certificate expiry, regional failover. Each scenario needs detectable metrics, a runbook step, and a tested rollback. Game days beat postmortems for building muscle memory.

Contract tests at boundaries use anonymized production samples—nullable fields and unicode edge cases break synthetic fixtures. Security review documents untrusted inputs and log redaction rules in the PR description so auditors and on-call engineers inherit context without archaeology.

Performance work ties to field data on mid-tier mobile hardware, not desktop lab profiles. Slice dashboards by route, deploy version, and region before declaring victory on global averages.