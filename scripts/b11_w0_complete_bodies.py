# Part 2: remaining POSTS bodies for b11_w0_complete.py
# POSTS dict must exist in caller namespace before exec
POSTS["security-headers-hardening"] = '''---
title: "HTTP Security Headers Hardening"
slug: "security-headers-hardening"
description: "Harden HTTP responses with security headers: CSP, HSTS, frame options, and middleware configs that survive real applications."
datePublished: "2025-07-06"
dateModified: "2026-07-17"
tags: ["Security", "HTTP", "Web Security", "Headers"]
keywords: "HTTP security headers, Content-Security-Policy, HSTS, X-Frame-Options, security headers middleware, Helmet.js, CSP nonce"
faq:
  - q: "Which security headers are non-negotiable?"
    a: "Strict-Transport-Security on HTTPS sites, Content-Security-Policy matched to your asset origins, X-Content-Type-Options nosniff, and frame-ancestors or X-Frame-Options against clickjacking. Referrer-Policy and Permissions-Policy reduce leakage and unused API abuse. Cross-Origin-Opener-Policy helps isolate OAuth popups."
  - q: "How do I roll out CSP without breaking production?"
    a: "Run Content-Security-Policy-Report-Only first, collecting violations to a report endpoint. Replace inline scripts with nonces or external files. Tighten script-src and connect-src incrementally. Switch to enforcing mode when violations near zero for a full week. Document every third-party domain in an ADR when marketing adds tools."
  - q: "Does HSTS replace HTTPS redirects?"
    a: "No—they solve different moments. Redirects protect the first visit; HSTS tells returning browsers to use HTTPS directly. Preload submission requires max-age at least 31536000, includeSubDomains, and preload after verifying every subdomain serves valid TLS."
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

## Resources

- [OWASP Secure Headers Project](https://owasp.org/www-project-secure-headers/)
- [MDN Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Helmet.js documentation](https://helmetjs.github.io/)
- [HSTS preload list](https://hstspreload.org/)
- [web.dev CSP guide](https://web.dev/articles/csp)
'''

