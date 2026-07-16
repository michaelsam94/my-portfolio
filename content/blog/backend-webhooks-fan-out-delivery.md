---
title: "Fan-Out Webhook Delivery"
slug: "backend-webhooks-fan-out-delivery"
description: "Webhook fan-out delivers events to thousands of subscriber endpoints reliably. Design signing, retry policies, dead letter queues, and delivery dashboards for SaaS webhook infrastructure."
datePublished: "2024-11-29"
dateModified: "2024-11-29"
tags: ["Backend", "Architecture", "Webhooks", "API"]
keywords: "webhook fan-out delivery, webhook retry, HMAC signature webhooks, webhook dead letter queue, SaaS webhook infrastructure"
faq:
  - q: "How do webhooks differ from polling?"
    a: "Webhooks push events to subscriber URLs in near-real-time when something happens. Polling requires subscribers to repeatedly ask 'anything new?' Webhooks are efficient for the subscriber but push delivery complexity — retries, signing, endpoint validation — onto the publisher."
  - q: "How should webhook payloads be signed?"
    a: "Include an HMAC-SHA256 signature of the raw request body in a header (e.g., X-Signature-SHA256), using a per-subscriber secret. Subscribers verify the signature before processing. Never sign parsed JSON — whitespace differences break verification. Include a timestamp to prevent replay attacks."
  - q: "What retry policy works for webhook delivery?"
    a: "Exponential backoff over 24–72 hours: attempt at 0s, 1m, 5m, 30m, 2h, 8h, 24h. Stop after 7–10 attempts and move to dead letter. Return the failed event in a dashboard so subscribers can manually replay. Disable endpoints that fail consistently (410 Gone or 50+ consecutive failures)."
---

Your SaaS product ships webhooks — "we'll POST to your URL when events happen." One customer signs up, easy. Five hundred customers with three endpoints each, handling subscriber downtime, SSL cert expiry, and 3-second timeouts on shared hosting — that's fan-out delivery infrastructure. Stripe, GitHub, and Twilio all solved this with signed payloads, aggressive retries, and subscriber-facing delivery logs. Here's how to build the same.

## Architecture

```
Event bus → Webhook dispatcher → delivery queue (per endpoint)
                                      ↓
                              HTTP POST + signature
                                      ↓
                              2xx → mark delivered
                              4xx/5xx/timeout → retry queue
                                      ↓
                              max retries → DLQ + alert subscriber
```

Decouple event ingestion from delivery. The dispatcher writes delivery jobs; workers execute HTTP calls.

## Data model

```sql
CREATE TABLE webhook_endpoints (
    id            UUID PRIMARY KEY,
    account_id    UUID NOT NULL,
    url           TEXT NOT NULL,
    secret        VARCHAR(255) NOT NULL,
    events        TEXT[] NOT NULL,  -- ['order.created', 'order.updated']
    enabled       BOOLEAN DEFAULT true,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE webhook_deliveries (
    id            UUID PRIMARY KEY,
    endpoint_id   UUID REFERENCES webhook_endpoints(id),
    event_id      UUID NOT NULL,
    event_type    VARCHAR(100) NOT NULL,
    payload       JSONB NOT NULL,
    status        VARCHAR(20) DEFAULT 'pending',
    attempt_count INT DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    response_code INT,
    response_body TEXT,
    delivered_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now()
);
```

## Signing payloads

```typescript
function signPayload(payload: string, secret: string, timestamp: number): string {
  const signedContent = `${timestamp}.${payload}`;
  return createHmac('sha256', secret).update(signedContent).digest('hex');
}

async function deliverWebhook(delivery: WebhookDelivery, endpoint: WebhookEndpoint) {
  const payload = JSON.stringify(delivery.payload);
  const timestamp = Math.floor(Date.now() / 1000);
  const signature = signPayload(payload, endpoint.secret, timestamp);

  const response = await fetch(endpoint.url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Webhook-Id': delivery.id,
      'X-Webhook-Timestamp': String(timestamp),
      'X-Webhook-Signature': `sha256=${signature}`,
      'User-Agent': 'MyApp-Webhooks/1.0',
    },
    body: payload,
    signal: AbortSignal.timeout(30_000),
  });

  return { status: response.status, body: await response.text().catch(() => '') };
}
```

Subscribers verify:

```typescript
function verifyWebhook(payload: string, signature: string, timestamp: string, secret: string): boolean {
  const age = Date.now() / 1000 - parseInt(timestamp);
  if (age > 300) return false; // reject replays older than 5 min

  const expected = signPayload(payload, secret, parseInt(timestamp));
  return timingSafeEqual(
    Buffer.from(signature.replace('sha256=', '')),
    Buffer.from(expected)
  );
}
```

## Retry schedule

```typescript
const RETRY_INTERVALS_SECONDS = [0, 60, 300, 1800, 7200, 28800, 86400];

function nextRetryTime(attemptCount: number): Date {
  const delaySec = RETRY_INTERVALS_SECONDS[Math.min(attemptCount, RETRY_INTERVALS_SECONDS.length - 1)];
  return new Date(Date.now() + delaySec * 1000);
}
```

