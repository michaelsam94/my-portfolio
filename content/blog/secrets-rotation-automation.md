---
title: "Automating Secret Rotation"
slug: "secrets-rotation-automation"
description: "Automate secret rotation for databases, API keys, and TLS: dual-credential windows, reload signals, and verification without downtime."
datePublished: "2025-07-02"
dateModified: "2025-07-02"
tags: ["Security", "Secrets", "DevOps", "Automation"]
keywords: "secret rotation automation, credential rotation, dual credential window, database password rotation, API key rotation schedule, zero downtime rotation"
faq:
  - q: "How long should two valid credentials overlap during rotation?"
    a: "Overlap until all running instances pick up the new secret and all sessions using the old credential expire. For hourly-rotated DB users, overlap might be 2 hours. For API keys, keep old key valid 24–72 hours after new key deploys so edge caches and partner configs update. Document overlap in runbooks to prevent premature revocation."
  - q: "Who initiates rotation—scheduler or leak?"
    a: "Both. Scheduled rotation limits blast radius of undetected leaks and satisfies compliance (PCI, SOC2). Emergency rotation triggers on Gitleaks findings, employee offboarding, or vendor breach notification. Emergency path must be automated too—manual panic rotation at 2 AM skips verification steps."
  - q: "How do applications pick up new secrets without restart?"
    a: "Sidecars (Vault Agent) rewrite files and send SIGHUP; Kubernetes rolling updates mount new Secret version; apps poll secret manager with version check. Design for reload on file change or subscribe to rotation events. Long-lived connection pools may need staggered drain after credential swap."
---

The database password rotated quarterly—manually, via ticket, with a typo that locked out production for twelve minutes. Automated rotation turns credentials into short-lived resources: generate new, deploy, verify, revoke old, repeat on schedule. The hard part is not generating random strings but keeping zero-downtime while connection pools, CI pipelines, and partner webhooks still hold yesterday's key.


## Rotation architecture

```
Scheduler → Secret Manager → New version N+1
                ↓
    Deploy/canary → Health checks → Revoke version N
```

Emit events (`secret.rotated`) for subscribers to reload.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Dual-credential pattern

Database user `app_v3` active while apps still hold `app_v2` connection strings:

1. Create `app_v3` with identical grants
2. Update Vault/Secrets Manager primary
3. Rolling restart or SIGHUP reload apps
4. Monitor error rate and connection counts on `app_v2`
5. Drop `app_v2` after overlap TTL

```sql
-- Verify no connections on old role
SELECT usename, count(*) FROM pg_stat_activity
WHERE usename = 'app_v2' GROUP BY usename;
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## API key rotation

Issue `sk_live_NEW`, document in developer portal, email integrators 30 days ahead for scheduled rotation. Accept both keys in auth middleware keyed by key ID:

```python
def authenticate(header: str) -> Principal:
    key_hash = hmac_sha256(header)
    record = db.lookup_key_hash(key_hash)
    if record and record.status in ("active", "rotating"):
        return record.principal
    raise AuthError()
```

Mark old key `rotating` with `expires_at`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## TLS certificate rotation

ACME handles automatically—monitor expiry separately. For mTLS internal certs, rotate before 50% lifetime consumed.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## AWS Secrets Manager example

```python
import boto3

client = boto3.client("secretsmanager")
response = client.rotate_secret(
    SecretId="prod/db/app",
    RotationLambdaARN="arn:aws:lambda:...:function:RotateSecret",
    RotationRules={"AutomaticallyAfterDays": 30},
)
```

Lambda implements `createSecret`, `setSecret`, `testSecret`, `finishSecret` steps.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Verification gates

After deploy, synthetic transaction must succeed before revoking old credential. Rollback keeps old version active if canary fails. Never revoke until metrics green for defined window.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Log rotation events with actor (scheduler vs human), secret ARN, and version IDs—not secret values. Prove rotation interval to auditors with CloudTrail or Vault audit devices.

Synthetic transaction after deploy must succeed before revoking old credential. Rollback keeps old version active if canary fails.

API key rotation: mark old key rotating with expires_at; accept both in middleware during overlap window documented to partners.

CloudTrail or Vault audit proves rotation interval to auditors—log version IDs, never secret values.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.

## Resources

- [AWS Secrets Manager rotation](https://docs.aws.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [HashiCorp Vault rotate root credentials](https://developer.hashicorp.com/vault/tutorials/db-credentials/database-secrets)
- [Google Cloud Secret Manager rotation](https://cloud.google.com/secret-manager/docs/creating-and-managing-secrets)
- [NIST SP 800-57 key management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
