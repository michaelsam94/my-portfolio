---
title: "Idempotency in Distributed Systems"
slug: "idempotency-distributed-systems"
description: "Why idempotency is the safety net for retries in distributed systems: idempotency keys, dedup windows, and patterns that prevent double charges."
datePublished: "2026-05-28"
dateModified: "2026-05-28"
tags: ["Distributed Systems", "Idempotency", "Backend", "Reliability"]
keywords: "idempotency, idempotency key, distributed systems, exactly-once, retry safety, deduplication"
faq:
  - q: "What does idempotency mean in distributed systems?"
    a: "An operation is idempotent if performing it multiple times has the same effect as performing it once. In distributed systems this makes retries safe: if a client resends a request after a timeout, the server processes it once and returns the same result instead of duplicating the effect."
  - q: "What is an idempotency key?"
    a: "An idempotency key is a unique identifier the client generates and attaches to a request. The server records it, so if the same key arrives again it returns the stored result of the first attempt instead of executing the operation twice. Stripe and other payment APIs use exactly this pattern."
  - q: "Is exactly-once delivery possible?"
    a: "Exactly-once network delivery is generally impossible, but exactly-once processing is achievable. You accept at-least-once delivery and make handlers idempotent, so duplicate deliveries produce a single effect. That combination is what people mean when they say exactly-once."
---

Idempotency is the property that lets you retry safely, and in a distributed system you *will* retry — networks time out, connections drop mid-request, and clients resend. An operation is idempotent when doing it twice has the same effect as doing it once. Get this right and a flaky link produces harmless duplicate requests; get it wrong and the same flakiness produces double charges, duplicate orders, and the kind of incident that ends up in a postmortem. On a payment-adjacent platform I built, idempotency was not a nice-to-have — it was the single rule that prevented the worst failure mode from ever occurring.

Here is how to reason about it and how to implement it without hand-waving.

## Why you cannot avoid retries

The fundamental problem: when a client sends a request and the response never arrives, the client cannot tell *what happened*. Did the request never reach the server? Did the server process it and the response got lost on the way back? These are indistinguishable from the client's side.

The client has two options: give up (and risk a lost operation) or retry (and risk a duplicate). In any system that cares about not losing operations, you retry. That is why network delivery is fundamentally **at-least-once**. Idempotency is how you make at-least-once delivery behave like exactly-once *processing* — which is the only kind of "exactly-once" that is actually achievable.

## Some operations are naturally idempotent; most are not

HTTP semantics are a useful mental model. `GET`, `PUT`, and `DELETE` are meant to be idempotent: setting a resource's state to X twice leaves it at X. `POST` — "create a new thing" — is not, and that is where the danger lives.

```
Naturally idempotent:   SET balance = 100      (same result every time)
NOT idempotent:         balance = balance + 50 (each retry adds 50 again)
NOT idempotent:         INSERT new order       (each retry creates an order)
```

The classic disaster is "charge the card $50." Model it as an increment or a blind insert and every retry is real money moved twice. So for non-idempotent operations you add idempotency explicitly.

## The idempotency key pattern

The standard, battle-tested approach — the one Stripe and every serious payment API uses — is the **idempotency key**. The client generates a unique key (a UUID) per logical operation and sends it with the request. The server records the key and the operation's result. If the same key ever arrives again, the server skips execution and returns the stored result.

```http
POST /v1/charges
Idempotency-Key: 3f8b0c1a-9d2e-4b7a-8c11-2f0e5a6b7c8d
Content-Type: application/json

{ "amount": 5000, "currency": "usd", "source": "tok_visa" }
```

Server-side, the flow is:

```sql
-- One atomic check-and-insert prevents two concurrent retries racing.
INSERT INTO idempotency_keys (key, status, request_hash)
VALUES ($1, 'in_progress', $2)
ON CONFLICT (key) DO NOTHING
RETURNING key;
```

- If the insert **succeeds**, this is the first time you have seen the key. Execute the operation, then store the result against the key.
- If it **conflicts**, the key already exists. Return the stored result (or, if still `in_progress`, tell the client to retry shortly).

Two details separate a correct implementation from a buggy one:

1. **Store the request hash.** If a client reuses a key with a *different* payload, that is a bug on their side — reject it rather than returning a mismatched result.
2. **Persist the result, not just the key.** The whole point is returning the *same response* on retry. Recording "we saw this key" without the response leaves the client unable to learn the outcome.

## Deduplication windows and storage

Idempotency keys cannot live forever — that table would grow without bound. You keep a **dedup window**: 24 hours, 7 days, whatever exceeds your realistic client retry horizon. After that, keys expire. Choose the window to comfortably outlast client and queue retry policies; a 30-second window against a job that retries for an hour is a bug waiting to happen.

For high throughput, keys often live in a fast store (Redis with TTL) fronting the durable record, but the *authority* on "did this already happen" should be the same transactional store as the effect, so the check and the effect commit atomically. Splitting them invites the exact race you are trying to prevent.

## Where idempotency shows up beyond APIs

The pattern generalizes far past HTTP endpoints:

| Context | Idempotency mechanism |
| --- | --- |
| Message queue consumers | Dedup on a message id before applying the effect |
| Event sourcing / [outbox](https://blog.michaelsam94.com/event-driven-outbox-pattern/) | Consumers track processed event ids |
| Database upserts | `INSERT ... ON CONFLICT DO UPDATE` keyed on a natural key |
| Offline mobile sync | Client-generated keys in the [outbox queue](https://blog.michaelsam94.com/offline-first-flutter-sync/) |

That last one is why idempotency and offline-first are the same conversation from two directions. An offline mobile app queues writes locally and pushes them on reconnect; without idempotency keys, a retried push after a partial success duplicates the write. With them, the retry is a no-op. It is the identical discipline that kept the [EV charging platform](https://blog.michaelsam94.com/how-i-architected-an-ev-charging-platform/) from ever opening a second billable session when a socket dropped mid-`StartTransaction`.

## The rule I write down for teams

Make every state-changing operation idempotent *before* you write the happy path, not after the first double-charge incident. Concretely:

- Generate an idempotency key at the point the user intent is formed (the client), not deep in the server.
- Check-and-record the key in the same transaction as the effect.
- Store and replay the original response.
- Validate the request hash to catch key reuse bugs.
- Set a dedup window that outlives every retry policy in the system.

Idempotency is unglamorous plumbing, and it is precisely the kind of boring, strict discipline that makes real-time and payment systems trustworthy. Retries are not an edge case in distributed systems — they are the normal case — so design for them from the first line. Want help auditing where your system is exposed to duplicate writes? [Let's talk](/#contact).

## Resources

- [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests)
- [AWS Builders' Library: making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
- [Idempotent receiver pattern (microservices.io)](https://microservices.io/patterns/communication-style/idempotent-consumer.html)
- [RFC 9110: HTTP idempotent methods](https://www.rfc-editor.org/rfc/rfc9110#name-idempotent-methods)
- [Azure: retry and idempotency guidance](https://learn.microsoft.com/en-us/azure/architecture/best-practices/transient-faults)
- [Martin Fowler: distributed systems patterns](https://martinfowler.com/articles/patterns-of-distributed-systems/)
