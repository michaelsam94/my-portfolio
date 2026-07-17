---
title: "AI Agents: Webhook Signature Verification"
slug: "agent-webhook-signature-verification"
description: "Verify inbound webhooks to agent platforms: HMAC timing-safe comparison, key rotation, replay prevention, and provider-specific quirks for Stripe, GitHub, and tool callbacks."
datePublished: "2025-09-15"
dateModified: "2026-07-17"
tags: ["AI Agents", "Webhooks", "Security", "Integration"]
keywords: "agent webhook signature verification, HMAC webhook security, Stripe webhook agent, replay attack prevention"
faq:
  - q: "Why must agent platforms verify webhooks at the edge?"
    a: "Unverified webhooks let attackers forge tool-completion events, billing state changes, or human-approval callbacks — triggering agent runs that execute real side effects (refunds, deployments, emails). Verification is authentication for server-to-server callbacks."
  - q: "Raw body or parsed JSON for HMAC verification?"
    a: "Always HMAC the raw request bytes before JSON parsing. Re-serialized JSON changes whitespace and key order — signature mismatch on legit requests. Buffer raw body in middleware, then parse."
  - q: "How do you handle webhook secret rotation?"
    a: "Accept two signing secrets during overlap window — try primary, fallback secondary on failure. Provider dashboards (Stripe, Svix) support dual secrets. Remove old secret after 72h zero secondary usage."
  - q: "What stops replay attacks on signed webhooks?"
    a: "Timestamp tolerance (e.g., reject if >5 min skew) plus idempotency store on event ID. Signature proves integrity; timestamp + dedupe proves freshness."
---

Your agent resumes a workflow when Stripe sends `payment_intent.succeeded` or when a human approver clicks Approve in an external ticketing system. If those POST requests aren't cryptographically verified, anyone who guesses the URL shape can **forge completions** and trigger tool chains that ship orders, merge PRs, or exfiltrate data via agent tool calls. Webhook signature verification is non-negotiable at the agent gateway.

## Verification flow

```
Provider                    Agent gateway
   │                              │
   │  POST /webhooks/stripe       │
   │  Stripe-Signature: t=...,v1=│
   │  body: raw JSON              │
   │ ────────────────────────────►│
   │                              │ 1. Read raw body
   │                              │ 2. Verify signature + timestamp
   │                              │ 3. Dedupe event_id
   │                              │ 4. Parse JSON → enqueue agent resume
   │◄──────────────────────────────│ 200 OK (fast — work async)
```

Return 200 quickly after verification; heavy agent work belongs on queue.

## Generic HMAC verifier (timing-safe)

```python
import hmac
import hashlib
import time

def verify_hmac_sha256(
    secret: str,
    raw_body: bytes,
    signature_header: str,
    timestamp_header: str | None = None,
    tolerance_sec: int = 300,
) -> bool:
    if timestamp_header:
        ts = int(timestamp_header)
        if abs(time.time() - ts) > tolerance_sec:
            return False
        signed_payload = f"{ts}.".encode() + raw_body
    else:
        signed_payload = raw_body

    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=")
    return hmac.compare_digest(expected, provided)
```

Never use `==` for signature comparison — timing leaks.

## Stripe-specific verification

```python
import stripe

@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(
            payload, sig, secrets.current("stripe_webhook")
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "invalid signature")

    if await dedupe.seen(event["id"]):
        return {"ok": True}
    await queue.publish({"type": "stripe", "event": event})
    await dedupe.mark(event["id"], ttl=86400 * 7)
    return {"ok": True}
```

Stripe signs `timestamp.payload` — library handles edge cases.

## GitHub webhooks

```python
def verify_github(payload: bytes, sig_header: str, secret: str) -> bool:
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)
```

Also validate `X-Hub-Signature-256` on **raw body**; consider IP allowlist for github.com meta ranges as defense in depth.

## Tool callback webhooks (custom integrations)

Third-party tools calling back to agent orchestrator need standardized signing:

```http
POST /webhooks/tools/acme-crm
X-Agent-Timestamp: 1721200000
X-Agent-Signature: v1=abc123...
X-Agent-Event-Id: evt_unique_8842

{"tool_run_id": "tr_9f3", "status": "completed", "result_ref": "s3://..."}
```

Document in partner integration guide; issue per-tenant webhook secrets rotatable in admin UI.

## Dual-secret rotation

```python
def verify_with_rotation(raw: bytes, header: str) -> bool:
    for secret in secrets.list_active("webhook_hmac"):
        if verify_hmac_sha256(secret, raw, header):
            metrics.increment("webhook_verify", labels={"secret_version": secret.version})
            return True
    return False
```

Alert if `secret_version=old` exceeds 5% after rotation window.

## Idempotency store

| Provider | Dedupe key |
|----------|------------|
| Stripe | `event.id` |
| GitHub | `X-GitHub-Delivery` |
| Custom | `X-Agent-Event-Id` |

```sql
CREATE TABLE webhook_events (
  event_id text PRIMARY KEY,
  received_at timestamptz DEFAULT now(),
  provider text NOT NULL
);
```

Duplicate delivery returns 200 without re-enqueueing agent resume — critical for at-least-once providers.

## Fastify / Express raw body capture

```typescript
app.addContentTypeParser(
  "application/json",
  { parseAs: "buffer" },
  (req, body, done) => {
    (req as any).rawBody = body;
    done(null, JSON.parse(body.toString()));
  }
);
```

Next.js App Router — disable default body parser on webhook route or use `request.text()`.

## Failure modes

| Mistake | Symptom |
|---------|---------|
| JSON re-stringify before verify | Random 400s in prod |
| NGINX buffer mutation | Signature drift — disable unnecessary transforms |
| 500 on duplicate event | Provider infinite retry storm |
| Sync agent run in handler | Timeouts → provider retries → duplicate side effects |

## Resources

- [Stripe — Webhook signatures](https://docs.stripe.com/webhooks/signatures)
- [GitHub — Validating webhook deliveries](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
- [Svix — Webhook standard](https://docs.svix.com/receiving/verifying-payloads)
- [OWASP — Webhook security cheat sheet](https://cheatsheetseries.owasp.org/cheatsheets/Webhook_Security_Cheat_Sheet.html)

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

## Operational checklist for production rollouts

Before widening traffic, confirm dashboards exist for the leading indicators discussed above — not only lagging incident counts. Run a game day that exercises rollback: feature flag off, alias revert, or kill switch without a new deploy. Document who owns each control in the service catalog so on-call is not guessing during a Sev2.

Slice metrics by tenant tier during canary. Global averages hide bad enterprise cohorts. Pair technical metrics with a sample of user-visible outcomes weekly — support ticket themes often lead dashboards by 48 hours.

When third-party providers change defaults (models, TLS roots, streaming semantics), error-class metrics should catch drift within hours even if no deploy shipped on your side. Keep a changelog subscription for every dependency on the critical path.

## Field notes from incident reviews

Repeat incidents without automation tickets are a planning failure, not an engineering surprise. Capture toil hours in retro; fund paydown in the next sprint. Prefer idempotent handlers and explicit state machines over ad-hoc scripts that only the author understands.

Audit trails matter for billing, auth, and safety paths. Log structured enums — not prose — so aggregation survives high volume. Redact secrets and tokens at the logging boundary; debugging can use correlation ids instead.

