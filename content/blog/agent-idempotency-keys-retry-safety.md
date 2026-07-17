---
title: "Idempotency Keys and Retry Safety for Agent APIs"
slug: "agent-idempotency-keys-retry-safety"
description: "Design idempotency keys for agent run creation, tool invocations, and billing webhooks—handle concurrent retries, payload mismatches, and TTL expiry without double-charging LLM workloads."
datePublished: "2024-10-28"
dateModified: "2024-10-28"
tags: ["AI Agents", "API Design", "Reliability", "Idempotency"]
keywords: "idempotency keys, retry safety, agent API, duplicate request prevention, Idempotency-Key header, LLM billing"
faq:
  - q: "Who generates idempotency keys for agent requests—client or server?"
    a: "Clients generate keys for user-initiated actions (start run, submit feedback, purchase credits). Servers generate keys for internal retries and async job replays. Never let the LLM invent keys; expose keys only through your SDK and HTTP headers, not prompt text."
  - q: "How long should idempotency records live?"
    a: "24–72 hours covers most client retry windows. Agent runs that span hours need TTL at least max_run_duration + retry_buffer. Document expiry behavior: after TTL, the same key may create a new run—clients must use fresh keys for intentionally new work."
  - q: "What HTTP status should duplicate in-flight requests return?"
    a: "Return 409 Conflict with the original request fingerprint when the same key arrives with a different body. Return 200/201 with the stored response when the same key and body retry while complete. Return 202 with Retry-After when the first request is still processing."
  - q: "Do idempotency keys apply to streaming agent responses?"
    a: "Keys guard the create/start mutation, not every SSE chunk. POST /v1/runs with Idempotency-Key creates at most one run; GET /v1/runs/{id}/stream is safe to reconnect without a key if the run_id is stable. Store run_id as the idempotent outcome."
---

Finance noticed duplicate charges on the same `run_id` before engineering did. The agent API accepted retries — mobile clients, gateway timeouts, impatient users double-tapping — and each retry spawned a **new OpenAI thread** because the handler checked idempotency **after** enqueueing work. The fix was not "disable retries." It was **idempotency keys** with atomic claim semantics, stored outcomes, and honest HTTP status codes.

Agent platforms are retry magnets. Runs take seconds to minutes. Clients use exponential backoff. Load balancers replay POSTs. Without idempotency, you double-bill, double-send emails, and double-invoke destructive tools.

## Idempotency scope for agent APIs

Apply keys to **mutations with side effects**, not reads:

| Endpoint | Idempotent? | Key source |
|----------|-------------|------------|
| `POST /v1/runs` | Yes | Client `Idempotency-Key` |
| `POST /v1/runs/{id}/cancel` | Yes | Client or derived from run_id |
| `POST /v1/tools/invoke` | Yes | Hash(run_id, tool, args_hash) |
| `POST /v1/billing/charge` | Yes | Required — PCI adjacent |
| `GET /v1/runs/{id}` | No | — |
| `GET /v1/runs/{id}/stream` | Reconnect only | run_id in URL |

Streaming is idempotent at the **resource** level once `run_id` exists. The key problem is creating two runs for one user intent.

## Header contract

Follow Stripe-style conventions — developers already understand them:

```
POST /v1/runs HTTP/1.1
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Content-Type: application/json

{"agent_id":"support-v2","input":{"ticket_id":"T-8821"}}
```

Server rules:

1. Keys are opaque strings, max 256 chars, UUID v4 recommended
2. Same key + same request body → same response (byte-stable JSON preferred)
3. Same key + different body → `409 Conflict`
4. Unknown key → process normally, store result
5. Keys scoped per **API key / tenant**, not global — prevent cross-tenant collision

## Storage schema

```sql
CREATE TABLE idempotency_records (
  tenant_id         TEXT NOT NULL,
  idempotency_key   TEXT NOT NULL,
  request_hash      TEXT NOT NULL,       -- SHA-256 of canonical body
  status            TEXT NOT NULL,       -- processing | completed | failed
  response_code     INT,
  response_body     JSONB,
  run_id            TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at      TIMESTAMPTZ,
  expires_at        TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (tenant_id, idempotency_key)
);

CREATE INDEX ON idempotency_records (expires_at) WHERE status = 'completed';
```

