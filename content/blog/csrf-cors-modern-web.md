---
title: "CSRF and CORS in the Modern Web"
slug: "csrf-cors-modern-web"
description: "CSRF and CORS explained for engineers: how SameSite cookies, CSRF tokens, and preflight requests actually protect cross-origin requests — and where they don't."
datePublished: "2026-02-04"
dateModified: "2026-02-04"
tags: ["Security", "Web", "Frontend"]
keywords: "CSRF, CORS, SameSite cookies, cross-origin, CSRF tokens, web security, preflight requests"
faq:
  - q: "What is the difference between CSRF and CORS?"
    a: "CSRF (Cross-Site Request Forgery) is an attack where a malicious site tricks a user's browser into making an authenticated request to your app using cookies the browser sends automatically. CORS (Cross-Origin Resource Sharing) is a browser mechanism that controls which origins can read responses from your API via JavaScript. CSRF is a threat you defend against; CORS is a policy you configure — and importantly, CORS is not a CSRF defense."
  - q: "Do SameSite cookies make CSRF tokens unnecessary?"
    a: "SameSite=Lax or Strict blocks most classic CSRF because the browser withholds the cookie on cross-site requests. But it is defense-in-depth, not a complete replacement. Older browsers, same-site subdomain attacks, and GET-based state changes can still slip through, so security-sensitive apps keep CSRF tokens on top of SameSite."
  - q: "Does enabling CORS make my API less secure?"
    a: "CORS itself doesn't weaken your API — it's an allowlist that relaxes the same-origin policy for specific origins you trust. The danger is misconfiguration: reflecting the Origin header blindly or using a wildcard with credentials effectively disables the protection. Configure explicit allowed origins and only send credentials to origins you control."
---

Two of the most misunderstood acronyms in web security sit right next to each other in every code review I do: CSRF and CORS. They sound similar, they both involve "cross-origin," and engineers routinely reach for one to solve a problem that belongs to the other. CSRF is an *attack* that abuses the browser's habit of attaching cookies to every request; CORS is a *browser policy* that decides which origins may read your API responses from JavaScript. Getting the distinction right is the difference between a secure app and one that just looks secure.

I've watched teams "fix" a CSRF finding by loosening CORS, which does nothing, and I've watched others break their own SPA by locking CORS down while ignoring the actual forgery risk. Let me untangle both, because the mental model is what keeps you from those mistakes.

## What CSRF actually exploits

CSRF works because the browser is helpful to a fault. When a request goes to `bank.example`, the browser automatically attaches any cookies scoped to that domain — including your session cookie — regardless of which site *initiated* the request. So if you're logged into your bank and you visit `evil.example`, a hidden form on that page can POST to `bank.example/transfer` and the browser cheerfully includes your session cookie. The server sees an authenticated request and processes it.

The critical detail: the attacker never *reads* the response. They don't need to. The side effect — money moved, email changed, account deleted — is the whole payload. That's why CSRF is a "write" attack. It also explains why CORS doesn't help: CORS controls whether JavaScript can *read* a cross-origin response, but the forged request already fired and the damage is done before any response is inspected.

## SameSite cookies: the modern first line

The single biggest shift in CSRF defense over the last few years is `SameSite` cookies, now defaulting to `Lax` in every major browser. A cookie marked `SameSite=Lax` is simply not sent on cross-site subrequests like a POST from another origin, which neuters the classic form-POST attack.

```
Set-Cookie: session=abc123; HttpOnly; Secure; SameSite=Lax; Path=/
```

The three flavors, and how I choose:

| Value | Cookie sent cross-site? | Use when |
| --- | --- | --- |
| `Strict` | Never | High-value actions, admin panels, banking |
| `Lax` | Only on top-level GET navigations | Default for most session cookies |
| `None` | Always (requires `Secure`) | Third-party embeds, cross-site SSO |

`Lax` is the right default for almost everyone. Reach for `Strict` on cookies that guard destructive actions, accepting that a user following a link from an email won't arrive already-authenticated. Only use `None` when you genuinely need the cookie in a cross-site context, and never without `Secure`.

## Why tokens still earn their place

