---
title: "Same Site Cookie Policy"
slug: "llm-same-site-cookie-policy"
description: "SameSite=Lax broke our OAuth return flow; SameSite=None broke CSRF assumptions. A field guide to cookie policy for agent platforms with embedded widgets and cross-origin API calls for teams running LLM features in production."
datePublished: "2025-10-01"
dateModified: "2026-07-17"
tags:
  - "AI"
  - "LLM"
keywords: "SameSite cookie, Secure attribute, CSRF protection, OAuth cookie flow, cross-origin agent embedding, session cookie policy"
faq:
  - q: "Why did Chrome stop sending my session cookie after I set SameSite=Lax?"
    a: "SameSite=Lax sends cookies on top-level navigations (clicking a link) but blocks them on cross-site subresource requests and most POST navigations. If your agent UI loads in an iframe on a customer domain, or your API receives credentialed fetches from a different origin, Lax cookies will not attach. You need SameSite=None; Secure for cross-site credentialed requests — and you must accept the CSRF implications that come with it."
  - q: "When is SameSite=Strict the right default for agent session cookies?"
    a: "Strict when your agent console and API share one origin and users always navigate directly to your domain — internal admin tools, standalone SaaS dashboards. Strict blocks all cross-site cookie sends, which eliminates an entire class of CSRF but breaks OAuth/OIDC return flows unless you use a same-site redirect hop or store tokens differently for the callback leg."
  - q: "How do I debug SameSite issues without guessing?"
    a: "Open DevTools → Application → Cookies and check the SameSite column. In Network tab, inspect request headers — if Cookie is missing on a credentialed fetch, compare the request origin to the cookie's registrable domain. Chrome's Issues panel flags SameSite warnings. Reproduce with curl using -H 'Cookie: ...' to isolate server-side vs browser-side problems."
  - q: "Should agent refresh tokens use the same SameSite policy as access session cookies?"
    a: "Often no. Short-lived session cookies can be Strict or Lax on your primary origin. Refresh tokens, if stored in cookies at all, benefit from Strict plus Path=/auth/refresh and a separate cookie name — limiting exposure if XSS ever bypasses HttpOnly. Many teams move refresh tokens to HTTP-only Secure cookies on an auth subdomain while keeping access tokens in memory on the client."
---
The support ticket read: "Agent works in staging, blank screen in production." Staging lived at `staging.app.example.com`. Production embedded the agent widget inside `customer-crm.com` via iframe. The session cookie had `SameSite=Lax`. The browser correctly refused to send it on the cross-site iframe load. Auth returned 401. The widget rendered an empty state with no error message.

SameSite is not a security checkbox — it is a scoping rule that tells the browser which requests may carry which cookies. Get it wrong and authentication silently fails, CSRF defenses crumble, or OAuth callbacks loop forever. Agent platforms compound the problem because they mix embedded widgets, server-sent streaming, third-party tool callbacks, and long-lived sessions in one product surface.

## What SameSite actually controls

Before 2016, browsers sent cookies on nearly every request to a matching domain — including cross-site `<img>` tags and `fetch()` calls from attacker-controlled pages. CSRF attacks exploited this liberally.

The `SameSite` attribute restricts when a cookie attaches to outgoing requests based on the **site** (roughly the registrable domain) of the requesting context versus the cookie's site.

Three values matter in production:

| Value | Cross-site subresource (iframe, fetch, XHR) | Top-level GET navigation from external site | Top-level POST from external site |
|---|---|---|---|
| **Strict** | Blocked | Blocked | Blocked |
| **Lax** (browser default since Chrome 80) | Blocked | Sent | Blocked |
| **None** | Sent (requires `Secure`) | Sent | Sent |

`Secure` is mandatory when `SameSite=None`. Non-secure cookies with `None` are rejected by modern browsers.

`HttpOnly` is orthogonal — it prevents JavaScript from reading the cookie but does not change SameSite send behavior. You need both on session identifiers.

## The agent platform topology problem

Agent products rarely live on a single origin. Typical topology:

```
app.example.com          — Agent console (first-party)
api.example.com          — Agent API + streaming
embed.example.com        — Widget loader script
customer-site.com        — Partner page with embedded iframe
auth.example.com         — OIDC provider / token endpoint
```

