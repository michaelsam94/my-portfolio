---
title: "Problem Details for HTTP APIs"
slug: "rest-api-error-responses-rfc9457"
description: "Standardize API errors with RFC 9457 Problem Details: consistent JSON shape, type URIs, field-level validation, and client-friendly retry hints."
datePublished: "2025-04-09"
dateModified: "2026-07-17"
tags: ["REST", "API Design", "HTTP", "Error Handling"]
keywords: "RFC 9457, Problem Details, HTTP API errors, application/problem+json, validation errors, API error format, retry-after"
faq:
  - q: "Should every error response use application/problem+json?"
    a: "Every error response your API documents should use it for 4xx and 5xx bodies when a body is present. Success responses stay with your domain media type. Clients can branch on Content-Type and parse one predictable structure instead of guessing whether errors look like {error: ...} or {message: ...} today."
  - q: "What goes in the type field?"
    a: "The type is a URI identifying the error category, often a stable URL on your docs site that explains remediation. Use about:blank only for generic errors where no specific doc exists. Never put stack traces or internal IDs in type; keep those in extension fields gated behind debug modes."
  - q: "How do I represent validation errors on multiple fields?"
    a: "RFC 9457 defines an invalid-params extension used widely in practice: an array of objects with name and reason for each field. Keep reasons human-readable for form UIs and machine-stable with a separate code if clients localize strings themselves."
faqAnswers:
  - question: "When is rest api error responses rfc9457 the wrong tool?"
    answer: "Skip rest api error responses rfc9457 when a simpler control or library already covers the failure mode, or when the operational cost exceeds the risk reduction for your threat model."
  - question: "What should I measure after adopting rest api error responses rfc9457?"
    answer: "Track a leading signal (coverage, error class rate, or latency) and a lagging outcome (incidents, CVEs exploited, or user-visible failures) tied specifically to rest api error responses rfc9457."
  - question: "How do I roll back a bad rest api error responses rfc9457 change?"
    answer: "Keep the previous config/version behind a flag or previous artifact; verify the rollback path in staging once, then document the one-command revert for on-call."
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

## Choose stable type URIs

Each distinct failure mode gets a type URI that resolves to human documentation:

```
https://api.example.com/problems/validation-failed
https://api.example.com/problems/idempotency-conflict
https://api.example.com/problems/rate-limited
```

Avoid embedding variable data in `type`. Variable context belongs in `detail` or extensions. Teams that reuse one generic type for everything lose analytics granularity; teams that create a type per enum value create unmaintainable doc pages.

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

## OpenAPI and client generation

Register a `ProblemDetails` schema in OpenAPI 3.1 and reference it as the default error response on operations. Generated TypeScript clients then expose typed error parsing. Integration tests should assert both status and `type` URI, not substring matches on English prose that will change during copy edits.

Problem Details are user-visible. Strip SQL fragments, file paths, and authorization internals from `detail`. Use a separate `debug_id` extension enabled only for authenticated staff sessions. 401 and 403 messages should not reveal whether an email exists in the system.

Register a ProblemDetails schema in OpenAPI 3.1 and reference it as the default error response on operations. Generated TypeScript clients expose typed error parsing. Integration tests assert both status and type URI, not substring matches on English prose that changes during copy edits.

Centralize error mapping in middleware so controllers never hand-roll JSON. Map domain exceptions to problem types in one registry; log internal causes server-side while keeping detail safe for end users. Support staff correlate using instance or correlation_id returned to clients.

401 and 403 messages must not reveal whether an email exists. Problem Details are user-visible—strip SQL fragments, file paths, and authorization internals from detail. Use debug_id extension enabled only for authenticated staff sessions during incidents.

## Resources

- [RFC 9457: Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html)
- [IANA application/problem+json](https://www.iana.org/assignments/media-types/application/problem+json)
- [OpenAPI 3.1 Response Objects](https://spec.openapis.org/oas/v3.1.0#response-object)
- [HTTP Status Codes (IANA registry)](https://www.iana.org/assignments/http-status-codes/http-status-codes.xhtml)
- [Zalando RESTful API Guidelines: errors](https://opensource.zalando.com/restful-api-guidelines/#176)

## Failure modes specific to rest api error responses rfc9457


Operating rest api error responses rfc9457 well means tying design choices to measurable outcomes and explicit owners. Ambiguous ownership is how pages rot.

For rest api error responses rfc9457:
- Write the SLO and the user journey it protects
- Automate the boring verification; reserve humans for judgment calls
- Prefer progressive delivery with fast rollback over big-bang cuts
- Keep runbooks next to the code that can break

Revisit the design when the metric that justified rest api error responses rfc9457 stops moving — sunsetting is a feature.



| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |


## Metrics and alarms for rest api error responses rfc9457

Reviewers should challenge assumptions encoded in rest api error responses rfc9457: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for rest api error responses rfc9457: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for rest api error responses rfc9457: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for rest api error responses rfc9457: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Cross-team contracts for rest api error responses rfc9457

Roll out rest api error responses rfc9457 behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for rest api error responses rfc9457

Detail 1 (174): for rest api error responses rfc9457, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for rest api error responses rfc9457 becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break rest api error responses rfc9457, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about rest api error responses rfc9457: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.

## Developer experience when changing rest api error responses rfc9457

Detail 2 (403): for rest api error responses rfc9457, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When developer experience when changing rest api error responses rfc9457 becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break rest api error responses rfc9457, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about rest api error responses rfc9457: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.
