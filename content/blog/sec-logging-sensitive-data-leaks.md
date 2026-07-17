---
title: "Preventing Sensitive Data in Logs"
slug: "sec-logging-sensitive-data-leaks"
description: "Keep secrets and PII out of logs: structured logging patterns, redaction filters, sampling policies, and compliance-aware retention."
datePublished: "2025-05-31"
dateModified: "2026-07-17"
tags: ["Security", "Logging", "Privacy", "Observability"]
keywords: "sensitive data logging, PII in logs, log redaction, secret leakage, GDPR logging, structured logging security, PCI log data"
faq:
  - q: "What counts as sensitive in application logs?"
    a: "Passwords, API keys, session tokens, refresh tokens, full credit card numbers, government IDs, health records, and full request bodies on auth endpoints. Also quasi-identifiers combined—email plus IP may be PII under GDPR. When uncertain, treat as sensitive and redact; legal can narrow later easier than scrubbing leaked production logs."
  - q: "Should I log request bodies for debugging?"
    a: "Avoid logging bodies on authentication, payment, and profile routes entirely. Elsewhere, log hashed identifiers and field names only, or sample at low rate in non-production. If body logging is required temporarily, use feature flags with automatic expiry and restrict access via IAM."
  - q: "How do I redact without losing debuggability?"
    a: "Use structured fields with typed serializers that mask by default—email becomes j***@example.com, card becomes ****4242. Include correlation IDs so support traces requests without seeing secrets. Separate security audit logs (append-only, minimal fields) from verbose debug streams."
---
Incident response pulled CloudWatch and found `Authorization: Bearer eyJ...` on every line—session replay waiting to happen. Developers `console.log(req.body)` during checkout debugging and forgot to remove it. Log aggregators index everything for years; deletion is expensive and may violate retention policies requiring immutability. Sensitive data in logs is a breach that keeps paying rent. Design logging so secrets and PII never enter the pipeline, rather than scrambling to grep-delete after shipping.

## Default-deny field logging

```typescript
const SENSITIVE_KEYS = new Set([
  "password", "token", "authorization", "ssn", "creditCard",
]);

function sanitize(obj: unknown): unknown {
  if (obj && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj).map(([k, v]) =>
        SENSITIVE_KEYS.has(k.toLowerCase())
          ? [k, "[REDACTED]"]
          : [k, sanitize(v)]
      )
    );
  }
  return obj;
}
```

Apply in logger middleware before emit. Framework hooks (Pino redact paths, log4j RewritePolicy) centralize policy.

## Never log headers wholesale

```typescript
logger.info({ requestId, method, path, status }, "request completed");
```

If headers matter, allowlist: `user-agent`, `content-type`, `x-request-id`. Strip `cookie`, `authorization`, `set-cookie` always.

## Token and secret patterns

Scan log lines in CI tests for JWT regex (`eyJ[A-Za-z0-9_-]+\.`), AWS keys (`AKIA`), and private key PEM headers. Gitleaks-style rules on CI log artifacts from integration tests catch regressions.

## PCI and payment flows

PCI DSS forbids storing full track data, CVV, or PIN in logs. Log gateway transaction IDs and last-four only. Point-in-time audits grep Kibana for PAN regex—automate monthly.

## PII minimization for GDPR

Log user IDs (opaque UUIDs) instead of emails in application logs. Map ID to email via admin tool with separate access log. Honor erasure: if user deletes account, structured logs may retain ID as necessary for fraud prevention—document legal basis; never retain deleted user's email in debug strings.

## Audit vs debug separation

| Stream | Contents | Retention | Access |
|--------|----------|-----------|--------|
| Audit | who did what, when | 7 years | Security/compliance |
| App info | metrics, errors | 30 days | Engineering |
| Debug | verbose traces | 24 hours | On-call only |

Ship debug logs to separate index with stricter IAM.

Exception messages from SQL drivers may embed query parameters. Wrap database errors for user display; log internal cause in restricted field. Sentry scrubbing rules mask `password` before upload.

Separate audit stream from debug with stricter IAM and retention. Debug logs rotate quickly; audit logs may require years immutability for compliance.

Sentry and similar services need scrubbing rules before upload. Exception messages from SQL drivers may embed parameters—wrap for user display.

Monthly automated grep for PAN regex and JWT patterns in log indices catches regressions when new endpoints ship without redaction middleware.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## Rollout and ownership

Teams shipping this capability should wire observability before calling the work done: metrics on the user-visible outcome the control protects, alerts linked to runbook steps, and at least one automated test covering the last incident class you care about. Slice dashboards by region and device during rollout because global averages hide bad canaries. When vendors, routes, or org structure change, revisit assumptions from launch week—they age faster than code. Document rollback commands in the runbook header so on-call does not rediscover steps during pagination. Cross-functional review after major traffic shifts keeps product, platform, and security aligned on the leading metric.

## A concrete playbook for sec logging sensitive data leaks

Security work around sec logging sensitive data leaks fails when it is treated as a checklist instead of a feedback loop. Start from a threat model: who is the adversary, what is the asset, and which control fails closed if misconfigured. For sec logging sensitive data leaks, I write the abuse cases first — credential stuffing, dependency CVE, log exfiltration, CSRF on cookie sessions — then map each to a detection signal and an owner.

### Controls that actually change outcomes

| Control | Where enforced | Failure mode |
|---------|----------------|--------------|
| Input validation | API edge | Injection / mass assignment |
| Authn | IdP + resource server | Stolen session / token |
| Authz | Policy engine | Broken object level auth |
| Secrets | Vault / KMS | Long-lived plaintext keys |

Wire these into CI where possible. A control that only lives in a wiki page will not survive the next on-call rotation.

### Incident-shaped verification

Run a tabletop: assume the primary control for sec logging sensitive data leaks failed at 02:00. Who gets paged? What is the first command? How do you revoke access or roll credentials without cascading outages? If you cannot answer in under five minutes, the design is incomplete.

### Measurement

Track mean time to remediate findings related to sec logging sensitive data leaks, false-positive rate of scanners, and number of production changes that bypass the gate. Celebrate burn-down of legacy exceptions with expiry dates — permanent exceptions are just vulnerabilities with paperwork.

### Pitfalls specific to this domain

Avoid denylist-only validation, logging secrets "temporarily," and blocking every advisory at severity informational. Prefer allowlists, structured redaction, and severity+reachability for gates. Document the dual-credential or dual-key window whenever rotation is involved so operators do not revoke early.

## Resources

- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [PCI DSS logging requirements](https://www.pcisecuritystandards.org/)
- [GDPR Article 5 data minimization](https://gdpr-info.eu/art-5-gdpr/)
- [Pino redaction documentation](https://getpino.io/#/docs/redaction)
- [OpenTelemetry semantic conventions: sensitive data](https://opentelemetry.io/docs/specs/semconv/general/recording/)