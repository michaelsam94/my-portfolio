---
title: "Input Validation and Allowlisting"
slug: "sec-input-validation-allowlisting"
description: "Validate untrusted input with allowlists: schema design, normalization, defense against injection, and validation at trust boundaries."
datePublished: "2025-05-23"
dateModified: "2026-07-17"
tags: ["Security", "Input Validation", "Web Security", "Backend"]
keywords: "input validation allowlist, whitelist validation, schema validation, injection prevention, trust boundary, sanitization vs validation"
faq:
  - q: "Allowlist or denylist for validation?"
    a: "Allowlists define what is permitted; everything else rejects. Denylists block known bad patterns and fail when attackers encode bypasses. Use allowlists for enums, file extensions, HTML tags, and SQL sort columns. Denylists supplement allowlists for obvious attack signatures, never as the primary control."
  - q: "Should validation happen on client and server?"
    a: "Client validation improves UX; server validation is mandatory. Attackers bypass browsers entirely. Duplicate rules only where product needs instant feedback—generate server schemas from one source (OpenAPI, Zod, pydantic) and derive client types to avoid drift."
  - q: "Where is the trust boundary?"
    a: "Validate at every boundary where data crosses trust zones: HTTP ingress, message queue consumers, webhook handlers, file uploads, and admin import tools. Internal service calls still validate when the caller could be compromised or buggy—zero trust applies to payloads, not only networks."
---
Your admin panel accepted `sort=price; DROP TABLE users--` because the filter builder concatenated strings. Blocklists of SQL keywords lost to encoding tricks. Allowlisting accepts only `price`, `created_at`, and `-name` as sort keys—everything else returns 400 before touching the query builder. Input validation is not "sanitize HTML and hope"; it is defining the finite set of shapes your program can meaningfully process and rejecting the rest at the door.

## Schema-first validation

```typescript
import { z } from "zod";

const CreateUser = z.object({
  email: z.string().email().max(254),
  role: z.enum(["member", "admin"]),
  age: z.number().int().min(13).max(120),
});

const input = CreateUser.parse(req.body);
```

Parse, do not validate piecemeal after destructuring. Unknown keys: use `.strict()` to reject mass-assignment surprises.

## Allowlist enums and ranges

| Field type | Strategy |
|------------|----------|
| Status filter | Enum of known DB values |
| Page size | Integer 1–100 |
| Country code | ISO 3166-1 alpha-2 set |
| MIME type | Map extension → allowed MIME |

Reject unknown enum strings with problem details—do not coerce to default silently.

## Normalization before validation

Unicode normalization (NFC), trim whitespace, lowercase canonical forms for emails. Apply normalization once in middleware so downstream logic sees consistent input. Log raw and normalized values separately for fraud review.

## Injection-specific boundaries

- **SQL:** parameterized queries only; allowlist column names for dynamic ORDER BY
- **Shell:** never pass user input to exec; use library APIs
- **Path:** `Path.resolve` and verify result stays under upload root
- **HTML:** allowlist tags via sanitizer (DOMPurify server-side) if rich text required

```python
ALLOWED_SORT = {"created_at", "amount", "status"}

def parse_sort(raw: str) -> tuple[str, str]:
    desc = raw.startswith("-")
    field = raw.lstrip("-")
    if field not in ALLOWED_SORT:
        raise ValidationError("invalid sort field")
    return field, "DESC" if desc else "ASC"
```

## File uploads

Validate magic bytes, not only extension. Allowlist `image/jpeg`, `image/png`, `application/pdf`. Re-encode images to strip EXIF and embedded payloads. Store outside web root; serve via signed URLs.

## Rate limit validation failures

Burst of 400s from one IP may indicate scanning. Alert on validation error spikes per route—distinct from 401 brute force.

Fuzz JSON bodies with property-based tests. Include overlong strings, null bytes, surrogate pairs, and nested depth bombs. Security regression suite runs on every PR.

Fuzz JSON bodies with property-based tests. Include overlong strings, null bytes, surrogate pairs, nested depth bombs. Security regression suite runs every PR.

Rate limit validation failures—burst of 400s from one IP may indicate scanning. Alert separately from 401 brute force patterns.

Client validation improves UX; server validation is mandatory. Generate server schemas from one source and derive client types to avoid drift between TypeScript forms and API rules.

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

## Shipping sec input validation allowlisting without regrets

Security work around sec input validation allowlisting fails when it is treated as a checklist instead of a feedback loop. Start from a threat model: who is the adversary, what is the asset, and which control fails closed if misconfigured. For sec input validation allowlisting, I write the abuse cases first — credential stuffing, dependency CVE, log exfiltration, CSRF on cookie sessions — then map each to a detection signal and an owner.

### Controls that actually change outcomes

| Severity | Response SLA | Gate |
|----------|--------------|------|
| Critical exploitable | 48h | Block deploy |
| High | 7d | Block staging promote |
| Medium | 30d | Ticket + dashboard |

Wire these into CI where possible. A control that only lives in a wiki page will not survive the next on-call rotation.

### Incident-shaped verification

Run a tabletop: assume the primary control for sec input validation allowlisting failed at 02:00. Who gets paged? What is the first command? How do you revoke access or roll credentials without cascading outages? If you cannot answer in under five minutes, the design is incomplete.

### Measurement

Track mean time to remediate findings related to sec input validation allowlisting, false-positive rate of scanners, and number of production changes that bypass the gate. Celebrate burn-down of legacy exceptions with expiry dates — permanent exceptions are just vulnerabilities with paperwork.

### Pitfalls specific to this domain

Avoid denylist-only validation, logging secrets "temporarily," and blocking every advisory at severity informational. Prefer allowlists, structured redaction, and severity+reachability for gates. Document the dual-credential or dual-key window whenever rotation is involved so operators do not revoke early.

## Resources

- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [JSON Schema specification](https://json-schema.org/)
- [Zod documentation](https://zod.dev/)
- [OWASP Mass Assignment Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [CWE-20: Improper Input Validation](https://cwe.mitre.org/data/definitions/20.html)