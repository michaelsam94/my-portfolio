---
title: "OAuth2 Token Introspection and Revocation"
slug: "oauth2-token-introspection-revocation"
description: "Use RFC 7662 introspection and RFC 7009 revocation correctly—when opaque tokens and immediate logout require more than JWT self-validation."
datePublished: "2026-01-17"
dateModified: "2026-07-17"
tags: ["Security", "OAuth", "Authentication", "Backend"]
keywords: "oauth2 token introspection, token revocation RFC 7009, opaque access tokens, RFC 7662"
faq:
  - q: "When should I use token introspection instead of local JWT validation?"
    a: "For opaque tokens or when you need real-time revocation after offboarding or stolen token response. JWT local validation cannot know a token was revoked until expiry without a blocklist."
  - q: "Does revocation invalidate access tokens immediately?"
    a: "RFC 7009 revokes refresh tokens; access token behavior depends on AS implementation. Pair revocation store with introspection or keep access TTL ≤ 5 minutes for sensitive scopes."
  - q: "Who may call the introspection endpoint?"
    a: "Only confidential resource servers with authenticated client credentials—never expose to browsers."
  - q: "How do I avoid introspection as a single point of failure?"
    a: "Cache active results briefly (30–60s), fail closed for high-risk APIs, scale introspection horizontally, prefer JWT with short TTL for read-heavy paths where delayed revocation is acceptable."
---

HR terminated an employee at 09:00. Their JWT still had 45 minutes of `exp`. The gateway validated signature locally. Introspection would have returned `"active": false` after sessions were revoked at 09:01.

## JWT vs introspection

Local JWT verify is fast but cannot know revocation unless `jti` blocklist or short TTL. Opaque tokens require introspection.

## RFC 7662

POST token to introspection endpoint; response includes `active`, `scope`, `sub`, `aud`, `exp`. Resource server rejects inactive like invalid bearer. Cache active results only with short TTL—never cache inactive=false long.

## RFC 7009 revocation

Revoke refresh or access tokens; AS returns 200 even if already invalid. Document whether access tokens die immediately or live until exp after refresh revocation.

## Pairing revocation with introspection

Revocation writes to store keyed by `jti`; introspection checks store before `active: true`. Push `jti` blocklist to gateways for JWT paths.

## Performance

20k RPS cannot introspect every request without cache. Circuit breaker: fail closed for admin routes. Alert on introspection p99 and error rate.

## Compliance drills

Quarterly: revoke test user, assert resource API rejects within TTL + cache window. Log `{actor, subject, jti, reason}` without token plaintext.

Introspection and revocation bridge "logout in the IdP" and "this access token stops working now"—implement with caching discipline and honest documentation of access token lifetime after logout.

## Multi-region introspection topology

Production authorization servers rarely run as a single pod. When introspection endpoints sit behind geo-routed load balancers, resource servers must not cache "active" across regions longer than revocation propagation time. Patterns that work:

**Central revocation store** — DynamoDB Global Table, Redis Cluster with cross-region replication, or PostgreSQL with logical replication. Introspection workers in each region read the same store; 30-second positive cache is safe if replication lag is monitored and stays under 5 seconds.

**Regional AS with async revocation fan-out** — Revoke in primary region; event bus replicates `jti` to secondaries. Resource servers in EU must not call US introspection on every request if latency matters—local regional introspection endpoint with shared store backend.

```yaml
# Resource server config sketch
introspection:
  endpoints:
    - url: https://as-eu.example.com/oauth/introspect
      region: eu-west-1
    - url: https://as-us.example.com/oauth/introspect
      region: us-east-1
  cache_ttl_active_seconds: 30
  cache_ttl_inactive_seconds: 0
  fail_closed: true
```

Alert when cross-region replication lag exceeds cache TTL—otherwise revoked tokens stay usable in one geography.

## Partner and machine-to-machine introspection

B2B APIs often accept tokens minted by a partner IdP. Two patterns:

**Local JWT validation** with JWKS from partner—fast, no introspection unless token is opaque.

**Delegated introspection** — your AS introspects partner token via RFC 7662 forward (non-standard but common in federations). Document latency budget; partner introspection outage becomes your outage unless cached JWKS path exists for JWT partners.

Machine clients using client credentials typically receive JWT access tokens you validate locally. Reserve introspection for opaque tokens from legacy AS products and for step-up revocation after credential rotation.

## Compliance and audit evidence

SOC2 and ISO audits ask: "When employment terminates, how fast does access end?" Your answer must cite:

- Revocation API called from HRIS webhook within N minutes
- Introspection `active: false` for all outstanding access token `jti`s
- Maximum access token TTL documented (e.g. 15 minutes)
- Logs retained: `{actor, subject, jti, reason, timestamp}` without storing token plaintext

Quarterly drill: revoke test user, assert resource API rejects within TTL + cache window. Save Grafana screenshot for auditors.

## Load testing introspection

Before Black Friday, load test resource servers at 2× peak with introspection enabled. Watch:

- p99 introspection latency vs p99 API latency (should stay <10% of total)
- Cache hit ratio on positive introspection (target >85% at steady state)
- AS introspection endpoint 429 rate—rate limits should scale with registered resource servers, not punish during legitimate traffic spikes

If introspection dominates latency, shorten access token TTL and widen cache carefully—not disable introspection on admin paths without explicit risk acceptance.

## Token introspection caching anti-patterns

**Negative caching inactive tokens** — Never cache `active: false` longer than zero. Attackers probing revoked tokens could theoretically trigger cache poisoning in poorly designed caches—always re-introspect or use zero TTL for inactive.

**Shared cache across environments** — Staging introspection responses cached in Redis instance also used by prod resource servers causes spectacular cross-environment auth bugs. Separate cache namespaces by `environment` label minimum.

**Logging introspection responses** — Full JSON includes `sub`, `scope`, sometimes `username`. Redact in log pipeline; log hash of token instead of token parameter.

## Federation logout cascades

OIDC back-channel logout notifies RPs when session ends. Pair with:

1. Revoke refresh tokens (RFC 7009)
2. Mark access token JTIs inactive
3. Introspection returns false within cache TTL

Test federated logout quarterly—partners depending on your introspection must see consistent `active` state within documented SLA (typically <60 seconds).

## Operational runbook

**Symptom:** Users report access after logout. **Check:** introspection cache TTL, revocation write lag, access token TTL. **Mitigate:** lower cache TTL temporarily, push emergency `jti` blocklist to gateways, force global session revoke in IdP admin.

**Symptom:** Introspection p99 spikes. **Check:** AS DB saturation, cache stampede after mass revocation. **Mitigate:** scale introspection pods, widen positive cache slightly with risk acceptance documented.

Never disable introspection on admin APIs during AS outages without explicit break-glass approval—fail closed beats silent continued access for privileged routes.
## Caching implementation sketch

```python
@lru_cache_with_ttl(ttl=30)
def introspect(token: str) -> IntrospectionResult:
    return httpx.post(INTROSPECT_URL, data={"token": token}, auth=RS_AUTH).json()
```

Never cache inactive responses. On AS timeout, fail closed for admin scopes; fail open for read-only public catalog only if product accepts stale reads—document explicitly.

## HRIS integration

Webhook from HRIS on termination → call revocation API for all refresh tokens for `sub` → enqueue access token `jti` blocklist → verify introspection returns inactive within SLA in automated test triggered by webhook in staging.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.

Validate with staging load tests and document rollback before enabling enforcement in production.