Use [full jitter](https://blog.michaelsam94.com/backend-retry-jitter-exponential-backoff/) on top to prevent synchronized retries to the same failing endpoint.

## Endpoint verification on signup

Challenge subscribers to prove URL ownership:

```typescript
async function verifyEndpoint(url: string, secret: string): Promise<boolean> {
  const challenge = randomBytes(16).toString('hex');
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ type: 'endpoint.verification', challenge }),
    signal: AbortSignal.timeout(10_000),
  });
  const body = await response.json();
  return body.challenge === challenge;
}
```

## Subscriber-facing delivery log

Expose `GET /webhooks/deliveries?endpoint_id=...` showing status, response code, and replay button. This is the #1 support deflection tool — subscribers debug their own 500s instead of opening tickets.

## Auto-disable failing endpoints

After 50 consecutive failures or repeated 410 responses, disable the endpoint and email the account owner. Re-enable requires manual confirmation or successful verification challenge.

## Fan-out at scale

Shard delivery workers by endpoint ID. Rate-limit per endpoint (max 10 concurrent deliveries) to avoid overwhelming subscriber servers. Batch internal event processing; deliver individually.

## Webhook event design

Payload design affects subscriber integration quality:

```json
{
  "id": "evt_abc123",
  "type": "order.created",
  "created": "2025-03-15T10:30:00Z",
  "data": {
    "object": {
      "id": "ord_xyz",
      "total": 5000,
      "currency": "usd"
    }
  },
  "api_version": "2025-03-01"
}
```

Rules for webhook payloads:

- **Include event ID** — subscribers deduplicate on this
- **Wrap data in `data.object`** — consistent envelope across event types (Stripe pattern)
- **Version the API** — `api_version` field lets subscribers handle schema changes
- **Don't include PII unnecessarily** — subscribers store your payloads; minimize sensitive data
- **Keep payloads small** — include IDs, not full nested objects; subscribers fetch details via API if needed
- **Same event type, same schema** — don't change payload shape without version bump

## Subscriber endpoint requirements

Document what you expect from subscriber endpoints:

- Respond with 2xx within 30 seconds (configurable timeout)
- Return 410 Gone to signal permanent removal — auto-disable endpoint
- Return 429 with Retry-After if temporarily overloaded — respect it
- Idempotent processing — your retries will duplicate deliveries
- HTTPS only — reject HTTP endpoints at registration
- Valid SSL certificate — check on registration and periodically

## Security beyond HMAC signing

- **Timestamp validation** — reject payloads with timestamps >5 minutes old (replay prevention)
- **Constant-time comparison** — use `timingSafeEqual` for signature verification, not `===`
- **IP allowlisting** — optional, for enterprise subscribers who want to firewall your delivery IPs
- **Secret rotation** — allow subscribers to roll secrets without downtime (dual-secret verification window)
- **Payload encryption** — optional for enterprise tier; encrypt with subscriber's public key

## Delivery dashboard features

The delivery log is your best support tool. Include:

- Filter by endpoint, event type, status, date range
- Response code and truncated response body for failures
- Manual replay button (generates new delivery with same payload, new delivery ID)
- Bulk replay for failed deliveries after subscriber fixes their endpoint
- Webhook test button — send sample event to endpoint on demand
- Delivery latency percentiles per endpoint

## Scaling fan-out delivery

At thousands of endpoints and millions of events daily:

- **Shard workers by endpoint ID hash** — consistent routing, no duplicate delivery
- **Priority queues** — enterprise tier endpoints get dedicated workers
- **Batch event ingestion, individual delivery** — don't batch HTTP calls; each endpoint gets its own delivery job
- **Circuit breaker per endpoint** — stop delivering to endpoints in sustained failure
- **Geographic routing** — deliver from region closest to subscriber endpoint when global
- **Connection pooling** — reuse HTTP connections to frequently-delivering endpoints

## Failure modes

- **Signing parsed JSON instead of raw body** — whitespace differences break verification
- **No timestamp in signature** — replay attacks possible
- **Retrying 4xx errors** — 400/404 won't fix themselves; send to DLQ immediately
- **No auto-disable** — one broken endpoint consumes retry budget indefinitely
- **Delivering before DB commit** — event references data that doesn't exist yet; deliver after transaction commits (outbox pattern)
- **Shared secret across endpoints** — one leak compromises all; per-endpoint secrets

## Production checklist

- HMAC-SHA256 signature of raw body with per-endpoint secret
- Timestamp included in signature with 5-minute replay window
- Exponential backoff retry over 24–72 hours, then DLQ
- Auto-disable after consecutive failures with email notification
- Endpoint verification challenge on registration
- Subscriber-facing delivery log with manual replay
- 4xx (except 429) goes to DLQ without retry
- Event payloads versioned with api_version field
- Rate limit concurrent deliveries per endpoint

## Resources

- [Stripe webhooks best practices](https://stripe.com/docs/webhooks/best-practices)
- [GitHub webhook documentation](https://docs.github.com/en/webhooks)
- [Standard Webhooks specification](https://www.standardwebhooks.com/)
- [Svix webhook infrastructure (open source)](https://docs.svix.com/)
- [OWASP webhook security](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html)
