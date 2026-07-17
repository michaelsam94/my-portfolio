---
title: "AI Agents: Api Key Scoping Tenants"
slug: "agent-api-key-scoping-tenants"
description: "Design tenant-bound API keys for multi-tenant agent platforms—scope matrices, prefix routing, rotation without cross-tenant bleed, and audit-friendly key lifecycle."
datePublished: "2026-01-11"
dateModified: "2026-01-11"
tags: ["AI", "Agent", "Api"]
keywords: "API key scoping, multi-tenant agents, tenant isolation, least privilege API keys, key rotation, agent platform security"
faq:
  - q: "Should each tenant get one API key or many scoped keys?"
    a: "Many scoped keys. One omnibus key per tenant simplifies onboarding but makes rotation a cliff and leaks full tenant access when a single integration is compromised. Issue keys per integration surface—embed widget, batch ETL, admin console—with explicit scope bundles and separate rate limits."
  - q: "How do you prevent a scoped key from accessing another tenant's data?"
    a: "Bind tenant_id at issuance time into the key record and enforce it in middleware before any handler runs. Never trust tenant_id from request body or query string when a key is present. Cross-check resource IDs against the key's tenant on every database query."
  - q: "What scopes matter most for agent API keys?"
    a: "Separate read vs write for conversations, tool invocation, file upload, embedding index, and billing. Agent run creation and tool execution should require distinct scopes so a read-only analytics key cannot trigger paid side effects."
  - q: "How often should tenant API keys rotate?"
    a: "User-facing keys: 90-day soft expiry with 14-day overlap. Service keys: 30 days with automated rotation via your secrets manager. Emergency revoke should propagate to edge caches within 60 seconds—measure this in game days, not assume it."
---
A partner pasted their production API key into a public Slack thread. Revoking it was easy. What took three hours was figuring out whether that key could read every tenant in our staging cluster because someone copied the "platform admin" scope template into the self-serve key generator. **Tenant scoping is not a column on the keys table—it is a enforcement chain that starts at the edge and ends at every row your agent touches.**

Multi-tenant agent platforms sit at an awkward intersection: customers want simple `Authorization: Bearer sk-...` ergonomics, while your security team wants per-integration least privilege, rotation, and provable isolation. This piece walks through how to design keys that survive real onboarding, real incidents, and real auditors.

## The key object model

Treat an API key as a credential **record**, not a random string. At minimum:

| Field | Purpose |
|-------|---------|
| `key_id` | Public prefix for logs (`sk_live_acme_7f3a`) |
| `secret_hash` | Argon2id or bcrypt of the full secret—never store plaintext after creation |
| `tenant_id` | Immutable binding set at creation |
| `scopes[]` | Machine-readable capability set |
| `environment` | `live` vs `test`—hard separation, no scope overlap |
| `rate_limit_tier` | Per-key throttle independent of tenant plan |
| `expires_at` | Soft expiry with grace window |
| `created_by` | User or service account for audit |

Scopes should be namespaced and composable:

```
agent:conversation:read
agent:conversation:write
agent:run:create
agent:tool:invoke
agent:file:upload
agent:embedding:query
billing:usage:read
```

Avoid `admin:*` wildcards in tenant-issued keys. Platform operators get a separate auth path—SSO with short-lived tokens—not the same key format customers use.

## Prefix routing and fail-closed middleware

Parse the key prefix before hitting your application database. Live keys starting with `sk_live_` route to production validators; test keys never touch production data stores even if someone misconfigures a connection string.

```typescript
import { createHash, timingSafeEqual } from "crypto";

type ApiKeyRecord = {
  keyId: string;
  tenantId: string;
  secretHash: string;
  scopes: Set<string>;
  environment: "live" | "test";
  revokedAt: Date | null;
};

export async function authenticateApiKey(
  authHeader: string | undefined,
  requiredScope: string
): Promise<{ tenantId: string; keyId: string }> {
  if (!authHeader?.startsWith("Bearer sk_")) {
    throw new AuthError("missing_or_malformed_key", 401);
  }

  const presented = authHeader.slice("Bearer ".length);
  const keyId = presented.slice(0, 24); // public prefix segment
  const record = await keyStore.findByKeyId(keyId);

  if (!record || record.revokedAt) {
    throw new AuthError("invalid_key", 401);
  }

  const hash = createHash("sha256").update(presented).digest();
  const stored = Buffer.from(record.secretHash, "base64");
  if (!timingSafeEqual(hash, stored)) {
    throw new AuthError("invalid_key", 401);
  }

  if (!record.scopes.has(requiredScope)) {
    throw new AuthError("insufficient_scope", 403);
  }

  return { tenantId: record.tenantId, keyId: record.keyId };
}
```

Attach `tenantId` and `keyId` to request context **before** routing to handlers. Handlers that accept `tenant_id` as a parameter should reject mismatches:

```typescript
export function assertTenantMatch(ctx: RequestContext, resourceTenantId: string) {
  if (ctx.tenantId !== resourceTenantId) {
    // Log as potential IDOR attempt; do not leak existence
    throw new AuthError("not_found", 404);
  }
}
```

