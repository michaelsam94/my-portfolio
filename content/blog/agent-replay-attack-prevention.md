---
title: "AI Agents: Replay Attack Prevention"
slug: "agent-replay-attack-prevention"
description: "Stop captured agent tool requests, webhook payloads, and signed approvals from executing twice—combining request binding, freshness windows, and idempotency without breaking legitimate retries."
datePublished: "2025-09-17"
dateModified: "2025-09-17"
tags: ["AI", "Agent", "Replay"]
keywords: "replay attack prevention, agent webhook security, HMAC request signing, nonce store, idempotency keys, MCP tool invocation"
faq:
  - q: "Is HTTPS enough to prevent replay attacks on agent APIs?"
    a: "No. TLS protects bytes in transit; replay captures a valid request after delivery and resends it. If the server accepts the same signed payload again—approve refund, delete resource, invoke paid tool—the attack succeeds without breaking encryption."
  - q: "Should agent tool calls use nonces or idempotency keys?"
    a: "Use both for mutating operations. Idempotency keys let clients safely retry on timeout and receive the same response. Nonces enforce single execution within a short window. A retry reuses the idempotency key; a replay attacker cannot mint fresh nonces without the signing secret."
  - q: "How long should replay protection windows last for human approval links?"
    a: "Match the business SLA: 15 minutes for Slack approve/deny buttons, 24 hours max for email links with step-up auth on open. Shorter is better; pair long windows with one-time nonce consumption at click time."
  - q: "Do replay defenses apply to MCP server tool invocations?"
    a: "Yes for side-effecting tools. The MCP host should attach monotonic session sequence numbers or signed envelopes verified by the server; stateless re-execution of identical JSON-RPC ids must not double-charge or double-write."
---
An attacker pasted the same `curl` command three times and created three outbound wire transfers. Our agent had approved the first invocation after HMAC verification; nobody checked whether that exact payload had already run. TLS was fine. Authentication was fine. **Freshness and uniqueness** were missing—the request was a valid frozen moment the attacker could replay until the signing key rotated.

Agent systems amplify replay risk because tools perform real-world side effects: spend credits, send email, merge pull requests, call paid APIs. Prevention is layered; no single header solves every path.

## Attack surfaces in agent architectures

```
Attacker captures ──► Retries before expiry ──► Server accepts ──► Duplicate effect
        │                      │
        ├─ Browser devtools on approval POST
        ├─ Proxy logs on webhook ingress
        ├─ Compromised integration partner
        └─ LLM prompt injection triggering duplicate tool JSON
```

Each path needs a control matched to trust boundaries—not copy-pasted middleware from a blog post.

## Layer 1: Signed envelopes with timestamp and nonce

For inbound webhooks and orchestrator→worker commands, verify:

```python
import hmac, hashlib, time
from dataclasses import dataclass

MAX_SKEW_SECONDS = 300

@dataclass
class SignedRequest:
    body: bytes
    timestamp: int
    nonce: str
    signature: str

def verify_envelope(req: SignedRequest, secret: bytes, nonce_store) -> bool:
    now = int(time.time())
    if abs(now - req.timestamp) > MAX_SKEW_SECONDS:
        return False  # stale or clock attack

    if not nonce_store.consume(req.nonce, ttl_seconds=MAX_SKEW_SECONDS):
        return False  # replay or duplicate

    message = f"{req.timestamp}.{req.nonce}.".encode() + req.body
    expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, req.signature)
```

`consume` must be atomic—Redis `SET key 1 NX EX ttl` or database `DELETE ... RETURNING`. Checking then deleting in two steps loses races.

Rotate webhook secrets with overlap: accept old and new signatures for 48 hours, then retire old.

## Layer 2: Idempotency for safe client retries

Network timeouts cause legitimate duplicates. Separate replay defense from retry semantics:

```typescript
async function handleToolInvoke(req: Request, db: Db): Promise<Response> {
  const idempotencyKey = req.headers.get("Idempotency-Key");
  if (!idempotencyKey) {
    return jsonError(400, "Idempotency-Key required for mutating tools");
  }

  const cached = await db.getIdempotentResponse(idempotencyKey);
  if (cached) return Response.json(cached.body, { status: cached.status });

  await verifyEnvelope(req); // includes nonce consume

  const result = await executeTool(await req.json());
  await db.storeIdempotentResponse(idempotencyKey, result, ttlHours: 24);
  return Response.json(result);
}
```

Idempotency keys are **client-chosen and stable across retries**. Nonces are **server-verified single use**. Confusing them produces either double execution or rejected legitimate retries.

## Layer 3: Session-bound sequence for long-lived agent runs

Multi-step agent sessions replay individual steps if an attacker captures one HTTP call. Bind each mutating step to a monotonic counter stored server-side:

```sql
CREATE TABLE agent_session_state (
  session_id    text PRIMARY KEY,
  last_seq      bigint NOT NULL DEFAULT 0,
  updated_at    timestamptz NOT NULL DEFAULT now()
);
```

```typescript
async function invokeStep(sessionId: string, seq: bigint, action: Action, db: Db) {
  const updated = await db.query(
    `UPDATE agent_session_state
     SET last_seq = $2, updated_at = now()
     WHERE session_id = $1 AND last_seq = $2 - 1
     RETURNING last_seq`,
    [sessionId, seq]
  );
  if (updated.rowCount === 0) {
    throw new ReplayError("out-of-order or replayed step");
  }
  return runAction(action);
}
```

Clients receive `next_seq` in each response. Replaying `seq=5` after the server advanced to `6` fails.

