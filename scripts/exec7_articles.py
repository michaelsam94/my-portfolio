#!/usr/bin/env python3
"""Topic-specific article content for exec7 rewrite batch."""
from __future__ import annotations

DATE_MOD = "2026-07-17"

# slug -> {title, description, tags, keywords, hook, sections, faq}
# sections: list of (heading, [paragraphs], optional_code)

TOPICS: dict[str, dict] = {}

def _t(slug, **kw):
    TOPICS[slug] = kw

# --- NEXTJS (26 remaining) ---

_t("nextjs-csp-headers-middleware",
   title="CSP Headers via Next.js Middleware",
   description="Set Content-Security-Policy in middleware — nonce threading to RSC, and static vs dynamic routes.",
   tags=["Next.js", "Security", "CSP"],
   keywords="Next.js CSP middleware, Content Security Policy Next.js, nonce middleware, strict-dynamic",
   hook="A security audit flagged inline scripts on your marketing site. You added a Content-Security-Policy header in next.config.js, and every page broke—Stripe checkout, Google Analytics, and your own hydration bundles all blocked. Middleware is where CSP belongs in the App Router: generate a per-request nonce, thread it through Server Components, and attach headers before HTML leaves the edge.",
   sections=[
     ("Why middleware beats next.config headers", [
       "Static CSP headers in next.config.js cannot include per-request nonces. Without nonces, you either allow unsafe-inline (defeating XSS protection) or block every inline script—including Next.js bootstrap code and third-party widgets that inject inline handlers.",
       "Middleware runs on every matched request before rendering. Generate cryptographically random nonce, store in request headers, and build CSP from a template. Server Components read the nonce via headers() and pass to next/script and any inline style blocks.",
     ], '''// middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const csp = [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic' https://js.stripe.com`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: https:",
    "frame-src https://js.stripe.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}'''),
     ("Threading nonce into the document", [
       "The root layout must read the nonce and apply it to Next.js Script components and any unavoidable inline scripts. In App Router, use headers() in the root layout—this opts the layout into dynamic rendering, which is acceptable for CSP.",
       "Report-only mode helps rollout: Content-Security-Policy-Report-Only sends violations to your collector without blocking. Run report-only for two weeks, fix violations, then enforce.",
     ], '''// app/layout.tsx
import { headers } from "next/headers";
import Script from "next/script";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = headers().get("x-nonce") ?? "";
  return (
    <html lang="en">
      <body>
        {children}
        <Script src="https://js.stripe.com/v3/" strategy="afterInteractive" nonce={nonce} />
      </body>
    </html>
  );
}'''),
     ("Static routes and CDN caching", [
       "CSP with per-request nonces makes HTML uncacheable at the CDN unless you vary on something unique—which defeats caching. Split your app: marketing pages with static CSP (hash-based allowlist for known scripts) vs authenticated app routes with nonce-based CSP in middleware.",
       "For static marketing pages, use script hashes instead of nonces. Compute SHA-256 of each allowed inline script at build time and embed in CSP. Next.js build output includes hashed chunks you can allow explicitly.",
     ]),
     ("Third-party script inventory", [
       "Before enforcing CSP, inventory every script source: analytics, chat widgets, A/B testing, payment providers, error tracking. Each needs an explicit allowlist entry or a nonce-capable loader. Document owners and renewal dates—abandoned vendors become CSP debt.",
       "strict-dynamic allows scripts loaded by nonce-trusted scripts to execute without individual allowlisting. This simplifies Stripe and similar loaders but requires your first script to carry the nonce correctly.",
     ]),
     ("Violation reporting and triage", [
       "Configure report-uri or report-to endpoint. Log blocked-uri, violated-directive, and document-uri. Dashboard weekly violation counts—spikes after deploys indicate missing allowlist entries.",
       "Common false positives: browser extensions injecting scripts (filter by source), stale service workers serving old HTML with wrong nonces, and preview environments missing middleware matcher config.",
     ]),
     ("Production rollout checklist", [
       "Start report-only on staging with production-like third parties enabled. Fix violations before enforce. Test checkout and auth flows under enforced CSP. Verify middleware matcher includes all HTML routes but excludes static assets and _next/image.",
     ]),
   ],
   faq=[
     ("Can I use CSP without making every page dynamic?", "Nonce-based CSP requires per-request HTML, which prevents static CDN caching of document responses. Use hash-based CSP for fully static marketing sites, and reserve nonce middleware for authenticated or personalized routes."),
     ("Why does my CSP break Next.js hydration?", "Missing nonce on the framework inline bootstrap script or blocking unsafe-eval when a dependency requires it. Check browser console for exact violated-directive. Often fixed by adding nonce to root layout and enabling strict-dynamic."),
     ("Should style-src allow unsafe-inline?", "Most apps need unsafe-inline for CSS-in-JS and Tailwind runtime in dev. Tighten style-src in production with hashed styles or move to static extraction. script-src is the XSS priority—do not weaken script-src to fix style violations."),
   ])

# Continue building remaining topics in generator below

def build_article(slug: str) -> str:
    t = TOPICS[slug]
    lines = [
        "---",
        f'title: "{t["title"]}"',
        f'slug: "{slug}"',
        f'description: "{t["description"]}"',
        f'datePublished: "{t.get("datePublished", "2025-08-25")}"',
        f'dateModified: "{DATE_MOD}"',
        "tags: " + str(t["tags"]).replace("'", '"'),
        f'keywords: "{t["keywords"]}"',
        "faq:",
    ]
    for q, a in t["faq"]:
        lines.append(f'  - q: "{q}"')
        lines.append(f'    a: "{a}"')
    lines.append("---")
    lines.append("")
    lines.append(t["hook"])
    lines.append("")
    for section in t["sections"]:
        heading, paras = section[0], section[1]
        code = section[2] if len(section) > 2 else None
        lines.append(f"## {heading}")
        lines.append("")
        for p in paras:
            lines.append(p)
            lines.append("")
        if code:
            lines.append(code)
            lines.append("")
    lines.append("## Resources")
    lines.append("")
    for r in t.get("resources", [
        "https://nextjs.org/docs/app/building-your-application/configuring/content-security-policy",
        "https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP",
        "https://web.dev/articles/strict-csp",
    ]):
        lines.append(f"- [{r}]({r})")
    return "\n".join(lines)

ARTICLES = {slug: build_article(slug) for slug in TOPICS}
