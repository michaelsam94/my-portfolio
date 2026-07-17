---
title: "Reliable Webhook Delivery"
slug: "webhooks-reliable-delivery"
description: "How to build reliable webhook delivery: retries with backoff, idempotency keys, HMAC signing, dead-letter queues, and at-least-once guarantees."
datePublished: "2026-06-07"
dateModified: "2026-07-17"
tags:
  - "Backend"
  - "API Design"
  - "Architecture"
  - "Messaging"
keywords: "webhooks, reliable delivery, retries, idempotency webhooks, signing webhooks, dead letter, at-least-once"
faq:
  - q: "At-least-once vs exactly-once delivery?"
    a: "At-least-once is achievable with retries; exactly-once over HTTP is not — consumers must dedupe with stable event IDs."
  - q: "How long to retry failed webhooks?"
    a: "24–72 hours with exponential backoff and jitter covers most outages. Dead-letter permanently failing endpoints after max attempts."
  - q: "Should webhooks be synchronous with the transaction?"
    a: "Never block user requests on delivery — write to outbox in same DB transaction as business event; async worker delivers."
faqAnswers:
  - question: "When is webhooks reliable delivery the wrong approach?"
    answer: "When a simpler control already covers the risk, or when the operational cost exceeds the benefit for your threat and traffic model."
  - question: "What should we measure for webhooks reliable delivery?"
    answer: "Pair a leading operational signal with a lagging user or risk outcome, reviewed on a fixed cadence with a named owner."
  - question: "How do we roll back webhooks reliable delivery safely?"
    answer: "Keep the prior artifact or config warm, rehearse the revert once in staging, and document the one-command rollback for on-call."
---
Webhooks look trivial until the receiving server is down for ninety seconds and you discover your "delivery" was a single fire-and-forget POST. Reliable webhook delivery is the set of guarantees that keep that outage from silently losing events: persist every event before sending, retry with backoff when the consumer fails, give each event a stable ID so duplicates are harmless, sign the payload so it can't be forged, and dead-letter what can't be delivered instead of dropping it. Get those five right and you've built an integration partners can actually depend on.

I've been on both ends of this — building the sender and cursing the sender as a receiver — and the failures are always the same handful. The good news is they're well-understood and the fixes compose cleanly. Here's how I build a webhook system that holds up.

## Persist first, then deliver

The cardinal rule: **never attempt delivery from an in-memory event.** If your web process generates an event and immediately POSTs it, a process restart between "event happened" and "delivery succeeded" loses it forever. Instead, write the event to durable storage as part of the transaction that created it, then let a separate delivery worker read from that store and attempt delivery.

