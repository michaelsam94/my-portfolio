---
title: "Referrer-Policy Configuration for Privacy"
slug: "security-referrer-policy-configuration"
description: "Referrer leakage in URLs — strict-origin-when-cross-origin vs no-referrer for sensitive routes."
datePublished: "2026-10-23"
dateModified: "2026-07-17"
tags: ["Security", "Headers", "Privacy"]
keywords: "Referrer-Policy header, referrer leakage privacy, strict-origin-when-cross-origin"
faq:
  - q: "Safest default?"
    a: "strict-origin-when-cross-origin for most apps; no-referrer on sensitive admin routes."
  - q: "Referer vs Referrer-Policy?"
    a: "Policy controls how much URL is sent; misspelling Referer is in the HTTP spec forever."
  - q: "Tokens in query strings?"
    a: "Fix URL design first; Referrer-Policy is defense in depth."
---

A full account URL with a password-reset token appeared in a third-party analytics dashboard—via the Referer header on a tracking pixel. The application team assumed HTTPS meant privacy; nobody mapped which subresources received full URLs on cross-origin requests.

Referrer-Policy is one HTTP response header that controls leakage of browsing context. Misconfiguration is silent until compliance or a customer notices sensitive paths in vendor logs.

## How Referer behaves without policy

Browsers default toward sending referrer information—historically full URLs. Any third-party script, font, analytics pixel, or CDN asset request may include the current page URL in Referer. Query strings with tokens, internal IDs, or search terms leave your origin.

The HTTP header is misspelled `Referer` forever; `Referrer-Policy` is spelled correctly. Both appear in specs and tools—grep for either in audits.

## Policy values and trade-offs

| Policy | Same-origin | Cross-origin HTTPS | HTTPS→HTTP |
| --- | --- | --- | --- |
| no-referrer | none | none | none |
| strict-origin | origin | origin | none |
| strict-origin-when-cross-origin | full URL | origin | none |
| origin | origin | origin | none |
| same-origin | full URL | none | none |

**strict-origin-when-cross-origin** balances analytics on your own site with privacy on external requests—reasonable global default for marketing and product surfaces.

**no-referrer** for `/account/*`, `/admin/*`, medical search results, and document preview routes handling sensitive filenames.

## Deployment layers

Set globally in middleware:

```javascript
app.use((req, res, next) => {
  const sensitive = /^\/(account|admin|reset)/.test(req.path);
  res.setHeader(
    "Referrer-Policy",
    sensitive ? "no-referrer" : "strict-origin-when-cross-origin"
  );
  next();
});
```

CDN path rules can apply zone-specific policies without redeploying application code—document zone maps in security baseline so new microsites inherit correct defaults.

HTML meta tag works but is weaker than HTTP header for subresources loaded before parser reaches meta—prefer header.

Per-element override for exceptions:

```html
<img src="https://analytics.example.com/pixel" referrerpolicy="no-referrer" alt="" />
```

Use when document policy stays permissive but one embed must not leak paths.

## OAuth, SAML, and payment flows

Identity provider redirects sometimes log referrer URLs containing authorization codes when integrations misconfigure redirect URIs. Regression-test IdP login after tightening policy—broken flows show up as sudden login failure spikes, not CSP console errors.

Payment iframes and 3-D Secure challenges may require explicit `referrerpolicy` on embed tags. Coordinate with payment vendor documentation before global no-referrer.

## Interaction with CSP and analytics

Content-Security-Policy violation reports may include referrer URLs—treat report endpoints as sensitive logs with restricted access. Strict-Transport-Security prevents downgrade scenarios where HTTPS URLs would leak to HTTP endpoints.

Marketing attribution often depends on full referrer paths. After tightening policy, cross-origin analytics sees origins only. Migrate campaigns to UTM parameters you control and first-party collection stored server-side. Coordinate with growth before deploy—revenue attribution regressions are politically harder than privacy tickets.

## Healthcare and search leakage

Applications putting patient names or diagnoses in query strings need `no-referrer` on result pages regardless of other zones. URL design fix comes first; policy limits damage when legacy URLs cannot change immediately.

## GDPR and vendor contracts

Full URLs with user identifiers may constitute personal data under GDPR. Data processing agreements with analytics vendors must cover referrer collection—or policy must strip paths cross-origin. Export weekly header snapshots from production into evidence storage for audits proving control persistence after CDN refactors.

## Testing checklist

- curl -I sensitive routes for expected policy value
- Browser devtools Network tab: inspect Referer on third-party requests before and after change
- Playwright assertion on password reset page
- Verify OAuth and checkout E2E still pass

## Incident response for referrer leaks

If a leaked URL appears in a vendor dashboard:

1. Rotate any tokens in the path immediately
2. Set no-referrer on affected routes
3. Audit which third-party scripts receive subresource referrers
4. Notify privacy/compliance if PII exposed
5. Move identifiers from URLs to opaque server-side session state post-incident

## Search query leakage

Healthcare and legal apps with query strings in URLs need `no-referrer` on search result pages — `strict-origin-when-cross-origin` still leaks path on same-origin subresource requests to CDNs.

## Referrer-Policy on redirects

302 chains inherit policy from final response — set Referrer-Policy on all redirect hops in OAuth and password reset flows, not only the landing page.

## Resources

- [MDN Referrer-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy)
- [W3C Referrer Policy spec](https://www.w3.org/TR/referrer-policy/)
- [OWASP Information Exposure through query strings](https://owasp.org/www-community/vulnerabilities/Information_exposure_through_query_strings_in_url)
- [web.dev Referrer best practices](https://web.dev/articles/referrer-best-practices)
- [RFC 7231 Referer header](https://datatracker.ietf.org/doc/html/rfc7231#section-5.5.2)

## Operational checklist (1)

Before promoting Security Referrer Policy Configuration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Security Referrer Policy Configuration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Referrer Policy Configuration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Security Referrer Policy Configuration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Security Referrer Policy Configuration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Referrer Policy Configuration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Security Referrer Policy Configuration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Security Referrer Policy Configuration after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Referrer Policy Configuration touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Security Referrer Policy Configuration changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Reviewer checklist for security referrer policy configuration

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most security referrer policy configuration regressions before production.

| Check | Expected for security referrer policy configuration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around security referrer policy configuration

Most incidents involving security referrer policy configuration start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

Concrete probe 2: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Invariants to enforce for security referrer policy configuration

Name three invariants that must hold after every deploy of security referrer policy configuration. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for security referrer policy configuration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for security referrer policy configuration

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to security referrer policy configuration, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 4: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for security referrer policy configuration

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for security referrer policy configuration should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for security referrer policy configuration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for security referrer policy configuration

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how security referrer policy configuration breaks without a clear owner in the incident channel.

Concrete probe 6: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for security referrer policy configuration

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct security referrer policy configuration changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for security referrer policy configuration |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for security referrer policy configuration in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
