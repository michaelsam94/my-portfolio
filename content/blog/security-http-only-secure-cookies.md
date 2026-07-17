---
title: "HttpOnly and Secure Cookie Configuration"
slug: "security-http-only-secure-cookies"
description: "Session cookies need HttpOnly, Secure, SameSite — __Host- prefix rules and subdomain cookie scope."
datePublished: "2026-10-21"
dateModified: "2026-07-17"
tags: ["Security", "Cookies", "Auth"]
keywords: "HttpOnly Secure cookie, SameSite cookie, session cookie security"
faq:
  - q: "What does HttpOnly do?"
    a: "Prevents JavaScript from reading the cookie, reducing XSS exfiltration risk."
  - q: "Secure flag requirement?"
    a: "Cookies with Secure send only over HTTPS — required for session cookies."
  - q: "SameSite for auth?"
    a: "Lax for OAuth return flows; Strict when cross-site POST is never needed."---

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

## Sustaining production quality

Scan staging and production Set-Cookie headers after every auth-related deploy. Cookie prefixes __Host- and __Secure- add defense when supported browsers are your baseline. Document SameSite choice in ADR when OAuth or embedded widgets require cross-site cookies — Strict breaks more flows than teams expect.

## Cookie prefix hardening

`__Host-` prefix requires Secure, Path=/, and no Domain attribute — strongest session cookie shape for modern browsers. Integration test Set-Cookie on login in production profile after every auth deploy.

## OAuth and SameSite=Lax

OAuth return flows break with SameSite=Strict on session cookies — the cross-site redirect from the IdP will not send cookies. Use Lax for session cookies on auth flows; Strict only when UX allows intermediate landing pages.

## Resources

- [MDN Set-Cookie](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie)
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html)
- [Chrome SameSite updates](https://developers.google.com/privacy-sandbox/3pcd)
- [RFC 6265bis cookie prefixes](https://datatracker.ietf.org/doc/html/draft-ietf-httpbis-rfc6265bis)
- [web.dev SameSite cookies explained](https://web.dev/articles/samesite-cookies-explained)

## Operational checklist (1)

Before promoting Security Http Only Secure Cookies changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (2)

Re-baseline Security Http Only Secure Cookies after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (3)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Http Only Secure Cookies touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (4)

Before promoting Security Http Only Secure Cookies changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (5)

Re-baseline Security Http Only Secure Cookies after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (6)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Http Only Secure Cookies touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (7)

Before promoting Security Http Only Secure Cookies changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.

## Field validation (8)

Re-baseline Security Http Only Secure Cookies after browser upgrades or CDN configuration changes. Mobile share above seventy percent shifts median device class — optimizations tuned on desktop lab profiles may not transfer.

## Coordination (9)

Align with platform and backend owners on cache TTL, deploy windows, and API contracts when Security Http Only Secure Cookies touches shared infrastructure — single-layer wins often disappear when another tier invalidates caches.

## Operational checklist (10)

Before promoting Security Http Only Secure Cookies changes, confirm observability dashboards cover error rate and p75 latency for affected routes, rollback is documented in the pull request, and a staging drill reproduced the last known failure mode.