POSTS["security-logging-audit-trails"] = '''---
title: "Security Logging and Audit Trails"
slug: "security-logging-audit-trails"
description: "Build security audit trails: tamper-evident logs, who-did-what events, retention, and correlation with SIEM for incident response."
datePublished: "2025-07-10"
dateModified: "2026-07-17"
tags: ["Security", "Logging", "Compliance", "Audit"]
keywords: "security audit logging, audit trail design, tamper evident logs, SIEM integration, authentication audit events, compliance logging"
faq:
  - q: "How are audit logs different from application logs?"
    a: "Audit logs are append-only, structured, and answer who did what to which resource with outcome. Application logs debug stack traces and latency. Mixing them in one stream complicates retention—audit events need years and legal hold; debug logs can expire in weeks."
  - q: "What fields belong in every audit event?"
    a: "Actor identity, action verb, target resource type and ID, timestamp in UTC, result success or failure, correlation ID, source IP or device context, and optional approver for dual-control actions. Never log secret values, full payment PANs, or raw passwords."
  - q: "How long should audit logs be retained?"
    a: "Match regulatory minimums—often one to seven years for financial and healthcare contexts. Store audit streams separately from operational logs with delete denied on the bucket policy. Legal hold must pause automated lifecycle without corrupting immutability guarantees."
---

Compliance asked who elevated a user to admin last Tuesday. We had verbose application logs, stack traces, and a Grafana dashboard—but no immutable record tying actor, action, and target. The investigation took three days of grep across unstructured text. Audit trails exist so that question answers in one query.

Security audit logging is not "turn on debug level in production." It is a designed event vocabulary emitted at authorization boundaries, shipped to tamper-evident storage, and correlated with detections in your SIEM.

## Application logs versus audit events

| Dimension | Application log | Audit event |
| --- | --- | --- |
| Purpose | Debug failures, profile latency | Prove accountability |
| Mutability | Rotated, sampled, deleted | Append-only, WORM |
| Content | Stack traces, cache keys | Actor, action, target, result |
| Audience | Engineers on-call | Auditors, legal, IR team |
| Retention | Days to months | Years with hold |

When audit events land in the same index as debug noise, retention policies either delete evidence too early or store stack traces for seven years. Separate streams, separate buckets, separate access controls.

## Event schema that survives audits

Standardize on a versioned JSON schema:

```json
{
  "schema_version": 1,
  "event_id": "01J…",
  "timestamp": "2026-07-17T10:22:01.123Z",
  "actor": { "type": "user", "id": "usr_abc", "session_id": "ses_xyz" },
  "action": "role.assign",
  "target": { "type": "membership", "id": "mem_456", "tenant_id": "tnt_789" },
  "result": "success",
  "metadata": { "role": "admin", "previous_role": "member" },
  "correlation_id": "req-uuid",
  "source_ip": "203.0.113.10",
  "user_agent_hash": "sha256:…"
}
```

Use past-tense verb phrases (`role.assign`, `document.export`, `api_key.create`). Include tenant ID on every multi-tenant event so SIEM rules scope correctly.

Emit at the authorization decision point—not only when controllers succeed. Failed privilege escalations matter as much as successes for detection.

## Tamper-evident storage patterns

Object storage with versioning plus bucket policy denying `s3:DeleteObject` for application roles satisfies many SOC2 reviewers. AWS CloudTrail Lake, Azure immutable blobs, and GCS retention locks add legal-grade guarantees.

Hash chaining—each batch includes hash of previous batch—detects retroactive tampering if an attacker gains storage credentials. Services like Chronicle or dedicated audit vendors implement this; roll your own only with cryptographic review.

Separate write and read IAM roles. Applications write via limited policy; analysts read via break-glass role with MFA and session logging.

## What to audit first

Prioritize high-risk actions before logging every read:

- Authentication success and failure, MFA enrollment, password reset
- Role and permission changes
- API key and OAuth client lifecycle
- Data export, bulk download, cross-tenant access
- Billing and payout configuration
- Security setting changes (CSP, IP allowlists, SSO metadata)

Reads of sensitive records may require audit in healthcare (HIPAA) contexts—balance volume against detection value. Sample or aggregate read audits when full logging exceeds cost limits, but document the sampling policy for auditors.

## SIEM correlation and detections

Ship audit streams to Splunk, Elastic, or cloud-native SIEM with field extraction for `actor.id`, `action`, and `target.tenant_id`. Detections to implement early:

- Impossible travel: same user auth from distant geos within minutes
- Privilege escalation followed by bulk export within one hour
- Admin actions from new device fingerprint
- Repeated failed authorization then success from same IP
- Service account performing human-only actions

Correlate audit `correlation_id` with application request logs for deep dives—not for long-term storage of duplicate data.

## PII and secrets in audit payloads

Redact at emission time. Debugging temptation leads engineers to log request bodies containing passwords or tokens. Code review checklist: audit calls never receive raw HTTP bodies.

Hash or truncate IP addresses where GDPR requires minimization. Document lawful basis for retaining actor identifiers.

## Retention, legal hold, and export

Automated lifecycle transitions audit buckets to Glacier after hot search window. Legal hold flags objects exempt from deletion without modifying content. Quarterly test export: generate sample audit bundle for staging environment and walk compliance through field definitions before real audit season.

## Implementation in application code

Centralize audit emission in one module:

```typescript
export async function audit(event: AuditInput): Promise<void> {
  const payload = AuditSchema.parse({
    ...event,
    event_id: ulid(),
    timestamp: new Date().toISOString(),
    schema_version: 1,
  });
  await auditSink.write(payload); // Kafka, CloudWatch, stdout sidecar
}
```

Middleware can attach `correlation_id` from incoming headers. Authorization middleware calls `audit()` on allow and deny.

Avoid blocking user requests on audit sink failure—queue locally with backpressure and alert if queue depth exceeds threshold. Silent audit loss is worse than delayed responses; totally blocking checkout on audit outage is also unacceptable. Document the trade-off.

## Incident response usage

When investigating compromise, timeline reconstructions use audit ordering:

1. Filter by `target.tenant_id` and time window
2. Pivot on `actor.id` for all actions in window
3. Join failed auth events with subsequent success from new IP
4. Identify API keys created or roles assigned
5. Revoke credentials and scope blast radius from audit graph

Preserve original logs with chain of custody notes if law enforcement involvement is possible.

## Organizational ownership

Product teams define which business actions are auditable; platform owns sink reliability and retention; security owns detections and access to read paths. Onboarding docs should show one example query answering "who changed this setting."

Audit design is iterative—add events when postmortems reveal gaps. Version schema carefully; SIEM parsers break on silent field renames.

## Resources

- [NIST SP 800-92 Guide to Computer Security Log Management](https://csrc.nist.gov/publications/detail/sp/800-92/final)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [CloudTrail best practices](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/best-practices-security.html)
- [ISO 27001 logging controls mapping](https://www.iso.org/standard/54534.html)
- [Google Chronicle audit pipeline patterns](https://cloud.google.com/chronicle/docs)
'''

