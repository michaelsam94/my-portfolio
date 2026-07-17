---
title: "Automating Secret Rotation"
slug: "secrets-rotation-automation"
description: "Automate secret rotation for databases, API keys, and TLS: dual-credential windows, reload signals, and verification without downtime."
datePublished: "2025-07-02"
dateModified: "2026-07-17"
tags:
  - "Engineering"
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

## TLS certificate rotation

ACME handles automatically—monitor expiry separately. For mTLS internal certs, rotate before 50% lifetime consumed.

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

## Verification gates

After deploy, synthetic transaction must succeed before revoking old credential. Rollback keeps old version active if canary fails. Never revoke until metrics green for defined window.

Log rotation events with actor (scheduler vs human), secret ARN, and version IDs—not secret values. Prove rotation interval to auditors with CloudTrail or Vault audit devices.

Synthetic transaction after deploy must succeed before revoking old credential. Rollback keeps old version active if canary fails.

API key rotation: mark old key rotating with expires_at; accept both in middleware during overlap window documented to partners.

CloudTrail or Vault audit proves rotation interval to auditors—log version IDs, never secret values.

## Overlap sizing worked example

Postgres pool max lifetime 30 minutes; deploy wave 20 minutes — overlap TTL 90 minutes minimum before DROP ROLE. Graph `pg_stat_activity` for old role until zero for 15 continuous minutes. API keys: revoke when `rotating` key RPS hits zero for 1 hour, not on partner's promised calendar date alone.

## Overlap sizing worked example

Postgres pool max lifetime 30 minutes; deploy wave 20 minutes — overlap TTL 90 minutes minimum before DROP ROLE. Graph `pg_stat_activity` for old role until zero for 15 continuous minutes. API keys: revoke when `rotating` key RPS hits zero for 1 hour, not on partner's promised calendar date alone.

## Secrets Rotation Automation verification

Compare tier-1 route p75 RUM for seven days after release; alert on mobile-only regression before global mean moves.

## Deep dive (1)

Production secrets rotation automation needs observability, rollback, and field validation on mid-tier devices.

## Deep dive (2)

When shipping secrets rotation automation, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (3)

Security reviews for secrets rotation automation should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (4)

Load tests for secrets rotation automation use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (5)

Runbooks for secrets rotation automation link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (6)

Canary secrets rotation automation changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (7)

After incidents involving secrets rotation automation, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (8)

Production secrets rotation automation needs observability, rollback, and field validation on mid-tier devices.

## Deep dive (9)

When shipping secrets rotation automation, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (10)

Security reviews for secrets rotation automation should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (11)

Load tests for secrets rotation automation use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (12)

Runbooks for secrets rotation automation link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (13)

Canary secrets rotation automation changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (14)

After incidents involving secrets rotation automation, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (15)

Production secrets rotation automation needs observability, rollback, and field validation on mid-tier devices.

## Deep dive (16)

When shipping secrets rotation automation, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (17)

Security reviews for secrets rotation automation should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (18)

Load tests for secrets rotation automation use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (19)

Runbooks for secrets rotation automation link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (20)

Canary secrets rotation automation changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (21)

After incidents involving secrets rotation automation, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (22)

Production secrets rotation automation needs observability, rollback, and field validation on mid-tier devices.

## Deep dive (23)

When shipping secrets rotation automation, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (24)

Security reviews for secrets rotation automation should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (25)

Load tests for secrets rotation automation use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Deep dive (26)

Runbooks for secrets rotation automation link from dashboards — on-call should not search Confluence during incidents.

## Deep dive (27)

Canary secrets rotation automation changes on highest-traffic locale before global rollout; global means hide cohort regressions.

## Deep dive (28)

After incidents involving secrets rotation automation, update tests and alerts — postmortem action items belong in the repo.

## Deep dive (29)

Production secrets rotation automation needs observability, rollback, and field validation on mid-tier devices.

## Deep dive (30)

When shipping secrets rotation automation, instrument the primary user journey with correlation IDs and deploy version tags in RUM.

## Deep dive (31)

Security reviews for secrets rotation automation should map trust boundaries — what data crosses them and who verifies integrity.

## Deep dive (32)

Load tests for secrets rotation automation use production-shaped payloads; empty staging databases hide N+1 and timeout failures.

## Resources

- [AWS Secrets Manager rotation](https://docs.aws.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [HashiCorp Vault rotate root credentials](https://developer.hashicorp.com/vault/tutorials/db-credentials/database-secrets)
- [Google Cloud Secret Manager rotation](https://cloud.google.com/secret-manager/docs/creating-and-managing-secrets)
- [NIST SP 800-57 key management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

## Vault dynamic database credentials

Vault database secrets engine issues short-lived users per lease — rotation becomes issuance, not password editing. Tune lease TTL against connection pool recycle; pools outliving lease hold dead passwords until recycle.
