---
title: "WAF and Bot Management for Agent APIs"
slug: "agent-waf-bot-management"
description: "Protect agent gateways from credential stuffing, prompt abuse, and scraper bots: WAF rules, rate limits, bot scores, JWT binding, and false positive tuning for streaming endpoints."
datePublished: "2025-05-13"
dateModified: "2026-07-17"
tags: ["AI Agents", "Security", "WAF", "API"]
keywords: "WAF agent API protection, bot management LLM gateway, rate limit agent endpoints, Cloudflare bot score"
faq:
  - q: "Why do standard WAF rules fail on agent streaming endpoints?"
    a: "SSE and WebSocket connections stay open for minutes with irregular byte patterns — rate-based WAF rules tuned for REST burst traffic false-positive as abuse. Exempt streaming paths from body-inspection rules; apply connection limits and JWT binding instead."
  - q: "How should rate limits differ for /chat vs /tools?"
    a: "/chat limits tokens-per-minute and concurrent streams per user. /tools limits invocations per tool class (expensive tools lower quota). Global IP limits catch scrapers; per-tenant limits catch credential abuse. Publish 429 with Retry-After."
  - q: "Can bot scores block headless agent clients?"
    a: "Legitimate automation (CI eval bots, enterprise integrations) should use API keys with elevated bot score thresholds — not browser cookie challenges. Separate API key tier from browser session tier in WAF policy."
  - q: "How do you tune false positives without opening prompt injection?"
    a: "Shadow mode new rules for 7 days — log would-block without blocking. Prompt injection rules belong at application layer with semantic filters; WAF handles volumetric abuse, geo anomalies, and known bad ASNs."
---

Your agent gateway publishes a `/v1/chat/completions`-style endpoint. Within a week, scrapers hammer it for free inference, credential stuffers test stolen passwords against `/login`, and someone's "research script" opens 500 parallel SSE streams. A **WAF with bot management** is the first line — but agent APIs break naive rule packs built for JSON request/response cycles under 200ms.

## Threat model at the agent edge

| Threat | Signal | Control layer |
|--------|--------|---------------|
| Credential stuffing | High `/auth` 401 rate, distributed IPs | WAF rate limit + MFA |
| LLM scraping | Sustained `/chat` from datacenter ASNs | Bot score + API key requirement |
| Prompt flooding | Large payloads, high RPM single token | Token bucket + max body size |
| Account takeover | JWT from new geo + high-value tool calls | Risk score + step-up auth |
| DDoS | Connection SYN flood | CDN L3/L4 + challenge |

Application-layer prompt injection detection stays **behind** authenticated gateway — WAF regex on prompts causes false positives and doesn't catch novel attacks.

## Rule topology

```
Internet
   │
   ▼
┌──────────────────┐
│ CDN + Bot Mgmt   │  ← bot score, JA3/JA4, ASN blocklists
└────────┬─────────┘
         ▼
┌──────────────────┐
│ WAF (OWASP CRS)  │  ← SQLi on metadata params, path traversal
└────────┬─────────┘
         ▼
┌──────────────────┐
│ Agent gateway    │  ← JWT, tenant quota, semantic moderation
└──────────────────┘
```

Split policies: `policy_browser` vs `policy_api_key`.

## Cloudflare-style bot score tiers

| Bot score | Client type | Action |
|-----------|-------------|--------|
| 1–29 | Likely automated abuse | Block or managed challenge |
| 30–49 | Suspicious | Rate limit 10 RPM |
| 50–79 | Mixed | Standard limits |
| 80–99 | Likely human/browser | Standard limits |
| API key header present | Bypass score challenge | Key-based quota only |

```javascript
// Cloudflare Workers snippet — API key bypass
export async function onRequest(context) {
  const key = context.request.headers.get("X-API-Key");
  if (key && await validateApiKey(key)) {
    return context.next(); // skip browser challenge
  }
  return context.next(); // bot fight mode applies
}
```

## Rate limiting schema

Redis sliding window per dimension:

```python
LIMITS = {
    ("user", "chat_stream"): (5, 60),      # 5 concurrent streams
    ("user", "tokens"): (100_000, 60),     # 100k tokens/min
    ("user", "tool_code_exec"): (10, 3600),
    ("ip", "auth_attempts"): (20, 300),
    ("tenant", "global_rpm"): (10_000, 60),
}

def check_limit(scope: str, key: str, metric: str) -> bool:
    max_val, window = LIMITS[(scope, metric)]
    return redis_sliding_window(f"rl:{scope}:{key}:{metric}", max_val, window)
```

Return structured 429:

```json
{
  "error": "rate_limit_exceeded",
  "metric": "tokens",
  "retry_after": 42,
  "limit": 100000,
  "window_seconds": 60
}
```

Agent SDKs must respect `Retry-After` — exponential backoff on streaming reconnect.

## Streaming endpoint exceptions

WAF rules to **avoid** on `/v1/chat/stream`:

- Full request body inspection on every chunk (N/A for SSE client POST body — single shot)
- Short idle timeout disconnects (<120s) — agent thinking pauses exceed this
- ModSecurity CRS rule 942100 on JSON body containing markdown code fences (false positive city)

Instead apply:

- Max connection duration (e.g., 30 min)
- Max concurrent connections per JWT (`jti` claim)
- Idle read timeout with client heartbeat ping

## JWT binding against token theft

Bind session to client fingerprint hash (lightweight, not fingerprinting users for ads):

```python
def issue_agent_jwt(user_id: str, client_ctx: str) -> str:
    return jwt.encode({
        "sub": user_id,
        "client_ctx_hash": hashlib.sha256(client_ctx.encode()).hexdigest()[:16],
        "exp": ... ,
    }, SECRET)

def verify_request(req):
    claims = jwt.decode(req.headers["Authorization"])
    if claims["client_ctx_hash"] != hash_client_ctx(req):
        raise AuthError("context_mismatch")  # stolen token reuse from new client
```

WAF logs `context_mismatch` spikes separately from brute force.

## False positive tuning workflow

1. Deploy rule in **log-only** mode.
2. Sample 1000 would-block events; classify true/false positive with security + PM.
3. Adjust threshold or add exclusion for known good user agents (mobile app version strings).
4. Enforce; monitor support tickets tagged `blocked_request`.

Track `waf_false_positive_rate` — target <0.1% of legitimate traffic.

## Prompt abuse vs WAF scope

Volumetric prompt spam (10MB system prompt repeats) — WAF `max_body_size 256kb` handles.

Semantic jailbreaks — **not WAF**. Gateway runs moderation classifier (see toxicity threshold post) post-auth.

## Observability

- `waf_block_total{rule_id, path}`
- `bot_score_histogram`
- `rate_limit_429_total{metric}`
- Correlation: block events → tenant → revenue tier (don't silently block enterprise)

## Resources

- [Cloudflare — Bot Management documentation](https://developers.cloudflare.com/bots/)
- [OWASP — API Security Top 10](https://owasp.org/www-project-api-security/)
- [AWS WAF — rate-based rules](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based.html)
- [IETF — RateLimit header fields draft](https://datatracker.ietf.org/doc/html/draft-ietf-httpapi-ratelimit-headers)

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