POSTS["security-http-only-secure-cookies"] = '''---
title: "HttpOnly and Secure Cookie Configuration"
slug: "security-http-only-secure-cookies"
description: "Session cookies need HttpOnly, Secure, SameSite — __Host- prefix rules and subdomain cookie scope."
datePublished: "2026-10-21"
dateModified: "2026-07-17"
tags: ["Security", "Cookies", "Auth"]
keywords: "HttpOnly Secure cookie, SameSite cookie, session cookie security"
faq:
  - q: "What does the HttpOnly flag do?"
    a: "HttpOnly prevents JavaScript from reading the cookie via document.cookie. If XSS exists, HttpOnly stops most session token theft through script injection. It does not prevent CSRF or network interception—pair with Secure and SameSite."
  - q: "When should I use SameSite=Strict vs Lax?"
    a: "Lax sends cookies on top-level GET navigations from external sites but blocks them on cross-site POST and fetch— stopping most CSRF while preserving email link login. Strict blocks all cross-site sends; users from external links appear logged out until a same-site navigation. Use Strict for admin; Lax for consumer apps."
  - q: "What is the __Host- cookie prefix?"
    a: "__Host- requires Secure, Path=/, and no Domain attribute. Browsers reject misconfigured cookies, preventing subdomain scope attacks where compromised staging.app.com overwrites production session cookies."
---

An XSS bug in our analytics wrapper read `document.cookie` and exfiltrated session tokens—we had set `Secure` but forgot `HttpOnly`. Three attributes and a prefix fixed a vulnerability class that had lingered through two pentests because "cookies were encrypted in transit."

Session cookies are bearer tokens. Treat them like secrets the browser carries automatically. Configuration mistakes rarely throw errors; they fail open until an attacker demonstrates impact.

## The minimum viable session cookie

```http
Set-Cookie: __Host-session=eyJ…; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=3600
```

| Flag | What it blocks |
| --- | --- |
| HttpOnly | `document.cookie` and XSS exfiltration |
| Secure | Transmission over plaintext HTTP |
| SameSite=Lax | Cross-site POST CSRF and most embedded contexts |
| __Host- prefix | Domain-scoping mistakes and missing Secure/Path=/ |

Express example:

```javascript
res.cookie("__Host-session", token, {
  httpOnly: true,
  secure: true,
  sameSite: "lax",
  maxAge: 3600 * 1000,
  path: "/",
  // no domain attribute with __Host-
});
```

Never mirror session identifiers in `localStorage` for SPA convenience—any XSS owns the token permanently until expiry.

## SameSite behavior in real flows

**Lax (default recommendation)** — cookie sent when user clicks `https://yoursite.com/path` from email or search results. Not sent on cross-site `<form POST>` or cross-origin `fetch` from evil.com.

**Strict** — cookie withheld even on top-level cross-site GET. OAuth return URLs and marketing deep links may need an intermediate same-site landing page or Strict breaks login continuity.

**None** — requires `Secure`; used for embedded widgets and cross-site iframes that must send cookies. Increases CSRF surface—mandate anti-CSRF tokens on all mutating endpoints when using SameSite=None.

Chrome's third-party cookie deprecation changes embedding scenarios—audit iframe integrations annually.

## Cookie prefixes in depth

Browser-enforced prefixes reduce misconfiguration:

| Prefix | Requirements |
| --- | --- |
| `__Host-` | Secure, Path=/, no Domain |
| `__Secure-` | Secure flag required |
| `__Session-` | no Max-Age or Expires (session cookie) |

`__Host-` prevents setting `Domain=.example.com` that would expose cookies to all subdomains—including attacker-controlled `user-content.example.com` if subdomain takeover occurs.

## Subdomain and cross-subdomain auth

Setting `Domain=.example.com` shares cookies across `app`, `www`, and `api`. Compromise of any subdomain steals sessions for all. Prefer host-only cookies on primary auth domain and explicit token exchange for API subdomains when architecture requires separation.

Staging environments on `staging.example.com` must not share cookie domain with production—use separate registrable domains or host-only cookies per environment.

## Refresh tokens and rotation

Long-lived refresh tokens belong in HttpOnly cookies with rotation on each use:

```typescript
// After successful refresh
setCookie(response, "__Host-refresh", newRefresh, { maxAge: 30 * 86400 });
setCookie(response, "__Host-session", newAccess, { maxAge: 3600 });
invalidateRefresh(oldRefreshId);
```

Detect refresh token reuse—parallel requests with same consumed token indicates theft; revoke family and force re-auth.

## CSRF pairing

SameSite=Lax is not complete CSRF defense for all APIs. Mutations still need synchronizer tokens, double-submit cookies, or Origin/Referer validation especially for SameSite=None embeds.

JSON APIs with `Content-Type: application/json` resist simple form CSRF but not all attacks—do not skip CSRF because "we use JWT in header" when cookies also authenticate.

## Testing cookie configuration

Playwright or curl integration tests should assert Set-Cookie attributes on login:

```bash
curl -sI https://app.example.com/login -d '…' | grep -i set-cookie
```

Verify absence of session cookies on HTTP redirect chains. Scan for JavaScript reading cookies in frontend bundles—grep `document.cookie` in CI.

## Mobile and WebView caveats

Embedded WebViews may not honor SameSite identically to desktop Chrome. Test OAuth and SSO on iOS in-app browsers. Custom URL schemes for mobile auth should not pass session tokens in query strings—use one-time exchange codes.

## Migration from localStorage sessions

Moving existing SPAs from localStorage to HttpOnly cookies requires:

1. Backend endpoint issuing Set-Cookie on login
2. CSRF token endpoint readable by frontend
3. Frontend switching API client to cookie credentials with `credentials: 'include'`
4. CORS allowing specific origins—not wildcard—with credentials

Roll out with feature flag; monitor 401 rate during migration window.

## Incident patterns

Stolen session cookies bypass password resets until expiry or server-side revocation. Maintain server-side session registry or token blocklist for logout-everywhere. Short access token TTL limits XSS window even if HttpOnly fails on misconfigured debug builds.

Cookie theft via MITM implies missing Secure or mixed content—fix HSTS and eliminate HTTP asset loads.

## Resources

- [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Chrome SameSite updates](https://developers.google.com/privacy-sandbox/3pcd)
- [RFC 6265bis cookie prefixes](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis)
- [web.dev SameSite cookies explained](https://web.dev/articles/samesite-cookies-explained)
'''

