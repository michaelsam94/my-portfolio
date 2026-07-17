---
title: "Content Security Policy with Nonces"
slug: "rag-content-security-policy-nonce"
description: "Deploy strict Content-Security-Policy with per-request nonces on agent chat UIs, streaming widgets, and third-party tool embeds without breaking inline hydration or dynamic script injection."
datePublished: "2025-10-05"
dateModified: "2026-07-17"
tags: ["AI Agents", "Security", "CSP", "Frontend"]
keywords: "content security policy nonce, CSP strict-dynamic, agent web UI, XSS prevention, nonce middleware, Next.js CSP"
faq:
  - q: "Why use nonces instead of hashes for agent chat UIs?"
    a: "Hashes work for static bundles but break when build IDs change every deploy and when frameworks inject inline bootstrap scripts. Nonces rotate per request, so SSR pages can emit fresh inline scripts safely without maintaining a hash allowlist across every release."
  - q: "Does strict-dynamic replace the need for host allowlists?"
    a: "Partially. strict-dynamic lets nonce-trusted scripts load other scripts dynamically, which helps agent widgets that lazy-load chart libraries. You still need explicit host sources for images, fonts, connect-src (LLM API endpoints), and frame-src if tools embed third-party iframes."
  - q: "How do nonces interact with streaming SSR and React hydration?"
    a: "Generate one nonce per HTTP response before the first byte. Pass it to the HTML shell, inline hydration payload, and any server-rendered script tags. Never reuse nonces across requests or cache HTML containing a nonce at CDN edges without stripping or regenerating it."
---

Your agent dashboard renders user markdown, streams tokens into a React island, lazy-loads a syntax highlighter, and calls three different API origins. Security wants `script-src 'self'` with no `'unsafe-inline'`. Product wants the chat widget shipped this sprint. **Content Security Policy nonces** are how you satisfy both: a cryptographically random token, issued once per response, that whitelists specific inline and dynamically loaded scripts while keeping the default deny posture everywhere else.

This is not academic hardening. Agent UIs are XSS magnets — retrieved documents, tool outputs, and model-generated HTML all arrive untrusted. A nonce-based CSP is the baseline for any production surface where the model or RAG pipeline can influence rendered content.

## How nonces fit a strict CSP

A CSP nonce is a base64 random string included in two places:

1. The `Content-Security-Policy` header: `script-src 'nonce-{value}' 'strict-dynamic'`
2. Every permitted `<script>` tag: `<script nonce="{value}">`

Browsers execute only scripts whose nonce matches the policy. Attack-injected `<script>` tags lack the nonce and are blocked.

For stacks, the typical policy skeleton looks like:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'nonce-{RANDOM}' 'strict-dynamic';
  style-src 'self' 'nonce-{RANDOM}';
  connect-src 'self' https://api.openai.com https://*.your-telemetry.com;
  img-src 'self' data: https:;
  frame-src 'self' https://sandbox.your-tools.com;
  object-src 'none';
  base-uri 'self';
  frame-ancestors 'none';
```

`'strict-dynamic'` is the critical addition for modern agent frontends. A nonce-trusted bootstrap script may load additional modules via `import()` or `document.createElement('script')` without listing every CDN host in `script-src`. That covers chart libraries, WASM runtimes, and code editors loaded after the user opens a tool result panel.

## Per-request generation and the caching trap

Nonces must be **unique per HTTP response**. The generation belongs in your edge middleware or SSR handler, before any HTML is flushed:

```typescript
// middleware/csp.ts
import { randomBytes } from "crypto";

export function createCspNonce(): string {
  return randomBytes(16).toString("base64");
}

