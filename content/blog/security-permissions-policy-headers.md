---
title: "Permissions-Policy Header Configuration"
slug: "security-permissions-policy-headers"
description: "Permissions-Policy restricts browser feature APIs — camera, geolocation, payment, USB — reducing attack surface when third-party scripts request capabilities your app never uses."
datePublished: "2026-10-22"
dateModified: "2026-07-17"
tags:
  - "Engineering"
keywords: "Permissions-Policy header, Feature-Policy, browser feature restriction, geolocation disable, camera API block"
faq:
  - q: "Permissions-Policy vs CSP?"
    a: "CSP controls resource origins; Permissions-Policy controls whether APIs like camera can run."
  - q: "Default for marketing sites?"
    a: "Deny camera, microphone, geolocation globally; allow on specific routes only."
  - q: "Feature-Policy legacy?"
    a: "Prefer Permissions-Policy; some browsers still accept Feature-Policy during migration."
---

A third-party chat widget on our marketing site requested camera access during a product demo embedded in an iframe. Users saw a browser permission prompt on a page with no legitimate reason to touch hardware APIs. Marketing had pasted a snippet; nobody reviewed which APIs the script could invoke once loaded.

Content Security Policy blocked inline script injection, but CSP does not stop an allowed third-party bundle from calling `navigator.mediaDevices.getUserMedia()`. Permissions-Policy closes that gap by declaring, at the HTTP layer, which powerful features may run in this document and its iframes.

## Header stack: where Permissions-Policy fits

Security headers answer different questions. Treat them as layers, not alternatives.

| Header | Question it answers |
|---|---|
| CSP | May this script load from cdn.example.com? |
| Permissions-Policy | Even if loaded, may it open the camera? |
| Referrer-Policy | What URL metadata leaks on navigation? |
| COOP/COEP | How isolated is this browsing context? |

A common gap: strict `script-src` while geolocation and payment defaults remain at browser allow-prompt. Attackers who achieve script execution via supply-chain compromise in an allowed origin inherit every API the browser exposes unless Permissions-Policy narrows the surface.

## Directive syntax and defaults

Modern Permissions-Policy uses structured directives. Each feature lists allowed origins in parentheses. Empty `()` means deny everywhere, including same-origin scripts.

```
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()
```

Allow-list syntax grants a feature to specific origins:

```
Permissions-Policy: geolocation=(self "https://maps.example.com")
```

`self` refers to the document origin. Quoted origins must match exactly — scheme included.

Legacy `Feature-Policy` used similar syntax with different parsing. During migration, emit both headers with identical intent, then retire Feature-Policy when RUM shows negligible legacy traffic.

## Express middleware pattern

Set the header once for HTML document responses. Static assets and JSON API responses typically omit it.

```javascript
const DEFAULT_POLICY = [
  "camera=()", "microphone=()", "geolocation=()",
  "payment=()", "usb=()", "interest-cohort=()",
].join(", ");

app.use((req, res, next) => {
  if (req.accepts("html") && !req.path.startsWith("/api")) {
    res.setHeader("Permissions-Policy", DEFAULT_POLICY);
  }
  next();
});
```

Route-specific overrides apply only where product requirements justify them — store locator may allow `geolocation=(self)`; checkout may allow `payment=(self)`. Document every exception in the security runbook.

## Iframe embeds and allow attributes

Permissions-Policy on the parent can deny camera globally, but an iframe with `allow="camera"` re-enables it for that subtree. Audit all iframe embeds quarterly — marketing CMS plugins add embeds without security review.

```html
<iframe src="https://support.example.com/widget"
        allow="clipboard-write"
        sandbox="allow-scripts allow-same-origin"></iframe>
```

Align `allow` attributes with Permissions-Policy. Overbroad `allow` lists defeat the header silently.

## Report-Only rollout

Use `Permissions-Policy-Report-Only` during pilot to collect violations without blocking. Violation reports include feature name, source file, and line number when available. Two-week report-only window before enforce mode — features you assumed unused often appear in legacy A/B snippets.

## Policy matrix by surface

| Surface | camera | geolocation | payment | notes |
|---|---|---|---|---|
| Marketing/blog | deny | deny | deny | third-party widgets |
| Store locator | deny | self | deny | user-initiated |
| Checkout | deny | deny | self | PCI scope |
| Support chat iframe | deny | deny | deny | sandbox + minimal allow |

Separate admin onto `admin.example.com` with its own policy rather than carving exceptions into the public site.

## Interaction with other defenses

Permissions-Policy complements DOM XSS defenses. Trusted Types blocks unsafe sink assignments; Permissions-Policy blocks API abuse after script runs. Subresource Integrity ensures script bytes match expected hash — none replace the others.

Payment Request API access on checkout without policy restriction means any XSS on checkout can invoke `PaymentRequest`. Deny payment globally; allow `(self)` only on payment routes.

## Features worth denying by default

Beyond camera and geolocation: `interest-cohort=()` opts out of Topics; `usb=()` and `serial=()` block WebUSB/WebSerial vectors; `fullscreen=(self)` prevents third-party fullscreen phishing overlays.

Review the Permissions Policy features list annually — browsers add new powerful APIs.

## Testing checklist

