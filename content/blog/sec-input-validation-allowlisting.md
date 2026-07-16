---
title: "Input Validation and Allowlisting"
slug: "sec-input-validation-allowlisting"
description: "Validate untrusted input with allowlists: schema design, normalization, defense against injection, and validation at trust boundaries."
datePublished: "2025-05-23"
dateModified: "2025-05-23"
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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Allowlist enums and ranges

| Field type | Strategy |
|------------|----------|
| Status filter | Enum of known DB values |
| Page size | Integer 1–100 |
| Country code | ISO 3166-1 alpha-2 set |
| MIME type | Map extension → allowed MIME |

Reject unknown enum strings with problem details—do not coerce to default silently.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Normalization before validation

Unicode normalization (NFC), trim whitespace, lowercase canonical forms for emails. Apply normalization once in middleware so downstream logic sees consistent input. Log raw and normalized values separately for fraud review.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

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

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## File uploads

Validate magic bytes, not only extension. Allowlist `image/jpeg`, `image/png`, `application/pdf`. Re-encode images to strip EXIF and embedded payloads. Store outside web root; serve via signed URLs.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Rate limit validation failures

Burst of 400s from one IP may indicate scanning. Alert on validation error spikes per route—distinct from 401 brute force.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Fuzz JSON bodies with property-based tests. Include overlong strings, null bytes, surrogate pairs, and nested depth bombs. Security regression suite runs on every PR.

Fuzz JSON bodies with property-based tests. Include overlong strings, null bytes, surrogate pairs, nested depth bombs. Security regression suite runs every PR.

Rate limit validation failures—burst of 400s from one IP may indicate scanning. Alert separately from 401 brute force patterns.

Client validation improves UX; server validation is mandatory. Generate server schemas from one source and derive client types to avoid drift between TypeScript forms and API rules.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.


## Resources

- [OWASP Input Validation Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html)
- [JSON Schema specification](https://json-schema.org/)
- [Zod documentation](https://zod.dev/)
- [OWASP Mass Assignment Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Mass_Assignment_Cheat_Sheet.html)
- [CWE-20: Improper Input Validation](https://cwe.mitre.org/data/definitions/20.html)
