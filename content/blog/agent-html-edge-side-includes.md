---
title: "AI Agents: Html Edge Side Includes"
slug: "agent-html-edge-side-includes"
description: "Use HTML Edge Side Includes to compose agent chat UIs—personalized shells at CDN edge, dynamic tool panels from origin, cache efficiency, and ESI security for LLM-powered pages."
datePublished: "2026-05-16"
dateModified: "2026-05-16"
tags: ["AI", "Agent", "Html"]
keywords: "agent, html, edge, side, includes, ai, production, engineering, architecture"
faq:
  - q: "What is ESI and why use it for agent UIs instead of full SSR or SPA?"
    a: "Edge Side Includes let a CDN assemble HTML from cacheable fragments. Agent chat shells (layout, CSS, static welcome copy) cache at edge while personalized session headers and tool status panels fetch from origin per request. You avoid shipping a heavy JS bundle for mostly-static marketing + chat chrome."
  - q: "Which CDNs support ESI for agent workloads?"
    a: "Fastly has native ESI. Akamai supports ESI with configuration. CloudFront does not support classic ESI—use Lambda@Edge fragment assembly or SSR frameworks instead. Verify your CDN before designing around include tags."
  - q: "How do you cache agent UI fragments without leaking one user's data to another?"
    a: "Mark only truly public fragments as cacheable (shared CSS, docs sidebar). Session-specific ESI fragments must carry Vary: Cookie or private cache directives, or use edge auth to inject user scope before include fetch. Never cache personalized tool results at edge without tenant-scoped cache keys."
  - q: "What are ESI security risks with AI agent pages?"
    a: "ESI injection if user input reaches include URLs—attackers can swap fragments. Strict allowlist include paths server-side, ignore client-supplied esi URLs, and treat origin ESI endpoints with the same auth as API routes. Agent prompt echoes in HTML need escaping before any edge assembly."
---
The agent product page loaded in 180ms from Singapore—except the signed-in chat header, which blocked on origin in Dublin for 900ms. Marketing wanted global CDN caching; engineering wanted personalized session state and live tool-connection badges. A full client-side React shell solved personalization but regressed LCP and shipped 400KB of JS for a page that was 85% static HTML.

HTML Edge Side Includes (ESI) split the page: cache the shell at the edge, pull dynamic fragments from origin at request time. For agent UIs—chat widgets embedded in docs, status dashboards with mostly-static chrome—ESI is an underused pattern that trades complexity at the CDN layer for faster first paint and lower origin load.

## ESI mechanics for agent pages

ESI is an XML-based markup interpreted by supporting CDNs. The edge server fetches the parent page, encounters include directives, sub-fetches fragments, merges, and returns assembled HTML.

```html
<!-- agent-chat-shell.html — cached at edge, TTL 3600 -->
<!DOCTYPE html>
<html lang="en">
<head>
  <title>Acme Agent — Documentation</title>
  <link rel="stylesheet" href="/static/agent-shell.css">
</head>
<body>
  <header>...</header>

  <!-- Personal fragment: session + tier badge -->
  <esi:include src="/esi/agent/session-header"
               onerror="continue"
               cache-control="private, max-age=0"/>

  <main id="chat-container">
    <esi:include src="/esi/agent/welcome-panel"
                 cache-control="max-age=300"/>
  </main>

  <!-- Tool connectivity strip — short TTL -->
  <esi:include src="/esi/agent/tool-status"
               cache-control="max-age=30"/>

  <script src="/static/agent-bootstrap.js" defer></script>
</body>
</html>
```

| Fragment | Cache policy | Content |
|----------|--------------|---------|
| Shell | 1 hour, shared | Layout, static nav, CSS |
| Session header | private, no-store | User name, plan tier, quota |
| Welcome panel | 5 min, language-keyed | Localized static copy + feature flags |
| Tool status | 30 sec | Connected integrations indicator |

The browser receives fully assembled HTML—no client-side layout shift from async header injection.

## Origin ESI endpoints

Expose small, fast HTML partials—not full JSON APIs unless your edge converts them:

```python
# origin/routes/esi.py
from flask import Blueprint, request, g

esi = Blueprint("esi", __name__)

ALLOWED_ESI_PATHS = {
    "/esi/agent/session-header",
    "/esi/agent/welcome-panel",
    "/esi/agent/tool-status",
}

@esi.before_request
def validate_esi_request():
    if request.path not in ALLOWED_ESI_PATHS:
        return "Forbidden", 403
    # CDN should pass authenticated identity via trusted header
    g.user = verify_edge_auth_header(request.headers.get("X-Edge-Auth"))

@esi.route("/esi/agent/session-header")
def session_header():
    user = g.user
    return f"""
    <div class="agent-session" data-user-id="{esc(user.id)}">
      <span class="tier">{esc(user.tier)}</span>
      <span class="quota">{user.remaining_tokens} tokens left</span>
    </div>
    """, 200, {"Content-Type": "text/html; charset=utf-8"}
```

Keep fragments tiny (< 2KB). ESI multiplies origin requests—one page view may trigger three sub-fetches.

## Fastly VCL configuration sketch

```vcl
# Fastly service snippet — enable ESI
sub vcl_fetch {
  if (beresp.http.Content-Type ~ "text/html") {
    set beresp.do_esi = true;
  }

  # Session fragments never enter shared cache
  if (req.url ~ "^/esi/agent/session-header") {
    set beresp.cacheable = false;
    return(deliver);
  }

  # Tool status: short TTL, vary by auth cookie
  if (req.url ~ "^/esi/agent/tool-status") {
    set beresp.ttl = 30s;
    set beresp.http.Vary = "Cookie";
  }
}
```