POSTS["security-referrer-policy-configuration"] = '''---
title: "Referrer-Policy Configuration for Privacy"
slug: "security-referrer-policy-configuration"
description: "Referrer leakage in URLs — strict-origin-when-cross-origin vs no-referrer for sensitive routes."
datePublished: "2026-10-23"
dateModified: "2026-07-17"
tags: ["Security", "Headers", "Privacy"]
keywords: "Referrer-Policy header, referrer leakage privacy, strict-origin-when-cross-origin"
faq:
  - q: "What does Referrer-Policy control?"
    a: "It tells the browser how much of the current page URL to send in the Referer header on navigations and subresource requests—full URL, origin only, or nothing."
  - q: "What is the safest default for most apps?"
    a: "strict-origin-when-cross-origin sends full URL on same-origin requests, only origin on cross-origin HTTPS, and strips referrer on HTTPS to HTTP downgrade. Use no-referrer on password reset, admin, and health record pages."
  - q: "Can Referrer-Policy leak session tokens?"
    a: "Yes if tokens live in query strings. Permissive policies expose full paths to third-party analytics and CDNs. Fix URL design first; Referrer-Policy is defense in depth, not a substitute for opaque server-side sessions."
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
  const sensitive = /^\\/(account|admin|reset)/.test(req.path);
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

## Resources

- [MDN Referrer-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy)
- [W3C Referrer Policy spec](https://www.w3.org/TR/referrer-policy/)
- [OWASP Information Exposure through query strings](https://owasp.org/www-community/vulnerabilities/Information_exposure_through_query_strings_in_url)
- [web.dev Referrer best practices](https://web.dev/articles/referrer-best-practices)
- [RFC 7231 Referer header](https://datatracker.ietf.org/doc/html/rfc7231#section-5.5.2)
'''