TTL index supports cleanup cron. **`processing`** status is the lock — only one worker may hold it.

## Atomic claim pattern

The race: two identical retries arrive before either completes. Only one may execute side effects:

```python
import hashlib
import json
from datetime import timedelta
from fastapi import HTTPException

def canonical_hash(body: dict) -> str:
    normalized = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode()).hexdigest()

async def claim_idempotency(
    tenant_id: str,
    key: str,
    body: dict,
    ttl_hours: int = 48,
) -> tuple[str, dict | None]:
    req_hash = canonical_hash(body)
    expires = now() + timedelta(hours=ttl_hours)

    row = await db.fetchrow(
        """
        INSERT INTO idempotency_records
          (tenant_id, idempotency_key, request_hash, status, expires_at)
        VALUES ($1, $2, $3, 'processing', $4)
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
        RETURNING status, request_hash, response_code, response_body, run_id
        """,
        tenant_id, key, req_hash, expires,
    )

    if row is not None:
        return "claimed", None  # this request owns execution

    existing = await db.fetchrow(
        """
        SELECT status, request_hash, response_code, response_body, run_id
        FROM idempotency_records
        WHERE tenant_id = $1 AND idempotency_key = $2 AND expires_at > now()
        """,
        tenant_id, key,
    )

    if existing is None:
        return "expired", None  # treat as new request — re-insert

    if existing["request_hash"] != req_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key reused with different request body",
        )

    if existing["status"] == "processing":
        return "in_progress", None

    return "replay", {
        "code": existing["response_code"],
        "body": existing["response_body"],
        "run_id": existing["run_id"],
    }
```

```python
@app.post("/v1/runs")
async def create_run(request: Request, body: CreateRunBody):
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise HTTPException(400, "Idempotency-Key required")

    state, cached = await claim_idempotency(tenant_id, key, body.dict())

    if state == "replay":
        return JSONResponse(cached["body"], status_code=cached["code"])

    if state == "in_progress":
        return JSONResponse(
            {"status": "processing", "retry_after_seconds": 2},
            status_code=202,
            headers={"Retry-After": "2"},
        )

    try:
        run = await execute_run(body)  # LLM + tools — expensive
        response = {"run_id": run.id, "status": run.status}
        await complete_idempotency(tenant_id, key, 201, response, run.id)
        return JSONResponse(response, status_code=201)
    except Exception as e:
        await fail_idempotency(tenant_id, key, str(e))
        raise
```

## Request handler middleware

Centralize in middleware so every team does not reimplement:

```typescript
// middleware/idempotency.ts
import { createHash } from "crypto";
import type { Request, Response, NextFunction } from "express";

export function idempotencyMiddleware(store: IdempotencyStore) {
  return async (req: Request, res: Response, next: NextFunction) => {
    if (req.method !== "POST") return next();

    const key = req.header("Idempotency-Key");
    if (!key) {
      res.status(400).json({ error: "Idempotency-Key header required" });
      return;
    }

    const tenantId = req.auth!.tenantId;
    const bodyHash = createHash("sha256")
      .update(JSON.stringify(req.body))
      .digest("hex");

    const claim = await store.claim({ tenantId, key, bodyHash });

    if (claim.status === "replay") {
      res.status(claim.responseCode).json(claim.responseBody);
      return;
    }
    if (claim.status === "in_progress") {
      res.status(202).set("Retry-After", "2").json({ status: "processing" });
      return;
    }
    if (claim.status === "conflict") {
      res.status(409).json({ error: "Key reused with different payload" });
      return;
    }

    // Capture response for storage
    const originalJson = res.json.bind(res);
    res.json = (body: unknown) => {
      store.complete({ tenantId, key, code: res.statusCode, body }).catch(console.error);
      return originalJson(body);
    };

    next();
  };
}
```

