---
title: "Secrets Management with Vault"
slug: "secrets-management-vault"
description: "Centralize secrets with HashiCorp Vault: dynamic credentials, policies, Kubernetes auth, and patterns that beat .env files."
datePublished: "2025-06-28"
dateModified: "2025-06-28"
tags: ["Security", "Vault", "DevOps", "Secrets"]
keywords: "HashiCorp Vault secrets, dynamic database credentials, Vault Kubernetes auth, secret management, Vault policies, lease revocation"
faq:
  - q: "When should I use Vault instead of cloud secret managers?"
    a: "Vault fits multi-cloud, on-prem hybrid, and dynamic secret generation (database users with TTL) across uniform API. Cloud-native teams often use AWS Secrets Manager or GCP Secret Manager with less ops overhead. Vault wins when you need one abstraction spanning Kubernetes, VMs, and CI with detailed policy-as-code."
  - q: "What are dynamic secrets?"
    a: "Vault generates short-lived credentials on demand—Postgres user valid 1 hour, then auto-revoked. Applications request creds at startup and refresh before lease expiry. Compromised credentials self-destruct instead of living until someone rotates a static password in a spreadsheet."
  - q: "How do pods authenticate to Vault?"
    a: "Kubernetes auth method maps service account JWT to Vault role and policy. Pod mounts projected SA token, exchanges for Vault token, reads secret path. No long-lived Vault root token in cluster—bootstrap with auto-unseal (KMS) and break-glass procedures only."
---

Forty microservices each mount a Kubernetes Secret copied from last year's onboarding doc. Rotation means editing YAML in forty repos and hoping nobody cached the old DB password in a crash dump. HashiCorp Vault stores secrets centrally, audits every read, and can mint database credentials that expire in an hour. The operational cost is real—unseal, HA, backups—but static secrets in git is technical debt with compound interest.


## Core concepts

- **Secrets engine:** KV (static), database (dynamic), PKI, AWS IAM
- **Policy:** path-based ACL (`secret/data/prod/api` read)
- **Auth method:** Kubernetes, AppRole, OIDC, AWS IAM
- **Lease:** TTL after which secret revokes automatically

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Static secrets in KV v2

```bash
vault kv put secret/prod/payment stripe_key=$STRIPE_KEY
vault kv get -field=stripe_key secret/prod/payment
```

Versioned; rollback supported. Still static—rotate via CI pushing new version and signaling apps to reload.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Kubernetes auth

```yaml
# Pod annotation for Vault Agent Injector
vault.hashicorp.com/agent-inject: "true"
vault.hashicorp.com/role: "api-service"
vault.hashicorp.com/agent-inject-secret-config: "secret/data/prod/api"
```

Sidecar renders file or env vars; app unchanged. Map `ServiceAccount` → Vault role with minimal policy.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Unseal and HA

Production uses auto-unseal via cloud KMS. Shamir shards for break-glass only. Monitor seal status; sealed Vault denies all reads—page immediately.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Enable audit device to immutable storage. Every secret read ties to identity—compliance and incident forensics.

Unseal monitoring pages immediately—sealed Vault denies all reads. Auto-unseal via KMS for production; Shamir shards break-glass only.

Policy least privilege per service account. Deny by default. Audit device to immutable storage for every secret read during incidents.

Kubernetes auth maps service account JWT to role—no root token in cluster. Vault Agent Injector sidecar pattern keeps apps unchanged while credentials rotate.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.

## Resources

- [HashiCorp Vault documentation](https://developer.hashicorp.com/vault/docs)
- [Vault Kubernetes auth method](https://developer.hashicorp.com/vault/docs/auth/kubernetes)
- [Vault database secrets engine](https://developer.hashicorp.com/vault/docs/secrets/databases)
- [Vault Agent Injector](https://developer.hashicorp.com/vault/docs/platform/k8s/injector)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