POSTS["security-subresource-integrity-sri"] = '''---
title: "Subresource Integrity for Third-Party Scripts"
slug: "security-subresource-integrity-sri"
description: "SRI hashes detect CDN tampering — integrity attribute, fallback when hash rotates, and CSP require-sri-for."
datePublished: "2026-10-20"
dateModified: "2026-07-17"
tags: ["Security", "SRI", "CDN"]
keywords: "Subresource Integrity SRI, integrity attribute CDN, script integrity"
faq:
  - q: "What does SRI protect against?"
    a: "SRI ensures a script or stylesheet fetched from a CDN matches the exact bytes you tested. If the CDN is compromised or a supply-chain attacker replaces file content, the browser refuses execution because the hash mismatches."
  - q: "Do bundled first-party scripts need SRI?"
    a: "No. Assets you build and serve from your origin pass through your CI pipeline. SRI matters for third-party scripts and stylesheets loaded via external script or link tags."
  - q: "How do I handle CDN version updates?"
    a: "Pin versioned URLs, never latest aliases. When upgrading, regenerate the integrity hash in the same pull request as the version bump so production never serves a URL without a matching hash."
---

The analytics vendor served JavaScript from a CDN with a versioned path. We trusted TLS and DNS and skipped integrity attributes—until a supply-chain advisory proved that CDN edge compromise had happened elsewhere in the industry. Subresource Integrity turns "we hope the CDN is honest" into "the browser verifies bytes before execute."

SRI is not paranoia about major CDNs. It is cheap insurance when a single script tag runs with full page privileges and your CSP still allows that origin.

## Threat model SRI addresses

Attackers who compromise CDN credentials, BGP-hijack traffic, or inject malicious builds into vendor release pipelines change file contents without changing the URL your HTML references. TLS authenticates the connection, not the file at the other end if the server itself serves malware.

SRI adds a cryptographic hash check:

```html
<script
  src="https://cdn.example.com/lib/analytics-v3.2.1.min.js"
  integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"
  crossorigin="anonymous"
></script>
```

If bytes differ, the browser blocks execution and fires a console error—fail closed.

## crossorigin is mandatory

SRI on cross-origin resources requires CORS-enabled responses and the `crossorigin="anonymous"` attribute on the tag. Without it, browsers may omit CORS mode and integrity verification fails even when the hash is correct.

Verify CDN sends `Access-Control-Allow-Origin` appropriate for anonymous use. Self-hosted copies through your origin avoid CORS complexity but shift operational burden to you.

## First-party versus third-party scope

| Asset source | SRI needed? | Reason |
| --- | --- | --- |
| Webpack/Vite bundle on your domain | No | CI builds artifact you deploy |
| npm package copied into `/static` | No | Same pipeline control |
| Google Tag Manager container | Partial | Container loads dynamic tags—hash outer loader only |
| Stripe.js from js.stripe.com | Yes if policy requires | Vendor-controlled bytes |
| Font Awesome CDN CSS | Yes | Stylesheets also execute in CSS injection contexts |

Focus SRI effort on scripts with DOM and network access from high-trust CDNs you do not build.

## Generating hashes reliably

OpenSSL one-off:

```bash
curl -s https://cdn.example.com/lib/v1/app.js | openssl dgst -sha384 -binary | openssl base64 -A
```

Prefix with algorithm: `sha384-…`. Prefer sha384 or sha512; sha256 remains common.

Build pipeline injection avoids manual copy-paste rot:

```javascript
// vite.config.js with vite-plugin-sri (conceptual)
import { sri } from "vite-plugin-sri";
export default { plugins: [sri({ algorithms: ["sha384"] })] };
```

HTML templates receive updated integrity on each release. Manual hashes in JSX without automation fail within one deploy cycle.

## CSP require-sri-for escalation

Content-Security-Policy can mandate SRI:

```http
Content-Security-Policy: require-sri-for script;
```

Start in report-only combined with existing script-src allowlist. Third-party widgets without integrity will fail until self-hosted or vendor publishes hashes—inventory before enforce.

Pair with strict script-src to prevent attackers loading unintegrity-checked scripts from allowed origins.

## Fallback strategies when SRI blocks

Production outages occur when vendors patch hotfixes without notifying integrators. Mitigations:

- Pin exact version paths, subscribe to vendor security mailing lists
- Self-host critical libraries with your own integrity checks in CI
- Feature flag non-critical third-party scripts off when integrity fails
- Monitor console error rates for SRI failure messages after CDN deploys

Some teams mirror CDN files to their origin nightly with internal hash verification—SRI then covers same-origin path with hash generated from mirror job.

## Interaction with caching

CDNs cache by URL. Integrity hash is tied to URL plus content. If vendor serves byte-range requests or compresses differently per edge, hashes remain stable on full file content—verify against full download, not partial.

Service workers intercepting script requests must not serve stale mismatched content—bust caches on integrity updates.

## Testing in CI

Fetch pinned URLs in CI, compute hash, compare to committed HTML template values. Fail build on drift. Include check in supply-chain security review for new third-party embeds.

Playwright smoke test: page loads without script integrity errors in console for critical flows.

## Common mistakes

- Omitting `crossorigin="anonymous"`
- Using `latest` or unpinned CDN URLs
- Updating URL without hash in same commit
- Applying SRI to inline scripts (use CSP nonces instead)
- Assuming SRI replaces CSP—it does not stop first-party XSS

## Vendor negotiation

Enterprise contracts can require vendors publish integrity hashes in documentation or npm package metadata. Open-source CDNs like cdnjs expose SRI values on file pages—copy from authoritative source, not blog posts.

When vendor refuses pinning, self-host or accept risk explicitly in security review minutes.

## Resources

- [MDN Subresource Integrity](https://developer.mozilla.org/en-US/docs/Web/Security/Subresource_Integrity)
- [W3C SRI specification](https://www.w3.org/TR/SRI/)
- [web.dev SRI guide](https://web.dev/articles/sri)
- [cdnjs SRI hashes](https://cdnjs.com/)
- [CSP require-sri-for](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/require-sri-for)
'''

