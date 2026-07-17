---
title: "HTTP Security Headers Hardening"
slug: "security-headers-hardening"
description: "Harden HTTP responses with security headers: CSP, HSTS, frame options, and middleware configs that survive real applications."
datePublished: "2025-07-06"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "HTTP security headers, Content-Security-Policy, HSTS, X-Frame-Options, security headers middleware, Helmet.js, CSP nonce"
faq:
  - q: "Non-negotiable headers?"
    a: "HSTS, CSP, X-Content-Type-Options, frame-ancestors, Referrer-Policy, Permissions-Policy."
  - q: "Roll out CSP safely?"
    a: "Report-Only first, fix violations, then enforce."
  - q: "Does HSTS replace redirects?"
    a: "No — redirects protect first visit; HSTS pins HTTPS on return visits."
---

Security headers earned a compliance checkbox while Content-Security-Policy stayed at `default-src *` and our admin console loaded inside a phishing iframe. Headers do not patch SQL injection, but they shrink blast radius when other bugs exist: reflected XSS cannot exfiltrate if script-src blocks the attacker domain; session cookies resist sslstrip when HSTS is pinned.

I hardened headers on a payments app where marketing added analytics scripts without telling engineering. Security headers are a living contract between your application and every third-party script on the page—not a one-time nginx paste.

## Baseline response shape

Every HTML response from authenticated and public routes should carry a coherent set:

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-…' https://js.stripe.com; ...
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-site
```

Prefer `frame-ancestors 'none'` inside CSP over legacy `X-Frame-Options: DENY` where both apply—CSP frame-ancestors wins in modern browsers and covers nested contexts more predictably.

## Content-Security-Policy as inventory

Most CSP breakage is missing inventory, not cryptography. Before writing directives, export every script, style, font, connect, and frame origin from production HAR captures across checkout, dashboard, and marketing pages. Stripe, Intercom, Segment, and PDF viewers each need explicit entries.

Roll out in report-only mode:

```http
Content-Security-Policy-Report-Only: default-src 'self'; report-uri /csp-report; report-to csp-endpoint
```

Aggregate reports in Sentry or a dedicated collector. Group by `blocked-uri` and `violated-directive`. Fix the top five offenders weekly until the violation rate flatlines.

### Nonces versus hashes

Dynamic HTML with inline bootstraps needs per-request nonces:

```html
<script nonce="rAnd0mPerRequest">window.__CONFIG__ = …</script>
```

```javascript
// Express middleware sketch
app.use((req, res, next) => {
  res.locals.cspNonce = crypto.randomBytes(16).toString("base64");
  next();
});
```

Static inline snippets in emailed templates may use hash-based CSP (`'sha256-…'`) instead. Never mix `'unsafe-inline'` in enforcing policy unless you have a dated migration plan—marketing "just this once" becomes permanent.

## HSTS staging strategy

Jumping straight to one-year HSTS with includeSubDomains bricks internal HTTP-only tooling. Stage deliberately:

| Stage | max-age | Purpose |
| --- | --- | --- |
| Pilot | 300 | Detect mixed content quickly |
| Stable | 86400 | One day soak |
| Production | 31536000 | Long-term pin |
| Preload | + preload directive | Browser list inclusion |

Verify every subdomain—including legacy `staging`, `assets`, and partner CNAMEs—before includeSubDomains. Preload is difficult to undo; treat submission as irreversible.

## Middleware configuration examples

Helmet centralizes defaults but still requires tuning:

```javascript
import helmet from "helmet";

app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'", (req, res) => `'nonce-${res.locals.cspNonce}'`, "https://js.stripe.com"],
        connectSrc: ["'self'", "https://api.stripe.com"],
        imgSrc: ["'self'", "data:", "https:"],
        frameSrc: ["https://js.stripe.com"],
      },
    },
    hsts: { maxAge: 31536000, includeSubDomains: true, preload: false },
    referrerPolicy: { policy: "strict-origin-when-cross-origin" },
  })
);
```

In nginx, `add_header … always` ensures headers appear on 404 and 502 responses attackers probe:

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
```