This is exactly the [event-driven outbox pattern](https://blog.michaelsam94.com/event-driven-outbox-pattern/) applied to webhooks. The business change and the "we owe this webhook" record commit atomically in the same database transaction, so there's no window where the event happened but the delivery obligation was never recorded. A delivery table looks roughly like:

```sql
CREATE TABLE webhook_deliveries (
  id            uuid PRIMARY KEY,
  endpoint_id   uuid NOT NULL,
  event_id      uuid NOT NULL,      -- stable across all retries
  payload       jsonb NOT NULL,
  status        text NOT NULL DEFAULT 'pending',  -- pending|delivered|failed
  attempts      int  NOT NULL DEFAULT 0,
  next_attempt  timestamptz NOT NULL DEFAULT now(),
  created_at    timestamptz NOT NULL DEFAULT now()
);
```

The delivery worker polls for rows where `status = 'pending' AND next_attempt <= now()`, attempts the POST, and updates the row. Because the event is durable, a worker crash just means another worker picks it up. That single design decision is the difference between "usually delivered" and "reliably delivered."

## Retries: backoff, jitter, and a ceiling

Consumers fail transiently all the time — deploys, restarts, brief overloads. The answer is retries, but naive retries make things worse. Retrying immediately hammers a struggling consumer; retrying on a fixed schedule creates thundering herds where every failed event retries in lockstep.

The correct policy is **exponential backoff with jitter and a maximum attempt count**:

```python
import random

def next_delay(attempt: int) -> float:
    base = min(60 * (2 ** attempt), 3600)   # cap growth at 1 hour
    return base * (0.5 + random.random())   # full jitter: 50%-150%

# attempt 0 -> ~60s, 1 -> ~120s, 2 -> ~240s ... capped, spread out
```

The jitter matters more than people expect: without it, a provider outage that fails 10,000 deliveries at once will retry all 10,000 at the same instant, re-creating the overload. Spreading retries across a window smooths the load on both sides. I typically retry over a total window of 24–72 hours — long enough to survive a real consumer outage, bounded so a permanently-dead endpoint doesn't retry forever.

## At-least-once means the consumer must dedupe

Here's the guarantee to be honest about: reliable delivery is **at-least-once, not exactly-once.** Exactly-once over an unreliable network is a fantasy — if the consumer processes the event but its `200 OK` is lost to a timeout, the sender *must* retry, and the consumer sees the event twice. There's no way around it, so the contract has to make duplicates safe.

That means every event carries a stable `event_id` that never changes across retries, sent both in the payload and a header:

```http
POST /webhooks HTTP/1.1
Webhook-Id: evt_01HXYZ...           # stable across all retry attempts
Webhook-Timestamp: 1717718400
Webhook-Signature: v1,3n8dG...
Content-Type: application/json
```

The consumer records processed `Webhook-Id`s and ignores repeats. This is the same [idempotency discipline that distributed systems](https://blog.michaelsam94.com/idempotency-distributed-systems/) live and die by — the sender guarantees delivery, the receiver guarantees processing each event's effect only once. Document this loudly for your consumers, because the ones who don't dedupe will double-charge someone and blame your API.

## Signing: prove it came from you

A webhook endpoint is a public URL accepting POSTs, which means anyone can POST to it. Without authentication, an attacker can forge events — fake a "payment succeeded" and watch what happens. The standard defense is **HMAC signing**:

```python
import hashlib, hmac

def sign(secret: bytes, timestamp: str, body: bytes) -> str:
    msg = timestamp.encode() + b"." + body
    return "v1," + hmac.new(secret, msg, hashlib.sha256).hexdigest()

def verify(secret: bytes, timestamp: str, body: bytes, header: str) -> bool:
    expected = sign(secret, timestamp, body)
    return hmac.compare_digest(expected, header)  # constant-time!
```

Three details that are easy to get wrong: sign the **raw** request body (not a re-serialized version — JSON key ordering will bite you), include the **timestamp** in the signed data and reject old timestamps to prevent replay attacks, and always compare with a **constant-time** function so you don't leak the signature byte-by-byte through timing. HMAC-SHA256 with a shared secret is enough for the vast majority of webhook use cases; reserve mTLS for genuinely high-security B2B integrations.

## Dead-letter and observability

Eventually an endpoint is just gone — the customer deleted the service, the URL 404s permanently. After exhausting retries, don't drop the event: move it to a **dead-letter** state and stop retrying, but keep the record. This gives you two things: a way to inspect what failed and why, and a way to replay events once the consumer fixes their endpoint. A "replay failed deliveries" button has saved more partner relationships than any amount of uptime.

Round it out with per-endpoint observability. Track delivery success rate, retry counts, and latency per endpoint, and automatically disable endpoints that fail consistently for a long stretch (with a notification) so a dead consumer doesn't consume your delivery capacity forever.

| Concern | Mechanism | Failure it prevents |
| --- | --- | --- |
| Durability | Persist before delivery (outbox) | Lost events on crash |
| Transient failure | Exponential backoff + jitter | Dropped events, thundering herd |
| Duplicates | Stable event ID + consumer dedupe | Double-processing |
| Forgery | HMAC signature + timestamp | Spoofed / replayed events |
| Permanent failure | Dead-letter + replay | Silent data loss |
| Bad endpoints | Per-endpoint metrics + auto-disable | Wasted capacity |

None of these pieces is exotic, and that's the point. Reliable webhooks aren't a clever algorithm; they're a small set of boring guarantees applied consistently. Persist, retry sanely, make duplicates safe, sign everything, and never silently drop — build on those and your webhooks become the dependable backbone of your integrations rather than the thing partners complain about. If I had to pick the one that teams skip most often, it's "persist first" — and it's the one whose absence causes the quiet, unrecoverable data loss you only discover weeks later.

## Resources

- [Standard Webhooks specification](https://www.standardwebhooks.com/)
- [Stripe webhooks documentation](https://docs.stripe.com/webhooks)
- [AWS: exponential backoff and jitter](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- [RFC 2104 — HMAC: Keyed-Hashing for Message Authentication](https://datatracker.ietf.org/doc/html/rfc2104)
- [GitHub: securing webhook deliveries](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [OWASP: cheat sheet on server-side request forgery / webhooks](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

Webhooks looked trivial until a consumer outage silently dropped events — persist-first delivery with backoff turned integrations from complaint magnets into dependable contracts.

## Production context

**Production context** — In production, reliable webhook delivery with outbox and retries shows up where latency, correctness, and compliance intersect. When partners depend on event notifications for billing, fulfillment, or sync. The expensive mistake teams repeat: fire-and-forget post without durable queue or retry policy.

## Core mechanism

From incident review: Webhooks looked trivial until a consumer outage silently dropped events — persist-first delivery with backoff turned integrations from complaint magnets into dependable contracts. That symptom is the compass — if your design cannot explain how it prevents that user-visible failure, narrow scope before widening rollout.

## Implementation walkthrough

Instrument the change on one route or tenant first. Slice RUM by device class and connection type; lab Lighthouse confirms repro but field p75 decides priority. Document owner, rollback path, and the single metric you expect to move.

## Edge cases

Edge cases matter: corporate proxies, Save-Data clients, ad blockers, and OEM battery savers behave unlike staging on office Wi-Fi. Test keyboard-only paths, refresh mid-flow, and back navigation — especially when reliable webhook delivery with outbox and retries touches auth or checkout.

## Performance impact

Security and privacy ride along even for "frontend-only" work. Treat URL params, CMS HTML, and webhook bodies as hostile. Fail closed, log correlation IDs, and add CI checks so unsafe patterns regress visibly.

## Accessibility

Operability: link runbooks from dashboards, alert on week-over-week p75 regression for tier-1 surfaces, and schedule a 15-minute review after the next traffic doubling. Assumptions drift faster than dependencies.

## Operational checklist

Accessibility: WCAG 2.2 AA remains the bar — focus visibility, target size, reduced motion, and polite live regions for async feedback. Automated axe in CI catches roughly a third of issues; manual screen reader passes catch the rest.