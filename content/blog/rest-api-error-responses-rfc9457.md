---
title: "Problem Details for HTTP APIs"
slug: "rest-api-error-responses-rfc9457"
description: "Standardize API errors with RFC 9457 Problem Details: consistent JSON shape, type URIs, field-level validation, and client-friendly retry hints."
datePublished: "2025-04-09"
dateModified: "2025-04-09"
tags: ["REST", "API Design", "HTTP", "Error Handling"]
keywords: "RFC 9457, Problem Details, HTTP API errors, application/problem+json, validation errors, API error format, retry-after"
faq:
  - q: "Should every error response use application/problem+json?"
    a: "Every error response your API documents should use it for 4xx and 5xx bodies when a body is present. Success responses stay with your domain media type. Clients can branch on Content-Type and parse one predictable structure instead of guessing whether errors look like {error: ...} or {message: ...} today."
  - q: "What goes in the type field?"
    a: "The type is a URI identifying the error category, often a stable URL on your docs site that explains remediation. Use about:blank only for generic errors where no specific doc exists. Never put stack traces or internal IDs in type; keep those in extension fields gated behind debug modes."
  - q: "How do I represent validation errors on multiple fields?"
    a: "RFC 9457 defines an invalid-params extension used widely in practice: an array of objects with name and reason for each field. Keep reasons human-readable for form UIs and machine-stable with a separate code if clients localize strings themselves."
---

Your mobile client parses error JSON with three different shapes depending on which team shipped the endpoint. Support cannot grep logs because `message`, `errorMessage`, and `detail` mean the same thing in different services. RFC 9457 (Problem Details for HTTP APIs, obsoleting RFC 7807) gives you one envelope: `type`, `title`, `status`, `detail`, and `instance`, plus registered extensions for common cases. Adopting it is less about RFC compliance and more about giving integrators a single parser and giving operators correlatable incidents.


## The canonical problem object

```json
{
  "type": "https://api.example.com/problems/insufficient-funds",
  "title": "Insufficient funds",
  "status": 402,
  "detail": "Account acct_7x cannot cover transfer of 150.00 USD.",
  "instance": "/v1/transfers/trf_91c2"
}
```

Send it with `Content-Type: application/problem+json`. The HTTP status code remains authoritative; `status` inside the body must match. `instance` identifies the specific occurrence—often the request path or a trace ID—so users quoting "I got an error on checkout" map to one log line.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Choose stable type URIs

Each distinct failure mode gets a type URI that resolves to human documentation:

```
https://api.example.com/problems/validation-failed
https://api.example.com/problems/idempotency-conflict
https://api.example.com/problems/rate-limited
```

Avoid embedding variable data in `type`. Variable context belongs in `detail` or extensions. Teams that reuse one generic type for everything lose analytics granularity; teams that create a type per enum value create unmaintainable doc pages.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Field-level validation with invalid-params

```json
{
  "type": "https://api.example.com/problems/validation-failed",
  "title": "Validation failed",
  "status": 422,
  "errors": [
    {"field": "email", "code": "format_invalid", "message": "Must be a valid email address."},
    {"field": "age", "code": "out_of_range", "message": "Must be between 13 and 120."}
  ]
}
```

The `errors` array (community convention; align with your OpenAPI components) lets forms highlight fields without string matching on `detail`. Return 422 for semantic validation failures and 400 only when the JSON is not parseable.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Retry hints and rate limits

For 429 and transient 503 responses, combine Problem Details with standard headers:

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/problem+json
Retry-After: 120

{
  "type": "https://api.example.com/problems/rate-limited",
  "title": "Rate limit exceeded",
  "status": 429,
  "detail": "Quota of 1000 requests per hour exceeded for key sk_live_abc."
}
```

Clients backed off on `Retry-After` reduce thundering herds. Document whether limits are per API key, IP, or account so SDK authors implement the right backoff strategy.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Server implementation sketch

```typescript
function problem(
  res: Response,
  status: number,
  type: string,
  title: string,
  detail: string,
  extensions?: Record<string, unknown>,
) {
  res.status(status).type("application/problem+json").json({
    type: `https://api.example.com/problems/${type}`,
    title,
    status,
    detail,
    instance: res.locals.requestPath,
    ...extensions,
  });
}
```

Centralize this helper in middleware so controllers never hand-roll error JSON. Map domain exceptions to problem types in one registry; log the internal cause server-side while keeping `detail` safe for end users.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## OpenAPI and client generation

Register a `ProblemDetails` schema in OpenAPI 3.1 and reference it as the default error response on operations. Generated TypeScript clients then expose typed error parsing. Integration tests should assert both status and `type` URI, not substring matches on English prose that will change during copy edits.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Problem Details are user-visible. Strip SQL fragments, file paths, and authorization internals from `detail`. Use a separate `debug_id` extension enabled only for authenticated staff sessions. 401 and 403 messages should not reveal whether an email exists in the system.

Register a ProblemDetails schema in OpenAPI 3.1 and reference it as the default error response on operations. Generated TypeScript clients expose typed error parsing. Integration tests assert both status and type URI, not substring matches on English prose that changes during copy edits.

Centralize error mapping in middleware so controllers never hand-roll JSON. Map domain exceptions to problem types in one registry; log internal causes server-side while keeping detail safe for end users. Support staff correlate using instance or correlation_id returned to clients.

401 and 403 messages must not reveal whether an email exists. Problem Details are user-visible—strip SQL fragments, file paths, and authorization internals from detail. Use debug_id extension enabled only for authenticated staff sessions during incidents.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Resources

- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [IANA application/problem+json](https://www.iana.org/assignments/media-types/application/problem+json)
- [OpenAPI 3.1 Response Objects](https://spec.openapis.org/oas/v3.1.0#response-object)
- [HTTP Status Codes (IANA registry)](https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml)
- [Zalando RESTful API Guidelines: errors](https://opensource.zalando.com/restful-api-guidelines/#176)