Each arrow represents a context where cookies might need to flow — or must not.

**First-party console**: `SameSite=Lax` or `Strict` on session cookies works. Users navigate directly to your app. CSRF on state-changing POSTs still needs anti-CSRF tokens or double-submit cookies because Lax allows cookies on top-level GET navigations from external sites.

**Embedded iframe on partner domain**: Session cookies scoped to `example.com` will not be sent inside an iframe on `customer-site.com` unless they are `SameSite=None; Secure`. That opens credentialed cross-site requests — and CSRF on any endpoint that accepts cookie auth without additional proof.

**Credentialed API calls from a SPA on a different subdomain**: `app.example.com` calling `api.example.com` is same-site (both are `example.com`). Lax cookies attach. But `app.example.com` calling `api.otherproduct.com` is cross-site — they will not.

Draw your origin diagram before setting cookie attributes. The mistake in the opening incident was assuming staging topology matched production embedding.

## Setting cookies correctly at each layer

### Express / Node

```typescript
import session from "express-session";

app.use(
  session({
    name: "__Host-agent.sid",
    secret: process.env.SESSION_SECRET!,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      secure: true,
      sameSite: "lax", // console-only deployment
      maxAge: 8 * 60 * 60 * 1000,
      path: "/",
    },
  })
);

// Embedded widget auth — separate cookie with explicit cross-site policy
function setEmbedSessionCookie(res: Response, token: string): void {
  res.cookie("agent_embed", token, {
    httpOnly: true,
    secure: true,
    sameSite: "none", // required for iframe on partner origins
    maxAge: 60 * 60 * 1000,
    path: "/embed",
    domain: ".example.com", // shared across api + embed subdomains
  });
}
```

The `__Host-` prefix on the console session enforces `Secure`, `Path=/`, and no `Domain` attribute — binding the cookie to exactly `app.example.com`, not sibling subdomains. Embed cookies intentionally use a broader domain and different SameSite policy because their threat model and delivery context differ.

### Next.js App Router — Server Actions and middleware

```typescript
// middleware.ts — set policy per route class
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const isEmbedRoute = request.nextUrl.pathname.startsWith("/embed");

  if (isEmbedRoute) {
    // Embed routes expect cross-origin iframe parents
    response.headers.set(
      "Set-Cookie",
      serialize("agent_ctx", ctxToken, {
        httpOnly: true,
        secure: true,
        sameSite: "none",
        path: "/embed",
        maxAge: 3600,
      })
    );
  }
  return response;
}
```

Middleware runs at the edge — useful for setting cookies before SSR renders a page that will load inside a partner iframe.

### Reverse proxy (nginx)

```nginx
# Strip dangerous client-supplied Set-Cookie overrides
proxy_cookie_path / "/; Secure; HttpOnly; SameSite=Lax";

# Embed location block — different policy
location /embed/ {
    proxy_pass http://agent_backend;
    proxy_cookie_flags ~ secure samesite=none;
}
```

Proxy-level cookie rewriting is a migration tool when legacy backends emit bare `Set-Cookie` without SameSite. Prefer fixing the application, but nginx flags buy time during rollouts.

## OAuth, OIDC, and the Lax redirect exception

OAuth authorization code flows depend on cookies surviving a round trip: your app redirects to the IdP, the IdP redirects back with a code, your callback endpoint exchanges it for tokens.

With `SameSite=Strict`, the callback request from the IdP is cross-site — session cookies do not attach — and the callback handler cannot correlate state. Classic failure mode: "Invalid state parameter."

Mitigations:

1. **Same-site redirect hop**: IdP callback hits `auth.example.com/callback` (same site as cookie), which sets tokens and redirects to `app.example.com`.
2. **Lax on session cookie**: Top-level GET navigations from the IdP carry Lax cookies. This is why Lax became the browser default.
3. **Store OAuth state in sessionStorage** keyed by state parameter, not server session — trades CSRF surface for simpler cross-site behavior on the callback leg only.

For agent platforms integrating third-party tool OAuth (Google Calendar, Slack, GitHub), each provider callback URL must match the SameSite policy you chose for the correlating cookie.

