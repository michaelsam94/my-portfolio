---
title: "AI Agents: Oidc Discovery Caching"
slug: "agent-oidc-discovery-caching"
description: "Cache OpenID Provider discovery documents without stale JWKS disasters: TTL math, rotation handling, and fallback behavior for agent authentication gateways."
datePublished: "2025-12-31"
dateModified: "2025-12-31"
tags: ["AI", "Agent", "Oidc"]
keywords: "OIDC discovery document, JWKS caching, OpenID Connect metadata, agent authentication, stale-while-revalidate, HTTP cache-control"
faq:
  - q: "What is the minimum you must cache from /.well-known/openid-configuration?"
    a: "At minimum: issuer, authorization_endpoint, token_endpoint, jwks_uri, and supported signing algorithms. Agent gateways that only cache jwks_uri still hit the discovery endpoint on every cold start unless they persist the full document. Cache the JSON blob atomically so partial reads never serve a Frankenstein config."
  - q: "How long can JWKS safely be cached?"
    a: "Follow Cache-Control from the IdP when present; default to 15–60 minutes for JWKS with a stale-while-revalidate window equal to one TTL period. Never cache beyond the IdP's key rotation schedule without a background refresh job—Auth0, Okta, and Azure AD rotate on unpredictable cadences tied to admin action."
  - q: "Should agent pods fetch discovery directly or through a central auth service?"
    a: "Central auth service. Thousands of agent replicas hammering an IdP discovery endpoint triggers rate limits and creates N distinct cache states. One gateway cluster caches discovery and JWKS; pods receive already-validated signing keys via internal API or mounted JWKS snapshot refreshed by the gateway."
  - q: "What happens when cached keys are stale after an emergency IdP rotation?"
    a: "JWT signature verification fails with key-not-found. Implement negative-cache bypass: on kid miss, force-refresh JWKS synchronously once per minute per cluster, then retry verification. Page if forced refresh fails twice—likely IdP outage or network partition, not ordinary rotation."
---
Every agent pod that cold-starts and fetches `/.well-known/openid-configuration` adds latency and loads someone else's IdP. Multiply by autoscaling during a traffic spike and you get throttled—401s that look like "agent broken" but are really "cache missing." OIDC discovery caching is the unglamorous layer between your agent gateway and Azure AD that determines whether login survives Black Friday concurrency.

## Anatomy of what you are caching

OpenID Connect discovery returns JSON describing the provider:

```json
{
  "issuer": "https://login.example.com/",
  "authorization_endpoint": "https://login.example.com/oauth2/v2.0/authorize",
  "token_endpoint": "https://login.example.com/oauth2/v2.0/token",
  "jwks_uri": "https://login.example.com/oauth2/v2.0/discovery/v2.0/keys",
  "id_token_signing_alg_values_supported": ["RS256"],
  "response_types_supported": ["code"],
  "subject_types_supported": ["pairwise"]
}
```

JWKS at `jwks_uri` is a separate JSON document:

```json
{
  "keys": [
    {
      "kty": "RSA",
      "kid": "abc123",
      "use": "sig",
      "n": "...",
      "e": "AQAB"
    }
  ]
}
```

Your cache has two logical entries per issuer: **discovery** (low churn) and **jwks** (rotates). Treat them as a versioned pair keyed by `issuer` URL normalized to HTTPS without trailing slash inconsistencies.

## Why naive fetch-on-every-request fails

Agent gateways validate inbound JWTs from orchestrators and outbound tokens from tool OAuth. Each validation path needs the current signing key for `kid` in the JWT header.

Without cache:

- p99 auth latency includes DNS + TLS + IdP RTT on every request.
- IdP rate limits (`429`) surface as agent errors.
- Autoscaling creates thundering herds after deploys.

With overly aggressive cache:

- Emergency key rotation breaks all verification until TTL expires.
- Compromised JWKS served from cache extends attacker window.

The design target is **fresh enough, fast enough, fail visibly**.

## Cache layer architecture

```
Agent pod → Auth gateway → [Discovery cache] → IdP
                ↓
           [JWKS cache]
                ↓
         JWT verify (local)
```

Gateway exposes internal endpoint `/internal/jwks/{issuer}` for pods that cannot run HTTP cache logic—optional, but keeps verification libraries uniform.

Implementation sketch with stale-while-revalidate:

