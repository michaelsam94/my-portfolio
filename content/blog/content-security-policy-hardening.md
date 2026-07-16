---
title: "Hardening Content Security Policy"
slug: "content-security-policy-hardening"
description: "A practical guide to Content Security Policy hardening: nonce-based CSP, strict-dynamic, report-only rollout, and the XSS mitigation traps that quietly weaken policies."
datePublished: "2026-03-03"
dateModified: "2026-03-03"
tags: ["Security", "Web", "Frontend"]
keywords: "content security policy, CSP, nonce CSP, XSS mitigation, strict-dynamic, CSP report-only"
faq:
  - q: "What is Content Security Policy and what does it protect against?"
    a: "Content Security Policy (CSP) is an HTTP response header that tells the browser which sources of scripts, styles, images, and other resources are allowed to load and execute on a page. Its primary job is XSS mitigation: even if an attacker injects a script tag, a strict CSP prevents the browser from executing it because the source isn't allowlisted. It also restricts things like framing, form targets, and mixed content."
  - q: "Should I use a nonce-based or hash-based CSP?"
    a: "Use a nonce-based CSP when your server renders pages dynamically and can inject a fresh random nonce per response — it's the most maintainable strict approach. Use hashes when content is static or served from a CDN where you can't generate per-request nonces. Many strong policies combine both, and add 'strict-dynamic' so trusted scripts can load their own dependencies."
  - q: "Why should I roll out CSP in report-only mode first?"
    a: "Content-Security-Policy-Report-Only applies the policy without blocking anything, sending violation reports instead. This lets you discover every inline script, third-party widget, and legacy resource your policy would break before it affects real users. Run it in production for a couple of weeks, fix the reported violations, then switch to the enforcing header."
---

A Content Security Policy is the browser-level backstop for the XSS you didn't catch in code review. Even a well-audited app ships an injection eventually — a templating mistake, a vulnerable dependency, a bit of user content rendered without escaping. A hardened CSP means that when that day comes, the injected script simply doesn't run, because the browser refuses to execute anything the policy didn't explicitly bless. That's the entire value proposition: CSP turns "one XSS bug equals full account compromise" into "one XSS bug equals a violation report."

Most CSPs I audit are theater. They start with good intentions and end with `script-src 'self' 'unsafe-inline'`, which is a policy that permits exactly the inline scripts an attacker injects. Hardening CSP is mostly about removing the escape hatches you added to make it work, and doing so without breaking the site.

## Why `'unsafe-inline'` defeats the point

The most common CSP mistake is allowing inline scripts. The moment your policy contains `'unsafe-inline'` in `script-src`, an attacker who can inject `<script>steal()</script>` wins, because inline scripts are precisely what that directive permits. Domain allowlisting (`script-src cdn.example`) is only marginally better — researchers have repeatedly shown that large allowlists contain bypasses through JSONP endpoints, open redirects, and hosted user content.

The modern consensus, echoed by Google's own CSP evaluator, is to stop allowlisting hosts for scripts and instead allow only scripts you've explicitly marked as trusted, per request, with a nonce or hash. That's a "strict CSP," and it's the target of any real hardening effort.

## Nonce-based policies, done right

A nonce is a random value your server generates fresh for every response and stamps on both the CSP header and each trusted `<script>` tag. The browser runs a script only if its nonce matches.

```
Content-Security-Policy:
  script-src 'nonce-r4Nd0m2026' 'strict-dynamic';
  object-src 'none';
  base-uri 'none';
```

```html
<script nonce="r4Nd0m2026" src="/app.js"></script>
```

Three non-negotiables I enforce on any nonce setup:

- **The nonce must be cryptographically random and unique per response.** A static or predictable nonce is the same as no nonce. Generate at least 128 bits from a CSPRNG.
- **Never reflect user input near the nonce.** If an attacker can guess or read the nonce, they can attach it to their injected script.
- **Add `'strict-dynamic'`.** This lets a trusted (nonced) script load its own dependencies without you allowlisting every CDN, while ignoring host allowlists that older browsers might honor. It's what makes strict CSP maintainable with real-world bundlers.

