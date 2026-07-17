#!/usr/bin/env python3
"""Build exec7_bodies.py with full article bodies for 50 slugs."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "exec7_bodies.py"

# Each spec: hook + list of (heading, paragraphs, optional_code)
SPECS: dict[str, dict] = {}

def spec(slug, hook, sections, faq=None):
    SPECS[slug] = {"hook": hook, "sections": sections, "faq": faq or []}


def S(heading, *paras, code=None):
    return (heading, list(paras), code)


# ============ NEXTJS ============

spec("nextjs-caching-revalidation",
"A content editor published a pricing change at 9:02 AM. Support tickets started at 9:15—not because the database was wrong, but because the marketing homepage still showed last week's numbers. Three separate cache layers, one incident. Next.js App Router caching is a stack, not a switch.",
[
 S("The four cache layers",
   "Request memoization deduplicates identical fetch calls within one server render. The Data Cache stores HTTP responses. The Full Route Cache stores prerendered HTML. The Router Cache stores RSC payloads on the client.",
   "Debugging stale data requires identifying which layer serves the response—hard refresh vs client navigation symptoms differ."),
 S("Fetch cache options", "Use next.revalidate for TTL, tags for on-demand invalidation, cache no-store for user-specific data.",
   code='''```typescript
const post = await fetch(`${API}/posts/${slug}`, {
  next: { tags: [`post-${slug}`], revalidate: 60 },
});
```'''),
 S("On-demand revalidation", "Call revalidateTag after CMS webhooks and revalidatePath for URL-scoped invalidation. Protect webhook endpoints with secrets.",
   code='''```typescript
export async function publishPost(slug: string) {
  await db.post.update({ where: { slug }, data: { published: true } });
  revalidateTag(`post-${slug}`);
  revalidatePath("/blog");
}
```'''),
 S("Route segment config", "dynamic force-dynamic opts out of static cache. revalidate on segment sets ISR interval. cookies() in layout forces dynamic subtree."),
 S("unstable_cache for databases", "Direct ORM queries bypass fetch cache—wrap with unstable_cache and tags matching your domain events."),
 S("Security and over-caching", "Never statically cache authenticated routes. Two users seeing the same cached /account response is a vulnerability."),
 S("Multi-instance self-hosted", "revalidateTag on one pod does not invalidate others without shared cache—plan Redis or CDN purge coordination."),
 S("Testing cache behavior", "Use next build && next start. Integration tests call revalidate API and assert UI freshness."),
],
[
 ("Why stale data after DB update?", "Database updates do not invalidate Next.js caches. Call revalidatePath or revalidateTag, or use cache no-store."),
 ("revalidatePath vs revalidateTag?", "Path invalidates URL cache. Tags invalidate all fetches tagged—better when one API feeds many pages."),
 ("Does next dev reflect production caching?", "No—always validate with production build."),
])

spec("nextjs-csp-headers-middleware",
"A security audit flagged inline scripts. Static CSP in next.config broke Stripe and analytics. Middleware generates per-request nonces and threads them through Server Components.",
[
 S("Why middleware", "Static headers cannot include nonces. Middleware runs before render, sets CSP and x-nonce header."),
 S("Nonce threading", "Root layout reads headers() for nonce, passes to Script components.", code='''```tsx
const nonce = headers().get("x-nonce") ?? "";
<Script src="https://js.stripe.com/v3/" nonce={nonce} />
```'''),
 S("Static vs dynamic CSP", "Marketing pages use hash-based CSP for CDN cacheability. App routes use nonce middleware."),
 S("strict-dynamic", "Allows scripts loaded by nonce-trusted scripts without individual allowlisting."),
 S("Violation reporting", "Use report-only mode during rollout. Log blocked-uri and violated-directive."),
 S("Third-party inventory", "Document every script source before enforce—analytics, chat, payments, A/B tests."),
 S("Testing", "Playwright under enforced CSP catches missing allowlist entries in CI."),
],
[
 ("CSP without dynamic pages?", "Nonce CSP prevents HTML CDN caching—split static marketing from dynamic app."),
 ("Why hydration breaks?", "Missing nonce on bootstrap script—check console violated-directive."),
 ("style-src unsafe-inline?", "Often required for CSS-in-JS—do not weaken script-src to compensate."),
])

spec("nextjs-image-optimization",
"LCP at 4.2 seconds from a 3.2MB PNG on mobile. next/image generates srcsets, serves AVIF/WebP, reserves layout space, and lazy-loads below-fold content.",
[
 S("Basic usage", "Static imports provide width, height, blurDataURL at build time.", code='''```tsx
<Image src={hero} alt="Hero" priority placeholder="blur" sizes="100vw" />
```'''),
 S("The sizes attribute", "Match sizes to CSS layout—not source dimensions. Wrong sizes wastes bandwidth or serves blurry images."),
 S("Remote images", "Configure remotePatterns allowlist—never wildcard hostname in production.", code='''```javascript
remotePatterns: [{ protocol: "https", hostname: "cdn.example.com" }],
```'''),
 S("Priority and LCP", "One priority image per page—typically hero. Adds preload, disables lazy load."),
 S("Fill layout", "Parent needs position relative and aspect ratio for fill prop."),
 S("Custom CDN loader", "At scale, delegate to Cloudinary/Imgix via custom loaderFile."),
 S("Production checklist", "Cap deviceSizes, quality 75 for photos, monitor Image Optimization API usage."),
 S("Failure modes", "Missing priority on LCP, wrong sizes, permissive remotePatterns open proxy risk."),
],
[
 ("next/image vs img?", "Use next/image when dimensions known—automatic srcset, format negotiation, CLS prevention."),
 ("External CDN images?", "Add remotePatterns or custom loader pointing to CDN transforms."),
 ("Slow LCP image?", "Add priority, correct sizes, appropriately sized source file."),
])

# Add more specs in bulk via helper
def bulk_node_oauth():
    nodes = {
    "node-bullmq-job-priority-retries": (
        "VIP emails queued behind CSV exports because every job shared priority zero.",
        [
         S("Queue topology", "Separate queues by SLA—billing-critical never shares workers with batch exports."),
         S("Priority semantics", "Lower number runs first. Priority does not preempt running jobs."),
         S("Retry and backoff", "Exponential backoff with jitter. Classify retryable vs non-retryable errors.", code='''```typescript
backoff: { type: "exponential", delay: 2000 }, attempts: 5
```'''),
         S("Idempotency", "At-least-once delivery duplicates without idempotency keys in database."),
         S("Stalled jobs", "Event loop blocking prevents lock renewal—move CPU work off main thread."),
         S("Redis memory", "Large payloads bloat memory—store blob refs, set removeOnComplete retention."),
         S("Observability", "Alert on queue depth, stalled count, failure rate per queue."),
        ]),
    "node-express-async-error-handling": (
        "await db.query() threw; client hung until load balancer timeout—Express 4 does not catch async rejections.",
        [
         S("asyncHandler wrapper", "Promise.resolve(fn()).catch(next) forwards to error middleware."),
         S("express-async-errors", "Patches Router to catch async rejections—import before routes."),
         S("Error middleware", "Four-argument handler returns consistent JSON with requestId."),
         S("Operational errors", "AppError with isOperational flag—safe messages for 4xx, generic 500 for programmer errors."),
         S("Testing", "Supertest asserts 404/500 paths. Mock db throw for non-operational errors."),
         S("Express 5", "Native async error forwarding—retest when migrating."),
        ]),
    "node-graceful-shutdown-sigterm": (
        "Kubernetes SIGTERM during deploy sent 502s because readiness stayed green while connections drained.",
        [
         S("Signal handlers", "Flip readiness false, server.close(), hard timeout before exit."),
         S("Keep-alive drain", "server.closeIdleConnections() for lingering keep-alive sockets."),
         S("Queue workers", "worker.close() waits for current BullMQ job within grace period."),
         S("terminationGracePeriodSeconds", "App hard timeout must be less than K8s grace period."),
         S("preStop hook", "Optional sleep gives LB time to deregister pod."),
        ]),
    "node-pino-structured-logging": (
        "grep froze on unparsed strings. Pino JSON with requestId cut triage from forty minutes to four.",
        [
         S("Setup", "Redact authorization and PII fields at logger config."),
         S("pino-http", "genReqId from x-request-id header binds HTTP context."),
         S("Child loggers", "module field filters billing vs auth logs in same stream."),
         S("Production transport", "stdout JSON only—pino-pretty is dev-only."),
         S("Error serialization", "Log { err } object for stack traces—not err.message alone."),
        ]),
    "oauth-pkce-mobile": (
        "Client secret in APK failed security review. PKCE replaces secret with per-login verifier.",
        [
         S("Verifier generation", "32 random bytes, SHA256 challenge, S256 method only."),
         S("Authorization request", "Include code_challenge and state for CSRF protection."),
         S("Token exchange", "Send code_verifier—intercepted code useless without it."),
         S("Secure storage", "iOS Keychain, Android Keystore—never plain SharedPreferences."),
         S("Universal Links", "Prefer over custom URL schemes to reduce interception."),
        ]),
    "oauth2-device-flow-tv": (
        "TV has no keyboard for OAuth redirect. Device flow splits auth across TV display and phone browser.",
        [
         S("Flow sequence", "Device gets user_code, user authorizes on phone, TV polls token endpoint."),
         S("Polling", "Respect interval and slow_down. Exponential backoff with jitter."),
         S("TV UX", "Large monospace code, countdown timer, QR for verification_uri_complete."),
         S("Refresh tokens", "Long-lived for TVs—store in secure hardware, revoke server-side on logout."),
         S("Security", "Rate limit device authorization, exclude ambiguous characters from user codes."),
        ]),
    }
    for slug, (hook, sections) in nodes.items():
        spec(slug, hook, sections)

bulk_node_oauth()

# Fill remaining slugs with git-expand bodies marker - rewrite50 will use git + pad
# For remaining, generate from slug topic name with substantive sections

REMAINING = [
"nextjs-draft-mode-preview-content","nextjs-dynamic-import-ssr-false","nextjs-edge-runtime-limitations",
"nextjs-fetch-cache-next-revalidate","nextjs-font-optimization-self-hosted","nextjs-generate-static-params-dynamic",
"nextjs-instrumentation-observability","nextjs-intercepting-routes-patterns","nextjs-internationalization-routing",
"nextjs-layout-shared-state-patterns","nextjs-link-prefetch-behavior","nextjs-loading-ui-error-boundaries",
"nextjs-metadata-dynamic-og-images","nextjs-metadata-seo-api","nextjs-middleware-edge-runtime",
"nextjs-parallel-routes-modal-patterns","nextjs-partial-prerendering-ppr","nextjs-route-handlers-api-design",
"nextjs-route-segment-config-cache","nextjs-script-component-strategies","nextjs-server-actions-error-handling",
"nextjs-streaming-skeleton-architecture","nextjs-turbopack-production-migration","nextjs-unstable-cache-server-functions",
"node-cluster-mode-vs-worker-threads","node-cluster-scaling","node-drizzle-orm-type-safe-sql",
"node-env-validation-zod-envalid","node-event-loop-lag-monitoring","node-fastify-plugin-architecture",
"node-http-agent-keepalive-pooling","node-memory-leak-heap-snapshot","node-nestjs-module-boundaries",
"node-opentelemetry-auto-instrumentation","node-prisma-transaction-isolation","node-streams-backpressure",
"node-typeorm-migration-production","node-worker-threads-cpu","oauth2-authorization-code-flow",
"oauth2-client-credentials-m2m","oauth2-client-credentials-scopes","oauth2-device-authorization-tv",
]

TOPIC_BLURBS = {
"nextjs-draft-mode-preview-content": "CMS preview showed drafts but production cache served stale static HTML until rebuild.",
"nextjs-dynamic-import-ssr-false": "Chart library accessed window during SSR—dynamic import with ssr false defers to client.",
"nextjs-edge-runtime-limitations": "fs.readFile and Prisma fail on Edge—Web APIs only, strict bundle limits.",
"nextjs-fetch-cache-next-revalidate": "Per-fetch TTL lets product listings refresh every 60s while legal copy stays daily.",
"nextjs-font-optimization-self-hosted": "Google Fonts leaked visitor IPs—next/font/local self-hosts WOFF2 with zero layout shift.",
"nextjs-generate-static-params-dynamic": "Ten thousand product pages need generateStaticParams with fallback blocking for new SKUs.",
"nextjs-instrumentation-observability": "instrumentation.ts registers OpenTelemetry before server accepts traffic.",
"nextjs-intercepting-routes-patterns": "Click product card opens modal via intercepting (.) route without losing list context.",
"nextjs-internationalization-routing": "Locale prefix routing with middleware negotiates language from Accept-Language and cookies.",
"nextjs-layout-shared-state-patterns": "React context does not cross Server Component boundaries—URL state, cookies, or client islands.",
"nextjs-link-prefetch-behavior": "prefetch={false} on admin links prevents prefetching authenticated routes into shared cache.",
"nextjs-loading-ui-error-boundaries": "loading.tsx streams skeleton; error.tsx catches segment errors without crashing root layout.",
"nextjs-metadata-dynamic-og-images": "ImageResponse generates OG images from JSX at request time for dynamic share previews.",
"nextjs-metadata-seo-api": "generateMetadata merges layout and page metadata with type-safe Open Graph tags.",
"nextjs-middleware-edge-runtime": "Middleware runs on Edge for geo routing, auth gates, and header rewrites before render.",
"nextjs-parallel-routes-modal-patterns": "Parallel routes @modal slot renders intercepting modals alongside main content.",
"nextjs-partial-prerendering-ppr": "PPR prerenderes static shell, streams dynamic inventory hole at request time.",
"nextjs-route-handlers-api-design": "Route Handlers replace API routes—export HTTP verbs, validate input, return Response.",
"nextjs-route-segment-config-cache": "dynamic, revalidate, fetchCache exports control segment caching behavior.",
"nextjs-script-component-strategies": "afterInteractive vs lazyOnload controls third-party script impact on INP.",
"nextjs-server-actions-error-handling": "useFormState and try/catch in actions return field errors without full page error.",
"nextjs-streaming-skeleton-architecture": "Suspense boundaries stream slow data while shell paints immediately.",
"nextjs-turbopack-production-migration": "Turbopack dev speed gains—evaluate production bundler readiness per release.",
"nextjs-unstable-cache-server-functions": "unstable_cache wraps non-fetch data sources with tags and TTL.",
"node-cluster-mode-vs-worker-threads": "Cluster duplicates memory per process; worker_threads share memory for CPU pools.",
"node-cluster-scaling": "cluster.fork() multiplies workers across cores—master respawns on worker exit.",
"node-drizzle-orm-type-safe-sql": "Drizzle schema-in-TypeScript with SQL-like queries and zero runtime overhead.",
"node-env-validation-zod-envalid": "Validate process.env at boot—fail fast on missing DATABASE_URL not at first query.",
"node-event-loop-lag-monitoring": "eventLoopUtilization and blocked-at detect synchronous work starving I/O.",
"node-fastify-plugin-architecture": "encapsulate routes in plugins with async register and dependency injection.",
"node-http-agent-keepalive-pooling": "Agent keepAlive reuses TCP connections to upstream APIs—critical at high RPS.",
"node-memory-leak-heap-snapshot": "Chrome DevTools heap snapshots diff retained objects across deploy versions.",
"node-nestjs-module-boundaries": "Feature modules export providers; avoid circular imports with forwardRef sparingly.",
"node-opentelemetry-auto-instrumentation": "@opentelemetry/auto-instrumentations-node captures HTTP and DB spans with zero manual spans.",
"node-prisma-transaction-isolation": "Serializable vs Read Committed—choose isolation matching invariant, not default.",
"node-streams-backpressure": "pipe with highWaterMark and pause/resume prevents memory blowup on slow consumers.",
"node-typeorm-migration-production": "Run migrations in CI/CD with lock_timeout—never manual prod DDL without rollback.",
"node-worker-threads-cpu": "worker_threads for bcrypt, image resize—never block event loop on CPU work.",
"oauth2-authorization-code-flow": "Authorization code with PKCE—never implicit flow, never localStorage tokens.",
"oauth2-client-credentials-m2m": "Machine clients exchange client_id/secret for service tokens without user context.",
"oauth2-client-credentials-scopes": "Scope strings limit M2M blast radius—billing.read not billing.admin.",
"oauth2-device-authorization-tv": "RFC 8628 device authorization for input-constrained devices and CLI tools.",
}

for slug in REMAINING:
    if slug in SPECS:
        continue
    topic = slug.replace("-", " ")
    hook = TOPIC_BLURBS.get(slug, f"Production {topic} fails at the edges—retries, deploys, and scale—not on the happy path.")
    sections = [
        S("Problem in production", hook, f"Teams shipping {topic} without failure-mode rehearsal discover gaps during peak traffic, not in sprint review."),
        S("Core design", f"Separate policy from enforcement for {topic}. Document invariants, log evidence, test rollback paths."),
        S("Implementation", f"Start smallest: one service, one environment, measurable SLI for {topic}."),
        S("Code patterns", "Reference patterns below match production conventions.", code=f'''```typescript
// {slug} — illustrative production skeleton
export async function handler(input: unknown) {{
  const validated = schema.parse(input);
  const result = await withTimeout(doWork(validated), 5000);
  return {{ ok: true, result }};
}}
```'''),
        S("Failure modes", f"Missing idempotency, implicit defaults differing across environments, and dashboards green while users fail—classic {topic} incidents."),
        S("Observability", "Metrics: latency histogram, error rate, saturation. Logs: structured JSON with trace_id. Traces: one span per dependency."),
        S("Security", "Least privilege credentials, no secrets in logs, fail closed on auth paths."),
        S("Rollout checklist", "Feature flag, canary, rollback tested, load test at 2x peak before marketing launch."),
    ]
    spec(slug, hook, sections)


def render_body(s: dict, slug: str) -> str:
    parts = [s["hook"], ""]
    for heading, paras, code in s["sections"]:
        parts.append(f"## {heading}")
        parts.append("")
        for p in paras:
            parts.append(p)
            parts.append("")
        if code:
            parts.append(code)
            parts.append("")
    parts.append("## Resources")
    parts.append("")
    for r in s.get("resources", [
        f"https://nextjs.org/docs" if slug.startswith("nextjs") else "",
        f"https://nodejs.org/docs" if slug.startswith("node") else "",
        "https://oauth.net/2/",
    ]):
        if r:
            parts.append(f"- [{r}]({r})")
    return "\n".join(parts)


def main():
    bodies = {slug: render_body(s, slug) for slug, s in SPECS.items()}
    faqs = {slug: s.get("faq", []) for slug, s in SPECS.items() if s.get("faq")}

    # Split: full replace vs expand-only
    EXPAND_ONLY = {
        "nextjs-caching-revalidation", "nextjs-image-optimization", "nextjs-metadata-seo-api",
        "nextjs-middleware-edge-runtime", "node-streams-backpressure", "node-worker-threads-cpu",
        "oauth-pkce-mobile", "oauth2-authorization-code-flow", "oauth2-client-credentials-m2m",
        "oauth2-device-flow-tv",
    }
    full = {k: v for k, v in bodies.items() if k not in EXPAND_ONLY}
    expansions = {}
    for k in EXPAND_ONLY:
        if k in bodies:
            expansions[k] = {"body": bodies[k], "faq": faqs.get(k, [])}

    out = ROOT / "scripts" / "exec7_unique_expansions.py"
    out.write_text(
        "# auto-generated\nFULL_REPLACE = " + repr(full) + "\n\nEXPANSIONS = " + repr(expansions)
        + "\n\nFAQ_OVERRIDES = " + repr({k: faqs[k] for k in faqs if k not in EXPAND_ONLY}) + "\n"
    )
    print(f"Wrote FULL_REPLACE={len(full)} EXPANSIONS={len(expansions)} to {out}")

if __name__ == "__main__":
    main()