export function buildCspHeader(nonce: string): string {
  const directives = [
    "default-src 'self'",
    `script-src 'nonce-${nonce}' 'strict-dynamic'`,
    `style-src 'self' 'nonce-${nonce}'`,
    "connect-src 'self' https://api.openai.com https://telemetry.example.com",
    "img-src 'self' data: https:",
    "frame-src 'self' https://sandbox.example.com",
    "object-src 'none'",
    "base-uri 'self'",
    "frame-ancestors 'none'",
    "report-uri /api/csp-report",
  ];
  return directives.join("; ");
}
```

Wire it into Next.js middleware or Express:

```typescript
// middleware.ts (Next.js App Router)
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { createCspNonce, buildCspHeader } from "./middleware/csp";

export function middleware(request: NextRequest) {
  const nonce = createCspNonce();
  const csp = buildCspHeader(nonce);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("Content-Security-Policy", csp);
  return response;
}
```

The failure mode that burns teams: **caching HTML with embedded nonces**. If your CDN serves a cached page, every user gets the same nonce — which weakens the model slightly — but worse, your SSR layer may generate a *different* nonce in the header than the one baked into cached body HTML. Scripts fail silently; the agent UI shows a blank panel. Rule: either disable HTML caching on authenticated agent routes, or use `Cache-Control: private, no-store` on responses that carry nonces.

## SSR, hydration, and streaming agent widgets

Agent chat interfaces almost always hydrate client-side after SSR. The inline bootstrap that calls `hydrateRoot` must carry the nonce:

```tsx
// app/layout.tsx
import { headers } from "next/headers";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const nonce = (await headers()).get("x-nonce") ?? "";

  return (
    <html lang="en">
      <body>
        {children}
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: `window.__AGENT_CONFIG__ = ${JSON.stringify({ streamEndpoint: "/api/chat" })}`,
          }}
        />
      </body>
    </html>
  );
}
```

For **streaming SSR** — common when the first token arrives before the full page shell completes — generate the nonce before opening the stream and pass it through your template context. Do not generate a second nonce mid-stream. Frameworks like React 19 streaming will flush early HTML chunks; each chunk's inline scripts must reference the same nonce issued at stream start.

Third-party agent widgets (embedded copilots, support bots) often ship as a `<script src="https://vendor.com/widget.js">` tag. With `'strict-dynamic'`, your nonce-trusted loader can inject the vendor script without adding `https://vendor.com` to `script-src`. Verify the vendor loader is itself nonce-tagged inline or loaded from `'self'`.

## Agent-specific CSP surfaces

### Markdown and tool output rendering

When agents render user or tool-provided markdown to HTML, you are one `<script>` tag away from XSS even with CSP — unless rendering is sanitized server-side. CSP is defense in depth, not a sanitizer. Pair nonce CSP with a strict allowlist sanitizer (DOMPurify with `USE_PROFILES: { html: true }` and no `ALLOW_UNKNOWN_PROTOCOLS`).

For inline styles in code blocks or highlighted snippets, either:

- Use `style-src 'nonce-...'` and tag generated `<style>` blocks, or
- Prefer CSS classes from your design system and forbid inline styles entirely

### connect-src for LLM and tool calls

Agent frontends call more origins than typical CRUD apps: model APIs, embedding endpoints, WebSocket streams, telemetry, and OAuth token refresh. Inventory every `fetch`, `EventSource`, and WebSocket URL, then encode them in `connect-src`. Missing entries produce console errors that look like "agent is broken" but are CSP blocks.

Use CSP violation reports to discover gaps:

```typescript
// app/api/csp-report/route.ts
export async function POST(request: Request) {
  const report = await request.json();
  console.warn("[CSP violation]", JSON.stringify(report["csp-report"]));
  // Ship to your observability stack — filter on blocked-uri
  return new Response(null, { status: 204 });
}
```

### frame-src for sandboxed tool execution

Agents that run code or render untrusted HTML in iframes need explicit `frame-src`. Use a dedicated sandbox origin (`sandbox.tools.example.com`) with its own tighter CSP. Never use `frame-src *` because a compromised tool iframe becomes a phishing surface.

## Report-only rollout strategy

