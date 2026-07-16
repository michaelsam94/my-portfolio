---
title: "Next.js Middleware on the Edge"
slug: "nextjs-middleware-edge-runtime"
description: "Build Next.js middleware on the Edge Runtime: authentication gates, geo routing, A/B testing, header injection, and matcher configuration."
datePublished: "2025-09-03"
dateModified: "2025-09-03"
tags: ["Web", "Next.js", "Edge", "Security"]
keywords: "Next.js middleware, Edge Runtime Next.js, middleware matcher, authentication middleware Next.js, geo routing edge, Next.js edge functions"
faq:
  - q: "What can Next.js middleware do that route handlers cannot?"
    a: "Middleware runs before a request reaches any route handler or page. It can rewrite URLs, redirect, modify request/response headers, and set cookies globally. Use it for auth gates, geo routing, and bot detection that must apply across many routes without duplicating logic."
  - q: "Why is my middleware not running on API routes?"
    a: "Check your matcher config. The default matcher excludes _next/static, _next/image, and favicon.ico. If you explicitly set matcher, ensure /api/:path* is included. Middleware only runs on paths matching the matcher pattern."
  - q: "What are Edge Runtime limitations in middleware?"
    a: "Middleware runs on the Edge Runtime, which lacks Node.js APIs (fs, child_process, native modules). Use Web Crypto, fetch, and URL APIs. Database connections must go through HTTP-based clients or edge-compatible drivers like @vercel/postgres or Upstash Redis."
---

Every protected page duplicates the same auth check at the top. A new `/admin` route ships without it because someone copy-pasted the wrong template. Next.js middleware runs once per request before any page or API route executes—one file, one matcher config, consistent behavior across the app. It runs on the Edge Runtime, so it executes close to the user with sub-millisecond cold starts, but that speed comes with API restrictions.

## Basic structure

```typescript
// middleware.ts (project root)
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const token = request.cookies.get("session")?.value;

  if (!token && request.nextUrl.pathname.startsWith("/dashboard")) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/:path*"],
};
```

Place `middleware.ts` at the project root (or inside `src/`). Only one middleware file per project.

## Matcher patterns

```typescript
export const config = {
  matcher: [
    // All routes except static files and images
    "/((?!_next/static|_next/image|favicon.ico|public).*)",
    // Specific paths
    "/api/:path*",
    "/admin/:path*",
  ],
};
```

Negative lookahead excludes paths efficiently. Overly broad matchers run middleware on static assets—wasted edge invocations.

## Authentication pattern

```typescript
import { jwtVerify } from "jose";

const SECRET = new TextEncoder().encode(process.env.JWT_SECRET);

export async function middleware(request: NextRequest) {
  const token = request.cookies.get("token")?.value;
  const isProtected = request.nextUrl.pathname.startsWith("/app");

  if (!isProtected) return NextResponse.next();

  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  try {
    const { payload } = await jwtVerify(token, SECRET);
    const response = NextResponse.next();
    response.headers.set("x-user-id", payload.sub as string);
    return response;
  } catch {
    const response = NextResponse.redirect(new URL("/login", request.url));
    response.cookies.delete("token");
    return response;
  }
}
```

Use `jose` for JWT—it's Web Crypto based and works on Edge. Avoid `jsonwebtoken` (Node.js only).

## Geo routing

```typescript
export function middleware(request: NextRequest) {
  const country = request.geo?.country ?? "US";
  const url = request.nextUrl.clone();

  if (country === "DE" && !url.pathname.startsWith("/de")) {
    url.pathname = `/de${url.pathname}`;
    return NextResponse.rewrite(url);
  }

  return NextResponse.next();
}
```

`request.geo` is available on Vercel and compatible edge platforms. Rewrite, don't redirect, to keep the URL clean for the user.

## A/B testing

