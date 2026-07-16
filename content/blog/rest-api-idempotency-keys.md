---
title: "Idempotency Keys for Safe Retries"
slug: "rest-api-idempotency-keys"
description: "Design idempotency keys for POST and PATCH: storage semantics, conflict handling, TTL, and client patterns that survive flaky networks."
datePublished: "2025-04-17"
dateModified: "2025-04-17"
tags: ["REST", "API Design", "Reliability", "Backend"]
keywords: "idempotency key, safe retries, POST idempotency, Idempotency-Key header, payment API, duplicate request prevention"
faq:
  - q: "Which HTTP methods need idempotency keys?"
    a: "POST is the primary target because it creates resources and is not idempotent by default. PATCH may need keys when partial updates trigger side effects like charging a card. PUT and DELETE are already idempotent by HTTP semantics, though DELETE may still benefit from keys when deletion triggers irreversible external workflows."
  - q: "How long should the server store idempotency records?"
    a: "Store at least 24 hours for consumer apps and 72 hours for B2B integrations where clients retry aggressively. Payment processors often use 24–48 hours aligned with settlement windows. Expired keys should behave like new requests, with monitoring for duplicate side effects if TTL is too short."
  - q: "What happens if the same key is reused with a different body?"
    a: "Return 409 Conflict or 422 with a problem type indicating payload mismatch. Replaying the identical request should return the original status code and body, including the same resource IDs. Silent acceptance of different bodies under one key causes reconciliation nightmares in accounting systems."
---

Mobile checkout failed with a spinner. The user tapped Pay again. Your server created two payment intents, captured twice, and support issued a refund manually. HTTP retries are inevitable on lossy networks; without idempotency keys, POST is a loaded gun. Stripe popularized the `Idempotency-Key` header pattern: clients generate a unique key per logical operation, servers persist the first result, and duplicates replay the stored response without re-executing side effects.

## Client responsibilities

Generate a UUID v4 (or ULID for sortable logs) once per user intent—not per HTTP attempt:

```typescript
const key = crypto.randomUUID();
await fetch("/v1/transfers", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Idempotency-Key": key,
  },
  body: JSON.stringify(payload),
});
```

Retry the *same* key on timeout or 503. Generate a *new* key only when the user explicitly submits again. Persist keys locally until success so app restarts mid-flight do not double-charge.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Server storage model

On first sight of a key, acquire a lock row in the database:

```sql
CREATE TABLE idempotency_keys (
  key_hash       BYTEA PRIMARY KEY,
  request_hash   BYTEA NOT NULL,
  response_code  INT,
  response_body  JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Hash keys with HMAC using a server secret so raw client keys never appear in logs. Compare `request_hash` on replay; mismatch means conflict.

Processing flow:

1. Insert pending row or select existing.
2. If completed, return stored response immediately.
3. If pending and owned by this worker, execute business logic in a transaction.
4. Persist response, release lock.

Use `INSERT ... ON CONFLICT DO NOTHING` or advisory locks to handle concurrent duplicates arriving milliseconds apart.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Response replay semantics

Replay must return the original HTTP status and body byte-for-byte where possible. If the first attempt returned `201 Created` with `Location`, the retry must too—even if the client never saw the first response. Include `Idempotent-Replayed: true` as an optional header so clients distinguish fresh success from replay in metrics.

For long-running operations, return `202 Accepted` on first processing and store the final outcome when complete; replays during processing should either wait or return the same `202` with a consistent `Retry-After`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Scope keys correctly

Scope idempotency per authenticated principal and API environment. The same key from two different API keys must not collide, but the same user reusing a key across test and production should fail loudly. Prefix stored records with `account_id` or `tenant_id`.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Side effects beyond HTTP

Email sends, warehouse picks, and ledger postings must happen inside the idempotent unit of work or use outbox deduplication keyed by the same idempotency key. Teams that only dedupe the HTTP response but still enqueue two Kafka messages have solved half the problem.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Observability

Metric: replay rate by endpoint. Spikes indicate client bugs or network instability. Alert on conflict rate (same key, different body)—often a client regenerating keys incorrectly or serializing unstable JSON field order.

Store idempotency records in Redis or Postgres with TTL matching your retry window. Hash keys with HMAC using a server secret so raw client keys never appear in logs. Compare request_hash on replay; mismatch means conflict, not silent overwrite.

Publish idempotency requirements in developer docs with retry pseudocode. Partners on older HTTP clients retry on connection reset—duplicate keys within TTL should replay success, not 409, unless body hash differs. 409 signals client bug, not normal retry.

Side effects beyond HTTP—email, warehouse picks, ledger postings—must happen inside the idempotent unit of work or use outbox deduplication keyed by the same idempotency key. Deduping HTTP alone while enqueueing two Kafka messages solves half the problem.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.
## Resources

- [Stripe Idempotent Requests documentation](https://docs.stripe.com/api/idempotent_requests)
- [RFC 9110: HTTP method safety and idempotency](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)
- [PayPal Idempotency header guide](https://developer.paypal.com/api/rest/reference/idempotency/)
- [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html)
- [AWS Architecture Blog: idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