```typescript
interface CacheEntry<T> {
  value: T;
  fetchedAt: number;
  softExpiresAt: number;
  hardExpiresAt: number;
}

class OidcDiscoveryCache {
  constructor(
    private readonly fetcher: (url: string) => Promise<Response>,
    private readonly softTtlMs = 3600_000,   // 1 hour
    private readonly hardTtlMs = 7200_000,     // 2 hours SWR max
  ) {}

  private discovery = new Map<string, CacheEntry<OidcDiscovery>>();

  async getDiscovery(issuer: string): Promise<OidcDiscovery> {
    const key = normalizeIssuer(issuer);
    const hit = this.discovery.get(key);
    const now = Date.now();

    if (hit && now < hit.softExpiresAt) return hit.value;

    if (hit && now < hit.hardExpiresAt) {
      void this.refreshDiscovery(key).catch(() => {}); // background
      return hit.value;
    }

    return this.refreshDiscovery(key);
  }

  private async refreshDiscovery(issuer: string): Promise<OidcDiscovery> {
    const url = `${issuer}/.well-known/openid-configuration`;
    const res = await this.fetcher(url);
    if (!res.ok) throw new Error(`discovery fetch failed: ${res.status}`);
    const doc = (await res.json()) as OidcDiscovery;
    validateDiscovery(doc, issuer);
    const now = Date.now();
    this.discovery.set(issuer, {
      value: doc,
      fetchedAt: now,
      softExpiresAt: now + this.softTtlMs,
      hardExpiresAt: now + this.hardTtlMs,
    });
    return doc;
  }
}
```

Honor upstream `Cache-Control` when IdP sends it—many enterprise providers do not; your defaults apply.

## JWKS refresh on kid miss

Normal path: JWT arrives with `kid: abc123`. Local JWKS map has `abc123` → verify.

Rotation path: `kid` unknown. Trigger synchronous refresh once, not per request:

```typescript
async function verifyJwt(token: string, cache: JwksCache): Promise<Payload> {
  const header = decodeProtectedHeader(token);
  const issuer = normalizeIssuer(decodeJwt(token).iss!);

  let jwks = await cache.getJwks(issuer);
  let key = jwks.keys.find((k) => k.kid === header.kid);

  if (!key) {
    jwks = await cache.forceRefreshJwks(issuer);
    key = jwks.keys.find((k) => k.kid === header.kid);
  }

  if (!key) throw new AuthError("unknown_signing_key");
  return jwtVerify(token, await importJwk(key), { issuer });
}
```

Rate-limit `forceRefreshJwks` per issuer—one refresh per 60 seconds cluster-wide via distributed lock:

```typescript
async function forceRefreshJwks(issuer: string): Promise<Jwks> {
  const lock = await redis.set(`jwks:refresh:${issuer}`, "1", "NX", "EX", 60);
  if (!lock) {
    await sleep(200);
    return this.getJwks(issuer); // another instance refreshed
  }
  return this.refreshJwks(issuer);
}
```

## Validating discovery before trust

Never cache unvalidated JSON. Minimum checks:

```typescript
function validateDiscovery(doc: OidcDiscovery, expectedIssuer: string): void {
  if (normalizeIssuer(doc.issuer) !== normalizeIssuer(expectedIssuer)) {
    throw new Error("issuer mismatch — possible misconfiguration or MITM");
  }
  if (!doc.jwks_uri.startsWith("https://")) {
    throw new Error("jwks_uri must be HTTPS");
  }
  const allowedAlgs = doc.id_token_signing_alg_values_supported ?? [];
  if (!allowedAlgs.includes("RS256") && !allowedAlgs.includes("ES256")) {
    throw new Error("unsupported signing algorithms");
  }
}
```

Pin issuers in config—agent gateways should not accept arbitrary `iss` from tokens and then fetch discovery dynamically for unknown tenants without an allowlist.

## Multi-tenant agent platforms

Enterprise customers bring their own IdP. Store per-tenant issuer URL in tenant config; cache partition key is `(tenant_id, issuer)`.

```yaml
# tenant-acme-auth.yaml
tenantId: acme
oidc:
  issuer: https://acme.okta.com/oauth2/default
  clientId: ${OKTA_CLIENT_ID}
  discoverySoftTtl: 3600
  jwksSoftTtl: 900
```

Different TTLs per tenant when contracts require faster rotation detection. Never share cache entries across tenants—even identical issuer strings should include tenant ID in the key to prevent cache poisoning via misconfigured admin UI.