Apply only to routes registered in an idempotency allowlist — do not break webhooks that use signature auth instead.

## Tool invocation idempotency

Internal tool calls retry inside the run worker. Derive keys server-side:

```python
def tool_idempotency_key(run_id: str, tool_name: str, arguments: dict) -> str:
    material = f"{run_id}|{tool_name}|{canonical_hash(arguments)}"
    return hashlib.sha256(material.encode()).hexdigest()
```

Before calling a payment API or sending email:

```python
key = tool_idempotency_key(run.id, "send_refund_email", args)
if await idempotency_seen(key):
    return cached_tool_result(key)
result = await send_email(args)
await idempotency_store(key, result)
```

This layer protects against **worker retries** even when the client behaved correctly.

## Client SDK guidance

Document retry rules in the SDK — humans will not read RFCs:

```typescript
// sdk/agent-client.ts
export async function createRun(
  client: AgentClient,
  input: CreateRunInput,
  options?: { idempotencyKey?: string }
): Promise<Run> {
  const key = options?.idempotencyKey ?? crypto.randomUUID();

  for (let attempt = 0; attempt < 5; attempt++) {
    const res = await client.post("/v1/runs", input, {
      headers: { "Idempotency-Key": key },
    });

    if (res.status === 202) {
      await sleep(parseRetryAfter(res.headers.get("Retry-After")) ?? 2000);
      continue;
    }

    if (res.ok) return res.json();
    if (res.status === 409) throw new IdempotencyConflictError(await res.json());
    throw new AgentApiError(res.status, await res.text());
  }

  throw new Error("Run creation timed out after retries");
}
```

**Same key across retries** — never regenerate per attempt. New user action → new key.

## Failure and crash recovery

If the worker dies after LLM spend but before `complete_idempotency`:

- Record stays `processing`
- Retries get `202 Retry-After`
- Sweeper job reconciles stale `processing` rows older than N minutes:

```sql
-- Find orphaned processing records
SELECT tenant_id, idempotency_key, run_id, created_at
FROM idempotency_records
WHERE status = 'processing'
  AND created_at < now() - interval '15 minutes';
```

Sweeper checks if `run_id` was actually created in the runs table. If yes, backfill completed response. If no, mark failed and allow client retry with same key to proceed. This is operational glue most tutorials skip.

## Metrics and alerts

Track:

- `idempotency.replay_total` — healthy on retry-heavy clients
- `idempotency.conflict_total` — bug or malicious reuse; alert if spikes
- `idempotency.stale_processing` — sweeper findings; indicates crash window
- `idempotency.expired_new_run` — client reused old key after TTL

Dashboard replay rate against 202 rate. High 202 without eventual replay means clients gave up — user sees stuck UI.

## Security considerations

Idempotency keys are not auth. Validate API key first. Rate-limit key **creation**, not replay lookups. Do not echo stored response bodies to a different authenticated principal — tenant scoping is mandatory.

Avoid predictable keys (`ticket_id` alone). Combine with tenant and operation: `sha256(tenant + operation + client_request_id)`.

## The takeaway

Idempotency keys make agent APIs safe under retries: atomic claim, request body fingerprinting, stored outcomes, and 202 while in-flight. Require keys on run creation and billing, derive keys for internal tool retries, run a sweeper for crashed workers, and ship SDKs that reuse one key per logical user action. Double LLM charges and duplicate side effects are optional failures — idempotency is the default fix.

## Resources

- [Stripe — Idempotent requests guide](https://stripe.com/docs/api/idempotent_requests)
- [IETF draft — The Idempotency-Key HTTP Header Field](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-idempotency-key-header)
- [PayPal — Idempotency best practices](https://developer.paypal.com/api/rest/reference/info-security.html)
- [AWS — Exponential backoff and jitter](https://aws.amazon.com/builders-library/exponential-backoff-and-jitter/)
- [Google Cloud — Idempotent operations pattern](https://cloud.google.com/storage/docs/retry-strategy#idempotency)