POSTS["seo-canonical-url-strategies"] = '''---
title: "Canonical URL Strategies for SPAs"
slug: "seo-canonical-url-strategies"
description: "Duplicate URLs dilute ranking signals — canonical tags, trailing slash policy, and parameterized URL handling."
datePublished: "2026-09-23"
dateModified: "2026-07-17"
tags: ["SEO", "Canonical", "Routing"]
keywords: "canonical URL SPA, duplicate content SEO, rel canonical"
faq:
  - q: "Should SPAs use rel=canonical in HTML or HTTP headers?"
    a: "Both work. HTML link tags integrate cleanly with Next.js and Remix metadata APIs per route. HTTP Link headers help at CDN edge for non-HTML resources. Pick one authoritative source per URL and avoid emitting conflicting values."
  - q: "How do I handle UTM and tracking parameters?"
    a: "Strip marketing parameters from canonical URLs. /pricing?utm_source=twitter should canonicalize to https://example.com/pricing so Google consolidates signals on one URL."
  - q: "Do client-side navigations need canonical updates?"
    a: "Yes. SPAs must update or replace the canonical link element on each route change. Otherwise crawlers that execute JavaScript may index the landing page canonical on every virtual route."
---

Fourteen URLs served identical pricing content—HTTP and HTTPS variants, trailing slash inconsistencies, uppercase paths, and UTM-tagged campaign links. Search Console listed them as duplicates without user-selected canonical. Revenue pages competed against themselves for rankings.

Canonical URLs tell search engines which version to index and credit when multiple addresses render the same content. For JavaScript-heavy sites, canonical strategy spans server rendering, client navigations, CDN redirects, and sitemap generation—one weak link duplicates the whole graph.

## Duplicate sources in modern stacks

| Source | Example | Fix |
| --- | --- | --- |
| Protocol | http vs https | 301 to https, canonical https |
| Slash policy | /docs vs /docs/ | Pick one, 301 the other |
| Case | /Pricing vs /pricing | Lowercase redirect |
| Parameters | ?ref=, ?utm_* | Strip in canonical |
| Pagination | ?page=2 | self-canonical or rel prev/next |
| Facets | ?color=red&size=m | noindex or canonical to category |
| SPA routes | same shell, stale head | update link rel=canonical |

Audit with Screaming Frog or Sitebulb after information architecture changes—not once at launch.

## Self-referencing canonical on every indexable page

Even unique pages benefit from self-referencing canonical tags—they protect against parameter injection and external links attaching tracking query strings:

```html
<link rel="canonical" href="https://example.com/pricing" />
```

Next.js App Router:

```typescript
export async function generateMetadata(): Promise<Metadata> {
  return {
    alternates: { canonical: "https://example.com/pricing" },
  };
}
```

Ensure absolute URLs with correct production host—staging canonicals leaking through DNS mistakes deindex production.

## Trailing slash as organization policy

Mixed slash policies duplicate silently. Document decision in next.config, nginx, and sitemap generator together:

```javascript
// next.config.js
module.exports = { trailingSlash: false };
```

```nginx
# Redirect slash-addition if policy is no trailing slash
rewrite ^/(.*)/$ /$1 permanent;
```

Pick policy matching internal links—relative links propagate whichever pattern developers use by habit.

## Parameter handling strategies

**Strip tracking params in canonical only** — page remains accessible with UTMs for analytics; Google consolidates to clean URL.

**Middleware normalization** — redirect unknown params on product pages:

```typescript
export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone();
  const allowed = ["page", "sort"];
  const filtered = new URLSearchParams();
  for (const key of allowed) {
    if (url.searchParams.has(key)) filtered.set(key, url.searchParams.get(key)!);
  }
  url.search = filtered.toString();
  if (url.toString() !== request.url) {
    return NextResponse.redirect(url, 301);
  }
}
```

Faceted navigation generating thousands of thin combinations should noindex or canonical to parent category—Search Console coverage report highlights inflate quickly otherwise.

## HTTP Link header alternative

For non-HTML assets or edge-only control:

```http
Link: <https://example.com/pricing>; rel="canonical"
```

Useful when HTML templates are hard to change but CDN can inject headers. Do not emit both conflicting HTML and HTTP canonicals.

## SPA client navigation updates

React Router or Vue Router must swap canonical on navigation:

```typescript
useEffect(() => {
  let link = document.querySelector('link[rel="canonical"]') as HTMLLinkElement;
  if (!link) {
    link = document.createElement("link");
    link.rel = "canonical";
    document.head.appendChild(link);
  }
  link.href = `https://example.com${location.pathname}`;
}, [location.pathname]);
```

Server-render initial canonical for crawlers that do not execute JavaScript reliably. Client update covers users sharing URLs after in-app navigation.

## hreflang interaction

Multilingual sites pair canonical with hreflang alternates—not duplicate canonical across languages. Each language URL self-canonicals with hreflang pointing siblings.

## Sitemap alignment

Sitemap `<loc>` entries must match canonical URLs exactly—host, slash, and parameter policy. Automated sitemap jobs reading router tables prevent drift when marketing adds landing pages.

## Monitoring in Search Console

Watch Pages → Duplicate without user-selected canonical. Drill into exemplar URLs; trace whether redirect chain, canonical tag, or parameter handling failed. Fix template before requesting recrawl spam.

Compare indexed count to expected indexable inventory monthly—unexplained growth often means parameter or staging leak.

## International and staging isolation

Staging environments need authentication plus noindex—canonical to production is wrong if staging is publicly reachable. Prefer non-indexable domains (`staging.internal`) over noindex alone for confidential pre-release content.

## Resources

- [Google canonical documentation](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
- [MDN link types canonical](https://developer.mozilla.org/en-US/docs/Web/HTML/Attributes/rel#canonical)
- [Next.js metadata alternates](https://nextjs.org/docs/app/api-reference/functions/generate-metadata)
- [RFC 5988 Link header](https://datatracker.ietf.org/doc/html/rfc5988)
- [Screaming Frog canonical report](https://www.screamingfrog.co.uk/seo-spider/)
'''

