---
title: "Verifying Webhook Signatures"
slug: "webhooks-signature-verification"
description: "Verify webhook authenticity with HMAC signatures: Stripe-style signing, timestamp validation, constant-time comparison, and preventing replay attacks."
datePublished: "2026-05-25"
dateModified: "2026-07-17"
tags: ["Backend", "Webhooks", "Security", "API"]
keywords: "webhook signature, HMAC verification, webhook security, replay attack, Stripe signature, SHA-256"
faq:
  - q: "Why is webhook signature verification necessary?"
    a: "Webhook endpoints are public URLs. Without signature verification, anyone who discovers the URL can send fake events — creating fraudulent orders, triggering refunds, or modifying account state. Signatures prove the payload came from the expected sender and wasn't modified in transit. Always verify before processing any webhook payload."
  - q: "Should I verify the signature before or after parsing the JSON body?"
    a: "Verify before parsing. Read the raw request body as bytes, compute the expected signature, and compare. Then parse JSON. If you parse first and re-serialize, whitespace and key ordering differences will cause signature mismatches. Most frameworks let you access the raw body before JSON middleware processes it."
  - q: "How do timestamp checks prevent replay attacks?"
    a: "Include a timestamp in the signed payload. Reject webhooks with timestamps older than your tolerance window (typically 5 minutes). An attacker who captures a valid webhook cannot replay it after the window expires. Combine timestamp validation with idempotency keys for defense in depth against both replay and duplicate delivery."
---
An attacker found our webhook URL in a client-side error log and POSTed a fake `order.completed` event. Our handler processed it — no signature check, no authentication. One line of middleware verifying HMAC-SHA256 would have rejected it. We added signature verification that day and rotated the webhook secret as a precaution.

## HMAC signature scheme

Most providers use HMAC-SHA256:

```
signature = HMAC-SHA256(secret, timestamp + "." + raw_body)
```

The sender includes the signature and timestamp in headers. The receiver recomputes and compares.

## Stripe-style verification

```python
import hmac
import hashlib
import time

def verify_stripe_signature(payload: bytes, sig_header: str, secret: str, tolerance: int = 300):
    elements = dict(item.split("=", 1) for item in sig_header.split(","))
    timestamp = int(elements["t"])
    received_sig = elements["v1"]

    # Reject stale timestamps
    if abs(time.time() - timestamp) > tolerance:
        raise WebhookError("Timestamp outside tolerance window")

    # Compute expected signature
    signed_payload = f"{timestamp}.".encode() + payload
    expected_sig = hmac.new(
        secret.encode(), signed_payload, hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    if not hmac.compare_digest(expected_sig, received_sig):
        raise WebhookError("Invalid signature")

    return True
```

## Generic HMAC verification

For custom webhooks or providers using simpler schemes:

```python
def verify_hmac_signature(payload: bytes, signature: str, secret: str):
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)
```

Header format varies by provider:

| Provider | Header | Format |
|---|---|---|
| Stripe | `Stripe-Signature` | `t=timestamp,v1=sig` |
| GitHub | `X-Hub-Signature-256` | `sha256=hex_sig` |
| Shopify | `X-Shopify-Hmac-Sha256` | base64 sig |
| Svix | `svix-signature` | `v1,base64_sig` |

## Express middleware

```javascript
function webhookVerifier(secret) {
  return (req, res, next) => {
    const signature = req.headers['x-webhook-signature'];
    const timestamp = req.headers['x-webhook-timestamp'];
    const rawBody = req.rawBody; // capture before JSON parsing

    if (!signature || !timestamp) {
      return res.status(401).json({ error: 'Missing signature headers' });
    }

    const age = Math.abs(Date.now() / 1000 - parseInt(timestamp));
    if (age > 300) {
      return res.status(401).json({ error: 'Timestamp too old' });
    }

    const signedPayload = `${timestamp}.${rawBody}`;
    const expected = crypto
      .createHmac('sha256', secret)
      .update(signedPayload)
      .digest('hex');

    if (!crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signature))) {
      return res.status(401).json({ error: 'Invalid signature' });
    }

    next();
  };
}

// Capture raw body before JSON middleware
app.use('/webhooks', express.raw({ type: 'application/json' }));
app.use('/webhooks', webhookVerifier(process.env.WEBHOOK_SECRET));
app.use('/webhooks', (req, res, next) => {
  req.body = JSON.parse(req.body);
  next();
});
```