## Hashes for static content

When you can't generate per-request nonces — static site output, aggressively cached HTML, edge-served pages — hashes are the alternative. You compute the SHA-256 of each inline script's exact contents and list the digest:

```
Content-Security-Policy:
  script-src 'sha256-B2yPHKaXnvFWtRChIbabYmUBFZdVfKKXHbWtWidDVF8=' 'strict-dynamic';
```

The downside is brittleness: change one byte of the script and the hash breaks. I reserve hashes for genuinely static inline snippets and let the build pipeline compute them, never a human.

## Roll out with report-only, always

Never ship a strict CSP straight to enforcement. The `Content-Security-Policy-Report-Only` header applies the policy, blocks nothing, and posts JSON violation reports to an endpoint you specify. This is how you find the surprises — the analytics snippet a marketer added through a tag manager, the inline `onclick` handler in a legacy template, the third-party chat widget nobody documented.

```
Content-Security-Policy-Report-Only:
  script-src 'nonce-r4Nd0m2026' 'strict-dynamic';
  report-to csp-endpoint;
```

Run report-only in production for a real traffic cycle — I use two weeks minimum to catch weekly batch jobs and infrequent flows. Triage the reports, fix or nonce the legitimate scripts, and only then flip to the enforcing header. Deciding which violations are real threats versus noise is where a bit of structured [threat modeling with STRIDE](https://blog.michaelsam94.com/threat-modeling-stride/) pays off, because it forces you to reason about the actual attacker rather than chasing every console warning.

## Directives beyond `script-src`

Hardening isn't only about scripts. The directives that quietly matter:

| Directive | Why it matters | Hardened value |
| --- | --- | --- |
| `object-src` | Blocks Flash/plugin-based injection | `'none'` |
| `base-uri` | Stops `<base>` tag hijacking of relative URLs | `'none'` |
| `frame-ancestors` | Clickjacking defense; replaces X-Frame-Options | `'self'` or explicit list |
| `form-action` | Prevents forms POSTing to attacker origins | `'self'` |
| `require-trusted-types-for` | DOM-XSS defense via Trusted Types | `'script'` |

`object-src 'none'` and `base-uri 'none'` are close to free and close required for a policy to count as strict. `frame-ancestors` is your clickjacking control and pairs naturally with the cross-origin thinking in [CSRF and CORS on the modern web](https://blog.michaelsam94.com/csrf-cors-modern-web/) — same-origin discipline shows up everywhere in browser security. Trusted Types is the ambitious one: it forces DOM sinks like `innerHTML` to accept only sanitized, typed values, closing off DOM-based XSS that even a strict script policy can miss.

## The honest tradeoffs

CSP hardening is not free, and I won't pretend otherwise. Nonces require server-side rendering or an edge worker to inject them, which complicates fully static hosting. `strict-dynamic` isn't understood by very old browsers, so you keep a host-based fallback for them (harmless, since modern browsers ignore it when a nonce is present). Third-party scripts that use inline event handlers or `eval` will fight you, and some vendors simply never fixed their code — you'll either drop them or sandbox them in an iframe.

My rule after shipping this on a few production apps: budget the report-only phase generously, automate nonce injection so developers never hand-write one, and treat every `'unsafe-inline'` or `'unsafe-eval'` in a PR as a blocking review comment. A CSP that took a week to harden and blocks one real XSS has already paid for itself many times over. The mediocre `'self' 'unsafe-inline'` policy, by contrast, is a checkbox that protects nothing.

## Resources

- [MDN — Content Security Policy (CSP)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CSP)
- [W3C — Content Security Policy Level 3](https://www.w3.org/TR/CSP3/)
- [Google Web Fundamentals — Strict CSP](https://web.dev/articles/strict-csp)
- [OWASP — Content Security Policy Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html)
- [CSP Evaluator by Google](https://csp-evaluator.withgoogle.com/)
- [MDN — Trusted Types API](https://developer.mozilla.org/en-US/docs/Web/API/Trusted_Types_API)