## Human-in-the-loop approvals

Email and Slack buttons are replay magnets. Requirements:

- One-time nonce embedded in URL, consumed on first GET/POST
- Short TTL (15 minutes default)
- Step-up auth for high-risk actions even inside TTL
- POST-only mutations with CSRF token tied to nonce

```html
<!-- Anti-replay: form posts to consume nonce server-side -->
<form method="POST" action="/approvals/consume">
  <input type="hidden" name="nonce" value="{{nonce}}" />
  <input type="hidden" name="csrf" value="{{csrf}}" />
  <button type="submit">Approve deployment</button>
</form>
```

Never expose side effects on idempotent GET with lingering tokens in query strings—browser prefetch and email scanners will trigger them.

## MCP and JSON-RPC considerations

JSON-RPC `id` deduplication prevents duplicate responses within a connection; it does **not** protect cross-connection replay. MCP servers exposing paid tools should require:

- Transport-level auth (mTLS or bearer)
- Per-invocation signature or server-issued invocation ticket consumed at execution
- Audit log correlating `tool_name`, `ticket_id`, and `caller_identity`

Treat identical argument payloads as suspicious when ticket reuse fails—even if the LLM innocently repeats itself.

## Testing: red team checklist

| Test | Expected |
|------|----------|
| Replay identical webhook within skew window | Second rejected at nonce |
| Replay after skew window | Rejected at timestamp |
| Retry with same Idempotency-Key | Same response, one execution |
| Retry with new key, old nonce | Rejected |
| Parallel duplicate POSTs | One wins, one 409 |
| Approval link clicked twice | Second shows consumed state |

Automate these in CI against a dockerized agent gateway; regressions here are severity-1.

## Operational signals

Metrics worth dashboarding:

- `replay_rejected_total{reason="nonce|timestamp|sequence"}`
- Ratio of idempotent cache hits to total mutating requests ( sudden drop may mean client bug)
- Webhook verification failures by integration partner

Alert when rejection rate spikes 10× baseline—could be attack or partner clock drift.

## Choosing controls by risk tier

| Tier | Example tools | Minimum controls |
|------|---------------|------------------|
| Read-only | Search docs | Auth + rate limit |
| Spend credits | LLM call, embedding | Idempotency + auth |
| Irreversible | Payments, prod deploy | Signature + nonce + seq + approval |

Over-engineering read paths adds latency; under-engineering write paths adds incidents.

## Clock skew and distributed agents

Timestamp validation breaks when agent workers run on laptops with drifted clocks or edge nodes without NTP. Mitigations:

- Prefer server-issued timestamps inside signed envelopes rather than client `Date` headers
- Allow symmetric skew (±300s default) but log clients whose skew exceeds 60s for remediation
- For globally distributed orchestrators, sign with the auth service clock only—never merge timestamps from worker nodes

When skew rejects spike after daylight saving changes, suspect cron misconfiguration on integration partners before rotating secrets.

## Rate limiting as replay amplifier defense

Replay attacks often arrive in bursts. Combine nonce rejection with token-bucket limits per `(caller_ip, integration_id)`:

```python
async def guard_webhook(caller: str, limiter: RateLimiter) -> None:
    if not await limiter.allow(caller, max_per_minute=120):
        raise HTTPException(status_code=429, headers={"Retry-After": "60"})
```

429 responses must not leak whether failure was signature, nonce, or rate— attackers should not tune attacks from error text.

## Logging without enabling replay

Security logs tempt teams to store full request bodies. Hash bodies instead:

```python
body_digest = hashlib.sha256(raw_body).hexdigest()
logger.info("webhook_rejected", extra={"reason": "nonce", "body_sha256": body_digest})
```

Support can correlate with primary storage using digest lookup tables with 24-hour retention if needed.

## Agent orchestration frameworks

LangGraph, Temporal, and custom DAG runners retry failed nodes. Ensure workflow engines attach **stable idempotency keys derived from `(workflow_id, node_id, attempt)`** to downstream HTTP tools—not random UUIDs per retry attempt. Random keys defeat idempotent stores and make replay indistinguishable from legitimate retry storms in metrics.

Document which tools are safe at-least-once vs exactly-once in your tool registry; codegen idempotency headers for the latter category.

## Webhook partner onboarding

New integration partners ship replay-vulnerable payloads first; fix in production under fire. Onboarding checklist before production credentials:

- Partner implements monotonic `event_id` with 7-day dedupe store on your side
- Clock sync documented; skew test passes in sandbox
- Red team replay script included in partner certification
- Runbook exchange: who gets paged when `replay_rejected_total` spikes for their `integration_id`

Sandbox environments must use separate signing secrets—partners often point staging webhooks at prod URLs during testing, replaying captured staging payloads against production if secrets match.

## Resources

- [OWASP — Replay Attack](https://owasp.org/www-community/attacks/Replay_Attack) — threat overview and mitigation catalog
- [IETF draft on HTTP Message Signatures](https://datatracker.ietf.org/doc/draft-ietf-httpbis-message-signatures/) — standardized signing for webhook envelopes
- [Stripe — Idempotent requests](https://stripe.com/docs/api/idempotent_requests) — reference design for mutating API retry safety
- [Model Context Protocol specification](https://modelcontextprotocol.io/specification) — tool invocation semantics and transport security expectations
- [NIST SP 800-63B — Authentication and Lifecycle Management](https://pages.nist.gov/800-63-3/sp800-63b.html) — session and verifier lifecycle guidance applicable to agent approval flows