Deploying strict CSP on a live agent product without a rehearsal breaks production. Start in **`Content-Security-Policy-Report-Only`** mode for two weeks:

1. Log violations to `/api/csp-report` tagged by route and tenant
2. Bucket violations by `violated-directive` and `blocked-uri`
3. Fix legitimate resources; investigate unexpected inline scripts
4. Flip to enforcing CSP on internal tenants first, then percentage rollout

Track a metric: **CSP violation rate per 1k sessions**. Spikes after deploy usually mean a new lazy-loaded bundle missed the nonce chain.

## Nonce vs hash vs unsafe-inline

| Approach | Agent UI fit | Ops burden |
|----------|-------------|------------|
| `'unsafe-inline'` | Works everywhere | No XSS protection from inline scripts |
| SHA-256 hashes | Static bundles only | Recompute hashes every build |
| Nonces | SSR + dynamic hydration | Per-request middleware, no CDN HTML cache |
| `'strict-dynamic'` + nonce | Lazy tool bundles | Requires modern browsers (2018+) |

Avoid `'unsafe-eval'` unless a specific tool (some notebook kernels) requires it. If unavoidable, isolate that tool on a separate subdomain with a narrower policy.

## Testing CSP in CI

Add automated checks so CSP regressions do not reach production:

```javascript
// tests/csp.test.ts
import { test, expect } from "@playwright/test";

test("agent chat page sends enforcing CSP with nonce", async ({ page }) => {
  const response = await page.goto("/agent/chat");
  const csp = response?.headers()["content-security-policy"] ?? "";
  expect(csp).toContain("script-src");
  expect(csp).not.toContain("unsafe-inline");
  expect(csp).toMatch(/'nonce-/);

  // Inline bootstrap present and nonce matches header
  const nonceMatch = csp.match(/'nonce-([^']+)'/);
  const nonce = nonceMatch?.[1];
  const inlineScript = page.locator(`script[nonce="${nonce}"]`);
  await expect(inlineScript.first()).toBeAttached();
});
```

Run Playwright against staging after every frontend deploy. Pair with a ZAP or CSP Evaluator scan for structural issues (overly broad `https:` in `img-src`, missing `object-src 'none'`, etc.).

## Common failure modes

**Nonce mismatch after edge middleware rewrite.** Some proxies strip or regenerate headers. Ensure the nonce travels on an internal header (`x-nonce`) from middleware to SSR, not by parsing the outbound CSP header in React.

**Third-party analytics outside strict-dynamic chain.** GTM snippets injected as standalone inline scripts need their own nonce or must load from a `'self'` proxy you control.

**Web Workers and blob URLs.** `worker-src` defaults to `script-src` in CSP Level 3. Agent code runners using `blob:` workers need `worker-src blob: 'self'` explicitly.

**Style nonces on dynamically inserted CSS.** If tool renderers inject `<style>` at runtime from client JS, those elements need the nonce attribute set in JavaScript — the nonce must be available on `window.__NONCE__` from your trusted bootstrap.

## The takeaway

CSP nonces let agent-powered web apps run strict `script-src` while keeping SSR hydration, streaming chat, and lazy-loaded tool widgets functional. The implementation is straightforward; the discipline is harder — one nonce per response, no cached HTML with stale nonces, report-only validation before enforcement, and `connect-src` kept in sync with every LLM and tool endpoint. Treat CSP as living configuration maintained alongside your API route map, not a one-time security ticket.

## Resources

- [MDN — Content-Security-Policy script-src](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/script-src)
- [W3C CSP Level 3 — strict-dynamic](https://www.w3.org/TR/CSP3/#strict-dynamic-usage)
- [Google — CSP Evaluator](https://csp-evaluator.withgoogle.com/)
- [Next.js — Content Security Policy guide](https://nextjs.org/docs/app/building-your-application/configuring/content-security-policy)
- [OWASP — Content Security Policy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