SameSite is excellent, but I don't treat it as a complete CSRF defense on anything that matters. The gaps are real: some embedded webviews and older clients don't honor it consistently, sibling subdomains can be "same-site" for cookie purposes while being controlled by different teams, and any state-changing GET endpoint sidesteps `Lax` entirely (which is a good reason to never mutate state on GET).

The synchronizer token pattern remains the belt to SameSite's suspenders. The server issues an unpredictable token, embeds it in the form or a response header, and requires it back on every mutating request. Because a cross-origin attacker can't read the token (the same-origin policy stops them), they can't forge a valid request.

```javascript
// Double-submit cookie variant: token in a cookie AND echoed in a header
app.post("/transfer", (req, res) => {
  const cookieToken = req.cookies["csrf"];
  const headerToken = req.get("X-CSRF-Token");
  if (!cookieToken || cookieToken !== headerToken) {
    return res.status(403).send("CSRF check failed");
  }
  // ...process transfer
});
```

For token-based auth (bearer tokens in an `Authorization` header rather than cookies), CSRF largely evaporates, because the browser doesn't auto-attach `Authorization` headers. That's one reason many API-first designs prefer header tokens — though then you inherit XSS-driven token theft as the risk to manage, which ties directly into [hardening your Content Security Policy](https://blog.michaelsam94.com/content-security-policy-hardening/).

## CORS: what it does and doesn't do

CORS is the browser relaxing the same-origin policy under controlled conditions. By default, JavaScript on `app.example` can *send* a request to `api.other.example` but can't *read* the response. CORS lets the server opt specific origins back in.

For "non-simple" requests — anything with a custom header, a JSON content type, or methods like `PUT`/`DELETE` — the browser first fires a **preflight** `OPTIONS` request asking permission:

```
OPTIONS /orders HTTP/1.1
Origin: https://app.example
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type, x-csrf-token

HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://app.example
Access-Control-Allow-Methods: POST, GET, OPTIONS
Access-Control-Allow-Headers: content-type, x-csrf-token
Access-Control-Allow-Credentials: true
Access-Control-Max-Age: 600
```

The trap I keep seeing in production: reflecting the `Origin` header straight back into `Access-Control-Allow-Origin` to "support all our frontends." Combined with `Allow-Credentials: true`, that's an open door — any site becomes a trusted origin that can read authenticated responses. Use an explicit allowlist, validate against it, and never pair a wildcard `*` with credentials (the spec forbids it, but people work around it and regret it).

## Putting the two together

The reason these belong in one article is that a secure app needs both, playing different positions. CORS decides who can *read* your API from a browser. CSRF defenses decide whether an authenticated *write* was actually intended by your user. Neither substitutes for the other.

My default recipe for a cookie-authenticated web app in 2026:

- Session cookies are `HttpOnly`, `Secure`, and `SameSite=Lax` (or `Strict` for sensitive scopes).
- Mutating endpoints require a CSRF token, validated server-side, even with SameSite in place.
- CORS uses an explicit origin allowlist, with `Allow-Credentials` only for origins you own.
- No state changes on `GET`, ever — this keeps the SameSite=Lax guarantee meaningful.
- Layer authentication itself on something phishing-resistant where possible, like [passkeys and WebAuthn](https://blog.michaelsam94.com/passkeys-webauthn-implementation/), so a stolen session is harder to obtain in the first place.

The honest downside of all this is friction: preflights add a round trip, CSRF tokens add plumbing, and `SameSite=Strict` breaks some cross-site link flows. I accept every bit of it, because the failure mode on the other side is a user's account being drained by a page they never knowingly interacted with. Get the model straight — CSRF is the attack, CORS is the policy — and the configuration follows naturally.

## Resources

- [MDN — Cross-Site Request Forgery (CSRF)](https://developer.mozilla.org/en-US/docs/Web/Security/Attacks/CSRF)
- [MDN — Cross-Origin Resource Sharing (CORS)](https://developer.mozilla.org/en-US/docs/Web/HTTP/Guides/CORS)
- [OWASP — CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [MDN — SameSite cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Set-Cookie/SameSite)
- [Fetch Standard — CORS protocol](https://fetch.spec.whatwg.org/#http-cors-protocol)
