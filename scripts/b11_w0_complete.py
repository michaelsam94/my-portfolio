#!/usr/bin/env python3
"""Atomically write the 9 failing b11_w0 blog posts with unique deep-dive content."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "content" / "blog"
BANNED = [
    "Validate this in staging",
    "Additional production considerations",
    "Measuring success in production",
    "We keep a living FAQ",
    "Document the decision, owner",
    "production pattern for frontend",
    "Architecture and boundaries",
    "The gap between reading about",
]

POSTS = {}

POSTS["secrets-rotation-automation"] = '''---
title: "Automating Secret Rotation"
slug: "secrets-rotation-automation"
description: "Automate secret rotation for databases, API keys, and TLS: dual-credential windows, reload signals, and verification without downtime."
datePublished: "2025-07-02"
dateModified: "2026-07-17"
tags: ["Security", "Secrets", "DevOps", "Automation"]
keywords: "secret rotation automation, credential rotation, dual credential window, database password rotation, API key rotation schedule, zero downtime rotation"
faq:
  - q: "How long should two valid credentials overlap during rotation?"
    a: "Overlap until every running instance has loaded the new secret and every session tied to the old credential has expired. For hourly-rotated database users, two hours of overlap is typical. For partner API keys, keep the old key valid 24–72 hours after the new key ships so integrators and edge caches can update without midnight pages."
  - q: "Who initiates rotation—scheduler or leak?"
    a: "Both paths must exist. Scheduled rotation limits blast radius of undetected leaks and satisfies PCI and SOC2 evidence requirements. Emergency rotation triggers on scanner findings, employee offboarding, or vendor breach notifications. If emergency rotation requires manual SSH at 2 AM, people skip verification steps and revoke too early."
  - q: "How do applications pick up new secrets without restart?"
    a: "Vault Agent sidecars rewrite files and send SIGHUP; Kubernetes rolling updates mount new Secret versions; some apps poll the secret manager for version changes. Connection pools holding stale passwords need staggered drain after credential swap—design reload hooks before you automate the scheduler."
---

The database password rotated quarterly through a ticket queue. Someone pasted the new value into the wrong environment variable, and production connection pools rejected auth for twelve minutes while on-call grep'd deployment manifests. That incident convinced leadership that rotation should be boring infrastructure—not a calendar reminder with human copy-paste in the loop.

Automated rotation treats credentials as short-lived resources: generate, deploy, verify, revoke, repeat. The hard part is not random string generation. It is keeping traffic healthy while connection pools, CI pipelines, partner webhooks, and cron jobs still hold yesterday's key.

## Why manual rotation fails at scale

Manual rotation optimizes for the happy path documented in a wiki page. Production has long-lived pods that never restarted after deploy, staging databases that share credential names with production, and third-party SaaS dashboards where only one engineer knows how to update the webhook secret. Each manual cycle adds drift between what the secret manager stores and what actually authenticates.

Compliance auditors ask for evidence: rotation interval, who triggered each event, and proof old credentials were revoked. Spreadsheet tracking does not survive acquisitions or team churn. Automated pipelines emit structured audit events with secret ARN and version IDs—never the secret value itself.

## Rotation pipeline overview

```
Scheduler / Event ──▶ Secret Manager (version N+1)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         App reload   CI sync    Partner notify
              │            │            │
              └────────────┼────────────┘
                           ▼
              Synthetic verify ──▶ Revoke version N
```

Publish `secret.rotated` events on a message bus so subscribers reload without polling. Database rotation Lambdas, Kubernetes operators, and custom sidecars should all subscribe to the same contract.

## Dual-credential window for databases

The safest database pattern keeps two valid users during overlap:

1. Create `app_v3` with identical grants to `app_v2`
2. Write `app_v3` as the primary in Vault or Secrets Manager
3. Rolling restart applications or send SIGHUP to reload connection strings
4. Monitor `pg_stat_activity` (or equivalent) for connections still using `app_v2`
5. Drop `app_v2` only after overlap TTL and zero connections

```sql
SELECT usename, count(*) AS sessions
FROM pg_stat_activity
WHERE usename IN ('app_v2', 'app_v3')
GROUP BY usename;
```

RDS and Cloud SQL managed rotation often create a shadow user, swap the secret pointer, then delete the old user. Understand your provider's steps before trusting the default Lambda—custom extensions and read replicas sometimes need extra grants.

Connection poolers like PgBouncer cache credentials at pool creation. After rotation, set `pool_mode` transactions appropriately and recycle pools or use `DISCARD ALL` on borrowed connections. A green health check on one pod does not prove every pooler shard picked up the new password.

## API key rotation with partner lead time

Public API keys cannot flip instantly. Issue `sk_live_NEW`, register it in your auth middleware, deploy code that accepts both keys during overlap, then mark the old key `rotating` with `expires_at`:

```python
def authenticate(raw_key: str) -> Principal:
    digest = hmac_sha256(raw_key)
    record = db.lookup_key_hash(digest)
    if record and record.status in ("active", "rotating"):
        if record.status == "rotating" and record.expires_at < utcnow():
            raise AuthError("key_expired")
        return record.principal
    raise AuthError("invalid_key")
```

Email integrators thirty days ahead for scheduled rotation. Emergency rotation compresses that window—maintain a contact list and status page template. Log which key ID authenticated each request during overlap so you know when old traffic dropped to zero.

## TLS and mTLS certificates

Public TLS is largely solved by ACME clients. Monitor expiry independently—automation fails when DNS validation breaks or rate limits hit during incident-driven reissues. For internal mTLS, rotate client certificates before fifty percent of lifetime consumed; short-lived certs reduce the value of stolen material.

Store private keys in HSM or cloud KMS where policy allows. Rotation scripts that write PEM files to `/tmp` recreate the leakage path you are trying to eliminate.

## AWS Secrets Manager rotation hooks

AWS implements rotation as a four-step Lambda contract:

```python
# Conceptual steps inside rotation Lambda
def handler(event, context):
    step = event["Step"]
    if step == "createSecret":
        generate_new_password()
    elif step == "setSecret":
        apply_to_database(new_password)
    elif step == "testSecret":
        verify_connection(new_password)
    elif step == "finishSecret":
        mark_current_version()
```

`testSecret` must run a real query—not `SELECT 1` against a read replica that still accepts the old password on a lagging node. `finishSecret` moves the `AWSCURRENT` label; premature finish during a failed canary locks you out.

## Kubernetes secret mounting

Kubernetes Secrets mounted as volumes update files on disk when the Secret object changes—but applications must watch inotify or poll. Environment variable injection from Secrets does not update without pod restart. Prefer volume mounts plus reload hooks over env vars for rotatable credentials.

External Secrets Operator syncs cloud secret versions into cluster Secrets on interval. Tune sync frequency against API rate limits and blast radius requirements.

## Verification gates before revocation

Never revoke the old credential because the scheduler finished. Require:

- Synthetic transaction success against production-like path
- Error rate flat versus baseline for fifteen minutes minimum
- Zero connections or requests authenticated with old version
- Explicit rollback path if canary fails—keep old version `AWSPENDING` until promoted

Rollback means keeping version N active and deleting N+1 from the manager, not redeploying application code. Runbooks should name the exact CLI commands.

## Emergency rotation playbook

When Gitleaks fires or a laptop is stolen:

1. Identify affected secret scope—one repo token vs organization root
2. Generate and deploy new credential through automation, not manual paste
3. Revoke old credential at provider immediately after deploy starts
4. Scan audit logs for use of old credential after known compromise time
5. Notify partners if their integrations break

Panic manual rotation skips step four and leaves attackers with a longer window.

## Observability and audit evidence

Log rotation events with: trigger (scheduled vs emergency), actor service account, secret identifier, old and new version IDs, duration, and verification result. Ship logs to immutable storage—CloudTrail, Vault audit devices, or SIEM with tamper detection.

Dashboards should show time-since-last-successful-rotation per secret class. Alert when rotation jobs fail twice consecutively or overlap windows exceed policy max.

## Organizational habits that stick

Rotation automation succeeds when application teams own reload behavior. Platform provides the scheduler and secret store; product teams implement SIGHUP handlers and pool recycling. Quarterly game days rotate a non-production secret end-to-end with engineers who did not write the original automation.

Treat overlap TTL as a documented contract in runbooks, not tribal knowledge. The next on-call should not guess whether `app_v2` was dropped early during a previous incident.

## Resources

- [AWS Secrets Manager rotation](https://docs.aws.amazon.com/secretsmanager/latest/userguide/rotating-secrets.html)
- [HashiCorp Vault database secrets](https://developer.hashicorp.com/vault/tutorials/db-credentials/database-secrets)
- [Google Cloud Secret Manager rotation](https://cloud.google.com/secret-manager/docs/creating-and-managing-secrets)
- [NIST SP 800-57 key management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
'''

# Additional posts written to separate files loaded below
_bodies: dict = {}
exec(open(Path(__file__).parent / "b11_w0_complete_bodies.py").read(), {"POSTS": _bodies})
POSTS.update(_bodies)

def verify(slug: str, text: str) -> tuple[bool, str]:
    body = text.split("---", 2)[2].strip()
    words = len(re.findall(r"\b[\w'-]+\b", body))
    fm = text.split("---", 2)[1]
    faq = len(re.findall(r"^\s*-\s+q:", fm, re.M))
    bad = [b for b in BANNED if b in text]
    dm = re.search(r'dateModified: "([^"]+)"', fm)
    dm_val = dm.group(1) if dm else "MISSING"
    ok = words >= 1200 and faq == 3 and not bad and dm_val == "2026-07-17"
    return ok, f"{words}w faq={faq} dm={dm_val} bad={bad}"

def main():
    all_ok = True
    for slug, content in POSTS.items():
        path = ROOT / f"{slug}.md"
        ok, info = verify(slug, content)
        if not ok:
            print(f"WARN pre-write {slug}: {info}")
            all_ok = False
        path.write_text(content)
        ok2, info2 = verify(slug, path.read_text())
        status = "OK" if ok2 else "FAIL"
        print(f"{status} {slug}: {info2}")
        if not ok2:
            all_ok = False
    return 0 if all_ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