Test ESI assembly in staging with `Surrogate-Control` headers before enabling in production. Misconfigured `onerror` can silently drop security-critical fragments.

## Agent-specific composition patterns

**Docs + embedded chat** — documentation body caches aggressively; sidebar chat launcher includes session-aware "Continue conversation" link via ESI.

**Admin agent dashboard** — static grid layout at edge; each widget (`/esi/agent/widget/usage`, `/esi/agent/widget/errors`) includes independently with tier-appropriate TTL.

**Post-tool-run feedback strip** — after agent executes a tool, origin renders a small HTML partial users see on refresh; ESI pulls latest strip without invalidating entire dashboard cache.

```html
<esi:try>
  <esi:attempt>
    <esi:include src="/esi/agent/recent-tool-runs?limit=5"/>
  </esi:attempt>
  <esi:except>
    <!-- Degrade gracefully if origin slow -->
    <p class="muted">Activity temporarily unavailable</p>
  </esi:except>
</esi:try>
```

Use `esi:try` for non-critical fragments so edge pages survive origin blips—important when agent status depends on multiple backend checks.

## Caching strategy and cache keys

ESI without cache key discipline causes cross-user leakage—the classic personalized fragment cached and served to the wrong session.

Rules:

1. **Public fragments** — cache key: URL + `Accept-Language` only
2. **Authenticated fragments** — `private`, `Vary: Cookie`, or edge-generated cache key from JWT `sub` claim
3. **Never** put session IDs in ESI `src` query strings logged at CDN—prefer edge auth injection

```
Cache key for /esi/agent/session-header:
  hash(user_id from X-Edge-Auth) + fragment path
```

Coordinate TTL with agent state freshness. Tool status at 30s may show stale "connected" while webhook processing failed—pair with client-side websocket for real-time critical paths; ESI for approximate status is fine.

## Security: ESI injection and XSS

ESI injection occurs when attackers control the `src` attribute—classic attack against misconfigured parsers. Mitigations:

- Origin generates all include URLs; never reflect user input into `<esi:include src="...">`
- Allowlist fragment paths at CDN edge—reject unknown `/esi/*` patterns
- Escape all dynamic HTML in fragments; agent outputs may contain markdown→HTML conversion—sanitize before fragment render
- CSP nonces on shell scripts; fragments should not introduce inline scripts

Agent prompt injection that reaches HTML rendering is XSS. Treat ESI fragments with the same output encoding as main templates.

```typescript
// Bad — never do this
const esiSrc = `/esi/agent/custom?prompt=${userQuery}`;
// Good — server selects fragment from enum based on validated session state
const esiSrc = `/esi/agent/welcome-panel?locale=${validatedLocale}`;
```

## Performance measurement

Compare before/after ESI adoption:

| Metric | Target |
|--------|--------|
| TTFB (cached shell) | < 100ms at p95 globally |
| Origin ESI sub-requests | < 50ms p95 each |
| Total origin RPS reduction | 40–70% on agent landing pages |
| LCP | Improves when hero is in static shell |

Instrument fragment timings separately. One slow `/esi/agent/tool-status` blocks entire page assembly on some CDNs—set aggressive timeouts and `onerror="continue"`.

## When ESI is the wrong tool

Skip ESI if:

- Your CDN is CloudFront without a Lambda@Edge assembly layer
- Pages are highly dynamic end-to-end (pure chat transcript view)
- Team lacks CDN debugging expertise—ESI failures are opaque

Alternatives: **partial hydration** (React Server Components, Astro islands), **edge middleware** (Vercel, Cloudflare Workers) that stitch HTML without classic ESI syntax.

ESI shines when agent UIs are **mostly static composition with a few personalized holes**—marketing site plus chat chrome, docs plus session banner—not when every pixel depends on live LLM output.

## Migration path from SPA to ESI-composed agent shell

Teams rarely rewrite overnight. A practical sequence:

1. **Extract static shell** — move layout, nav, and marketing hero into server-rendered HTML served through CDN with long TTL.
2. **Identify personalization holes** — list DOM regions that require session data; convert each to an ESI include with explicit cache policy.
3. **Keep client hydration narrow** — `agent-bootstrap.js` mounts only the live chat stream component; everything else arrives in first HTML byte.
4. **Load test fragment endpoints** — ESI multiplies origin QPS by fragment count; capacity-plan before cutover Friday.

Run A/B tests comparing SPA vs. ESI shell on LCP and chat engagement. Most agent products see improved bounce rate on docs landing pages when the welcome copy renders immediately without waiting for JS bundle parse.

Monitor CDN cache hit ratio on the shell separately from fragment hit ratio. A shell miss forces full origin assembly; alert when shell hit rate drops below 95% in any PoP.

## The takeaway

HTML Edge Side Includes let agent products cache the boring 85% at the CDN while origin serves session headers, tool badges, and localized welcome copy on demand. Design fragment boundaries with strict cache keys, allowlist ESI paths, degrade gracefully on origin failure, and measure sub-fragment latency. Done well, global users see fast agent shells without shipping a monolithic SSR page or a heavyweight SPA for static chrome.

## Resources

- [Fastly ESI documentation](https://www.fastly.com/documentation/guides/full-site-delivery/edge-side-includes/)
- [Akamai ESI developer guide](https://techdocs.akamai.com/esi/docs)
- [WebPageTest — measure LCP with edge caching](https://www.webpagetest.org/)
- [OWASP ESI injection](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/07-Input_Validation_Testing/15-Testing_for_HTTP_Splitting_Smuggling)
- [Cloudflare Workers HTMLRewriter (ESI alternative)](https://developers.cloudflare.com/workers/runtime-apis/html-rewriter/)