CDN layers may strip or duplicate headers—test through the full edge path, not origin alone.

## Clickjacking and embedding

SaaS products sometimes need iframe embedding for partner marketplaces. Use CSP `frame-ancestors https://partner.example` instead of global DENY. Document allowed embedders in security review. OAuth and payment flows benefit from Cross-Origin-Opener-Policy `same-origin` to block window reference attacks.

## Permissions-Policy as feature firewall

Even with CSP blocking script injection, Permissions-Policy denies camera, microphone, and payment APIs your app never uses:

```http
Permissions-Policy: geolocation=(), microphone=(), camera=(), payment=(self)
```

Review after adding video KYC or WebRTC features—policies are easy to forget when product scope expands.

## Testing and regression detection

Automate header assertions in Playwright or integration tests for 200, 404, and 500 paths. Scan with [securityheaders.com](https://securityheaders.com/) after CDN changes. Compare CSP report volume week-over-week; spikes after deploy usually mean a new third-party snippet.

When checkout breaks after CSP enforce, rollback to report-only immediately, then fix forward. Revenue incidents outweigh theoretical XSS risk for the minutes required to patch script-src.

## Common failure modes

- **Stripe or analytics blocked** — missing connect-src or script-src entry
- **Inline config blocked** — forgot nonce plumbing in SSR template
- **WebSocket failures** — connect-src omits `wss://` host
- **PDF or blob previews** — frame-src or worker-src too strict
- **Duplicate headers** — CDN and origin both set CSP, browser merges unpredictably

Maintain a third-party registry linked from pull request templates. Marketing requests should include domains for CSP review before merge.

## Governance without bureaucracy

Assign header ownership to platform or security engineering with product consultation. Quarterly diff production CSP against registry—orphan domains indicate shadow IT scripts. Version control nginx and Helm values; header drift between regions is a frequent post-incident finding.

Headers complement auth, input validation, and dependency patching. They are cheap insurance when other layers fail—and expensive when misconfigured without report-only rehearsal.

## Extended guidance for security headers hardening

Maintain CSP in source control beside application code, not only in CDN UI. When security headers change, run automated checkout and OAuth smoke tests — CSP breaks are silent until revenue drops. Include Subresource Integrity and Trusted Types in the same hardening epic when XSS is in threat model; headers stack rather than replace secure coding.

Fail CI if production responses lack HSTS or enforcing CSP after report-only phase completes.

## Resources

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Helmet.js documentation](https://helmetjs.github.io/)
- [HSTS preload list](https://hstspreload.org/)
- [web.dev CSP guide](https://web.dev/articles/csp)

When operating security headers hardening in production, tie changes to measurable outcomes: error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. Compare canary versus control for at least one full business day on mid-tier mobile hardware before promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook so on-call can revert without paging the author.

When operating security headers hardening in production, tie changes to measurable outcomes: error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. Compare canary versus control for at least one full business day on mid-tier mobile hardware before promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook so on-call can revert without paging the author. Revisit thresholds quarterly for security workloads as traffic mix shifts.

When operating security headers hardening in production, tie changes to measurable outcomes: error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. Compare canary versus control for at least one full business day on mid-tier mobile hardware before promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook so on-call can revert without paging the author. Revisit thresholds quarterly for security workloads as traffic mix shifts.

When operating security headers hardening in production, tie changes to measurable outcomes: error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. Compare canary versus control for at least one full business day on mid-tier mobile hardware before promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook so on-call can revert without paging the author. Revisit thresholds quarterly for security workloads as traffic mix shifts.

When operating security headers hardening in production, tie changes to measurable outcomes: error rate, latency p75 on affected routes, and support ticket volume tagged to the feature area. Compare canary versus control for at least one full business day on mid-tier mobile hardware before promoting to full traffic. Document rollback in the pull request and link the dashboard from the runbook so on-call can revert without paging the author. Revisit thresholds quarterly for security workloads as traffic mix shifts.