## CSRF when you must use SameSite=None

Cross-site credentialed requests require `SameSite=None`. They also require explicit CSRF defense because cookies will attach to attacker-initiated requests.

Defense stack:

```typescript
// Double-submit: cookie + header must match
export function csrfMiddleware(req: Request, res: Response, next: NextFunction) {
  if (["POST", "PUT", "PATCH", "DELETE"].includes(req.method)) {
    const cookieToken = req.cookies["csrf"];
    const headerToken = req.headers["x-csrf-token"];
    if (!cookieToken || cookieToken !== headerToken) {
      return res.status(403).json({ error: "csrf_validation_failed" });
    }
  }
  next();
}
```

Prefer `Authorization: Bearer` tokens in headers for API calls from embedded widgets instead of cookie auth — headers are not sent automatically on cross-site requests, eliminating classic CSRF. If you must use cookies cross-site, pair them with CSRF tokens and Origin/Referer validation on mutating endpoints.

## Migration playbook: from broken defaults to explicit policy

**Phase 1 — Inventory.** Export all `Set-Cookie` headers from production responses. Classify each cookie: session, analytics, CSRF, embed, legacy. Note current SameSite, Domain, Path, Secure, HttpOnly.

**Phase 2 — Classify by delivery context.** Console-only cookies → Lax or Strict. Embed/API cross-origin cookies → None + Secure + CSRF. Analytics → consider removing; third-party analytics cookies are dying under privacy regulation anyway.

**Phase 3 — Staged rollout.** Ship cookie changes behind a feature flag that sets new attributes for internal users first. Monitor auth error rates, OAuth callback failures, and embed load success by partner origin.

**Phase 4 — Partner communication.** Embedded widget customers may need CSP frame-ancestors updates and documented allowed origins. Send them a checklist before you flip SameSite=None in production.

## Debugging checklist for auth failures after a cookie change

1. DevTools → Network → failing request → Request Headers → is `Cookie` present?
2. DevTools → Application → Cookies → verify SameSite, Secure, Domain, Path, Expires.
3. Compare request URL origin to cookie's site. Cross-site? Expect Lax/Strict cookies to be withheld.
4. Is the request inside an iframe? Third-party cookie phaseout in Safari/Firefox may block regardless of SameSite — test in each target browser.
5. Check for duplicate cookies with conflicting Domain scopes — browsers pick one unpredictably.
6. curl the endpoint with explicit `-H "Cookie: name=value"` to isolate browser policy from server bugs.

Log auth failures with `{ origin, cookiePresent: boolean, route, embed: boolean }` — not cookie values. Aggregate by partner origin to spot embed-specific regressions within minutes.

## Policy defaults worth documenting in your runbook

| Cookie | SameSite | Secure | HttpOnly | Path | Notes |
|---|---|---|---|---|---|
| Console session | Lax | yes | yes | / | __Host- prefix if single host |
| Embed session | None | yes | yes | /embed | Requires CSRF on mutations |
| CSRF token | Lax | yes | no | / | Readable by JS for header submit |
| Refresh token | Strict | yes | yes | /auth/refresh | Narrow path limits blast radius |

Document these in your security review template. When a new engineer adds a cookie for "just a quick experiment," they should find the table before copying Stack Overflow's `sameSite: 'lax'` into an embed route.

SameSite policy is where browser security models meet product topology. Agent platforms that embed across customer origins pay the complexity tax upfront — or pay it in silent auth failures and weekend incidents later.

## Resources

- [MDN — SameSite cookies explained](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie/SameSite) — Authoritative attribute semantics and browser behavior
- [web.dev — SameSite cookies explained](https://web.dev/articles/samesite-cookies-explained) — Practical guide with Lax/Strict/None examples
- [Chromium — SameSite cookie policy](https://www.chromium.org/administrators/policy-list-3/cookie-legacy-samesite-policies/) — Enterprise policy knobs and rollout timeline
- [OWASP — Cross-Site Request Forgery Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html) — CSRF defenses required when using SameSite=None
- [RFC 6265bis — Cookies: HTTP State Management Mechanism](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis) — Current draft standard for cookie attributes