## Persistence across gateway restarts

In-memory caches cold-start empty. Options ranked:

1. **Redis backing store** — write-through on refresh; gateway reads Redis first.
2. **File snapshot on disk** — acceptable for single-replica gateways; watch permissions.
3. **Init container preload** — fetch discovery before accepting traffic in readiness probe.

Readiness gate:

```yaml
readinessProbe:
  httpGet:
    path: /readyz
    port: 8080
  initialDelaySeconds: 2
  periodSeconds: 5
```

`/readyz` returns 503 until discovery and JWKS for all configured issuers load successfully.

## Security considerations

- **HTTPS only** for discovery and JWKS fetch; pin nothing at TLS layer unless you operate corporate MITM—prefer standard CA validation.
- **Do not cache error responses** beyond a short negative TTL (30s) to avoid amplifying IdP outages into long self-inflicted ones.
- **Log cache age** on verification failures—`kid_miss` with `cache_age_seconds > 3600` implicates stale cache, not bad token.
- **Protect internal cache admin API** — force-refresh endpoints are DoS vectors if exposed.

## Observability

Metrics per issuer:

- `oidc_discovery_fetch_total{result}`
- `oidc_jwks_refresh_total{trigger=scheduled|kid_miss|forced}`
- `oidc_cache_age_seconds` gauge
- `jwt_verify_failures_total{reason=unknown_kid|expired|issuer_mismatch}`

Trace spans: `discovery.fetch`, `jwks.refresh`, `jwt.verify` as siblings so latency regressions show whether network or crypto dominates.

## Testing rotation without waiting for Okta

Use a local IdP (Keycloak, Dex) with admin API to rotate keys on demand:

```bash
# Keycloak example: create new RSA key, disable old after overlap window
kcadm.sh create components -r agents -s name=rsa-new -s providerId=rsa-generated ...
```

Integration test flow:

1. Fetch token signed with key A → verify OK.
2. Rotate to key B only.
3. Old token still verifies until exp (expected).
4. New token with kid B verifies after kid-miss refresh.
5. Remove key A; tokens with kid A fail.

Automate in CI with Testcontainers Keycloak.

## Operational runbook snippet

**Symptom:** Spike in `jwt_verify_failures{reason=unknown_kid}`

1. Check IdP status page.
2. Inspect `oidc_jwks_refresh_total` — did kid_miss trigger refresh?
3. If refresh errors, verify egress from gateway to `jwks_uri`.
4. Manual mitigator: `curl` JWKS URL, compare `kid` list to cache dump endpoint.
5. Force cluster-wide refresh via admin API once network confirmed healthy.

**Symptom:** Discovery fetch slow but JWKS fine

Discovery TTL can be longer—verify background refresh job runs and soft TTL is not set to zero in a recent config change.

## ETag and If-None-Match for bandwidth discipline

Some IdPs support conditional GET on discovery and JWKS endpoints. Pass through stored ETags on refresh:

```typescript
async function fetchWithEtag(url: string, etag?: string): Promise<{ status: 304 | 200; body?: unknown; etag?: string }> {
  const headers: Record<string, string> = {};
  if (etag) headers["If-None-Match"] = etag;
  const res = await fetch(url, { headers });
  if (res.status === 304) return { status: 304 };
  return { status: 200, body: await res.json(), etag: res.headers.get("etag") ?? undefined };
}
```

A `304 Not Modified` response skips JSON parsing and proves the cache is current—useful when soft TTL expires but content has not changed. Store ETag alongside cache entries; reset hard TTL only when body actually changes.

## Closing perspective

Discovery caching trades a few minutes of potential staleness for orders-of-magnitude fewer outbound calls and predictable auth latency. The implementation details—stale-while-revalidate, kid-miss refresh, issuer pinning—are what separate agent platforms that scale from those that mysteriously fail auth every time the IdP hiccups.

## Resources

- [OpenID Connect Discovery 1.0 specification](https://openid.net/specs/openid-connect-discovery-1_0.html)
- [RFC 7517 — JSON Web Key (JWK)](https://datatracker.ietf.org/doc/html/rfc7517)
- [RFC 7519 — JSON Web Token (JWT)](https://datatracker.ietf.org/doc/html/rfc7519)
- [Auth0 — signing key rotation](https://auth0.com/docs/secure/tokens/signing-keys/signing-key-rotation)
- [jose — JavaScript JWT/JWK library](https://github.com/panva/jose)