1. Load each route in Chrome DevTools → Application → Permissions Policy
2. Verify third-party scripts cannot trigger permission prompts on marketing pages
3. Confirm checkout payment flow works under restricted policy
4. Add header assertion to Playwright smoke tests for critical routes

```javascript
test("marketing pages deny camera", async ({ request }) => {
  const res = await request.get("/");
  expect(res.headers()["permissions-policy"] ?? "").toMatch(/camera=\(\)/);
});
```

## Incident response

If a supply-chain script in an allowed CSP origin starts invoking APIs, Permissions-Policy limits blast radius while you rotate the compromised package. Keep a break-glass policy variant documented — temporarily allow a feature for a single route during vendor migration, with expiry date and rollback owner.

Permissions-Policy turns "we never use the camera on this site" from an assumption into an HTTP-enforced guarantee.

## iframe allow attribute pairing

Permissions-Policy must permit payment for Stripe origin AND the iframe needs allow="payment". Missing either side breaks checkout with opaque console errors unrelated to CSP.

## Feature policy migration from legacy headers

Older Feature-Policy header names differ from Permissions-Policy — audit CDN configs after browser deprecation cycles. Duplicate conflicting headers leave effective policy undefined across browsers.

## Notes on security permissions policy headers

When tightening camera or microphone denial, test video KYC and support call routes in staging with real devices. Report-only Permissions-Policy helps before blocking embeds that marketing added without ticket. Pair header policy with CSP frame-src — both layers matter for checkout iframes.

## Resources

- [web.dev — Core Web Vitals](https://web.dev/vitals/)
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)
- [MDN Web Docs — Web APIs](https://developer.mozilla.org/en-US/docs/Web/API)
- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev/)

## iframe allow attribute pairing

Permissions-Policy must permit `payment` for Stripe origin AND the iframe needs `allow="payment"`. Missing either side breaks checkout with opaque console errors.

## Production notes

When tightening camera or microphone denial, test video KYC and support call routes in staging with real devices. Report-only Permissions-Policy helps before blocking embeds that marketing added without ticket. Pair header policy with CSP frame-src — both layers matter for checkout iframes.

Re-run feature inventory when marketing adds video or chat widgets — headers drift silently.

Ship security permissions policy headers changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff.

Ship security permissions policy headers changes with a named owner, dashboard link, and rollback command in the runbook — operational readiness matters as much as the code diff. Re-baseline metrics after the next traffic doubling affecting security routes.

## Failure modes specific to security permissions policy headers

Threat modeling for security permissions policy headers starts with assets (tokens, PII, session cookies, signing keys) and actors (anonymous scrapers, stolen refresh tokens, insider with staging access). Map each abuse case to a control that fails closed.

For security permissions policy headers, I insist on:
- Explicit allowlists at trust boundaries — not denylists that lag attacker creativity
- Short-lived credentials with automated rotation and break-glass audited separately
- Structured audit events that never embed secrets or full PANs
- Dependency and container scanning gated on severity *and* exploitability (VEX/KEV), not CVE count vanity

When security permissions policy headers lands in a PR, reviewers should ask: what is the bypass if this control is skipped in a secondary code path? Shadow APIs, admin tools, and batch jobs are where security postures quietly diverge from the happy path.

| Signal | Target | Alarm |
|--------|--------|-------|
| Cold start p95 | Team-defined SLO | Page on burn rate |
| Throttle count | Baseline − noise | Ticket if sustained |
| Downstream timeouts | Budget cap | Weekly review |

## Metrics and alarms for security permissions policy headers

Reviewers should challenge assumptions encoded in security permissions policy headers: defaults copied from tutorials, timeouts that exceed upstream SLAs, and authz checks applied only on the primary UI path. Require a short threat or failure note in the PR when the change touches a trust boundary.

Concrete probes:
1. Scenario B for security permissions policy headers: bad config shipped — prove rollback within the declared RTO without data corruption.
2. Scenario C for security permissions policy headers: traffic 3× baseline — prove autoscaling or shedding keeps the golden journey healthy.
3. Scenario A for security permissions policy headers: partial dependency outage — prove clients degrade gracefully and retries do not amplify load.

## Capacity planning with security permissions policy headers in mind

Roll out security permissions policy headers behind a flag or weighted route when possible. Start with internal users or a low-risk geography. Watch the signals in the table for at least one full business cycle before calling the migration done. Keep the previous path warm until error budgets stabilize.

Document the owner, the dashboard, and the single command that reverts the change. If that sentence is hard to write, the design is not ready for production traffic.

## Compliance evidence for security permissions policy headers

Detail 1 (232): for security permissions policy headers, define the contract between producers and consumers explicitly — payload shape, timeout, and idempotency key. When compliance evidence for security permissions policy headers becomes painful, it is usually because that contract was implicit.

I keep a short matrix: who can break security permissions policy headers, how we detect it within five minutes, and who is paged. Update the matrix when ownership moves. Add one synthetic check that exercises the failure path, not only the happy path. Prefer checks that run continuously over quarterly manual reviews that everyone skips under deadline pressure.

If you only remember one thing about security permissions policy headers: optimize for reversible decisions. Reversibility beats cleverness when the incident channel is busy and the blast radius is unclear.