POSTS["seo-core-web-vitals-ranking"] = '''---
title: "Core Web Vitals and Search Ranking Signals"
slug: "seo-core-web-vitals-ranking"
description: "Page experience signals include CWV — correlation not causation, prioritize user impact over gaming metrics."
datePublished: "2026-10-01"
dateModified: "2026-07-17"
tags: ["SEO", "Core Web Vitals", "Performance"]
keywords: "Core Web Vitals SEO ranking, page experience signals, Google ranking"
faq:
  - q: "Do Core Web Vitals directly determine rankings?"
    a: "They are a ranking signal, but modest compared to relevance, authority, and intent match. Google uses field data from real users in CrUX, not lab scores alone. Failing badly on competitive queries can break tie-rank scenarios."
  - q: "Which Core Web Vital matters most in 2026?"
    a: "INP replaced FID as the responsiveness metric. LCP remains central for load perception. CLS still matters for layout stability. Fix whichever fails at p75 in Search Console for your money templates first."
  - q: "Should I optimize lab or field data?"
    a: "Field data drives eligibility for experience signals. Use Lighthouse and WebPageTest to diagnose regressions locally, but declare success when Search Console and CrUX p75 move from fail to pass over the 28-day rolling window."
---

Forty percent of our product detail templates rated Poor on Largest Contentful Paint in Search Console—while blog posts passed. Competitors on the same commercial queries did not outwrite us; they outloaded us on mid-tier Android over 4G. Core Web Vitals became the tiebreaker Google documentation always implied but marketing rarely prioritized.

Core Web Vitals measure real user experience: how fast main content appears, how quickly pages respond to input, and how much layout shifts during load. They correlate with conversion and support volume even when you ignore SEO entirely.

## Field data versus lab data

| Source | What it measures | Used for |
| --- | --- | --- |
| CrUX / Search Console | Real users, p75 per URL group | Ranking signals, pass/fail |
| Lighthouse | Simulated single session | CI regression, local debug |
| RUM (your analytics) | Your traffic mix | Business correlation |

Lab scores improve by throttling CPU on a developer laptop; field data includes extensions, low memory devices, and congested networks. A green Lighthouse score with Poor field LCP means you optimized the wrong layer—often CDN cache miss or hero image bytes.

## The three metrics in practice

**LCP (Largest Contentful Paint)** — time until largest visible content element renders—usually hero image, heading block, or video poster. Fix image compression, preload LCP resource with `fetchpriority="high"`, eliminate render-blocking CSS/JS above fold, improve TTFB via caching.

**INP (Interaction to Next Paint)** — worst interaction latency across page lifetime (replacing FID). Long JavaScript tasks from analytics, chat widgets, and hydration block input. Break tasks, defer third parties, reduce main-thread work on product templates.

**CLS (Cumulative Layout Shift)** — unexpected layout movement. Reserve space for ads, embeds, and web fonts with size attributes and `font-display: optional` or metrics overrides.

## Ranking signal reality check

Google states page experience—including CWV—is among many signals. Excellent content on a slightly slow page still ranks. Mediocre content on a fast page does not win sustainably.

CWV matter most when:

- Query competition is tight among similar quality results
- Mobile experience is primary traffic share
- Your templates fail Poor threshold at scale

Do not expect +30 positions from LCP alone; expect reduced bounce and improved conversion—which indirectly supports SEO through engagement proxies.

## Diagnosis workflow for failing URL groups

Search Console groups URLs by similar template. Export Poor LCP clusters:

1. Identify LCP element in Chrome DevTools Performance panel
2. Check TTFB—if high, backend or CDN not frontend
3. Check resource load waterfall for LCP candidate
4. Compare crUX by form factor—mobile vs desktop divergence hints image or JS bloat
5. Ship fix to subset route; wait 28 days for CrUX window

Segment RUM by template, not site-wide average—blog passing while PDP fails still hurts revenue queries.

## Fixes that survive deploy

**Images** — AVIF/WebP, responsive `srcset`, explicit width/height, CDN resize parameters.

**Third parties** — load chat and analytics after idle or first interaction; tag managers firing ten pixels on load destroy INP.

**SSR/SSG** — ship meaningful HTML first paint; client-only rendering delays LCP for crawlers and users alike.

**Fonts** — subset, preload critical woff2, avoid invisible text flash causing CLS.

**Server** — cache HTML at edge for anonymous product pages; personalize via edge includes or client fetch after LCP.

## Connecting CWV to business metrics

Tie performance work to conversion on templates that failed CWV, not abstract scores. A/B holdout: delay third-party load on checkout—measure completion rate and INP together. Executive sponsorship follows revenue charts faster than Lighthouse dashboards.

## Anti-patterns

- Chasing 100 Lighthouse while CrUX Poor
- Lazy-loading LCP image (never lazy-load LCP candidate)
- Infinite scroll without pagination hurting crawl and INP
- Client-side A/B hiding LCP element until JS runs
- Ignoring origin trial metrics until Search Console email

## Monitoring cadence

Weekly Search Console CWV report review for new Poor groups. CI Lighthouse budget on key templates. RUM alert when p75 LCP regresses 10% after release. Correlate deploy markers with metric shifts.

Wait full 28-day CrUX window after fix before declaring SEO impact null—early wins show in RUM first.

## Resources

- [web.dev Core Web Vitals](https://web.dev/vitals/)
- [Search Console CWV report](https://support.google.com/webmasters/answer/9205520)
- [CrUX documentation](https://developer.chrome.com/docs/crux)
- [INP guidance](https://web.dev/articles/inp)
- [Google page experience documentation](https://developers.google.com/search/docs/appearance/page-experience)
'''