Returning 404 instead of 403 for cross-tenant probes reduces oracle attacks where an attacker learns which resource IDs exist in other tenants.

## Scope bundles for common integrations

Ship curated bundles so customers do not hand-pick twelve scopes:

**Embed widget (browser-exposed proxy key):** `agent:conversation:read`, `agent:conversation:write`, `agent:run:create` — never `agent:tool:invoke` on a key that could be extracted from frontend JavaScript. Tool calls go through your server-side proxy with a different credential.

**Batch reindex pipeline:** `agent:file:upload`, `agent:embedding:write` — no conversation scopes. Rate limit aggressively; batch jobs should not share limits with interactive traffic.

**Analytics export:** `agent:conversation:read`, `billing:usage:read` — read-only, no run creation.

Document each bundle in your developer portal with a diagram showing which backend paths it can reach. Security reviewers and customers both benefit from the same artifact.

## Rotation without downtime

Rotation fails when teams treat it as "generate new key, delete old key, hope nobody cached the old one."

Better pattern:

1. Issue `key_v2` with identical scopes, 14-day overlap window.
2. Emit webhook `api_key.rotation_available` to tenant admin contacts.
3. Log usage by `key_id`—alert when `key_v1` still receives traffic after day 10.
4. Soft-revoke `key_v1` (returns 401 with `Retry-After` header pointing to docs).
5. Hard-delete `key_v1` secret hash after overlap ends.

For service-to-service keys your platform owns, automate via Vault or AWS Secrets Manager with dual-active secrets during rotation. Agent worker pools should hot-reload credentials on SIGHUP or file watch without draining in-flight runs.

```python
# Rotation job: never delete until traffic hits zero
async def finalize_rotation(old_key_id: str) -> None:
    stats = await metrics.daily_requests_by_key(old_key_id, days=7)
    if stats.total > 0:
        await alerts.send(
            f"Rotation blocked: {old_key_id} still has {stats.total} req/week"
        )
        return
    await key_store.hard_revoke(old_key_id)
```

## Rate limits and cost isolation per key

A misconfigured cron job with a tenant's main key can burn through LLM budget in minutes. Per-key rate limits decouple "tenant plan tier" from "this one integration went haywire."

Implement token bucket limits at the edge (Cloudflare, API gateway) **and** application-level quotas on `agent:run:create` and `agent:tool:invoke`. The edge stops floods; the app stops subtle spend drift.

Expose current utilization in the tenant dashboard: requests remaining, runs created today, estimated cost attribution by `key_id`. When a key hits 80% of its daily run quota, email the admin—before the invoice surprises them.

## Observability and audit

Every authenticated request should log structured fields:

```json
{
  "event": "api_request",
  "key_id": "sk_live_acme_7f3a",
  "tenant_id": "ten_acme_corp",
  "scope_used": "agent:run:create",
  "route": "POST /v1/runs",
  "latency_ms": 142,
  "outcome": "success"
}
```

Never log the full secret or prompt contents in the same stream as key metadata. Separate PII-adjacent audit logs with tighter retention and access controls.

Dashboards worth building:

- Top keys by request volume (detect leaked keys running hot)
- 401/403 rate by `key_id` (detect brute force or misconfigured clients)
- Cross-tenant rejection count (should be zero; any spike is an incident)
- Scope denial heatmap (product signal for missing bundles)

## Testing tenant isolation

Isolation bugs are silent until they are catastrophic. Add CI checks that cannot merge without passing:

**Contract tests:** Create two tenants, two keys. Tenant A's key must receive 404 for Tenant B's conversation IDs, not B's data.

**Property tests:** Random UUID resource IDs with Tenant A's key always return 404/403, never 200 with another tenant's payload.

**Chaos:** Rotate a key mid-integration-test; verify in-flight requests with old key fail cleanly and new key succeeds.

**Game day:** Revoke a production key used by your own dogfood tenant. Measure time-to-detection and time-to-mitigation.

## Migration from shared platform keys

Legacy setups often have one `PLATFORM_API_KEY` env var shared across services. Migration path:

1. Issue per-service keys with minimal scopes.
2. Deploy dual-auth middleware accepting both old shared key (deprecated) and new scoped keys.
3. Metric on shared key usage; block new services from receiving it.
4. Set hard cutoff date; remove shared key validation.

Do not skip step 2—teams discover mystery dependencies at cutoff otherwise.

## Closing thoughts

Tenant-scoped API keys are the front door to your agent platform. If the scoping model is vague, every downstream authorization check becomes a debate. If it is explicit—immutable tenant binding, composable scopes, per-key rate limits, rotation with overlap—your agents can grow features without growing blast radius.

Start by drawing the scope matrix on a whiteboard with your three most common integrations. Implement middleware before you add the fourth integration. Measure cross-tenant rejection rate in production; it should be a flat zero line.

## Resources

- [OWASP API Security Top 10 — Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)
- [Stripe API key best practices](https://stripe.com/docs/keys)
- [HashiCorp Vault — Dynamic Secrets](https://developer.hashicorp.com/vault/docs/secrets)
- [RFC 9700 — OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/rfc9700)
- [NIST SP 800-57 — Key Management Recommendations](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
