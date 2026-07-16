---
title: "HTTP Security Headers Hardening"
slug: "security-headers-hardening"
description: "Harden HTTP responses with security headers: CSP, HSTS, frame options, and middleware configs that survive real applications."
datePublished: "2025-07-06"
dateModified: "2025-07-06"
tags: ["Security", "HTTP", "Web Security", "Headers"]
keywords: "HTTP security headers, Content-Security-Policy, HSTS, X-Frame-Options, security headers middleware, Helmet.js, CSP nonce"
faq:
  - q: "Which security headers are non-negotiable?"
    a: "Strict-Transport-Security on HTTPS sites, Content-Security-Policy tailored to your asset origins, X-Content-Type-Options nosniff, and frame-ancestors or X-Frame-Options to prevent clickjacking. Referrer-Policy and Permissions-Policy reduce leakage and feature abuse. Cross-Origin-Opener-Policy helps isolate windows on auth flows."
  - q: "How do I roll out CSP without breaking production?"
    a: "Start with Content-Security-Policy-Report-Only collecting violations to a report-uri endpoint. Fix inline scripts by nonces or moving JS external. Tighten default-src and script-src incrementally. Flip to enforcing mode when violation rate near zero for a week. Avoid unsafe-inline in final policy unless legacy constraints force temporary exceptions with migration plan."
  - q: "Does HSTS replace HTTPS redirects?"
    a: "No—they complement each other. Redirects protect first visit; HSTS tells browsers to use HTTPS directly on return visits and optionally include subdomains. preload list submission requires max-age ≥31536000, includeSubDomains, and preload directive after validating entire subdomain tree serves valid TLS."
---

Security headers won a compliance checkbox while CSP remained `default-src *` and the admin panel loaded in an iframe on a phishing site. Headers do not fix SQL injection, but they shrink blast radius when bugs exist: XSS cannot phone home if script-src blocks it; stolen sessions resist downgrade if HSTS is pinned. The work is tailoring policies to actual asset origins—not copy-pasting OWASP examples that break Stripe.js on checkout.


## Baseline header set

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
Content-Security-Policy: default-src 'self'; script-src 'self' https://js.stripe.com; ...
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
Cross-Origin-Opener-Policy: same-origin
```

Prefer `frame-ancestors 'none'` in CSP over legacy XFO where browsers support both.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## CSP with nonces

```html
<script nonce="rAnd0m123">/* inline allowed with matching nonce */</script>
```

```http
Content-Security-Policy: script-src 'self' 'nonce-rAnd0m123'
```

Generate fresh nonce per request in middleware. Hash-based CSP works for static inline blocks.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## HSTS rollout

Stage 1: `max-age=300` (five minutes) to test breakage. Stage 2: increase to one year. Verify no mixed content and all subdomains support TLS before `includeSubDomains`. Submit to [HSTS preload list](https://hstspreload.org/) only after audit.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Express with Helmet

```javascript
import helmet from "helmet";

app.use(
  helmet({
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'", "https://cdn.example.com"],
        imgSrc: ["'self'", "data:", "https:"],
      },
    },
    hsts: { maxAge: 31536000, includeSubDomains: true },
  })
);
```

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Nginx

```nginx
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
add_header Content-Security-Policy "default-src 'self';" always;
add_header X-Content-Type-Options "nosniff" always;
```

`always` ensures headers on error responses too.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

## Testing

[C securityheaders.com scan](https://securityheaders.com/), Mozilla Observatory, and integration tests asserting header presence on 200 and 404. CSP reports aggregate in reporting endpoint or Sentry.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.


Third-party widgets need explicit script-src/connect-src entries. PDF viewers and WebSockets require frame-src/connect-src updates. Document allowed domains in ADR when marketing adds analytics.

CSP Report-Only week before enforce—collect violations without breaking checkout. Stripe and analytics domains need explicit script-src connect-src entries.

HSTS preload only after entire subdomain tree serves valid TLS. Start max-age=300 before one-year commitment.

Test headers on 404 and 500 responses—always flag in nginx ensures headers on error paths attackers probe.

Validate this in staging with production-like data volume before declaring done. Capture metrics baseline the week before change and compare for seven days after—subtle regressions hide in aggregates until a large tenant hits the path. Update the on-call runbook with the failure signature and rollback command so responders need not rediscover steps during an incident.

Document the decision, owner, and rollback path in your team wiki the same week you ship. Future you will not remember which environment variable toggled the behavior unless it is written next to the runbook entry and linked from the alert. That habit costs ten minutes per change and saves hours when pagination or auth misbehaves under a single large tenant.



Run the change through your standard PR checklist: tests, observability, and a two-minute rollback drill in staging. Small operational habits accumulate into systems that survive on-call nights without heroics.


Share a short write-up in your engineering channel after rollout: what shipped, what metric you watch, and who owns follow-up. That closes the loop for teammates who were not in the PR and surfaces gaps in docs before the next person repeats the same investigation.


Prefer boring, repeatable process over one heroic migration weekend.


Treat operational readiness as part of definition-of-done: dashboards, alerts, runbook links, and a named owner. Skipping those steps ships code that works in demo and fails quietly in production until a customer or auditor finds the gap.

## Resources

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Helmet.js documentation](https://helmetjs.github.io/)
- [HSTS preload list](https://hstspreload.org/)
- [web.dev: CSP guide](https://web.dev/articles/csp)