POSTS["seo-internal-linking-architecture"] = '''---
title: "Internal Linking Architecture for Product Sites"
slug: "seo-internal-linking-architecture"
description: "Internal links distribute PageRank and aid discovery — hub pages, breadcrumbs, and related content modules."
datePublished: "2026-09-27"
dateModified: "2026-07-17"
tags: ["SEO", "Content", "Architecture"]
keywords: "internal linking SEO, site architecture, hub pages"
faq:
  - q: "How many internal links should a page have?"
    a: "There is no magic number. Every link should help users or crawlers reach relevant content. Orphan pages with zero internal inlinks rarely rank regardless of content quality."
  - q: "Do JavaScript-rendered internal links count?"
    a: "Google renders JavaScript and follows DOM links, but discovery is slower than static HTML in main navigation. Put critical links in server-rendered HTML—header, footer, breadcrumbs, and XML sitemap alone are insufficient for large sites."
  - q: "What is a hub page?"
    a: "A page targeting a broad topic that links to detailed spoke pages—consolidating authority, clarifying site structure, and helping users navigate complex product or docs catalogs."
---

One hundred eighty documentation articles had zero internal inlinks—they appeared in Search Console only because the XML sitemap listed them. No hub referenced them; no related-doc module suggested them; navigation stopped at top-level categories. Writers published excellent content into a crawl desert.

Internal linking is site architecture made visible to users and crawlers. Links distribute ranking signals, establish topical relationships, and determine what Google discovers without sitemap hints alone.

## Orphans and crawl budget

An orphan page is reachable only via direct URL or sitemap—no internal anchor path. Crawlers deprioritize orphans because links signal importance. For large docs and ecommerce catalogs, orphans accumulate silently when CMS publishes without editorial linking workflow.

Monthly orphan crawl: sitemap URLs minus crawled inlink graph from Screaming Frog. Assign each orphan to a hub owner for link placement or explicit noindex decision.

## Hub-and-spoke model

Hub pages target head terms and category intent:

```
/features (hub)
  ├── /features/analytics (spoke)
  ├── /features/automation (spoke)
  └── /features/integrations (spoke)
```

Hub copy summarizes subtopics with descriptive anchor text—not "click here." Spokes link back to hub and sideways to related spokes. Depth should not exceed three to four clicks from homepage for commercial pages.

Product marketing launches features without updating hubs when editorial ownership is unclear—define hub updates as part of release checklist.

## Navigation versus contextual links

Global header/footer links repeat on every page—they establish baseline discovery but carry diluted per-link equity compared to in-content contextual links from high-authority pages.

Contextual links from popular blog posts to product pages move needles faster than footer duplicates. Editorial guidelines: two to three internal links per thousand words where naturally relevant.

## Breadcrumbs and structured data

Breadcrumbs aid users and reinforce hierarchy for crawlers:

```html
<nav aria-label="Breadcrumb">
  <ol itemscope itemtype="https://schema.org/BreadcrumbList">
    <li itemprop="itemListElement" itemscope itemtype="https://schema.org/ListItem">
      <a itemprop="item" href="/docs"><span itemprop="name">Docs</span></a>
      <meta itemprop="position" content="1" />
    </li>
    …
  </ol>
</nav>
```

JSON-LD BreadcrumbList mirrors visual trail in SERP snippets—implement both consistently.

## Related content modules

Docs platforms often add "Related articles" from tag overlap or embedding similarity. Rules-based fallback when ML is overkill:

- Same category and tag intersection ≥ 2
- Exclude current page
- Cap at 5 links to avoid clutter

Modules must server-render for crawlers—client-only fetch after idle delays discovery weeks.

## Anchor text discipline

Descriptive anchors ("database migration guide") beat generic ("learn more"). Over-optimized exact-match anchors across thousands of footers trigger spam heuristics—vary naturally.

## Pagination and faceted linking

Category pagination should link prev/next and optionally canonical strategy documented separately. Faceted filters should not generate thousands of thin cross-links from hub footers—noindex or canonical faceted URLs instead of linking every combination from main nav.

## JavaScript SPAs and docs sites

Client routers must emit `<a href>` for internal navigation—not only `onClick` handlers without href. Crawlers improved on JS but hrefless buttons still fail accessibility and SEO.

Static generation of nav trees from filesystem or CMS taxonomy ensures new pages gain links on build—not when someone remembers to update React state.

## Link equity and consolidation

When merging products or retiring URLs, 301 redirect and update internal links—do not rely on redirects alone while old links remain in CMS body content. Search Console link report helps find stale internal targets returning 404.

## Editorial workflow integration

Publishing checklist:

- Assigned hub category selected
- At least two internal outlinks to related content
- At least one expected inlink from hub or related module within sprint
- Breadcrumb path validated

Docs teams without SEO embedded in workflow recreate orphan problems every quarter.

## Measuring internal link health

- Orphan count trend
- Average inlinks per template type
- Crawl depth histogram from log files
- Internal 404s from broken CMS links
- Rankings for hub terms after spoke expansion

Improvement shows over months—not overnight—because recrawl and signal consolidation take time.

## Resources

- [Google site structure guidance](https://developers.google.com/search/docs/crawling-indexing/links-crawlable)
- [Moz internal linking basics](https://moz.com/learn/seo/internal-link)
- [Schema.org BreadcrumbList](https://schema.org/BreadcrumbList)
- [Screaming Frog internal link metrics](https://www.screamingfrog.co.uk/seo-spider/)
- [web.dev accessible navigation patterns](https://web.dev/articles/website-navigation)
'''