```typescript
export function middleware(request: NextRequest) {
  const bucket = request.cookies.get("ab-bucket")?.value;

  if (!bucket) {
    const newBucket = Math.random() < 0.5 ? "a" : "b";
    const response = NextResponse.next();
    response.cookies.set("ab-bucket", newBucket, { maxAge: 60 * 60 * 24 * 30 });
    response.headers.set("x-ab-bucket", newBucket);
    return response;
  }

  const response = NextResponse.next();
  response.headers.set("x-ab-bucket", bucket);
  return response;
}
```

Read `x-ab-bucket` in Server Components via `headers()` to render variant content.

## Response modification

```typescript
export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set(
    "Content-Security-Policy",
    "default-src 'self'; script-src 'self' 'unsafe-inline'"
  );

  return response;
}
```

Security headers in middleware apply to every matched route without touching individual pages.

## Rate limiting at the edge

```typescript
import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(100, "1 m"),
});

export async function middleware(request: NextRequest) {
  const ip = request.ip ?? "127.0.0.1";
  const { success, remaining } = await ratelimit.limit(ip);

  if (!success) {
    return NextResponse.json({ error: "Rate limited" }, { status: 429 });
  }

  const response = NextResponse.next();
  response.headers.set("X-RateLimit-Remaining", String(remaining));
  return response;
}
```

Edge-compatible Redis (Upstash) keeps rate limit state without Node.js TCP connections.

## Debugging

Middleware errors surface as 500s with minimal client detail. Log explicitly:

```typescript
export function middleware(request: NextRequest) {
  console.log(`[mw] ${request.method} ${request.nextUrl.pathname}`);
  // ...
}
```

Logs appear in your deployment platform's edge function logs, not the Node.js server log.

## Middleware matcher precision

```typescript
export const config = {
  matcher: ['/dashboard/:path*', '/api/protected/:path*'],
};
```

Over-broad `matcher: '/:path*'` runs middleware on static assets — adds latency to every `_next/static` request. Keep middleware under 25ms CPU budget on Vercel Edge.

## Common production mistakes

Teams get middleware edge runtime wrong in predictable ways:

- **Skipping failure-mode rehearsal** — run a game day or fault injection exercise before peak traffic, not after the first outage.
- **Missing correlation context** — every error path should carry request, trace, or tenant identifiers so incidents are debuggable.
- **Optimizing for demo, not steady state** — load tests, cache warm-up, and cold-start paths matter more than local dev latency.
- **Undocumented trade-offs** — if you chose speed over strict correctness (or vice versa), write that down for the next engineer.

Production implementations of middleware edge runtime fail when staging mirrors production topology poorly, rollback is untested, and on-call runbooks describe the happy path only.

## Debugging and triage workflow

When middleware edge runtime misbehaves in production, work top-down instead of guessing:

1. **Confirm scope** — one tenant, region, or deployment stage? Narrow blast radius before deep diving.
2. **Check recent changes** — deploys, flag flips, config pushes, and schema migrations in the last 24 hours.
3. **Compare golden signals** — latency, error rate, saturation, and traffic for the affected surface vs. baseline.
4. **Reproduce minimally** — smallest input or scenario that triggers the failure; capture traces/logs with correlation IDs.
5. **Fix forward or rollback** — if rollback is faster than root-cause during incident, rollback first, postmortem second.
6. **Add a guard** — alert, integration test, or circuit breaker so the same class of failure is caught earlier next time.

Document the timeline during triage. Future you (and on-call) will need timestamps, not just conclusions.

## Resources

- [Next.js Middleware docs](https://nextjs.org/docs/app/building-your-application/routing/middleware) — API and conventions
- [Edge Runtime supported APIs](https://nextjs.org/docs/app/api-reference/edge) — what works and what doesn't
- [matcher configuration](https://nextjs.org/docs/app/api-reference/file-conventions/middleware#matcher) — path pattern syntax
- [jose JWT library](https://github.com/panva/jose) — Edge-compatible JWT verification
- [Upstash rate limiting](https://upstash.com/docs/redis/sdks/ratelimit-ts/overview) — edge rate limiter
