---
title: "Building on Cloudflare Workers"
slug: "edge-computing-cloudflare-workers"
description: "Deploy globally distributed logic on Cloudflare Workers: V8 isolates, fetch handlers, KV and D1 bindings, limits, and patterns for auth at the edge."
datePublished: "2025-11-16"
dateModified: "2025-11-16"
tags: ["DevOps", "Edge Computing", "Cloudflare", "Serverless"]
keywords: "Cloudflare Workers, edge computing, Workers KV, D1 database, V8 isolates, wrangler deploy, edge middleware, Cloudflare fetch handler"
faq:
  - q: "How is a Cloudflare Worker different from AWS Lambda?"
    a: "Workers run on V8 isolates at Cloudflare's edge PoPs worldwide, with cold starts measured in single-digit milliseconds and no regional function ARN. Lambda runs containerized functions in chosen AWS regions with fuller Node/Python runtimes but higher cold-start latency. Workers excel at HTTP middleware, routing, and lightweight transforms; Lambda fits heavier compute and deep AWS integration."
  - q: "What runtime APIs are available in Workers?"
    a: "Workers use the WinterCG subset: fetch, Request, Response, Headers, URL, crypto.subtle, and Web Streams. Node.js APIs require the nodejs_compat compatibility flag and still differ from full Node. No filesystem or native modules — design around fetch, bindings, and WASM."
  - q: "How do I store state in Workers?"
    a: "Use Workers KV for low-latency eventually consistent key-value reads, D1 for relational SQL at the edge, R2 for object storage, and Durable Objects for strongly consistent per-entity state with WebSocket hibernation. In-memory state in a Worker is not shared across requests or isolates."
---

The user in Sydney hits your API and the request bounces to us-east-1 before a JWT gets verified and a geolocation header applied. Three hundred milliseconds gone on physics alone. Cloudflare Workers run your JavaScript or WASM at the edge — in the same PoP that terminates TLS — so auth, A/B routing, and response rewriting happen before the origin sees traffic. Workers are not mini EC2 instances; they are V8 isolates that start in milliseconds and bill per request. That model changes what belongs at the edge versus in your core backend.

## Request lifecycle and fetch handler

Every Worker exports a default object with a `fetch` method:

```javascript
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === '/health') {
      return new Response('ok', { status: 200 });
    }

    const token = request.headers.get('Authorization');
    if (!token || !(await verifyJwt(token, env.JWT_SECRET))) {
      return new Response('Unauthorized', { status: 401 });
    }

    // Forward to origin with enriched headers
    const upstream = new Request(request);
    upstream.headers.set('X-Verified-Sub', claims.sub);
    return fetch(upstream);
  },
};
```

`env` carries bindings (secrets, KV namespaces, D1 databases). `ctx.waitUntil()` schedules background work — cache warming, analytics — without blocking the response.

## wrangler.toml and deployments

Wrangler is the CLI for develop and deploy:

```toml
name = "api-edge"
main = "src/index.js"
compatibility_date = "2025-11-01"

[vars]
ENVIRONMENT = "production"

[[kv_namespaces]]
binding = "CACHE"
id = "abc123..."

[[d1_databases]]
binding = "DB"
database_name = "edge-config"
database_id = "def456..."
```

```bash
npx wrangler dev          # local with Miniflare
npx wrangler deploy       # global rollout in seconds
npx wrangler secret put JWT_SECRET
```

Routes attach Workers to URL patterns in the Cloudflare dashboard or via wrangler routes configuration.

## Bindings: KV, D1, and R2

**Workers KV** — read-heavy config and cache. Writes propagate globally with eventual consistency; not for inventory counts.

```javascript
const cached = await env.CACHE.get(`route:${path}`, { type: 'json' });
if (cached) return Response.json(cached);
```

**D1** — SQLite at the edge for relational data that must be queryable with SQL:

```javascript
const { results } = await env.DB.prepare(
  'SELECT feature_flag FROM flags WHERE tenant_id = ?'
).bind(tenantId).all();
```

**R2** — S3-compatible object storage without egress fees to Workers.

