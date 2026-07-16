---
title: "Handling GDPR Data Subject Requests"
slug: "gdpr-data-subject-requests"
description: "DSAR workflows for access, deletion, and portability under GDPR. Identity verification, SLAs, audit logs, and engineering hooks that legal can trust."
datePublished: "2025-04-19"
dateModified: "2025-04-19"
tags: ["Security", "Compliance", "GDPR", "Privacy"]
keywords: "GDPR data subject request, DSAR process, right to erasure, data portability GDPR, privacy compliance engineering"
faq:
  - q: "How long do we have to respond to a GDPR DSAR?"
    a: "Generally one month from verification, extendable by two further months for complex requests with notice. Internal SLA should be shorter—engineering needs lead time before legal deadline."
  - q: "Must we delete all user data on erasure request?"
    a: "Not always. Exceptions include legal obligation to retain, exercise of legal claims, and archiving in public interest. Legal determines scope; engineering executes deletion or anonymization per data map."
  - q: "What belongs in a data export for portability?"
    a: "Personal data provided by the user and generated through use, in machine-readable format (JSON/CSV). Not required to include proprietary derived analytics or data about other users."
---

Legal forwarded a deletion request at 4 PM Friday—verified identity, ticket number, user ID. Engineering had no runbook. We grep'd databases manually and missed Redis session keys. GDPR data subject requests (DSARs) are recurring production workflows, not one-off favors to compliance.

GDPR grants rights including access (Article 15), rectification (16), erasure (17), and portability (20). Engineering implements the systems; legal defines scope and verification.

## Request intake and verification

Never act on anonymous email alone. Standard flow:

1. User submits form or emails privacy@company.com
2. Identity verification (login re-auth, ID check for high-risk data)
3. Ticket in privacy queue with unique reference
4. Legal/compliance assigns type: access, delete, restrict, portability

Automate ticket creation from authenticated in-app "Download my data" to reduce fraudulent email requests.

## Data inventory prerequisite

You cannot delete what you have not mapped. Maintain record of processing:

| System | Data categories | Retention | Erasure method |
|--------|-----------------|----------|----------------|
| Postgres users | email, profile | account life | hard delete row |
| S3 uploads | files | 90d after delete | lifecycle + purge |
| Analytics | pseudonymous events | 13 months | anonymize user_id |
| Backups | snapshots | 30d rolling | exclude or re-purge |

Update when new services ship—privacy review in design doc template.

## Access and portability export

```typescript
async function exportUserData(userId: string): Promise<UserExportBundle> {
  const [profile, orders, preferences] = await Promise.all([
    db.users.findById(userId),
    orderService.listForUser(userId),
    prefsStore.get(userId),
  ]);

  return {
    exportedAt: new Date().toISOString(),
    profile: redactInternalFields(profile),
    orders,
    preferences,
  };
}
```

Deliver JSON or ZIP via secure download link with expiry. Log export event in audit table.

Exclude other users' PII and trade secrets from model outputs.

## Erasure workflow

```typescript
async function eraseUser(userId: string, ticketId: string) {
  await auditLog.record({ action: 'erasure_started', userId, ticketId });

  await db.transaction(async (tx) => {
    await tx.orders.anonymize(userId); // keep order totals, remove PII
    await tx.users.delete(userId);
  });

  await cache.delete(`session:${userId}`);
  await searchIndex.removeUser(userId);
  await marketingProvider.suppressEmail(userId);

  await auditLog.record({ action: 'erasure_completed', userId, ticketId });
}
```

Order **anonymize vs delete** per legal—financial records may require retained line items without identity.

## Backups and eventual consistency

Document that backup tapes are overwritten on rotation—not individually edited. GDPR allows reasonable backup retention if data not actively processed; restore-test procedures must not resurrect erased users into production without re-purge job.

Run nightly job reconciling erasure queue against analytics warehouses with delayed ETL.

## Audit and accountability

Store immutable audit logs: who approved, what systems touched, timestamps. Regulators ask for demonstration of process, not just policy PDF.

Restrict audit access—contains PII of requesters.

## Engineering APIs for privacy team

Internal admin tool or scripts:

- `POST /internal/privacy/export { userId }`
- `POST /internal/privacy/erase { userId, ticketId }`
- Read-only status per subsystem

Role-based access with break-glass logging.

## SLAs and automation

Target: acknowledge in 72 hours, complete within 25 days leaving buffer before legal 30-day limit. Automate export generation; manual review only for edge cases.

## Identity verification tiers

Low-risk export: re-authenticated session sufficient. High-risk (full PII dump): ID document verification manual step—engineering waits for legal **verified** flag on ticket.

## Partial erasure

User deletes account but legal requires invoice retention—anonymize PII fields while keeping monetary amounts:

```sql
UPDATE orders SET customer_email = 'deleted-' || id || '@redacted.local' WHERE user_id = $1;
```

Document in ROPA (record of processing activities).

## Cross-border transfers

Export to user in EEA—host download in EU region bucket; avoid transferring export through US logging pipeline without SCCs.

## Metrics

Track DSAR volume, mean time to complete, error rate per subsystem—ops review quarterly.


## Children's data

COPPA/GDPR-Kids may require parental consent flows—DSAR for minor accounts routes through verified guardian contact; engineering gates export/delete until legal flag set.

## Third-party processors

DSAR deletion must propagate to Stripe, SendGrid, analytics—maintain subprocessor list with API delete-user support documented. Ticket tracks each vendor completion checkbox.

## SLA dashboards

Legal ops dashboard: open DSAR count, age histogram, blocked on verification count—engineering webhook updates status when export.zip ready for upload to secure portal.

## Post-erasure confirmation

Email user confirmation of deletion completion—template must not include deleted PII in body; use ticket reference only.

## Automation limits

Fully automated erasure without human verification only for low-risk self-service account settings—not for accounts with financial disputes open requiring legal hold flag check in workflow engine.

## Rollout guidance

DSAR automation phase one export manual legal trigger only—automate after three manual runs document exceptions encountered engineering encodes rules not guessing edge cases first automation PR.

## Team practices

Shipping Gdpr Data Subject Requests in production taught our team that documentation beats hero demos. We wrote runbooks covering failure modes, on-call steps, and rollback triggers before the second release, not after the first outage.

When reviewing PRs touching Gdpr Data Subject Requests, we ask for measurable outcomes: latency, crash rate, or support ticket volume—not subjective feels faster. If metrics are unavailable, the PR includes a DevTools trace or load test snippet proving the change.

Onboarding engineers paste a checklist into their first Gdpr Data Subject Requests PR description: environment setup verified, tests added or updated, accessibility spot-checked, and release notes drafted for user-visible changes.

We keep a living FAQ in the repo wiki for Gdpr Data Subject Requests questions repeated in Slack more than twice. FAQ entries link to source files and Slack threads, reducing tribal knowledge and repeated explanations in code review.

## Resources

- [GDPR full text (EUR-Lex)](https://gdpr-info.eu/)
- [ICO guide to right of access](https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/individual-rights/right-of-access/)
- [Article 17 Right to erasure](https://gdpr-info.eu/art-17-gdpr/)
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework)
- [Google GDPR resource center](https://privacy.google.com/businesses/compliance/)