## Raw body capture

Framework-specific raw body access:

```python
# FastAPI
@app.post("/webhooks")
async def handle_webhook(request: Request):
    body = await request.body()  # raw bytes
    signature = request.headers.get("X-Webhook-Signature")
    verify_hmac(body, signature, SECRET)
    payload = json.loads(body)
```

```ruby
# Rails — skip params parsing for webhook routes
class WebhooksController < ApplicationController
  skip_before_action :verify_authenticity_token

  def create
    payload = request.raw_post
    verify_signature(payload, request.headers["X-Signature"])
    process(JSON.parse(payload))
  end
end
```

## Secret management

- Generate secrets with `openssl rand -hex 32`
- Store in a secrets manager, not environment variables in code
- Support secret rotation with dual-secret verification during transition
- Rotate immediately if a secret is exposed
- Use different secrets per webhook endpoint

```python
def verify_with_rotation(payload, signature, timestamp):
    for secret in [current_secret, previous_secret]:
        try:
            return verify_signature(payload, signature, secret, timestamp)
        except WebhookError:
            continue
    raise WebhookError("No valid secret matched")
```

## Security checklist

1. **Verify signature on every request** — no exceptions for "testing"
2. **Use raw body bytes** — never re-serialize parsed JSON
3. **Validate timestamp** — reject replays outside tolerance window
4. **Constant-time comparison** — use `hmac.compare_digest` or `crypto.timingSafeEqual`
5. **Return generic 401** — don't leak whether timestamp or signature failed
6. **Log verification failures** — alert on repeated failures from same IP
7. **Rotate secrets** — support dual-secret during rotation windows

## Clock skew tolerance

Set timestamp tolerance to 5 minutes (300 seconds) — enough for minor clock drift, short enough to limit replay windows. Log rejected timestamps with the delta for debugging NTP issues on receiver servers.

## Testing signature verification

Generate test vectors in CI:

```python
def test_signature_roundtrip():
    payload = b'{"event": "test"}'
    ts = str(int(time.time()))
    sig = compute_signature(payload, ts, TEST_SECRET)
    assert verify(payload, f"t={ts},v1={sig}", TEST_SECRET)
```

## Resources

- [Stripe webhook signatures](https://docs.stripe.com/webhooks/signatures)
- [GitHub webhook validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [Svix webhook verification library](https://github.com/svix/svix-webhooks)
- [OWASP Webhook Security](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html)
- [Shopify HMAC verification](https://shopify.dev/docs/apps/build/webhooks/subscribe/https)

## Operational checklist (1)

Before promoting Webhooks Signature Verification changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Webhooks Signature Verification after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Webhooks Signature Verification touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Webhooks Signature Verification changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Webhooks Signature Verification after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Webhooks Signature Verification touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Cross-team contracts for webhooks signature verification

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how webhooks signature verification breaks without a clear owner in the incident channel.

| Check | Expected for webhooks signature verification |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for webhooks signature verification

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct webhooks signature verification changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

Concrete probe 2: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for webhooks signature verification

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most webhooks signature verification regressions before production.

| Check | Expected for webhooks signature verification |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around webhooks signature verification

Most incidents involving webhooks signature verification start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

Concrete probe 4: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for webhooks signature verification

Name three invariants that must hold after every deploy of webhooks signature verification. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for webhooks signature verification |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for webhooks signature verification

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to webhooks signature verification, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 6: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for webhooks signature verification

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for webhooks signature verification should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for webhooks signature verification |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for webhooks signature verification in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