Choose per access pattern. KV for "read config ten thousand times per write"; D1 when you need joins and transactions within SQLite limits.

## Limits that shape design

Workers enforce CPU time per request (typically 10–30 ms on free tiers, more on paid with unbound), memory caps, and subrequest limits. Heavy JSON transforms or ML inference may belong on origin or in a dedicated compute service. Profile with `wrangler tail` and Cloudflare analytics.

Do not stream unbounded bodies through Workers without backpressure awareness. Use TransformStream for large passthrough with size guards.

## Patterns that work at the edge

1. **Auth gateway** — validate JWT or session cookie; reject before origin load.
2. **Geo routing** — route EU users to EU origin via fetch subrequests.
3. **HTML edge includes** — personalize fragments from KV without SSR on origin.
4. **Rate limiting** — token bucket in Durable Objects or Cloudflare Rate Limiting rules plus Worker logic.

Avoid putting your primary database write path solely at the edge unless you understand D1 consistency and replication trade-offs.

## Local development and testing

`wrangler dev` uses Miniflare to simulate bindings locally. For integration tests, Vitest with `@cloudflare/vitest-pool-workers` runs tests inside the Workers runtime:

```javascript
import { env, createExecutionContext } from 'cloudflare:test';
import worker from '../src/index';

it('returns 401 without token', async () => {
  const req = new Request('https://example.com/api');
  const res = await worker.fetch(req, env, createExecutionContext());
  expect(res.status).toBe(401);
});
```

## Cold start and latency

Workers spin up in milliseconds globally, but first-request latency still matters for user-facing paths:

- **Keep handlers small** — tree-shake dependencies, avoid heavy polyfills
- **Warm critical paths** — Cron Triggers ping health endpoints every 5 minutes
- **Cache at edge** — `Cache API` with `cache.put()` for static fragments
- **Minimize subrequests** — each `fetch()` to origin adds RTT

Measure TTFB from multiple regions using Cloudflare's analytics or external synthetics. Edge wins evaporate if every request chains three origin fetches sequentially.

## Security model

Workers run in V8 isolates — not containers. Still treat them as production attack surface:

```javascript
export default {
  async fetch(request, env) {
    const token = request.headers.get('Authorization');
    if (!await verifyJwt(token, env.JWT_SECRET)) {
      return new Response('Unauthorized', { status: 401 });
    }
    // Never expose env secrets in responses or logs
  }
};
```

- Validate all input at the edge — don't pass malicious payloads to origin
- Use `env` bindings for secrets, never hardcode in script
- Enable WAF rules in front of Workers for DDoS and OWASP top 10
- Audit `fetch()` destinations — SSRF via user-controlled URLs is common

## Durable Objects for stateful edge

When KV's eventual consistency isn't enough, Durable Objects provide single-threaded state per ID:

```javascript
export class RateLimiter {
  constructor(state, env) { this.state = state; }
  async fetch(request) {
    // Single instance per user ID — safe counter increments
  }
}
```

Use for: collaborative editing sessions, WebSocket rooms, per-tenant rate limits, leader election. Don't use for bulk analytics — that's what origin databases are for.

Pair with [CDN caching strategies](https://blog.michaelsam94.com/cdn-caching-strategies-edge/) when Workers act as cache key normalizers in front of origin.

## Production checklist

- [ ] Secrets in `env` bindings only, never in script source
- [ ] JWT validated at edge before origin fetch
- [ ] CPU time profiled with `wrangler tail` under load
- [ ] Cron triggers warm critical paths in cold regions
- [ ] Durable Objects used only where KV consistency insufficient

## Resources

- [Cloudflare Workers documentation](https://developers.cloudflare.com/workers/)
- [Wrangler CLI reference](https://developers.cloudflare.com/workers/wrangler/)
- [Workers runtime APIs](https://developers.cloudflare.com/workers/runtime-apis/)
- [D1 SQLite at the edge](https://developers.cloudflare.com/d1/)
- [Cloudflare Workers limits](https://developers.cloudflare.com/workers/platform/limits/)
